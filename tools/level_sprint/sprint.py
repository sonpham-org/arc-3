#!/usr/bin/env python3
"""
Author: Claude Opus 5.5 (Bubba)
Date: 09-October-2026
PURPOSE: Level-start sprint (Son, #arc-3, 9-Oct-2026 22:30 ET): play every stuck level at once, one lane per level,
  each from that level's start, under one prompt/harness variant, with a hard wall clock, and report cleared or not
  per level plus actions used. Built so a prompt or harness change can be judged in about thirty minutes of play.
  It is a thin driver over the Spark runner (tools/spark_runner): every lane is one sample.py process with a
  spec.json written here, exactly the way the runner's server writes one, so the harness, the checkpoint restore,
  the winning-line replay and its board checks, the turn hooks and result.json are the runner's own code.
    plan   resolve each lane's start and print it (no model, no game play)
    run    plan, then start every lane at once against an OpenAI-compatible server; kill any lane still alive at the
           wall clock plus a grace period; write results.json + results.md in the output folder
    report reprint results.md from a finished output folder
    freeze-env  write <harness>/notebook_env.json from the CURRENT process environment (Kaggle: call it after the
           notebook's own setup and port cells ran, so the flags are exactly the notebook's, nothing retyped)
  Lane starts (lanes.json "start"):
    exact  the runner's chosen exact level-start checkpoint (carried context from a real clear of the level before);
           refused if none is saved for that level
    replay the verified winning line replayed to the level start, model starts with no context (sample.py "replay")
    warmup the winning line to the level BEFORE, then the model plays that level and carries its own context into
           the target level; the 30-minute clock covers both; cleared = both levels cleared
    auto   exact if one is saved, else replay
  Paths come from the runner's own variables: ARC3_RUNNER_HOME (solutions/, replays/, checkpoints/),
  ARC3_RUNNER_HARNESS (built harness + notebook_env.json), ARC3_RUNNER_ENVIRONMENTS (game files).
  Usage: sprint.py run --lanes lanes.json --variant variants/stock.json --out <dir> --base-url <url> --model-id <id>
                       [--wall-minutes 30] [--max-turns 0] [--max-actions 1000] [--only sk48,lf52]
SRP/DRY check: Pass - no game, harness or checkpoint logic here: starts come from checkpoints.chosen and
  replays.start_for, play from sample.main. This file only plans lanes, runs processes, enforces the clock and tallies.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER_CODE = Path(os.environ.get("ARC3_SPRINT_RUNNER_CODE", HERE.parent / "spark_runner"))
sys.path.insert(0, str(RUNNER_CODE))
import checkpoints  # noqa: E402
import replays  # noqa: E402

RUNNER_HOME = Path(os.environ.get("ARC3_RUNNER_HOME", Path.home() / "arc3-runner"))
ENV_DIR = Path(os.environ.get("ARC3_RUNNER_ENVIRONMENTS", RUNNER_HOME / "environment_files"))
GRACE_S = 180          # a lane past wall clock + grace is killed; sample.py's own time cap normally ends it first
ENV_PREFIXES = ("ARC3_", "LOCAL_ANALYZER_", "MULTIMODAL_", "EXPOSE_", "INFERENCE_", "OPENAI_", "TAAF_", "ONLY_RESET",
                "USE_TF", "TRANSFORMERS_NO")


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, default=str))
    tmp.replace(path)


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return default


def game_id_for(game: str) -> str | None:
    for meta in sorted((ENV_DIR / game).glob("*/metadata.json")):
        gid = read_json(meta, {}).get("game_id")
        if gid:
            return gid
    return None


def resolve(lane: dict, variant: str) -> dict:
    """The sample.py start for one lane: {kind, start, context, stuck_level, levels_to_play, start_label}."""
    game, level, want = lane["game"], int(lane["level"]), lane.get("start", "auto")
    if want in ("exact", "auto"):
        cp = checkpoints.chosen(game, level, variant)
        if cp is not None:
            return {"start": {"kind": "checkpoint", "path": cp["path"]}, "context": "carried", "stuck_level": level,
                    "levels_to_play": 1, "start_label": f"exact ({cp['actions_to_reach']} actions from RESET)"}
        if want == "exact":
            raise ValueError(f"{game} level {level}: no exact checkpoint saved for this level start")
    if want in ("replay", "auto"):
        st = replays.start_for(game, level, variant)
        if st is None:
            raise ValueError(f"{game} level {level}: no verified replay to this level start")
        return {"start": {"kind": "replay", **st}, "context": "none", "stuck_level": level, "levels_to_play": 1,
                "start_label": f"no context ({st['source']})"}
    if want == "warmup":
        if level < 2:
            raise ValueError(f"{game}: warmup needs a level before the target")
        st = replays.start_for(game, level - 1, variant)
        if st is None:
            raise ValueError(f"{game} level {level - 1}: no verified replay to the warmup level")
        return {"start": {"kind": "replay", **st}, "context": "carried", "stuck_level": level - 1, "levels_to_play": 2,
                "start_label": f"warmup from level {level - 1} ({st['source']})"}
    raise ValueError(f"unknown start {want!r}")


def stock_slot(var: dict) -> dict:
    settings = dict(checkpoints.STOCK_SETTINGS)
    if os.environ.get("LOCAL_ANALYZER_TEMPERATURE"):
        settings["temperature"] = float(os.environ["LOCAL_ANALYZER_TEMPERATURE"])
    settings.update(var.get("settings") or {})
    return {"key": "stock", "mode": "stock", "name": var.get("name", "stock"),
            "instructions": var.get("instructions") or "", "settings": settings, "version": 1}


def plan(lanes: list[dict], var: dict) -> list[dict]:
    rows = []
    for lane in lanes:
        row = {"game": lane["game"], "name": lane.get("name", lane["game"]), "level": int(lane["level"]),
               "heatmap_pct": lane.get("heatmap_pct")}
        try:
            row.update(resolve(lane, var.get("variant", "son")))
            row["game_id"] = game_id_for(lane["game"])
            if not row["game_id"]:
                raise ValueError(f"{lane['game']}: no game files under {ENV_DIR}")
        except ValueError as exc:
            row["plan_error"] = str(exc)
        rows.append(row)
    return rows


def spec_for(row: dict, var: dict, args) -> dict:
    """The same spec shape server.py writes for a Play job (one sample), plus env_overrides."""
    return {"kind": "play", "game": row["game"], "game_id": row["game_id"], "stuck_level": row["stuck_level"],
            "variant": var.get("variant", "son"), "scheme": [], "stock": stock_slot(var), "start": row["start"],
            "context": row["context"], "prompt_profile": var.get("prompt_profile", "original"),
            "capture": row["context"] == "carried",
            "caps": {"max_actions": args.max_actions, "max_turns": args.max_turns, "max_minutes": args.wall_minutes,
                     "levels_to_play": row["levels_to_play"]},
            "model": {"base_url": args.base_url, "model_id": args.model_id},
            "env_overrides": var.get("env") or {}, "sprint": {"target_level": row["level"], "variant": var.get("name")}}


def lane_result(row: dict, lane_dir: Path) -> dict:
    res = read_json(lane_dir / "samples" / "0" / "result.json")
    prog = read_json(lane_dir / "samples" / "0" / "progress.json", {})
    out = {"game": row["game"], "name": row["name"], "level": row["level"], "heatmap_pct": row.get("heatmap_pct"),
           "start": row.get("start_label")}
    if row.get("plan_error"):
        return {**out, "cleared": False, "outcome": "not_started", "error": row["plan_error"]}
    if res is None:
        return {**out, "cleared": False, "outcome": "killed_at_wall", "actions_used": prog.get("actions"),
                "levels_cleared": prog.get("levels_cleared"), "turns": prog.get("turn"),
                "error": (lane_dir / "samples" / "0" / "error.txt").read_text()[-500:]
                if (lane_dir / "samples" / "0" / "error.txt").exists() else None}
    cleared = int(res.get("levels_cleared") or 0) >= int(row["levels_to_play"])
    return {**out, "cleared": cleared, "outcome": res.get("outcome"), "actions_used": res.get("actions_used"),
            "levels_cleared": res.get("levels_cleared"), "turns": res.get("turns"), "seconds": res.get("seconds"),
            "tokens": res.get("generated_tokens"), "first_request_exact": (res.get("first_request") or {}).get("equal"),
            "checkpoints_written": len(res.get("checkpoints_written") or []), "error": res.get("error")}


def markdown(summary: dict) -> str:
    lines = [f"# Level-start sprint: variant {summary['variant']}",
             "", f"{summary['started']} to {summary['finished']}, wall clock {summary['wall_minutes']} min per lane, "
                 f"model {summary['model_id']}. Cleared {summary['cleared']} of {summary['lanes']} levels.", "",
             "| Game | Level | Heatmap % | Start | Cleared | Outcome | Actions | Turns | Minutes |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in summary["results"]:
        mins = f"{r['seconds'] / 60:.1f}" if r.get("seconds") else ""
        lines.append(f"| {r['name']} | {r['level']} | {r.get('heatmap_pct', '')} | {r.get('start') or ''} | "
                     f"{'yes' if r['cleared'] else 'no'} | {r['outcome']} | {r.get('actions_used') if r.get('actions_used') is not None else ''} | "
                     f"{r.get('turns') if r.get('turns') is not None else ''} | {mins} |")
    errs = [r for r in summary["results"] if r.get("error")]
    if errs:
        lines += ["", "Errors:"] + [f"- {r['name']} level {r['level']}: {str(r['error'])[:300]}" for r in errs]
    return "\n".join(lines) + "\n"


def run(args) -> int:
    lanes = read_json(args.lanes)["lanes"]
    if args.only:
        keep = set(args.only.split(","))
        lanes = [l for l in lanes if l["game"] in keep]
    var = read_json(args.variant)
    out = Path(args.out)
    rows = plan(lanes, var)
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    write_json(out / "plan.json", {"variant": var, "lanes": rows, "started": started})
    procs = {}
    for i, row in enumerate(rows):
        print(f"lane {i:2d} {row['name']} level {row['level']}: {row.get('start_label') or row.get('plan_error')}", flush=True)
        if row.get("plan_error"):
            continue
        lane_dir = out / "lanes" / f"{i:02d}-{row['game']}-L{row['level']}"
        write_json(lane_dir / "spec.json", spec_for(row, var, args))
        (lane_dir / "samples").mkdir(parents=True, exist_ok=True)
        log = open(lane_dir / "samples" / "0.log", "w")
        procs[i] = (subprocess.Popen([sys.executable, str(RUNNER_CODE / "sample.py"), str(lane_dir), "0"],
                                     stdout=log, stderr=subprocess.STDOUT, env=os.environ.copy()), lane_dir, log)
    t0 = time.time()
    deadline = t0 + args.wall_minutes * 60 + GRACE_S
    last_print = 0.0
    while any(p.poll() is None for p, _, _ in procs.values()):
        if time.time() > deadline:
            for i, (p, lane_dir, _) in procs.items():
                if p.poll() is None:
                    print(f"lane {i} still running at wall clock + grace: killed", flush=True)
                    p.kill()
            break
        if time.time() - last_print >= args.print_every:
            last_print = time.time()
            bits = []
            for i, (p, lane_dir, _) in procs.items():
                pr = read_json(lane_dir / "samples" / "0" / "progress.json", {})
                bits.append(f"{rows[i]['game']}:{pr.get('status', '?')[:4]} L{pr.get('level')} a{pr.get('actions')} "
                            f"+{pr.get('levels_cleared', 0)}")
            print(f"[{(time.time() - t0) / 60:5.1f} min] " + " | ".join(bits), flush=True)
        time.sleep(5)
    for p, _, log in procs.values():
        try:
            p.wait(timeout=30)
        except subprocess.TimeoutExpired:
            p.kill()
        log.close()
    results = []
    for i, row in enumerate(rows):
        lane_dir = out / "lanes" / f"{i:02d}-{row['game']}-L{row['level']}"
        results.append(lane_result(row, lane_dir))
    summary = {"variant": var.get("name"), "variant_spec": var, "model_id": args.model_id, "base_url": args.base_url,
               "wall_minutes": args.wall_minutes, "started": started,
               "finished": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "lanes": len(results), "cleared": sum(1 for r in results if r["cleared"]), "results": results}
    write_json(out / "results.json", summary)
    (out / "results.md").write_text(markdown(summary))
    print(markdown(summary), flush=True)
    return 0


def freeze_env(harness: Path) -> None:
    flags = {k: v for k, v in sorted(os.environ.items()) if k.startswith(ENV_PREFIXES)}
    write_json(harness / "notebook_env.json", {"daniel": flags, "son_port": {},
                                               "source": {"frozen_from": "notebook process environment",
                                                          "at": datetime.now(timezone.utc).isoformat()}})
    print(f"notebook_env.json: {len(flags)} flags frozen into {harness}")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "run"):
        p = sub.add_parser(name)
        p.add_argument("--lanes", type=Path, default=HERE / "lanes.json")
        p.add_argument("--variant", type=Path, default=HERE / "variants" / "stock.json")
        p.add_argument("--only", default="")
        if name == "run":
            p.add_argument("--out", required=True)
            p.add_argument("--base-url", required=True)
            p.add_argument("--model-id", required=True)
            p.add_argument("--wall-minutes", type=float, default=30.0)
            p.add_argument("--max-turns", type=int, default=0, help="0 = no turn cap; the wall clock is the limit")
            p.add_argument("--max-actions", type=int, default=1000)
            p.add_argument("--print-every", type=float, default=60.0)
    r = sub.add_parser("report")
    r.add_argument("out")
    f = sub.add_parser("freeze-env")
    f.add_argument("harness", type=Path)
    args = ap.parse_args()
    if args.cmd == "plan":
        lanes = read_json(args.lanes)["lanes"]
        if args.only:
            lanes = [l for l in lanes if l["game"] in set(args.only.split(","))]
        for row in plan(lanes, read_json(args.variant)):
            print(f"{row['name']:22s} level {row['level']}: {row.get('start_label') or 'ERROR ' + row['plan_error']}")
        return 0
    if args.cmd == "report":
        print(markdown(read_json(Path(args.out) / "results.json")))
        return 0
    if args.cmd == "freeze-env":
        freeze_env(args.harness)
        return 0
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
