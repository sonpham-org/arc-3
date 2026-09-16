<!--
Author: Claude Opus 5 (Bubba)
Date: 13-September-2026
PURPOSE: Result of job 2, the sparse-deletion prompt arm (arm B), measured against the
job-1 control (arm A) on the same seven bottom games, same hardware, same caps. Records
the pre-registered comparison window (passes 0-2), the honest variance caveat, and what
it means for arm C.
SRP/DRY check: Pass — companion to 2026-09-13-job1-control-baseline.md (arm A only).
-->

# Job 2 — the sparse-deletion arm beats control

Kernel `markbarney/arc3-job2-sparse-deletion`, COMPLETE 13-Sep-2026.
7 lanes x 4 passes, `concurrency=7`, per-game cap 1980s, outer budget 7920s.

**Arm provenance, read out of the run log — clean:**

```
ARM_PROVENANCE arm=B-sparse-deletion
ARM_PROVENANCE probe='64 x 64'            present=False
ARM_PROVENANCE probe='puzzle'             present=False
ARM_PROVENANCE probe='remaining-steps bar' present=False
ARM_PROVENANCE system_prompt_chars=11991
NVIDIA RTX PRO 6000 Blackwell Server Edition
```

Control was 12,681 chars. 690 characters deleted, nothing added.

## Pre-registered comparison — passes 0-2, n=3

Pass 3 is excluded per the job-1 finding that the outer budget cancels it; this window
was agreed with Sherlock *before* job 2's number existed.

| Game | A control | B deletion | delta |
|---|---|---|---|
| g50t | 0.000 | **1.405** | +1.405 |
| ls20 | 0.261 | 1.393 | +1.132 |
| tn36 | 2.770 | 3.571 | +0.801 |
| lf52 | 1.818 | 2.602 | +0.784 |
| bp35 | 0.194 | 0.293 | +0.099 |
| wa30 | 1.481 | 1.481 | 0.000 |
| sk48 | 0.192 | **0.000** | -0.192 |
| **OVERALL** | **0.960** | **1.535** | **+0.575 (+60%)** |

All four passes, for completeness: A 0.864 -> B 1.216.

The prediction was that gain would land in the bottom seven. It did: five of seven up,
one flat, one down.

## The caveat, stated up front

**This is n=3 on a distribution that is mostly zeros with occasional spikes.** The
per-pass scores make that plain:

```
tn36   A [8.31, 0.00,  0.00, 0.00]   B [0.00, 0.00, 10.71, 0.00]
ls20   A [0.00, 0.00,  0.78, 0.00]   B [0.26, 0.34,  3.57, 0.00]
sk48   A [0.00, 0.00,  0.58, 0.00]   B [0.00, 0.00,  0.00, 0.00]
lf52   A [1.82, 1.82,  1.82, 1.82]   B [1.82, 4.17,  1.82, 1.82]
g50t   A [0.00, 0.00,  0.00, 0.00]   B [1.70, 2.51,  0.00, 0.00]
```

tn36's +0.801 is one lucky pass in each arm. sk48's -0.192 is one lucky control pass and
no B pass — it is not evidence the deletion hurt sk48. Neither number should be argued
from. A single-pass spike is the unit of noise in this benchmark, and most per-game deltas
here are one spike wide.

## What is not noise

Two results are structural rather than spiky:

1. **g50t: 0.000 across all four control passes -> two nonzero B passes (1.70, 2.51).**
   The control arm has never scored on this game. Going from a hard zero to scoring twice
   is a different kind of event than a spike moving between passes. It is also the game we
   now have a human WIN replay for — 7/7 levels, 533 actions
   (`2026-09-13-g50t-human-win-vs-our-zero.md`).
2. **lf52 broke its own ceiling.** Control was 1.818 on all four passes — zero variance,
   the exact value of level-1 credit, four times. B produced a 4.169. That is the first
   time any pass of either arm has exceeded level-1 credit on lf52, and it directly tests
   Sherlock's phase-transition hypothesis.

## Consequence for arm C

The gate written down before this number existed: if B beats control, the headline
comparison for job 4 is B -> C. B beat control, so arm C stacks on B as built, and the
comparison stands as pre-registered.

Job 3 (null check — cd82/lp85/sb26 plus four mid games) goes next and is the real test of
whether this is an effect or a mood. If the three games we already solve move under arm B,
the +60% is not what I claim it is.
