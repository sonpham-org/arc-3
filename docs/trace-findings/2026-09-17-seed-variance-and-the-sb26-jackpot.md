<!--
Author: Claude Opus 5 (Bubba)
Date: 17-September-2026
PURPOSE: Records a top-competitor's verbatim statement that run-to-run seed variance is ~20% of
score and that harness work is near plateau, and tests it against our own four-pass 27B run.
Establishes the measured noise floor for total-score comparisons, identifies sb26 as the single
jackpot game that produces nearly all of that spread, and retires the compact-reasoning A/B's
+20.46 score delta as a seed artefact rather than a prompt effect. Ends with the metric change
this forces: paired per-game deltas, not arm totals.
SRP/DRY check: Pass — this is the variance/measurement-validity finding. The compact A/B's own
results live in docs/compact-reasoning-style-experiment.md and the zero-scoring game set in
docs/trace-findings/2026-09-17-the-slippery-seven.md; both are cited here, not restated.
-->

# Seed variance and the sb26 jackpot

## 1. What the competitor said

Relayed to #arc-3 by the Boss on 17-Sep-2026. A top-five competitor, currently scoring roughly
two points above us on the leaderboard; **name not given to me**, so this is attributed only as
stated.

> Yeah, I was thinking the same thing. It became much harder to track improvements, since std of
> the same sub across seeds is like 20% of the score, and harness work will probably plateau soon
>
> Though I doubt that I'll be able to finetune anything meaningful without spending half of my
> savings or having a teammate with access to clusters lol

Two separate claims, and both matter to us. The first is a measurement claim. The second is a
strategy claim, and it is the one with money attached.

## 2. The measurement claim checks out against our own data

He is describing the same submission re-run across seeds on the leaderboard. We have not measured
that. What we have measured is **sampling variance at temperature 1.0 across four passes of the
same 25 games** in `20260916_102724_qwen38-27b-massdata-25g-4p` — same model, same harness, same
catalog, same clock, same everything except the sampler's luck. Different measurement, same
question. Treat the agreement below as convergent evidence, not a replication.

Per-pass totals, from each run's own `final_score` in `artifacts/*_viewer_data.json`:

| pass | score | levels | games scoring |
|---|---|---|---|
| p0 | 53.03 | 16 | 12 |
| p1 | 57.39 | 17 | 14 |
| p2 | **82.55** | 20 | 15 |
| p3 | 50.90 | 15 | 12 |

Mean 60.97, range 31.65, best pass **1.62×** the worst.

- sample sd **14.64 = 24.0%** of the mean (n=4, so 3 df)
- population sd 12.68 = **20.8%** of the mean

His "like 20% of the score" lands inside that. Independent setup, independent measurement,
same order. **We should stop treating our own pass-to-pass spread as an anomaly of one run and
start treating it as the noise floor of this benchmark.**

Caveat that governs everything downstream: **n=4.** An sd on three degrees of freedom carries
roughly a 0.6×–3.7× confidence interval. Every number in §4 is an order of magnitude, not an
estimate.

## 3. One game of 25 produces nearly all of it

`sb26-7fbdac44` does not have a distribution so much as a coin flip.

| run | score | levels | actions per level |
|---|---|---|---|
| baseline `20260915_230835` p0 | 2.78 | 1 / 8 | 12, 59 |
| massdata p0 | 2.78 | 1 / 8 | 11, 57 |
| massdata p1 | 2.78 | 1 / 8 | 10, 51 |
| massdata p2 | **27.78** | **4 / 8** | 11, 41, 15, 16, 17 |
| massdata p3 | 2.78 | 1 / 8 | 9, 52 |

Level 2 is a wall it clears about one try in four, and when it clears it, it runs on through
levels 3, 4 and 5 for ten times the points. Nothing changed between those passes.

Drop that one game and the run stops being noisy:

| | pass totals | mean | sd | CV |
|---|---|---|---|---|
| all 25 games | 53.03 / 57.39 / 82.55 / 50.90 | 60.97 | 14.64 | **24.0%** |
| 24 games, minus `sb26` | 50.25 / 54.62 / 54.77 / 48.12 | 51.94 | 3.30 | **6.3%** |

One game of twenty-five drives the run-to-run spread; excluding it takes the coefficient of
variation from 24% to 6%. (With n=4 and a single jackpot event, a variance decomposition
*must* attribute most of the spread to the outlier — the direction is solid, the share is not a
figure to quote.)

`sb26` is not the only such game, only the loudest. `cn04` and `ka59` score in two passes and
zero in the other two; `ls20` and `wa30` score in one of four. Bimodal level-clears, not
Gaussian jitter around a mean.

## 4. What this costs to measure

Using sd = 14.64 per single pass, a two-arm comparison where the 95% interval on the difference
excludes zero needs roughly:

| difference to detect | passes per arm |
|---|---|
| 20 points | ~5 |
| 10 points | ~17 |
| 5 points | ~66 |

That is the *interval-excludes-zero* threshold, not 80% power — for power, roughly double it.
And on 3 df the sd itself is soft, so read these as **tens of passes, not a handful**. A pass of
25 games at concurrency 25 costs about four hours of a108. A clean 10-point A/B is on the order
of a week of GPU per arm.

**Total-score A/B on this benchmark is, for practical purposes, unaffordable to us.** That is the
real content of "it became much harder to track improvements."

## 5. This retires the compact-reasoning score result

`docs/compact-reasoning-style-experiment.md` reports the `ARC3_REASONING_STYLE` arm scoring
**59.24 against the 38.79 baseline, +20.46** — with the honest note already attached that `sb26`
alone moved +23.37 (2.78 → 26.14, 1 level → 4) and that dropping it makes the delta **−2.91**.

Section 3 explains why. The compact arm's `sb26` result — **26.14, four levels** — sits squarely
inside the *baseline* model's own distribution for that game: 27.78 at four levels, reached in
one of four identical passes with no prompt change whatsoever. The compact arm rolled the same
result the unmodified harness rolls about a quarter of the time.

So the +20.46 is not evidence the prompt helped. Both arms were single passes; the sd of a
difference between two single passes is about 14.64 × √2 ≈ 20.7. **The observed delta is under
one sigma of pure sampling noise, and its mechanism is a game we can watch produce that exact
delta unprompted.** Not a weakened claim — a retired one.

(The 26.14 figure is cited from the compact A/B write-up; I have not re-verified it against the
a108 artefacts, which were not pulled local.)

## 6. What survives, and what we measure from now on

The same experiment's **efficiency** result is untouched by any of this, because it was measured
the right way: **paired, per game.** Tokens per action went 874 → 595, and **19 of 25 games
improved**, median ratio 0.56. As a sign test that is p = 0.0073 — significant on its own, with
no reliance on arm totals, and robust to any single game jackpotting.

That is the template:

1. **Score arm totals are not a usable A/B metric** at the pass counts we can afford. Stop
   reporting a single-pass total delta as a result. Our previous framing — "this needs several
   passes before the number means anything" — was directionally right and is now quantified.
2. **Compare paired per-game deltas** and report the count improved/same/worse plus a sign test.
3. **Report `sb26` separately** in any run summary, or exclude it and say so. It is a lottery
   ticket stapled to the scoreboard.
4. **Prefer low-variance proxies** — tokens per action, actions per hour, levels reached per
   game — over final score, wherever the hypothesis allows it.

## 7. The second claim is the strategic one

> I doubt that I'll be able to finetune anything meaningful without spending half of my savings
> or having a teammate with access to clusters

A competitor two points ahead of us says harness work is near plateau and that the next lever —
finetuning — is priced out of reach without cluster access.

We have two DGX Sparks. LoRA round 1 completed end-to-end on gx10-a424 on 17-Sep-2026: real
adapter on disk, 208/208 `lora_B` tensors nonzero, 39.6M trainable parameters, zero OOMs
(`docs/` LoRA round-1 write-up and PR #35). The pipeline is proven; the adapter is unevaluated
and the eight-step loss was flat, so nothing is *learned* yet. But the constraint he names as
blocking is a constraint we do not have, and a424 is sitting idle.

Read §4 and §7 together: the lever he expects to plateau is the one we were spending GPU hours
A/B-testing with a metric too noisy to resolve the result. **The Sparks are better spent on the
lever he can't pull than on harness A/Bs we can't measure.** That is a call for the Boss, not
for me, but the evidence points one way.

## 8. Not verified

1. The competitor's identity, his actual leaderboard position, and the "two points" gap — all
   as relayed; I have not seen the leaderboard.
2. His "20%" is across seeds of one submission on the official leaderboard. Ours is across four
   temperature-1.0 passes of one local run. Same order, not the same quantity.
3. n = 4. Every sd, CV and pass-count figure here rests on four numbers.
4. `sb26`'s one-in-four clear rate is 2 observations of 6 local runs (massdata p2 and the
   compact arm). It is a rough rate, not a measured probability.
5. The compact arm's 26.14 / four levels is cited from that experiment's write-up, not
   re-derived from a108 artefacts.
6. Whether the level-2 clear on `sb26` is genuinely stochastic or triggered by some reachable
   state the model sometimes stumbles into — nobody has read those four transcripts side by
   side. That is the obvious next read, and it is free.
7. No test of whether pass-to-pass variance differs by model; all figures are `qwen38-27b-nvfp4`.
8. The power doubling in §4 is a rule of thumb, not a computed power analysis.
