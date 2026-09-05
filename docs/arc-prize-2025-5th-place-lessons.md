<!--
Author: Claude Opus 5 (Bubba)
Date: 05-September-2026
PURPOSE: Analysis of the ARC Prize 2025 5th-place Kaggle writeup (lonnieqin, "random seed as a
hyperparameter") and what it implies for ARC-3 benchmark design. Primary source pulled from
Kaggle's internal discussions API; verbatim copy saved alongside as
2026-09-05-arc-prize-2025-5th-place-writeup-source.md.
SRP/DRY check: Pass — no prior doc covers this writeup. Related: docs/2026-08-27-kaggle-*.
-->

# ARC Prize 2025, 5th place — what it actually shows, and what ARC-3 should take from it

Source: https://www.kaggle.com/competitions/arc-prize-2025/writeups/arc-prize-2025-competition-writeup-5th-place
Author: lonnieqin. Retrieved 2026-09-05 via `POST /api/i/discussions.WriteUpsService/GetWriteUpBySlug`
(the page is client-rendered; plain curl returns an empty shell). Full markdown preserved in the
companion `-source.md` file.

## What he did

Forked the ARChitects (Franzen/Disselhoff) 2024 1st-place notebook by way of two public reposts.
Nemo Mini, LoRA rank 32, first 32 layers trainable, transposition/rotation/colour-permutation
augmentation, test-time priming on each task's own examples, turbo-DFS beam search with augmented
scoring. **His single change was the random seed: 19920627.**

Result: **344th public LB, 5th private LB.** Public 4.17% (5/120). Private ~10% (12/120).

## The claim

"In small-sample competitions, treat the random seed as a first-class hyperparameter." He measures
the seed-variance envelope of his own notebook at **3.33%–6.67%** (4/120 to 8/120) and calls that a
2x swing that explains competitive placement.

## Why the claim does not survive his own numbers

**1. His result is outside his own envelope.** He puts seed variance at 4–8 solves. He scored 12.
Whatever produced 12 is not in the range he attributes to seed choice. The mechanism he advocates
cannot account for the outcome he is explaining with it.

**2. The direction of transfer is backwards.** He tuned seeds against the public LB and finished
**344th** there. If seed selection transferred, the tuned quantity would show up on the surface he
tuned against. Excellent private + poor public on disjoint 120-task splits is the signature of
variance, not of a tuned parameter.

**3. His tail probability is off by ~8x, and he never applies a multiple-comparisons correction.**
He normal-approximates Bin(120, 0.04) to get P(X≥12) ≈ 0.04%, "1 in 2,500". The normal
approximation badly understates the right tail of a skewed count. Exact:

    P(X ≥ 12 | n=120, p=0.04) = 0.00323   → 1 in 310

ARC Prize 2025 had **1,455 teams** (Kaggle `GetCompetition`: totalTeams=1455, totalCompetitors=1684,
totalSubmissions=15141). Expected number of teams reaching ≥12 solves by luck alone, at a 4% base
rate:

    0.00323 × 1455 ≈ 4.7 teams

He finished 5th. The count of pure-luck outliers a field that size should produce is *the same number
as the rank he got*. Even under a conservative reading where only ~300 teams ran a comparable
baseline, the expectation is ≈1 — still an ordinary draw, not a 1-in-2500 event.

Caveat, stated because it matters: not all 1,455 teams ran a ~4%-accurate baseline (many submitted
nothing scoring). So 4.7 is an upper estimate on expected lucky outliers. It does not need to be
exact — it needs to be O(1) or larger to kill "1 in 2,500", and it is.

**None of this is an accusation.** He's transparent about the fork, the seed, and the public/private
gap, and his closing section explicitly says solving ARC-AGI "fundamentally remains extremely
difficult". The writeup is honest. The inference drawn from it is wrong, and the wrongness is the
useful part.

## The actual finding

A benchmark where the top of the leaderboard is one shared baseline, scored all-or-nothing on 120
items at a ~4% solve rate, **cannot rank its top entrants**. σ = √(120·0.04·0.96) ≈ 2.15 solves.
The gap between 5th and 344th is roughly three standard deviations of pure noise on a metric whose
signal is 4.8 expected solves. The leaderboard measured luck. That is a property of the measurement
instrument, not of the entrants — and it is the thing ARC-3 has to avoid.

## What ARC-3 should take from it

### 1. Continuous scoring instead of binary clears — we already have the data

We have per-level optimal action counts for every authored game (g155: 8/14/15/22/23/31; g033:
53/101/111/147/147; g030: 9/11/16/19/24/30/35; g162: 16/20/25/29/32/34). ~6 levels × 50 games is
**~300 measurement points with real resolution**, versus 50 all-or-nothing bits. Scoring
actions-taken against optimal — plus levels-reached — turns a coin-flip leaderboard into one that
can separate agents. This is the cheapest available fix for exactly the failure above, and the
denominators are already computed and verifier-checked.

### 2. The differentiation loop is statistical power, not housekeeping

Correlated items shrink *effective* n below actual n: when games share mechanic, shape, palette and
AST structure, one capability solves several, outcomes covary, and Var(total) exceeds np(1−p) — the
noise floor rises and rank separation gets worse. Driving pairwise similarity down pushes effective
n back toward 50. That is a second, independent justification for the pair-differentiate cycles
beyond "the games shouldn't feel samey": **it is what makes a 50-item set able to measure anything
at all.** Same argument covers the topology gate — exotic lattices assigned by rarity rather than
need were a shared artifact across 10 games, i.e. correlated structure.

### 3. Report a distribution, not a number

Agents are stochastic even when our games are deterministic (they are — verified by double-render,
zero drift). N runs per agent, report median and spread. A single-run leaderboard number on 50
items is not a measurement. This is the direct antidote to seed-fishing: if the score *is* a
distribution, picking a lucky seed has nothing to buy.

### 4. Hold out games, properly

g500–g599 is an **id reservation** for Son, not a held-back eval set — different thing, don't
conflate them. If ARC-3 gets a public leaderboard, some fraction of authored games must never be
published, or the public set gets tuned against exactly like the ARC Prize public split was.

### 5. Watch for monoculture at the top

The 2025 top was variations on one notebook. Our analogue is a single shared agent harness
(`sonpham-org/try-harder-harness`). If every serious entrant runs one harness with different knobs,
the benchmark measures knob luck no matter how good the games are. Worth tracking, not worth acting
on yet.

## Endorsement worth noting

His own "what could be improved" list closes on **symbolic function generation** — program
synthesis / rule induction over direct grid prediction — as the fix for pixel-level fragility. That
is a competitor at the top of the 2025 board concluding the pixel-prediction path is the wrong one.
Consistent with where ARC-3's interactive framing already sits.
