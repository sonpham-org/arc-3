# Author: Claude Opus 5.5 (Bubba)
# Date: 25-September-2026
# PURPOSE: Tests for the three picks of the third Warehouse debate (docs 2026-09-25-warehouse-expert-debate-3.md, Round 8;
#   OpenMind #arc-3 25-Sep-2026 05:47 ET):
#     - pick 1, interrupting options (explore.ExploreConfig.interrupt, agent._interrupt): arrival raises a check but does
#       not cut the trip; surprise is relative to the play's own running surprisal (a play that is always ~2.5 nats does
#       not fire, an outlier does); where every button moves the self nothing interrupts (the check is cleared, the trip
#       goes on); a non-moving button whose G beats every move interrupts, at most `dwell` times per check; an interrupting
#       action that moved the self makes the next trip go to the SAME target; live on the turning-sprite world the agent
#       interrupts next to the box and presses the non-moving button there;
#     - pick 2, contact neighbourhood (epistemic.ContactContext): the Beta information gain; facing the box, the box
#       beside and the open field are different codes; novelty of a non-moving button falls where it was pressed and
#       stays high at a new contact; a press that changed something makes "changes something" more likely at the same
#       contact than in the open; ambient parts (a ticking bar) are not a change; the policy scores the non-moving button
#       from the contact code;
#     - pick 3, budget (budget.LivesReader, BudgetConfig.learn_end): a counter of identical items beside the bar is found
#       and read, nothing is found without one; spare lives lower P(game over | run out) and bring an information value
#       for non-RESET actions only; a survived run-out drops P(fatal) sharply; urgency is off while the plan fits or
#       running out is cheap; live, with lives the agent lets the bar run out and never ends the game, without lives it
#       still resets before the end;
#     - default: the three switches off, none of the new state is built, the stage-one budget numbers are unchanged.
# SRP/DRY check: Pass -- worlds and helpers from synth.py, test_debate_picks.py (TurnEnv, WARMUP) and test_stage1.py (BarEnv,
#   _bar_board, _tr); the package's own agent, explorer, epistemic, policy and budget. New: the tests.
from __future__ import annotations

from types import SimpleNamespace as NS

import numpy as np

from rulediscovery1__fepInspired.agent import AgentConfig, RuleDiscoveryAgent
from rulediscovery1__fepInspired.budget import BudgetConfig, BudgetModel, LivesReader
from rulediscovery1__fepInspired.epistemic import ContactContext, beta_eig
from rulediscovery1__fepInspired.explore import ExploreConfig, ObjectContactExplorer
from rulediscovery1__fepInspired.perception import Action
from rulediscovery1__fepInspired.tests.synth import put
from rulediscovery1__fepInspired.tests.test_debate_picks import WARMUP, TurnEnv
from rulediscovery1__fepInspired.tests.test_stage1 import BAR, BarEnv, _bar_board, _tr

BUTTONS5 = ["ACTION1", "ACTION2", "ACTION3", "ACTION4", "ACTION5"]
U, D, L, R, X = (Action(n) for n in BUTTONS5)


def _warm(cfg: AgentConfig, env: TurnEnv, explorer=None, extra=("RESET",)):
    ag = RuleDiscoveryAgent(cfg, explorer=explorer)
    ag.start_play(env.board(), BUTTONS5 + list(extra))
    for a in WARMUP:
        grid, _, _ = env.step(a)
        ag.observe(a, grid)
    return ag


def _walk(ag, env, actions):
    for a in actions:
        grid, _, _ = env.step(a)
        ag.observe(a, grid)


# ---------------------------------------------------------------- pick 1: interrupting options

class _Sur:
    def __init__(self, x, spike=False):
        self.last_surprise = NS(surprisal=x, spike=spike)


def test_arrival_raises_a_check_but_keeps_the_trip():
    ex = ObjectContactExplorer(ExploreConfig(handoff=True, interrupt=True))
    near = (20, 30, 23, 33)
    obj = {("o", 20, 34): (20, 34, 23, 37)}
    ex.prev_adj, ex.plan, ex._scored = set(), [("ACTION4", (0, 4))], True
    ex._check(_Sur(0.1), True, None, near, obj)
    assert ex.plan == [("ACTION4", (0, 4))] and ex.check == "arrival" and ex.checks == {"arrival": 1}
    ex.check = None
    ex._check(_Sur(0.1), True, None, near, obj)          # same object from the same place: no second check
    assert ex.check is None


def test_surprise_is_relative_to_the_plays_own_level():
    ex = ObjectContactExplorer(ExploreConfig(handoff=True, interrupt=True, min_sur_n=20, z_surprise=2.0))
    ex._scored = True
    rng = np.random.default_rng(0)
    fired = 0
    for _ in range(60):                                  # a noisy game: ~2.5 nats every step, the old fixed threshold
        ex.plan, ex.check = [("ACTION1", (-4, 0))], None
        ex._check(_Sur(float(2.5 + 0.2 * rng.standard_normal())), True, None, (0, 0, 3, 3), {})
        fired += ex.check == "surprise"
    assert fired <= 3                                    # (the fixed 2.5-nat threshold would fire on about half)
    ex.plan, ex.check = [("ACTION1", (-4, 0))], None
    ex._check(_Sur(6.0), True, None, (0, 0, 3, 3), {})   # an outlier for THIS play
    assert ex.check == "surprise"


def _interrupt_agent(non_moving: bool):
    env = TurnEnv(y=20, x=20, box=(20, 40))
    ex = ObjectContactExplorer()
    cfg = AgentConfig(seed=0, use_self=True, use_epistemic=True, handoff_efe=True, contact_context=True)
    ag = _warm(cfg, env, ex, extra=())
    if not non_moving:                                   # every button moves (a Locksmith): drop the interact button
        ag.valid = [b for b in ag.valid if b != "ACTION5"]
    return ag, ex, env


def test_no_interruption_where_every_button_moves():
    ag, ex, _ = _interrupt_agent(non_moving=False)
    ex.check, ex.plan = "arrival", [("ACTION4", (0, 4))]
    drew = []
    ag.policy.draw = lambda b: drew.append(1)
    assert ag._interrupt(ag.perceiver.current) is None
    assert ex.check is None and ex.plan == [("ACTION4", (0, 4))] and not drew   # nothing scored, trip unchanged


def test_a_better_non_moving_button_interrupts_up_to_the_dwell():
    from rulediscovery1__fepInspired.policy import ActionScore
    ag, ex, _ = _interrupt_agent(non_moving=True)
    G = {"ACTION5": -5.0}

    def score(rc, *a, **k):
        return ActionScore(rc.action, 0, 0, 0, 0, 0, G.get(rc.action.name, 0.0))
    ag.policy.score = score
    ex.cfg.dwell = 2
    ex.check, ex.plan = "arrival", [("ACTION4", (0, 4))]
    a = ag._interrupt(ag.perceiver.current)
    assert a is not None and a.name == "ACTION5" and ag.last_decision.mode == "handoff"
    assert ag._interrupt(ag.perceiver.current).name == "ACTION5"
    assert ag._interrupt(ag.perceiver.current) is None and ex.check is None        # dwell used up: resume the trip
    assert ex.interrupts == {"arrival": 2} and ex.plan == [("ACTION4", (0, 4))]
    ex.check = "end"
    G["ACTION5"] = 1.0                                   # continuing (the best move) is better: no interruption
    assert ag._interrupt(ag.perceiver.current) is None and ex.check is None


def test_resume_goes_to_the_same_target_when_the_path_broke():
    ex = ObjectContactExplorer(ExploreConfig(handoff=True, interrupt=True))
    ex._scored = True
    ex.plan, ex.target = [("ACTION4", (0, 4))], NS(type_key=("t",), y0=5, x0=6)
    ex.dwell, ex.dwell_box = 1, (0, 0, 3, 3)
    ex._check(_Sur(0.1), False, None, (0, 4, 3, 7), {})  # the interrupting action moved the self
    assert ex.plan == [] and ex.resume_target == (("t",), 5, 6)


def test_live_agent_interrupts_next_to_the_box_and_presses_interact():
    env = TurnEnv(y=20, x=20, box=(20, 40))
    ex = ObjectContactExplorer()
    cfg = AgentConfig(seed=0, use_self=True, use_epistemic=True, handoff_efe=True, contact_context=True)
    ag = _warm(cfg, env, ex, extra=())
    ex.tries["ACTION5"] = 5
    pressed_next_to_box = 0
    for _ in range(80):
        a = ag.act()
        by, bx = env.box
        beside = abs(env.y - by) + abs(env.x - bx) == 4
        grid, _, _ = env.step(a)
        ag.observe(a, grid)
        pressed_next_to_box += int(beside and a.name == "ACTION5")
    assert sum(ex.checks.values()) > 0 and ex.trip_steps > 0
    assert pressed_next_to_box > 0


# ---------------------------------------------------------------- pick 2: contact neighbourhood

def test_beta_information_gain():
    assert abs(beta_eig(1, 1) - (np.log(2) - 0.5)) < 1e-9       # uniform: H(1/2) - E[H] = ln 2 - 1/2
    assert beta_eig(1, 1) > beta_eig(5, 5) > beta_eig(50, 50) > 0
    assert beta_eig(1, 1) > beta_eig(20, 1)


def _code_at(ag, env, contact):
    rc = ag.slow.ctx.context(ag.perceiver.current, X)
    return contact.code(rc, ag.slow.ctx.controlled_direction), rc


def test_contact_codes_tell_facing_beside_and_open_apart():
    env = TurnEnv(y=20, x=20, box=(20, 40))
    ag = _warm(AgentConfig(seed=0, use_self=True, use_epistemic=True, contact_context=True), env)
    cc = ag.slow.ctx.contact
    assert cc is not None and ag.cfg.policy.w_ceig > 0
    _walk(ag, env, [R] * ((36 - env.x) // 4) if env.x < 36 else [])
    while (env.y, env.x) != (20, 36):                   # stand left of the box
        _walk(ag, env, [U if env.y > 20 else D] if env.y != 20 else [L if env.x > 36 else R])
    _walk(ag, env, [R])                                  # blocked by the box: now FACING it
    face, rc = _code_at(ag, env, cc)
    assert rc.facing is not None and env.ahead() == env.box
    _walk(ag, env, [U, D])                               # turn away and back down, still beside the box, facing down
    beside, _ = _code_at(ag, env, cc)
    _walk(ag, env, [L, L, L])                            # the open field
    open_, _ = _code_at(ag, env, cc)
    sim = lambda a, b: float(cc.vsa.sim(a, b))           # noqa: E731
    assert sim(face, face) > 0.99 and sim(face, beside) < 0.8 and sim(open_, face) < 0.5


def test_novelty_and_effect_belief_follow_the_contact():
    env = TurnEnv(y=20, x=20, box=(20, 40))
    ag = _warm(AgentConfig(seed=0, use_self=True, use_epistemic=True, contact_context=True), env)
    cc, d = ag.slow.ctx.contact, ag.slow.ctx.controlled_direction
    rc_open = ag.slow.ctx.context(ag.perceiver.current, X)
    assert cc.applies(rc_open, d)
    n0 = cc.novelty(rc_open, d)
    for _ in range(4):                                   # interact in the open: nothing happens
        _walk(ag, env, [X])
    rc_open = ag.slow.ctx.context(ag.perceiver.current, X)
    assert cc.novelty(rc_open, d) < 0.5 * n0
    while (env.y, env.x) != (20, 36):
        _walk(ag, env, [U if env.y > 20 else D] if env.y != 20 else [L if env.x > 36 else R])
    _walk(ag, env, [R])                                  # facing the box: a new contact
    rc_box = ag.slow.ctx.context(ag.perceiver.current, X)
    assert cc.novelty(rc_box, d) > 0.8
    a0, b0 = cc.p_change(rc_box, d)
    _walk(ag, env, [X])                                  # the box lights up: a change (the contact the press was made in)
    a1, b1 = cc.p_change(rc_box, d)
    pa, pb = cc.p_change(rc_open, d)
    assert a1 > a0 + 0.5 and a1 / (a1 + b1) > pa / (pa + pb)
    assert cc.changes >= 1


def test_ambient_parts_are_not_a_change():
    cc = ContactContext(min_steps=3)
    tick = NS(reset=False, scored=True, parts=lambda: ["grow", "shrink"], action=X)
    rc = NS(action=Action("ACTION1"))                    # a moving button: only the ambient counts are fed
    for _ in range(5):
        cc.observe(rc, tick, lambda b: (0, 4))
    assert not cc.changed_something({"grow", "shrink"}) and cc.changed_something({"grow", "van"})


def test_policy_scores_a_non_moving_button_from_its_contact():
    env = TurnEnv(y=20, x=20, box=(20, 40))
    ag = _warm(AgentConfig(seed=0, use_self=True, use_epistemic=True, contact_context=True), env)
    s = ag.slow
    for _ in range(4):
        _walk(ag, env, [X])
    rc = s.ctx.context(ag.perceiver.current, X)
    g_open = ag.policy.score(rc, s.beliefs, s.goals, s.prefs, s.ctx)
    while (env.y, env.x) != (20, 36):
        _walk(ag, env, [U if env.y > 20 else D] if env.y != 20 else [L if env.x > 36 else R])
    _walk(ag, env, [R])
    rc = s.ctx.context(ag.perceiver.current, X)
    g_box = ag.policy.score(rc, s.beliefs, s.goals, s.prefs, s.ctx)
    assert g_box.local_novelty > g_open.local_novelty and g_box.disagreement > g_open.disagreement


# ---------------------------------------------------------------- pick 3: lives, end belief, urgency

LIFE = 8


def _lives_board(n, lives=3, player=(20, 20)):
    g = _bar_board(n, player)
    for i in range(lives):
        put(g, 62, 40 + 3 * i, 2, 2, LIFE)
    return g


def test_lives_reader_finds_and_reads_a_counter_beside_the_bar():
    rd = LivesReader()
    first = np.array(_lives_board(24))
    rd.find(first, (62, 63, 0, 23), BAR)
    assert rd.spec is not None and rd.count(first) == 3
    assert rd.count(np.array(_lives_board(10, lives=2))) == 2
    rd.find(np.array(_bar_board(24)), (62, 63, 0, 23), BAR)
    assert rd.spec is None and rd.count(np.array(_bar_board(24))) is None
    big = _bar_board(24)
    for i in range(3):
        put(big, 62, 40 + 6 * i, 2, 5, LIFE)              # 10 cells each: too big for a counter item
    rd.find(np.array(big), (62, 63, 0, 23), BAR)
    assert rd.spec is None


def _feed_lives(bm, values, lives):
    for i, n in enumerate(values):
        bm.observe(_tr(), _lives_board(n, lives, (20, 20 + 4 * (i % 5))))


def test_spare_lives_lower_the_run_out_risk_and_bring_information():
    bm = BudgetModel(BudgetConfig(learn_end=True))
    bm.begin(_lives_board(24))
    _feed_lives(bm, list(range(23, 3, -1)), 3)           # 4 columns left
    f = bm.forecast()
    assert bm.lives_now == 3 and bm.spare()
    assert f.p_over < 0.2                                # prior 0.8 fatal; a counter beside the bar: lives
    assert bm.info(Action("ACTION1")) > 0.1 and bm.info(Action("RESET")) == 0.0
    assert not bm.urgent()                               # running out is cheaper than a RESET here
    nolife = BudgetModel(BudgetConfig(learn_end=True))
    nolife.begin(_bar_board(24))
    for i, n in enumerate(range(23, 3, -1)):
        nolife.observe(_tr(), _bar_board(n, (20, 20 + 4 * (i % 5))))
    assert nolife.lives_now is None and not nolife.spare()
    assert nolife.forecast().p_over >= 0.8 and nolife.info(Action("ACTION1")) == 0.0 and nolife.urgent()


def test_a_survived_run_out_refutes_fatal():
    bm = BudgetModel(BudgetConfig(learn_end=True))
    bm.begin(_lives_board(12))
    _feed_lives(bm, list(range(11, 0, -1)), 3)
    p_before = bm.p_fatal(BAR)
    _feed_lives(bm, [24], 2)                             # refilled without a RESET, one life gone
    assert bm.survived_ends == 1 and bm.tests == 1 and bm.lives_now == 2
    assert bm.p_fatal(BAR) < 0.1 * p_before


def test_last_life_makes_running_out_fatal_again():
    bm = BudgetModel(BudgetConfig(learn_end=True))
    bm.begin(_lives_board(24))
    _feed_lives(bm, list(range(23, 3, -1)), 1)           # one life shown: no spare
    assert not bm.spare() and bm.forecast().p_over > 0.99 and bm.urgent()


def test_urgency_waits_while_the_plan_fits():
    bm = BudgetModel(BudgetConfig(learn_end=True))
    bm.begin(_bar_board(24))
    for i, n in enumerate(range(23, 3, -1)):             # 4 steps left, no lives: urgent
        bm.observe(_tr(), _bar_board(n, (20, 20 + 4 * (i % 5))))
    assert bm.urgent(0) and bm.urgent(9)                 # no plan / a plan that does not fit
    assert not bm.urgent(3) and bm.urgency(3) == "plan_fits"


def test_learn_end_off_keeps_the_stage_one_numbers():
    a, b = BudgetModel(), BudgetModel(BudgetConfig(learn_end=True))
    for bm in (a, b):
        bm.begin(_lives_board(24))
        _feed_lives(bm, list(range(23, 3, -1)), 3)
    assert abs(a.forecast().p_over - 0.8) < 1e-9 and a.lives_now is None and a.info(Action("ACTION1")) == 0.0
    assert a.urgent() and a.urgent(3)                    # stage one: plan and lives ignored
    assert b.forecast().p_over < a.forecast().p_over


class LivesBarEnv(BarEnv):
    """BarEnv whose empty bar costs a life (three 2 x 2 items beside it) and refills; the last life ends the game."""

    def __init__(self):
        super().__init__()
        self.lives = 3

    def board(self):
        g = super().board()
        for i in range(self.lives):
            put(g, 62, 40 + 3 * i, 2, 2, LIFE)
        return g

    def step(self, a):
        if a.name == "RESET":
            self.lives = 3
        grid, lc, go = super().step(a)
        if go:
            self.lives -= 1
            if self.lives > 0:
                self.n = 24
                return self.board(), False, False
        return self.board(), lc, go


def _lives_play(env, steps=120):
    from rulediscovery1__fepInspired.policy import PolicyConfig
    ag = RuleDiscoveryAgent(AgentConfig(seed=1, use_budget=True, budget_learn=True, policy=PolicyConfig(cost_reset=3.0)))
    ag.start_play(env.board(), BUTTONS5 + ["RESET"])
    for n in range(steps):
        a = ag.act()
        grid, _, go = env.step(a)
        ag.observe(a, grid, game_over=go)
        if go:
            return ag, n + 1
    return ag, None


def test_live_with_lives_the_agent_tests_the_run_out_and_survives():
    ag, over = _lives_play(LivesBarEnv())
    bm = ag.budget
    assert over is None and bm.lives_found >= 1 and bm.tests >= 1 and bm.p_fatal(BAR) < 0.05


def test_live_without_lives_the_agent_still_resets_before_the_end():
    ag, over = _lives_play(BarEnv(), steps=80)
    assert over is None and ag.budget.lives_found == 0 and ag.budget_resets >= 2


# ---------------------------------------------------------------- default off

def test_debate3_switches_default_off():
    cfg = AgentConfig()
    assert not (cfg.handoff_efe or cfg.contact_context or cfg.budget_learn)
    ex = ObjectContactExplorer()
    ag = RuleDiscoveryAgent(cfg, explorer=ex)
    ag.start_play(TurnEnv().board(), BUTTONS5)
    assert ag.slow.ctx.contact is None and ag.cfg.policy.w_ceig == 0 and not ex.cfg.interrupt
    ag2 = RuleDiscoveryAgent(AgentConfig(use_budget=True))
    ag2.start_play(TurnEnv().board(), BUTTONS5)
    assert not ag2.budget.cfg.learn_end
