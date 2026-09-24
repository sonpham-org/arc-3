# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026 (tensor-logic arms 24-September-2026)
# PURPOSE: Proposal step 5 (docs/plans/2026-09-23-rulediscovery-locksmith-score.md): check that what
#   helped on Locksmith is not a Locksmith-only trick. Plays any locally available game build (env.GameEnv)
#   with a uniform-random baseline, the rule agent (quarter prior), and the rule agent with the
#   object-contact explorer plus EBUL curiosity, several seeds each, RESET offered as in the harness.
#   Reports levels cleared, the action at which each level was cleared, and game overs. Game-agnostic:
#   no game internals are read (unlike locksmith_run.py's Locksmith probes).
#   Run: cd ARC3-Inference && .venv/bin/python -m rulediscovery1__fepInspired.game_sweep --games g50t:5849a774 wa30:ee6fef47
#   24-Sep-2026 HDC integration A/B (OpenMind 10:17 ET): arms touch_hdc (touch + AgentConfig.use_hdc, all pieces)
#   and touch_tape / touch_walls / touch_fate (one piece each); --arms picks arms, --tag writes to
#   results/game_sweep/<tag>/ (the first sweep's files stay). Every play also reports prediction quality from the
#   agent's own prequential surprise: nats per scored step under its posterior and under the counts-only back-off
#   (their difference = what the rules add), the same on steps where the ghost tape made a prediction, how many
#   such steps, runs (rewinds) seen, and whether the tape rule is in the final MAP rule set.
#   24-Sep-2026 tensor-logic overhaul (OpenMind): arms touch_tl (touch + AgentConfig.use_tl: tensor-logic rule learning
#   ADDED next to the templates) and tl_only (use_tl with the hand-written templates off: rules from tensor logic only,
#   explorer mover from the learned program). Extra per-play fields: steps on which the MAP rule set held a learned
#   rule, distinct learned rules the posterior ever made MAP, learned rules in the final MAP, active equations and
#   when they switched on, learner seconds, and the final MAP's learned clauses in plain words.
# SRP/DRY check: Pass -- environment, agent, explorer and curiosity are the package's own; this file is
#   only the loop over games, arms and seeds, and the table.
"""Random vs rule agent vs rule agent + explorer on any local game build."""
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

OUT = Path(__file__).parent / "results" / "game_sweep"
ARMS = ("random", "agent", "touch")
HDC_ARMS = {"touch_hdc": ("tape", "walls", "fate"), "touch_tape": ("tape",), "touch_walls": ("walls",),
            "touch_fate": ("fate",)}
TL_ARMS = {"touch_tl": {"use_tl": True, "tl_templates": True}, "tl_only": {"use_tl": True, "tl_templates": False}}
ALL_ARMS = ARMS + tuple(HDC_ARMS) + tuple(TL_ARMS)


def play(job) -> dict:
    game, build, arm, seed, budget = job
    env = GameEnv(game, build)
    obs = env.reset()
    valid = lambda o: o.valid_actions + ["RESET"]  # noqa: E731
    rng = random.Random(seed)
    agent = None
    if arm != "random":
        drive = explorer = None
        if arm == "touch" or arm in HDC_ARMS or arm in TL_ARMS:
            from .curiosity import CuriosityConfig, CuriosityDrive, load_encoder
            from .explore import ObjectContactExplorer
            drive = CuriosityDrive(load_encoder(), CuriosityConfig(temperature=1.0), seed=seed)
            explorer = ObjectContactExplorer()
        cfg = AgentConfig(seed=seed, dl_weight=0.25, use_hdc=arm in HDC_ARMS, hdc_pieces=HDC_ARMS.get(arm, ()),
                          **TL_ARMS.get(arm, {}))
        agent = RuleDiscoveryAgent(cfg, curiosity=drive, explorer=explorer)
        agent.start_play(obs.grid, valid(obs), level=0)
    clears, t0 = [], time.time()
    q = {"nats": 0.0, "nats_counts": 0.0, "steps": 0, "tape_nats": 0.0, "tape_nats_counts": 0.0, "tape_steps": 0}
    tl_map_steps, tl_ever = 0, set()
    for n in range(1, budget + 1):
        if agent:
            a = agent.act()
        else:                                            # random baseline: a click needs a random board cell
            name = rng.choice(valid(obs))
            a = Action(name, rng.randrange(64), rng.randrange(64)) if name == "ACTION6" else Action(name)
        obs = env.step(a)
        if agent:
            hdc = agent.slow.ctx.hdc
            taped = hdc is not None and hdc.annot.get("tape") is not None
            rep = agent.observe(a, obs.grid, level_completed=obs.level_completed, game_over=obs.state == "GAME_OVER",
                                level=obs.levels_completed, valid_actions=valid(obs))
            if rep.transition.scored:
                q["nats"] += rep.surprise.surprisal
                q["nats_counts"] += rep.surprise.backoff_surprisal
                q["steps"] += 1
                if agent.tl_source is not None:
                    tl_in = [r for r in agent.slow.beliefs.map_hypothesis().ruleset.rules() if r.template == "tl"]
                    tl_map_steps += bool(tl_in)
                    tl_ever |= {r.key() for r in tl_in}
                if taped:
                    q["tape_nats"] += rep.surprise.surprisal
                    q["tape_nats_counts"] += rep.surprise.backoff_surprisal
                    q["tape_steps"] += 1
        if obs.level_completed:
            clears.append(n)
        if obs.done:
            break
    out = {"game": game, "arm": arm, "seed": seed, "levels": obs.levels_completed, "clear_at": clears,
           "actions": n, "state": obs.state, "seconds": round(time.time() - t0, 1)}
    if agent:
        out.update({k: round(v, 3) for k, v in q.items()})
        hdc = agent.slow.ctx.hdc
        out["runs_seen"] = len(hdc.tape.finder.runs) if hdc is not None and hdc.tape is not None else None
        out["trips"] = agent.explorer.trips if agent.explorer is not None else None
        out["tape_in_map"] = any(r.template == "tape" for r in agent.slow.beliefs.map_hypothesis().ruleset.rules())
        src = agent.tl_source
        if src is not None:
            final = [r for r in agent.slow.beliefs.map_hypothesis().ruleset.rules() if r.template == "tl"]
            L = src.learner
            out.update({"tl_map_steps": tl_map_steps, "tl_ever_map": len(tl_ever), "tl_final_map": len(final),
                        "tl_active": "".join(sorted(L.active)), "tl_activated": L.activated[:12],
                        "tl_fit_seconds": round(L.seconds, 1), "tl_fits": L.fits,
                        "tl_trips": explorer.trips if explorer is not None else None,
                        "tl_clauses": [c for r in final for c in r.clauses()[:8]][:16],
                        "tl_final_rules": [r.describe()[:200] for r in final],
                        "tl_explanations": L.explanations[:5]})
            out["map_rules"] = agent.slow.beliefs.map_hypothesis().ruleset.describe()[:12]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--games", nargs="+", required=True, help="game:build, e.g. g50t:5849a774")
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--budget", type=int, default=500)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--arms", nargs="+", default=list(ARMS), choices=list(ALL_ARMS))
    ap.add_argument("--tag", default="", help="write to results/game_sweep/<tag>/ instead of results/game_sweep/")
    args = ap.parse_args()
    out_dir = OUT / args.tag if args.tag else OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    arms = tuple(args.arms)
    from .curiosity import load_encoder
    load_encoder()
    games = [tuple(g.split(":")) for g in args.games]
    jobs = [(g, b, arm, s, args.budget) for g, b in games for s in range(args.seeds) for arm in arms]
    t0 = time.time()
    with get_context("spawn").Pool(args.workers) as pool:
        rows = []
        for r in pool.imap_unordered(play, jobs):            # progress to the log as plays finish
            rows.append(r)
            print(json.dumps(r), flush=True)
            (out_dir / "rows.partial.json").write_text(json.dumps(rows, indent=1))
    lines = [f"# Game sweep ({args.seeds} seeds, {args.budget} actions, RESET offered)", "",
             "| game | arm | levels (total) | plays clearing a level | first clear at (median action) | game overs "
             "| nats/step (posterior) | nats/step (counts) |",
             "|---|---|---|---|---|---|---|---|"]
    for g, _ in games:
        for arm in arms:
            rs = [r for r in rows if r["game"] == g and r["arm"] == arm]
            firsts = sorted(r["clear_at"][0] for r in rs if r["clear_at"])
            med = firsts[len(firsts) // 2] if firsts else "-"
            steps = sum(r.get("steps", 0) for r in rs)
            nats = f"{sum(r['nats'] for r in rs) / steps:.3f}" if steps else "-"
            cnts = f"{sum(r['nats_counts'] for r in rs) / steps:.3f}" if steps else "-"
            lines.append(f"| {g} | {arm} | {sum(r['levels'] for r in rs)} | {sum(bool(r['clear_at']) for r in rs)} | "
                         f"{med} | {sum(r['state'] == 'GAME_OVER' for r in rs)} | {nats} | {cnts} |")
    lines.append(f"\nwall {time.time() - t0:.0f} s")
    text = "\n".join(lines)
    (out_dir / "table.md").write_text(text + "\n")
    (out_dir / "rows.json").write_text(json.dumps(rows, indent=1))
    print(text)


if __name__ == "__main__":
    main()
