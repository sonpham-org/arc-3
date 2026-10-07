# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026 (tensor-logic arms 24-September-2026, debate three, four and five 25-September-2026)
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
#   24-Sep-2026 debate picks (OpenMind 22:49 ET; Claude Opus 5.5 (Bubba)): arms dp_self / dp_face / dp_epi / dp_arch /
#   dp_goal (one pick each on top of touch_tl), dp_s12 / dp_s123 (picks in build order) and dp_all. Extra per-play fields:
#   presses per action, decision modes, changes of the tracker's controlled type, the self model's tallies, steps on
#   which the MAP rule set held a Facing clause and the final ones in words, explorer preemptions, archive cells and
#   returns, the contrast log. --max_seconds sets a per-play alarm (a timed-out play is recorded as TIMEOUT and left out
#   of the table); --hook names an OUTSIDE labeller (game internals for scoring only, never shown to the agent);
#   --first_seed shifts the seed range. Without these flags a play is exactly as before.
#   25-Sep-2026 stage one (docs 2026-09-25-warehouse-expert-debate-2.md, OpenMind #arc-3 02:38 ET; Claude Opus 5.5 (Bubba)):
#   arms s1_keep (touch_tl + self + epistemic + archive: last night's kept picks, no facing, no contrast), s1_handoff
#   (+ explore_handoff), s1_budget (+ use_budget), s1_both (+ both). Extra per-play fields: hand-offs by trigger, trip and
#   dwell steps, and the budget's gauge / forecast / RESET bookkeeping.
#   25-Sep-2026 debate three (docs 2026-09-25-warehouse-expert-debate-3.md, OpenMind #arc-3 05:47 ET; Claude Opus 5.5 (Bubba)):
#   arms on top of s1_both, each new pick replacing its stage-one piece: d3_handoff (EFE-compared interruption instead of
#   the stage-one hand-off; stage-one budget), d3_contact (stage one + contact-neighbourhood context), d3_budget (stage-one
#   hand-off + learnable end belief / plan-aware urgency), d3_all (all three new picks). Extra per-play fields: EFE checks
#   and interruptions by trigger, resumed trips; contact presses / changes; lives found, run-out tests, plan-fits and
#   cheap-end steps, the final P(run-out is fatal). d3_hb (added after the main sweep): picks 1 and 3 without pick 2.
#   25-Sep-2026 debate four (docs 2026-09-25-warehouse-expert-debate-4.md, OpenMind #arc-3 11:24 ET; Claude Opus 5.5 (Bubba)):
#   arms on top of d3_hb (debate three's kept configuration): d4_opt (pick 1: option-value interruption + try-once per new
#   contact class), d4_ov / d4_try (pick 1's two halves alone, for attribution), d4_goal (pick 2: goal babbling + contrast on
#   action-caused change), d4_both (1 + 2), d4_all (1 + 2 + 3, gated contact novelty), d4_opt3 (1 + 3; added after the main
#   sweep because pick 2 cost Ghost Twin clears). Extra per-play fields: the agent's
#   check log (every EFE check: step, trigger, what won, action, remaining trip steps, G of continuing / of the best
#   non-moving button / of the best move), try-once presses and new contact classes; goal babbling's episodes, plan
#   attempts, weights and log; the caused-change shares of the top goals; gated contact presses.
#   25-Sep-2026 debate five (docs 2026-09-25-openmind-agent-expert-debate-5.md picks 2 and 3, OpenMind #arc-3 17:14 ET; Claude
#   Opus 5.5 (Bubba)): arms on top of d4_opt: d5_flat (pick 2: flat outcome preferences until the first clear), d5_lib
#   (pick 3: rule library + MDL reuse discount + self-move carry-over), d5_both (2 + 3), d5_flat_notry (pick 2 without
#   debate four's try-once, to see whether try-once still matters). Every agent play now also records, per restart
#   (level clear, RESET, lost life = a run-out the play survived), the actions until the MAP rule set is right again (its
#   predicted parts all occur) on 5 scored steps in a row (None if the next restart or the end came first) and whether
#   the rule set that was MAP just before is still a hypothesis / MAP 10 actions later ("relearn"); with the library on,
#   its report. Measurement only.
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
from .beliefs import rule_missed
from .env import GameEnv
from .perception import Action

OUT = Path(__file__).parent / "results" / "game_sweep"
ARMS = ("random", "agent", "touch")
HDC_ARMS = {"touch_hdc": ("tape", "walls", "fate"), "touch_tape": ("tape",), "touch_walls": ("walls",),
            "touch_fate": ("fate",)}
TL_ARMS = {"touch_tl": {"use_tl": True, "tl_templates": True}, "tl_only": {"use_tl": True, "tl_templates": False}}
# Debate picks (24-Sep-2026): each pick on top of touch_tl, alone and cumulatively in build order, and all five together
_B = {"use_tl": True, "tl_templates": True}
DP_ARMS = {"dp_self": {**_B, "use_self": True},
           "dp_face": {**_B, "tl_facing": True},
           "dp_epi": {**_B, "use_epistemic": True},
           "dp_arch": {**_B, "use_archive": True},
           "dp_goal": {**_B, "goal_contrast": True},
           "dp_s12": {**_B, "use_self": True, "tl_facing": True},
           "dp_s123": {**_B, "use_self": True, "tl_facing": True, "use_epistemic": True},
           "dp_all": {**_B, "use_self": True, "tl_facing": True, "use_epistemic": True, "use_archive": True,
                      "goal_contrast": True}}
# Stage one (25-Sep-2026): last night's kept picks, then the explorer hand-off and the budget, alone and together
_K = {**_B, "use_self": True, "use_epistemic": True, "use_archive": True}
S1_ARMS = {"s1_keep": _K, "s1_handoff": {**_K, "explore_handoff": True}, "s1_budget": {**_K, "use_budget": True},
           "s1_both": {**_K, "explore_handoff": True, "use_budget": True}}
# Debate three (25-Sep-2026): each new pick on s1_both in place of its stage-one piece, and all three new picks together
_S1B = {**_K, "explore_handoff": True, "use_budget": True}
D3_ARMS = {"d3_handoff": {**_K, "handoff_efe": True, "use_budget": True},
           "d3_contact": {**_S1B, "contact_context": True},
           "d3_budget": {**_S1B, "budget_learn": True},
           "d3_all": {**_K, "handoff_efe": True, "contact_context": True, "use_budget": True, "budget_learn": True},
           # added after the main sweep: picks 1 and 3 without pick 2 (pick 2 cost every Ghost Twin clear)
           "d3_hb": {**_K, "handoff_efe": True, "use_budget": True, "budget_learn": True}}
# Debate four (25-Sep-2026): each pick on top of d3_hb, pick 1's halves alone, picks together
_HB = D3_ARMS["d3_hb"]
_P1 = {"option_value": True, "try_once": True}
_P2 = {"goal_babble": True, "goal_contrast": True, "caused_contrast": True}
D4_ARMS = {"d4_opt": {**_HB, **_P1},
           "d4_ov": {**_HB, "option_value": True},
           "d4_try": {**_HB, "try_once": True},
           "d4_goal": {**_HB, **_P2},
           "d4_both": {**_HB, **_P1, **_P2},
           "d4_all": {**_HB, **_P1, **_P2, "contact_gated": True},
           # added after the main sweep: picks 1 and 3 without pick 2 (pick 2 cost Ghost Twin clears)
           "d4_opt3": {**_HB, **_P1, "contact_gated": True}}
# Debate five (25-Sep-2026): picks 2 and 3 on top of d4_opt (debate four's kept configuration), and pick 2 without try-once
_D4 = D4_ARMS["d4_opt"]
D5_ARMS = {"d5_flat": {**_D4, "flat_prefs": True},
           "d5_lib": {**_D4, "carry_library": True},
           "d5_both": {**_D4, "flat_prefs": True, "carry_library": True},
           "d5_flat_notry": {**_HB, "option_value": True, "flat_prefs": True}}
TL_ARMS = {**TL_ARMS, **DP_ARMS, **S1_ARMS, **D3_ARMS, **D4_ARMS, **D5_ARMS}
RELEARN_RUN = 5          # debate five: MAP right on this many scored steps in a row = re-learned
RELEARN_KEEP = 10        # ... and whether the pre-restart MAP rule set is still there this many actions later


class Relearn:
    """Per restart (clear / RESET / lost life): actions until the MAP rule set is right RELEARN_RUN scored steps in a row;
    whether the rule set that was MAP just before is still a hypothesis (and MAP) RELEARN_KEEP actions later."""

    def __init__(self):
        self.open, self.done, self.ends = [], [], 0

    def step(self, n, agent, a, obs, rep, pre_key) -> None:
        s = agent.slow.beliefs
        for e in self.open:
            if rep.transition.scored:
                p = rep.surprise.predicted          # the MAP's own hit test (parts of its prediction all occurred)
                e["run"] = e["run"] + 1 if (p is not None and not rule_missed(p, rep.surprise.label)) else 0
                if e["steps"] is None and e["run"] >= RELEARN_RUN:
                    e["steps"] = n - e["n"]
            if n - e["n"] == RELEARN_KEEP:
                e["kept"] = any(h.ruleset.key() == e["key"] for h in s.hyps)
                e["map"] = s.map_hypothesis().ruleset.key() == e["key"]
        bm = agent.budget
        life = bm is not None and bm.survived_ends > self.ends
        if bm is not None:
            self.ends = bm.survived_ends
        why = "clear" if obs.level_completed else "reset" if a.name == "RESET" else "life" if life else None
        if why is not None or obs.done:
            for e in self.open:
                self.done.append([e["why"], e["n"], e["steps"], e["kept"], e["map"], e["empty"]])
            self.open = []
        if why is not None and not obs.done:
            self.open.append({"why": why, "n": n, "run": 0, "steps": None, "kept": None, "map": None, "key": pre_key,
                              "empty": len(pre_key) == 0})

    def result(self) -> list:
        return self.done + [[e["why"], e["n"], e["steps"], e["kept"], e["map"], e["empty"]] for e in self.open]
ALL_ARMS = ARMS + tuple(HDC_ARMS) + tuple(TL_ARMS)


class PlayTimeout(Exception):
    pass


def _alarm(signum, frame):
    raise PlayTimeout()


def _hook(spec: str, game: str):
    """An outside per-step labeller "module:function" -> function(game) returning an object with before(env, agent),
    after(env, agent, action, obs, rep) and result() -> dict, or None for games it does not label. Scoring only: the
    agent never sees it."""
    import importlib
    mod, fn = spec.split(":")
    return getattr(importlib.import_module(mod), fn)(game)


def play(job) -> dict:
    game, build, arm, seed, budget = job[:5]
    hook_spec = job[5] if len(job) > 5 else None
    max_seconds = job[6] if len(job) > 6 else 0
    if max_seconds:
        import signal
        signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(int(max_seconds))
    try:
        return _play(game, build, arm, seed, budget, hook_spec)
    except PlayTimeout:
        return {"game": game, "arm": arm, "seed": seed, "levels": None, "clear_at": [], "actions": None,
                "state": "TIMEOUT", "seconds": max_seconds}
    finally:
        if max_seconds:
            import signal
            signal.alarm(0)


def _play(game, build, arm, seed, budget, hook_spec=None) -> dict:
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
    hook = _hook(hook_spec, game) if hook_spec else None
    dp = {"presses": {}, "modes": {}, "ctl_changes": 0, "face_map_steps": 0, "face_map_first": None}
    last_ctl = None
    relearn = Relearn() if agent else None
    for n in range(1, budget + 1):
        if agent:
            a = agent.act()
            m = agent.last_decision.mode.split("+")[0] if agent.last_decision is not None else "?"
            dp["modes"][m] = dp["modes"].get(m, 0) + 1
        else:                                            # random baseline: a click needs a random board cell
            name = rng.choice(valid(obs))
            a = Action(name, rng.randrange(64), rng.randrange(64)) if name == "ACTION6" else Action(name)
        dp["presses"][a.name] = dp["presses"].get(a.name, 0) + 1
        if hook is not None:
            hook.before(env, agent, a)
        obs = env.step(a)
        if agent:
            pre_key = agent.slow.beliefs.map_hypothesis().ruleset.key()
            hdc = agent.slow.ctx.hdc
            taped = hdc is not None and hdc.annot.get("tape") is not None
            rep = agent.observe(a, obs.grid, level_completed=obs.level_completed, game_over=obs.state == "GAME_OVER",
                                level=obs.levels_completed, valid_actions=valid(obs))
            relearn.step(n, agent, a, obs, rep, pre_key)
            ctl = agent.slow.ctx.state.agency.tracker.controlled()
            dp["ctl_changes"] += int(last_ctl is not None and ctl != last_ctl)
            last_ctl = ctl
            if agent.cfg.tl_facing and rep.transition.scored:
                from .tl.relations import E_MAX, N_ACT, N_COL, SELF_RELS_ALL
                face = SELF_RELS_ALL.index("facing")
                if any(k == "WP" and i // E_MAX // N_ACT // N_COL == face
                       for r in agent.slow.beliefs.map_hypothesis().ruleset.rules() if r.template == "tl"
                       for k, i, w in r.weights if w > 0):
                    dp["face_map_steps"] += 1
                    dp["face_map_first"] = dp["face_map_first"] or n
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
        if hook is not None:
            hook.after(env, agent, a, obs, rep if agent else None)
        if obs.level_completed:
            clears.append(n)
        if obs.done:
            break
    out = {"game": game, "arm": arm, "seed": seed, "levels": obs.levels_completed, "clear_at": clears,
           "actions": n, "state": obs.state, "seconds": round(time.time() - t0, 1)}
    out["presses"] = dp["presses"]
    if hook is not None:
        out["labels"] = hook.result()
    if agent:
        out["relearn"] = relearn.result()             # debate five: [why, action, actions to re-learn, kept, MAP, was empty]
        if agent.library is not None:
            out["library"] = agent.library.report()
        if agent.cfg.flat_prefs:
            out["prefs_cleared"] = agent.slow.prefs.cleared
        out["modes"] = dp["modes"]
        out["ctl_changes"] = dp["ctl_changes"]
        sm = agent.slow.ctx.selfm
        if sm is not None:
            out["self"] = {"tracked": sm.n_tracked, "lost": sm.n_lost, "acquired": sm.n_acquired,
                           "colours": sorted(int(c) for c in sm.colours()),
                           "moves": {b: list(d) for b, d in sm.dirs().items()}}
        if agent.cfg.tl_facing:
            out["face_map_steps"] = dp["face_map_steps"]
            out["face_map_first"] = dp["face_map_first"]
            out["face_clauses"] = sorted({c for r in agent.slow.beliefs.map_hypothesis().ruleset.rules()
                                          if r.template == "tl" for c in r.clauses() if "(facing)" in c})[:8]
        if agent.cfg.use_epistemic:
            out["epi_preempts"] = agent.epi_preempts
            out["lnov_observed"] = agent.slow.ctx.lnov.observed
        arc = agent.archive
        if arc is not None:
            out["archive"] = {"cells": arc.total_cells(), "cells_level0": (arc.cells_per_level[:1] or [len(arc.cells)])[0],
                              "returns": arc.returns, "arrived": arc.arrived, "missed": arc.missed,
                              "new_after_return": arc.new_after_return}
        if agent.cfg.goal_contrast:
            out["contrast_log"] = agent.slow.goals.contrast_log[:6]
        ex = agent.explorer
        if agent.cfg.explore_handoff and ex is not None:
            out["handoff"] = {"triggers": dict(ex.handoffs), "trip_steps": ex.trip_steps, "dwell_steps": ex.dwell_steps}
        if agent.cfg.handoff_efe and ex is not None:
            out["interrupt"] = {"checks": dict(ex.checks), "interrupts": dict(ex.interrupts), "resumed": ex.resumed,
                                "trip_steps": ex.trip_steps, "dwell_steps": ex.dwell_steps,
                                "sur_mean": round(ex.sur_mean, 3),
                                "sur_sd": round((ex.sur_m2 / (ex.sur_n - 1)) ** 0.5, 3) if ex.sur_n > 1 else None}
        if (agent.cfg.option_value or agent.cfg.try_once) and ex is not None:   # debate four pick 1
            out["check_log"] = agent.check_log
            out["try_once"] = {"new_classes": ex.new_classes, "classes": sorted(ex.contact_classes),
                               "presses": ex.interrupts.get("try_once", 0)}
        bb, cz = agent.babble, agent.caused
        if cz is not None:                              # debate four pick 2
            G = agent.slow.goals
            out["caused"] = {"idle_steps": cz.idle_steps, "active_steps": cz.active_steps,
                             "top_goals": [[g.describe(), round(p, 4), round(cz.share(g.key()), 3)] for g, p in G.top(8)]}
        if bb is not None:
            out["babble"] = {"episodes": bb.episodes, "reached": bb.reached, "stalled": bb.stalled,
                             "attempts": bb.attempts, "plans": bb.plans, "plan_steps": bb.plan_steps,
                             "pref_decisions": bb.pref_decisions, "done_at_clear": bb.done, "tried": bb.tried,
                             "weights": bb.weights_report(agent.slow.goals), "log": bb.log[:60]}
        cc = agent.slow.ctx.contact
        if cc is not None:
            out["contact"] = {"observed": cc.observed, "changes": cc.changes}
            if agent.cfg.contact_gated:                 # debate four pick 3
                out["contact"].update({"open_at": cc.open_at, "open_presses": cc.open_presses})
        bm = agent.budget
        if bm is not None:
            out["budget"] = {"found_at": bm.found_at, "urgent_steps": bm.urgent_steps, "risky_steps": bm.risky_steps,
                             "min_steps_left": None if bm.min_steps_left is None else round(bm.min_steps_left, 1),
                             "survived_ends": bm.survived_ends, "ends": {str(k): v for k, v in bm.ends.items()},
                             "gauges": [(g["colour"], list(g["region"]), g["sign"]) for g in bm.gauges][:4],
                             "resets_urgent": agent.budget_resets, "returns": agent.budget_returns,
                             "abandoned": agent.budget_abandoned}
            if bm.cfg.learn_end:
                fc = bm.forecast()
                out["budget"].update({"lives_found": bm.lives_found, "lives_now": bm.lives_now, "tests": bm.tests,
                                      "plan_fits": bm.plan_fits, "cheap_ends": bm.cheap_ends,
                                      "over_spare": {str(k): v for k, v in bm.over_spare.items()},
                                      "p_fatal": None if not bm.gauges else round(bm.p_fatal(bm.gauges[0]["colour"]), 4),
                                      "p_over_last": None if fc is None else round(fc.p_over, 4)})
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
    ap.add_argument("--first_seed", type=int, default=0)
    ap.add_argument("--hook", default="", help="outside labeller module:function (scoring only)")
    ap.add_argument("--max_seconds", type=int, default=0, help="per-play wall-clock limit (0 = none)")
    args = ap.parse_args()
    out_dir = OUT / args.tag if args.tag else OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    arms = tuple(args.arms)
    from .curiosity import load_encoder
    load_encoder()
    games = [tuple(g.split(":")) for g in args.games]
    seeds = range(args.first_seed, args.first_seed + args.seeds)
    extra = (args.hook or None, args.max_seconds) if (args.hook or args.max_seconds) else ()
    jobs = [(g, b, arm, s, args.budget) + extra for g, b in games for s in seeds for arm in arms]
    t0 = time.time()
    with get_context("spawn").Pool(args.workers, maxtasksperchild=4 if extra else None) as pool:
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
            rs = [r for r in rs if r.get("state") != "TIMEOUT"]
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
