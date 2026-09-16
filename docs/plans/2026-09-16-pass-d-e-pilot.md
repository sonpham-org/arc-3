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

**Status:** pilot run, 16-Sep-2026. Results in §5. Pass C stays off.

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
6. **cd82 has no moments.** lp85's 7 moments were already annotated before this pass.

**Items 1-4 were overtaken by the change of unit in §3** before any record was written to them:
no death, undo or RESET record was added in this pass, so the RESET-imitation risk they guarded
against did not arise. Item 5 stands.

In scope for this pass: **bp35, g50t (both runs), cn04, ls20, and lp85.** Pass E covers those plus the 12
records already on `main`, which have never been through it.

## 3. The record unit — changed during the pass, and why

The unit written down before annotation was "the move before the event, plus the recovery
decision". Two things made it the wrong unit once the recordings were open:

- **The move before a death rarely carries a readable intention.** Writing why a player stepped
  left into a spike means inventing a plan, and the expectation ("the state stays
  NOT_FINISHED") is the same for every such record.
- **The recovery decision is almost always RESET**, which is the imitation problem §2 exists to
  avoid.

What the recordings do support, mechanically, is the thing the recovery eval asks about. A level
splits into attempts (a new attempt starts at the level's opening, after a RESET, or after a
death). Because a game replays identically from the same opening, the attempt that finally
clears a level and an earlier failed attempt stand on **the identical board** until the first
move where they choose differently. That **fork** is a same-board, different-choice decision
with the failure on tape: "last time, from here, you chose X and that attempt failed; this time
Y, and the level cleared."

`tools/find_retries.py` finds them. It compares choices by the board they leave, not by the
action text, so two clicks a cell apart on one tile are one choice and a walk into a wall is not
a step; it tolerates four cells for step counters; and it flags a fork whose winning choice an
earlier attempt had already made from that same board, because then the difference lies in
something the board does not show. Across the six recordings with dispatch tables it finds 20
forks, of which 14 are genuine changes of choice.

**Each fork record** is gold, sits on the winning attempt's fork row, and carries in `memory_in`
only what the run had shown by then: the failed attempt's moves and where it ended, and effects
visible in earlier frames, each cited by row. Its `expected_observation` names a cell box that was
checked against the frames before the record was written. Eleven were written: bp35 74, 217,
276, 396; g50t 207, 307, 493; lp85 177, 389; ls20 140; cn04 352. Left out: g50t 359 and 421 and
bp35 132, whose effects could not be stated precisely enough for pass E, and g50t 449, the same
fork as 421 in the player's second run.

## 4. Pass E — how it is kept independent

Pass D is written in one session. Pass E runs as a **separate headless agent per record**
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

Implementation: `tools/pass_e_review.py` runs `claude -p --model claude-opus-5 --tools ""
--safe-mode --no-session-persistence` from an empty temporary directory, so no tool, project file
or memory is reachable; the evidence comes from `tools/frame_evidence.py evidence`. Verdicts are
appended to `datasets/decision-steps/v0/pass-e/*.jsonl`, and `--apply` deletes what they cut.
To check that the gate can fail at all, three records with a defect planted on purpose (a flipped
`expectation_held`, a source-code fact in `memory_in`, a vague expectation) go through it too.

## 5. Results

### The gate cuts about half, and it can fail

| run | records | kept | cut |
|---|---|---|---|
| the 12 records already on `main` | 12 | 4 | **8** |
| the 11 fork records from this pass | 11 | 7 | **4** |
| planted defects (control) | 3 | 0 | **3** |

One model call per record, 26 in all, about two and a half minutes each.

Verdicts, with the reviewer's reasons: `datasets/decision-steps/v0/pass-e/2026-09-16-*.jsonl`.

**The control first, because it decides whether the rest means anything.** Three copies of fork
records, each with one defect planted: `expectation_held` flipped, a source-code fact added to
`memory_in`, and the expectation replaced with "the blue block moves and the board updates".
All three were cut, each on the check the defect was aimed at (`matches_frames`,
`memory_from_run`, `falsifiable`). The kept verdicts are not a reviewer that keeps everything:
they name cell boxes and counts it checked against the frames.

**The 12 existing records: 8 cut, all for `memory_from_run`.** All seven lp85 records quote the
game source in `memory_in` (the sprite-tag test a click must pass, and the `64/StepCounter`
arithmetic of the step bar); bp35 row 214 says every ACTION3 so far changed about 50 cells,
where the level history shows four that changed about 1,500. The expectations themselves mostly
held up: the reviewer counted column-0 bar cells and confirmed them. What failed was what the
record claims a player knew.

**The 11 fork records: 4 cut, two of them my errors and two a gap in the evidence.**

- g50t row 493 (`matches_frames`): the expectation said the move uncovers yellow at cols 18-23;
  cols 18-20 of row 40 were already yellow before the move. Wrong box.
- lp85 row 389 (`rationale_and_role`): the record said the (29,49) button had not been pressed
  from this board and the plan was to learn what it moves; the same arrow was pressed at rows
  369-372 with the identical effect. The run already knew.
- bp35 rows 74 and 396 (`observed_consistent`): `outcome.observed` carries the segmenter's
  painted-cell count, and the evidence never showed one, so the reviewer could not reconcile it.
  That is a defect in `frame_evidence.py`, fixed after the run (the evidence now states the count
  under the segmenter's own definition). The two records were deleted anyway: re-running the
  gate until a record passes is the softening the plan rules out.

Across the 23 real records the gate cut **12 (52%)**; leaving out the two evidence-gap cuts,
**10 of 21 (48%)**.

### What it says

The step-5 plan's §6 names this outcome in advance: *if the gate cuts most of the pilot's
records, the constraint is annotation quality.* It cut about half. Two separate failure modes:

1. **Hand-written records leak the source.** Every cut on the older records is an annotator
   writing down what the game code says rather than what the run showed. The source is necessary
   to cite `action_role_source` and the annotator reads it; keeping it out of `memory_in` is the
   discipline that failed, eight times out of twelve.
2. **Precise expectations are easy to get slightly wrong.** The fork records are built to be
   refutable, and two were refuted by their own frames at the level of a few cells.

**The fork unit survives better: 7 of 11 kept, against 4 of 12.** Its `memory_in` is the run's
own attempt history, cited by row, which leaves little room to leak source knowledge.

### What the corpus holds now

**11 records**, down from 12 this morning: the 4 older ones that survived (bp35 rows 213, 215,
216; cn04 row 345) and 7 fork records (bp35 217, 276; cn04 352; g50t 207, 307; lp85 177; ls20
140). The 7 forks are the recovery eval's first real items: a board, the failed attempt made
from it, and the change of choice that cleared the level.

That is small. On 11 recordings the finder turns up 14 genuine forks, about 1.3 per recording.
If the eval needs more rows, the cheapest next ones are the three forks left unwritten here and
pass B for dc22, ft09, ka59 and m0r0 so their forks can be found. Pass C stays off, per Dr.
Fable's §2.

### Side effect: the split's pinned-game list

`datasets/splits/public25-train-test-split.json` pins every game with labelled records into
training. The fork records add g50t and ls20, both already training games. Regenerated: **the
train and test lists are identical**; only `training_only_games` and the count of candidate test
sets searched changed. Dr. Fable's §0 already calls the pin unnecessary now; it is left in place.

### Not done in this pass

- bp35's 11 fatal moves and 11 undo bursts; live-board resets under the §2 caps.
- The deferred four games (§2 item 5).
- g50t forks at rows 359, 421 and bp35 row 132, left out as imprecise.
