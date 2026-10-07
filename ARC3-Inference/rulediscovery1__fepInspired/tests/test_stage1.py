# Author: Claude Opus 5.5 (Bubba)
# Date: 25-September-2026
# PURPOSE: Tests for stage one of the second Warehouse debate (docs 2026-09-25-warehouse-expert-debate-2.md, Round 8 picks 1
#   and 2; OpenMind #arc-3 25-Sep-2026 02:38 ET):
#     - explorer as an option (explore.ExploreConfig.handoff): a running trip is cut when the self comes into NEW contact
#       with an object (each object / self position once), or on a surprising outcome; the policy then has the choice for
#       the dwell while the self stays put; the trip's target is not marked touched; on the turning-sprite world the agent
#       hands off and presses the non-moving button while standing next to the box;
#     - budget (budget.py): the ring gauge finder finds a draining bar from boards alone; the forecast gives steps left,
#       the refill after a RESET, and a risk that is near zero far from the end, high at the end, zero for RESET and
#       exactly zero with no gauge; a bar that runs out and refills without a RESET lowers P(game over | run out); the
#       policy's G for a non-RESET action rises by w_prag * risk * -c_game_over; a live agent on a world whose bar ends the
#       game resets before running out;
#     - the archive's start_return respects a replay-length limit; only a RESET chosen while the budget is urgent
#       becomes an archive return;
#     - with the contingency self a trip is not cut as "blocked" when the sprite redraws on turning (the live test);
#     - default: both switches off, no new state anywhere.
# SRP/DRY check: Pass -- worlds and helpers from synth.py and test_debate_picks.py (TurnEnv); the package's own agent,
#   explorer, archive, policy and budget. New: the tests.
from __future__ import annotations

from types import SimpleNamespace as NS

import numpy as np

from rulediscovery1__fepInspired.agent import AgentConfig, RuleDiscoveryAgent
from rulediscovery1__fepInspired.archive import GoExploreArchive
from rulediscovery1__fepInspired.budget import BudgetModel
from rulediscovery1__fepInspired.explore import ExploreConfig, ObjectContactExplorer
from rulediscovery1__fepInspired.perception import Action
from rulediscovery1__fepInspired.tests.synth import blank, put
from rulediscovery1__fepInspired.tests.test_debate_picks import WARMUP, TurnEnv, _Ctx, _scene, _Tr

BUTTONS5 = ["ACTION1", "ACTION2", "ACTION3", "ACTION4", "ACTION5"]


# ---------------------------------------------------------------- hand-off, unit

class _Agent:
    def __init__(self, surprisal=0.1, spike=False):
        self.last_surprise = NS(surprisal=surprisal, spike=spike)


def test_handoff_cuts_the_trip_on_new_contact_once():
    ex = ObjectContactExplorer(ExploreConfig(handoff=True, dwell=2))
    far, near = (10, 10, 13, 13), (20, 30, 23, 33)
    obj = {("o", 20, 34): (20, 34, 23, 37)}           # touches the self box `near` on its right edge
    ex.prev_adj = set()
    ex.plan, ex.target = [("ACTION4", (0, 4))], "target"
    ex._handoff(_Agent(), True, None, far, obj)         # not in contact: the trip goes on
    assert ex.plan and ex.dwell == 0 and not ex.handoffs
    ex._handoff(_Agent(), True, None, near, obj)        # new contact: cut, the policy gets the choice
    assert ex.plan == [] and ex.dwell == 2 and ex.handoffs == {"arrival": 1}
    assert ex.next_action(None) is None                 # dwell: no trip (the agent is not even consulted)
    ex._handoff(_Agent(), False, None, near, obj)       # a policy step, self stays: dwell counts down
    assert ex.dwell == 1
    ex._handoff(_Agent(), False, None, far, obj)        # the policy walked away: dwell over
    assert ex.dwell == 0
    ex.plan, ex.prev_adj = [("ACTION4", (0, 4))], set()
    ex._handoff(_Agent(), True, None, near, obj)        # the same object from the same place: no second hand-off
    assert ex.plan and ex.handoffs == {"arrival": 1}


def test_handoff_on_surprise_and_on_trip_end():
    ex = ObjectContactExplorer(ExploreConfig(handoff=True))
    ex.prev_adj, ex.plan = set(), [("ACTION1", (-4, 0))]
    ex._handoff(_Agent(surprisal=3.0), True, None, (0, 0, 3, 3), {})
    assert ex.plan == [] and ex.handoffs == {"surprise": 1}
    ex.dwell = 0
    ex._handoff(_Agent(), True, "blocked", (0, 0, 3, 3), {})
    ex.dwell = 0
    ex._handoff(_Agent(), True, "end", (0, 0, 3, 3), {})
    assert ex.handoffs == {"surprise": 1, "blocked": 1, "end": 1}


def test_handoff_off_leaves_the_explorer_untouched():
    ex = ObjectContactExplorer()
    assert not ex.cfg.handoff
    ag = RuleDiscoveryAgent(AgentConfig(use_self=True), explorer=ex)
    ag.start_play(TurnEnv().board(), BUTTONS5)
    assert not ex.cfg.handoff and ag.budget is None


# ---------------------------------------------------------------- hand-off, live on the turning-sprite world

def test_agent_hands_off_next_to_the_box_and_presses_interact_there():
    env = TurnEnv(y=20, x=20, box=(20, 40))
    ex = ObjectContactExplorer()
    ag = RuleDiscoveryAgent(AgentConfig(seed=0, use_self=True, use_epistemic=True, explore_handoff=True), explorer=ex)
    ag.start_play(env.board(), BUTTONS5)
    for a in WARMUP:                                    # learn the moves (every button tried)
        grid, _, _ = env.step(a)
        ag.observe(a, grid)
    ex.tries["ACTION5"] = 5
    modes, pressed_x_next_to_box = [], 0
    for _ in range(60):
        a = ag.act()
        modes.append(ag.last_decision.mode)
        by, bx = env.box
        beside = abs(env.y - by) + abs(env.x - bx) == 4
        grid, _, _ = env.step(a)
        ag.observe(a, grid)
        pressed_x_next_to_box += int(beside and a.name == "ACTION5")
    assert sum(ex.handoffs.values()) > 0 and ex.handoffs.get("arrival", 0) + ex.handoffs.get("end", 0) > 0
    assert "touch" in modes and any(m != "touch" for m in modes)
    assert pressed_x_next_to_box > 0


# ---------------------------------------------------------------- budget

BAR = 9


def _bar_board(n, player=(20, 20)):
    g = blank()
    put(g, player[0], player[1], 4, 4, 14)
    if n:
        put(g, 62, 0, 2, n, BAR)
    return g


def _tr(reset=False, game_over=False):
    return NS(reset=reset, level_completed=False, game_over=game_over, pre=NS(level=0), post=NS(level=0))


def _feed(bm, values, player_moves=True):
    for i, n in enumerate(values):
        bm.observe(_tr(), _bar_board(n, (20, 20 + 4 * (i % 5)) if player_moves else (20, 20)))


def test_no_gauge_means_exactly_zero_risk():
    bm = BudgetModel()
    bm.begin(_bar_board(32))
    _feed(bm, [32] * 20)                                # nothing drains
    assert bm.forecast() is None and bm.risk(Action("ACTION1")) == 0.0 and not bm.urgent()


def test_budget_forecasts_steps_left_refill_and_risk():
    bm = BudgetModel()
    bm.begin(_bar_board(24))
    _feed(bm, list(range(23, 9, -1)))                   # one column (2 cells) per step, down to 10 columns
    f = bm.forecast()
    assert f is not None and f.colour == BAR
    assert abs(f.rate - 2.0) < 1e-9 and abs(f.steps_left - 10.0) < 1e-9
    assert abs(f.steps_after_reset - 24.0) < 1e-9       # read on the level's first board
    assert bm.risk(Action("ACTION1")) < 0.05 and bm.risk(Action("RESET")) < 1e-6 and not bm.urgent()
    _feed(bm, list(range(9, 3, -1)))                    # 4 steps left
    assert bm.urgent() and bm.risk(Action("ACTION1")) > 0.4 and bm.risk(Action("RESET")) < 1e-6
    bm.observe(_tr(reset=True), _bar_board(20))         # a RESET refills to 20 columns: learned
    _feed(bm, [19, 18])
    assert abs(bm.forecast().steps_after_reset - 20.0) < 1e-9 and not bm.urgent()


def test_running_out_and_refilling_lowers_p_game_over():
    bm = BudgetModel()
    bm.begin(_bar_board(12))
    _feed(bm, list(range(11, 0, -1)) + [40])            # runs to one, then refills without a RESET: survived
    assert bm.survived_ends == 1
    _feed(bm, list(range(39, 30, -1)))
    f = bm.forecast()
    assert f is not None and f.p_over < 0.8 - 1e-9      # prior 4/5 -> 4/6


def test_policy_prices_the_run_out_risk_with_the_game_over_preference():
    from rulediscovery1__fepInspired.policy import PolicyConfig
    env = TurnEnv()
    base = RuleDiscoveryAgent(AgentConfig(seed=0))
    base.start_play(env.board(), BUTTONS5 + ["RESET"])
    rc = base.slow.ctx.context(base.perceiver.current, Action("ACTION1"))
    s = base.slow
    g0 = base.policy.score(rc, s.beliefs, s.goals, s.prefs, s.ctx).G
    s.ctx.budget = NS(risk=lambda a: 0.5)
    assert base.policy.score(rc, s.beliefs, s.goals, s.prefs, s.ctx).G == g0     # w_budget 0: ignored
    base.policy.cfg = PolicyConfig(w_budget=1.0)
    sc = base.policy.score(rc, s.beliefs, s.goals, s.prefs, s.ctx)
    assert abs(sc.G - (g0 + 0.5 * -s.prefs.c_game_over)) < 1e-9 and sc.budget_risk == 0.5


class BarEnv(TurnEnv):
    """TurnEnv with a step bar: 2 x 24 cells, one column per action; empty bar -> game over; RESET refills it."""

    def __init__(self):
        super().__init__(box=(44, 44))
        self.n = 24

    def board(self):
        g = super().board()
        if self.n:
            put(g, 62, 0, 2, self.n, BAR)
        return g

    def step(self, a):
        if a.name == "RESET":
            self.y, self.x, self.face, self.n = 20, 20, (-4, 0), 24
            return self.board(), False, False
        super().step(a)
        self.n = max(self.n - 1, 0)
        return self.board(), False, self.n == 0


def _bar_play(use_budget: bool, steps: int = 80):
    from rulediscovery1__fepInspired.policy import PolicyConfig
    env = BarEnv()
    # RESET priced high, so that without the budget the agent has no reason to press it
    ag = RuleDiscoveryAgent(AgentConfig(seed=1, use_budget=use_budget, policy=PolicyConfig(cost_reset=3.0)))
    ag.start_play(env.board(), BUTTONS5 + ["RESET"])
    resets = 0
    for n in range(steps):
        a = ag.act()
        grid, _, go = env.step(a)
        resets += int(a.name == "RESET")
        ag.observe(a, grid, game_over=go)
        if go:
            return ag, resets, n + 1
    return ag, resets, None


def test_agent_with_budget_resets_before_the_bar_runs_out():
    _, resets0, over0 = _bar_play(False)
    assert over0 is not None and resets0 == 0             # without: the bar runs out
    ag, resets, over = _bar_play(True)
    assert ag.budget.found_at is not None and over is None
    assert resets >= 2 and ag.budget_resets == resets     # every RESET was pressed with the run-out imminent


def test_only_an_urgent_reset_becomes_an_archive_return():
    from rulediscovery1__fepInspired.policy import Decision
    ag = RuleDiscoveryAgent(AgentConfig(seed=0, use_budget=True, use_archive=True))
    ag.start_play(TurnEnv().board(), BUTTONS5 + ["RESET"])
    ag.policy.choose = lambda *a, **k: Decision(Action("RESET"), "efe")
    asked = []
    ag.archive.start_return = lambda n=None: asked.append(n) or Action("RESET")
    ag.budget.return_len = lambda: 9
    a = ag._policy_step(ag.perceiver.current, False)     # not urgent: the policy's RESET is left as it was
    assert a.name == "RESET" and ag.last_decision.mode == "efe" and not asked and ag.budget_returns == 0
    a = ag._policy_step(ag.perceiver.current, True)      # urgent: a return whose replay fits the refilled budget
    assert a.name == "RESET" and ag.last_decision.mode == "return" and asked == [9]
    assert ag.budget_returns == 1 and ag.budget_resets == 1


# ---------------------------------------------------------------- archive return limit

def test_archive_start_return_respects_the_replay_limit():
    ctx = _Ctx()
    arc = GoExploreArchive()
    s0 = _scene(40)
    arc.begin(ctx, s0, 0)
    s1 = _scene(44)
    from rulediscovery1__fepInspired.tests.test_debate_picks import R
    arc.observe(ctx, _Tr(s0, s1, R), 0)                 # a cell one step from the start
    assert arc.start_return(max_len=0) is None
    a = arc.start_return(max_len=1)
    assert a is not None and a.name == "RESET" and [x.name for x in arc.queue] == ["ACTION4"]
    arc.abandon()
    assert arc.queue == [] and arc.target is None


# ---------------------------------------------------------------- default off

def test_stage1_switches_default_off():
    cfg = AgentConfig()
    assert not (cfg.explore_handoff or cfg.use_budget)
    ex = ObjectContactExplorer()
    ag = RuleDiscoveryAgent(cfg, explorer=ex)
    ag.start_play(TurnEnv().board(), BUTTONS5)
    assert ag.budget is None and ag.slow.ctx.budget is None and ag.cfg.policy.w_budget == 0 and not ex.cfg.handoff
    a = ag.act()
    grid, _, _ = TurnEnv().step(a)
    ag.observe(a, grid)
    assert ex.handoffs == {} and ex.trip_steps == 0 and ag.budget_resets == 0
    assert np.isfinite(ag.slow.beliefs.posterior_entropy())
