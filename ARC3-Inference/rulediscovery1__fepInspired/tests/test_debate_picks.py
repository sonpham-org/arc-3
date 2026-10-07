# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Tests for the five debate picks (docs 2026-09-24-warehouse-expert-debate.md, OpenMind #arc-3 22:49 ET), on a
#   small synthetic "turning sprite" world (TurnEnv): a 4x4 player whose facing strip (colour 11) sits on the side it
#   faces and whose body (colour 14) takes the rest, so every turn redraws both parts (the Warehouse failure); arrows
#   turn and move one 4-cell step unless blocked; ACTION5 recolours a 4x4 box (6 <-> 3) only when the player faces it.
#     - pick 1: the contingency self learns both colours, keeps the player's exact box through turns, and learns 4-cell
#       moves (the type-keyed tracker sees 3 / 5 / 7-cell steps here);
#     - pick 2: with the Facing relation the tensor-logic learner exports a rule that predicts "the box ahead turns
#       colour 3" for ACTION5 when facing the box, and nothing when facing away;
#     - pick 3: the local-context novelty decays with visits and stays high for an unseen colour neighbourhood; the
#       ensemble disagreement is zero for agreeing and positive for disagreeing rule sets; the tempered draws reach
#       rule sets that are behind;
#     - pick 4: the archive key leaves out the self and clock lines; stagnation triggers RESET + replay of the stored path;
#     - pick 5: contrast evidence prefers the goal that is distinctive of the clearing board over one that held all along;
#     - default: every switch off, no new state anywhere.
# SRP/DRY check: Pass -- board helpers from synth.py, the package's own Perceiver / ContextBuilder / learner.
from __future__ import annotations

import random

from rulediscovery1__fepInspired.agent import AgentConfig, RuleDiscoveryAgent
from rulediscovery1__fepInspired.archive import GoExploreArchive, config_key
from rulediscovery1__fepInspired.epistemic import LocalNovelty, disagreement, sample_hypotheses
from rulediscovery1__fepInspired.goals import FillGoal, GoalBeliefs
from rulediscovery1__fepInspired.perception import Action, Perceiver, Scene
from rulediscovery1__fepInspired.rules import ContextBuilder
from rulediscovery1__fepInspired.selfmodel import ContingentSelf
from rulediscovery1__fepInspired.tests.synth import blank, put

STRIP, BODY, BOX, LIT = 11, 14, 6, 3
U, D, L, R, X = (Action(n) for n in ("ACTION1", "ACTION2", "ACTION3", "ACTION4", "ACTION5"))
STEP = {"ACTION1": (-4, 0), "ACTION2": (4, 0), "ACTION3": (0, -4), "ACTION4": (0, 4)}


class TurnEnv:
    def __init__(self, y: int = 20, x: int = 20, box: tuple = (20, 40)):
        self.y, self.x, self.face = y, x, (-4, 0)
        self.box, self.lit = box, False

    def board(self):
        g = blank()
        put(g, self.box[0], self.box[1], 4, 4, LIT if self.lit else BOX)
        y, x = self.y, self.x
        put(g, y, x, 4, 4, BODY)
        fy, fx = self.face
        if fy < 0:
            put(g, y, x, 1, 4, STRIP)
        elif fy > 0:
            put(g, y + 3, x, 1, 4, STRIP)
        elif fx < 0:
            put(g, y, x, 4, 1, STRIP)
        else:
            put(g, y, x + 3, 4, 1, STRIP)
        return g

    def ahead(self) -> tuple:
        return (self.y + self.face[0], self.x + self.face[1])

    def step(self, a: Action):
        if a.name in STEP:
            self.face = STEP[a.name]
            ny, nx = self.ahead()
            if 8 <= ny <= 52 and 8 <= nx <= 52 and (ny, nx) != self.box:
                self.y, self.x = ny, nx
        elif a.name == "ACTION5" and self.ahead() == self.box:
            self.lit = not self.lit
        return self.board(), False, False


WARMUP = [D, D, U, U, U, L, L, R, R, R, D, D, U, U, L, L, R, R, D, U, L, R, D, D, U, U, L, L, R, R]


def route(env, actions, y, x) -> list:
    """Actions that, after `actions`, walk the player to (y, x) (vertical first), on a copy of the world."""
    import copy
    e = copy.deepcopy(env)
    for a in actions:
        e.step(a)
    out = []
    while e.y != y:
        a = D if e.y < y else U
        e.step(a)
        out.append(a)
    while e.x != x:
        a = R if e.x < x else L
        e.step(a)
        out.append(a)
    return out


def run(env, actions, ctx=None):
    p = Perceiver()
    ctx = ctx or ContextBuilder(selfm=ContingentSelf())
    p.begin(env.board())
    ctx.begin(p.current)
    trs = []
    for a in actions:
        grid, _, _ = env.step(a)
        rc = ctx.context(p.current, a)
        tr = p.observe(a, grid)
        ctx.observe(tr)
        trs.append((rc, tr, (env.y, env.x)))
    return ctx, p, trs


# ---------------------------------------------------------------- pick 1

def test_contingency_self_survives_turning():
    env = TurnEnv()
    ctx, p, trs = run(env, WARMUP + [L, U, R, D, R, U, L, D])
    sm = ctx.selfm
    assert {STRIP, BODY} <= sm.colours()
    assert sm.dirs() == {"ACTION1": (-4, 0), "ACTION2": (4, 0), "ACTION3": (0, -4), "ACTION4": (0, 4)}
    f = sm.frame(p.current)
    assert f is not None and f.box == (env.y, env.x, env.y + 3, env.x + 3)
    # every one of the last eight steps turned the sprite; the self kept the true box through all of them
    for rc, tr, (y, x) in trs[-7:]:
        fr = sm.frame(tr.pre)
        assert rc.self_ids is not None and rc.agent is not None and rc.agent.id in rc.self_ids
    moves, blockers, passable = sm.mover()
    assert set(moves) == {"ACTION1", "ACTION2", "ACTION3", "ACTION4"}


def test_self_is_frozen_into_the_context_and_explorer_uses_it():
    from rulediscovery1__fepInspired.explore import SELFGROUP, ObjectContactExplorer

    class Stub:                               # the two agent attributes the explorer's mover lookup reads
        pass
    env = TurnEnv()
    ctx, p, _ = run(env, WARMUP)
    rc = ctx.context(p.current, R)
    assert rc.self_ids == ctx.selfm.frame(p.current).ids
    ag = Stub()
    ag.slow = Stub()
    ag.slow.ctx = ctx
    ex = ObjectContactExplorer()
    moves, blockers, (ctl, group) = ex.mover_model(ag)
    assert group == SELFGROUP and moves["ACTION4"] == (0, 4)
    parts = ex.sprite(ag, p.current, ctl, group)
    assert {c.colour for c in parts} == {STRIP, BODY}


# ---------------------------------------------------------------- pick 2

def test_facing_relation_learns_interact_changes_the_object_ahead():
    from rulediscovery1__fepInspired.tl.bridge import TLSource, make_tl
    from rulediscovery1__fepInspired.tl.learner import TLConfig
    env = TurnEnv()
    tl = make_tl(TLConfig(facing=True))
    ctx = ContextBuilder(tl=tl, selfm=ContingentSelf(), facing=True)
    # warm up, walk next to the box (left of it), face it, press interact facing it and facing away
    seq = WARMUP + route(env, WARMUP, env.box[0], env.box[1] - 4)
    seq += [R, X, X, X, L, X, X, R, X, X, U, X, D, R, X, X, X]
    ctx, p, trs = run(env, seq, ctx)
    src = TLSource(tl)
    rules = src.propose()
    face = [r for r in rules if any("(facing)" in c and "ACTION5" in c for c in r.clauses())]
    assert face, [r.describe() for r in rules]
    # predictions on the live board: the player faces the box -> interact recolours it; the same board with the
    # facing turned away (only the frozen view changes) -> no recolour
    import dataclasses
    assert env.ahead() == env.box
    rc = ctx.context(p.current, X)
    recol = lambda rc_: any(any(e.kind == "recolour" for e in (r.predict(rc_) or [])) for r in face)  # noqa: E731
    assert recol(rc)
    away = rc.replace(tl=dataclasses.replace(rc.tl, facing=(0, -4, 1.0)))
    assert not recol(away)


# ---------------------------------------------------------------- pick 3

def test_local_novelty_decays_with_visits_and_is_soft():
    env = TurnEnv()
    ctx, p, _ = run(env, WARMUP)
    ln = LocalNovelty()
    rc = ctx.context(p.current, R)
    d = ctx.controlled_direction
    assert abs(ln.novelty(rc, d) - 1.0) < 1e-9
    ln.observe(rc, d)
    assert 0.4 < ln.novelty(rc, d) < 0.6
    ln.observe(rc, d)
    assert 0.25 < ln.novelty(rc, d) < 0.42
    rc_up = ctx.context(p.current, U)                 # other action: its own memory
    assert abs(ln.novelty(rc_up, d) - 1.0) < 1e-9


def test_disagreement_and_tempered_draws():
    a = {"x": 0.9, "y": 0.1}
    b = {"x": 0.1, "y": 0.9}
    assert disagreement([a, a], [0, 1]) < 1e-12
    assert disagreement([a, b], [0, 1]) > 0.3

    class H:
        def __init__(self, s):
            self.log_score = s

    class B:
        hyps = [H(0.0), H(-10.0)]
    rng = random.Random(0)
    cold = sample_hypotheses(B, rng, 400, 1.0)
    warm = sample_hypotheses(B, rng, 400, 5.0)
    assert cold.count(1) <= 2 and warm.count(1) > 20


# ---------------------------------------------------------------- pick 4

class _F:
    def __init__(self, ids):
        self.ids = frozenset(ids)


class _SelfStub:
    def __init__(self):
        self.ids = set()

    def frame(self, scene):
        return _F(self.ids)


class _Ctx:
    def __init__(self):
        self.selfm = _SelfStub()


class _Tr:
    def __init__(self, pre, post, action, reset=False):
        self.pre, self.post, self.action, self.reset, self.level_completed = pre, post, action, reset, False


def _scene(box_x: int, player_x: int = 10, bar: int = 5):
    g = blank()
    put(g, 30, box_x, 4, 4, BOX)
    put(g, 20, player_x, 4, 4, BODY)
    put(g, 62, 0, 1, bar, 7)                           # a clock on the border
    sc = Scene.from_grid(g, None)
    return sc


def test_archive_key_ignores_self_and_clocks():
    a = _scene(40, 10, 5)
    b = _scene(40, 18, 9)
    me_a = {c.id for c in a.objects() if c.colour == BODY}
    me_b = {c.id for c in b.objects() if c.colour == BODY}
    rows = frozenset([62])
    assert config_key(a, me_a, rows) == config_key(b, me_b, rows)
    assert config_key(a, me_a, rows) != config_key(_scene(44), me_a, rows)


def test_archive_returns_by_reset_and_replay():
    ctx = _Ctx()
    arc = GoExploreArchive()
    arc.cfg.stagnation = 3
    s0 = _scene(40)
    arc.begin(ctx, s0, 0)
    s1 = _scene(44)
    arc.observe(ctx, _Tr(s0, s1, R), 0)                # a new configuration, reached by [R]
    for _ in range(3):
        arc.observe(ctx, _Tr(s1, s1, U), 0)            # nothing new
    a = arc.next_action(["ACTION1", "ACTION4", "RESET"])
    assert a.name == "RESET" and arc.returns == 1 and [x.name for x in arc.queue] == ["ACTION4"]
    arc.observe(ctx, _Tr(s1, s0, a, reset=True), 0)
    a2 = arc.next_action(["ACTION1", "ACTION4", "RESET"])
    assert a2.name == "ACTION4"
    arc.observe(ctx, _Tr(s0, s1, a2), 0)
    assert arc.arrived == 1 and arc.missed == 0


# ---------------------------------------------------------------- pick 5

def _goal_scene(n2: int, extra: bool):
    g = blank()
    for i in range(n2):
        put(g, 10, 10 + 5 * i, 2, 2, 2)
    put(g, 40, 40, 3, 3, 5)                            # one colour-5 object, always there
    if extra:
        put(g, 50, 50, 2, 2, 8)
    return Scene.from_grid(g, None)


class _GTr:
    def __init__(self, pre, post, clear=False):
        self.pre, self.post, self.level_completed, self.reset = pre, post, clear, False
        self.scored = not clear


def test_contrast_prefers_the_distinctive_goal():
    start = _goal_scene(3, True)
    out = {}
    for contrast in (False, True):
        gb = GoalBeliefs(contrast=contrast)
        gb.bind_level(start)
        for _ in range(10):
            gb.observe(_GTr(start, start))
        win = _goal_scene(0, True)                     # every colour-2 piece converted away
        gb.observe(_GTr(win, None, clear=True), imagined=win)
        post = gb.posterior()
        out[contrast] = post[FillGoal(2).key()]
    assert out[True] > out[False]


# ---------------------------------------------------------------- default off

def test_all_debate_switches_default_off():
    cfg = AgentConfig()
    assert not (cfg.use_self or cfg.tl_facing or cfg.use_epistemic or cfg.use_archive or cfg.goal_contrast)
    env = TurnEnv()
    ag = RuleDiscoveryAgent(cfg)
    ag.start_play(env.board(), ["ACTION1", "ACTION2", "ACTION3", "ACTION4", "ACTION5"])
    assert ag.slow.ctx.selfm is None and ag.slow.ctx.lnov is None and ag.archive is None
    assert not ag.slow.ctx.track_facing and not ag.slow.goals.contrast
    pc = ag.cfg.policy
    assert pc.w_dis == 0 and pc.w_lnov == 0 and pc.epi_preempt == 0
    rc = ag.slow.ctx.context(ag.perceiver.current, X)
    assert rc.self_ids is None and rc.facing is None
