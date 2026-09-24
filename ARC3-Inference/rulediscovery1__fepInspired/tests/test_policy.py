# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Tests (written, NOT run) for rulediscovery1__fepInspired/policy.py: salience (expected information gain
#   about which rule set is true) ranks the action the hypotheses disagree on above one they agree on;
#   count novelty prefers an untried context (inhibition of return); choose() returns a valid action;
#   precision rises as the posterior concentrates; the planner finds a short path to a reach goal in
#   the believed model.
# SRP/DRY check: Pass -- fixtures from synth.py.
from __future__ import annotations

from rulediscovery1__fepInspired.beliefs import BeliefState
from rulediscovery1__fepInspired.goals import GoalBeliefs, Preferences, ReachGoal
from rulediscovery1__fepInspired.perception import Action, Scene
from rulediscovery1__fepInspired.policy import BeamPlanner, EFEPolicy, HabitPrior, precision
from rulediscovery1__fepInspired.rules import ContextBuilder, MoveRule, NoOpRule, RuleSet
from rulediscovery1__fepInspired.tests.synth import MOVER, RIGHT, UP, WALL, MoverEnv, feed, mover_comp

VALID = ["ACTION1", "ACTION2", "ACTION3", "ACTION4"]


def _two_hypotheses(scene):
    t = mover_comp(scene).type_key
    quiet_up = NoOpRule(("ACTION1",))
    h1 = RuleSet.of([MoveRule("ACTION4", t, 1, 0), quiet_up])       # right moves the piece
    h2 = RuleSet.of([NoOpRule(("ACTION4",)), quiet_up])              # right does nothing
    b = BeliefState()
    b.add_rulesets([h1, h2])
    return b


def test_salience_ranks_disagreement_first():
    scene = Scene.from_grid(MoverEnv().board(), None)
    b = _two_hypotheses(scene)
    ctx, pol = ContextBuilder(), EFEPolicy()
    goals, prefs = GoalBeliefs(), Preferences()
    goals.bind_level(scene)
    s_right = pol.score(ctx.context(scene, RIGHT), b, goals, prefs, ctx)
    s_up = pol.score(ctx.context(scene, UP), b, goals, prefs, ctx)
    assert s_right.salience > s_up.salience + 1e-6


def test_novelty_prefers_untried_context():
    env = MoverEnv()
    b, ctx, p, _ = feed(env, [RIGHT] * 5)
    nov_right = b.novelty.novelty(ctx.context(p.current, RIGHT).hc_ctx)
    nov_up = b.novelty.novelty(ctx.context(p.current, UP).hc_ctx)
    assert nov_up > nov_right


def test_choose_returns_a_valid_action():
    env = MoverEnv()
    b, ctx, p, _ = feed(env, [RIGHT] * 3)
    goals = GoalBeliefs()
    goals.bind_level(p.current)
    d = EFEPolicy().choose(p.current, VALID, b, goals, Preferences(), ctx, HabitPrior())
    assert d.action.name in VALID and d.scores and d.gamma > 0


def test_precision_rises_as_posterior_concentrates():
    assert precision(4.0, 0.0, 8) > precision(4.0, 1.5, 8) > 0


def test_planner_reaches_the_wall_in_the_believed_model():
    env = MoverEnv(x=18, wall_x=26)
    scene = Scene.from_grid(env.board(), None)
    t = mover_comp(scene).type_key
    rs = RuleSet.of([MoveRule("ACTION4", t, 1, 0, frozenset({WALL})), MoveRule("ACTION3", t, -1, 0),
                     NoOpRule(("ACTION1",)), NoOpRule(("ACTION2",))])
    goals = GoalBeliefs()
    goals.bind_level(scene)
    goals.goals = {ReachGoal(MOVER, WALL).key(): ReachGoal(MOVER, WALL)}   # pin the goal for the test
    goals.loglik = {k: 0.0 for k in goals.goals}
    ctx = ContextBuilder()
    plan = BeamPlanner().plan(scene, VALID, rs, goals, ctx, ctx.context(scene, Action("RESET")))
    assert plan is not None and plan.progress >= goals.satisfied
    assert [a.name for a in plan.actions] == ["ACTION4"] * 6          # piece on 18-19, wall at 26
