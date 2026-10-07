#!/usr/bin/env python3
"""
Author: Claude Opus 5.5 (Bubba)
Date: 07-October-2026 (Watch events endpoint; first written 06-October-2026)
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
    GET  /api/jobs/{id}/samples/{k}/events?after=&limit=   the sample's trace-viewer events from index `after`, for the
                                      site's Watch view (7-Oct, Son: "click on each currently being played game and
                                      view it"); bearer key
    GET  /api/exact-starts            exact level-start checkpoints: per game, level and variant, the chosen one (public)
    POST /api/settings                harvest on/off and lanes (bearer key)
    GET  /api/start-board?game=&level=&variant=&context=   the board at the start Play would use there (boards.py; public)
    GET  /api/replay-starts           per trainable game, the levels a No-context job can start from (replays.py; public)
    POST /api/preview-request         {game, level, variant, context, prompt_profile, mode, name, instructions}: the exact
                                      first request Play would send there with that mode, rendered with no model
                                      (render_requests.py), plus the duplicate check of it (dupcheck.py); key needed
  A job = one game's starting level, one variant (son|daniel), one scheme (ordered slots of mode + prompt + settings)
  and N samples (default 10). The start is EXACT when an exact checkpoint exists for that game, level and variant
  (checkpoints.py: full request body, harness state, actions from RESET, written whenever a level is cleared);
  otherwise level 1 starts a fresh game from RESET (any public game; added 6-Oct for the page's level buttons), and
  any other level the stuck-level snapshot with its conversation rebuilt from the site's transcripts ("rebuilt").
  Context (added 6-Oct, Son: "Add a 'non-context' mode too"): a Play job carries context ("carried", the default and
  everything above) or not ("none"). A No-context job starts the chosen level at that level's start board, reached by a
  verified replay (replays.py: exact checkpoint actions, else the original game's winning line; level 1 a fresh game),
  with a new game's first turn: the harness system prompt and its normal first prompt for that board, no earlier
  turns, no retained functions. Its samples write no checkpoints. Old jobs without the field carried context.
  Harvest (default on, ARC3_RUNNER_HARVEST / settings.json): while no Play sample is queued or running, one or two
  one-sample Stock runs from RESET on the public games outside the held-out eight, only to collect exact checkpoints
  for every level they clear. A queued Play job pre-empts them at once (process group killed, job "preempted";
  checkpoints already written stay). One Play job at a time (Son, 6-Oct): the oldest unfinished Play job gets every
  lane (ARC3_RUNNER_CONCURRENCY, default 4, sized for the two-Spark server speed) and the others wait whole, first
  come first served, each job view carrying its place_in_line (1 = playing now). Samples run as separate sample.py
  processes. State lives
  in ~/arc3-runner/jobs/<id>/ (spec.json, job.json, samples/<k>/...); a restart marks running samples as
  interrupted and requeues them. Old trajectories are pruned when the jobs folder passes ARC3_RUNNER_MAX_GB.
SRP/DRY check: Pass - the game is played only by sample.py through Son's harness; prompts come from the page's
  modes.json copy (or the user's custom mode text); this file is queueing, auth and reporting.
"""
from __future__ import annotations

import hashlib
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
import checkpoints  # noqa: E402
import replays  # noqa: E402
import prompt_profiles  # noqa: E402
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
# 7-Oct-2026 (Boss, agreed by Son, #arc-3): the old eight-game fence is lifted. Synthetic games are the main
# holdouts now; Functional Tiles (ft09) and one more easy official game are held out only from WRITING the
# public-wisdom rulebook and stay playable here, since measuring on them is the point.
HELD_OUT: tuple = ()
ALLOW_HELD_OUT = os.environ.get("ARC3_RUNNER_ALLOW_HELD_OUT", "") == "1"
JOB_RE = re.compile(r"^[a-z0-9-]{8,40}$")
ENV_DIR = Path(os.environ.get("ARC3_RUNNER_ENVIRONMENTS", HOME / "environment_files"))
SETTINGS_FILE = HOME / "settings.json"
DEFAULT_SETTINGS = {"harvest": os.environ.get("ARC3_RUNNER_HARVEST", "1") == "1",
                    "harvest_lanes": int(os.environ.get("ARC3_RUNNER_HARVEST_LANES", "2"))}
# Harvest sample caps: long enough to clear early levels from RESET, short enough to rotate through the games.
HARVEST_CAPS = {"max_actions": 400, "max_turns": 40, "max_minutes": 150, "levels_to_play": 9}
HARVEST_VARIANT = os.environ.get("ARC3_RUNNER_HARVEST_VARIANT", "son")
TERMINAL = ("done", "failed", "cancelled", "preempted", "interrupted")

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
    # The mode's turn-only instructions (prompt_profiles.py; empty for Stock). Pages from before 6-Oct send the
    # full template instead (prompt + stock_template); sample.slot_instructions turns that into instructions.
    instructions: str | None = Field(default=None, max_length=4000)
    prompt: str | None = Field(default=None, max_length=20000)
    stock_template: str | None = Field(default=None, max_length=20000)
    settings: Settings = Settings()


class PreviewRequest(BaseModel):
    game: str = Field(pattern=r"^[a-z0-9]{4}$")
    level: int = Field(ge=1, le=12)
    variant: Literal["son", "daniel"] = "son"
    context: Literal["carried", "none"] = "carried"
    prompt_profile: Literal["dedup", "original"] = "dedup"
    mode: str = Field(default="stock", min_length=1, max_length=64)
    name: str | None = Field(default=None, max_length=64)
    instructions: str = Field(default="", max_length=4000)


class PlayRequest(BaseModel):
    game: str
    stuck_level: int = Field(ge=1, le=12)
    variant: Literal["son", "daniel"] = "son"
    scheme: list[Slot] = Field(default_factory=list, max_length=40)
    stock: Slot
    samples: int = Field(default=10, ge=1, le=20)
    max_actions: int = Field(default=250, ge=10, le=1000)
    max_turns: int = Field(default=20, ge=1, le=60)
    max_minutes: int = Field(default=120, ge=5, le=180)
    levels_to_play: int = Field(default=1, ge=1, le=9)
    context: Literal["carried", "none"] = "carried"
    prompt_profile: Literal["dedup", "original"] = "dedup"   # prompt_profiles.py; "original" only to compare with old runs
    label: str | None = Field(default=None, max_length=120)
    by: str | None = Field(default=None, max_length=120)

    @field_validator("game")
    @classmethod
    def game_code(cls, v: str) -> str:
        if not CODE_RE.fullmatch(v):
            raise ValueError("game must be a four-character game code")
        return v


# ------------------------------------------------------------------ helpers

def runner_settings() -> dict:
    return {**DEFAULT_SETTINGS, **(read_json(SETTINGS_FILE, {}) or {})}


def public_games() -> list[str]:
    """Games harvest may play: the public games on disk minus the held-out eight (never those, whatever the
    Play setting says)."""
    return sorted(p.name for p in ENV_DIR.iterdir() if p.is_dir() and CODE_RE.fullmatch(p.name) and p.name not in HELD_OUT)


def game_id_for(game: str) -> str | None:
    d = ENV_DIR / game
    for meta in d.glob("*/metadata.json"):
        m = read_json(meta, {}) or {}
        if m.get("game_id"):
            return m["game_id"]
    subs = [p.name for p in d.iterdir() if p.is_dir()] if d.is_dir() else []
    return f"{game}-{subs[0]}" if len(subs) == 1 else None


def exact_levels(game: str) -> list[dict]:
    return [{"level": r["level"], "variant": r["variant"], "count": r["count"], "chosen": r["chosen"]}
            for r in checkpoints.index().get("levels", []) if r["game"] == game and r.get("chosen")]


def snapshot_path(game: str) -> Path:
    return SNAPSHOTS / f"{game}.json"


def stuck_points() -> list[dict]:
    index = read_json(SNAPSHOTS / "index.json", {}) or {}
    verified = read_json(SNAPSHOTS / "verified.json", {}) or {}
    out = []
    for s in index.get("snapshots", []):
        v = verified.get(s["game"])
        out.append({**s, "replay_verified": bool(v and v.get("ok")), "replay_checked": v.get("checked") if v else None,
                    "held_out": s["game"] in HELD_OUT, "playable": bool(v and v.get("ok")) and (ALLOW_HELD_OUT or s["game"] not in HELD_OUT),
                    "exact_levels": exact_levels(s["game"])})
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


def job_view(job_id: str, *, full: bool = False, line: list[str] | None = None) -> dict | None:
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
                                                       "final_level", "seconds", "error", "replay_verified", "generated_tokens",
                                                       "start_kind", "start_checkpoint", "first_request",
                                                       "checkpoints_written", "checkpoint_errors", "context",
                                                       "replay_source", "prompt_profile")}
            row["result"]["context"] = row["result"]["context"] or job.get("context", "carried")
        samples.append(row)
    view = {k: job.get(k) for k in ("id", "created", "game", "stuck_level", "variant", "samples", "status", "label", "by",
                                    "caps", "scheme_summary", "model", "conversation_exact", "finished", "kind",
                                    "start_kind", "start_checkpoint", "preempted", "context", "replay_source",
                                    "prompt_profile", "prompt_profile_assigned")}
    view["kind"] = view["kind"] or "play"
    # Jobs that finished before prompt profiles (6-Oct) ran the original prompts; one still waiting runs the default.
    if not view["prompt_profile"]:
        view["prompt_profile"] = (prompt_profiles.DEFAULT_PROFILE if view["status"] in ("queued", "running")
                                  else "original")
    view["context"] = view["context"] or "carried"
    view["start_kind"] = view["start_kind"] or ("exact" if job.get("conversation_exact") else "rebuilt")
    if view["kind"] == "play" and view["status"] in ("queued", "running"):
        line = play_line() if line is None else line
        if job_id in line:
            view["place_in_line"] = line.index(job_id) + 1    # 1 = being played now
            view["jobs_ahead"] = line.index(job_id)
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


def play_line() -> list[str]:
    """The Play queue: unfinished, uncancelled Play jobs, oldest first. The first one is the job being played; only
    its samples start, the rest wait whole (one person's request at a time keeps every lane on it)."""
    jobs = [read_json(p / "job.json") for p in JOBS.iterdir() if (p / "job.json").exists()]
    line = [j for j in jobs if j and j.get("kind", "play") == "play" and j["status"] in ("queued", "running")
            and not j.get("cancel") and any(s in ("queued", "running") for s in j["sample_state"])]
    # created is to the second; queued_ns breaks ties between jobs sent in the same second
    return [j["id"] for j in sorted(line, key=lambda j: (j["created"], j.get("queued_ns", 0), j["id"]))]


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


_MODEL_UP = {"t": 0.0, "ok": True}


def model_up() -> bool:
    """Cached model reachability (20 s), so the scheduler holds samples while the server is down."""
    if time.time() - _MODEL_UP["t"] > 20:
        _MODEL_UP["ok"] = bool(model_status().get("reachable"))
        _MODEL_UP["t"] = time.time()
    return _MODEL_UP["ok"]


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
                    j["sample_state"][k] = ("done" if res else "preempted" if j.get("preempted")
                                            else "cancelled" if j.get("cancel") else "failed")
            update_job(job_id, mark)
        # finish jobs
        jobs = sorted((read_json(p / "job.json") for p in JOBS.iterdir() if (p / "job.json").exists()),
                      key=lambda j: j["created"])
        for job in jobs:
            if job["status"] in ("queued", "running") and all(s in TERMINAL for s in job["sample_state"]):
                update_job(job["id"], lambda j: j.update(
                    status="preempted" if j.get("preempted") else "cancelled" if j.get("cancel")
                    else "interrupted" if "interrupted" in j["sample_state"] else "done",
                    finished=now()))
                prune_disk()
        line = play_line()
        play_waiting = bool(line)
        play_running = sum(1 for (jid, _k) in PROCS if (read_json(JOBS / jid / "job.json", {}) or {}).get("kind", "play") == "play")
        harvest_procs = [(jid, k) for (jid, k) in PROCS if (read_json(JOBS / jid / "job.json", {}) or {}).get("kind") == "harvest"]
        # Play always pre-empts harvest: a queued Play job stops every harvest sample right away.
        if play_waiting and harvest_procs:
            for jid, k in harvest_procs:
                update_job(jid, lambda j: j.__setitem__("preempted", now()))
                try:
                    os.killpg(PROCS[(jid, k)].pid, 15)
                except ProcessLookupError:
                    pass
            HARVEST["preemptions"] += len(harvest_procs)
            HARVEST["last_preempted"] = now()
            return   # reaped on the next tick, then Play gets every slot
        # Model server down (e.g. Cletus off): hold every queued sample instead of letting it fail at the model.
        if not model_up():
            return
        # start Play samples of the job at the head of the line only; later jobs wait whole
        free = CONCURRENCY - play_running - len(harvest_procs)
        for job in [read_json(JOBS / jid / "job.json") for jid in line[:1]]:
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
                    if not j.get("prompt_profile"):
                        # queued before prompt profiles existed: it runs under the default (sample.py does the
                        # same with its spec); the job says so, and when
                        j["prompt_profile"] = prompt_profiles.DEFAULT_PROFILE
                        j["prompt_profile_assigned"] = f"at start, {now()} (queued before prompt profiles)"
                update_job(job["id"], started)
        # harvest when idle: no Play job in line and no Play sample still running
        settings = runner_settings()
        HARVEST["enabled"] = bool(settings["harvest"])
        if not settings["harvest"] or play_waiting or play_running:
            return
        lanes = max(0, min(2, int(settings["harvest_lanes"])))
        for _ in range(lanes - len(harvest_procs)):
            start_harvest()


def start_harvest() -> None:
    """One-sample Stock run from RESET on the public game that has been harvested least (runs that were not
    pre-empted; fewest exact levels as the tie-break), started straight away."""
    games = public_games()
    if not games:
        return
    counts = {g: 0 for g in games}
    for p in JOBS.iterdir():
        j = read_json(p / "job.json")
        # a pre-empted or interrupted run did not get to play, so it does not count: that game is tried again first
        if j and j.get("kind") == "harvest" and j["game"] in counts \
                and j.get("status") not in ("preempted", "interrupted"):
            counts[j["game"]] += 1
    busy = {jid.split("--")[-1] for (jid, _k) in PROCS}
    exact = {g: len(exact_levels(g)) for g in games}
    choices = [g for g in games if g not in busy and game_id_for(g)]
    if not choices:
        return
    game = min(choices, key=lambda g: (counts[g], exact[g], g))
    job_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4] + "--" + game
    d = JOBS / job_id
    (d / "samples" / "0").mkdir(parents=True)
    stock = {"key": "0:stock", "mode": "stock", "name": "Stock", "base": "turn", "instructions": "",
             "settings": dict(checkpoints.STOCK_SETTINGS)}
    spec = {"kind": "harvest", "game": game, "game_id": game_id_for(game), "stuck_level": 1, "variant": HARVEST_VARIANT,
            "scheme": [], "stock": stock, "start": {"kind": "reset"}, "caps": dict(HARVEST_CAPS),
            "prompt_profile": prompt_profiles.DEFAULT_PROFILE,
            "model": {"base_url": MODEL_BASE_URL, "model_id": MODEL_ID}}
    write_json(d / "spec.json", spec)
    job = {"id": job_id, "kind": "harvest", "created": now(), "game": game, "stuck_level": 1, "variant": HARVEST_VARIANT,
           "samples": 1, "status": "running", "label": "harvest: Stock from RESET for exact level starts", "by": "runner",
           "caps": spec["caps"], "scheme_summary": [], "model": {"model_id": MODEL_ID}, "conversation_exact": True,
           "start_kind": "reset", "sample_state": ["running"], "finished": None,
           "prompt_profile": prompt_profiles.DEFAULT_PROFILE}
    write_json(d / "job.json", job)
    log = open(d / "samples" / "0.log", "ab")
    PROCS[(job_id, 0)] = subprocess.Popen([PYTHON, str(HERE / "sample.py"), str(d), "0"], stdout=log,
                                          stderr=subprocess.STDOUT, cwd=str(d), start_new_session=True)
    HARVEST["started"] += 1
    HARVEST["last_started"] = {"job": job_id, "game": game, "at": now()}


HARVEST = {"enabled": DEFAULT_SETTINGS["harvest"], "started": 0, "preemptions": 0, "last_started": None,
           "last_preempted": None}


def recover() -> None:
    JOBS.mkdir(parents=True, exist_ok=True)
    for p in JOBS.iterdir():
        job = read_json(p / "job.json")
        if not job or job["status"] not in ("queued", "running"):
            continue

        def fix(j):
            for k, s in enumerate(j["sample_state"]):
                if s == "running" and j.get("kind") == "harvest":   # harvest is not replayed, just closed
                    j["sample_state"][k] = "interrupted"
                elif s == "running":   # the process died with the service; play it again from its start
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
    with LOCK:
        harvest_running = [{"job": jid, "game": jid.split("--")[-1]} for (jid, _k) in PROCS if "--" in jid]
    settings = runner_settings()
    idx = checkpoints.index()
    line = play_line()
    play_queue = []
    for place, jid in enumerate(line, 1):
        j = read_json(JOBS / jid / "job.json", {}) or {}
        play_queue.append({"place": place, "job": jid, "game": j.get("game"), "level": j.get("stuck_level"),
                           "context": j.get("context", "carried"),
                           "prompt_profile": j.get("prompt_profile") or prompt_profiles.DEFAULT_PROFILE,
                           "samples": j.get("samples"), "by": j.get("by"), "created": j.get("created")})
    return {"ok": True, "time": now(), "concurrency": CONCURRENCY,
            "features": ["sample_events"],   # the page shows Watch links only when the runner says it can serve them
            "samples_running": running - len(harvest_running), "samples_queued": queued,
            "scheduling": "one Play job at a time, first come first served; it gets every lane",
            "play_queue": play_queue,
            "model": {"base_url_kind": "two-Spark Flash-Next server (via tunnel)", "model_id": MODEL_ID, **model_status()},
            "snapshots": len(stuck_points()),
            "replay_starts": {"games": len(replays.summary()["games"]), "checked": replays.summary()["checked"]},
            "harvest": {"enabled": bool(settings["harvest"]), "lanes": settings["harvest_lanes"],
                        "running": harvest_running, "started_since_restart": HARVEST["started"],
                        "preemptions_since_restart": HARVEST["preemptions"], "last_started": HARVEST["last_started"],
                        "last_preempted": HARVEST["last_preempted"], "games": public_games()},
            "exact_starts": {"levels": sum(1 for r in idx.get("levels", []) if r.get("chosen")),
                             "checkpoints": sum(r["count"] for r in idx.get("levels", [])), "built": idx.get("built")}}


@app.get("/api/stuck-points")
def get_stuck_points() -> dict:
    return {"stuck_points": stuck_points()}


@app.get("/api/exact-starts")
def get_exact_starts(game: str | None = None) -> dict:
    idx = checkpoints.index()
    rows = [r for r in idx.get("levels", []) if game is None or r["game"] == game]
    return {"rule": idx.get("rule"), "built": idx.get("built"), "levels": rows}


@app.get("/api/replay-starts")
def get_replay_starts() -> dict:
    """Levels a No-context job can start from, per trainable public game (level 1 always; later levels with a verified
    replay, see replays.py)."""
    return replays.summary()


@app.get("/api/start-board")
def get_start_board(game: str, level: int, variant: Literal["son", "daniel"] = "son",
                    context: Literal["carried", "none"] = "carried") -> dict:
    """The board at the start Play would use for this game, level and wording (boards.py: exact checkpoint replayed,
    fresh game, snapshot replayed, or the level's opening frame when there is no start). Runs the game file in a
    subprocess; answers are cached on disk, so only a new start costs a replay."""
    if not CODE_RE.fullmatch(game) or not 1 <= level <= 30:
        raise HTTPException(422, "game is four letters or digits, level 1 to 30")
    if game in HELD_OUT and not ALLOW_HELD_OUT:
        raise HTTPException(403, f"{game} is one of the eight held-out games")
    if not (ENV_DIR / game).is_dir():
        raise HTTPException(404, f"{game} is not among the runner's games")
    try:
        r = subprocess.run([PYTHON, str(HERE / "boards.py"), game, str(level), variant, context],
                           capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "drawing the board took too long")
    if r.returncode != 0:
        last = (r.stderr.strip().splitlines() or ["drawing the board failed"])[-1]
        raise HTTPException(422 if "ValueError" in last else 500, last[-300:])
    return json.loads(r.stdout.strip().splitlines()[-1])


class RunnerSettings(BaseModel):
    harvest: bool | None = None
    harvest_lanes: int | None = Field(default=None, ge=0, le=2)


@app.post("/api/settings", dependencies=[Depends(require_key)])
def set_settings(req: RunnerSettings) -> dict:
    cur = {**runner_settings(), **{k: v for k, v in req.model_dump().items() if v is not None}}
    write_json(SETTINGS_FILE, cur)
    return cur


@app.get("/api/jobs")
def list_jobs(game: str | None = None, limit: int = 50, kind: Literal["play", "harvest", "all"] = "play") -> dict:
    rows = []
    for p in JOBS.iterdir():
        j = read_json(p / "job.json")
        if j and (game is None or j["game"] == game) and (kind == "all" or j.get("kind", "play") == kind):
            rows.append(j)
    rows.sort(key=lambda j: j["created"], reverse=True)
    line = play_line()
    return {"jobs": [job_view(j["id"], line=line) for j in rows[: max(1, min(limit, 200))]]}


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


EVENTS_MAX_BYTES = 4 * 1024 * 1024   # per answer; the site relay caps answers at 16 MB


@app.get("/api/jobs/{job_id}/samples/{k}/events", dependencies=[Depends(require_key)])
def sample_events(job_id: str, k: int, after: int = 0, limit: int = 400) -> dict:
    """The sample's own trace-viewer events (viewer_events.jsonl, one per action or analysis step) from index `after`,
    for the site's Watch view (docs/static/js/spark-watch.js), which polls with after = the last answer's `next`.
    Only complete lines count: the harness appends while the sample runs, so a half-written last line waits for the
    next poll. The integer board is dropped (the viewer paints board_ascii). Answers stop at `limit` events or about
    4 MB, whichever first, so a long sample's first load comes in pieces."""
    if not JOB_RE.fullmatch(job_id):
        raise HTTPException(404, "no such job")
    job = read_json(JOBS / job_id / "job.json")
    if job is None or not 0 <= k < int(job.get("samples") or 0):
        raise HTTPException(404, "no such sample")
    sd = JOBS / job_id / "samples" / str(k)
    try:
        raw = (sd / "viewer_events.jsonl").read_bytes()
    except OSError:
        raw = b""
    lines = raw.split(b"\n")[:-1]   # the part after the last newline is unfinished (or empty)
    after = max(0, after)
    events, size = [], 0
    for line in lines[after: after + max(1, min(limit, 1000))]:
        try:
            ev = json.loads(line)
        except (json.JSONDecodeError, UnicodeDecodeError):
            ev = {"type": "unreadable"}
        ev.pop("board", None)
        size += len(line)
        if events and size > EVENTS_MAX_BYTES:
            break
        events.append(ev)
    viewer = read_json(sd / "viewer.json", {}) or {}
    state = (job.get("sample_state") or [None] * (k + 1))[k]
    status = viewer.get("status") or "playing"
    if state != "running" and status == "playing":
        status = state or "stopped"   # killed, cancelled or still queued: nothing more will come
    return {"job": job_id, "sample": k, "game": job.get("game"), "game_id": viewer.get("game_id"), "state": state,
            "status": status, "levels_completed": viewer.get("levels_completed"), "total_levels": viewer.get("total_levels"),
            "after": after, "next": after + len(events), "total": len(lines), "events": events}


def resolve_start(game: str, level: int, variant: str, context: str) -> tuple[dict, str, str, str | None]:
    """Where a Play job for this game and level starts: (start, start_kind, game_id, replay_source). Shared by
    Play and the request preview (render_requests.py), so a preview starts where the job would."""
    # Exact checkpoint for this game, level and variant if there is one; else the rebuilt stuck-level snapshot.
    snap_file = snapshot_path(game)
    snap = read_json(snap_file)
    cp = checkpoints.chosen(game, level, variant)
    replay_source = None
    if context == "none":
        # No context: the level's start board by a verified replay, and a new game's first turn
        r = replays.start_for(game, level, variant)
        game_id = game_id_for(game)
        if r is None or game_id is None:
            raise HTTPException(409, f"{game} level {level} has no verified replay to its start, so it "
                                     "cannot be played without context")
        start = {"kind": "replay", "source": r["source"], "checkpoint": r.get("checkpoint"), "actions": r["actions"],
                 "expected": r["expected"], "id": r.get("checkpoint")}
        start_kind, replay_source = "replay", r["source"]
    elif cp is not None:
        start = {"kind": "checkpoint", "path": cp["path"], "id": cp["id"]}
        start_kind, game_id = "exact", cp["game_id"]
    elif level == 1:
        # Level 1 is the game's first frame: a fresh game from RESET, as harvest plays it, for any game on disk.
        game_id = game_id_for(game)
        if game_id is None:
            raise HTTPException(404, f"{game} is not among the runner's games")
        start, start_kind = {"kind": "reset"}, "reset"
    else:
        if snap is None:
            raise HTTPException(404, f"no starting point for {game}: nothing to play from")
        if snap["stuck_level"] != level:
            raise HTTPException(409, f"{game} has no exact start at level {level} yet, and its snapshot "
                                     f"starts at level {snap['stuck_level']}")
        verified = (read_json(SNAPSHOTS / "verified.json", {}) or {}).get(game)
        if not verified or not verified.get("ok"):
            raise HTTPException(409, f"the snapshot for {game} has not passed its replay check")
        bare = not snap["actions"] and not snap["turns"]
        start = {"kind": "snapshot", "path": str(snap_file)}
        start_kind, game_id = ("reset" if bare else "rebuilt"), snap["game_id"]
    return start, start_kind, game_id, replay_source


@app.post("/api/play", dependencies=[Depends(require_key)])
def play(req: PlayRequest) -> dict:
    if req.game in HELD_OUT and not ALLOW_HELD_OUT:
        raise HTTPException(403, f"{req.game} is one of the eight held-out games, which this runner does not play "
                                 "(they stay out of prompt tuning); Son can switch that off on the runner")
    start, start_kind, game_id, replay_source = resolve_start(req.game, req.stuck_level, req.variant, req.context)
    slots = []
    for i, s in enumerate(req.scheme + [req.stock]):
        if s.instructions is None and not (s.prompt and s.stock_template):
            raise HTTPException(422, f"slot {i + 1}: a slot needs instructions (or, from an older page, prompt and "
                                     "stock_template)")
        if s.instructions is None:
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
    spec = {"kind": "play", "game": req.game, "game_id": game_id, "stuck_level": req.stuck_level, "variant": req.variant,
            "scheme": slots[:-1], "stock": slots[-1], "start": start, "context": req.context,
            "prompt_profile": req.prompt_profile, "capture": req.context == "carried",
            "caps": {"max_actions": req.max_actions, "max_turns": req.max_turns, "max_minutes": req.max_minutes, "levels_to_play": req.levels_to_play},
            "model": {"base_url": MODEL_BASE_URL, "model_id": MODEL_ID}}
    write_json(d / "spec.json", spec)
    job = {"id": job_id, "created": now(), "game": req.game, "stuck_level": req.stuck_level, "variant": req.variant,
           "samples": req.samples, "status": "queued", "label": req.label, "by": req.by, "caps": spec["caps"],
           "scheme_summary": [{"mode": s["mode"], "name": s.get("name"), "settings": s["settings"]} for s in slots[:-1]],
           "prompt_profile": req.prompt_profile,
           "model": {"model_id": MODEL_ID}, "conversation_exact": start_kind != "rebuilt", "kind": "play",
           "start_kind": start_kind, "start_checkpoint": start.get("id"), "context": req.context,
           "replay_source": replay_source,
           "sample_state": ["queued"] * req.samples, "finished": None, "queued_ns": time.time_ns()}
    write_json(d / "job.json", job)
    line = play_line()
    return {"job": job_id, "queued_samples": req.samples,
            "place_in_line": line.index(job_id) + 1 if job_id in line else None, "start_kind": start_kind,
            "start_checkpoint": start.get("id"), "context": req.context, "replay_source": replay_source,
            "prompt_profile": req.prompt_profile}


PREVIEWS = HOME / "previews"


def preview_view(body: dict) -> dict:
    """A request body as the page shows it: every message's text parts in order, images as labelled stand-ins (the
    pictures are the board, which the page draws already), the tool schema and the sampling settings."""
    msgs = []
    for m in body.get("messages") or []:
        c = m.get("content")
        parts = [{"kind": "text", "text": c}] if isinstance(c, str) else [
            {"kind": "text", "text": p.get("text", "")} if p.get("type") == "text" else {"kind": "image"}
            for p in c or [] if isinstance(p, dict)]
        row = {"role": m.get("role"), "parts": parts}
        if m.get("tool_calls"):
            row["tool_calls"] = [((t.get("function") or {}).get("arguments") or "")[:2000] for t in m["tool_calls"]]
        msgs.append(row)
    return {"messages": msgs, "tools": body.get("tools"),
            "settings": {k: v for k, v in body.items() if k not in ("messages", "tools", "model")}}


@app.post("/api/preview-request", dependencies=[Depends(require_key)])
def preview_request(req: PreviewRequest) -> dict:
    """The first request a Play job would send for this game, level and mode, built by the real harness with no model
    (render_requests.py preview), and the duplicate check of it. Cached per input; a render takes a few seconds."""
    if req.game in HELD_OUT and not ALLOW_HELD_OUT:
        raise HTTPException(403, f"{req.game} is one of the eight held-out games")
    start, start_kind, game_id, replay_source = resolve_start(req.game, req.level, req.variant, req.context)
    slot = {"key": f"0:{req.mode}", "mode": req.mode, "name": req.name or req.mode, "base": "turn",
            "instructions": req.instructions, "settings": dict(checkpoints.STOCK_SETTINGS)}
    stock = {"key": "stock", "mode": "stock", "name": "Stock", "base": "turn", "instructions": "",
             "settings": dict(checkpoints.STOCK_SETTINGS)}
    spec = {"kind": "play", "game": req.game, "game_id": game_id, "stuck_level": req.level, "variant": req.variant,
            "scheme": [slot], "stock": stock, "start": start, "context": req.context,
            "prompt_profile": req.prompt_profile, "capture": False,
            "caps": {"max_actions": 250, "max_turns": 20, "max_minutes": 40, "levels_to_play": 1},
            "model": {"base_url": "http://127.0.0.1:9/v1", "model_id": MODEL_ID}}
    key = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:24]
    cached = read_json(PREVIEWS / f"{key}.json")
    if cached:
        return cached
    out = PREVIEWS / f"{key}.work"
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    (PREVIEWS / f"{key}.spec.json").write_text(json.dumps(spec))
    try:
        r = subprocess.run([PYTHON, str(HERE / "render_requests.py"), str(PREVIEWS / f"{key}.spec.json"), str(out),
                            "preview"], capture_output=True, text=True, timeout=55)
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "building the preview took too long")
    first = out / "requests" / "01.json.gz"
    if r.returncode != 0 or not first.exists():
        last = ((r.stderr or r.stdout).strip().splitlines() or ["the harness built no request"])[-1]
        raise HTTPException(500, f"preview failed: {last[-300:]}")
    import dupcheck
    body = dupcheck.load(first)
    check = dupcheck.check(body)
    view = {"game": req.game, "level": req.level, "variant": req.variant, "context": req.context,
            "prompt_profile": req.prompt_profile, "mode": req.mode, "start_kind": start_kind,
            "start_checkpoint": start.get("id"), "replay_source": replay_source, "built": now(),
            "request": preview_view(body),
            "duplicate_check": {"ok": check["ok"], "fail_counts": check["fail_counts"],
                                "failures": {k: check[k][:5] for k in check["fail_counts"] if check[k]}}}
    write_json(PREVIEWS / f"{key}.json", view)
    shutil.rmtree(out, ignore_errors=True)
    return view


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
