# Author: Claude Opus 5.5 (Bubba)
# Date: 25-September-2026
# PURPOSE: Tests for picks 2 and 3 of the fifth expert debate (docs 2026-09-25-openmind-agent-expert-debate-5.md, Round 7;
#   OpenMind #arc-3 25-Sep-2026 17:14 ET):
#     - pick 2, flat outcome preferences before the first clear (goals.Preferences flat_until_clear, AgentConfig.flat_prefs):
#       before any clear the most common outcome is no longer the least wanted (every ordinary outcome is 0); the fixed
#       clear / game-over preferences and the game-over aversion stay; after the first clear log_pref equals the learned
#       one of an agent that never flattened; the switch reaches the agent's Preferences;
#     - pick 3, rule library (library.RuleLibrary, AgentConfig.carry_library): a library rule costs `reuse` x its
#       description length in BeliefState.price, a new rule pays full price; snapshots keep only non-empty sets that beat
#       counts-only, deduplicated, newest first, capped; seed() re-enters a pruned set with exactly its replayed evidence;
#       temper_moves keeps each learned move but lets a few new presses overturn it;
#     - what a RESET within a level keeps (with and without the library): the rule-set posterior and its stored steps,
#       the self's learned moves, the goal beliefs; with the library a RESET is a snapshot + seed and never tempers the
#       moves, a clear tempers them.
# SRP/DRY check: Pass -- worlds and helpers from synth.py (MoverEnv, feed), test_debate_picks.py (TurnEnv) and
#   test_debate3.py (_warm, BUTTONS5); the package's own beliefs, goals, library and agent. New: the tests.
from __future__ import annotations

import math
from collections import Counter
from types import SimpleNamespace as NS

from rulediscovery1__fepInspired.agent import AgentConfig
from rulediscovery1__fepInspired.beliefs import BeliefState, score_ruleset
from rulediscovery1__fepInspired.goals import Preferences
from rulediscovery1__fepInspired.library import LibraryConfig, RuleLibrary
from rulediscovery1__fepInspired.perception import Action, Scene
from rulediscovery1__fepInspired.rules import MoveRule, NoOpRule, RuleSet
from rulediscovery1__fepInspired.tests.synth import LEFT, RIGHT, WALL, MoverEnv, feed, mover_comp
from rulediscovery1__fepInspired.tests.test_debate3 import _warm
from rulediscovery1__fepInspired.tests.test_debate_picks import TurnEnv


def _tr(label, clear=False, over=False, reset=False):
    return NS(label=label, level_completed=clear, game_over=over, reset=reset)


def _feed_prefs(p: Preferences, labels):
    for lab in labels:
        p.observe(_tr(lab, clear=lab == "level_clear", over=lab == "game_over"))


# ---------------------------------------------------------------- pick 2: flat preferences before the first clear

def test_before_a_clear_the_common_outcome_is_not_the_least_wanted():
    labels = ["nothing"] * 40 + ["move"] * 5
    old, flat = Preferences(), Preferences(flat_until_clear=True)
    _feed_prefs(old, labels)
    _feed_prefs(flat, labels)
    assert old.log_pref("nothing") < old.log_pref("move") < 0          # the self-made prior this pick removes
    assert flat.log_pref("nothing") == flat.log_pref("move") == flat.log_pref("never seen") == 0.0


def test_game_over_aversion_and_the_fixed_preferences_stay_flat_or_not():
    p = Preferences(flat_until_clear=True)
    _feed_prefs(p, ["nothing", "bump", "game_over"])
    assert p.log_pref("game_over") == p.c_game_over and p.log_pref("level_clear") == p.c_clear
    assert p.log_pref("bump") == p.c_avoid and p.log_pref("move") == 0.0


def test_after_the_first_clear_preferences_are_the_learned_ones():
    labels = ["nothing"] * 10 + ["move"] * 3 + ["level_clear"] + ["nothing"] * 4 + ["grab"] * 2
    old, flat = Preferences(), Preferences(flat_until_clear=True)
    _feed_prefs(old, labels[:13])
    _feed_prefs(flat, labels[:13])
    assert not flat.cleared and flat.log_pref("move") == 0.0
    _feed_prefs(old, labels[13:])
    _feed_prefs(flat, labels[13:])
    assert flat.cleared
    for lab in ("nothing", "move", "grab", "unseen"):
        assert math.isclose(flat.log_pref(lab), old.log_pref(lab))


def test_the_switch_reaches_the_agents_preferences():
    env = TurnEnv()
    on = _warm(AgentConfig(seed=0, use_self=True, flat_prefs=True), env)
    off = _warm(AgentConfig(seed=0, use_self=True), TurnEnv())
    assert on.slow.prefs.flat_until_clear and not off.slow.prefs.flat_until_clear
    assert on.library is None and on.slow.beliefs.library is None


# ---------------------------------------------------------------- pick 3: the rule library

def _sets(env):
    t = mover_comp(Scene.from_grid(env.board(), None)).type_key
    right = MoveRule("ACTION4", t, 1, 0, frozenset({WALL}))
    left = MoveRule("ACTION3", t, -1, 0)
    return right, left, RuleSet.of([right, left])


def test_a_library_rule_costs_less_and_a_new_rule_pays_full_price():
    env = MoverEnv(x=18, wall_x=26)
    right, left, both = _sets(env)
    b = BeliefState(dl_weight=0.25)
    full_both, full_left = b.price(both), b.price(RuleSet.of([left]))
    lib = RuleLibrary(LibraryConfig(reuse=0.5))
    lib._add(RuleSet.of([right]))
    b.library = lib
    d_right = right.description_length(b.dlc)
    assert math.isclose(b.price(both), full_both - 0.25 * 0.5 * d_right)      # only the reused rule is discounted
    assert math.isclose(b.price(RuleSet.of([left])), full_left)               # nothing reused: full price


def test_snapshot_keeps_only_sets_that_beat_counts_only_deduplicated_and_capped():
    env = MoverEnv(x=18, wall_x=26)
    right, left, both = _sets(env)
    b0 = BeliefState(dl_weight=0.25)
    lib = RuleLibrary(LibraryConfig(max_sets=2))
    assert lib.snapshot(b0, "reset", 1) == 0 and lib.sets == []              # counts-only posterior: nothing held
    b = BeliefState(dl_weight=0.25)
    b.add_rulesets([both])
    feed(env, ([RIGHT] * 8 + [LEFT] * 6) * 4, b)
    assert b.map_hypothesis().ruleset.key() == both.key()
    lib.snapshot(b, "clear", 2)
    lib.snapshot(b, "reset", 3)
    assert [s.key() for s in lib.sets] == [both.key()]                        # the same set twice: once
    lib._add(RuleSet.of([left]))
    lib._add(RuleSet.of([NoOpRule(("ACTION5",))]))
    assert len(lib.sets) == 2 and lib.sets[-1].key() == RuleSet.of([left]).key()   # newest first, capped
    assert set(lib.rules) == {r.key() for s in lib.sets for r in s.rules()}
    assert lib.events[:3] == [[1, "reset", 0, 0], [2, "clear", 1, 1], [3, "reset", 1, 1]]


def test_seed_brings_back_a_pruned_set_with_exactly_its_replayed_evidence():
    env = MoverEnv(x=18, wall_x=26)
    _, _, both = _sets(env)
    b = BeliefState(dl_weight=0.25)
    feed(env, ([RIGHT] * 8 + [LEFT] * 6) * 3, b)
    assert both.key() not in {h.ruleset.key() for h in b.hyps}
    lib = RuleLibrary()
    lib._add(both)
    assert lib.seed(b) == 1 and lib.seed(b) == 0 and lib.seeded == 1
    h = next(h for h in b.hyps if h.ruleset.key() == both.key())
    ll, fires, misses = score_ruleset(both, b.records, b.cache)
    assert h.origin == "library" and math.isclose(h.loglik, ll) and (h.fires, h.misses) == (fires, misses)


def test_tempered_moves_are_kept_but_a_few_new_presses_overturn_them():
    selfm = NS(stats={"ACTION1": Counter({(-4, 0): 60, (0, 0): 20}), "ACTION5": Counter({(0, 0): 30})})
    RuleLibrary(LibraryConfig(carry_n=4)).temper_moves(selfm)
    a1 = selfm.stats["ACTION1"]
    assert sum(a1.values()) <= 5 and a1.most_common(1)[0][0] == (-4, 0)       # still the learned move
    assert selfm.stats["ACTION5"] == Counter({(0, 0): 4})
    a1[(4, 0)] += 4                                                          # the new level: this button now goes down
    nz = Counter({d: n for d, n in a1.items() if d != (0, 0)})
    assert nz.most_common(1)[0][0] == (4, 0)


# ---------------------------------------------------------------- what a RESET within a level keeps

def _state(ag):
    s = ag.slow
    return (s.beliefs, len(s.beliefs.records), {h.ruleset.key() for h in s.beliefs.hyps},
            {b: Counter(c) for b, c in s.ctx.selfm.stats.items()}, dict(s.goals.loglik), s.goals)


def _reset(ag, env):
    ag.observe(Action("RESET"), env.board())


def test_a_reset_within_a_level_keeps_what_was_learned_with_and_without_the_library():
    for lib in (False, True):
        env = TurnEnv()
        ag = _warm(AgentConfig(seed=0, use_self=True, carry_library=lib), env)
        beliefs, n_rec, keys, stats, gl, goals = _state(ag)
        assert stats and ag.slow.ctx.selfm.dirs()                          # moves were learned in the warm-up
        _reset(ag, env)
        b2, n2, keys2, stats2, gl2, goals2 = _state(ag)
        assert b2 is beliefs and n2 == n_rec + 1 and keys <= keys2          # same posterior, its steps kept
        assert stats2 == stats and goals2 is goals and gl2 == gl            # moves (not tempered) and goal beliefs kept
        if lib:
            assert ag.library.events[-1][1] == "reset"


def test_with_the_library_a_clear_snapshots_seeds_and_tempers_the_moves():
    env = TurnEnv()
    ag = _warm(AgentConfig(seed=0, use_self=True, carry_library=True), env)
    dirs = ag.slow.ctx.selfm.dirs()
    ag.observe(Action("ACTION1"), env.board(), level_completed=True, level=1)
    assert ag.library.events[-1][1] == "clear"
    assert ag.slow.ctx.selfm.dirs() == dirs                                  # the same moves, as a starting belief
    assert all(sum(c.values()) <= ag.library.cfg.carry_n + len(c) for c in ag.slow.ctx.selfm.stats.values())
    lib_keys = {s.key() for s in ag.library.sets}
    assert lib_keys <= {h.ruleset.key() for h in ag.slow.beliefs.hyps}      # seeded (pruning comes at the next proposal)
