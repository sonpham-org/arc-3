<!--
Author: Claude Fable 5.1 (Dr. Fable)
Date: 16-September-2026
PURPOSE: The decisions on the four questions in 2026-09-15-review-request-for-dr-fable.md, made
so the work can move. Each call states what changes on disk or in the plan, and what would
reverse it. Posted first as the review on PR #21; recorded here because a PR review is not a
document the next session reads.
SRP/DRY check: Pass - the review request holds the evidence and options and is not restated;
the step-5 plan holds the forward plan and is amended in place to match these calls; the
readiness doc (2026-09-15-qwen27b-finetune-readiness.md) holds the no-teacher decision this
rests on. This holds only the calls and their consequences.
-->

# Dr. Fable's calls on the step-5 review

**Date:** 16-Sep-2026. **Answers:** [`2026-09-15-review-request-for-dr-fable.md`](2026-09-15-review-request-for-dr-fable.md).
**Read against:** `main` at `f01a150`, which includes Son's no-teacher decision (`7074b67`) and
the a424 clearance.

---

## 0. The premise moved, and this is the call that governs the other four

Son's decision of 15-Sep 21:19 EDT stands: **no teacher model.** RL is on-policy, and any SFT
bootstrap the 27B needs comes from its own winning rollouts by rejection sampling. The
decision-step corpus was specified as SFT teacher data. That role is gone.

**The corpus's job from today is the recovery eval, plus at most a small weighted mix-in.**

- `datasets/decision-steps/` is no longer described as "the training target." Its records are
  the held-out behavioural questions in §3 below.
- Volume is no longer gated on "does the eval show an effect." It is gated on "does the eval
  need more rows," and 128 recovery moments on disk is enough to ask the question.
- The split in `datasets/splits/public25-train-test-split.json` forced bp35, cn04 and lp85
  into training to protect the corpus as teacher data. That constraint is now unnecessary. It
  is **left in place** because it does no harm, and because the eval rows for those three games
  come from human replays, not model rollouts, so training the model on those games is not
  contamination of the eval. If the split is redrawn after the baseline (see §3), drop the
  constraint.

What would reverse this: the base 27B clearing nothing anywhere, and its own rollouts giving
no bootstrap. Then a human-annotated corpus becomes the only bootstrap available, and this
paragraph is rewritten.

## 1. RESET: expose it behind a guard, as one measured arm; keep the records

The harness strips RESET from the model's menu (`solver.py:171`) and auto-resets on
`GAME_OVER` (`solver.py:345-352`). Two things the review understated:

- **On ls20 a voluntary RESET is a winning move, not recovery.** Row 454 of the Boss's run:
  one life left, RESET pressed on a live board, three lives and a full step meter back, level
  unchanged. Four of seven ls20 levels have a 21-step budget; a human wins by resetting on
  purpose. The harness cannot make that move on any game. Option (a) does not only cost the
  cleanest records; it removes a level-winning move.
- **The decision precedes the 27B baseline.** The baseline fixes the action space for the RL
  experiment. A policy trained with RESET hidden never learns it, and adding it mid-experiment
  breaks the comparison.

Calls:

1. **The 27B baseline runs on the pinned harness, RESET hidden**, as Son directed. Not touched.
2. **Run option (b) as one Kaggle harness arm**, stacked on arm B (deletion), on the bottom
   seven, with a game-agnostic guard: never two RESETs in a row, and at most one RESET per 20
   actions. as66's 98-of-101 run trips that guard on its second action. Report reset rate per
   game next to level clears. Clears up on ls20 or wa30 with the rate held: expose RESET in the
   RL harness. Clears down or rate at the cap: option (a) wins by measurement.
3. **Option (c) is dropped.** `tool_agent.py:257` already tells the model an auto-reset
   happened. One more sentence is not worth a run.
4. **Every "chose RESET on a live board" record stays.** They are the eval rows for whether the
   arm above matters. Retarget training rows to "notice the refutation earlier and do not
   re-enter the fatal move after the auto-reset" only if the arm loses.

Owner: the harness track. Spec for the arm: two edits against the arm-B bundle, the RESET
filter in `_engine_action_names` lifted behind the guard, and one line in `prompts.py` saying
RESET restarts the level and is rate-limited. Nothing else changes in that bundle.

## 2. Ceiling: pilot only, and stop

Annotate what is on disk (13 in-scope recordings, ~128 recovery moments), run pass E, and
**do not pull the other ~110 recordings.** With no teacher role, 2,500 to 3,500 records buys
nothing that 128 moments cannot buy as an eval. Re-measure the ceiling only if the arm in §1
wins and the mix-in question comes back.

## 3. Measurement: whole-game holdout and the behavioural question, with two gates

Both proposals are accepted. Report the behavioural number next to an ex-`ft09` run on
`baseline-v12`, never instead of it. Two additions become hard gates in the step-5 plan:

1. **The seven held-out games must score above zero on the base 27B.** If they do not, the test
   set cannot show a gain and the split is redrawn on measured agent difficulty. The bottom-seven
   numbers from the September Kaggle arms are agent difficulty and the split did not use them;
   the redraw should.
2. **The 18/7 experiment measures transfer within the public 25.** It proves the pipeline moves
   a number. It is not evidence about the hidden set, and `docs/how-this-feeds-kaggle.md` says
   why. `as66` is outside the lineup, has 15 recordings on disk, and costs nothing to run: it is
   the one out-of-lineup probe, reported as such.

## 4. Convention: imposed

Schema and validator changes go through a PR that names the migration and ships the migration
script. Records and findings can keep landing directly. `validate.py` already refuses any
record whose `schema_version` is not the current constant (the `schema-version-drift` fixture
proves it), so a stale record fails at the door; that gate stays and is not to be loosened to
"accept older versions."

---

## What moves next, in order

1. Harness track: build and run the RESET-guard arm (§1.2). One arm, bottom seven, n=4 with the
   corrected per-pass cap.
2. Corpus track: passes D and E on the 13 recordings on disk, nothing pulled. Cut rate reported.
3. Spark track (Son's directive, unchanged): learner stack on aarch64, 54G BF16 download, the
   27B baseline, then the §3 gate on the split.
