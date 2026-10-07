# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Check that the tensor-logic overhaul changes nothing when it is switched off (AgentConfig.use_tl False, the
#   default): play the "touch" arm of game_sweep (rule agent + object-contact explorer + EBUL curiosity) with the
#   current package and with the pre-overhaul backup (../backupsOldVersions/rulediscovery1__fepInspired_6e55c3332208,
#   imported as its own package), same game, seed and budget, and compare the actions and outcomes step by step.
#   Run: .venv/bin/python -m rulediscovery1__fepInspired.tl.verify_default --games ls20:9607627b g50t:5849a774 --seeds 0 1
#   24-Sep-2026 debate picks (Claude Opus 5.5 (Bubba)): --backup names the backup package to compare with, --arms the
#   game_sweep arms whose AgentConfig is built on BOTH packages (touch, touch_tl, tl_only), --out the result file; the
#   defaults are the original check.
#   25-Sep-2026 stage one (Claude Opus 5.5 (Bubba)): an arm's AgentConfig keywords now come from EACH package's own
#   game_sweep.TL_ARMS (so last night's arms, e.g. dp_all, can be compared too); a package without that table falls back
#   to the three original arms.
# SRP/DRY check: Pass -- uses game_sweep's own arm construction on both packages; only the comparison is new.
"""Default-off equivalence: current package (use_tl False) vs the pre-overhaul backup, action for action."""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from multiprocessing import get_context
from pathlib import Path

BACKUP = "rulediscovery1__fepInspired_6e55c3332208"
BACKUP_DIR = Path(__file__).resolve().parents[2] / "backupsOldVersions"


def trace(job) -> list:
    pkg, game, build, seed, budget = job[:5]
    arm = job[5] if len(job) > 5 else "touch"
    if pkg != "rulediscovery1__fepInspired" and str(BACKUP_DIR) not in sys.path:
        sys.path.insert(0, str(BACKUP_DIR))
        sys.path.insert(0, str(BACKUP_DIR.parent / "distill"))   # the backup's _distill looks one level too high
    A = importlib.import_module(f"{pkg}.agent")
    E = importlib.import_module("rulediscovery1__fepInspired.env")   # the environment (not agent code): one copy
    C = importlib.import_module(f"{pkg}.curiosity")
    X = importlib.import_module(f"{pkg}.explore")
    env = E.GameEnv(game, build)
    obs = env.reset()
    valid = lambda o: o.valid_actions + ["RESET"]  # noqa: E731
    drive = C.CuriosityDrive(C.load_encoder(), C.CuriosityConfig(temperature=1.0), seed=seed)
    kws = {"touch": {}, "touch_tl": {"use_tl": True, "tl_templates": True},
           "tl_only": {"use_tl": True, "tl_templates": False}}
    try:
        kws.update(importlib.import_module(f"{pkg}.game_sweep").TL_ARMS)
    except (ImportError, AttributeError):
        pass
    kw = kws[arm]
    agent = A.RuleDiscoveryAgent(A.AgentConfig(seed=seed, dl_weight=0.25, **kw), curiosity=drive,
                                 explorer=X.ObjectContactExplorer())
    agent.start_play(obs.grid, valid(obs), level=0)
    out = []
    for _ in range(budget):
        a = agent.act()
        obs = env.step(a)
        agent.observe(a, obs.grid, level_completed=obs.level_completed, game_over=obs.state == "GAME_OVER",
                      level=obs.levels_completed, valid_actions=valid(obs))
        out.append((a.name, a.row, a.col, obs.levels_completed, obs.state))
        if obs.done:
            break
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--games", nargs="+", default=["ls20:9607627b", "g50t:5849a774"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1])
    ap.add_argument("--budget", type=int, default=200)
    ap.add_argument("--backup", default=BACKUP)
    ap.add_argument("--arms", nargs="+", default=["touch"], help="touch, touch_tl, tl_only or any game_sweep TL arm")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[1] / "results" / "tl" / "verify_default.json"))
    args = ap.parse_args()
    jobs, keys = [], []
    for g in args.games:
        game, build = g.split(":")
        for s in args.seeds:
            for arm in args.arms:
                for pkg in ("rulediscovery1__fepInspired", args.backup):
                    jobs.append((pkg, game, build, s, args.budget, arm))
                    keys.append((game, s, arm, pkg))
    with get_context("spawn").Pool(min(len(jobs), args.workers)) as pool:
        res = pool.map(trace, jobs)
    by = dict(zip(keys, res))
    report = []
    for g in args.games:
        game = g.split(":")[0]
        for s in args.seeds:
            for arm in args.arms:
                a, b = by[(game, s, arm, "rulediscovery1__fepInspired")], by[(game, s, arm, args.backup)]
                first = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), None)
                same = first is None and len(a) == len(b)
                report.append({"game": game, "seed": s, "arm": arm, "actions": len(a), "identical": same,
                               "first_difference": first})
                print(json.dumps(report[-1]), flush=True)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
