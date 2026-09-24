# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Tests (written, NOT run) for rulediscovery1__fepInspired/rules.py: MoveRule free / blocked / unknown
#   obstacle (silent), ClickToggleRule, CounterRule phase, PersistRule mapping, the RuleSet decision
#   list with additive modifiers (and silence when only a modifier fires), CodeRule sandboxing, and
#   the stub language-model provider.
# SRP/DRY check: Pass -- fixtures from synth.py.
from __future__ import annotations

from rulediscovery1__fepInspired.perception import Scene
from rulediscovery1__fepInspired.rules import (ClickToggleRule, CodeRule, ContextBuilder, CounterRule, MoveRule, NoOpRule,
                                 PersistRule, RuleSet, StubLLMRuleProvider, advance_since)
from rulediscovery1__fepInspired.tests.synth import MOVER, RIGHT, UP, WALL, MoverEnv, ToggleEnv, mover_comp


def _ctx(scene, action, **kw):
    return ContextBuilder().context(scene, action, **kw)


def _move_rule(scene, blockers=frozenset({WALL})):
    return MoveRule("ACTION4", mover_comp(scene).type_key, 1, 0, frozenset(blockers))


def test_move_rule_free_space_moves():
    scene = Scene.from_grid(MoverEnv().board(), None)
    eff = _move_rule(scene).predict(_ctx(scene, RIGHT))
    assert len(eff) == 1 and eff[0].kind == "move" and (eff[0].dx, eff[0].dy) == (1, 0)
    assert _move_rule(scene).predict(_ctx(scene, UP)) is None          # other button: silent


def test_move_rule_blocked_by_wall_predicts_nothing():
    scene = Scene.from_grid(MoverEnv(x=24, wall_x=26).board(), None)   # piece on cols 24-25, wall at 26
    assert _move_rule(scene).predict(_ctx(scene, RIGHT)) == []


def test_move_rule_unknown_obstacle_is_silent():
    scene = Scene.from_grid(MoverEnv(x=24, wall_x=26).board(), None)
    assert _move_rule(scene, blockers=frozenset()).predict(_ctx(scene, RIGHT)) is None


def test_click_toggle():
    env = ToggleEnv()
    scene = Scene.from_grid(env.board(), None)
    tile = scene.comp_at(*env.TILE)
    rule = ClickToggleRule(tile.shape, 9, 8)
    eff = rule.predict(_ctx(scene, env.click_tile()))
    assert eff and eff[0].label_part() == "rc9>8"
    assert rule.predict(_ctx(scene, env.click_other())) is None


def test_counter_rule_phase():
    # counters come from advance_since, exactly as ContextBuilder.observe produces them: a tick on
    # step t, nothing on t+1, a tick again on t+2 (period 2, the gap fit_counters measures)
    scene = Scene.from_grid(MoverEnv().board(), None)
    rule = CounterRule(("grow",), 2, "any")
    assert rule.predict(_ctx(scene, RIGHT, since={})) is None                   # no phase yet
    after_tick = advance_since({}, RIGHT, ["grow", "mv+1+0"])
    assert rule.predict(_ctx(scene, RIGHT, since=after_tick)) == []            # step t+1: quiet
    after_quiet = advance_since(after_tick, RIGHT, ["mv+1+0"])
    assert [e.label_part() for e in rule.predict(_ctx(scene, RIGHT, since=after_quiet))] == ["grow"]


def test_persist_rule_mapping():
    scene = Scene.from_grid(MoverEnv().board(), None)
    rule = PersistRule("last", (("nothing", "rc1>5"), ("rc1>5", "nothing")))
    assert [e.label_part() for e in rule.predict(_ctx(scene, RIGHT, last_label="nothing"))] == ["rc1>5"]
    assert rule.predict(_ctx(scene, RIGHT, last_label="rc1>5")) == []
    assert rule.predict(_ctx(scene, RIGHT, last_label="mv+1+0")) is None


def test_ruleset_decision_list_and_modifiers():
    scene = Scene.from_grid(MoverEnv().board(), None)
    rs = RuleSet.of([NoOpRule(("ACTION4",)), _move_rule(scene), CounterRule(("grow",), 2, "any")])
    assert rs.primaries[0].template == "move"                     # specific before general
    pred = rs.predict(_ctx(scene, RIGHT, since={("any", "grow"): 1}))
    assert pred.label == "grow|mv+1+0"
    # only the modifier would fire for UP: a rule set makes no claim then
    assert rs.predict(_ctx(scene, UP, since={("any", "grow"): 1})) is None


def test_code_rule_errors_are_silence_and_stub_provider_is_empty():
    scene = Scene.from_grid(MoverEnv().board(), None)

    def bad(view):
        raise ValueError("model-written bug")

    def good(view):
        return ["mv+1+0"] if view["action"] == "ACTION4" else None

    assert CodeRule("bad", "def bad(view): raise ValueError", bad).predict(_ctx(scene, RIGHT)) is None
    ok = CodeRule("good", "def good(view): ...", good)
    assert [e.label_part() for e in ok.predict(_ctx(scene, RIGHT))] == ["mv+1+0"]
    assert ok.description_length(None) > 0
    assert StubLLMRuleProvider().propose("summary") == []
    assert MOVER == mover_comp(scene).colour
