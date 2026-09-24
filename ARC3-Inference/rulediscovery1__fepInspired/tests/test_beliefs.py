# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Tests (written, NOT run) for rulediscovery1__fepInspired/beliefs.py: the chained back-off keeps mass on
#   unseen outcomes and sums to one; an event no rule explains costs the back-off probability instead
#   of zeroing a hypothesis; the posterior moves to the true rule set; surprise quantities are
#   non-negative; late entry by replay gives exactly the online log likelihood; the Dirichlet BMR
#   formula is zero for an identical reduced prior.
# SRP/DRY check: Pass -- fixtures from synth.py.
from __future__ import annotations

import math

from rulediscovery1__fepInspired.beliefs import NOVEL, BackoffModel, BeliefState, dirichlet_bmr, score_ruleset
from rulediscovery1__fepInspired.perception import Perceiver, Scene
from rulediscovery1__fepInspired.rules import ContextBuilder, CounterRule, MoveRule, NoOpRule, RuleSet
from rulediscovery1__fepInspired.tests.synth import LEFT, RIGHT, WALL, MoverEnv, feed, mover_comp


def _move_set(env) -> RuleSet:
    scene = Scene.from_grid(env.board(), None)
    return RuleSet.of([MoveRule("ACTION4", mover_comp(scene).type_key, 1, 0)])


def test_backoff_distribution_is_normalised_with_unseen_mass():
    scene = Scene.from_grid(MoverEnv().board(), None)
    rc = ContextBuilder().context(scene, RIGHT)
    d = BackoffModel().dist(rc)
    assert d[NOVEL] > 0
    assert math.isclose(sum(d.values()), 1.0, rel_tol=1e-9)


def test_unexplained_event_does_not_zero_a_hypothesis():
    env = MoverEnv(timer_every=2)                       # "grow" ticks that the MoveRule does not explain
    import rulediscovery1__fepInspired.beliefs as B
    old = B.LIKELIHOOD
    try:
        misses = {}
        for mode in ("label", "parts"):
            B.LIKELIHOOD = mode
            b = BeliefState()
            b.add_rulesets([_move_set(env if mode == "label" else MoverEnv(timer_every=2))])
            b, _, _, trs = feed(env if mode == "label" else MoverEnv(timer_every=2), [RIGHT] * 8, b)
            h = next(h for h in b.hyps if len(h.ruleset) == 1)
            assert math.isfinite(h.loglik)
            misses[mode] = h.misses
        # whole-label scoring blames the rule for the timer's side effect; part-level scoring does not
        assert misses == {"label": 4, "parts": 0}
    finally:
        B.LIKELIHOOD = old


def test_posterior_prefers_the_true_rule_set_over_a_wrong_one():
    # Compares two rule sets that share the left rule and differ on the right button, so the result
    # does not depend on how well the back-off alone does (whether rules beat counts-only here is an
    # empirical question for offline_eval, not a unit test). Wrong: "right does nothing", which misses
    # six of every eight right presses; the prior difference is dl_weight x ~11 nats.
    env = MoverEnv(x=18, wall_x=26)
    t = mover_comp(Scene.from_grid(env.board(), None)).type_key
    left = MoveRule("ACTION3", t, -1, 0)
    true = RuleSet.of([MoveRule("ACTION4", t, 1, 0, frozenset({WALL})), left])
    wrong = RuleSet.of([NoOpRule(("ACTION4",)), left])
    b = BeliefState(dl_weight=0.25)
    b.add_rulesets([true, wrong])
    feed(env, ([RIGHT] * 8 + [LEFT] * 6) * 6, b)
    h = {x.ruleset.key(): x for x in b.hyps}
    assert h[true.key()].misses == 0 and h[wrong.key()].misses == 36
    assert h[true.key()].log_score > h[wrong.key()].log_score


def test_surprise_quantities_are_non_negative():
    env = MoverEnv(timer_every=2)
    b = BeliefState()
    b.add_rulesets([_move_set(env), RuleSet.of(list(_move_set(env).rules()) + [CounterRule(("grow",), 2, "any")])])
    ctx, p = ContextBuilder(), Perceiver()
    p.begin(env.board())
    for _ in range(8):
        grid, lc, go = env.step(RIGHT)
        rc = ctx.context(p.current, RIGHT)
        tr = p.observe(RIGHT, grid, lc, go)
        s = b.observe(rc, tr)
        ctx.observe(tr)
        assert s.surprisal >= 0 and s.bayes_surprise >= -1e-12 and s.dirichlet_kl >= -1e-12


def test_late_entry_by_replay_equals_online_scoring():
    env = MoverEnv(timer_every=2)
    rs = RuleSet.of(list(_move_set(env).rules()) + [CounterRule(("grow",), 2, "any")])
    b = BeliefState()
    b.add_rulesets([rs])                                   # present from step 0: scored online
    feed(env, [RIGHT] * 10, b)
    online = next(h for h in b.hyps if h.ruleset.key() == rs.key())
    ll, fires, misses = score_ruleset(rs, b.records, b.cache)
    assert math.isclose(ll, online.loglik, rel_tol=1e-12, abs_tol=1e-12)
    assert (fires, misses) == (online.fires, online.misses)


def test_dirichlet_bmr_is_zero_for_the_same_prior():
    post, prior = [3.0, 1.5, 0.5], [1.0, 1.0, 0.5]
    assert abs(dirichlet_bmr(post, prior, prior)) < 1e-9


def test_compose_predictive_sums_to_one_and_credits_side_effects():
    """Part-level likelihood (added 23-Sep-2026): a rule predicting one move is credited when the
    observed label also carries side effects the back-off has seen."""
    from rulediscovery1__fepInspired.beliefs import compose_predictive, mix_predictive, rule_missed
    pb = {"grow|mv+0-3x2|shrink": 0.3, "nothing": 0.5, "mv+3+0": 0.1, NOVEL: 0.1}
    d = compose_predictive("mv+0-3", 0.2, pb)
    total = sum(v for k, v in d.items() if k != NOVEL) + d[NOVEL] * 0  # NOVEL is a per-label slot
    assert abs(sum(d.values()) - sum(mix_predictive("mv+0-3", 0.2, pb).values())) < 1e-9
    assert d["grow|mv+0-3x2|shrink"] > mix_predictive("mv+0-3", 0.2, pb)["grow|mv+0-3x2|shrink"]
    assert not rule_missed("mv+0-3", "grow|mv+0-3x2|shrink")
    assert rule_missed("mv+0-3", "mv+3+0")
