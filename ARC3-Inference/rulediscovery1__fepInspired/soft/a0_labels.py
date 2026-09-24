# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Stage A0 of docs/plans/2026-09-24-soft-agent-roadmap.md (OpenMind, #arc-3, 09:15 ET "do it!"):
#   ground-truth LABELS for the perception stages A1-A4, made by replaying recorded plays through the exact
#   local simulator (env.GameEnv). Labels only -- the soft perception never reads them.
#   Per action of every play: the board after the action (as the harness saw it), and for every engine sprite
#   whose position changed: its name, its displacement, and its exact pixel mask on the 64x64 frame (rendered
#   alone with the game's own camera, compared with an empty render), plus every sprite whose visibility flipped
#   (for co-change links). Per play: the "player" sprite name (the sprite that moves most on arrow presses),
#   and per arrow action whether the player moved (blocked or not). Gauges are game-specific accessors
#   (Locksmith's step counter and lives, Ghost Twin's timer); other games get none.
#   Games: Locksmith (ls20), Ghost Twin (g50t), Warehouse Associates (wa30) -- 20 plays each -- plus the plays
#   available for sp80 and cn04. Output results/soft/a0_<game>.jsonl (one play per line).
# SRP/DRY check: Pass -- simulator, trace finding and parsing are env.py / verify_env.py; this file only reads
#   the engine's sprites and writes labels.
"""A0: engine ground truth for the soft-perception stages."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np

from ..env import GameEnv
from ..verify_env import action_of, find_traces, load_rows

OUT = Path(__file__).resolve().parent.parent / "results" / "soft"
GAMES = [("ls20", "9607627b", 20), ("g50t", "5849a774", 20), ("wa30", "ee6fef47", 20),
         ("sp80", "589a99af", 20), ("cn04", "2fe56bfb", 20)]
ARROWS = {"ACTION1", "ACTION2", "ACTION3", "ACTION4"}


def gauges(game_id, g) -> dict:
    try:
        if game_id == "ls20":
            return {"steps": int(g._step_counter_ui.current_steps), "lives": int(g.aqygnziho)}
        if game_id == "g50t":
            return {"timer_x": int(g.twyixucrqi.x)}
    except Exception:            # level transition frames can lack the attributes
        return {}
    return {}


def snapshot(g):
    return {id(s): (s.name, s.x, s.y, bool(s.is_visible), s) for s in g.current_level.get_sprites()}


def mask_of(g, sprite, bg):
    m = np.asarray(g.camera.render([sprite])) != bg
    return np.flatnonzero(m).tolist()


def label_play(env, game_id, path):
    rows = [r for r in load_rows(path) if r.get("type") == "action"]
    env.reset()
    g = env.game
    prev = snapshot(g)
    steps = []
    for r in rows:
        obs = env.step(action_of(r))
        g = env.game
        cur = snapshot(g)
        bg = np.asarray(g.camera.render([]))
        moved, toggled = [], []
        for k, (name, x, y, vis, s) in cur.items():
            if k in prev:
                _, px, py, pvis, _ = prev[k]
                if (x, y) != (px, py) and vis:
                    moved.append({"sprite": k, "name": name, "dx": x - px, "dy": y - py, "mask": mask_of(g, s, bg)})
                if vis != pvis:
                    toggled.append({"sprite": k, "name": name, "visible": vis})
        steps.append({"action": r["action_name"], "levels": obs.levels_completed, "state": obs.state,
                      "board": obs.grid, "moved": moved, "toggled": toggled, "gauges": gauges(game_id, g)})
        prev = cur
    # the player: the sprite name that moves most often on arrow presses
    cnt = Counter(m["name"] for s in steps if s["action"] in ARROWS for m in s["moved"])
    player = cnt.most_common(1)[0][0] if cnt else None
    for s in steps:
        if s["action"] in ARROWS:
            s["player_moved"] = any(m["name"] == player for m in s["moved"])
    return {"trace": str(path), "player": player, "steps": steps}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for game_id, build, n in GAMES:
        env = GameEnv(game_id, build)
        paths = find_traces(game_id, build)[:n]
        tot_steps = tot_moved = blocked = arrows = 0
        with open(OUT / f"a0_{game_id}.jsonl", "w") as fh:
            for p in paths:
                play = label_play(env, game_id, p)
                fh.write(json.dumps(play) + "\n")
                tot_steps += len(play["steps"])
                tot_moved += sum(len(s["moved"]) for s in play["steps"])
                arrows += sum(1 for s in play["steps"] if "player_moved" in s)
                blocked += sum(1 for s in play["steps"] if s.get("player_moved") is False)
        print(f"A0 {game_id}: {len(paths)} plays, {tot_steps} actions, {tot_moved} sprite moves, "
              f"{arrows} arrow presses ({blocked} blocked)", flush=True)


if __name__ == "__main__":
    main()
