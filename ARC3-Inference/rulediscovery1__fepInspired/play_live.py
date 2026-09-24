# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Live play of the rule discovery agent (agent.RuleDiscoveryAgent) against the exact local
#   simulator (env.GameEnv), with no language model and no GPU: the "play the games live" step proposed
#   to OpenMind in #arc-3 (23-Sep-2026 22:31 ET). Also plays a uniform-random baseline with the same
#   action budget, so the agent's number has something to stand against. Reports levels cleared, actions
#   per cleared level, game-overs and wall time per seed. Game over ends a play (as on Kaggle). RESET is
#   offered like the harness does (--no-reset to withhold it).
#   Run: cd ARC3-Inference && .venv/bin/python -m rulediscovery1__fepInspired.play_live --budget 300 --seeds 3
# SRP/DRY check: Pass -- the agent, its config and the environment come from agent.py / env.py; this
#   file is only the loop and the tally.
"""Play a game live with the rule discovery agent (and a random baseline) in the local simulator."""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

from .agent import AgentConfig, RuleDiscoveryAgent
from .env import DEFAULT_BUILD, DEFAULT_GAME, GameEnv
from .perception import Action


def play(env: GameEnv, policy: str, budget: int, seed: int, offer_reset: bool = True) -> dict:
    obs = env.reset()
    # the Kaggle harness lets the model send RESET (restart the level; in Locksmith that also restores
    # the three lives), so it is offered here too unless --no-reset
    valid = lambda o: o.valid_actions + (["RESET"] if offer_reset else [])  # noqa: E731
    rng = random.Random(seed)
    agent = None
    if policy == "agent":
        agent = RuleDiscoveryAgent(AgentConfig(seed=seed))
        agent.start_play(obs.grid, valid(obs), level=obs.levels_completed)
    clears, t0 = [], time.time()
    for n in range(1, budget + 1):
        a = agent.act() if agent else Action(rng.choice(valid(obs)))
        obs = env.step(a)
        if agent:
            agent.observe(a, obs.grid, level_completed=obs.level_completed, game_over=obs.state == "GAME_OVER",
                          level=obs.levels_completed, valid_actions=valid(obs))
        if obs.level_completed:
            clears.append(n)
        if obs.done:
            break
    return {"policy": policy, "seed": seed, "resets_offered": offer_reset, "actions": n, "levels": obs.levels_completed, "clear_at": clears,
            "state": obs.state, "seconds": round(time.time() - t0, 1)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game", default=DEFAULT_GAME)
    ap.add_argument("--build", default=DEFAULT_BUILD)
    ap.add_argument("--budget", type=int, default=300, help="actions per play")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--no-reset", action="store_true", help="do not offer RESET")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    env = GameEnv(args.game, args.build)
    rows = []
    for pol in ("random", "agent"):
        for s in range(args.seeds):
            r = play(env, pol, args.budget, s, not args.no_reset)
            rows.append(r)
            print(json.dumps(r), flush=True)
    if args.out:
        Path(args.out).write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
