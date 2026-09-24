# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Proof that env.GameEnv simulates a game exactly: replays every recorded play of the game
#   (the *_events.jsonl traces the harness wrote on Kaggle, under ~/bubba-workspace/arc3-kaggle and
#   ~/arc3-job-output) through the local engine, action by action, and checks after every action that
#   the simulated board equals the recorded board, and that the level counter agrees. Reports per play
#   and in total, and stops listing mismatches after a few per play. Asked by OpenMind (#arc-3,
#   23-Sep-2026 22:34 ET) together with env.py. Default game: Locksmith (ls20-9607627b).
#   Run: cd ARC3-Inference && .venv/bin/python -m rulediscovery1__fepInspired.verify_env [--game ls20]
# SRP/DRY check: Pass -- stepping is env.GameEnv, actions are perception.Action; this file only finds
#   the traces, parses their rows and compares.
"""Replay recorded plays through GameEnv and check every board."""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from .env import DEFAULT_BUILD, DEFAULT_GAME, GameEnv
from .perception import CLICK, Action

TRACE_ROOTS = [Path.home() / "bubba-workspace/arc3-kaggle", Path.home() / "arc3-job-output"]
MOUSE_RE = re.compile(r"row\s*=\s*(\d+)\s*,\s*col\s*=\s*(\d+)")


def find_traces(game: str, build: str) -> list[Path]:
    out = []
    for root in TRACE_ROOTS:
        out += sorted(root.rglob(f"{game}-{build}_*_events.jsonl"))
    return out


def load_rows(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def board_of(row: dict):
    b = row.get("board")
    return json.loads(b) if isinstance(b, str) else b


def action_of(row: dict) -> Action:
    name = row["action_name"]
    if name == CLICK:
        m = MOUSE_RE.search(row.get("action_display") or "")
        if not m:
            raise ValueError(f"click without row/col: {row.get('action_display')}")
        return Action(name, int(m.group(1)), int(m.group(2)))
    return Action(name)


def replay(env: GameEnv, path: Path, max_report: int = 3) -> dict:
    rows = load_rows(path)
    init = next((r for r in rows if r.get("type") == "initial"), None)
    acts = [r for r in rows if r.get("type") == "action"]
    obs = env.reset()
    res = {"trace": str(path), "actions": len(acts), "initial_match": init is not None and board_of(init) == obs.grid,
           "board_match": 0, "level_match": 0, "mismatches": []}
    for i, r in enumerate(acts, 1):
        obs = env.step(action_of(r))
        same = board_of(r) == obs.grid
        # the trace's "level" is the level being played (1-based) after the action
        lvl_ok = r.get("level") in (None, "None") or int(r["level"]) == min(obs.levels_completed + 1, obs.win_levels)
        res["board_match"] += same
        res["level_match"] += lvl_ok
        if (not same or not lvl_ok) and len(res["mismatches"]) < max_report:
            res["mismatches"].append({"action": i, "name": r["action_name"], "board": same, "level": lvl_ok,
                                      "trace_level": r.get("level"), "sim_levels_completed": obs.levels_completed})
    res["final_levels_completed"] = obs.levels_completed
    res["final_state"] = obs.state
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game", default=DEFAULT_GAME)
    ap.add_argument("--build", default=DEFAULT_BUILD)
    ap.add_argument("--out", default=None, help="write the per-play results as JSON here")
    args = ap.parse_args()
    t0 = time.time()
    env = GameEnv(args.game, args.build)
    paths = find_traces(args.game, args.build)
    results = [replay(env, p) for p in paths]
    n_act = sum(r["actions"] for r in results)
    n_board = sum(r["board_match"] for r in results)
    n_lvl = sum(r["level_match"] for r in results)
    exact = sum(r["initial_match"] and r["board_match"] == r["actions"] and r["level_match"] == r["actions"]
                for r in results)
    for r in results:
        if r["mismatches"] or not r["initial_match"]:
            print(f"MISMATCH {r['trace']}: initial {r['initial_match']}, boards {r['board_match']}/{r['actions']}, "
                  f"levels {r['level_match']}/{r['actions']}; first: {r['mismatches']}")
    print(f"{args.game}-{args.build}: {len(results)} recorded plays, {exact} replay exactly; "
          f"{n_board}/{n_act} boards and {n_lvl}/{n_act} level counters match; "
          f"max levels reached in a play {max((r['final_levels_completed'] for r in results), default=0)} "
          f"of {env.last.win_levels if env.last else '?'}; {time.time() - t0:.1f} s")
    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
