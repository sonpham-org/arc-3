<!--
Author: Claude Opus 5 (Bubba)
Date: 15-September-2026
PURPOSE: Two things the lp85 labelling pass produced. (1) The game's loss condition is a
per-level STEP BUDGET, source-verified and confirmed against all 416 rows of the Boss's win --
which makes lp85 the second game after bp35 whose recovery economics are actually measured
rather than assumed. (2) A blocker: six of the seven decision-step records that pass wanted are
RESET steps, and the schema's action_role_source pattern cannot express a citation for RESET on
a game that does not vendor a RESET branch. The records are carried here verbatim because
.candidate.jsonl is gitignored and they would otherwise be lost. NOTHING was overridden and no
schema or tool was changed -- the standing rule is to stop and report, and this is the report.
SRP/DRY check: Pass -- 2026-09-15-bp35-undo-costs-a-move.md owns bp35's budget arithmetic and
2026-09-15-undo-is-not-a-platform-default.md owns the ACTION7 survey. This owns lp85's budget
and one schema limitation; it cites both rather than restating either. The undo doc's section 4
listed lp85's recovery economics as explicitly not measured. They are measured here.
-->

# lp85: the budget is the board, and its RESET cannot be cited

**Status:** finding plus a blocker, 15-Sep-2026. Mechanic read from
`docs/static/games/src/lp85-305b61c3/lp85.py` and confirmed against all 416 rows of
`129ddf21-d7ba-4ca0-9577-0cea2af042b6`. The blocker is reproduced below with the real
`validate.py` output.

---

## 1. The mechanic: a per-level step budget, drawn in column 0

`lp85` has one action (`ACTION6`, a click) and one way to lose: **run out of steps on a level.**
There is no hazard, no enemy and no fatal cell.

| what | where | what it says |
|---|---|---|
| the loss test | `lp85.py:21416` | `if not self.toxpunyqe.xsfawdkqoi(): self.lose()` |
| the counter | `lp85.py:21282-21284` | `if self.current_steps > 0: self.current_steps -= 1` then `return self.current_steps > 0` |
| the no-op guard | `lp85.py:21409` | `if not vctdsvnwjd: self.complete_action(); return` — a click that hit no button returns **before** the counter is reached |
| the win test, checked first | `lp85.py:21412` | `if self.khartslnwa(): self.next_level()` |
| budget per level | `lp85.py:21333-21338` | `izmredwten()` reads `StepCounter` off the level and calls `xkzycpirhl()` (`lp85.py:21287`) |
| refill on RESET | `lp85.py:21340-21342` | `on_set_level` calls `izmredwten()` at `:21342`, so re-entering the level restores it |
| the rendered bar | `lp85.py:21277` builds it from `lp85.py:21294-21300` | the display's cells are `(0, y)` for `y` in `range(0, 64)` — column 0, 64 cells |

Two consequences follow from the source alone and both are observable:

- **`xsfawdkqoi` decrements and then tests**, so the step that takes the counter to zero *is*
  the losing step. There is no state between "one step left" and `GAME_OVER`.
- **The win test runs before the loss test** (`:21412` before `:21416`), so a final click that
  completes the level clears it even if it would otherwise have emptied the budget.

### Confirmed against the recording, not inferred

Column 0 of `data.frame[-1]` is a 64-cell bar: colour `14` is budget remaining, colour `5` is
budget spent.

**It is PROPORTIONAL, not one cell per step**, and that correction is recorded here because an
earlier draft of this document claimed one cell per effective click as a general rule. It is not.
`izmredwten` (`lp85.py:21333-21338`) reads a per-level `StepCounter`, and the bar renders the
consumed *fraction* of it across 64 cells, so the cells-per-click figure is `64 / StepCounter`
for that level. Measured over every `ACTION6` in the run that neither changed level nor followed
a RESET:

| playing level | cells the bar advanced per effective click | reading |
|---|---|---|
| 1 | 5 (×5 clicks) | budget ≈ 13 steps |
| 2 | 1 (×21), 2 (×1) | budget ≈ 64, the 2 is rounding |
| 3–8 | 1 | budget 64 |

So "one cell per click" is true on levels 2–8 of this run and **false on level 1**. Everything
below is measured on levels 6 and 8, where the mapping is 1:1 and the cell count can be read as
a step count directly.

Measured across the run:

| observation | rows | measured |
|---|---|---|
| bar full at level start | 95 (level 6), 253 (level 8) | 0 of 64 cells consumed |
| one cell per **effective** click (level 6, 1:1 there) | 168–174 | 58 → 59 → 60 → 61 → 62 → 62 → 63 |
| a no-op click does not advance it | 172 → 173 | 62 → 62, an `ACTION6` at (54,55) that hit nothing |
| the last step is the losing step | 174 → 175 | 63 → 64 consumed, `NOT_FINISHED` → `GAME_OVER` |
| RESET refills it completely | 176, 269, 294, 311, 365, 386 | every one → 0 of 64 consumed |
| no-ops are common | level 6, rows 95–198 | 101 `ACTION6` of which **20 advanced nothing** |
| and on level 8 too | rows 253–415 | 157 `ACTION6` of which **34 advanced nothing**; every other one advanced exactly 1 |

That last line is worth stating on its own: **a fifth of the player's clicks on level 6 did
nothing at all**, and the game gave no signal distinguishing them from effective ones except the
bar not moving. The bar is the only feedback channel for whether an action was an action.

### What it does to the five level-8 resets

Rows 269, 294, 311, 365 and 386 are RESETs on a live board with no death before any of them. The
bar at the row before each: **11, 19, 13, 42 and 16 of 64 consumed.** None is near exhaustion.

So these are **not** budget-driven resets. They are plans abandoned as unwinnable, on a game
where RESET is the only way to unwind an arrangement because there is no undo — see
[`2026-09-15-undo-is-not-a-platform-default.md`](2026-09-15-undo-is-not-a-platform-default.md).
The refilled budget is a side effect the player collected, not the reason.

### Against bp35

[`2026-09-15-bp35-undo-costs-a-move.md`](2026-09-15-bp35-undo-costs-a-move.md) measured that on
`bp35` an error costs a move, undoing it costs another, and RESET refunds the whole level budget.
**lp85 is the second game where that arithmetic is now measured, and it comes out the same way
on the half it shares:** RESET refunds the entire budget, at no step cost. The half bp35 has and
lp85 does not is undo — so on lp85 the "prefer undo over RESET" rule has nothing to rank.

The undo survey listed lp85's recovery economics under *"Not measured."* This measures them. Its
section 4 has been updated to point here rather than to keep claiming otherwise.

---

## 2. The blocker: RESET on lp85 has no citable source line

### What was run

`tools/segment.py` (pass A) on seven rows — the death pair, and the five level-8 resets — with
only the judgment fields filled by hand afterwards. No mechanical field was touched.

```
python3.13 tools/segment.py --game-id lp85-305b61c3 \
  --guid 129ddf21-d7ba-4ca0-9577-0cea2af042b6 --rows 175:176 \
  --segment-prefix lp85-l6-death-reset --stdout
python3.13 tools/segment.py ... --rows 269:269 --segment-prefix lp85-l8-abandon-269 --stdout
# ... and likewise for rows 294, 311, 365, 386
```

The segmenter does not refuse the windows. It emits, for every `RESET` row:

```
UNCITABLE: RESET has no dispatch branch in docs/static/games/src/lp85-305b61c3/lp85.py
 - see unhandled_actions in datasets/decision-steps/dispatch/lp85-305b61c3.json
```

which is correct and honest. `Lp85.step` has exactly one branch, `ACTION6` at `lp85.py:21374`.
`RESET` is handled by `arcengine`, which is **not vendored in this repo** —
`datasets/decision-steps/dispatch/lp85-305b61c3.json`'s `unhandled_actions.note` already said so
before this pass.

### What validate.py says

Run against the annotated candidates in a scratch directory, since the finished-episode
directory is not where an invalid record belongs:

```
/tmp/lp85/death.candidate.annotated.jsonl:2: $.action_role_source: "UNCITABLE: RESET has no dispatch branch in docs/static/games/src/lp85-305b61c3/lp85.py - see unhandled_actions in datasets/decision-steps/dispatch/lp85-305b61c3.json" does not match the required pattern ^[^\s:]+:[0-9]+([ \t].*)?$
/tmp/lp85/abandon.candidate.annotated.jsonl:1: $.action_role_source: "UNCITABLE: RESET has no dispatch branch in docs/static/games/src/lp85-305b61c3/lp85.py - see unhandled_actions in datasets/decision-steps/dispatch/lp85-305b61c3.json" does not match the required pattern ^[^\s:]+:[0-9]+([ \t].*)?$
/tmp/lp85/abandon.candidate.annotated.jsonl:2: $.action_role_source: "UNCITABLE: RESET has no dispatch branch in docs/static/games/src/lp85-305b61c3/lp85.py - see unhandled_actions in datasets/decision-steps/dispatch/lp85-305b61c3.json" does not match the required pattern ^[^\s:]+:[0-9]+([ \t].*)?$
/tmp/lp85/abandon.candidate.annotated.jsonl:3: $.action_role_source: "UNCITABLE: RESET has no dispatch branch in docs/static/games/src/lp85-305b61c3/lp85.py - see unhandled_actions in datasets/decision-steps/dispatch/lp85-305b61c3.json" does not match the required pattern ^[^\s:]+:[0-9]+([ \t].*)?$
/tmp/lp85/abandon.candidate.annotated.jsonl:4: $.action_role_source: "UNCITABLE: RESET has no dispatch branch in docs/static/games/src/lp85-305b61c3/lp85.py - see unhandled_actions in datasets/decision-steps/dispatch/lp85-305b61c3.json" does not match the required pattern ^[^\s:]+:[0-9]+([ \t].*)?$
/tmp/lp85/abandon.candidate.annotated.jsonl:5: $.action_role_source: "UNCITABLE: RESET has no dispatch branch in docs/static/games/src/lp85-305b61c3/lp85.py - see unhandled_actions in datasets/decision-steps/dispatch/lp85-305b61c3.json" does not match the required pattern ^[^\s:]+:[0-9]+([ \t].*)?$
2 file(s), 7 record(s), 6 error(s) | FRAME-REF RESOLUTION: ON (/Users/macmini/GitHub/arc-3/datasets/decision-steps/v0/recordings)
```

`schema.json`'s `action_role_source` is `"pattern": "^[^\\s:]+:[0-9]+([ \\t].*)?$"` — a path,
a colon, a line number. There is no spelling of *"engine-level, source not in this repo"* that
the pattern admits. The field is required on every record. So the records cannot be written, and
the only ways to write them are to hand-edit the segmenter's output or to widen the schema.
**Neither was done.** The standing rule for this work is to stop and report rather than bend the
tool, and the six records below are the report.

### This is not an lp85 quirk — it is a coverage bias in the corpus

The one RESET record that exists today,
`bp35-0a0ad940__c935ca1b-…__l5-death-undo-reset-00.jsonl` row 216, validates only because
`bp35` *happens* to carry its own `GameAction.RESET` branch at `bp35.py:4529`. That is a property
of one game's source, not of RESET.

Put beside the undo survey, it composes into something worse than an inconvenience:

- On **19 of the 25 live builds** there is no `ACTION7`, so **RESET is the only recovery
  primitive there is**.
- Recovery after falsification is **the metric this whole corpus exists to move**
  (`CHANGELOG.md`, "Where this stands").
- But a recovery step can only be labelled on a build that happens to vendor a RESET branch.

So the corpus can currently record recovery **only on the games least representative of how
recovery works on this platform**. That is a selection effect in the dataset, introduced by a
regex, and it should be decided deliberately rather than discovered later as a skew.

### Options, not a recommendation

Listed for whoever owns the call. **None is implemented here.**

1. **Relax the pattern** to admit a sentinel form (e.g. `engine:RESET` with prose), accepting
   that `action_role_source` no longer always resolves to a readable line.
2. **Add a second citation class** — allow a citation into
   `datasets/decision-steps/dispatch/<game_id>.json:<line>` for engine-level actions, so the
   claim still points at a checked artefact in this repo, just not at game source.
3. **Vendor the engine**, which makes the problem disappear and is the largest change.
4. **Accept it** and record that RESET steps are unlabelable except on builds that dispatch
   RESET themselves — in which case the bias above belongs in `SCHEMA.md` and the README, stated
   rather than implicit.

Option 1 or 2 would need a `schema_version` decision: `schema.json`'s own note says adding a
value to a closed enum does not bump it but retyping a field does, and relaxing a `pattern` is
neither case as written.

---

## 3. The six records that cannot land, carried verbatim

`*.candidate.jsonl` is gitignored (`.gitignore:39`) and `validate.py` does not collect it from a
directory walk, so writing these as candidates would have left no durable trace. They are
reproduced here exactly as the segmenter emitted them plus the hand-filled judgment fields —
`action_role_source` included, unmodified, so the blocker is visible in the artefact rather than
only described.

Row 176 is the correction half of the pair the labelling pass was asked for. Rows 269, 294, 311,
365 and 386 are the five level-8 abandonments.

```jsonl
{"schema_version": "0.1", "game_id": "lp85-305b61c3", "source": {"kind": "human_replay", "recording_guid": "129ddf21-d7ba-4ca0-9577-0cea2af042b6", "row_index": 176}, "segment": {"id": "lp85-l6-death-reset-01", "boundary_reason": "death"}, "level": 5, "frame_ref": {"recording_guid": "129ddf21-d7ba-4ca0-9577-0cea2af042b6", "row_index": 175, "field": "data.frame"}, "ascii": null, "last_action": {"action": "ACTION6", "args": {"row": 30, "col": 45}}, "last_result": {"board_changed": true, "level_changed": false}, "decision": {"memory_out": {"known_mechanics": ["spending the final step of the budget ends the run outright -- there is no warning state between 'one step left' and GAME_OVER"]}, "action": {"action": "RESET"}, "rationale": "the board is dead and this game declares available_actions [6], so no undo exists to step back the losing click; RESET re-runs the level setup, which is the only path from GAME_OVER back to play", "expected_observation": "state returns to NOT_FINISHED on the same level -- levels_completed stays 5 -- and the column-0 bar returns to 0 of 64 cells consumed"}, "outcome": {"observed": "328 cells changed between the settled frame of row 175 and that of row 176; state GAME_OVER -> NOT_FINISHED; levels_completed 5 -> 5; painted cells 4096 -> 4096; the row carries 1 frames against 1 on row 175", "expectation_held": true}, "action_role_source": "UNCITABLE: RESET has no dispatch branch in docs/static/games/src/lp85-305b61c3/lp85.py - see unhandled_actions in datasets/decision-steps/dispatch/lp85-305b61c3.json", "rationale_provenance": "annotated", "tier": "gold", "memory_in": {"known_mechanics": ["ACTION6 is the only action this game offers; available_actions is [6] on every row", "ACTION6 is a click -- action_input.data carries {game_id, x, y}", "a click only does something when it lands on a sprite whose first tag contains 'button'; any other click is a total no-op", "the 64-cell bar in column 0 of the frame renders the consumed FRACTION of the level's step budget: it advances only on an effective click, never on a click that hit no button, and it advances by 64/StepCounter cells -- 1 cell per click on this level, but 5 on level 1, so cells are steps only where the level's budget is 64", "RESET restores the level's opening arrangement and refills the step budget bar to zero cells consumed"], "tested_actions": ["ACTION6", "RESET"], "hypotheses": ["the level clears when every marker sits on its goal cell, and pressing a button shifts a whole row or column of pieces at once"], "goal": "get back onto a live board on this level", "current_plan": "recover from the dead board; lp85 offers no undo, so RESET is the only move left"}, "action_role": "the only recovery primitive this game has: restores the level's opening arrangement and refills the step budget"}
{"schema_version": "0.1", "game_id": "lp85-305b61c3", "source": {"kind": "human_replay", "recording_guid": "129ddf21-d7ba-4ca0-9577-0cea2af042b6", "row_index": 269}, "segment": {"id": "lp85-l8-abandon-269-00", "boundary_reason": "episode_start"}, "level": 7, "frame_ref": {"recording_guid": "129ddf21-d7ba-4ca0-9577-0cea2af042b6", "row_index": 268, "field": "data.frame"}, "ascii": null, "last_action": {"action": "ACTION6", "args": {"row": 24, "col": 54}}, "last_result": {"board_changed": true, "level_changed": false}, "decision": {"memory_out": {"current_plan": "rebuild this level's arrangement from the opening layout on a different ordering of button presses"}, "action": {"action": "RESET"}, "rationale": "the board is alive and the bar shows only 11 of 64 steps consumed, so this is not budget pressure -- the arrangement reached from here cannot be finished, and RESET is the only way to unwind it because lp85 has no undo", "expected_observation": "state stays NOT_FINISHED, levels_completed stays 7, and the column-0 bar returns to 0 of 64 cells consumed from 11"}, "outcome": {"observed": "59 cells changed between the settled frame of row 268 and that of row 269; state NOT_FINISHED -> NOT_FINISHED; levels_completed 7 -> 7; painted cells 4096 -> 4096; the row carries 1 frames against 1 on row 268", "expectation_held": true}, "action_role_source": "UNCITABLE: RESET has no dispatch branch in docs/static/games/src/lp85-305b61c3/lp85.py - see unhandled_actions in datasets/decision-steps/dispatch/lp85-305b61c3.json", "rationale_provenance": "annotated", "tier": "gold", "memory_in": {"known_mechanics": ["ACTION6 is the only action this game offers; available_actions is [6] on every row", "ACTION6 is a click -- action_input.data carries {game_id, x, y}", "a click only does something when it lands on a sprite whose first tag contains 'button'; any other click is a total no-op", "the 64-cell bar in column 0 of the frame renders the consumed FRACTION of the level's step budget: it advances only on an effective click, never on a click that hit no button, and it advances by 64/StepCounter cells -- 1 cell per click on this level, but 5 on level 1, so cells are steps only where the level's budget is 64", "RESET restores the level's opening arrangement and refills the step budget bar to zero cells consumed"], "tested_actions": ["ACTION6", "RESET"], "hypotheses": ["the level clears when every marker sits on its goal cell, and pressing a button shifts a whole row or column of pieces at once"], "goal": "clear this level's arrangement before the column-0 step bar fills", "current_plan": "abandon the arrangement built so far on this level and start it again from the opening layout"}, "action_role": "plan abandonment on a live board -- RESET used to unwind an arrangement rather than to recover from a death"}
{"schema_version": "0.1", "game_id": "lp85-305b61c3", "source": {"kind": "human_replay", "recording_guid": "129ddf21-d7ba-4ca0-9577-0cea2af042b6", "row_index": 294}, "segment": {"id": "lp85-l8-abandon-294-00", "boundary_reason": "episode_start"}, "level": 7, "frame_ref": {"recording_guid": "129ddf21-d7ba-4ca0-9577-0cea2af042b6", "row_index": 293, "field": "data.frame"}, "ascii": null, "last_action": {"action": "ACTION6", "args": {"row": 58, "col": 36}}, "last_result": {"board_changed": true, "level_changed": false}, "decision": {"memory_out": {"current_plan": "rebuild this level's arrangement from the opening layout on a different ordering of button presses"}, "action": {"action": "RESET"}, "rationale": "the board is alive and the bar shows only 19 of 64 steps consumed, so this is not budget pressure -- the arrangement reached from here cannot be finished, and RESET is the only way to unwind it because lp85 has no undo", "expected_observation": "state stays NOT_FINISHED, levels_completed stays 7, and the column-0 bar returns to 0 of 64 cells consumed from 19"}, "outcome": {"observed": "183 cells changed between the settled frame of row 293 and that of row 294; state NOT_FINISHED -> NOT_FINISHED; levels_completed 7 -> 7; painted cells 4096 -> 4096; the row carries 1 frames against 1 on row 293", "expectation_held": true}, "action_role_source": "UNCITABLE: RESET has no dispatch branch in docs/static/games/src/lp85-305b61c3/lp85.py - see unhandled_actions in datasets/decision-steps/dispatch/lp85-305b61c3.json", "rationale_provenance": "annotated", "tier": "gold", "memory_in": {"known_mechanics": ["ACTION6 is the only action this game offers; available_actions is [6] on every row", "ACTION6 is a click -- action_input.data carries {game_id, x, y}", "a click only does something when it lands on a sprite whose first tag contains 'button'; any other click is a total no-op", "the 64-cell bar in column 0 of the frame renders the consumed FRACTION of the level's step budget: it advances only on an effective click, never on a click that hit no button, and it advances by 64/StepCounter cells -- 1 cell per click on this level, but 5 on level 1, so cells are steps only where the level's budget is 64", "RESET restores the level's opening arrangement and refills the step budget bar to zero cells consumed"], "tested_actions": ["ACTION6", "RESET"], "hypotheses": ["the level clears when every marker sits on its goal cell, and pressing a button shifts a whole row or column of pieces at once"], "goal": "clear this level's arrangement before the column-0 step bar fills", "current_plan": "abandon the arrangement built so far on this level and start it again from the opening layout"}, "action_role": "plan abandonment on a live board -- RESET used to unwind an arrangement rather than to recover from a death"}
{"schema_version": "0.1", "game_id": "lp85-305b61c3", "source": {"kind": "human_replay", "recording_guid": "129ddf21-d7ba-4ca0-9577-0cea2af042b6", "row_index": 311}, "segment": {"id": "lp85-l8-abandon-311-00", "boundary_reason": "episode_start"}, "level": 7, "frame_ref": {"recording_guid": "129ddf21-d7ba-4ca0-9577-0cea2af042b6", "row_index": 310, "field": "data.frame"}, "ascii": null, "last_action": {"action": "ACTION6", "args": {"row": 24, "col": 54}}, "last_result": {"board_changed": true, "level_changed": false}, "decision": {"memory_out": {"current_plan": "rebuild this level's arrangement from the opening layout on a different ordering of button presses"}, "action": {"action": "RESET"}, "rationale": "the board is alive and the bar shows only 13 of 64 steps consumed, so this is not budget pressure -- the arrangement reached from here cannot be finished, and RESET is the only way to unwind it because lp85 has no undo", "expected_observation": "state stays NOT_FINISHED, levels_completed stays 7, and the column-0 bar returns to 0 of 64 cells consumed from 13"}, "outcome": {"observed": "181 cells changed between the settled frame of row 310 and that of row 311; state NOT_FINISHED -> NOT_FINISHED; levels_completed 7 -> 7; painted cells 4096 -> 4096; the row carries 1 frames against 1 on row 310", "expectation_held": true}, "action_role_source": "UNCITABLE: RESET has no dispatch branch in docs/static/games/src/lp85-305b61c3/lp85.py - see unhandled_actions in datasets/decision-steps/dispatch/lp85-305b61c3.json", "rationale_provenance": "annotated", "tier": "gold", "memory_in": {"known_mechanics": ["ACTION6 is the only action this game offers; available_actions is [6] on every row", "ACTION6 is a click -- action_input.data carries {game_id, x, y}", "a click only does something when it lands on a sprite whose first tag contains 'button'; any other click is a total no-op", "the 64-cell bar in column 0 of the frame renders the consumed FRACTION of the level's step budget: it advances only on an effective click, never on a click that hit no button, and it advances by 64/StepCounter cells -- 1 cell per click on this level, but 5 on level 1, so cells are steps only where the level's budget is 64", "RESET restores the level's opening arrangement and refills the step budget bar to zero cells consumed"], "tested_actions": ["ACTION6", "RESET"], "hypotheses": ["the level clears when every marker sits on its goal cell, and pressing a button shifts a whole row or column of pieces at once"], "goal": "clear this level's arrangement before the column-0 step bar fills", "current_plan": "abandon the arrangement built so far on this level and start it again from the opening layout"}, "action_role": "plan abandonment on a live board -- RESET used to unwind an arrangement rather than to recover from a death"}
{"schema_version": "0.1", "game_id": "lp85-305b61c3", "source": {"kind": "human_replay", "recording_guid": "129ddf21-d7ba-4ca0-9577-0cea2af042b6", "row_index": 365}, "segment": {"id": "lp85-l8-abandon-365-00", "boundary_reason": "episode_start"}, "level": 7, "frame_ref": {"recording_guid": "129ddf21-d7ba-4ca0-9577-0cea2af042b6", "row_index": 364, "field": "data.frame"}, "ascii": null, "last_action": {"action": "ACTION6", "args": {"row": 29, "col": 54}}, "last_result": {"board_changed": true, "level_changed": false}, "decision": {"memory_out": {"current_plan": "rebuild this level's arrangement from the opening layout on a different ordering of button presses"}, "action": {"action": "RESET"}, "rationale": "the board is alive and the bar shows only 42 of 64 steps consumed, so this is not budget pressure -- the arrangement reached from here cannot be finished, and RESET is the only way to unwind it because lp85 has no undo", "expected_observation": "state stays NOT_FINISHED, levels_completed stays 7, and the column-0 bar returns to 0 of 64 cells consumed from 42"}, "outcome": {"observed": "142 cells changed between the settled frame of row 364 and that of row 365; state NOT_FINISHED -> NOT_FINISHED; levels_completed 7 -> 7; painted cells 4096 -> 4096; the row carries 1 frames against 1 on row 364", "expectation_held": true}, "action_role_source": "UNCITABLE: RESET has no dispatch branch in docs/static/games/src/lp85-305b61c3/lp85.py - see unhandled_actions in datasets/decision-steps/dispatch/lp85-305b61c3.json", "rationale_provenance": "annotated", "tier": "gold", "memory_in": {"known_mechanics": ["ACTION6 is the only action this game offers; available_actions is [6] on every row", "ACTION6 is a click -- action_input.data carries {game_id, x, y}", "a click only does something when it lands on a sprite whose first tag contains 'button'; any other click is a total no-op", "the 64-cell bar in column 0 of the frame renders the consumed FRACTION of the level's step budget: it advances only on an effective click, never on a click that hit no button, and it advances by 64/StepCounter cells -- 1 cell per click on this level, but 5 on level 1, so cells are steps only where the level's budget is 64", "RESET restores the level's opening arrangement and refills the step budget bar to zero cells consumed"], "tested_actions": ["ACTION6", "RESET"], "hypotheses": ["the level clears when every marker sits on its goal cell, and pressing a button shifts a whole row or column of pieces at once"], "goal": "clear this level's arrangement before the column-0 step bar fills", "current_plan": "abandon the arrangement built so far on this level and start it again from the opening layout"}, "action_role": "plan abandonment on a live board -- RESET used to unwind an arrangement rather than to recover from a death"}
{"schema_version": "0.1", "game_id": "lp85-305b61c3", "source": {"kind": "human_replay", "recording_guid": "129ddf21-d7ba-4ca0-9577-0cea2af042b6", "row_index": 386}, "segment": {"id": "lp85-l8-abandon-386-00", "boundary_reason": "episode_start"}, "level": 7, "frame_ref": {"recording_guid": "129ddf21-d7ba-4ca0-9577-0cea2af042b6", "row_index": 385, "field": "data.frame"}, "ascii": null, "last_action": {"action": "ACTION6", "args": {"row": 58, "col": 37}}, "last_result": {"board_changed": true, "level_changed": false}, "decision": {"memory_out": {"current_plan": "rebuild this level's arrangement from the opening layout on a different ordering of button presses"}, "action": {"action": "RESET"}, "rationale": "the board is alive and the bar shows only 16 of 64 steps consumed, so this is not budget pressure -- the arrangement reached from here cannot be finished, and RESET is the only way to unwind it because lp85 has no undo", "expected_observation": "state stays NOT_FINISHED, levels_completed stays 7, and the column-0 bar returns to 0 of 64 cells consumed from 16"}, "outcome": {"observed": "176 cells changed between the settled frame of row 385 and that of row 386; state NOT_FINISHED -> NOT_FINISHED; levels_completed 7 -> 7; painted cells 4096 -> 4096; the row carries 1 frames against 1 on row 385", "expectation_held": true}, "action_role_source": "UNCITABLE: RESET has no dispatch branch in docs/static/games/src/lp85-305b61c3/lp85.py - see unhandled_actions in datasets/decision-steps/dispatch/lp85-305b61c3.json", "rationale_provenance": "annotated", "tier": "gold", "memory_in": {"known_mechanics": ["ACTION6 is the only action this game offers; available_actions is [6] on every row", "ACTION6 is a click -- action_input.data carries {game_id, x, y}", "a click only does something when it lands on a sprite whose first tag contains 'button'; any other click is a total no-op", "the 64-cell bar in column 0 of the frame renders the consumed FRACTION of the level's step budget: it advances only on an effective click, never on a click that hit no button, and it advances by 64/StepCounter cells -- 1 cell per click on this level, but 5 on level 1, so cells are steps only where the level's budget is 64", "RESET restores the level's opening arrangement and refills the step budget bar to zero cells consumed"], "tested_actions": ["ACTION6", "RESET"], "hypotheses": ["the level clears when every marker sits on its goal cell, and pressing a button shifts a whole row or column of pieces at once"], "goal": "clear this level's arrangement before the column-0 step bar fills", "current_plan": "abandon the arrangement built so far on this level and start it again from the opening layout"}, "action_role": "plan abandonment on a live board -- RESET used to unwind an arrangement rather than to recover from a death"}
```

### What did land

One record: `datasets/decision-steps/v0/episodes/lp85-305b61c3__129ddf21-d7ba-4ca0-9577-0cea2af042b6__l6-budget-exhaustion.jsonl`,
row 175, tier `negative`, and it passes `validate.py --require-frame-resolution`.

**It is the falsified half of a pair whose corrected half is blocked**, and it should not be read
as the pair. Its own `corrected_decision` field says what should have been done — RESET, which
refills the budget at no step cost — so the record is complete and self-contained under the
schema; what is missing is the *observed* correction on row 176, which is a second record and is
the first of the six above.

---

## 4. Method note

The mechanic was derived from source first and then checked against the frames, not the other way
round, because the frames alone would have supported a weaker and wrong reading: "the bar fills
up and then you die" is consistent with a timer. The source says it is a counter decremented only
by clicks that hit a button, and rows 172 → 173 — a click that left the bar where it was — are
what separates the two readings. One row out of 416 carries the distinction.

Nothing here was taken from the analysis notes that proposed this run. Every number was
re-measured from the NDJSON in this pass.
