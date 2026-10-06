#!/usr/bin/env python3
"""
Author: Claude Opus 5.5 (Bubba)
Date: 06-October-2026
PURPOSE: The game board at the start Play would use, for the Mode explorer's board picture (Son, #arc-3, 6-Oct 10:47 ET:
  "in the screen where you set up mode, at least show the screen at that time as well").
  For one game, level and wording it mirrors server.play()'s choice of start and draws that start's board:
    exact      the chosen checkpoint's actions.json replayed from RESET in the offline engine; checked against the
               board hash the checkpoint saved
    reset      level 1: the frame after RESET
    rebuilt    the stuck-level snapshot's action line replayed; checked against the snapshot's board hash
    opening    no start for this level: the level's clean opening frame from the game file (the level's own sprites,
               as the site's in-browser player jumps to a level). Play is not available there.
  With context "none" (the No-context Play option, added 6-Oct) it draws the replayed level start a No-context sample
  plays from (replays.start_for: exact checkpoint actions, else the verified winning line; level 1 the first frame),
  checked against the expected board.
  Replay is the bare arcengine game (no harness, no model): a few hundred actions take well under a second. Each
  answer is cached under <home>/boards/ by game, level and what it was drawn from (checkpoint id, snapshot build
  time, game file), so a new chosen checkpoint gets a new picture and nothing else is redrawn.
  Run as a subprocess by server.py (/api/start-board), since it executes the game's own Python file:
    python boards.py <game> <level> <variant> [carried|none]   prints one JSON answer
    python boards.py --openings <game>               prints every level's opening frame (for the site's static copy)
SRP/DRY check: Pass - drawing only. The start choice is the same order as server.play() and reads the same files
  (checkpoints.chosen, snapshots/<game>.json, snapshots/verified.json); replay follows sample.replay's action format.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import checkpoints  # noqa: E402

HOME = Path(os.environ.get("ARC3_RUNNER_HOME", Path.home() / "arc3-runner"))
ENV_DIR = Path(os.environ.get("ARC3_RUNNER_ENVIRONMENTS", HOME / "environment_files"))
SNAPSHOTS = Path(os.environ.get("ARC3_RUNNER_SNAPSHOTS", HOME / "snapshots"))
CACHE = HOME / "boards"


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError):
        return default


def game_file(game: str) -> Path:
    files = sorted(glob.glob(str(ENV_DIR / game / "*" / f"{game}.py")))
    if not files:
        raise FileNotFoundError(f"{game} is not among the runner's games")
    return Path(files[0])


def game_class(game: str):
    from arcengine import ARCBaseGame
    path = game_file(game)
    ns = {"__file__": str(path), "__name__": f"arc3_board_{game}"}
    exec(compile(path.read_text(), str(path), "exec"), ns)  # noqa: S102 - the game's own source, as the engine runs it
    classes = [v for v in ns.values() if isinstance(v, type) and issubclass(v, ARCBaseGame) and v is not ARCBaseGame]
    if not classes:
        raise RuntimeError(f"no game class in {path.name}")
    return classes[-1]


def as_grid(frame) -> list[list[int]]:
    return [[int(v) for v in row] for row in (frame.tolist() if hasattr(frame, "tolist") else frame)]


def fresh(cls):
    from arcengine import ActionInput, GameAction
    game = cls()
    fd = game.perform_action(ActionInput(id=GameAction.RESET), raw=True)
    return game, fd


def replay(cls, actions: list[dict]) -> list[list[int]]:
    """Every action from the first RESET (checkpoint format {name, data} or snapshot format {name, row, col})."""
    from arcengine import ActionInput, GameAction
    game, fd = fresh(cls)
    for a in actions:
        data = a["data"] if "data" in a else ({"x": a["col"], "y": a["row"]} if a["name"] == "ACTION6" else {})
        fd = game.perform_action(ActionInput(id=GameAction.from_name(a["name"]), data=data), raw=True)
    return as_grid(fd.frame[-1])


def opening(cls, level: int) -> tuple[list[list[int]], int]:
    """The level's clean opening frame and the game's level count. Level 1 is the frame after RESET; later levels are
    the level's clean sprites rendered by the game's camera, exactly as games-engine.js jump_level does."""
    from arcengine import GameState
    game, fd = fresh(cls)
    n = len(game._clean_levels)
    if level == 1:
        return as_grid(fd.frame[-1]), n
    t = level - 1
    game._levels[t] = game._clean_levels[t].clone()
    game.set_level(t)
    game._score = t
    game._state = GameState.NOT_FINISHED
    return as_grid(game.camera.render(game.current_level.get_sprites())), n


def start_for(game: str, level: int, variant: str) -> dict:
    """What server.play() would start from, in the same order: exact checkpoint, fresh game for level 1, verified
    stuck-level snapshot; otherwise nothing ({'kind': 'opening'})."""
    cp = checkpoints.chosen(game, level, variant)
    if cp is not None:
        return {"kind": "exact", "id": cp["id"], "path": cp["path"], "board_sha256": cp.get("board_sha256"),
                "actions_to_reach": cp.get("actions_to_reach"), "key": f"exact-{cp['id']}"}
    if level == 1:
        return {"kind": "reset", "key": "reset"}
    snap = read_json(SNAPSHOTS / f"{game}.json")
    verified = (read_json(SNAPSHOTS / "verified.json", {}) or {}).get(game)
    if snap and snap.get("stuck_level") == level and verified and verified.get("ok"):
        bare = not snap.get("actions") and not snap.get("turns")
        return {"kind": "reset" if bare else "rebuilt", "snap": snap, "key": f"snapshot-{snap.get('built', 'x')}"}
    return {"kind": "opening", "key": "opening"}


def replay_start_for(game: str, level: int, variant: str) -> dict:
    """What a No-context sample would start from (replays.start_for), in the shape draw() uses."""
    import replays   # imported here: replays imports this module
    r = replays.start_for(game, level, variant)
    if r is None:
        return {"kind": "opening", "key": "opening"}
    key = f"replay-{r['source']}-{r.get('checkpoint') or (r['expected'] or {}).get('board_sha256', 'first')[:16]}"
    return {"kind": "replay", "source": r["source"], "checkpoint": r.get("checkpoint"), "actions": r["actions"],
            "expected": r["expected"], "key": key}


def draw(game: str, level: int, variant: str, context: str = "carried") -> dict:
    start = replay_start_for(game, level, variant) if context == "none" else start_for(game, level, variant)
    src = game_file(game)
    exact_key = start["kind"] == "exact" or start.get("source") == "checkpoint"
    key = f"{context}-{level}-{variant if exact_key else 'any'}-{start['key']}-{int(src.stat().st_mtime)}"
    cache = CACHE / game / f"{key}.json"
    hit = read_json(cache)
    if hit:
        return hit
    cls = game_class(game)
    _, n = opening(cls, 1)
    if not 1 <= level <= n:
        raise ValueError(f"{game} has {n} levels")
    open_grid, _ = opening(cls, level)
    out = {"game": game, "level": level, "variant": variant, "levels": n, "kind": start["kind"], "context": context}
    if start["kind"] == "replay":
        grid = replay(cls, start["actions"])
        exp = start["expected"]
        out.update(replay_source=start["source"], checkpoint=start.get("checkpoint"), actions_to_reach=len(start["actions"]),
                   matches_saved_board=(hashlib.sha256(json.dumps(grid).encode()).hexdigest() == exp["board_sha256"])
                   if exp else grid == open_grid)
    elif start["kind"] == "exact":
        grid = replay(cls, read_json(Path(start["path"]) / "actions.json", []))
        saved = start["board_sha256"]
        out.update(checkpoint=start["id"], actions_to_reach=start["actions_to_reach"],
                   # checkpoints hash json.dumps of the engine grid (sample.grid_hash)
                   matches_saved_board=(hashlib.sha256(json.dumps(grid).encode()).hexdigest() == saved) if saved else None)
    elif start["kind"] == "rebuilt":
        snap = start["snap"]
        grid = replay(cls, snap["actions"])
        exp = snap.get("expected") or {}
        chars = exp.get("color_chars")
        text = "\n".join("".join(chars[v] for v in row) for row in grid) if chars else None
        out.update(actions_to_reach=len(snap["actions"]),
                   matches_saved_board=(hashlib.sha256(text.encode()).hexdigest() == exp.get("board_sha256")) if text else None)
    else:
        grid = open_grid
    out["grid"] = grid
    out["same_as_opening_frame"] = grid == open_grid
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, separators=(",", ":")))
    tmp.replace(cache)
    return out


def openings(game: str) -> dict:
    cls = game_class(game)
    _, n = opening(cls, 1)
    return {"game": game, "levels": n, "frames": [opening(cls, lv)[0] for lv in range(1, n + 1)]}


if __name__ == "__main__":
    if sys.argv[1] == "--openings":
        print(json.dumps(openings(sys.argv[2]), separators=(",", ":")))
    else:
        print(json.dumps(draw(sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "carried"),
                         separators=(",", ":")))
