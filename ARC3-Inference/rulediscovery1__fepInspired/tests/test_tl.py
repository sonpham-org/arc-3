# Author: Claude Opus 5.5 (Bubba)
# Date: 24-September-2026
# PURPOSE: Tests for the tensor-logic overhaul (tl/, OpenMind #arc-3 24-Sep-2026):
#   - engine: Datalog as join + projection + step (the paper's Aunt example), recursive forward chaining to fixpoint
#     (transitive closure), the temperature (T = 0 step, T > 0 sigmoid), gradients of multilinear sparse equations
#     (dense-head, scalar, bilinear, softmax-simplex lag) against finite differences, and exact zeros from the L1 step;
#   - relations: per-object effect targets and the Ahead strip on the synthetic mover world;
#   - learner: with the templates OFF it learns the arrows and the wall of the mover world, the exported rule predicts
#     a free move and a blocked move correctly, the rule's identity changes with its weights, its price is in the same
#     range as the template d-pad rule on the same data, and the posterior's replay stays exact with learned rules;
#   - planning: forward-chaining reachability finds the same trip lengths and target as the explorer's search;
#   - default off: no tensor-logic state anywhere.
# SRP/DRY check: Pass -- fixtures from synth.py; checks only the new pieces.
from __future__ import annotations

import math

import numpy as np

from rulediscovery1__fepInspired.agent import AgentConfig, RuleDiscoveryAgent
from rulediscovery1__fepInspired.beliefs import PredictionCache, score_ruleset
from rulediscovery1__fepInspired.explore import ObjectContactExplorer, _on
from rulediscovery1__fepInspired.hypotheses import TemplateFitter
from rulediscovery1__fepInspired.perception import Action, Scene
from rulediscovery1__fepInspired.rules import DLContext, PadMoveRule
from rulediscovery1__fepInspired.tests.synth import LEFT, MOVER, RIGHT, UP, WALL, MoverEnv, blank, put
from rulediscovery1__fepInspired.tl import plan as tl_plan
from rulediscovery1__fepInspired.tl.engine import (Adam, Param, Program, Rel, SparseEq, equation, grads, logits,
                                                   nonlin, softmax_xent)
from rulediscovery1__fepInspired.tl.relations import EDGE, SceneRel, target_effects

DOWN = Action("ACTION2")


# ---------------------------------------------------------------- engine

def test_datalog_is_join_projection_step():
    sister = Rel.of(("x", "y"), [(0, 1)])                 # Alice(0) is Bob(1)'s sister
    parent = Rel.of(("y", "z"), [(1, 2), (1, 3)])         # Bob is the parent of Carol(2) and Dan(3)
    aunt = equation(("x", "z"), sister, parent, T=0.0)
    assert aunt.facts() == {(0, 2), (0, 3)}
    two_paths = Rel.of(("x", "y"), [(0, 1), (0, 4)]).join(Rel.of(("y", "z"), [(1, 2), (4, 2)])).project(("x", "z"))
    assert two_paths.to_dense((5, 5))[0, 2] == 2.0        # projection sums; the step makes it Boolean
    assert equation(("x", "z"), Rel.of(("x", "y"), [(0, 1), (0, 4)]), Rel.of(("y", "z"), [(1, 2), (4, 2)])).to_dense((5, 5))[0, 2] == 1.0


def test_forward_chaining_reaches_the_transitive_closure():
    edges = [(0, 1), (1, 2), (2, 3), (5, 6)]
    prog = Program().add("Anc", ("x", "y"), ("Par", ("x", "y"))).add("Anc", ("x", "z"), ("Anc", ("x", "y")), ("Par", ("y", "z")))
    db, passes = prog.forward_chain({"Par": Rel.of(("x", "y"), edges)})
    want = {(0, 1), (1, 2), (2, 3), (5, 6), (0, 2), (1, 3), (0, 3)}
    assert db["Anc"].facts() == want
    assert passes <= 5


def test_temperature_zero_is_the_step_function():
    x = np.array([-2.0, -1e-3, 0.0, 1e-3, 2.0])
    assert nonlin(x, 0.0).tolist() == [0, 0, 0, 1, 1]
    soft = nonlin(x, 1.0)
    assert np.all((soft > 0) & (soft < 1)) and soft[2] == 0.5
    assert np.allclose(nonlin(x[[0, 4]], 1e-3), [0, 1], atol=1e-6)


def _toy_eqs(rng):
    N, E = 7, 4
    n = rng.integers(0, N, 30)
    eqA = SparseEq("A", n[:10], rng.random(10), {}, head=("WA", rng.integers(0, 5, 10)))
    eqB = SparseEq("B", n[10:20], rng.random(10), {"WB": rng.integers(0, 3, 10)}, e=rng.integers(0, E, 10))
    eqH = SparseEq("H", n[20:], rng.random(10), {"Lag": rng.integers(0, 3, 10)}, head=("WH", rng.integers(0, 4, 10)))
    eqG = SparseEq("G", n[:10], rng.random(10), {"Lag": rng.integers(0, 3, 10), "WG": rng.integers(0, 2, 10)},
                   e=rng.integers(0, E, 10))
    P = {"WA": Param("WA", rng.normal(size=(5, E))), "WB": Param("WB", rng.normal(size=3)),
         "WH": Param("WH", rng.normal(size=(4, E))), "Lag": Param("Lag", rng.normal(size=3)),
         "WG": Param("WG", rng.normal(size=2))}
    y = rng.integers(0, E, N)
    return [eqA, eqB, eqH, eqG], P, y, N, E


def test_gradients_of_tensor_equations_match_finite_differences():
    rng = np.random.default_rng(0)
    eqs, P, y, N, E = _toy_eqs(rng)

    def loss():
        return softmax_xent(logits(eqs, P, N, E), y)[0]

    _, dL, _ = softmax_xent(logits(eqs, P, N, E), y)
    G = grads(eqs, P, dL)
    for k, p in P.items():
        base = p.value.copy()
        num = np.zeros_like(base)
        for i in range(base.size):
            for sgn in (1, -1):
                p.value = base.copy()
                p.value.flat[i] += sgn * 1e-6
                num.flat[i] += sgn * loss() / 2e-6
        p.value = base
        assert np.allclose(G[k], num, atol=1e-6), k


def test_simplex_lag_gradient_and_l1_zeros():
    rng = np.random.default_rng(1)
    eqs, P, y, N, E = _toy_eqs(rng)
    P["Lag"].simplex = True
    from rulediscovery1__fepInspired.tl.engine import simplex_grad

    def loss():
        return softmax_xent(logits(eqs, P, N, E), y)[0]

    _, dL, _ = softmax_xent(logits(eqs, P, N, E), y)
    g = simplex_grad(P["Lag"], grads(eqs, P, dL)["Lag"])
    base = P["Lag"].value.copy()
    for i in range(3):
        P["Lag"].value = base.copy(); P["Lag"].value[i] += 1e-6; a = loss()
        P["Lag"].value = base.copy(); P["Lag"].value[i] -= 1e-6; b = loss()
        assert abs((a - b) / 2e-6 - g[i]) < 1e-6
    P["Lag"].value = base
    # L1 proximal step: a weight on an uninformative feature ends exactly at zero
    n = np.arange(200)
    x_good = (n % 2).astype(float)
    y2 = (n % 2).astype(np.int64)
    rows = np.concatenate([x_good.astype(int), 2 + (n % 3 == 0)])      # rows 0/1 informative, rows 2/3 noise
    eq = [SparseEq("A", np.concatenate([n, n]), np.ones(400), {}, head=("W", rows))]
    W = {"W": Param("W", np.zeros((4, 2)), l1=0.02)}
    opt = Adam(0.1)
    for _ in range(300):
        _, dL2, _ = softmax_xent(logits(eq, W, 200, 2), y2)
        opt.step(W, grads(eq, W, dL2))
    assert np.all(W["W"].value[3] == 0) and np.abs(W["W"].value[1, 1] - W["W"].value[1, 0]) > 1.0


# ---------------------------------------------------------------- relations, learner, rule

def _play(env, actions, **cfg):
    agent = RuleDiscoveryAgent(AgentConfig(**cfg))
    agent.start_play(env.board(), ["ACTION1", "ACTION2", "ACTION3", "ACTION4", "RESET"])
    for a in actions:
        grid, lc, go = env.step(a)
        agent.observe(a, grid, lc, go)
    return agent


WALK = [RIGHT] * 6 + [UP, DOWN, LEFT, LEFT, UP, UP, DOWN] + [RIGHT] * 6 + [LEFT, UP, RIGHT, RIGHT, DOWN, RIGHT] * 3


def test_targets_and_ahead_strip_on_the_mover_world():
    env = MoverEnv(y=20, x=20, wall_x=23)
    agent = _play(env, [RIGHT], use_tl=True)
    tr_pre = agent.slow.beliefs.records[-1].tr
    t, n_app = target_effects(tr_pre.pre, tr_pre.post)
    mover = next(c for c in tr_pre.pre.objects() if c.colour == MOVER)
    assert t[mover.id] == "mv0,1" and n_app == 0
    now = agent.perceiver.current
    m2 = next(c for c in now.objects() if c.colour == MOVER)
    assert WALL in SceneRel.of(now).ahead((m2,), 0, 1)          # the wall is right ahead now
    assert WALL not in SceneRel.of(now).ahead((m2,), 0, -1)
    g = blank()
    put(g, 2, 30, 2, 2, MOVER)                               # near the top edge: a move up leaves the board
    top = Scene.from_grid(g, None)
    m3 = next(c for c in top.objects() if c.colour == MOVER)
    assert EDGE in SceneRel.of(top).ahead((m3,), -5, 0)


def _learned():
    env = MoverEnv(y=20, x=20, wall_x=30)
    return _play(env, WALK, use_tl=True, tl_templates=False), env


def test_learner_finds_arrows_and_wall_without_templates():
    agent, env = _learned()
    src = agent.tl_source
    assert src.learner.fits > 0 and not any(r.template != "tl" for h in agent.slow.beliefs.hyps for r in h.ruleset.rules())
    moves, walls, passable = src.mover(agent.slow.ctx.state.agency.tracker.controlled())
    assert moves == {"ACTION1": (-1, 0), "ACTION2": (1, 0), "ACTION3": (0, -1), "ACTION4": (0, 1)}
    assert WALL in walls
    rule = next(r for r in src.exported if r.family == "move" and r.scope == "all" and r.structure == "full")
    # a free move and a blocked move, predicted from fresh contexts on hand-made boards
    for x, expect_move in ((20, True), (28, False)):
        env2 = MoverEnv(y=20, x=x, wall_x=30)
        scene = Scene.from_grid(env2.board(), None)
        rc = agent.slow.ctx.context(scene, RIGHT)
        rc = rc.replace(agent=next(c for c in scene.objects() if c.colour == MOVER))
        eff = rule.predict(rc)
        assert eff is not None
        assert any(e.kind == "move" and (e.dx, e.dy) == (1, 0) for e in eff) == expect_move
    import dataclasses
    other = dataclasses.replace(rule, weights=rule.weights[:-1])
    assert other.key() != rule.key()


def test_learned_rule_price_is_in_template_range_and_replay_is_exact():
    agent, _ = _learned()
    dl = DLContext(n_types=3)
    rule = next(r for r in agent.tl_source.exported if r.family == "move" and r.scope == "all")
    pads = [r for r in TemplateFitter().propose(agent.slow.beliefs.records) if isinstance(r, PadMoveRule)]
    assert pads
    ratio = rule.description_length(dl) / pads[0].description_length(dl)
    assert 0.5 < ratio < 4.0, ratio
    b = agent.slow.beliefs
    for h in b.hyps:
        ll, _, _ = score_ruleset(h.ruleset, b.records, PredictionCache())
        assert math.isclose(ll, h.loglik, rel_tol=1e-9, abs_tol=1e-9), h.ruleset.describe()


def test_default_off_has_no_tensor_logic():
    env = MoverEnv(y=20, x=20)
    agent = _play(env, [RIGHT, LEFT])
    assert agent.tl_source is None and agent.slow.ctx.tl is None and agent.proposer.tl is None
    assert agent.slow.ctx.context(agent.perceiver.current, RIGHT).tl is None


# ---------------------------------------------------------------- planning

def test_forward_chaining_reach_matches_the_explorer_search():
    g = blank()
    put(g, 30, 10, 2, 2, MOVER)
    for r in range(14, 50):                                # a wall with one gap
        if r not in (30, 31):
            g[r][20] = WALL
    put(g, 12, 40, 3, 3, 9)                                 # targets
    put(g, 44, 26, 3, 3, 8)
    scene = Scene.from_grid(g, None)
    sprite = [c for c in scene.objects() if c.colour == MOVER]
    targets = [c for c in scene.objects() if c.colour in (8, 9)]
    moves = {"ACTION1": (-1, 0), "ACTION2": (1, 0), "ACTION3": (0, -1), "ACTION4": (0, 1)}
    ex = ObjectContactExplorer()
    bfs = ex.search(scene, sprite, moves, {WALL}, targets)
    fc = tl_plan.search(scene, sprite, moves, {WALL}, targets, _on, lambda c: -1)
    assert bfs is not None and fc is not None
    assert fc[1].id == bfs[1].id and len(fc[0]) == len(bfs[0])
    # the path is valid: replaying it on the sprite never enters a wall cell
    y, x = sprite[0].y0, sprite[0].x0
    for _, (dy, dx) in fc[0]:
        y, x = y + dy, x + dx
        assert g[y][x] != WALL and g[y + 1][x + 1] != WALL
