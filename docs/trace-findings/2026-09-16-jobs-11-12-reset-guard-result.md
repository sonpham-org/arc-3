<!--
Author: Claude Opus 5
Date: 16-September-2026
PURPOSE: Result of Kaggle jobs 11 and 12, the RESET-guard arm (arm I) and its same-cap arm-B
control, run for Dr. Fable's call 1.2 in docs/plans/2026-09-16-dr-fable-calls-on-the-step5-review.md.
Records run health, the per-game numbers, how often the model chose RESET, whether the extra clears
actually followed a RESET, and what the pre-registered decision rule says.
SRP/DRY check: Pass - harnesses/reset-guard/MANIFEST.md holds the arm's design and decision rule
and now points here for the score; the job-2 and job-10 result docs are the older arms' results.
-->

# Jobs 11 and 12 — the model uses RESET, the score rises, and the cause is not shown

**Jobs:** `markbarney/arc3-job11-reset-guard` (arm I, RESET offered behind the guard) and
`markbarney/arc3-job12-deletion-cap1620` (arm B, unchanged). Both COMPLETE 16-Sep-2026, run side
by side. 7 bottom-seven games × 4 passes, 1620s per game.

## In short

- **The model used RESET when offered it:** 32 times in 3,620 actions, about 1 per 100. The
  guard refused 4. The cap would allow 5 per 100, so the rate is nowhere near it.
- **Kaggle score: 1.54 with RESET, 0.995 without.** Level clears: **16 and 16.**
- **Most of the score gap is two single runs.** tn36 pass 2 (10.71) and wa30 pass 2 (6.67), both
  in job 11. Scores spike on one pass; that is the known shape of this benchmark.
- **The ls20 gain did not come through RESET.** ls20 cleared a level in 3 passes with RESET and 1
  without, but none of those 3 clears followed a RESET on the level it cleared.
- **bp35 went from 4 clears to 0.** Its first pass in job 11 never pressed RESET at all.

By the rule written before the run, this is a pass: clears went up on ls20 (1 → 3) and wa30
(3 → 4) with the reset rate well under the cap. But the evidence that **RESET itself** did it is
weak. Read it as "offering RESET did not hurt, and may help", not as "RESET wins".

## Run health

Both clean. `NVIDIA RTX PRO 6000 Blackwell Server Edition` in both logs, `per_game_s=1620.0`,
`only_reset_levels='true'`. Job 11's system prompt is 12,242 characters, job 12's 11,991: exactly
the 251-character RESET line apart, as the manifest predicted. Guard constant 20 in job 11, 0 in
job 12. Only arm I carries the arm-I marker.

**All four passes ran to the cap in every lane.** No lane was cancelled; the last lane finished at
7,093s (job 11) and 7,143s (job 12), under the 7,320s cutoff. The 1620s cap fixed the pass-3
truncation that hit jobs 1-10. Teardown raised the same `vLLM teardown did not reach the bounded
terminal gate` error as earlier jobs, after all artifacts were written.

## Per game

Level clears per pass, and mean Kaggle score over the four passes:

| game | RESET offered (job 11) | score | RESET hidden (job 12) | score | model RESETs (job 11) |
|---|---|---|---|---|---|
| bp35 | 0, 0, 0, 0 | 0.00 | 1, 1, 1, 1 | 0.75 | 3 |
| g50t | 1, 0, 1, 0 | 1.78 | 0, 1, 0, 1 | 1.70 | 2 |
| lf52 | 1, 1, 1, 1 | 1.82 | 1, 1, 1, 1 | 1.82 | 9 (3 refused) |
| ls20 | 0, 1, 1, 1 | 1.86 | 0, 0, 1, 0 | 0.82 | 8 |
| sk48 | 0, 0, 0, 0 | 0.00 | 0, 0, 1, 0 | 0.32 | 2 |
| tn36 | 0, 1, 2, 0 | 2.70 | 0, 1, 0, 0 | 0.08 | 7 |
| wa30 | 1, 0, 2, 1 | 2.61 | 1, 1, 0, 1 | 1.48 | 1 |
| **all** | **16 clears** | **1.54** | **16 clears** | **0.995** | **32 (4 refused)** |

Job 11 also took more actions, 3,620 against 2,675.

## Did the clears come from RESET?

For each level cleared, did the model press RESET on that level before clearing it?

- **Job 11: 6 of 16 clears followed a RESET on the same level** — g50t 2, tn36 2, lf52 1, wa30 1.
  The other 10 did not.
- **ls20: 0 of its 3 clears.** The game this arm was built around shows the gain, but not through
  the mechanism. A human wins ls20 by resetting on purpose; the model's three clears came without
  it.
- Job 12: 0 of 16, as expected, since RESET was hidden.

The gains on ls20 and bp35's loss are both at least as consistent with the 251-character prompt
line changing how the model plays, or with ordinary pass-to-pass noise, as with RESET being used
well. Arm H showed a prompt line can cost clears in lanes that never use the action; here the
totals held level, so that cost did not appear.

## Against the decision rule

From `harnesses/reset-guard/MANIFEST.md`, written before the run:

- *Clears up on ls20 or wa30 with the rate held → expose RESET in the RL harness.* **Met**: ls20
  1 → 3, wa30 3 → 4, rate about 1 per 100 against a cap of 5.
- *Clears down, or the rate at the cap → keep it hidden.* Not met: total clears unchanged, rate
  far from the cap.
- *The model barely uses it → uninformative.* Not met: 32 presses.

**The rule says expose it.** The in-tree harness already does, as of `ce371447a`. What the rule
does not cover, and this run cannot settle, is whether RESET is why. n = 4 passes a game, and the
per-game differences are one or two passes wide.

## What would settle it

The same pair again, at the same cap, when the GPU allowance refreshes (Thursday 18-Sep, 20:00
ET). If ls20, wa30 and tn36 hold their gains and bp35 comes back, keep it on. If bp35 stays at 0,
look at its traces for what the RESET line changed there before the RL experiment inherits it.
