# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: OpenMind's rule discovery agent (this package) against the exact Locksmith simulator
#   (env.GameEnv, ls20-9607627b), asked in #arc-3 23-Sep-2026 22:43 ET ("run my thing against the
#   locksmith environment sim"). Plays several seeds for each agent setting plus a uniform-random
#   baseline, RESET offered as in the harness, and records what the agent actually achieved inside the
#   game, read from the game's own state (the obfuscated ls20 attribute names are mapped once, in PROBE):
#   levels cleared, lives lost, how many distinct cells the player block visited, how many times the key
#   changed shape / colour / rotation, whether the key ever matched a lock, how often the agent pressed
#   RESET, and at the end the top rule set and goal the agent believed in. Writes a JSON per play and a
#   markdown table. 23-Sep-2026 23:10 ET: two curiosity arms added (curiosity.py, EBUL last-layer entropy):
#   on top of the EFE policy, and curiosity alone.
#   Run: cd ARC3-Inference && .venv/bin/python -m rulediscovery1__fepInspired.locksmith_run
# SRP/DRY check: Pass -- agent, config and environment come from agent.py / env.py; play_live.py stays
#   the generic loop; this file only adds the Locksmith-specific probes and the settings sweep.
"""Rule discovery agent vs the exact Locksmith simulator, with in-game diagnostics."""
from __future__ import annotations

import argparse
import json
import random
import time
from multiprocessing import get_context
from pathlib import Path

from .agent import AgentConfig, RuleDiscoveryAgent
from .env import GameEnv
from .perception import Action

OUT = Path(__file__).parent / "results" / "env_ls20"
SETTINGS = {                                   # agent settings swept (name -> AgentConfig kwargs)
    "default": {},
    "prior_quarter": {"dl_weight": 0.25},
    "prior_twentieth": {"dl_weight": 0.05},
    "curious": {},                             # + EBUL-entropy curiosity on top of the EFE policy
    "curious_only": {},                        # EBUL-entropy curiosity alone
    "touch": {"dl_weight": 0.25},              # proposal step 1: walk to untouched objects (+ curiosity)
    "touch_fullprior": {},                     # same at the full prior
}
TOUCH = {"touch", "touch_fullprior"}
CURIOUS = {"curious": dict(pure=False, temperature=1.0),   # setting -> CuriosityConfig kwargs
           "curious_only": dict(pure=True, temperature=0.25),
           "touch": dict(pure=False, temperature=1.0), "touch_fullprior": dict(pure=False, temperature=1.0)}


def probe(g) -> dict:
    """Locksmith state, read from ls20's own attributes (names are obfuscated in the source):
    gudziatsk = player sprite, aqygnziho = lives left, fwckfzsyc / hiaauhahz / cklxociuu = key shape,
    colour and rotation indices, bejndxqqzf(i) = key matches lock i, lvrnuajbl = locks opened."""
    return {"pos": (g.gudziatsk.x, g.gudziatsk.y), "lives": g.aqygnziho,
            "key": (g.fwckfzsyc, g.hiaauhahz, g.cklxociuu),
            "match": any(g.bejndxqqzf(i) for i in range(len(g.plrpelhym))),
            "opened": sum(g.lvrnuajbl), "locks": len(g.plrpelhym)}


def play(job) -> dict:
    policy, setting, seed, budget = job
    env = GameEnv()
    obs = env.reset()
    valid = lambda o: o.valid_actions + ["RESET"]  # noqa: E731  (the harness offers RESET)
    rng = random.Random(seed)
    agent = None
    if policy == "agent":
        drive = None
        if setting in CURIOUS:
            from .curiosity import CuriosityConfig, CuriosityDrive, load_encoder
            drive = CuriosityDrive(load_encoder(), CuriosityConfig(**CURIOUS[setting]), seed=seed)
        explorer = None
        if setting in TOUCH:
            from .explore import ObjectContactExplorer
            explorer = ObjectContactExplorer()
        agent = RuleDiscoveryAgent(AgentConfig(seed=seed, **SETTINGS[setting]), curiosity=drive, explorer=explorer)
        agent.start_play(obs.grid, valid(obs), level=0)
    t0 = time.time()
    cells, key_changes, match_steps, resets, lives_lost, opened_max = set(), 0, 0, 0, 0, 0
    reasons = {}
    prev = probe(env.game)
    cells.add(prev["pos"])
    clears = []
    for n in range(1, budget + 1):
        a = agent.act() if agent else Action(rng.choice(valid(obs)))
        if agent and agent.last_decision is not None:
            r = agent.last_decision.mode
            reasons[r] = reasons.get(r, 0) + 1
        resets += a.name == "RESET"
        obs = env.step(a)
        if agent:
            agent.observe(a, obs.grid, level_completed=obs.level_completed, game_over=obs.state == "GAME_OVER",
                          level=obs.levels_completed, valid_actions=valid(obs))
        if obs.level_completed:
            clears.append(n)
        if obs.done:
            break
        cur = probe(env.game)
        cells.add(cur["pos"])
        key_changes += cur["key"] != prev["key"] and a.name != "RESET"
        match_steps += cur["match"]
        lives_lost += cur["lives"] < prev["lives"]
        opened_max = max(opened_max, cur["opened"])
        prev = cur
    out = {"policy": policy, "setting": setting, "seed": seed, "actions": n, "levels": obs.levels_completed,
           "clear_at": clears, "state": obs.state, "cells_visited": len(cells), "key_changes": key_changes,
           "steps_with_matching_key": match_steps, "locks_opened_max": opened_max, "resets": resets,
           "lives_lost": lives_lost + (obs.state == "GAME_OVER"), "seconds": round(time.time() - t0, 1)}
    if agent:
        s = agent.slow
        (h, w), = s.beliefs.top(1)
        out["top_ruleset"] = {"p": round(w, 3), "rules": h.ruleset.describe()}
        g = s.goals.top(1)
        out["top_goal"] = {"p": round(g[0][1], 3), "goal": g[0][0].describe()} if g else None
        ctl = s.ctx.state.agency.tracker.controlled()
        out["controlled_found"] = bool(ctl)
        out["decisions"] = reasons
        if agent.curiosity is not None:
            rw = agent.curiosity.rewards
            out["curiosity_bits_total"] = round(sum(rw), 1)
            out["curiosity_bits_first50"] = round(sum(rw[:50]), 1)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--budget", type=int, default=500)
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    from .curiosity import load_encoder
    load_encoder()                             # train and cache the EBUL encoder once, before the pool
    jobs = [("random", "-", s, args.budget) for s in range(args.seeds)]
    jobs += [("agent", k, s, args.budget) for k in SETTINGS for s in range(args.seeds)]
    t0 = time.time()
    with get_context("spawn").Pool(args.workers) as pool:
        rows = pool.map(play, jobs)
    (OUT / "locksmith_run.json").write_text(json.dumps(rows, indent=1, default=str))
    lines = [f"# Rule discovery agent vs exact Locksmith simulator ({args.seeds} seeds, {args.budget} actions, "
             f"RESET offered)", "",
             "| arm | levels (total) | game overs | cells visited (mean) | key changes (mean) | "
             "steps with matching key (mean) | resets (mean) | movement rule adopted |", "|---|---|---|---|---|---|---|---|"]
    arms = [("random", "-")] + [("agent", k) for k in SETTINGS]
    for pol, st in arms:
        rs = [r for r in rows if r["policy"] == pol and r["setting"] == st]
        mean = lambda k: sum(r[k] for r in rs) / len(rs)  # noqa: E731
        mv = "-" if pol == "random" else sum(any("mov" in x.lower() for x in r["top_ruleset"]["rules"]) for r in rs)
        lines.append(f"| {pol if pol == 'random' else 'agent ' + st} | {sum(r['levels'] for r in rs)} | "
                     f"{sum(r['state'] == 'GAME_OVER' for r in rs)} | {mean('cells_visited'):.1f} | "
                     f"{mean('key_changes'):.1f} | {mean('steps_with_matching_key'):.1f} | {mean('resets'):.1f} | {mv} |")
    lines.append(f"\nwall {time.time() - t0:.0f} s")
    text = "\n".join(lines)
    (OUT / "locksmith_run.md").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
