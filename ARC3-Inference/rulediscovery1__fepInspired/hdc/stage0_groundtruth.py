# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Stage 0 of docs/plans/2026-09-24-hdc-ghost-roadmap.md (OpenMind, #arc-3, 24-Sep-2026 00:50 ET:
#   "do 1 but only for 20 traces"). Ground truth for the hyperdimensional time-model work: replays the first
#   20 recorded Ghost Twin plays (g50t-5849a774) through the exact local simulator (env.GameEnv) and writes,
#   per action: the action, the level, the player's position, every ghost's position (keyed by the order the
#   ghost was created in), whether this action was a rewind (the game starts a new run and turns the old run
#   into a ghost), and the number of successful player moves in the current run (the clock the game itself
#   uses to step ghosts). These are LABELS for testing only; the model in later stages never reads them.
#   Output: results/hdc/stage0_groundtruth.json. Needs Python 3.10+ (ARC3-Inference/.venv/bin/python).
# SRP/DRY check: Pass -- the simulator and the trace parsing are env.py / verify_env.py; this file only reads
#   Ghost Twin's state (its obfuscated attribute names are mapped once, in probe()) and saves it.
"""Stage 0: ground-truth player/ghost tracks for 20 Ghost Twin plays."""
from __future__ import annotations

import json
from pathlib import Path

from ..env import GameEnv
from ..verify_env import action_of, find_traces, load_rows

GAME, BUILD = "g50t", "5849a774"
OUT = Path(__file__).resolve().parent.parent / "results" / "hdc"


def probe(g) -> dict:
    """Ghost Twin state. vgwycxsxjz = level controller; dzxunlkwxt = player; rloltuowth = ghosts (dict in
    creation order: ghost -> its recorded path); areahjypvy = successful player moves this run."""
    w = g.vgwycxsxjz
    return {"player": [w.dzxunlkwxt.x, w.dzxunlkwxt.y],
            "ghosts": [[gh.x, gh.y] for gh in w.rloltuowth],
            "ghost_paths": [list(map(list, p)) for p in w.rloltuowth.values()],
            "run_moves": len(w.areahjypvy)}


def main(n: int = 20):
    OUT.mkdir(parents=True, exist_ok=True)
    env = GameEnv(GAME, BUILD)
    plays = []
    for path in find_traces(GAME, BUILD)[:n]:
        rows = [r for r in load_rows(path) if r.get("type") == "action"]
        env.reset()
        prev = probe(env.game)
        steps = []
        for r in rows:
            obs = env.step(action_of(r))
            cur = probe(env.game)
            steps.append({"action": r["action_name"], "level": obs.levels_completed,
                          "rewind": len(cur["ghosts"]) > len(prev["ghosts"]) or
                          (r["action_name"] == "ACTION5" and cur["run_moves"] < prev["run_moves"]),
                          **cur, "grid_matches_trace": obs.grid == (json.loads(r["board"]) if isinstance(r["board"], str) else r["board"])})
            prev = cur
        plays.append({"trace": str(path), "steps": steps})
    (OUT / "stage0_groundtruth.json").write_text(json.dumps(plays))
    n_steps = sum(len(p["steps"]) for p in plays)
    n_rew = sum(s["rewind"] for p in plays for s in p["steps"])
    n_ghost_steps = sum(bool(s["ghosts"]) for p in plays for s in p["steps"])
    exact = sum(all(s["grid_matches_trace"] for s in p["steps"]) for p in plays)
    with_ghost = sum(any(s["ghosts"] for s in p["steps"]) for p in plays)
    print(f"stage 0: {len(plays)} plays, {n_steps} actions, {n_rew} rewinds, {with_ghost} plays with a ghost, "
          f"{n_ghost_steps} actions with a ghost on the board; simulator matches the trace in {exact}/{len(plays)} plays")


if __name__ == "__main__":
    main()
