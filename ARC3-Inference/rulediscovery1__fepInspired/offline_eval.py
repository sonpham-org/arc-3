#!/usr/bin/env python3
# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Offline evaluation of the rule discovery prototype on saved ARC-3 plays (OpenMind, #arc-3,
#   23-Sep-2026 21:03 ET). WRITTEN, NOT RUN: OpenMind asked for the code only; nothing here has been
#   executed (only py_compile).
#   What it will do when run:
#     1. Load plays: ebul_perception.trace_paths(n) (the round-seven set), event-coded by
#        object_events.load_all (which advances the board after every step: no stale "before" board).
#     2. Folds: heldout_yardstick.folds (split "pass") or round5_combo.balanced_game_folds (split
#        "game"), as in round seven. Per fold, the few agent settings in CONFIG_GRID are compared on the
#        TRAINING plays only; the winner is scored on the test plays. Each play is scored within
#        itself (fresh beliefs per play, no carry across plays), back-off vocabulary seeded with the
#        training fold's labels and left open.
#     3. Per play, replay every step through the belief machinery in prequential order: rule context
#        before the outcome -> policy scores for every candidate action on the real pre board (the
#        agent does not act; it is asked what it WOULD probe) -> belief update -> goals / preferences
#        -> history -> periodic hypothesis proposal. Records:
#          nats_mix      prequential nats/step of the posterior mixture over rule sets
#          nats_backoff  the same for the chained back-off alone (handcolour -> +previous label: the
#                        round-seven "crafted-chain" setup with an open vocabulary) = the reference
#          policy agreement: share of steps where the agent's actual action was the EFE top choice,
#                        and its percentile rank among candidates; also the top-salience share (the
#                        round-one "picked a top-EIG candidate" statistic, now over rule-set disagreement)
#     4. Paired bootstrap over plays (heldout_yardstick.paired_boot), and game-cluster CIs, for
#        mixture vs back-off; per game type. Writes table.md and results.json under --out.
#   Run later (from ARC3-Inference/):  python -m rulediscovery1__fepInspired.offline_eval --n 250 --split pass --workers 8
# SRP/DRY check: Pass -- trace loading / event coding (object_events), folds and bootstrap
#   (heldout_yardstick, round5_combo), trace list (ebul_perception), belief / policy machinery (this
#   package). New: the replay driver and the policy-agreement statistics.
"""Replay saved plays: prequential nats of the rule-set posterior vs the chain back-off; policy agreement."""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import time
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from ._distill import ebul_perception, hy, oe, round7
from .agent import AgentConfig
from .beliefs import BeliefState, PlayScore
from .goals import GoalBeliefs, Preferences
from .hypotheses import HypothesisProposer
from .perception import Perceiver, Transition
from .policy import EFEPolicy, HabitPrior
from .rules import ContextBuilder

OUT = Path(__file__).resolve().parent / "results"
CONFIG_GRID = [
    {"propose_every": 5, "max_hypotheses": 8, "dl_weight": 1.0},
    {"propose_every": 5, "max_hypotheses": 8, "dl_weight": 0.25},
    {"propose_every": 10, "max_hypotheses": 4, "dl_weight": 1.0},
]


def _same_action(a, b, pre) -> bool:
    """Buttons by name; clicks by the clicked object's type (colour + shape), background by position."""
    if a.name != b.name:
        return False
    if not a.is_click:
        return True
    ca, cb = pre.comp_at(a.row, a.col), pre.comp_at(b.row, b.col)
    if ca is None or cb is None or ca.bg or cb.bg:
        return (a.row, a.col) == (b.row, b.col)
    return ca.type_key == cb.type_key


def replay_play(trace: "oe.Trace", cfg: AgentConfig, vocab0: Optional[list[str]] = None,
                rank_actions: bool = True) -> dict:
    """Prequential replay of one saved play. Returns per-play totals (see module docstring)."""
    trs: list[Transition] = Perceiver.transitions_from_trace(trace)
    beliefs = BeliefState(cfg.max_hypotheses, cfg.max_records, vocab0=vocab0, dl_weight=cfg.dl_weight)
    ctx, goals, prefs, habits = ContextBuilder(), GoalBeliefs(), Preferences(), HabitPrior()
    proposer, policy = HypothesisProposer(), EFEPolicy(cfg.policy, cfg.seed)
    score = PlayScore()
    top1 = ranked = top_sal = 0
    pct_sum = 0.0
    if trs:
        goals.bind_level(trs[0].pre)
    for n, tr in enumerate(trs):
        if tr.reset:
            ctx.observe(tr)
            if tr.post is not None:
                goals.bind_level(tr.post)
            continue
        rc = ctx.context(tr.pre, tr.action)
        if rank_actions:
            d = policy.choose(tr.pre, trace.valid, beliefs, goals, prefs, ctx, habits, greedy=True)
            order = sorted(d.scores, key=lambda s: -s.log_p)
            pos = next((i for i, s in enumerate(order) if _same_action(s.action, tr.action, tr.pre)), None)
            if pos is not None:
                ranked += 1
                top1 += int(pos == 0)
                pct_sum += 1.0 - pos / max(len(order) - 1, 1)
                sal_best = max(s.salience for s in order)
                top_sal += int(order[pos].salience >= sal_best - 1e-12)
        sur = beliefs.observe(rc, tr)
        score.add(sur)
        pred = beliefs.map_hypothesis().ruleset.predict(rc)
        goals.observe(tr, tr.pre.apply(pred.effects) if (pred is not None and pred.effects) else None)
        prefs.observe(tr)
        habits.observe(tr.action, tr.level_completed)
        ctx.observe(tr)
        if tr.level_completed and tr.post is not None:
            goals.bind_level(tr.post)
        if sur.spike or tr.level_completed or (n + 1) % cfg.propose_every == 0:
            beliefs.add_rulesets(proposer.propose(beliefs))
            beliefs.reduce()
    top = beliefs.top(1)
    return {"path": trace.path, "game": trace.nick, "gtype": trace.gtype, "steps": score.steps,
            "nats_mix": score.nats_mix, "nats_backoff": score.nats_backoff,
            "ranked": ranked, "top1": top1, "pct_rank_sum": pct_sum, "top_salience": top_sal,
            "final_rules": top[0][0].ruleset.describe() if top else [],
            "final_posterior_entropy": beliefs.posterior_entropy()}


def _job(args) -> dict:
    path, cfg_kw, vocab0, rank = args
    cfg = AgentConfig(**cfg_kw)
    from . import beliefs as _b
    _b.LIKELIHOOD = cfg.likelihood          # per-process setting (spawned workers do not inherit globals)
    t0 = time.time()
    out = replay_play(oe.load(path), cfg, vocab0, rank)
    out["seconds"] = time.time() - t0
    return out


def run_many(paths: list[str], cfg_kw: dict, vocab0: list[str], rank: bool, workers: int) -> list[dict]:
    jobs = [(p, cfg_kw, vocab0, rank) for p in paths]
    if workers > 1:
        with mp.get_context("spawn").Pool(workers) as pool:
            return pool.map(_job, jobs)
    return [_job(j) for j in jobs]


def per_play(results: list[dict], key: str) -> dict:
    return {r["path"]: (r[key], r["steps"]) for r in results}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=250)
    ap.add_argument("--split", choices=("pass", "game"), default="pass")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--no-rank", action="store_true", help="skip policy agreement (faster)")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--likelihood", choices=("parts", "label"), default="parts",
                    help="parts = rule predicts its own events, back-off supplies side effects; label = original")
    args = ap.parse_args()
    grid = [dict(c, likelihood=args.likelihood) for c in CONFIG_GRID]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    traces, _ = oe.load_all(ebul_perception().trace_paths(args.n), args.workers)
    r7 = round7()
    pairs = r7.r5.balanced_game_folds(traces)[0] if args.split == "game" else hy.folds(traces, args.split)
    results, chosen = [], []
    for f, (train, test) in enumerate(pairs):
        vocab0 = r7.vocab_of(hy.support_of(train), True)
        best, best_nats = None, None
        for cfg_kw in grid:                      # selection on the training plays only
            tr_res = run_many([t.path for t in train], cfg_kw, vocab0, False, args.workers)
            nats = sum(r["nats_mix"] for r in tr_res) / max(sum(r["steps"] for r in tr_res), 1)
            if best_nats is None or nats < best_nats:
                best, best_nats = cfg_kw, nats
        chosen.append({"fold": f, "config": best, "train_nats_per_step": best_nats})
        res = run_many([t.path for t in test], best, vocab0, not args.no_rank, args.workers)
        for r in res:
            r["fold"] = f
        results += res
    keys = [r["path"] for r in results]
    clusters = {r["path"]: r["game"] for r in results}
    mix, ref = per_play(results, "nats_mix"), per_play(results, "nats_backoff")
    table = {"all": hy.paired_boot(mix, ref, keys),
             "all_game_cluster": hy.paired_boot(mix, ref, keys, clusters=clusters)}
    by_type = defaultdict(list)
    for r in results:
        by_type[r["gtype"]].append(r["path"])
    for gt, ks in sorted(by_type.items()):
        table[gt] = hy.paired_boot(mix, ref, ks)
    ranked = sum(r["ranked"] for r in results)
    agree = {"top1_share": sum(r["top1"] for r in results) / max(ranked, 1),
             "mean_percentile": sum(r["pct_rank_sum"] for r in results) / max(ranked, 1),
             "top_salience_share": sum(r["top_salience"] for r in results) / max(ranked, 1),
             "ranked_steps": ranked}
    lines = [f"# Rule discovery prototype, offline replay ({args.split} split, {len(results)} plays, "
             f"likelihood={args.likelihood})", "",
             "| arm | nats/step | gain vs chain back-off (95% CI) |", "|---|---|---|"]
    for k, v in table.items():
        lines.append(f"| {k} | {v['nats']:.3f} | {v['gain']:+.3f} [{v['gain_ci'][0]:+.3f}, {v['gain_ci'][1]:+.3f}] |")
    lines += ["", f"policy agreement with the played action: {json.dumps(agree)}",
              f"configs chosen on training folds: {json.dumps(chosen)}", f"wall seconds: {time.time() - t0:.1f}"]
    (out / f"table_{args.split}.md").write_text("\n".join(lines) + "\n")
    (out / f"results_{args.split}.json").write_text(json.dumps(
        {"table": table, "agreement": agree, "chosen": chosen, "plays": results,
         "grid": CONFIG_GRID, "agent_defaults": asdict(AgentConfig())}, indent=1, default=str))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
