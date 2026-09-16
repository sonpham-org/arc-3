<!--
Author: Claude Opus 5
Date: 16-September-2026
PURPOSE: How passes D and E are being run on the recordings already on disk, per Dr. Fable's
item 2 (docs/plans/2026-09-16-dr-fable-calls-on-the-step5-review.md section 2). Records the
recount of the material that contradicts the step-5 plan's figures, the caps set before any
record was written so the corpus does not become a RESET-imitation set, the record unit per
moment, and how pass E is kept independent of pass D. Results are appended when they exist.
SRP/DRY check: Pass - the step-4 execution plan holds what passes D and E are; this holds only
the pilot's scope decisions and its measured outcome. Schema semantics stay in SCHEMA.md.
-->

# Passes D and E — the pilot on what is on disk

**Status:** in progress, 16-Sep-2026. Pass C stays off.

## 1. The material, recounted — it is not what the step-5 plan says

The step-5 plan and Dr. Fable's calls both cite **13 in-scope recordings, 132 recovery moments,
128 after the cull, ~3% lost.** Measured today on `datasets/decision-steps/v0/recordings/`:

| | step-5 plan | on disk |
|---|---|---|
| recordings (as66 excluded) | 13 | **11** |
| recovery moments | 132 | **117** |
| lost to the cull | ~3% (132 → 128) | **0** |

Method: a moment is a `GAME_OVER` flip, a `RESET` row after row 0, or an `ACTION7` row; the
cull drops moments on a level the run never cleared. **Every one of the 11 recordings is a full
win** (bp35 9/9, cd82 6/6, cn04 6/6, dc22 6/6, ft09 6/6, g50t 7/7 twice, ka59 7/7, lp85 8/8, ls20
7/7, m0r0 6/6), so the cull removes nothing here. The plan's two extra recordings and 15 extra
moments cannot be reproduced from disk. The ceiling argument in Dr. Fable's §2 does not depend
on the exact figure, so nothing downstream changes, but the numbers in those two documents
should not be quoted again.

Two more facts about the sample:

- **It is almost all RESET.** 117 moments = 74 resets + 37 undos + 13 deaths (counting every
  press). All 37 undos are bp35. Outside bp35 and lp85 the whole sample is resets, apart from
  one g50t death.
- **All 11 are training-side games** in `datasets/splits/public25-train-test-split.json`; none
  of the 7 held-out games has a recording. Dr. Fable's §0 already rules that human replays of
  training games do not contaminate the eval, so this is noted, not acted on.

Grouped into episodes rather than presses, bp35's material is 11 deaths, 11 undo bursts (one
of 14 presses) and 13 resets, of which 8 follow a death.

## 2. Caps, set before annotation

Annotating every press would ship a corpus whose modal record is "press RESET", which teaches
imitation, the thing the record format exists to avoid. So:

1. **Every death is annotated** — the fatal move is where the refutation lives, and each one is
   on a different board.
2. **Near-identical recoveries are capped at three per game.** bp35's "death → undo refused →
   RESET" triple repeats six times; the refused undo and the RESET after it are written for at
   most three (one already exists at row 215), and the fatal move is still written for all.
3. **Live-board resets: at most four per game**, spread across levels, preferring ones whose
   preceding move shows a visible refutation.
4. **An undo burst is one moment:** the move being undone, and the first `ACTION7`. Not every
   press of a 14-press burst.
5. **Deferred: dc22, ft09, ka59, m0r0.** They have recordings but no dispatch table (pass B), so
   the segmenter cannot cut them, and all 24 of their moments are resets. They add games but not
   recovery vocabulary. Pass B for them is the follow-up if the pilot says the eval needs rows.
6. **cd82 has no moments.** lp85 is already fully annotated (7 records).

In scope for this pass: **bp35, g50t (both runs), cn04, ls20.** Pass E covers those plus the 12
records already on `main`, which have never been through it.

## 3. The record unit

- **The move before the event** — the fatal move, the move that got undone, or the last move
  before a live reset when the frame shows why. `expectation_held: false` only when the next
  frame refutes the stated expectation.
- **The recovery decision** — the `RESET`, `ACTION7`, or first move after the death. Tier
  `negative` only when the tape shows the action failing *and* shows the correction (bp35's
  refused undo, corrected by the `RESET` on the next row).

`memory_in` holds only what the run itself has shown by that row. The game source is used for
`action_role_source` and for the annotator's own understanding, never written into
`memory_in`. **Several of the 12 existing records break this** (lp85's `memory_in` quotes sprite
tag names and the `StepCounter` arithmetic); pass E is told to check for exactly that.

## 4. Pass E — how it is kept independent

Pass D is written in one session. Pass E runs as a **separate headless agent per episode file**
(`claude -p`, no tools, no file access). It gets only three things:

1. the record(s);
2. evidence rendered from the recording: for each record, the board before and after as text
   (whole-board and changed-region crop), the state and level on both rows, and the action
   history of the level up to that row;
3. the rules: an `expected_observation` must be concrete enough for the shown frames to refute
   it; `expectation_held` must match what the frames show; `memory_in` may hold only what the
   run has shown; an `action_role` must not claim an effect the frames contradict.

It returns keep or cut for each record, with a one-line reason. **Cut records are deleted, not
rewritten.** The cut rate is reported, and a pass that cuts nothing is reported as suspect.

## 5. Results

Pending.
