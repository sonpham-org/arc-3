#!/usr/bin/env python3
"""
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: The Spark runner service behind the Mode explorer's Play button (arc3.sonpham.net/mode-explorer.html).
  Runs on Jethro (DGX Spark gx10-a424) as the systemd user service arc3-runner, published over HTTPS with Tailscale
  Funnel. FastAPI on 127.0.0.1:8787.
  Endpoints (CORS allows https://arc3.sonpham.net only):
    GET  /api/health                  runner + model server status (public)
    GET  /api/stuck-points            games with a verified-or-not snapshot, stuck level, source (public)
    GET  /api/jobs[?game=]            job list with per-sample progress (public, no prompts or trajectories)
    GET  /api/jobs/{id}               one job: spec summary, per-sample progress and results (public)
    POST /api/play                    queue a job (bearer key)
    POST /api/jobs/{id}/cancel        cancel queued/running samples (bearer key)
    GET  /api/jobs/{id}/samples/{k}/turns   per-turn log of one sample (bearer key)
  A job = one game's stuck point, one variant (son|daniel), one scheme (ordered slots of mode + prompt + settings)
  and N samples (default 10). Samples run as separate sample.py processes, at most ARC3_RUNNER_CONCURRENCY at a
  time across all jobs (default 4, sized for the two-Spark server speed), first queued first served. State lives
  in ~/arc3-runner/jobs/<id>/ (spec.json, job.json, samples/<k>/...); a restart marks running samples as
  interrupted and requeues them. Old trajectories are pruned when the jobs folder passes ARC3_RUNNER_MAX_GB.
SRP/DRY check: Pass - the game is played only by sample.py through Son's harness; prompts come from the page's
  modes.json copy (or the user's custom mode text); this file is queueing, auth and reporting.
"""
from __future__ import annotations

import hmac
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import requests
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from modes import ModeError, build_delta  # noqa: E402

HOME = Path(os.environ.get("ARC3_RUNNER_HOME", Path.home() / "arc3-runner"))
JOBS = HOME / "jobs"
SNAPSHOTS = Path(os.environ.get("ARC3_RUNNER_SNAPSHOTS", HOME / "snapshots"))
KEY_FILE = Path(os.environ.get("ARC3_RUNNER_KEY_FILE", HOME / "runner.key"))
MODEL_BASE_URL = os.environ.get("ARC3_RUNNER_MODEL_URL", "http://127.0.0.1:11234/v1")
MODEL_ID = os.environ.get("ARC3_RUNNER_MODEL_ID", "qwen3.8-flash-next")
CONCURRENCY = int(os.environ.get("ARC3_RUNNER_CONCURRENCY", "4"))
MAX_GB = float(os.environ.get("ARC3_RUNNER_MAX_GB", "40"))
PYTHON = os.environ.get("ARC3_RUNNER_PYTHON", sys.executable)
ORIGINS = [o for o in os.environ.get("ARC3_RUNNER_ORIGINS", "https://arc3.sonpham.net").split(",") if o]
CODE_RE = re.compile(r"^[a-z0-9]{4}$")
# House rule of this repo's run scripts: the eight held-out games stay out of prompt tuning.
HELD_OUT = ("vc33", "ar25", "sb26", "re86", "su15", "tr87", "tu93", "as66")
ALLOW_HELD_OUT = os.environ.get("ARC3_RUNNER_ALLOW_HELD_OUT", "") == "1"
JOB_RE = re.compile(r"^[a-z0-9-]{8,40}$")

app = FastAPI(title="ARC-3 Spark runner", docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["GET", "POST"],
                   allow_headers=["Authorization", "Content-Type"], max_age=600)
LOCK = threading.RLock()
PROCS: dict[tuple[str, int], subprocess.Popen] = {}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1))
    tmp.replace(path)


def require_key(authorization: str = Header(default="")) -> None:
    expected = KEY_FILE.read_text().strip() if KEY_FILE.exists() else ""
    given = authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""
    if not expected or not given or not hmac.compare_digest(given, expected):
        raise HTTPException(status_code=401, detail="runner key missing or wrong")


# ------------------------------------------------------------------ request model

class Settings(BaseModel):
    temperature: float | None = Field(default=0.6, ge=0, le=2)
    thinking: bool | None = True
    effort: Literal["default", "low", "medium", "high"] | None = "default"
    thinking_budget: int | None = Field(default=None, ge=256, le=32768)
    tool_calls: int | None = Field(default=None, ge=1, le=50)
    actions: int | None = Field(default=None, ge=1, le=500)


class Slot(BaseModel):
    mode: str = Field(min_length=1, max_length=64)
    name: str | None = Field(default=None, max_length=64)
    base: Literal["turn", "game_over", "level_start"] = "turn"
    prompt: str = Field(min_length=1, max_length=20000)          # the mode's text as shown on the page
    stock_template: str = Field(min_length=1, max_length=20000)  # Stock text of the same surface and variant
    settings: Settings = Settings()


class PlayRequest(BaseModel):
    game: str
    stuck_level: int = Field(ge=1, le=12)
    variant: Literal["son", "daniel"] = "son"
    scheme: list[Slot] = Field(default_factory=list, max_length=40)
    stock: Slot
    samples: int = Field(default=10, ge=1, le=20)
    max_actions: int = Field(default=250, ge=10, le=1000)
    max_turns: int = Field(default=20, ge=1, le=60)
    max_minutes: int = Field(default=75, ge=5, le=180)
    levels_to_play: int = Field(default=1, ge=1, le=9)
    label: str | None = Field(default=None, max_length=120)
    by: str | None = Field(default=None, max_length=120)

    @field_validator("game")
    @classmethod
    def game_code(cls, v: str) -> str:
        if not CODE_RE.fullmatch(v):
            raise ValueError("game must be a four-character game code")
        return v


# ------------------------------------------------------------------ helpers

def snapshot_path(game: str) -> Path:
    return SNAPSHOTS / f"{game}.json"


def stuck_points() -> list[dict]:
    index = read_json(SNAPSHOTS / "index.json", {}) or {}
    verified = read_json(SNAPSHOTS / "verified.json", {}) or {}
    out = []
    for s in index.get("snapshots", []):
        v = verified.get(s["game"])
        out.append({**s, "replay_verified": bool(v and v.get("ok")), "replay_checked": v.get("checked") if v else None,
                    "held_out": s["game"] in HELD_OUT, "playable": bool(v and v.get("ok")) and (ALLOW_HELD_OUT or s["game"] not in HELD_OUT)})
    return out


def model_status() -> dict:
    t0 = time.time()
    try:
        r = requests.get(f"{MODEL_BASE_URL.rstrip('/')}/models", timeout=5)
        ids = [m.get("id") for m in r.json().get("data", [])]
        return {"reachable": True, "model_ids": ids, "serves_expected_model": MODEL_ID in ids,
                "ms": int((time.time() - t0) * 1000)}
    except Exception as exc:  # noqa: BLE001 - reported, not raised
        return {"reachable": False, "error": type(exc).__name__}


def job_view(job_id: str, *, full: bool = False) -> dict | None:
    d = JOBS / job_id
    job = read_json(d / "job.json")
    if job is None:
        return None
    samples = []
    for k in range(job["samples"]):
        sd = d / "samples" / str(k)
        res = read_json(sd / "result.json")
        prog = read_json(sd / "progress.json")
        state = job["sample_state"][k]
        row = {"sample": k, "state": state}
        if prog:
            row["progress"] = {x: prog.get(x) for x in ("status", "turn", "mode", "actions", "level", "levels_cleared", "updated", "error")}
        if res:
            row["result"] = {x: res.get(x) for x in ("outcome", "levels_cleared", "actions_used", "turns", "modes_run",
                                                       "final_level", "seconds", "error", "replay_verified", "generated_tokens")}
        samples.append(row)
    view = {k: job[k] for k in ("id", "created", "game", "stuck_level", "variant", "samples", "status", "label", "by",
                                "caps", "scheme_summary", "model", "conversation_exact", "finished")}
    view["sample_rows"] = samples
    done = [s["result"] for s in samples if s.get("result")]
    view["summary"] = {
        "finished_samples": len(done),
        "cleared": sum(1 for r in done if r["outcome"] in ("cleared", "won")),
        "errors": sum(1 for r in done if r["outcome"] == "error"),
        "mean_actions": round(sum(r["actions_used"] or 0 for r in done) / len(done), 1) if done else None,
        "levels_gained": sum(r["levels_cleared"] or 0 for r in done),
    }
    return view


def update_job(job_id: str, fn) -> dict:
    with LOCK:
        path = JOBS / job_id / "job.json"
        job = read_json(path)
        fn(job)
        write_json(path, job)
        return job


def prune_disk() -> None:
    def size(p: Path) -> int:
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    dirs = sorted((p for p in JOBS.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime)
    total = sum(size(p) for p in dirs)
    for p in dirs:
        if total <= MAX_GB * 1e9:
            break
        job = read_json(p / "job.json") or {}
        if job.get("status") not in ("done", "cancelled"):
            continue
        for sd in (p / "samples").glob("*"):
            for name in ("transcript.txt", "viewer.json", "artifacts", "transcripts", "solver_analysis"):
                t = sd / name
                if t.is_dir():
                    total -= size(t); shutil.rmtree(t, ignore_errors=True)
                elif t.exists():
                    total -= t.stat().st_size; t.unlink()
        update_job(p.name, lambda j: j.__setitem__("trajectories_pruned", now()))


# ------------------------------------------------------------------ scheduler

def scheduler() -> None:
    while True:
        try:
            tick()
        except Exception as exc:  # noqa: BLE001
            print("scheduler error:", repr(exc), flush=True)
        time.sleep(2)


def tick() -> None:
    with LOCK:
        # reap finished processes
        for (job_id, k), proc in list(PROCS.items()):
            if proc.poll() is None:
                continue
            PROCS.pop((job_id, k))
            res = read_json(JOBS / job_id / "samples" / str(k) / "result.json")

            def mark(j, k=k, res=res):
                if j["sample_state"][k] == "running":
                    j["sample_state"][k] = "done" if res else ("cancelled" if j.get("cancel") else "failed")
            update_job(job_id, mark)
        # finish jobs
        jobs = sorted((read_json(p / "job.json") for p in JOBS.iterdir() if (p / "job.json").exists()),
                      key=lambda j: j["created"])
        for job in jobs:
            if job["status"] in ("queued", "running") and all(s in ("done", "failed", "cancelled") for s in job["sample_state"]):
                update_job(job["id"], lambda j: j.update(status="cancelled" if j.get("cancel") else "done", finished=now()))
                prune_disk()
        # start samples, oldest job first
        free = CONCURRENCY - len(PROCS)
        for job in jobs:
            if free <= 0:
                break
            if job["status"] not in ("queued", "running") or job.get("cancel"):
                continue
            for k, s in enumerate(job["sample_state"]):
                if free <= 0:
                    break
                if s != "queued":
                    continue
                log = open(JOBS / job["id"] / "samples" / f"{k}.log", "ab")
                (JOBS / job["id"] / "samples" / str(k)).mkdir(parents=True, exist_ok=True)
                PROCS[(job["id"], k)] = subprocess.Popen(
                    [PYTHON, str(HERE / "sample.py"), str(JOBS / job["id"]), str(k)],
                    stdout=log, stderr=subprocess.STDOUT, cwd=str(JOBS / job["id"]), start_new_session=True)
                free -= 1

                def started(j, k=k):
                    j["sample_state"][k] = "running"
                    j["status"] = "running"
                update_job(job["id"], started)


def recover() -> None:
    JOBS.mkdir(parents=True, exist_ok=True)
    for p in JOBS.iterdir():
        job = read_json(p / "job.json")
        if not job or job["status"] not in ("queued", "running"):
            continue

        def fix(j):
            for k, s in enumerate(j["sample_state"]):
                if s == "running":   # the process died with the service; play it again from the snapshot
                    j["sample_state"][k] = "queued"
                    shutil.rmtree(p / "samples" / str(k), ignore_errors=True)
            j.setdefault("restarts", []).append(now())
        update_job(p.name, fix)


@app.on_event("startup")
def _startup() -> None:
    recover()
    threading.Thread(target=scheduler, daemon=True).start()


# ------------------------------------------------------------------ routes

@app.get("/api/health")
def health() -> dict:
    with LOCK:
        running = len(PROCS)
    queued = 0
    for p in JOBS.iterdir():
        j = read_json(p / "job.json")
        if j and j["status"] in ("queued", "running"):
            queued += sum(1 for s in j["sample_state"] if s == "queued")
    return {"ok": True, "time": now(), "concurrency": CONCURRENCY, "samples_running": running, "samples_queued": queued,
            "model": {"base_url_kind": "two-Spark Flash-Next server (via tunnel)", "model_id": MODEL_ID, **model_status()},
            "snapshots": len(stuck_points())}


@app.get("/api/stuck-points")
def get_stuck_points() -> dict:
    return {"stuck_points": stuck_points()}


@app.get("/api/jobs")
def list_jobs(game: str | None = None, limit: int = 50) -> dict:
    rows = []
    for p in JOBS.iterdir():
        j = read_json(p / "job.json")
        if j and (game is None or j["game"] == game):
            rows.append(j)
    rows.sort(key=lambda j: j["created"], reverse=True)
    return {"jobs": [job_view(j["id"]) for j in rows[: max(1, min(limit, 200))]]}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    if not JOB_RE.fullmatch(job_id):
        raise HTTPException(404, "no such job")
    view = job_view(job_id)
    if view is None:
        raise HTTPException(404, "no such job")
    return view


@app.get("/api/jobs/{job_id}/samples/{k}/turns", dependencies=[Depends(require_key)])
def sample_turns(job_id: str, k: int) -> dict:
    if not JOB_RE.fullmatch(job_id):
        raise HTTPException(404, "no such job")
    path = JOBS / job_id / "samples" / str(k) / "turns.jsonl"
    if not path.exists():
        return {"turns": []}
    return {"turns": [json.loads(x) for x in path.read_text().splitlines() if x.strip()]}


@app.post("/api/play", dependencies=[Depends(require_key)])
def play(req: PlayRequest) -> dict:
    if req.game in HELD_OUT and not ALLOW_HELD_OUT:
        raise HTTPException(403, f"{req.game} is one of the eight held-out games, which this runner does not play "
                                 "(they stay out of prompt tuning); Son can switch that off on the runner")
    snap_file = snapshot_path(req.game)
    snap = read_json(snap_file)
    if snap is None:
        raise HTTPException(404, f"no starting point for {req.game}: nothing to play from")
    if snap["stuck_level"] != req.stuck_level:
        raise HTTPException(409, f"the snapshot for {req.game} starts at level {snap['stuck_level']}, "
                                 f"not {req.stuck_level}; only the stuck level is available for now")
    verified = (read_json(SNAPSHOTS / "verified.json", {}) or {}).get(req.game)
    if not verified or not verified.get("ok"):
        raise HTTPException(409, f"the snapshot for {req.game} has not passed its replay check")
    slots = []
    for i, s in enumerate(req.scheme + [req.stock]):
        try:
            build_delta(s.mode, s.stock_template, s.prompt)
        except ModeError as exc:
            raise HTTPException(422, f"slot {i + 1}: {exc}")
        d = s.model_dump()
        d["key"] = f"{i}:{s.mode}"
        d["settings"] = s.settings.model_dump()
        slots.append(d)
    job_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    d = JOBS / job_id
    (d / "samples").mkdir(parents=True)
    spec = {"game": req.game, "stuck_level": req.stuck_level, "variant": req.variant, "scheme": slots[:-1],
            "stock": slots[-1], "snapshot_path": str(snap_file),
            "caps": {"max_actions": req.max_actions, "max_turns": req.max_turns, "max_minutes": req.max_minutes, "levels_to_play": req.levels_to_play},
            "model": {"base_url": MODEL_BASE_URL, "model_id": MODEL_ID}}
    write_json(d / "spec.json", spec)
    job = {"id": job_id, "created": now(), "game": req.game, "stuck_level": req.stuck_level, "variant": req.variant,
           "samples": req.samples, "status": "queued", "label": req.label, "by": req.by, "caps": spec["caps"],
           "scheme_summary": [{"mode": s["mode"], "name": s.get("name"), "settings": s["settings"]} for s in slots[:-1]],
           "model": {"model_id": MODEL_ID}, "conversation_exact": bool(snap["conversation"]["exact"]),
           "sample_state": ["queued"] * req.samples, "finished": None}
    write_json(d / "job.json", job)
    return {"job": job_id, "queued_samples": req.samples}


@app.post("/api/jobs/{job_id}/cancel", dependencies=[Depends(require_key)])
def cancel(job_id: str) -> dict:
    if not JOB_RE.fullmatch(job_id) or not (JOBS / job_id / "job.json").exists():
        raise HTTPException(404, "no such job")
    with LOCK:
        def fn(j):
            j["cancel"] = now()
            j["sample_state"] = ["cancelled" if s == "queued" else s for s in j["sample_state"]]
        update_job(job_id, fn)
        for (jid, k), proc in list(PROCS.items()):
            if jid == job_id and proc.poll() is None:
                try:
                    os.killpg(proc.pid, 15)
                except ProcessLookupError:
                    pass
    return {"job": job_id, "cancelled": True}
