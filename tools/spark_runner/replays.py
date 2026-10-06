#!/usr/bin/env python3
"""
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: Replayed level starts for the Spark runner's "No context" Play option (Son, #arc-3, 6-Oct 11:50 ET: "Right now
  future levels require previous context. Add a 'non-context' mode too.").
  A No-context sample starts the chosen level with the game board at that level's start but a clean conversation, so
  only the game state is needed, never a saved conversation. This module says how to reach any level's start:
    checkpoint    the actions of the chosen exact checkpoint for that game and level (either wording; the actions do
                  not depend on the wording), checked against the board hash the checkpoint saved
    winning_line  the recorded winning line cut per level (datasets/copycat-games/recolor/solutions: each recolor
                  copy's line is the original game's line, proven level by level when the copies were made), levels
                  1 to N-1 played from RESET, checked against the board this module's verify pass recorded
    reset         level 1: the first frame, nothing to replay
  The winning lines exist only for the trainable public games (the held-out games have none and stay refused).
  Layout on the runner: <home>/solutions/ = copy of datasets/copycat-games/recolor/solutions/*.json + manifest.json
  (maps each copy to its original game); <home>/replays/verified.json = per game and level: actions to reach, level
  reached, board hash, whether the board equals the level's clean opening frame. Built by
    python replays.py --verify-all          bare-engine replay of every trainable game and level (no harness, no model)
  and read by server.play, boards.py and sample.py. A level is playable without context only when its row is ok.
SRP/DRY check: Pass - replay and opening frames reuse boards.py (game_class, replay, opening); checkpoint choice is
  checkpoints.chosen; the harness-path replay and the clean start live in sample.py.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import boards  # noqa: E402
import checkpoints  # noqa: E402

HOME = Path(os.environ.get("ARC3_RUNNER_HOME", Path.home() / "arc3-runner"))
SOLUTIONS = Path(os.environ.get("ARC3_RUNNER_SOLUTIONS", HOME / "solutions"))
VERIFIED = Path(os.environ.get("ARC3_RUNNER_REPLAYS", HOME / "replays")) / "verified.json"
HELD_OUT = ("vc33", "ar25", "sb26", "re86", "su15", "tr87", "tu93", "as66")


def _read(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return default


def grid_sha(grid) -> str:
    """Same hash as sample.grid_hash and the checkpoints' board_sha256: json.dumps of the engine grid."""
    return hashlib.sha256(json.dumps(grid).encode()).hexdigest()


def solution_levels(game: str) -> list[list[dict]] | None:
    """The original game's winning line, one action list per level, in the runner's {name, data} format; None for a
    game without one (held out, or not among the copies)."""
    if game in HELD_OUT:
        return None
    manifest = _read(SOLUTIONS / "manifest.json", {}) or {}
    row = next((g for g in manifest.get("games", []) if g.get("original_id") == game and g.get("verified")), None)
    sol = _read(SOLUTIONS / f"{row['copycat_id']}.json") if row else None
    if not sol or sol.get("copycat_of") != game:
        return None
    return [[{"name": a["id"], "data": {"x": a["x"], "y": a["y"]} if "x" in a else {}, "automatic": False}
             for a in lv] for lv in sol["levels"]]


def verified(game: str | None = None) -> dict:
    v = _read(VERIFIED, {}) or {}
    return v.get(game, {}) if game else v


def start_for(game: str, level: int, variant: str) -> dict | None:
    """How a No-context sample reaches this level's start, or None. {source, actions, expected{level, action_count,
    board_sha256}, checkpoint?}. Exact checkpoint actions first (same wording, then the other), then the verified
    winning line; level 1 is a fresh game."""
    if level == 1:
        return {"source": "reset", "actions": [], "expected": None}
    for v in (variant, "daniel" if variant == "son" else "son"):
        cp = checkpoints.chosen(game, level, v)
        if cp is not None:
            actions = _read(Path(cp["path"]) / "actions.json", [])
            return {"source": "checkpoint", "checkpoint": cp["id"], "actions": actions,
                    "expected": {"level": level, "action_count": cp["actions_to_reach"],
                                 "board_sha256": cp["board_sha256"]}}
    row = (verified(game).get("levels") or {}).get(str(level))
    lines = solution_levels(game)
    if not row or not row.get("ok") or not lines or level > len(lines):
        return None
    actions = [a for lv in lines[: level - 1] for a in lv]
    if len(actions) != row["action_count"]:
        return None      # the solutions changed since the verify pass: refuse until it is run again
    return {"source": "winning_line", "actions": actions,
            "expected": {"level": level, "action_count": row["action_count"], "board_sha256": row["board_sha256"]}}


def summary() -> dict:
    """Per trainable game: its level count and which levels can start without context (for the page)."""
    out = {}
    for game, g in verified().items():
        if game.startswith("_"):
            continue
        ok = [1] + sorted(int(lv) for lv, r in (g.get("levels") or {}).items() if r.get("ok"))
        out[game] = {"levels": g.get("levels_total"), "playable_levels": sorted(set(ok)),
                     "failed_levels": sorted(int(lv) for lv, r in (g.get("levels") or {}).items() if not r.get("ok"))}
    return {"games": out, "checked": (verified().get("_meta") or {}).get("checked"),
            "rule": "level 1 is a fresh game; later levels replay an exact checkpoint's actions if one exists, else the "
                    "verified winning line, and are checked against the expected board"}


def verify_game(game: str) -> dict:
    """Bare-engine replay of every level start: levels completed must be N-1 exactly at the end of segment N-1 (not
    before), the game still playing; records the board hash and whether it equals the level's clean opening frame."""
    from arcengine import ActionInput, GameAction, GameState
    lines = solution_levels(game)
    if not lines:
        return {"ok": False, "error": "no winning line"}
    cls = boards.game_class(game)
    _, n = boards.opening(cls, 1)
    if len(lines) != n:
        return {"ok": False, "error": f"winning line has {len(lines)} levels, game has {n}"}
    rows = {}
    g, fd = boards.fresh(cls)
    count = 0
    for lv in range(1, n):
        early = None
        for i, a in enumerate(lines[lv - 1]):
            fd = g.perform_action(ActionInput(id=GameAction.from_name(a["name"]), data=a["data"]), raw=True)
            count += 1
            if fd.levels_completed >= lv and i < len(lines[lv - 1]) - 1 and early is None:
                early = i + 1
        grid = boards.as_grid(fd.frame[-1])
        open_grid, _ = boards.opening(cls, lv + 1)
        ok = fd.levels_completed == lv and early is None and fd.state == GameState.NOT_FINISHED
        rows[str(lv + 1)] = {"ok": bool(ok), "level": lv + 1, "levels_completed": int(fd.levels_completed),
                             "state": fd.state.name, "action_count": count, "board_sha256": grid_sha(grid),
                             "same_as_opening_frame": grid == open_grid,
                             **({"cleared_early_at_action": early} if early else {})}
    # the last level's segment must win the game, so the line is whole
    for a in lines[-1]:
        fd = g.perform_action(ActionInput(id=GameAction.from_name(a["name"]), data=a["data"]), raw=True)
    return {"ok": all(r["ok"] for r in rows.values()), "levels_total": n, "levels": rows,
            "line_wins": fd.state == GameState.WIN}


def verify_all() -> dict:
    """One subprocess per game (the game file is exec'd); writes <home>/replays/verified.json."""
    import subprocess
    manifest = _read(SOLUTIONS / "manifest.json", {}) or {}
    games = sorted(g["original_id"] for g in manifest.get("games", []) if g["original_id"] not in HELD_OUT)
    out = {"_meta": {"checked": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "source": "datasets/copycat-games/recolor/solutions (original games' winning lines)"}}
    for game in games:
        r = subprocess.run([sys.executable, __file__, "--verify", game], capture_output=True, text=True, timeout=600)
        try:
            out[game] = json.loads(r.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            out[game] = {"ok": False, "error": (r.stderr or r.stdout)[-300:]}
        g = out[game]
        print(game, g.get("ok"), g.get("error", ""), "levels", g.get("levels_total"),
              "differ from opening:", [lv for lv, x in (g.get("levels") or {}).items() if not x.get("same_as_opening_frame")],
              flush=True)
    VERIFIED.parent.mkdir(parents=True, exist_ok=True)
    tmp = VERIFIED.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, indent=1))
    tmp.replace(VERIFIED)
    return out


if __name__ == "__main__":
    if sys.argv[1] == "--verify":
        print(json.dumps(verify_game(sys.argv[2])))
    elif sys.argv[1] == "--verify-all":
        res = verify_all()
        sys.exit(0 if all(v.get("ok") for k, v in res.items() if not k.startswith("_")) else 1)
    elif sys.argv[1] == "--summary":
        print(json.dumps(summary(), indent=1))
