# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Tests for the HDC integration A/B (hdc_bridge.py and its hooks in rules.py / agent.py):
#   - with use_hdc off, contexts carry no HDC values (the old code path);
#   - TapeRule predicts the ghost's move from the frozen context and, on the player-move clock, only when the
#     rule set's primary predicts a move of its own (RuleSet.predict gating);
#   - the soft wall map: a stored blocked strip reads back as blocked, a snapshot taken before a store does not
#     change, the per-cell score map averages to the strip score (the query is linear);
#   - replay exactness with use_hdc on: every surviving hypothesis's online log likelihood equals a fresh replay
#     over the stored records (the HDC values are frozen into each context, so replay sees what the step saw).
# SRP/DRY check: Pass -- fixtures from synth.py; checks only the new pieces.
from __future__ import annotations

import math

import numpy as np

from rulediscovery1__fepInspired.agent import AgentConfig, RuleDiscoveryAgent
from rulediscovery1__fepInspired.beliefs import PredictionCache, score_ruleset
from rulediscovery1__fepInspired.hdc.vsa import VSA
from rulediscovery1__fepInspired.hdc_bridge import WallMap
from rulediscovery1__fepInspired.perception import Action, Effect
from rulediscovery1__fepInspired.rules import NoOpRule, RuleSet, TapeRule
from rulediscovery1__fepInspired.tests.synth import MoverEnv

VALID = ["ACTION1", "ACTION2", "ACTION3", "ACTION4"]


def _play(use_hdc: bool, steps: int = 30):
    env = MoverEnv(x=18, wall_x=26, timer_every=2)
    agent = RuleDiscoveryAgent(AgentConfig(propose_every=4, seed=1, use_hdc=use_hdc))
    agent.start_play(env.board(), VALID)
    for _ in range(steps):
        a = agent.act()
        grid, lc, go = env.step(a)
        agent.observe(a, grid, lc, go)
    return agent


def test_hdc_off_leaves_contexts_bare():
    agent = _play(False, 8)
    rc = agent.slow.ctx.context(agent.perceiver.current, Action("ACTION1"))
    assert rc.tape is None and rc.walls is None and rc.fate is None
    assert agent.slow.ctx.hdc is None


def test_tape_rule_and_clock_gating():
    agent = _play(True, 6)
    rc = agent.slow.ctx.context(agent.perceiver.current, Action("ACTION1"))
    rs = RuleSet.of([NoOpRule(("ACTION1",)), TapeRule()])
    assert rs.predict(rc.replace(tape=None)).label == "nothing"
    moves = rc.replace(tape=(1, 0, 6, "moves"))
    acts = rc.replace(tape=(1, 0, 6, "actions"))
    assert TapeRule().predict(acts) == [Effect("move", 1, 6, 0)]
    assert rs.predict(moves).label == "nothing"          # the primary predicts no player move: the copy waits
    assert rs.predict(acts).label != "nothing"           # the action clock ticks anyway


def test_wall_map_snapshot_and_linearity():
    wm = WallMap(VSA(1024, seed=0))
    ys, xs, cols = np.array([10, 11]), np.array([20, 20]), [5, 5]
    wm.store(ys, xs, cols, blocked=False)
    before = wm.view(0.05)
    s0 = before.score(ys, xs, cols)
    for _ in range(3):
        wm.store(ys, xs, cols, blocked=True)
    after = wm.view(0.05)
    assert before.score(ys, xs, cols) == s0 and s0 < 0
    assert after.verdict(ys, xs, cols) is True
    arr = np.zeros((64, 64), dtype=int)
    arr[10:12, 20] = 5
    smap = after.score_map(arr)
    assert math.isclose(smap[ys, xs].mean(), after.score(ys, xs, cols), rel_tol=1e-6, abs_tol=1e-9)


def test_replay_is_exact_with_hdc():
    agent = _play(True, 30)
    b = agent.slow.beliefs
    for h in b.hyps:
        ll, fires, misses = score_ruleset(h.ruleset, b.records, PredictionCache())
        assert math.isclose(ll, h.loglik, rel_tol=1e-9, abs_tol=1e-9), (h.ruleset.describe(), ll, h.loglik)
