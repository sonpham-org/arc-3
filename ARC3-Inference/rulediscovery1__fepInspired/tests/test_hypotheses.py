# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Tests (written, NOT run) for rulediscovery1__fepInspired/hypotheses.py on synthetic worlds: a mover
#   hitting a wall (MoveRule with the wall colour as blocker), a click toggle (ClickToggleRule both
#   ways), a timer every two presses (CounterRule period 2), and the beam builder preferring the true
#   rule set over counts only.
# SRP/DRY check: Pass -- fixtures from synth.py.
from __future__ import annotations

from rulediscovery1__fepInspired.beliefs import BeliefState
from rulediscovery1__fepInspired.hypotheses import HypothesisProposer, TemplateFitter
from rulediscovery1__fepInspired.rules import ClickToggleRule, CounterRule, MoveRule, PadMoveRule, RuleSet
from rulediscovery1__fepInspired.tests.synth import LEFT, RIGHT, WALL, MoverEnv, ToggleEnv, feed


def test_fits_mover_blocked_by_wall():
    env = MoverEnv(x=20, wall_x=26)                     # four free moves, then the wall
    b, _, _, trs = feed(env, [RIGHT] * 8)
    assert [t.label for t in trs] == ["mv+1+0"] * 4 + ["nothing"] * 4
    rules = TemplateFitter().propose(b.records)
    moves = [r for r in rules if isinstance(r, MoveRule) and r.action == "ACTION4"]
    assert moves and (moves[0].dx, moves[0].dy) == (1, 0) and WALL in moves[0].blockers


def test_fits_click_toggle_both_ways():
    env = ToggleEnv()
    b, _, _, trs = feed(env, [env.click_tile()] * 5)
    assert [t.label for t in trs] == ["rc9>8", "rc8>9", "rc9>8", "rc8>9", "rc9>8"]
    toggles = {(r.from_colour, r.to_colour) for r in TemplateFitter().propose(b.records)
               if isinstance(r, ClickToggleRule)}
    assert {(9, 8), (8, 9)} <= toggles


def test_fits_timer_every_second_press():
    env = MoverEnv(timer_every=2)
    b, _, _, trs = feed(env, [RIGHT] * 8)
    assert [t.label for t in trs[:2]] == ["mv+1+0", "grow|mv+1+0"]
    counters = [r for r in TemplateFitter().propose(b.records) if isinstance(r, CounterRule)]
    assert any(c.parts == ("grow",) and c.period == 2 for c in counters)


def test_builder_composes_the_wall_rule():
    # Right x8 then left x6 between x=18 and a wall: the last two right presses of every cycle are
    # blocked. dl_weight = 0 isolates the composition from the prior: a rule set that is right every
    # time it speaks has p = (1 - eps) + eps p_b >= p_b at every step, so adding the always-correct
    # wall rule strictly raises the score and the beam must keep it. (Whether rules beat counts-only
    # at a real prior price is measured by offline_eval, not asserted here.)
    env = MoverEnv(x=18, wall_x=26)
    b = BeliefState(dl_weight=0.0)
    feed(env, ([RIGHT] * 8 + [LEFT] * 6) * 4, b)
    b.add_rulesets(HypothesisProposer().propose(b))
    b.reduce()
    best = b.map_hypothesis()
    # the right-mover may come as its own MoveRule or inside a d-pad rule (PadMoveRule, 23-Sep-2026)
    right = [r for r in best.ruleset.rules() if isinstance(r, MoveRule) and r.action == "ACTION4"]
    right += [m for r in best.ruleset.rules() if isinstance(r, PadMoveRule)
              for m in [r.as_move("ACTION4")] if m is not None]
    assert right and WALL in right[0].blockers and (right[0].dx, right[0].dy) == (1, 0)
    empty = next(h for h in b.hyps if h.ruleset.key() == RuleSet.empty().key())
    assert best.log_score >= empty.log_score
