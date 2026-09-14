<!--
Author: Claude Opus 5 (Bubba)
Date: 13-September-2026
PURPOSE: Job 3 (arm B on the null-check lanes) result, the level-completion readout for
jobs 1-3 that the score-only analysis was missing, and the reason job 5 (arm A on the same
null-check lanes) had to be added before the null check can answer anything.
SRP/DRY check: Pass — job 1 and job 2 results live in their own docs; this adds job 3 and
the cross-job level readout, and corrects the pass-3 truncation claim made in the job 1 doc.
-->

# Job 3 null check, and what `levels_completed` says that `score.json` didn't

## Job 3 ran clean

`markbarney/arc3-job3-null-check`, COMPLETE. Provenance in-log: `arm=B-sparse-deletion`,
`system_prompt_chars=11991`, all four deleted probes `present=False`,
`NVIDIA RTX PRO 6000 Blackwell Server Edition, 97887 MiB`. 7 lanes x 4 passes, 1980s cap.

Per-game, pre-registered window (passes 0-2), score then levels cleared across those 3 passes:

| game | mean score | levels (p0-2) | of |
|---|---|---|---|
| lp85 | 24.91 | 11 | 8 |
| r11l | 7.94 | 4 | 6 |
| ka59 | 5.41 | 4 | 7 |
| cn04 | 4.76 | 3 | 6 |
| sb26 | 2.78 | 3 | 8 |
| cd82 | 1.87 | 3 | 6 |
| sc25 | 0.53 | 2 | 6 |

Arm mean 6.885.

## The null check cannot be read yet — job 5 exists to fix that

The design was "run arm B on games we already solve; if they move, the effect isn't the
one being claimed." **There is no arm-A measurement on these lanes**, so there is nothing
for "move" to be measured against. The ~100 scores on cd82/lp85/sb26 quoted in earlier
docs come from `g4run-astra-grid2-b476` — a different harness and a different run shape.
Comparing against those would be comparing two things that differ in more than the prompt.

**Job 5** (`arc3-job5-null-control`) is arm A on the identical seven lanes, same 4 x 1980 /
7920 shape, so the pair is symmetric and the passes-0-2 window applies to both. Generated
and lint-clean; queued behind job 4.

One further split, to be applied when job 5 lands: `NULL_CHECK` mixes two different tests.
**cd82, lp85, sb26** are the actual null — games we already solve, which should not move.
**cn04, r11l, sc25, ka59** are not "mid-table" — cn04 and sc25 are floor games with their
own findings docs on this branch. If arm B lifts those, that *supports* the specificity
claim rather than refuting it. Averaged into one arm number a real result would read as
"the null check moved" and get called noise. Report the three and the four separately.

## Level readout for jobs 1-3 — the analysis that was missing

`score.json` was the only thing being read. `benchmark.json` carries `levels_completed`,
`number_of_levels`, `actions_per_level`, and `state` per lane-run. Levels cleared across
passes 0-2:

| | job 1 (A-control) | job 2 (B-deletion) |
|---|---|---|
| bp35 | 1 | 2 |
| g50t | 0 | 2 |
| lf52 | 3 | 4 |
| ls20 | 1 | 3 |
| sk48 | 1 | 0 |
| tn36 | 2 | 2 |
| wa30 | 2 | 2 |
| **total** | **10** | **15** |

**The arm-B gain is level clears, not score drift.** 10 -> 15 across the bottom seven,
and the two biggest score movers are both level movers: g50t 0 -> 2 levels (from four hard
zeros), lf52 3 -> 4 (the first pass either arm ever got past level 1 credit there). sk48
is the one regression, 1 -> 0, and it is one pass wide.

The pre-registration predicted the gain lands in the bottom seven. It does, and it lands as
the thing the boss's thesis says it should: the agent forming a workable model of one more
level, not squeezing more credit out of the same level.

## Correction to the job 1 doc's truncation claim

The job 1 write-up said pass 3 is truncated (~830s of its 1980) and is "four zeros in six
of seven games", implying truncation is fatal. Job 3 shows it is not uniformly fatal: pass 3
there returns cn04 4.762, sb26 2.778, r11l 4.762, ka59 2.913, lp85 8.333 — bit-identical
level credit to the earlier passes on the games that bank early. Truncation costs *time*,
and on hard games that time is where the level would have been found; on games that clear
level 1 in a few hundred actions it costs nothing.

Pass 3 stays excluded from the primary window anyway — it is not a like-for-like pass, and
changing that mid-series would add a second variable. Recorded here so the exclusion is
understood as a symmetry rule, not as "pass 3 is always empty".

## Every lane-run in all three jobs ended `gave_up` or `cancelled`

84 lane-runs across jobs 1-3. Zero wins. Passes 0-2 all report `state=gave_up` with
wallclock at or fractionally over the 1980s cap; pass 3 reports `cancelled` at the outer
budget. So `gave_up` here coincides with cap exhaustion and should not be read as the agent
voluntarily quitting — that distinction needs a run with a raised cap to separate, and is
not claimed either way on this evidence.

## Spend

Derived from run logs, not the quota API (`GetAcceleratorQuotaStatistics` is not reachable
with a cookie-only request and was not worth further chasing). Jobs 1-3 each ran ~7,400s
wall including the ~540s vLLM boot; job 0 v1+v2 and the accel smokes add ~1,700s. Roughly
**6.6h of the 30h**, refresh Thu 18-Sep. Jobs 4 and 5 are ~2.1h each.
