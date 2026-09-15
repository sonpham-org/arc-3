<!--
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: The ls20 game mechanic behind the Boss's 7-level win -- three lives PER LEVEL, a step
budget that is not the number it appears to be, and a RESET that refills both. Source-verified
against docs/static/games/src/ls20-9607627b/ls20.py and confirmed against all 562 rows of
7537433d-75af-48fa-ad3d-45fd32b23c00. Written because first-party-replays.json's ls20
attribution cites it and because the step-budget half was not written down anywhere.
SRP/DRY check: Pass -- the HARNESS defect that pairs with this (solver.py filtering RESET out of
the model's action menu) is NOT restated here; it is owned by the 2026-09-15 evening-session
CHANGELOG entry and this file cites it in section 4 rather than duplicating it.
2026-09-15-bp35-undo-costs-a-move.md owns bp35's budget arithmetic and
2026-09-15-lp85-step-budget-and-the-uncitable-reset.md owns lp85's; this owns ls20's.
-->

# ls20: three lives a level, a 42 that is often 21, and a RESET that refills both

**Status:** finding, 15-Sep-2026. Mechanic read from
`docs/static/games/src/ls20-9607627b/ls20.py` (2,042 lines) and confirmed against all 562 rows
of `7537433d-75af-48fa-ad3d-45fd32b23c00`, the Boss's WIN — 7 levels, 561 actions, 3 resets,
score 100.

Every line number below was opened and checked in this tree. Where a citation in the brief that
prompted this was wrong, section 5 says which and how.

---

## 1. Lives are per LEVEL, not per run

| what | where | what it says |
|---|---|---|
| lives are set to 3 | `ls20.py:1821` | `self.aqygnziho = 3` |
| …inside the per-level hook | `ls20.py:1778` | `def on_set_level(self, level: Level) -> None:` |
| running the budget out | `ls20.py:1950` | `bkuguqrpvq = not yubyobdoss and (not self._step_counter_ui.mfyzdfvxsm())` |
| …costs one life | `ls20.py:1961` | `self.aqygnziho -= 1`, inside `Ls20.step` (`:1890`) |
| the third one ends the run | `ls20.py:1962-1963` | `if self.aqygnziho == 0:` then `self.lose()` |

`self.aqygnziho = 3` sits in `on_set_level`, so **every level starts with a fresh three**. A
life is spent only on the `bkuguqrpvq` branch — budget exhaustion — and the run ends when the
count reaches zero, not when it goes negative.

**Rendered as three pips.** Frame row 61, columns 56, 59 and 62; colour 8 for a live pip and
colour 3 (background) for a spent one. Measured across all 562 frames of the recording, those
three cells take exactly three states and nothing else:

| pips at row 61, x=56/59/62 | rows |
|---|---|
| `(8, 8, 8)` — three lives | 419 |
| `(8, 8, 3)` — two | 140 |
| `(8, 3, 3)` — one | 3 |

`(3, 3, 3)` never occurs, which is the same fact as the recording carrying **zero `GAME_OVER`
rows**: the player never spent a third life. Two independent readings of the same run agree.

## 2. RESET refills the lives, and the run shows it

`RESET` is engine-level. The chain, in the vendored engine (see
[`vendor/README.md`](../../vendor/README.md) for why it can be cited at all):

`base_game.py:205` intercepts RESET → `:305` `handle_reset` → `:326` `level_reset` →
`:328` `set_level` → `:164` `self.on_set_level(level)`.

The hook is **re-entered, not patched**, so `ls20.py:1821` runs again and the lives go back to
three — along with the step meter, which `on_set_level` also rebuilds.

**Observed, not inferred.** Tracking the pips through the recording:

| row | action | level | lives | what happened |
|---|---|---|---|---|
| 36 | ACTION2 | 1 | 3 → 2 | budget exhausted |
| 81 | ACTION2 | 2 | 2 → 3 | level advance re-runs the hook |
| 135 | RESET | 3 | 3 → 3 | reset at full lives |
| 225 | ACTION3 | 4 | 3 → 2 | budget exhausted |
| 277 | ACTION1 | 5 | 2 → 3 | level advance |
| 408 | ACTION2 | 6 | 3 → 2 | budget exhausted |
| 451 | ACTION2 | 6 | 2 → 1 | budget exhausted — one life left |
| **454** | **RESET** | **6** | **1 → 3** | **reset refills to three, same level** |
| 482 | RESET | 6 | 3 → 3 | reset at full lives |

Row 454 is the whole mechanic in one row: one life left, RESET pressed, three lives back,
`levels_completed` unchanged. That is `level_reset` re-entering `on_set_level`, measured.

**This is why the run has 3 resets and no deaths.** All three resets were taken on a live board.
`RESET` here is not recovery-from-death at all — it is a *life refill* bought at the cost of
restarting the level's arrangement, which is a different trade from the one `bp35` and `lp85`
offer.

## 3. The "42-step budget" is 42 on three levels and 21 on four

All seven levels declare `"StepCounter": 42`. That is not the number of moves.

The meter drains by `StepsDecrement`, which **defaults to 2** —
`ls20.py:1771`, `efipnixsvl = 2 if hgkhqetaxy is None else hgkhqetaxy`, where `hgkhqetaxy` is
`self.current_level.get_data("StepsDecrement")` (`:1770`). Only three levels override it to 1,
at `ls20.py:724`, `:1088` and `:1324`.

Read by **parsing the level objects**, not by reading line proximity in `LEVELS_SPEC` — that is
the partial-read mistake `AGENTS.md` warns about, and it would get the mapping wrong:

| level | StepCounter | StepsDecrement | effective moves |
|---|---|---|---|
| 1 | 42 | 1 | **42** |
| 2 | 42 | *absent → 2* | **21** |
| 3 | 42 | *absent → 2* | **21** |
| 4 | 42 | 1 | **42** |
| 5 | 42 | *absent → 2* | **21** |
| 6 | 42 | 1 | **42** |
| 7 | 42 | *absent → 2* | **21** |

Reproduce it:

```python
import sys; sys.path.insert(0, "docs/static/games/src/ls20-9607627b")
import ls20
for i, l in enumerate(ls20.levels, 1):
    sd = l.get_data("StepsDecrement")
    print(i, l.get_data("StepCounter"), sd, l.get_data("StepCounter") / (2 if sd is None else sd))
```

**Why it matters for labelling.** A record whose `expected_observation` says "there are 42 moves
on this level" is wrong on four of the seven, and an agent reasoning from the on-screen counter
is reading a bar that moves twice as fast as it expects on a majority of levels. The counter is
honest; the *unit* is not one move.

## 4. The harness half — not restated here

This mechanic pairs with a defect in our own harness: `_engine_action_names()` filters `RESET`
out of the `valid_actions` menu the model is shown, so on a game whose only recovery and
life-refill primitive is `RESET`, our agent cannot press it.

**That finding is written up in the `CHANGELOG.md` entry "Evening session: five human wins, and
a harness defect that says the agent cannot press RESET", and is not duplicated here.** Two
things about it were checked in this tree while writing this file and both hold: the filter is
at `solver.py:171-172` inside `_engine_action_names` (`:164`), feeding `valid_actions` at `:692`
and `:928` and rendered at `agent/tool_agent.py:1408`; and the only `RESET` the harness issues
is `_execute_auto_reset()` (`:825-827`), fired at `:351` only once
`_is_engine_game_over(self.game)` is already true.

**No harness code was changed by this file and none should be on the strength of it.** That is
the Boss's and Dr. Fable's call.

## 5. Corrections to the citations this file was asked to check

Three of the line numbers handed to me were off. Checked one by one:

| claim as given | verdict |
|---|---|
| `ls20.py:1821` `aqygnziho = 3` in `on_set_level` | **holds** exactly |
| `:1950`, `:1961` budget exhaustion costs a life | **holds** exactly |
| `:1962` "the third calls `lose()`" | **off by one.** `:1962` is the test `if self.aqygnziho == 0:`; the `lose()` call is `:1963`. Cited as `:1962-1963` above |
| `:1771` `StepsDecrement` default 2, overridden at `:724`, `:1088`, `:1324` | **holds**, and the levels those map to are 1, 4 and 6, confirmed by parsing rather than by proximity |
| pips at row 61, x=56/59/62, colour 8 | **holds**, confirmed against all 562 frames |
| harness filter at `solver.py:170-171` | **off by one.** `:170` is the `continue` of the `except`; the RESET filter is `:171-172` |
| "`:752` would reject a RESET anyway" | **wrong, and it matters.** `taaf/game.py:188-193` defines `available_actions` as "Legal action ids, with RESET (0) always present" and re-adds `0` unconditionally, so the membership check at `:752` passes. It is **one filter, not two gates** — which makes the proposed fix a one-place change rather than two. The correction originated with Sherlock; it is recorded here because it was re-derived independently in this tree before being accepted |
