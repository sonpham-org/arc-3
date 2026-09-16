<!--
Author: Claude Opus 5 (Bubba)
Date: 13-September-2026
PURPOSE: Results of Kaggle job 1 (arm A, control) — the baseline measurement of the unmodified
minimal harness prompt across the bottom-seven games at n=4 passes on an RTX PRO 6000. Records
per-game and per-pass scores, the arm provenance proving the control prompt was unmodified, and
a measurement defect (pass 3 truncation) found in the wallclock timings.
SRP/DRY check: Pass — 2026-09-12-kaggle-experiment-plan.md holds the design; this holds arm A's
numbers only. Arm B gets its own file.
-->

# Job 1 — Arm A (control) baseline

**Kernel:** `markbarney/arc3-job1-control` · COMPLETE 12-Sep-2026 21:47 ET
**Card, in-log:** `NVIDIA RTX PRO 6000 Blackwell Server Edition, 97887 MiB, 580.159.04`
**Settings, in-log:** `arm=A-control lanes=7 passes=4 per_game_s=1980.0 budget_s=7920.0 concurrency=7`

All four control probes confirmed **present** in the assembled prompt — `DON'T DO THIS`,
`remaining-steps bar`, `64 x 64`, `puzzle`. The control arm really is unmodified.

## Scores — overall **0.864**

| game | score | pass 0 | pass 1 | pass 2 | pass 3 | levels cleared (of total) |
|---|---|---|---|---|---|---|
| tn36 | 2.078 | 8.310 | 0 | 0 | 0 | 2,0,0,0 / 7 |
| lf52 | 1.818 | 1.818 | 1.818 | 1.818 | 1.818 | 1,1,1,1 / 10 |
| wa30 | 1.667 | 2.222 | 2.222 | 0 | 2.222 | 1,1,0,1 / 9 |
| ls20 | 0.196 | 0 | 0 | 0.783 | 0 | 0,0,1,0 / 7 |
| bp35 | 0.146 | 0.583 | 0 | 0 | 0 | 1,0,0,0 / 9 |
| sk48 | 0.144 | 0 | 0 | 0.576 | 0 | 0,0,1,0 / 8 |
| g50t | **0.000** | 0 | 0 | 0 | 0 | 0,0,0,0 / 7 |

**g50t scored zero on all four passes.** Consistent with the corpus read
(`2026-09-12-astra-grid2-b476-run-floor.md`): the rewind verb goes unnamed, so the game is
never entered.

**lf52 is the only game with zero variance** — 1.818 four times out of four, level 1 and stop.
Every other game's score is carried by a single lucky pass. That is the fluke problem the
4-pass design exists to expose, and it shows up immediately: 5 of 7 games have a nonzero score
that rests on exactly one pass.

## The measurement defect: pass 3 is truncated

`final_wallclock_seconds` is cumulative from benchmark start, not per pass. Reading the
boundaries:

- pass 0 ends ~1980s · pass 1 ~3970s · pass 2 ~5950s · pass 3 **~6782s**

Passes 0, 1 and 2 each consumed the full 1980s cap. Pass 3 got **~830s — 42% of its
allotment** — and every lane came back `cancelled` with tiny action counts (13–50 actions vs
43–434 in the earlier passes). Pass 3 contributes four zeros to six of seven games and cannot
be distinguished from a genuine zero.

Cause: 4 × 1980 = 7920 exactly fills the outer budget, leaving nothing for the ~542s of vLLM
boot and harness setup that runs inside the same clock. The 33-minute cap was derived as
132 ÷ 4 and is correct arithmetic on the wrong numerator.

**All 28 runs hit the cap.** No lane ever finished early, so there is no slack to reclaim —
the cap is binding everywhere, which means effective n is 3, not 4.

**Decision: job 2 ships at 1980s unchanged.** A symmetric flaw across both arms preserves the
A/B comparison, which is the thing being measured. Changing the cap between arms would
introduce a second variable. The fix — cap ≈ 1840s, or budget 8462s — applies from job 4 on,
and is only worth paying for if a later job re-measures both arms together.

## What this baseline is for

Arm B (sparse deletion) is compared against this table game-by-game, not on the 0.864 average.
Pre-registered: the gain, if real, lands in these seven. Job 3 checks that cd82/lp85/sb26 do
not move.
