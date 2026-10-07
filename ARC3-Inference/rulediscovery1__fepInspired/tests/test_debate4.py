# Author: Claude Opus 5.5 (Bubba)
# Date: 25-September-2026
# PURPOSE: Tests for the picks of the fourth Warehouse debate (docs 2026-09-25-warehouse-expert-debate-4.md, Round 8;
#   OpenMind #arc-3 25-Sep-2026 11:24 ET):
#     - pick 1, option-value interruption (AgentConfig.option_value, agent._option_value): with one step left the value of
#       continuing is the arriving move's own G; it rises toward a button press's cost as the trip gets longer, so a
#       modest non-moving button beats a long trip that the best one-step move would have beaten; the arriving move's
#       local novelty is taken at the target's colour; with no trip to continue the best move's one-step G stays; every
#       check is logged; explorer.peek() plans the trip next_action then starts, without consuming the resume target;
#     - pick 1, try-once per contact class (AgentConfig.try_once): the first contact with a new colour on a trip raises a
#       check and a pending try, once per colour per play (a new level does not reset it); the pending try presses the best
#       non-moving button even when continuing is better, then the comparison decides again;
#     - pick 2, caused change (babble.CausedChange): a clock is not caused, change seen while the agent does nothing is
#       mostly not caused, rare change on active steps is caused, a goal that never changed keeps share 1;
#     - pick 2, soft reach (goals.GoalBeliefs soft_reach): a goal satisfied for many steps loses once per stretch, never
#       below the floor; the old per-step false alarm is unchanged without the switch; caused contrast: a clock cannot
#       explain a clear;
#     - pick 2, goal babbling (babble.GoalBabbler): candidates are the tied, caused, unsatisfied goals; reached -> weight
#       halves (floored), no progress for `patience` steps -> x 0.8, progress -> up; a clear ends babbling; the sampled
#       goal lowers G of an action imagined to progress it, and only while babbling is on; live, the agent babbles and
#       plans on the turning-sprite world;
#     - pick 3, gated contact novelty (AgentConfig.contact_gated): the contact terms stay out of the policy until every
#       button has been pressed GATE_TRIES times, then apply to the button with no learned move only; debate three's
#       ungated contact_context stays open from the start;
#     - default: every debate-four switch off, nothing new is built.
# SRP/DRY check: Pass -- worlds and helpers from test_debate_picks.py (TurnEnv, WARMUP) and test_debate3.py (_warm,
#   _interrupt_agent, _Sur); the package's own agent, explorer, goals, babble and policy. New: the tests.
from __future__ import annotations

import math
from types import SimpleNamespace as NS

from rulediscovery1__fepInspired.agent import AgentConfig, RuleDiscoveryAgent
from rulediscovery1__fepInspired.babble import BabbleConfig, CausedChange, GoalBabbler
from rulediscovery1__fepInspired.explore import ExploreConfig, ObjectContactExplorer
from rulediscovery1__fepInspired.goals import GoalBeliefs
from rulediscovery1__fepInspired.perception import Action, Effect
from rulediscovery1__fepInspired.policy import ActionScore
from rulediscovery1__fepInspired.tests.test_debate3 import BUTTONS5, _Sur, _warm
from rulediscovery1__fepInspired.tests.test_debate_picks import BOX, TurnEnv

P1 = dict(seed=0, use_self=True, use_epistemic=True, handoff_efe=True, option_value=True, try_once=True)


def _p1_agent(**over):
    env = TurnEnv(y=20, x=20, box=(20, 40))
    ex = ObjectContactExplorer()
    ag = _warm(AgentConfig(**{**P1, **over}), env, ex, extra=())
    ex.tries["ACTION5"] = 5
    return ag, ex, env


def _stub_scores(ag, G: dict, lnov: dict = None):
    lnov = lnov or {}

    def score(rc, *a, **k):
        n = rc.action.name
        return ActionScore(rc.action, 0, 0, 0, 0, 0, G.get(n, 0.0), local_novelty=lnov.get(n, 0.0))
    ag.policy.score = score


# ---------------------------------------------------------------- pick 1: option value

def test_one_step_left_is_the_arriving_moves_own_G_and_longer_trips_are_worth_less_per_step():
    ag, ex, _ = _p1_agent()
    ag.slow.ctx.lnov = None                              # no target-colour novelty correction here
    c = ag.cfg.policy.cost_button
    sc = [ActionScore(Action(n), 0, 0, 0, 0, 0, g) for n, g in
          [("ACTION1", -0.9), ("ACTION4", -0.6), ("ACTION5", 0.2)]]
    ex.target = NS(colour=BOX)
    ex.plan = [("ACTION4", (0, 4))]
    g1, k1 = ag._option_value(sc, -0.9)
    assert (k1, g1) == (1, -0.6)                          # the trip's own arriving move, not the best move (-0.9)
    ex.plan = [("ACTION1", (-4, 0))] * 3 + [("ACTION4", (0, 4))]
    g4, k4 = ag._option_value(sc, -0.9)
    assert k4 == 4 and math.isclose(g4, c + (-0.6 - c) / 4) and g4 > g1


def test_the_target_colours_novelty_replaces_the_arriving_moves():
    ag, ex, _ = _p1_agent()
    ln = ag.slow.ctx.lnov
    ln.mem.pop("ACTION4", None)                          # the arriving move never met anything: target fully novel
    sc = [ActionScore(Action("ACTION4"), 0, 0, 0, 0, 0, -0.5, local_novelty=0.25)]
    ex.target, ex.plan = NS(colour=BOX), [("ACTION4", (0, 4))]
    g, k = ag._option_value(sc, -0.5)
    assert k == 1 and math.isclose(g, -0.5 - ag.cfg.policy.w_lnov * (1.0 - 0.25))


def test_a_long_trip_loses_to_a_modest_button_that_the_best_move_would_beat():
    for option_value, expect in ((True, "ACTION5"), (False, None)):
        ag, ex, _ = _p1_agent(option_value=option_value, try_once=False)
        ag.slow.ctx.lnov = None
        _stub_scores(ag, {"ACTION5": -0.3, "ACTION1": -0.5, "ACTION2": -0.5, "ACTION3": -0.5, "ACTION4": -0.5})
        ex.check, ex.target = "arrival", NS(colour=BOX)
        ex.plan = [("ACTION4", (0, 4))] * 5
        a = ag._interrupt(ag.perceiver.current)
        assert (a.name if a is not None else None) == expect
    ag, ex, _ = _p1_agent(try_once=False)
    ag.slow.ctx.lnov = None
    _stub_scores(ag, {"ACTION5": -0.3, "ACTION4": -0.5})
    ex.check, ex.target, ex.plan = "arrival", NS(colour=BOX), [("ACTION4", (0, 4))] * 5
    ag._interrupt(ag.perceiver.current)
    step, trig, won, act, k = ag.check_log[-1][:5]
    assert (step, trig, won, act, k) == (ag.n_steps, "arrival", "button", "ACTION5", 5)


def test_no_trip_to_continue_keeps_the_one_step_comparison():
    ag, ex, _ = _p1_agent()
    ex.plan = []
    ex.peek = lambda agent: None
    sc = [ActionScore(Action("ACTION4"), 0, 0, 0, 0, 0, -0.5)]
    assert ag._option_value(sc, -0.7) == (-0.7, 0)


def test_peek_is_the_trip_next_action_starts_and_keeps_the_resume_target():
    env = TurnEnv(y=20, x=20, box=(20, 40))
    ex = ObjectContactExplorer()
    ag = _warm(AgentConfig(**P1), env, ex, extra=())
    ex.tries["ACTION5"] = 5
    ex.plan, ex.resume_target = [], ("nothing", 0, 0)
    found = ex.peek(ag)
    assert found is not None and ex.resume_target == ("nothing", 0, 0) and ex.plan == []
    path, target = list(found[0]), found[1]
    a = ex.next_action(ag)
    assert a.name == path[0][0] and ex.plan == path[1:] and ex.target is target
    assert ex.resume_target is None                      # consumed when the trip really started


# ---------------------------------------------------------------- pick 1: try once per contact class

def _key(colour, y, x):
    return ((colour, 1), y, x)


def test_first_contact_with_a_new_colour_raises_one_try_per_play():
    ex = ObjectContactExplorer(ExploreConfig(handoff=True, interrupt=True, try_once=True))
    ex._scored = True
    me = (20, 30, 23, 33)
    ex.prev_adj, ex.plan = set(), [("ACTION4", (0, 4))] * 3
    ex._check(_Sur(0.1), True, None, me, {_key(9, 20, 34): (20, 34, 23, 37)})
    assert ex.try_pending and ex.check == "arrival" and ex.contact_classes == {9} and ex.new_classes == 1
    ex.check = None
    ex._check(_Sur(0.1), True, None, (40, 30, 43, 33), {_key(9, 40, 34): (40, 34, 43, 37)})
    assert not ex.try_pending                            # another object of a colour already met: no try
    ex.reset_level()
    ex.prev_adj, ex.plan = set(), [("ACTION4", (0, 4))] * 3
    ex._check(_Sur(0.1), True, None, me, {_key(9, 20, 34): (20, 34, 23, 37)})
    assert not ex.try_pending                            # a new level does not make the colour new again
    ex._check(_Sur(0.1), True, None, me, {_key(4, 24, 30): (24, 30, 27, 33)})
    assert ex.try_pending and ex.contact_classes == {9, 4}


def test_a_try_once_on_a_step_that_raised_no_check_is_its_own_trigger():
    ex = ObjectContactExplorer(ExploreConfig(handoff=True, interrupt=True, try_once=True))
    ex._scored = True
    me = (20, 30, 23, 33)
    ex.prev_adj = {_key(4, 20, 34)}                      # already touching it: no arrival
    ex.plan = [("ACTION4", (0, 4))]
    ex._check(_Sur(0.1), True, None, me, {_key(4, 20, 34): (20, 34, 23, 37)})
    assert ex.try_pending and ex.check == "new_class"


def test_try_once_presses_the_button_even_when_continuing_wins_then_the_comparison_decides():
    ag, ex, _ = _p1_agent()
    ag.slow.ctx.lnov = None
    _stub_scores(ag, {"ACTION5": 2.0, "ACTION4": -0.5, "ACTION1": -0.5})
    ex.check, ex.target, ex.plan = "arrival", NS(colour=BOX), [("ACTION4", (0, 4))]
    ex.try_pending = True
    a = ag._interrupt(ag.perceiver.current)
    assert a.name == "ACTION5" and ag.last_decision.mode == "tryonce" and not ex.try_pending
    assert ex.interrupts.get("try_once") == 1 and ag.check_log[-1][2] == "try_once"
    assert ag._interrupt(ag.perceiver.current) is None and ag.check_log[-1][2] == "trip"


def test_try_once_needs_a_button_tried_enough_and_still_moveless():
    ag, ex, _ = _p1_agent()
    ag.slow.ctx.lnov = None
    ex.tries["ACTION5"] = 1                              # still being learned: not a non-moving button yet
    _stub_scores(ag, {"ACTION5": 2.0, "ACTION4": -0.5})
    ex.check, ex.target, ex.plan, ex.try_pending = "arrival", NS(colour=BOX), [("ACTION4", (0, 4))], True
    assert ag._interrupt(ag.perceiver.current) is None and not ex.try_pending


# ---------------------------------------------------------------- pick 2: caused change, soft reach, contrast

def _feed(cz, seq):
    """seq: (progress, idle) per step; progress of one goal 'g'."""
    for p, idle in seq:
        cz.observe({"g": p}, idle)


def test_caused_share():
    clock = CausedChange()
    _feed(clock, [(i / 100, i % 3 == 0) for i in range(60)])
    assert clock.share("g") == 0.0                       # changes on every step whatever the action
    idle = CausedChange()
    _feed(idle, [(0.0, False)] * 30 + [(0.1, True), (0.2, False), (0.2, True), (0.3, True)] + [(0.3, False)] * 20
          + [(0.4, True), (0.4, False)] * 3 + [(0.4, True)] * 10)
    rare = CausedChange()
    _feed(rare, [(0.0, False)] * 40 + [(0.5, False)] + [(0.5, True)] * 20 + [(1.0, False)] + [(1.0, False)] * 30)
    assert idle.share("g") < 0.25 < rare.share("g") == 1.0
    never = CausedChange()
    _feed(never, [(0.2, False), (0.2, True)] * 20)
    assert never.share("g") == 1.0
    reset = CausedChange()
    _feed(reset, [(0.0, False)])
    reset.observe(None, None)                            # a RESET / clear: no change is counted across it
    _feed(reset, [(0.9, False)])
    assert "g" not in reset.stats or reset.stats["g"][1] == 0


class _G:
    """A goal whose progress is read off the board (board.p[key])."""
    template = "fill"

    def __init__(self, name, dl=1.0):
        self.name, self.dl, self.a = name, dl, 0

    def progress(self, scene, base):
        return scene.p.get(self.name, 0.0)

    def description_length(self):
        return self.dl

    def key(self):
        return ("fake", self.name)

    def describe(self):
        return self.name


def _beliefs(names, **kw):
    gb = GoalBeliefs(**kw)
    for n in names:
        g = _G(n)
        gb.goals[g.key()], gb.loglik[g.key()] = g, 0.0
    return gb


def _step(gb, p, clear=False):
    board = NS(p=p, level=0)
    gb.observe(NS(reset=False, level_completed=clear, scored=not clear, post=None if clear else board, pre=board))


def test_soft_reach_loses_once_per_stretch_and_never_below_the_floor():
    old = _beliefs(["a"])
    for _ in range(3):
        _step(old, {"a": 1.0})
    assert math.isclose(old.loglik[("fake", "a")], 3 * math.log(0.1))     # the old per-step false alarm
    soft = _beliefs(["a"], soft_reach=True)
    for _ in range(5):
        _step(soft, {"a": 1.0})
    assert math.isclose(soft.loglik[("fake", "a")], math.log(0.5))
    for _ in range(10):                                  # leave and re-enter many times
        _step(soft, {"a": 0.5})
        _step(soft, {"a": 1.0})
    assert math.isclose(soft.loglik[("fake", "a")], math.log(0.05))
    assert soft.last_prog == {("fake", "a"): 1.0}


def test_a_clock_cannot_explain_a_clear():
    gb = _beliefs(["clock", "goal"], contrast=True, track_prog=True)
    gb.caused = CausedChange()
    gb.caused.stats = {("fake", "clock"): [50, 50, 10, 10], ("fake", "goal"): [50, 2, 10, 0]}
    for _ in range(4):
        _step(gb, {"clock": 0.5, "goal": 0.2})
    _step(gb, {"clock": 1.0, "goal": 1.0}, clear=True)
    top = gb.top_goal()[0]
    assert top.name == "goal" and gb.loglik[("fake", "clock")] < gb.loglik[("fake", "goal")] - 2.0


# ---------------------------------------------------------------- pick 2: goal babbling

def test_babbling_candidates_and_soft_updates():
    gb = _beliefs(["a", "b", "clock", "done", "weak"], soft_reach=True)
    gb.loglik[("fake", "weak")] = -5.0                   # far behind the tie
    bb = GoalBabbler(BabbleConfig(patience=3), seed=1)
    bb.caused.stats = {("fake", "clock"): [30, 30, 5, 5]}
    now = NS(p={"done": 1.0}, colour_objects=lambda c: [])
    assert sorted(k[1] for k in bb.candidates(gb, now)) == ["a", "b"]
    g = bb.sample(gb, now, 0)
    k = bb.key
    assert g.name in ("a", "b") and bb.episodes == 1
    tr = NS(reset=False, level_completed=False, scored=True, post=NS(p={}))
    gb.last_prog = {k: 0.4}
    bb.step(gb, tr, 1)
    assert bb.weight(k) == 1.25                           # progress: learning progress raises it
    gb.last_prog = {k: 1.0}
    bb.step(gb, tr, 2)
    assert bb.key is None and bb.reached == 1 and math.isclose(bb.weight(k), 0.625)
    for t in range(10):                                   # reached again and again: weakened, never killed
        bb.key, bb.best = k, 0.0
        bb.step(gb, tr, t)
    assert bb.weight(k) == bb.cfg.w_min
    bb.key, bb.best, bb.since = k, 0.9, 0
    gb.last_prog = {k: 0.5}
    for t in range(3):
        bb.step(gb, tr, t)
    assert bb.key is None and bb.stalled == 1
    assert bb.active(gb, urgent=False) and not bb.active(gb, urgent=True)
    gb.n_clears = 1
    assert not bb.active(gb, urgent=False) and bb.done


def test_the_babbled_goal_is_a_preference_only_while_babbling():
    env = TurnEnv(y=20, x=20, box=(20, 40))
    ag = _warm(AgentConfig(seed=0, use_self=True, use_epistemic=True, goal_babble=True), env, extra=())
    bb = ag.babble
    assert ag.cfg.policy.w_babble > 0 and ag.slow.ctx.babble is bb
    bb.key = next(iter(ag.slow.goals.goals))
    bb.gain = lambda goals, now, nxt: 0.5
    s, scene = ag.slow, ag.perceiver.current
    comp = scene.objects()[0]                            # every rule set imagines this piece moving one row down
    pred = NS(effects=[Effect("move", comp.id, dx=0, dy=1)], label="mv+0+1")
    s.beliefs.predictions = lambda rc: [(None, 1.0, pred, {"mv+0+1": 1.0})]
    ag.policy.draw(s.beliefs)

    def G(on):
        bb.on = on
        return ag.policy.score(s.ctx.context(scene, Action("ACTION2")), s.beliefs, s.goals, s.prefs, s.ctx).G
    assert math.isclose(G(False) - G(True), ag.cfg.policy.w_prag * ag.cfg.policy.w_babble * 0.5)
    bb.key = None                                        # no goal sampled: nothing added
    assert G(True) == G(False)


def test_live_agent_babbles_and_plans_before_a_clear():
    env = TurnEnv(y=20, x=20, box=(20, 40))
    ex = ObjectContactExplorer()
    ag = _warm(AgentConfig(seed=0, use_self=True, use_epistemic=True, handoff_efe=True, goal_babble=True,
                           goal_contrast=True, caused_contrast=True), env, ex, extra=())
    for _ in range(60):
        a = ag.act()
        grid, _, _ = env.step(a)
        ag.observe(a, grid)
    bb = ag.babble
    assert bb.episodes >= 1 and bb.attempts >= 1 and ag.slow.goals.caused is bb.caused
    assert all(bb.cfg.w_min <= w <= bb.cfg.w_max for w in bb.w.values())
    assert bb.caused.active_steps > 0


# ---------------------------------------------------------------- pick 3: gated contact novelty

def test_contact_novelty_waits_until_every_button_was_pressed_enough():
    from rulediscovery1__fepInspired.agent import GATE_TRIES
    env = TurnEnv(y=20, x=20, box=(20, 40))
    ex = ObjectContactExplorer()
    ag = _warm(AgentConfig(seed=0, use_self=True, use_epistemic=True, contact_gated=True), env, ex, extra=())
    cc, s, scene = ag.slow.ctx.contact, ag.slow, ag.perceiver.current
    assert ag.cfg.policy.w_ceig > 0 and not cc.open and ag.presses.get("ACTION5", 0) < GATE_TRIES
    ag.policy.draw(s.beliefs)

    def terms(name):
        rc = s.ctx.context(scene, Action(name))
        return ag.policy.epistemic(rc, [d for _, _, _, d in s.beliefs.predictions(rc)], s.ctx)
    closed = terms("ACTION5")
    ag.act()
    assert not cc.open                                   # ACTION5 still under GATE_TRIES presses
    for b in BUTTONS5:
        ag.presses[b] = GATE_TRIES
    ag.act()
    assert cc.open and cc.open_at == ag.n_steps
    opened = terms("ACTION5")
    assert opened[0] > closed[0]                         # the contact information gain now joins the disagreement
    assert terms("ACTION2") == terms("ACTION2")          # a moving button: never the contact path
    rc = s.ctx.context(scene, Action("ACTION2"))
    assert not cc.applies(rc, s.ctx.controlled_direction)


def test_ungated_contact_context_is_open_from_the_start():
    env = TurnEnv(y=20, x=20, box=(20, 40))
    ag = _warm(AgentConfig(seed=0, use_self=True, use_epistemic=True, contact_context=True), env, extra=())
    assert ag.slow.ctx.contact.open


def test_debate4_switches_default_off():
    cfg = AgentConfig()
    assert not (cfg.option_value or cfg.try_once or cfg.goal_babble or cfg.caused_contrast or cfg.contact_gated)
    ex = ObjectContactExplorer()
    ag = RuleDiscoveryAgent(AgentConfig(handoff_efe=True), explorer=ex)
    ag.start_play(TurnEnv().board(), BUTTONS5)
    assert ag.babble is None and ag.caused is None and ag.slow.ctx.babble is None
    assert ag.cfg.policy.w_babble == 0 and not ex.cfg.try_once and ag.check_log == []
    assert not ag.slow.goals.soft_reach and not ag.slow.goals.track_prog and ag.slow.goals.caused is None
