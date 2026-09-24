<!--
Author: Claude Opus 5.5 (Bubba)
Date: 23-September-2026
PURPOSE: Records the first cut of the free-energy-inspired offline trace analysis requested by
OpenMind in #arc-3 (Boss said go, 17:06 ET): what the script computes, the modelling choices, the
result on the first three traces of the 7.36 Kaggle run, and the known limits. No harness, prompt
or job was changed.
SRP/DRY check: Pass - companion to 2026-09-23-novelty-vs-solves.md (count novelty over windows);
this one adds Dirichlet information gain and Bayesian surprise per step.
-->

# FEP-style scoring of ARC-3 traces: first three traces (23-Sep-2026)

Script: ~/GitHub/arc-3/ARC3-Inference/distill/efe_trace_analysis.py (not committed).
Output: distill/results/efe_trace_analysis/ (first3.txt, one .efe.json per trace).
Traces: the first three event logs with actions in the 7.36 Kaggle run (Flash-Next):
Buoyant Pontoons, Coded Notches, Deck Control.

## What it computes

Replays each trace without changing it. Per context c, a Dirichlet over outcome classes. At each step:
- EIG of every candidate context = I(o; theta) = H[E p] - E[H p] (closed form, digamma), i.e. the
  book's novelty term for the transition parameters. Candidates = valid buttons + every distinct
  object type on the pre-action board when clicking is valid.
- Which EIG tier the agent's actual choice was in (tie-aware).
- After the outcome: surprisal -ln p(o|c) and Bayesian surprise KL[post || prior].
- Pragmatic side only as p(level clear | c); goal hidden, so it stays near the prior.

Modelling choices:
- Button context = action id. Click context = object TYPE (normalised shape; position and colour
  dropped), so identical pieces are one thing to learn about and recolour/move keep the key.
  (First version keyed clicks by position; seven clicks on seven identical pontoons each looked
  maximally novel and every metric sat at its prior constant. Fixed.)
- Outcome = nothing | level_clear | game_over | changed~2^k (log2 of changed cells), fixed support.
  --outcome fine also keys on colour transitions (support grows, outcomes fragment).
- HUD: whole edge rows/columns changing on most steps are masked (Buoyant Pontoons' bottom step bar).

## First result (three traces, not a conclusion)

Per step, the agent picked a top-EIG candidate only about a tenth of the time in all three; about
nine in ten steps were repeats of an already-tried context while untried ones were available.
Clear example: Buoyant Pontoons, level one, it clicked the same pontoon type seven times running
while other object types were never probed. Bayesian surprise spikes flag the steps where a
repeated context did something new (a bigger change), which is the signal worth looking at next.

## Known limits

- With fixed support and symmetric prior, EIG ranking = inverse visit count. The chosen-vs-best
  side restates count novelty (already null against solves in 2026-09-23-novelty-vs-solves.md).
  The new axis is the realised side: surprisal and Bayesian surprise.
- Button context ignores avatar position (right into a wall = right in open space).
- Size-only outcomes cannot tell "moved left" from "moved right".
- Edge-line HUD masking may eat a meaningful edge strip (Skewer Kebabs answer key); check before
  widening the trace set.
- Three traces. Nothing here says the novelty term would win levels.

## Next 30 traces (OpenMind, 17:51 ET)

Order: remaining traces with actions in the 7.36 run (Mirror Rendezvous, Skewer Kebabs, Toggle
Navigator, Trail Unwind; the rest of that folder holds no actions), then arm A and arm B of the
23-Sep prompt arms, both passes. Runtime: 15.5 s wall for all 30 on the Mac Mini (single process).
Table: distill/results/efe_trace_analysis/next30_table.txt; per-step output next30.txt; JSON next30/.

- Top-EIG choice share: median 0.08 (range 0.02 to 0.31). Highest: Trail Unwind (0.31), Locksmith
  (about 0.2), both small button sets. Lowest: Functional Tiles and Skewer Kebabs (0.02 to 0.04).
- Traces with a level clear vs none: top-EIG median 0.08 vs 0.05, Bayesian surprise per step 0.118
  vs 0.085. Confounded by trace length (failed traces run longer, and long traces exhaust fresh
  contexts), 22 vs 8 traces: not evidence either way.
- repeat_share (0.85 to 0.98) is near-trivial on long traces with few contexts; do not read it.
- HUD check: Skewer Kebabs had nothing masked in all three of its traces, so the answer-key strip
  was not eaten. Sixty-four masked cells = one edge line (the step bar) elsewhere.

## Next 20 traces (OpenMind, 17:53 ET)

Traces 34-53: the last two of arm B (Toggle Navigator), all fourteen of arm C, and four passes of
Buoyant Pontoons from arc3-job1-control. Runtime 22.3 s wall on the Mac Mini. Table:
distill/results/efe_trace_analysis/next20_table.txt; per-step next20.txt; JSON next20/.

- Top-EIG choice share median 0.08 again (0.03 Functional Tiles to 0.23 Locksmith).
- Clear vs no clear, these 20: top-EIG median 0.08 vs 0.08; Bayesian surprise per step 0.134 vs
  0.147. Pooled with the previous 30 (50 traces): 0.08 vs 0.07, surprise 0.132 vs 0.096.
  Correlation of top-EIG share with log trace length: -0.24. No separation.
- Arm C's Skewer Kebabs clear (pass two) came at a top-EIG share of 0.04, same as its failed plays:
  that solve was not an exploration outlier by this measure.
- Skewer Kebabs: nothing masked as HUD in any of its seven traces so far.
- Script fix: run names now come from the folder above artifacts/ (or above output/), so job-output
  traces no longer collide on file names.

## Learned perception with EBUL, first 53 traces (OpenMind, 17:58 ET)

Question: is there perception? Before this, only hand-built: connected components, shape-type keys,
log2 change-size buckets. Added distill/ebul_perception.py: two hidden tanh layers (12, 8) trained
without labels by EBUL (distill/ebul.py, copied unchanged from the #ebul channel script), greedy
layer-wise GA toward 8 then 5 gzip bits/sample; the percept is the ternary code of layer two.
A board net gives button contexts (button, board code); a patch net (9x9 window) gives click
contexts and click candidates (one patch per object centre). Same Dirichlet model and outcomes.

"Better" = prequential code length: mean surprisal of each outcome before it is seen (nats/step,
lower = contexts predict what actions do; over-splitting pays the prior cost of fresh contexts).

| arm | nats/step (pooled) | median trace | beats handmade on | top-EIG median | analysis time |
|---|---|---|---|---|---|
| none (button id, one click context) | 1.527 | 1.671 | 17/53 | 0.14 | 4 s |
| handmade (shape type) | 1.565 | 1.688 | - | 0.08 | 23 s |
| handstate (+ exact coarse board hash) | 1.557 | 1.662 | 6/53 | 0.09 | 27 s |
| random two-layer net (control) | 1.788 | 2.041 | 6/53 | 0.18 | 58 s |
| EBUL two-layer net | 1.588 | 1.722 | 11/53 | 0.06 | 56 s |

Second seed: EBUL 1.592, random 1.790, EBUL beats handmade on 9/53. EBUL training took about
40 s per seed (1500 boards and 1500 patches); whole comparison run 3.5 min wall on the Mac Mini.
EBUL codes: 42-46 board codes and 67-71 patch codes on the training set; random nets 122-460.

Reading: EBUL is clearly better than the same network with random weights (it learns a coarser,
more reusable code), but not better than the hand-built perception, and no perception at all
predicts outcomes best. That last point is the real finding: outcomes are described only by how
many cells changed, which barely depends on what or where you press, so finer contexts only pay
prior cost. Perception cannot help until it also describes the outcome (what changed and how).
Next step: encode the change (post minus pre patch) with the same EBUL net as the outcome class.
Clear vs no-clear top-EIG split stays small under every arm. One run per seed, two seeds.

## Round two: conv front end, width 120, learned outcomes (OpenMind, 18:19 ET)

Script distill/ebul_perception_conv.py; log distill/results/efe_trace_analysis/conv53.log.
18 fixed kernels (difference x, y, both diagonals; Ricker hats 3/5/7 along x, y, both diagonals;
isotropic hats 3/5) on colour and foreground channels (change: changed-mask, before, after),
pooled mean |response|. Outcome = EBUL code of the 9x9 change crop (12/8 net, 63 codes, fixed
support + <novel>; novel share 0.16). ebul.py gained parallel fitness (same GA, verified identical).
Timing: features 13 s, outcome + narrow nets 19 s, two wide 120/120 nets 214 s (12 processes),
seven analysis arms about 6 min. Total about 11 min wall.

| arm | nats/step | vs flat |
|---|---|---|
| flat (one context) | 2.081 | 0 |
| none | 2.441 | -0.36 |
| handmade | 2.649 | -0.57 |
| handstate | 2.669 | -0.59 |
| EBUL narrow | 2.615 | -0.53 |
| random conv 120 | 3.101 | -1.02 |
| EBUL conv 120 | 3.094 | -1.01 |

Two problems, both mine:
1. Wide EBUL did not converge: 114 (board) and 135 (patch) gzip bits/sample against a target of 5,
   about 800 distinct codes per 1000 training samples, i.e. nearly every board is its own context.
   With 78k weights, 60 GA generations of Gaussian mutation barely move it. Same as random weights.
2. The scoring punishes every split: each fresh context starts from a flat Dirichlet(1) over 67
   outcome classes, so its first prediction costs about ln 67 = 4.2 nats. With learned outcomes this
   cost dominates, so the single-context arm wins. Fix: back each context's prior off to the global
   outcome distribution (alpha_c = counts_c + beta * p_global), a hierarchical Dirichlet.

## Round three: back-off prior, wide nets at 300 generations (OpenMind, 18:46 ET)

Changes (distill/, not committed):
- efe_trace_analysis.py: optional hierarchical back-off prior, `analyse(..., prior="backoff")` /
  `--prior backoff`: alpha_c(o) = count_c(o) + BETA * p_global(o), p_global(o) = (G(o) + 1) / (N + K),
  pooled over every context of the trace so far, BETA = 2.0. Surprisal, EIG and Bayesian surprise use
  the same formulas on the new alpha; the global counts move only after the step's KL is taken.
  Default stays flat: the default run is byte-identical to the pre-edit output
  (results/efe_trace_analysis/first3_pre_backoff.txt) and all 190 step rows match first3.txt.
- ebul_perception_conv.py: encoders + outcome alphabet pickled to results/efe_trace_analysis/conv53/
  encoders.pkl with the trace list and settings; `--load` skips training and refuses a mismatch;
  `--prior {flat,backoff}`; `--wide-gens` (width-120 layers only; outcome and narrow nets stay at 60);
  scoring runs all (arm, trace) pairs in 12 processes (checked equal to the serial loop).
- ebul_perception.py: GENS / GA_VERBOSE pass-throughs; board-code cache keyed on the board object
  instead of id() (no effect on these numbers: the flat re-score below reproduces round two exactly
  for the six arms whose encoders did not change).

Wide nets after 300 generations (one run, seed 0; round two at 60 generations in brackets):
board 120/120: layer one 70.3 bits/sample (target 8), layer two 79.6 (target 5), 602 distinct codes
per 1000 (824). Patch 120/120: layer one 96.6, layer two 57.4 (135), 327 distinct codes (790).
Random 120/120 for reference: 132.9 / 190.6 bits, 830 / 800 codes. Five times the generations roughly
halved the patch code and cut the board code by a third, but both are still 11-16x over target and
the GA was still creeping at generation 299 (Gaussian mutation on ~78k weights). Not converged.

53 traces, same learned outcome alphabet (63 change codes + nothing/level_clear/game_over/novel,
novel share 0.162), same encoders in both columns:

| arm | backoff nats/step | gain vs flat | beats handmade | top-EIG median | flat-prior nats/step (gain) |
|---|---|---|---|---|---|
| flat (one context) | 1.533 | 0 | 43/53 | 1.00 | 2.081 (0) |
| none | 1.609 | -0.075 | 20/53 | 0.14 | 2.441 (-0.360) |
| handmade | 1.616 | -0.083 | - | 0.08 | 2.649 (-0.568) |
| handstate | 1.582 | -0.049 | 14/53 | 0.09 | 2.669 (-0.588) |
| EBUL narrow 12/8 | 1.634 | -0.100 | 14/53 | 0.06 | 2.615 (-0.534) |
| random conv 120 | 1.724 | -0.190 | 12/53 | 0.20 | 3.101 (-1.020) |
| EBUL conv 120 (300 gens) | 1.658 | -0.125 | 16/53 | 0.14 | 2.788 (-0.707) |

Timings (wall, Mac Mini, load average 13-18 from other work throughout): features 13.8 s; outcome coder
+ narrow nets 20.1 s; wide board net 309.5 s; wide patch net 382.7 s (wide total 692.2 s); scoring
seven arms 45.1 s (12 processes; was about 6 min serial); whole training + backoff run 771 s. The
flat re-score with `--load` took 44.9 s end to end.

Reading:
- The back-off prior changes two things at once: the SHAPE of a fresh context's prior (the trace's
  outcome distribution instead of uniform) and its total MASS (BETA = 2 instead of K ~ 67). Separated
  with a BETA = 67 rescore (same mass as flat, back-off shape): flat arm 2.081 -> 1.776, handmade gap
  0.568 -> 0.126. So the shape removes most of the split penalty; the lower mass then sharpens every
  arm further (flat 1.533 at BETA = 2), most of all the arms with the most data per context.
- It does not change the ranking. The single context still predicts outcomes best; every perception
  arm, hand-built or learned, costs more than it buys. So the round-two conclusion was not an artifact
  of the flat prior: on these traces, what an action does to the board barely depends on which
  context any of these perceptions puts it in (with the outcome coder we have).
- More generations helped the wide EBUL nets (flat prior: 3.094 at 60 generations -> 2.788 at 300;
  under backoff now clearly better than random wide weights, 1.658 vs 1.724), but they are still unconverged and still worse
  than handmade (1.658 vs 1.616), handstate, none, and the narrow EBUL net.
- Verdict: learned perception with the conv front end and width 120 is NOT better than hand-built
  perception here. It beats handmade on 16/53 traces, not on the pooled score.
- BETA sensitivity (same saved encoders, `--load`, about 50-60 s each): gain vs flat at BETA 2 / 10 / 67
  is handmade -0.083 / -0.116 / -0.126, handstate -0.049 / -0.098 / -0.122, none -0.075 / -0.086 /
  -0.084, EBUL narrow -0.100 / -0.123 / -0.123, EBUL conv120 -0.125 / -0.159 / -0.147, random conv120
  -0.190 / -0.229 / -0.191. Stronger back-off does not close the gaps; they widen slightly. Flat is
  first at every BETA tried, and EBUL conv120 stays behind handmade at every BETA.
- Trust check: the flat-prior re-score reproduces round two's pooled nats/step exactly for the six
  arms whose encoders did not change (2.081, 2.441, 2.649, 2.669, 2.615, 3.101); only the retrained
  wide EBUL net moved. That validates the pickle round trip, the parallel scorer and the cache change.
- One seed, one run of the wide training.

Logs: results/efe_trace_analysis/conv53_r3_backoff.log, conv53_r3_flat.log, conv53_r3_backoff_beta10.log,
conv53_r3_backoff_beta67.log; arms in conv53/arms_r3_*.json
(round two's conv53/arms.json left untouched). Provenance: project:arc3 event
aebfe859-b26a-4dca-9d77-c4af8e5f7298 (caused by d3feb27b-1b05-41e5-9cc2-23120afc0e77).

## Round four: object events, agency, predictive EBUL (OpenMind, 19:20 ET)

Expert-debate plan items 1, 2, 3, 4, 7 and 5 (log: ~/bubba-workspace/docs/arc3-expert-debate-log.txt,
entry 1). New files only, all in distill/ (not committed): object_events.py (item 2),
agency_contexts.py (item 3), heldout_yardstick.py (items 1, 5, 7), ebul_predictive.py (item 4),
round4.py (driver). Results: distill/results/efe_trace_analysis/round4/ (table.md, results.json with
per-trace nats, labels.txt, agency.txt, heads.json, run.log, timings.json). efe_trace_analysis.py and
ebul_perception_conv.py were NOT edited: the back-off prior (Beliefs(prior="backoff"), beta 2) is
imported as is, and the type prior is a subclass that overrides base() only.

### First: a bug in the earlier rounds

efe_trace_analysis.analyse never moves `pre` forward after a normal step (only after a RESET), so in
rounds one to three every step's outcome and every click context was computed against the board the
level (really: the play) STARTED from, not the board just before the action. Found while checking the
new scorer against analyse(): step one agreed exactly, from step two on the labels differed. On
round one's own outcome (size buckets, back-off, all 53, in-sample): "nothing" is 1.4% of steps as
scored, 10.7% with the right board; handmade's gain over flat goes from 0.07 to 0.24 nats/step,
none's from -0.01 to +0.16. Round three's own setup, re-scored read-only (its pickled learned
change-crop coder from conv53/encoders.pkl, back-off, all 53 in-sample; round4/stale_board_conv_check.json,
17 s): as scored it reproduces exactly (flat 1.533, none 1.609, handmade 1.616); with the right board
flat 1.228, none 1.217, handmade 1.179, i.e. gains vs flat go from -0.075 / -0.083 to +0.011 / +0.049.
So the bug flipped round three's sign ("one context predicts best"); the size of the round-four gains
below comes mostly from the object-event outcome.
Fix is one line (`pre = post` at the end of the loop in analyse); not applied, because that file
belongs to the round-three work and the brief allowed only additive hooks there. Every number below
uses the right board (the round-four scorer replays steps itself).

### Method

- Outcome (item 2, hand-built): components (4-connected, same colour, HUD lines masked, background
  above 512 cells ignored) touching the changed area are matched pre->post: unchanged, moved (dx, dy,
  greedy nearest among same colour+shape), recoloured in place (from, to), grew/shrank/reshaped (same
  colour, overlapping), vanished, appeared; plus nothing / level_clear / game_over / bgchange. Label =
  sorted multiset, dx/dy clipped to -3..3, counts 1/2/3+. Support = training-fold labels + <novel>.
  385 labels on all 53 traces; per game 11 (Toggle Navigator) to 84 (Locksmith), more than the ~20
  the panel expected, mostly from counts and the floor "grow|shrink" a moving piece leaves behind.
  Examples: Toggle Navigator rc1>5, rc5>1, nothing; Functional Tiles rc8>12, rc9>8; Streaming Purple
  mv+3+0, mv-3+0; Mirror Rendezvous mv+3+0|mv-3+0 (the mirrored pair); Locksmith
  grow|mv+0-3x2|shrink. Coding all 53 traces: 3.5 s wall.
- Contexts (item 3): the controlled object is found online as the object type (colour + shape) with
  the most evidence N * I(button; displacement) (plug-in mutual information, >= 3 nats), built only
  from steps already seen; button context = (button, what the object would move into: free / edge /
  wall colour / object colour), with explicit "noagent" / "nodir" / "lost" before it is known. Click
  context = handmade shape type + touching another object or not. Found per trace: Buoyant Pontoons,
  Locksmith, Streaming Purple, Deck Control, Trail Unwind, Coded Notches (but "lost" on 76% of its
  button steps), Skewer Kebabs (not yet known on 52% of button steps); Mirror Rendezvous never.
  Control arms added after seeing item 4: handcolour / agency-colour = click context also keys on the
  clicked cell's colour (the handmade key drops colour on purpose).
- Yardstick (item 1): prequential nats/step under the back-off prior. Two cross-fitted splits, every
  trace scored exactly once by a model built on the other fold: "pass" (as asked: p0/p2 vs p1/p3;
  novel test labels 9.5%) and "game" (whole games held out, folds balanced by type; 74% of test labels
  never occur in the training games, so there the vocabulary is open: new labels join online through
  the unseen slot). Paired bootstrap over traces (2000 replicates; both arms recomputed on the same
  resample, step-weighted) plus a game-cluster bootstrap. Game type from the valid-action list:
  click = Toggle Navigator, Functional Tiles, Sliding Indicator (18 traces); button = Locksmith, Trail
  Unwind (7); mixed = the other six games (28).
- Predictive EBUL (item 4): PCA (24 dims, training fold only) of the fixed conv features of round
  two (board features for buttons, 9x9 patch at the click), then two 24 -> 6 tanh heads ternarised as
  EBUL does (300 parameters), searched by antithetic ES (20 pairs, 300 iterations, Adam, centred
  ranks, early stopping on a validation quarter of the training traces). Fitness "dm" = nats/step of
  outcome code length given the action minus given (action, code), Dirichlet-multinomial with the
  yardstick's back-off base, minus 0.02 * |H(code) - 3 bits|; "gzip" = the literal gzip version;
  "entropy" = EBUL's own objective on the same head (gzip bits/sample -> 5); "random" = initial
  weights. Two seeds each. ebul.py untouched (layer, ternarise rule and gzip measure imported).
- Carry (item 7): "carry" keeps one Dirichlet (and one agency tracker) per game across its test
  traces in run-then-pass order; "prime" (pass split) first feeds that game's training-fold passes
  through it unscored; "type" backs the trace-level distribution off to the training fold's outcome
  distribution for the same game type instead of uniform.
- Pragmatic (item 5): C(o) = p(clear within 5 actions | outcome o) on the training fold; per test
  step, pragmatic value = sum_o p(o | context) C(o) before the outcome. AUC against "a clear within
  the next 5 actions", pooled and WITHIN trace (pairs from the same trace only; pooled AUC mostly tells
  clear-rich traces from clear-poor ones).

### Results (pass split, 53 traces, 6380 steps; gain = flat nats minus arm nats, 95% CI over traces)

| arm | nats/step | gain vs flat | click | button | mixed |
|---|---|---|---|---|---|
| flat (one context) | 2.751 [2.463, 3.019] | 0 | 0 | 0 | 0 |
| none (button id) | 2.291 | +0.459 [+0.300, +0.603] | 0.000 | +0.894 | +0.704 |
| handmade | 2.230 | +0.521 [+0.381, +0.649] | +0.156 | +0.894 | +0.701 |
| handstate | 2.372 | +0.378 [+0.241, +0.507] | +0.156 | +0.793 | +0.399 |
| agency | 2.197 | +0.553 [+0.384, +0.719] | +0.207 | +1.227 | +0.572 |
| handcolour (control) | 2.017 | +0.734 [+0.627, +0.823] | +0.694 | +0.894 | +0.696 |
| agency-colour | 2.003 | +0.748 [+0.582, +0.886] | +0.697 | +1.227 | +0.568 |
| EBUL predictive (dm) seed 0 / 1 | 2.118 / 2.189 | +0.633 [+0.490, +0.754] / +0.562 [+0.417, +0.683] | +0.682 / +0.562 | +1.030 / +1.034 | +0.393 / +0.334 |
| EBUL predictive (gzip) s0 / s1 | 2.344 / 2.347 | +0.407 / +0.404 | +0.410 / +0.373 | +0.850 / +0.891 | +0.192 / +0.201 |
| EBUL entropy-only s0 / s1 | 2.538 / 2.559 | +0.213 / +0.192 | +0.174 / +0.145 | +0.501 / +0.618 | +0.112 / +0.033 |
| random head s0 / s1 | 2.792 / 2.767 | -0.041 / -0.016 | -0.139 / -0.131 | +0.444 / +0.528 | -0.178 / -0.163 |
| agency + carry across passes/runs | 2.012 | +0.738 [+0.545, +0.921] | +0.280 | +1.233 | +0.953 |
| agency + carry + type prior | 1.931 | +0.820 [+0.629, +1.003] | +0.354 | +1.325 | +1.039 |
| agency + carry + prime (other passes) | 1.790 [1.595, 1.981] | +0.961 [+0.771, +1.159] | +0.515 | +1.493 | +1.146 |

Game split (whole games held out), same arms: flat 3.051; none +0.557; handmade +0.630; agency
+0.684 [+0.521, +0.838]; handcolour +0.846; agency-colour +0.881 [+0.740, +1.005]; EBUL dm +0.423 /
+0.427, entropy +0.448 / +0.416, random +0.434 / +0.429; agency + carry +0.970 [+0.749, +1.177].
Game-cluster CIs are roughly twice as wide (e.g. agency pass +0.20 to +0.89): eleven games.

Paired, pass split (positive = first arm better): agency vs handmade +0.03 [-0.06, +0.13]; button
games +0.33 [+0.10, +0.46]; mixed -0.13 [-0.18, -0.08]. Touching flag on clicks +0.02 [-0.02, +0.09].
Colour on clicks +0.21 [+0.11, +0.33] (click games +0.54). EBUL dm vs entropy-only +0.42 [+0.35,
+0.50] / +0.37 [+0.29, +0.45]; vs random +0.67 / +0.58; vs gzip fitness +0.23 / +0.16; vs handmade
+0.11 [-0.03, +0.26] / +0.04 [-0.09, +0.17]; vs handcolour -0.10 [-0.20, -0.02] / -0.17 [-0.27,
-0.08]. Game split: EBUL dm vs handmade -0.21 [-0.33, -0.07] / -0.20 [-0.32, -0.08]; vs random -0.01
/ -0.00 (no transfer).

Carry, gain over the same arm fresh (pass split): carry +0.15 to +0.19 (agency +0.19 [+0.08, +0.31]);
type prior +0.11 to +0.21; carry + prime +0.28 to +0.41 (agency +0.41 [+0.26, +0.56]). Game split:
carry +0.15 to +0.29 (agency +0.29 [+0.16, +0.40]); type prior from OTHER games -0.13 to -0.16 (hurts).

Pragmatic, within-trace AUC (pass split): agency 0.59 [0.53, 0.65], handmade 0.57 [0.51, 0.63], none
0.51, flat 0.43; "actions since the level started" baseline 0.55 [0.46, 0.65]. Pooled AUCs look
better (agency 0.73) but that is between-trace. Game split within-trace: 0.39 to 0.46, below chance.

Timings (wall, Mac Mini, 8 processes, load average about 20 from other work): event coding 3.5 s;
conv features 1.4 s; stale-board check 5.6 s; 32 head searches 54.5 s (dm about 6 s each, gzip 8 s,
entropy-only 20-29 s); scoring about 230 arm x fold jobs 32.7 s; bootstraps 37.1 s; total 135 s.

### Verdicts

1. Yardstick: done and it now separates arms, with held-out folds, paired CIs, per type, two seeds
   for learned heads. Its biggest effect was exposing the stale-board bug above.
2. Object events: helped. With them (and the right board) every context arm beats one context by 0.4
   to 0.75 nats/step; the ranking of rounds one to three reverses. Alphabet is bigger than hoped.
3. Agency: helps where there is an avatar (button games +0.33 over handmade, CI clear of zero), hurts
   in mixed games (-0.13), a wash overall. The single most useful hand-built addition turned out to be
   the clicked object's colour (+0.21 overall, +0.54 in click games).
4. Predictive EBUL: the predictive job clearly matters (+0.4 nats/step over entropy-only, +0.6 over
   random, both seeds), and DM beats the literal gzip fitness. But its win over handmade is the colour
   it sees in click games; hand-built colour beats it (-0.10 / -0.17), and it does not transfer to
   unseen games (equal to random heads there). F2's minority note stands: keep it only where no
   hand-built description exists.
5. Pragmatic: not established. Within a trace it barely beats "how long into the level", and it
   does not carry to unseen games.
7. Carry: helped in both splits (+0.15 to +0.29 from keeping counts across passes and runs, +0.28 to
   +0.41 when earlier passes of the same game are primed in). The game-type prior helps only when the
   same games are in training; from other games it hurts.

## Correction: stale "before" board in efe_trace_analysis.analyse (fixed 23-Sep-2026 ~19:45 ET)

Found by the round-four agent. The analyse loop never advanced the pre-action board except after a
RESET, so every step was compared with the board the play started from. Affected: the first-3,
next-30 and next-20 tables, and the scoring in rounds one to three (round-three encoders were trained
on correctly paired boards; only scoring was stale). Round four used its own correct scorer and also
re-scored round three with the right board: there handmade and none beat one-context. Fix: one line,
pre = post at the end of the loop (bubba). Default outputs after the fix no longer match first3.txt.
Rerun of the 53 traces with the fix (21 s): top-EIG share median 0.081 (0.01-0.30), unchanged in
substance; clear vs no-clear 0.091 vs 0.080, Bayesian surprise 0.117 vs 0.128: still no separation.
Output: distill/results/efe_trace_analysis/fixed53(.txt). Round one to three tables stand corrected by
round four's re-score; do not quote them.

## Round five: EBUL-predictive and hand-built colour in parallel, no retraining (OpenMind, 19:45 ET)

Script distill/round5_combo.py; results round5/ (table.md, results.json, heads_dm.pkl). Round four had
not saved the head weights, so the round-four "dm" heads were regenerated with the identical seeded job;
all eight (2 splits x 2 folds x 2 seeds) reproduce round4/heads.json diagnostics exactly and the
reference arms reproduce round four exactly (handcolour 2.017, EBUL dm 2.118 / 2.189), so these are the
same nets, not retrained. Heads now pickled. Within one play only (no carry: a scored run plays each
game once). joint = one context (handcolour key, EBUL code); mix = two count models, 50/50 average of
their predictions; bma = same two models weighted by their running likelihood within the play.

## split pass (within one play, back-off prior, event outcomes)
| arm | nats/step | gain vs flat | gain vs handcolour | click | button | mixed (vs handcolour) |
|---|---|---|---|---|---|---|
| flat | 2.751 | +0.000 [+0.000, +0.000] | -0.734 [-0.823, -0.627] | -0.694 | -0.894 | -0.696 |
| handcolour | 2.017 | +0.734 [+0.627, +0.823] | +0.000 [+0.000, +0.000] | +0.000 | +0.000 | +0.000 |
| ebul-dm-s0 | 2.118 | +0.633 [+0.490, +0.754] | -0.101 [-0.201, -0.011] | -0.012 | +0.136 | -0.303 |
| ebul-dm-s1 | 2.189 | +0.562 [+0.417, +0.683] | -0.172 [-0.266, -0.081] | -0.131 | +0.140 | -0.362 |
| joint-s0 | 2.136 | +0.614 [+0.464, +0.741] | -0.119 [-0.210, -0.033] | -0.054 | +0.136 | -0.306 |
| joint-s1 | 2.185 | +0.566 [+0.402, +0.705] | -0.168 [-0.266, -0.072] | -0.125 | +0.140 | -0.359 |
| mix-s0 | 1.938 | +0.813 [+0.693, +0.912] | +0.079 [+0.032, +0.125] | +0.100 | +0.223 | -0.011 |
| mix-s1 | 1.954 | +0.797 [+0.674, +0.896] | +0.063 [+0.018, +0.110] | +0.058 | +0.222 | -0.008 |
| bma-s0 | 1.940 | +0.811 [+0.698, +0.905] | +0.077 [+0.038, +0.117] | +0.115 | +0.148 | +0.006 |
| bma-s1 | 1.963 | +0.787 [+0.674, +0.879] | +0.054 [+0.018, +0.097] | +0.067 | +0.151 | -0.006 |

## split game (within one play, back-off prior, event outcomes)
| arm | nats/step | gain vs flat | gain vs handcolour | click | button | mixed (vs handcolour) |
|---|---|---|---|---|---|---|
| flat | 3.051 | +0.000 [+0.000, +0.000] | -0.846 [-0.920, -0.762] | -0.723 | -1.034 | -0.878 |
| handcolour | 2.205 | +0.846 [+0.762, +0.920] | +0.000 [+0.000, +0.000] | +0.000 | +0.000 | +0.000 |
| ebul-dm-s0 | 2.628 | +0.423 [+0.280, +0.553] | -0.423 [-0.541, -0.312] | -0.584 | -0.061 | -0.437 |
| ebul-dm-s1 | 2.623 | +0.427 [+0.287, +0.558] | -0.419 [-0.553, -0.284] | -0.535 | -0.189 | -0.414 |
| joint-s0 | 2.601 | +0.450 [+0.310, +0.577] | -0.396 [-0.513, -0.283] | -0.519 | -0.061 | -0.436 |
| joint-s1 | 2.542 | +0.509 [+0.382, +0.634] | -0.337 [-0.456, -0.220] | -0.333 | -0.189 | -0.413 |
| mix-s0 | 2.224 | +0.827 [+0.734, +0.910] | -0.019 [-0.062, +0.022] | -0.100 | +0.103 | +0.002 |
| mix-s1 | 2.208 | +0.843 [+0.757, +0.924] | -0.003 [-0.054, +0.052] | -0.068 | +0.101 | +0.011 |
| bma-s0 | 2.205 | +0.846 [+0.761, +0.921] | +0.000 [-0.005, +0.007] | -0.001 | +0.008 | -0.003 |
| bma-s1 | 2.168 | +0.883 [+0.809, +0.952] | +0.037 [+0.006, +0.080] | +0.089 | -0.003 | +0.004 |

timings: {"load_features_folds_s": 5.1, "regenerate_heads_s": 7.6, "scoring_s": 12.8, "total_s": 27.6}

Reading: putting both keys into ONE context (joint) is worse than hand-built colour alone (it splits
contexts too finely). Running the two models side by side and blending predictions helps on held-out
passes (mix +0.08 / +0.06, bma +0.08 / +0.05 nats/step over handcolour, CIs clear of zero; 13.3% ->
about 14.4% typical probability on the true outcome). On held-out whole games it is about a wash: mix
-0.02 / -0.00 (CIs span zero), bma +0.00 / +0.04 (s1 CI just clear of zero). BMA mostly learns to
trust the hand-built model there. Whole run 28 s wall.

## Round six: mix(EBUL predictive, hand-built colour), heads retrained, first 200 traces (OpenMind, 19:53 ET)

`round5_combo.py --n 200 --retrain` (ebul_perception.TRACE_GLOBS now also lists the other eight
Flash-Next prompt-matrix jobs, appended after the original list, so trace_paths(53) is unchanged).
200 traces, 20 games. dm heads trained fresh (2 splits x 2 folds x 2 seeds). Game split uses a new
balanced assignment (whole games, balanced by type and trace count), because round four fixed its
folds for eleven games only. Held-out games (e.g. Sequence Belt, Trail Unwind) are included: this is
an offline diagnostic, the heads are not part of any agent. Within one play; 151 s wall.
200 traces, 20 games; retrained dm heads

## split pass (within one play, back-off prior, event outcomes)
| arm | nats/step | gain vs flat | gain vs handcolour | click | button | mixed (vs handcolour) |
|---|---|---|---|---|---|---|
| flat | 3.321 | +0.000 [+0.000, +0.000] | -0.589 [-0.638, -0.533] | -0.439 | -0.709 | -0.607 |
| handcolour | 2.732 | +0.589 [+0.533, +0.638] | +0.000 [+0.000, +0.000] | +0.000 | +0.000 | +0.000 |
| ebul-dm-s0 | 2.868 | +0.453 [+0.371, +0.531] | -0.136 [-0.191, -0.083] | -0.072 | +0.021 | -0.324 |
| ebul-dm-s1 | 2.917 | +0.404 [+0.324, +0.485] | -0.185 [-0.240, -0.130] | -0.179 | -0.010 | -0.341 |
| joint-s0 | 2.921 | +0.400 [+0.311, +0.487] | -0.189 [-0.244, -0.137] | -0.251 | +0.021 | -0.321 |
| joint-s1 | 2.955 | +0.366 [+0.277, +0.452] | -0.224 [-0.278, -0.168] | -0.306 | -0.010 | -0.342 |
| mix-s0 | 2.613 | +0.708 [+0.642, +0.769] | +0.119 [+0.093, +0.146] | +0.125 | +0.216 | +0.030 |
| mix-s1 | 2.625 | +0.696 [+0.632, +0.755] | +0.106 [+0.082, +0.133] | +0.081 | +0.202 | +0.044 |
| bma-s0 | 2.678 | +0.643 [+0.580, +0.702] | +0.054 [+0.036, +0.075] | +0.066 | +0.098 | +0.006 |
| bma-s1 | 2.687 | +0.634 [+0.570, +0.693] | +0.044 [+0.026, +0.067] | +0.034 | +0.092 | +0.012 |

## split game (within one play, back-off prior, event outcomes)
| arm | nats/step | gain vs flat | gain vs handcolour | click | button | mixed (vs handcolour) |
|---|---|---|---|---|---|---|
| flat | 3.553 | +0.000 [+0.000, +0.000] | -0.694 [-0.743, -0.645] | -0.494 | -0.819 | -0.745 |
| handcolour | 2.860 | +0.694 [+0.645, +0.743] | +0.000 [+0.000, +0.000] | +0.000 | +0.000 | +0.000 |
| ebul-dm-s0 | 3.298 | +0.255 [+0.177, +0.332] | -0.438 [-0.506, -0.374] | -0.591 | -0.124 | -0.588 |
| ebul-dm-s1 | 3.263 | +0.291 [+0.209, +0.373] | -0.403 [-0.467, -0.337] | -0.585 | -0.043 | -0.567 |
| joint-s0 | 3.292 | +0.261 [+0.179, +0.342] | -0.433 [-0.496, -0.370] | -0.580 | -0.124 | -0.581 |
| joint-s1 | 3.213 | +0.340 [+0.263, +0.417] | -0.353 [-0.414, -0.296] | -0.432 | -0.043 | -0.558 |
| mix-s0 | 2.831 | +0.722 [+0.666, +0.778] | +0.029 [+0.004, +0.054] | -0.058 | +0.120 | +0.020 |
| mix-s1 | 2.867 | +0.687 [+0.632, +0.743] | -0.007 [-0.028, +0.015] | -0.093 | +0.037 | +0.025 |
| bma-s0 | 2.842 | +0.712 [+0.665, +0.762] | +0.018 [+0.008, +0.029] | +0.040 | +0.019 | -0.000 |
| bma-s1 | 2.852 | +0.701 [+0.653, +0.753] | +0.008 [+0.002, +0.015] | +0.010 | +0.010 | +0.004 |

timings: {"load_features_folds_s": 16.0, "regenerate_heads_s": 23.7, "scoring_s": 108.8, "total_s": 150.7}

Reading: with four times the data the result holds and gets firmer. Two models side by side with a
50/50 blend beat hand-built colour on held-out passes by +0.12 / +0.11 nats/step (tight CIs, gains in
all three game types, largest in button games); weighting by track record gains less (+0.05 / +0.04).
On held-out whole games the gain shrinks to about zero: mix +0.03 / -0.01, bma +0.02 / +0.01 (CIs
just clear of zero for three of four). EBUL alone and the joint key stay clearly worse than hand-built
colour. Absolute nats are not comparable with the 53-trace tables (more games, more outcome labels).

## Round seven: hand-crafted detectors (250 traces) (OpenMind, 20:04 ET)

Ask: "I don't think there is just colour as a feature. Analyse the first 250 games and look for all
kinds of features one can craft detectors for by hand. For everything else we have EBUL." Plays =
ebul_perception.trace_paths(250): 250 plays, 20 games, 27,599 scored steps. New files only, in
distill/ (not committed): feature_detectors.py (the detector library), round7.py (driver). Results:
distill/results/efe_trace_analysis/round7/ (table.md, results.json with per-play nats, selection.json
with every selection round, per_game.txt, detectors.pkl, heads_dm.pkl, timings.json). Nothing
existing was edited. Same yardstick as rounds four to six: object-event outcomes, prequential
nats/step, back-off prior (beta 2), fresh per play, no carry. The O(1) scorer in round7.py was
checked against heldout_yardstick.score on two arms (handcolour pass fold 0: 47036.1176 vs
47036.1176 nats; EBUL game fold 0: 36222.2468 both) and the script stops if they ever differ. Three
full reruns gave identical numbers.

### Step one: what decides the outcome, per game (plain words)

Sources: label tables per game and button, residual outcome entropy per handcolour context, sample
boards before/after, and a descriptive per-game pass that adds one detector at a time to handcolour
over all plays of that game (per_game.txt; description only, never used for selection).
Where the uncertainty sits: after handcolour, almost all the leftover surprise is on BUTTON presses
(Warehouse Associates 3.6 nats/step left with five contexts, Locksmith, Ghost Twin and Skewer Kebabs
above 2); click games are mostly settled by colour + shape (Toggle Navigator 0.3 left).

- Buoyant Pontoons (mixed, 35 plays): arrows slide a pair of pontoons; whether they move, stay, or
  spawn/remove a piece depends on what is beside them (look-ahead, steps-until-blocked); clicks on
  the pontoon pieces make pieces vanish. Pressing the same arrow again also predicts.
- Coded Notches (mixed, 5): arrows move a many-part piece; a counter tick (grow + shrink) shows up
  on every other move, so the previous outcome is the best predictor (+0.60 descriptive).
- Compass Dye (mixed, 4): arrows grow or shrink a pair of shapes, or nothing; no controllable object
  is ever found; nothing we built helps beyond "same button as last time".
- Deck Control (mixed, 1): too little data; background clicks shrink something or do nothing, half
  and half.
- Functional Tiles (click, 6): a click recolours a tile along a fixed colour cycle, and the cycle
  changes with the level (level one 9<->8, level three 8<->12, level four 14<->15): level index is
  the top detector (+0.19), then whether the click is next to another tile.
- Ghost Twin (button, 25): the avatar moves or is blocked (look-ahead +0.36), and independently a
  bar at the bottom ticks on every second press: after "bar ticked" comes "nothing" 82%, after
  "nothing" comes "bar ticked" 91%. The previous outcome is the top detector (+0.48).
- Kick Away (mixed, 4): arrows move a pair; free cells two ahead = plain move, an object there =
  push with grow/shrink. Look-ahead and nearest-object detectors (+0.25 to +0.27).
- Leapfrog (mixed, 24): arrows move a group or do nothing (about 45% nothing); clicks on the small
  pieces cause many-piece jumps. Level index and what is next to the click point help a little.
- Locksmith (button, 30): the key piece (two parts) moves through colour-3 corridors while a trail
  bar ticks on every move; the wall ahead and how close it sits to the colour-12 bar carry it
  (look-ahead +0.44, salient-colour profile +0.43, previous outcome +0.42).
- Loop and Pull (click, 4): clicking a piece that has a mirror partner pulls the pair apart in
  opposite directions (73% one label); without a partner, outcomes scatter. Mirror detector top.
- Mirror Rendezvous (mixed, 1): two pieces move mirrored; a bar ticks on alternate steps; previous
  outcome top.
- Reaching Lurch (click, 4): clicks flip the board between two states; after state A comes state B
  100% of the time. The last outcome of the same action is the top detector (+0.64).
- Sequence Belt (click, 4): clicking a belt tile next to another object gives "appear + shrink",
  one 3-5 cells away gives "appear" (75%). Distance to the nearest object and "on the rim of the
  populated area" top (+0.27, +0.25).
- Sigil Caster (mixed, 4): clicks recolour sigils (2->14, 0->14, 14->0/2); what that same sigil did
  last time repeats 74% of the time.
- Skewer Kebabs (mixed, 31): right adds skewer pieces, left removes them, up/down shift them; clicks
  do nothing. No single controlled object, so button detectors mostly read "not found / lost" and
  only the object count helps (+0.07).
- Sliding Indicator (click, 6): clicking a button moves the indicator; which button is given by the
  colours the clicked frame touches (the slot marker colour) (+0.46), then what it did last time.
- Streaming Purple (mixed, 6): arrows move one piece; how often the trail bar ticks changes with the
  level (level +0.14, object count +0.13).
- Toggle Navigator (click, 31): colour + shape already near-perfect (0.5 nats/step left); clicks on
  the dark area toggle the bar next to them (1->5 or 5->1); "inside the dark area" and the nearest
  colour add +0.02.
- Trail Unwind (button, 1): same arrow again vs a new one decides between a plain move and a turn.
- Warehouse Associates (button, 24): a push game: the moved group size varies, crates on targets
  recolour 4->3, and moves have momentum (after a three-part right move, the same again 65%). The
  avatar is often "lost" among identical crates, so look-ahead is missing half the time; previous
  outcome top (+0.73), then look-ahead (+0.37).

Pattern across games: the static layout features (shape, size, copies, touching, enclosure, border,
mirror, distances) matter in a few click games; in button games what matters is the one-step
look-ahead and, most of all, TIME: timers that tick on alternate presses, pushes that continue,
toggles that alternate. Two detectors were added after this look: "last outcome of this same
action" (full and coarse).

### Detectors (feature_detectors.py; value before the outcome, from the pre board, the click point,
the round-four controlled-object tracker and the play so far; "none" on the other action kind)

Click: c_colour (clicked colour, already in handcolour), c_size (doubling buckets), c_copies
(identical copies on the board), c_sameshape_other (same shape, other colour), c_colour_count
(objects of the clicked colour), c_touch_colours (which colours it touches), c_touch_n (how many
objects it touches), c_enclosed (inside one other object, and its colour), c_border (board edge or
HUD / against a wall / rim of the populated area / inside), c_near (colour and distance of the
nearest other object within two cells of the click), c_near_dist (that distance, any range), c_side
(which part of the object was clicked), c_agent_rowcol (click in the controlled object's row,
column, on it, neither), c_mirror (same-size object at the left-right / up-down mirror position),
c_last_click (did this object change the last time it was clicked), c_last_click_label (what it did),
c_same_obj (same object as the previous click), c_bg (object / background / HUD).
Button: b_look1 (what the controlled object would move into: free / edge / wall colour / object
colour), b_look2 (two moves ahead), b_blocked (moves until blocked, and by what), b_ahead_mover (the
object ahead has moved before in this play: pushable), b_agent_copies (copies of the controlled
object), b_last_moved (did it move on the last press), b_near (nearest other object: colour,
distance), b_agent_border (edge / wall / rim / inside).
Any action: salient (nearest object of a colour that keeps changing in this play, and how far),
salient_profile (distance class to each of the three most-changing colours), level (0, 1, 2, 3+),
age (actions since the level started, bucketed), repeat (same action as last step), last_label
(previous outcome), last_kind (its kind: nothing / move / move+ / recolour / other / clear), n_objects
(doubling buckets), last_same and last_same_kind (outcome the last time this same handcolour
context was taken). 36 in all; all 27,599 steps in 1.8 s wall on 8 processes.

### Selection (training folds only)

Per split and fold, on the training plays: fit = three quarters, validation = every fourth play (as
round4._head). Each round adds the detector with the best fit gain; stop when validation does not
improve by 0.0001 nats/step. Two predictors selected separately:
- "crafted": handcolour key + detectors, backing off (as the yardstick does) to the play's pooled
  outcome distribution;
- "crafted-chain": the same key, but each finer key backs off to the next coarser one, down to
  handcolour, then to the pooled distribution (guard against over-splitting).

Ranking on the training folds (mean of folds): plug-in conditional information given handcolour is
highest for last_label (1.7 nats pass / 1.6 game), last_same (1.5 / 1.3), salient_profile (1.2 /
1.0), b_look1 and b_near (0.8 / 0.7). Under the plain back-off, most of these LOSE in prequential
terms (last_label -0.42, age -0.50, salient_profile -0.20): the information is real but each split
starts from nothing. Only b_look1 (+0.02 / +0.05), level (+0.01), n_objects, c_enclosed and
c_touch_colours are positive.

Selected:
- crafted, pass fold 0: b_look1, b_ahead_mover, c_touch_colours; pass fold 1: c_enclosed, b_look1,
  b_ahead_mover; game fold 0: nothing; game fold 1: b_look1, b_ahead_mover, c_touch_colours, b_near.
- crafted-chain: last_label in all four folds (plus salient_profile in game fold 1).
What each added on the TEST plays, in selection order (95% CI over plays): b_ahead_mover +0.020
[+0.011, +0.030] and +0.016 [+0.005, +0.029] (pass folds), +0.006 [-0.001, +0.013] (game); b_look1
+0.005, -0.012, -0.014 (all CIs span zero); c_touch_colours -0.013 and -0.019 (hurt); c_enclosed
+0.001; b_near -0.021 (hurt). Chain: last_label +0.178 [+0.132, +0.223] / +0.133 [+0.090, +0.180]
(pass), +0.196 [+0.137, +0.253] / +0.135 [+0.099, +0.174] (game); salient_profile -0.015.

### Results (gain = nats saved per step vs the reference; 95% paired bootstrap over plays; game-cluster CI for vs handcolour)

split pass (250 plays, 27,599 steps)
| arm | nats/step | vs handcolour | game-cluster | vs crafted | vs crafted-chain | click | button | mixed |
|---|---|---|---|---|---|---|---|---|
| flat | 3.491 | -0.613 [-0.664, -0.564] | [-0.779, -0.437] | -0.622 | -0.773 | -0.404 | -0.757 | -0.626 |
| handcolour | 2.878 | 0 | | -0.009 [-0.052, +0.032] | -0.160 [-0.194, -0.129] | 0 | 0 | 0 |
| crafted | 2.869 | +0.009 [-0.032, +0.052] | [-0.138, +0.173] | 0 | -0.151 | -0.025 | +0.234 | -0.200 |
| crafted-chain | 2.718 | +0.160 [+0.129, +0.194] | [+0.074, +0.256] | +0.151 [+0.121, +0.183] | 0 | +0.090 | +0.319 | +0.049 |
| EBUL dm s0 / s1 | 3.030 / 3.071 | -0.152 / -0.193 | | -0.161 / -0.202 | -0.312 / -0.354 | -0.128 / -0.218 | -0.046 / -0.027 | -0.282 / -0.349 |
| mix(EBUL, crafted) s0 / s1 | 2.724 / 2.733 | +0.154 [+0.118, +0.192] / +0.145 | [+0.034, +0.285] | +0.145 [+0.121, +0.167] / +0.136 | -0.007 / -0.015 | +0.093 / +0.051 | +0.351 / +0.372 | -0.007 / -0.019 |
| bma(EBUL, crafted) s0 / s1 | 2.810 / 2.825 | +0.068 [+0.033, +0.106] / +0.053 | [-0.044, +0.206] | +0.059 / +0.044 | -0.092 / -0.107 | +0.018 / -0.008 | +0.253 / +0.256 | -0.087 / -0.113 |
| mix(EBUL, handcolour) s0 / s1 (round-six arm) | 2.750 / 2.756 | +0.128 / +0.122 | [+0.053, +0.200] | +0.119 / +0.113 | -0.032 / -0.038 | +0.109 / +0.068 | +0.219 / +0.241 | +0.047 / +0.041 |
| mix(EBUL, crafted-chain) s0 / s1 | 2.640 / 2.646 | +0.238 [+0.204, +0.272] / +0.232 [+0.195, +0.270] | [+0.132, +0.345] | +0.229 / +0.223 | +0.078 [+0.060, +0.096] / +0.072 [+0.052, +0.092] | +0.170 / +0.132 | +0.417 / +0.434 | +0.104 / +0.098 |
| bma(EBUL, crafted-chain) s0 / s1 | 2.709 / 2.714 | +0.169 / +0.164 | [+0.084, +0.264] | +0.160 / +0.155 | +0.008 [+0.004, +0.014] / +0.003 | +0.106 / +0.096 | +0.323 / +0.323 | +0.056 / +0.049 |

split game (whole games held out, balanced folds; 250 plays, 27,599 steps)
| arm | nats/step | vs handcolour | game-cluster | vs crafted | vs crafted-chain | click | button | mixed |
|---|---|---|---|---|---|---|---|---|
| flat | 3.691 | -0.707 [-0.753, -0.663] | [-0.861, -0.545] | -0.678 | -0.857 | -0.458 | -0.857 | -0.745 |
| handcolour | 2.984 | 0 | | +0.030 [+0.001, +0.059] | -0.150 [-0.184, -0.116] | 0 | 0 | 0 |
| crafted | 3.014 | -0.030 [-0.059, -0.001] | [-0.126, +0.064] | 0 | -0.180 | -0.050 | +0.090 | -0.139 |
| crafted-chain | 2.834 | +0.150 [+0.116, +0.184] | [+0.053, +0.254] | +0.180 [+0.145, +0.215] | 0 | +0.100 | +0.319 | +0.011 [-0.014, +0.036] |
| EBUL dm s0 / s1 | 3.319 / 3.378 | -0.335 / -0.394 | | -0.305 / -0.365 | -0.485 / -0.544 | -0.483 / -0.440 | -0.098 / -0.141 | -0.468 / -0.624 |
| mix(EBUL, crafted) s0 / s1 | 2.911 / 2.937 | +0.073 [+0.041, +0.107] / +0.047 | [-0.032, +0.191] | +0.102 / +0.076 | -0.077 / -0.103 | -0.031 / -0.045 | +0.247 / +0.218 | -0.029 / -0.061 |
| bma(EBUL, crafted) s0 / s1 | 2.991 / 2.997 | -0.006 [-0.036, +0.022] / -0.013 | [-0.101, +0.091] | +0.023 / +0.016 | -0.157 / -0.163 | -0.015 / -0.020 | +0.113 / +0.104 | -0.125 / -0.131 |
| mix(EBUL, handcolour) s0 / s1 | 2.916 / 2.927 | +0.068 / +0.057 | [-0.001, +0.144] | +0.097 / +0.087 | -0.082 / -0.093 | -0.009 / -0.016 | +0.160 / +0.148 | +0.031 / +0.021 |
| mix(EBUL, crafted-chain) s0 / s1 | 2.784 / 2.790 | +0.200 [+0.162, +0.240] / +0.194 [+0.158, +0.232] | [+0.089, +0.314] | +0.230 / +0.223 | +0.050 [+0.025, +0.076] / +0.044 [+0.020, +0.070] | +0.078 / +0.070 | +0.395 / +0.394 | +0.090 / +0.081 |
| bma(EBUL, crafted-chain) s0 / s1 | 2.824 / 2.827 | +0.160 / +0.157 | [+0.065, +0.261] | +0.190 / +0.186 | +0.010 [+0.003, +0.018] / +0.007 | +0.117 / +0.111 | +0.328 / +0.324 | +0.017 / +0.017 |

Game-cluster CIs are for s0 where two seeds are listed. Post-hoc diagnostics (chosen after seeing the
table above, so not headline): the flat-selected set under the chain back-off loses badly (-0.39 /
-0.46 vs handcolour); with last_label first and the flat-selected set after it: +0.063 / +0.066
(better than handcolour in button games, +0.32 / +0.29, worse in mixed, -0.16); blending that with
EBUL: +0.270 / +0.261 (pass) and +0.205 / +0.196 (game), i.e. +0.03 over mix(EBUL, crafted-chain) on
passes and nothing on games. Per-game tables for both splits are in table.md: under the chain,
Ghost Twin +0.39 / +0.40, Locksmith +0.38 / +0.38, Warehouse Associates +0.22 / +0.21, Functional
Tiles +0.17 / +0.16, Toggle Navigator +0.08 / +0.09; the negatives are small or rest on tiny samples
(Coded Notches -0.01 / -0.02; on the game split Skewer Kebabs -0.04 and Mirror Rendezvous, one play,
-0.17). Mix(EBUL, crafted-chain) s0 is positive in 17 of 20 games on passes (Coded Notches -0.09,
Mirror Rendezvous and Reaching Lurch -0.01) and 19 of 20 on games (Functional Tiles -0.07).

EBUL heads: dm, seeds 0 and 1, retrained on these folds (round4._head unchanged); validation dm gain
1.42 to 1.55 nats on the pass and game-fold-1 heads, 0.85 on game fold 0 (its training games are
mostly Toggle Navigator, Leapfrog, Warehouse Associates, Ghost Twin, Skewer Kebabs).

Timings (wall, Mac Mini, 8 processes, load average 11 to 16 from other jobs): loading and event
coding 14.9 s; all 36 detectors on all 27,599 steps 1.8 s; per-game description 0.7 s; conv
features and folds 6.7 s; eight greedy selections plus eight EBUL head searches in one pool 33.3 s
(selection 4 to 9 s each, heads 18 to 34 s each); EBUL codes and the scorer check 33.4 s; scoring
every arm 1.2 s; bootstraps 11.7 s; total 104 s.

### Verdict

1. Colour is not the only feature, but the static layout detectors add almost nothing on top of
   it. Of 36 hand-built detectors, the ones that describe the board (shape, size, copies, touching,
   enclosure, border, mirror partner, distances, look-ahead) are either already covered by colour +
   shape or split the counts too thinly. Selected on training folds and scored held out, they give
   +0.01 on held-out passes and -0.03 on held-out games. The only detector whose own step is
   positive with a CI clear of zero on both pass folds is "there is something ahead of the avatar
   that has moved before" (pushable): +0.02 / +0.016, but that is an increment over the look-ahead
   detector, which itself adds nothing (+0.005 / -0.012, CIs span zero), and the whole selected set
   still does not beat hand-built colour.
2. The feature that matters is time: what happened on the last step. It picks up timers that tick
   on every second press, pushes that keep going, and toggles that alternate. It is worth +0.16 on
   held-out passes and +0.15 on held-out games (CIs +0.13 to +0.19 and +0.12 to +0.18, game-cluster
   CIs clear of zero). The biggest gains are in button games (+0.32), and it is positive in click
   games too (+0.09 / +0.10). It works only when the finer key falls back on the colour key; with the
   yardstick's plain back-off the same detector costs 0.4 nats per step. So the guard against
   over-splitting matters more than which detectors are picked. "crafted-chain" is a single-detector
   result: previous outcome alone on three of four folds; the one extra detector the greedy loop
   accepted (salient-colour profile, game fold 1) lost on test (-0.015).
3. "For everything else we have EBUL" holds, as a blend: 50/50 with the linked-back-off
   model, EBUL adds a further +0.08 / +0.07 on held-out passes and +0.05 / +0.04 on held-out games,
   all CIs clear of zero. That makes it the best arm: +0.24 / +0.23 (passes) and +0.20 / +0.19
   (games) over hand-built colour. EBUL alone stays clearly worse, and blending weighted by track
   record gains almost nothing over the linked-back-off model alone.
4. What an agent could use cheaply: keep counts of what each action did per colour-and-shape key and
   per previous outcome. Split finer only through a back-off chain. Add the pushable-ahead flag in
   avatar games. None of this has been tried online; it would need the usual two-pass A/B.

## Note: faster compressors for EBUL fitness (OpenMind, 20:25 ET)

Benchmark on EBUL-style ternary codes (1000 samples x 120 units; Mac Mini; zstandard/lz4/brotli installed
for /usr/bin/python3 --user). Biggest win is packing 5 trits per byte (3^5 = 243 < 256) before compressing:
gzip-9 goes from about 130 ms to about 0.25 ms on the unconverged code (8 ms -> 0.1 ms on a converged-like
code) and compresses smaller. On packed input zstd level 3 is about 0.02 ms and at or near the best
ratio; lzma/zstd-19/brotli-11 squeeze a little more for 1.5-40 ms. lz4 is fastest but compresses worst.
Recommendation for ebul.gzip_bits: pack trits, then zstd-3 in the GA loop, lzma or zstd-19 for the
final reported number. Not yet applied to ebul.py.

## Note: fast estimators of EBUL's gzip entropy (OpenMind, 20:27 ET)

Benchmark (/tmp/entbench/bench.py, bench2.py): 107 ternary codes (1000 samples each; real board/patch
features through random layers of width 8-120 at several scales, GA-evolved 12-unit codes, and synthetic
k-distinct-row codes with noise). Reference = ebul.gzip_bits (gzip-9, one byte per trit), 19 ms/code
on average here. Per estimator: time, Spearman / Pearson vs gzip, median relative error raw / after a
one-off linear calibration, Spearman on the lower-entropy half (where EBUL targets live):
- zstd-3 on packed trits (5 per byte): 0.05 ms; 0.983 / 0.981; 0.18 / 0.06; 0.90
- gzip-9 on packed trits: 0.33 ms; 0.987 / 0.991; 0.22 / 0.07; 0.91
- distinct-row, LZ-style (literal cost per new row + pointer per repeat): 1.6 ms; 0.979 / 0.908; 0.32 / 0.18; 0.94
- adaptive context model (left trit + same unit one row up, KT counts): 0.21 ms; 0.945 / 0.885; 0.19 / 0.16; 0.81
- per-unit entropy sum (ebul.shannon_bits): 0.27 ms; 0.913 / 0.851; 0.20 / 0.21; 0.70
- min(zstd packed, distinct-row): 1.7 ms; 0.987 / 0.980; 0.32 / 0.09; 0.94
Pick: zstd-3 on packed trits, linearly calibrated to gzip once, for the GA loop; the distinct-row estimate
if ranking among low-entropy candidates matters most.

## Prototype: rule discovery system (not yet run) (OpenMind, 21:03 ET)

Ask: "build a prototype of such a rule discovery system for ARC, consider what you learned about the
free energy principle. Don't yet run the code." Design record: provenance event 560271a2 (the eight
components). Code: ~/GitHub/arc-3/ARC3-Inference/rulediscovery1__fepInspired/ (new folder, not committed). Only
`python3 -m py_compile` was used on it; no test, script or import of it was executed; no harness,
prompt, Kaggle or Jethro change.

Files:
- _distill.py: the one import shim into distill/ (object_events, agency_contexts, feature_detectors,
  heldout_yardstick, efe_trace_analysis; round7 and ebul_perception lazily). Nothing copied.
- perception.py: frame -> HUD-masked components -> tracked objects -> step label in the object_events
  alphabet; the Perceiver always advances pre = post; Scene.apply imagines the next board.
- rules.py: rule language. MoveRule, ClickToggleRule, ContactRule, CounterRule (modifier), NoOpRule,
  PersistRule (repeat or prev -> next table), CodeRule (fixed signature for model-written predictors,
  in-process sandbox only) and a stub provider that returns no rules. RuleSet = decision list
  (specific first) + additive modifiers, with a description length in nats. ContextBuilder builds the
  context before the outcome, mirroring feature_detectors.run_trace.
- hypotheses.py: template fitting from stored steps (part-level track record as a filter) and beam
  search over rule sets by the posterior's own score.
- beliefs.py: posterior over rule sets, prior exp(-dl_weight x DL), likelihood prequential with a KT
  miss rate over the shared chained back-off (round7.Model, handcolour -> + previous label), late
  entry by exact replay, rule-level model reduction, top-K pruning, surprise / Bayesian surprise /
  spike monitor, Dirichlet novelty model with the closed-form Dirichlet BMR.
- goals.py: goal templates over colours (reach, match, fill, empty, align, count), updated on clears
  and on "satisfied without a clear", carried across levels; preferences ln C over outcomes.
- policy.py: G(a) = -salience (rule-set disagreement) - novelty (Dirichlet EIG) - pragmatic (ln C +
  goal progress on the imagined board) - empowerment (early in a level) + action cost; softmax with
  habit prior E and precision gamma rising as the posterior concentrates; Thompson fast path; beam
  planner in the MAP rule set's imagined boards once the posterior is concentrated and a goal credible.
- agent.py: RuleDiscoveryAgent (fast memory per level, slow memory per play, never across games),
  TextSummaryAdvisor (text for the harness model), HarnessAdapter (runtime_state.Frame in; sandbox
  action payload out, names from inference/agent/action_names.py). Harness untouched.
- offline_eval.py: replays the round-seven play set; prequential nats of the rule-set mixture vs the
  chain back-off alone, paired and game-cluster bootstrap, settings chosen on training folds; how
  often the EFE top choice was the played action.
- tests/: synthetic 64x64 worlds (mover into a wall, click toggle, bar ticking every second press)
  for labels, the pre = post advance (Perceiver and full agent loop), fitting, back-off, replay =
  online scoring, salience ranking, novelty, planner, harness payloads.
- README.md: architecture diagram, active-inference mapping, evidence per choice, how to run, gaps.

Design mapping in one line each: A = perception (object events, round four's biggest gain); B = the
posterior over rule sets over a chain back-off (round seven: previous outcome helps only under the
chain); novelty = Dirichlet EIG; salience = rule-set disagreement; C = goal beliefs and outcome
preferences; gamma and E = precision and habits in the softmax; BMR = dropping rules and merging
contexts; two timescales = fast per-level plan vs slow per-play rules and goals (carry within a game
helped, a prior from other games hurt).

Found while writing, unverified until run: at full description-length price a rule of about 14 nats
needs many steps to beat the chain back-off within one play, because the counts learn deterministic,
position-free regularities in a few steps. So dl_weight tempers the prior and is selected on training
folds; rules should pay mainly where they see what counts cannot (look-ahead into walls, contacts,
imagined boards for planning).

Stubbed: the language-model rule provider (returns nothing); the in-process sandbox (model code must
go through the harness sandbox); EBUL is not in it (slot: a second back-off expert mixed 50/50 with
the chain, round seven's best arm). Next: run the tests, then offline_eval on both splits.
Provenance: event 9b883988-46a6-48d4-8ddb-6d5ac46eabaf (project:arc3, caused by 560271a2).

## Rule discovery prototype: first evaluation, first 30 plays (OpenMind, 21:37 ET)

First execution of rulediscovery1__fepInspired. Unit tests: 30 of 31 pass; the failing one
(salience ranks the disagreeing action first) fails because the counts-only rule set holds ~99.99%
of the prior weight at the start (MDL prior ~17 nats for a mover rule), so salience is ~0 for all
actions. Offline replay, pass split, 30 plays, 57 s wall (10 processes); config chosen on training
folds both times: propose every 10 steps, 4 hypotheses, full-strength MDL prior.
- Rule-set posterior vs the round-seven chain back-off: +0.012 [-0.003, +0.030] nats/step overall;
  click games +0.036 [+0.004, +0.068]; button games exactly 0; mixed -0.007 [-0.015, +0.000].
- Final posterior was "counts only" in 21 of 30 plays; only persist/"click background does nothing"
  rules survived; no movement rule was adopted even in Locksmith.
- Policy vs the played action: EFE top choice in 6.5% of steps; the played action sits on average at
  the 21st percentile of the EFE ranking (1 = top); played action tied for top salience in 79% of
  steps because salience is ~0 everywhere.
Diagnosis (Locksmith, pass 0): movement is detected cleanly (up/down/left/right move the piece by 5
cells; fitted move rules have perfect part-level track records, e.g. 19/19 by step 40), but real
outcome labels carry side effects ("grow|mv+0-3x2|shrink": floor residue and a second moving
object). Rule sets predict a partial event set while the likelihood scores the whole label, so a
correct rule "misses" on almost every step and the counts model, which learns whole labels, wins.
Next fix: part-level (factorised) likelihood or compose predicted parts with back-off-predicted
residual parts; then revisit the MDL weight and salience.

## Think-hard router: offline evidence (Son's ask, 22:00 ET)

Ask: a per-turn binary router, "think hard" (an intensive, hypothesis-strengthening mode) only when
needed. Can cheap signals, known before the turn and without an LLM call, predict when deep thinking
matters? Offline only, on the recorded Flash-Next plays (ebul_perception.trace_paths(301): 301 plays,
20 games; the held-out seven games are among them: this is a diagnostic, no gate ships). New files
only, not committed: distill/think_router_turns.py (turn table), distill/think_router.py (analysis).
Results: distill/results/think_router/ (turns.jsonl one row per turn, report.md all tables,
summary.json, calibration.json, extract_log.txt, run.log, timings.json). No harness, Kaggle or Jethro
change.

### Where the harness logs thinking

- Each analysis row's transcript holds one "[MODEL RESPONSE META]" block per model request with
  reasoning_chars and content_chars (no per-request token counts), followed by the [THINKING] text
  (its length matches reasoning_chars; correlation 0.997).
- A turn = one analysis_step id. The model is called repeatedly (python tool calls, inspection and
  failed action attempts) until one action(...) call executes; that call may carry a batch. A turn
  that runs past the per-turn time budget is written as several analysis rows with the same id
  ("Yielded control to solver: turn_time_budget"), so thinking is summed over every row of the id.
  Rows with no META are request time-outs. Action rows carry the id of the turn that issued them and
  are written before the analysis row, so actions are joined by id, not by position.
- 7,173 turns, 292 issued no action (time-outs and yields). Median turn: 1 request, about 4,000
  reasoning chars.
- Calibration against vLLM: in all nine prompt-matrix jobs the logged request count equals vLLM's
  request count exactly; reasoning + content + tool-argument chars / generated tokens = 3.00 to 3.08
  (mean 3.04); reasoning is 81-83% of what the model writes. So thinking tokens ~ reasoning_chars / 3.
  The 301 plays hold about 48 M reasoning chars, about 16 M reasoning tokens.
- The runtime-budget line (game seconds left) is written only in the Kaggle plays; the turn header's
  wall clock is in every play and is used as the budget proxy (seconds since the play's first turn).

### Features (before the turn) and outcomes

Round seven's chain back-off (handcolour context -> + previous outcome), fresh per play, open
vocabulary, no training: surprisal of the last outcome, last turn's max / mean surprisal, predictive
entropy and unseen-outcome mass over the candidate actions (valid buttons; for clicks the click
contexts already tried plus one fresh click: enumerating every object per turn would cost more than a
router may save); untried buttons and never-clicked object types on the board; first turn / just
cleared / after RESET or game over; stall (actions since the last new outcome label or clear); level,
actions into level, turn index, last batch size; game type. Outcomes: new outcome label (never seen
before in the play), level clear in the turn, clear within 5 / 10 actions of the turn's start.
The play's first turn is left out of (a) and (c): its outcome is new by construction. (It was in the
first draft and produced a false "level start" signal.) 6,580 acting turns remain; new-or-clear in
57% of them, a clear within ten actions in 8%.

### (a) Does longer thinking go with better outcomes? No, not within a play.

Within-play AUC (pairs of turns from the same play; 0.5 = none), 95% CIs over plays / over games:
- New outcome or clear: whole-turn reasoning 0.51 [0.49, 0.53] / [0.48, 0.55]; first request only
  (thinking before any tool result of the turn) 0.50 [0.48, 0.52]; request count 0.53 [0.51, 0.55].
- Clear within ten actions: whole-turn 0.45 [0.41, 0.49] / [0.40, 0.50] (more thinking, FEWER clears
  soon); first request 0.48 [0.45, 0.52].
- Not concentrated where the ask expected: high surprise (last outcome had p <= 5%) 0.51 [0.47,
  0.54]; stalled (10+ actions without a new outcome) 0.54 [0.47, 0.60]; level start (not the first
  turn) 0.55 [0.45, 0.66]; after RESET 0.62 [0.47, 0.75] on 18 plays only; predictable turns 0.43
  [0.36, 0.49]. By game type 0.49 (click), 0.56 [0.52, 0.59] (button), 0.50 (mixed).
- Dose-response by within-play quintile of reasoning: new-or-clear 0.58, 0.56, 0.58, 0.59, 0.56;
  clear within ten 0.10, 0.09, 0.07, 0.08, 0.07; the top quintile issues more actions (5.5 vs 4.6)
  and makes 3 requests vs 1.1.
- Held out (whole games): a logistic on the pre-turn state gains nothing from adding thinking for new
  outcomes (+0.000); for clears within ten it gains +0.02 [+0.01, +0.03], and the sign is negative
  (long thinking = a clear is NOT close). Reading: near a clear the model executes a known plan with
  little thinking; long thinking happens when it is lost.
- The model already routes itself: thinking percentile within the play is 0.71 right after a clear,
  0.61 after a RESET, 0.55 after a surprising outcome, 0.47 when stalled and 0.44 in predictable
  turns (0.5 = typical). Spearman with last-outcome surprisal +0.12, with candidate entropy +0.11.
- Censoring check: every turn with a request time-out issued no action, so none is among the acting
  turns above. Turns that ran past the per-turn time budget (1,113 acting turns, "yield") are long by
  construction; without them the clear-within-ten AUC is 0.46 [0.42, 0.51] / [0.40, 0.52] (interval
  now touches 0.5), new-or-clear 0.52 [0.49, 0.54]. With time-out and yield flags as covariates the
  held-out increment for clears stays +0.016 [+0.010, +0.024] (game CI), coefficient still negative.
So thinking is reactive: it rises after surprises and level changes, and in these plays that extra
thinking is not followed by more new outcomes or faster clears (if anything, weakly fewer clears).
Observational only; it cannot say what less thinking would do.

### (b) Predictable turns and the potential saving

Pre-registered rule (last outcome surprisal < 1 nat, mean candidate entropy < 1.5 nats, under 10
actions since the last new outcome, not a level start): 6.2% of turns, 5.7% of reasoning, 5.3% of
wall time. Inside, new-or-clear 0.41 vs 0.61 outside, but 7.6% of all in-turn clears fall inside
(plan execution). Looser settings (surprisal < 2, entropy < 2, stall < 20): 32% of turns, 29% of
reasoning, 31% of informative turns, 37% of clears: surprise and entropy barely separate informative
turns from the rest. Predictable turns do use slightly less thinking already (median 3,660 vs 4,090
chars). Full 27-setting grid in summary.json.

### (c) The gate, held-out whole games (balanced game folds; pass split in report.md)

New outcome or clear in the turn:
- Single signal chosen on the training games only (best within-play AUC there): "outcome labels seen
  so far" in both folds, within-play AUC 0.72 [0.69, 0.74] plays / [0.68, 0.76] games (pooled 0.48:
  it ranks turns inside a play, not plays against each other). The other "how far into the play"
  signals (turn index, wall seconds, unseen-outcome mass) sit at 0.69 [0.65, 0.73] (games), but those
  rows are ranked on the held-out table itself, so treat them as optimistic. New outcomes are
  front-loaded.
- Logistic on all pre-turn features: within-play 0.65 [0.63, 0.68] / [0.61, 0.69]; pooled 0.76
  [0.74, 0.78] / [0.69, 0.81] (pooled mostly tells button games, rich in new outcomes, from click
  games). The fitted model is worse than turn index alone within a play because it is fitted on the
  pooled signal.
- The (b) rule as a gate: 0.50 (too few turns to matter).
Clear within ten actions: logistic within-play 0.65 [0.60, 0.70] / [0.56, 0.71]; pooled 0.53; the
training-picked single rule (level index in one fold, actions into the level in the other) 0.60
[0.51, 0.69] (games). Level index scores 0.76 within play when read off the test table (later levels
clear faster); not a thinking signal.
Operating points (threshold set on the training games, applied to the held-out games):
- Gate for new-or-clear, 27% of turns light: 24% [20, 28] of reasoning in those turns; 12% [10, 15]
  of informative turns routed light (random gate: 27%); but 25% of in-turn clears routed light, the
  same as random.
- Same gate, 51% light: 49% of reasoning; 35% of informative turns missed (random 51%); 51% of clears.
- Gate for clear within ten, 23% light: 20% of reasoning; 17% [12, 22] of near-clear turns missed
  (random 23%).

### Verdict

1. Cheap signals predict WHERE new outcomes come (early in a play, while few outcome kinds have been
   seen and unseen-outcome mass remains), within-play AUC 0.65 (logistic) to 0.72 (one counter),
   game-cluster CIs 0.61 to 0.76; they do not predict progress (clears) usefully, and the surprise /
   entropy / stall signals the ask expected add little on their own.
2. There is no observational sign that longer thinking produces new outcomes or clears; for clears it
   runs weakly the other way (sensitive to the turns that ran past the per-turn time budget). The
   model already thinks more after surprises and level changes.
3. Potential saving: a novelty gate could route about a quarter of turns light, holding about a
   quarter of reasoning tokens, while keeping 88% of informative turns hard; but it routes clears
   light at the random rate, so whether light turns cost levels is untested.
4. Caveats: observational (thinking was always on, and it is endogenous: the model thinks more when
   confused); "informative" is a proxy for "thinking mattered"; outcome labels are the object-event
   alphabet, so "new" is fine-grained (57% of turns); per-turn wall clock includes environment time;
   request time-outs are censored; one model (Flash-Next), recorded plays only.
5. Live test needed: a micro-randomised trial inside normal runs: on each turn the gate calls light-
   eligible, flip a coin (say 50%) between hard and light thinking (a reasoning cap or thinking off),
   log it, and compare outcomes of randomised-light vs randomised-hard turns in the same situations;
   plus an arm-level A/B (always hard / gate / random light at the same share, the random arm being
   the control that separates the gate from the mere amount of light thinking), four passes each,
   levels cleared per game first. Pre-register equal wall clock or equal turn count: light turns are
   faster, so at equal wall clock the gated arm gets more turns.

Timings (Mac Mini, OMP_NUM_THREADS=1): turn table 29 s wall (load and event-code 17 s on 10
processes, table 2 s, calibration 6 s); analysis 89 s single process (bootstraps dominate).
Provenance: project:arc3 event 89d9bb42-6baf-46d2-97e5-1bee9048c8b5, with a correction event linked to it
(training-picked gate rule; time-budget sensitivity), both 23-Sep-2026.

### Second evaluation: event-by-event (part-level) scoring (23-Sep-2026, 22:27 ET)

OpenMind asked for the fix proposed after the first evaluation: score a rule against the parts of an event, not the whole label. Implemented in rulediscovery1__fepInspired/beliefs.py (compose_predictive spreads the rule's mass over every observed outcome that contains the predicted parts, rule_missed counts a miss only when a predicted part is absent; label-level scoring still available via --likelihood label). Part parsing is cached (the first run without the cache was far slower and was stopped). Same 30 plays, pass split, same config grid.

| arm | label scoring (first run) | part scoring |
|---|---|---|
| all | +0.012 [-0.003, +0.030] | +0.014 [+0.001, +0.030] |
| click | +0.036 [+0.004, +0.068] | +0.036 [+0.011, +0.066] |
| button | 0 | 0 |
| mixed | -0.007 [-0.015, 0.000] | -0.002 [-0.005, 0.000] |

Policy agreement unchanged (top-1 about 6 %, mean percentile about 0.21); top-salience share 0.79 -> 0.75. Wall time 128 s on 10 workers. Plays ending counts-only: 21 of 30 (was about the same). The rules that end up holding weight are still the simple ones ("click on background does nothing", "the last outcome of the same action repeats", "the previous step repeats"); no movement rule is adopted in button games. Conclusion: part scoring removes most of the mixed-game loss and pushes the overall gain just above zero, but the bottleneck is now the description-length prior, which still keeps proposed movement rules from gaining weight. Tests: 31 pass, 1 fails (salience ranking, same cause).

### Locksmith simulator (23-Sep-2026, 22:50 ET)

OpenMind asked for an environment that simulates Locksmith from its traces. The game's own source and the ARC engine are in the local arc-3 clone, so rulediscovery1__fepInspired/env.py runs the real game (exact, CPU only, Python 3.12 venv) rather than a hand-written approximation. verify_env.py replays all 43 recorded Locksmith plays: every board (5916 of 5916) and level counter matches, in 3.6 s. play_live.py runs the rule agent and a random baseline live, RESET offered as in the harness: neither clears a level in 300 actions over 3 seeds. The live HUD mask works (each arrow reads as a clean move, blocked moves as residue only), but the agent's posterior stays counts-only, so it never plans, never sends RESET, and loses all three lives by about 129 actions (the step bar gives about 43 moves per life). Random survives only by hitting RESET, which restores the lives. Next: the agent needs the movement rule and a key/lock goal to plan with; the live env is now the test bed for that. Mechanics summary in the package README.

### Rule discovery agent vs the Locksmith simulator (23-Sep-2026, 23:05 ET)

OpenMind: "run my thing against the locksmith environment sim". locksmith_run.py: random baseline plus the agent at three prior strengths (dl_weight 1, 0.25, 0.05), 10 seeds each, 500 actions, RESET offered; in-game probes read from the game state. Results (results/env_ls20/locksmith_run.md): no level cleared by any arm. All 30 agent plays end in game over around 129 actions (never presses RESET); random survives only by pressing RESET about a fifth of the time. Agent visits 17-20 distinct cells vs random 24; key changes about once per play at most. No agent play ends with a movement rule in its top rule set.
Diagnosis (one play traced step by step): movement rules ARE proposed (up and right; down and left fail the fitter's 70 % precision gate because they are blocked often) and briefly hold most of the weight, but once scored against the counts they lose log likelihood (about -3 nats over 50 steps even at a twentieth of the prior): they never learn a blocking colour ("blocked by colours -": every candidate blocker was also seen passable, so it is left silent), so they mispredict every blocked move, while the counts already know "up moves up". Once pruned they are re-proposed every few steps but scored and dropped immediately. With no rules the planner never engages; the best goal guess is weak ("convert every colour-0 cell", p 0.06) and no goal template covers "change the key to match the lock, then walk into it". The player piece is two colours, so movers are fitted per colour (two half-rules). 4 s wall for all 40 plays.

### EBUL-entropy curiosity (23-Sep-2026, 23:20 ET)

OpenMind: add artificial curiosity that picks actions maximising entropy, the entropy taken from EBUL's last layer. rulediscovery1__fepInspired/curiosity.py: an EBUL encoder (two evolved layers, ternary last-layer code) trained on 9x9 patches from OTHER games only, applied to patches centred on every object (HUD painted out). Whole-board EBUL codes were tried first: one single code for every Locksmith board, useless. Reward = entropy (ebul.gzip_bits, EBUL's own measure) the new board's last-layer codes add to the play's code history. Value per (percept, action) from experience, optimistic for untried pairs, falling back to the action's recent gain. Arms added to locksmith_run: curiosity on top of the EFE policy (temperature 1), and curiosity alone (temperature 0.25).
Results (10 seeds, 500 actions, RESET offered): EFE+curiosity visits 24.9 cells (plain agent 17.7, random 24.2), changes the key 2.0 times (0.4), holds a matching key on 8.2 steps (0.4). Curiosity alone: 24.9 cells, and cleared level one once (seed 4, action 80) -- the first clear by any non-language-model agent here; one in ten, so not yet distinguishable from luck. All curious plays still end in game over (no RESET, no step-bar awareness), still no movement rule adopted. Side check at 129 actions without RESET: curiosity alone about matches random exploration; the gain is over the EFE agent, which explores less than random.

### RESET, one-piece sprite, wall colour, and a scoring bug (23-Sep-2026, 23:35 ET)

OpenMind: "yes do that" (RESET + merged block). Changes in rulediscovery1__fepInspired:
- policy.py: RESET is a candidate action (it was excluded by design), cost 0.5; beliefs.py counts a chosen RESET in the novelty table so its epistemic value decays (back-off untouched).
- hypotheses.py / rules.py: types that always move together by the same displacement are fused into one MoveRule with a partner group (Locksmith's two-colour block -> one mover); group_look_ahead ignores the sprite's own cells.
- Wall colour: the look-ahead assumed the board's modal colour is open floor. In Locksmith the modal colour IS the wall. The group look-ahead now reports the modal colour, so it can be learned as a blocker (up-mover learned "blocked by colour 4").
- Bug fix in compose_predictive (written earlier tonight): the share for "a consistent label not seen yet" went to the bare predicted label and took half of the unseen slot, so a correct rule scored WORSE than the counts whenever the real outcome was new. It now goes to the unseen slot. Movers went from about -3 nats to about +2.7 nats over 60 steps against the counts.
Locksmith (10 seeds, 500 actions): game overs fell from 10 of 10 to 3 (default) and 0 (quarter prior); agents now use RESET (16-60 times per play, too often). Quarter prior is the best arm: 28.4 cells (random 24.2), key changes 2.5, matching key 7.1 steps, and 2 plays end with a mover on top. No level cleared (the lucky curiosity clear did not repeat); planning never engages, because there is no key/lock goal and the movers still do not pay the full prior early. 75 s wall.
Offline rerun, first 30 plays, part scoring after the fix: +0.035 [+0.002, +0.083] nats/step vs chain (was +0.014); button games +0.009 (first time above zero), mixed +0.042 (was -0.002), click +0.042. results/first30_parts_v2.

### Proposal steps 1, 2 and 5 implemented and evaluated (24-Sep-2026, 00:25 ET)

OpenMind approved the plan (docs/plans/2026-09-23-rulediscovery-locksmith-score.md).
- Step 2: rules.PadMoveRule, one rule for all arrows of a sprite (priced once, walls pooled); hypotheses.fit_pads. It helps but still does not pay the prior back within a play at a quarter prior (about +6 nats of evidence vs 10 nats of price at step 15).
- Step 1: explore.py, ObjectContactExplorer. Plans with the template fitter's best current mover (gate "fitted": the counts cannot plan, so the planning model need not win posterior weight), breadth-first over sprite offsets on the current board, to the least recently touched reachable object; "reached" means the sprite is ON the object (one box inside the other); a finished or failed trip marks its target touched; anything changing away from the sprite clears the touched set; trips start after every button was tried three times; target areas are passable (the lock's colour had been learned as a wall from wrong-key bumps). Four bugs found and fixed while tracing plays (only up/down movers known -> unreachable target chased; touching the lock frame counted as entering; the tile under the sprite invisible -> re-chosen forever; lock colour learned as wall).
- Locksmith (10 seeds, 500 actions): explorer arms clear level one in 10 of 10 plays at both quarter and full prior, first clear at action 32-51 (median about 48; language-model harness 15-336, median about 21). Every other arm: 0. Then level two: no clears, and 9-10 of 10 end in game over (step bar / lives not modelled).
- Offline 30-play benchmark after the d-pad rule: +0.053 [+0.007, +0.115] nats/step vs chain (was +0.035); button +0.064, mixed +0.063, click +0.038. results/first30_parts_v3.
- Step 5 (not Locksmith-only?): game_sweep.py on Ghost Twin (g50t) and Warehouse Associates (wa30), 10 seeds x 500 actions: 0 levels for random, agent and explorer alike; the explorer arm ends in game over in 7 and 3 plays. So far the gain is Locksmith-specific.
- Not done: step 3 (key-matches-lock goal), step 4 (RESET only to survive).

### Locksmith level two, measured (24-Sep-2026, 00:45 ET)

Simulator BFS after replaying the level-one solution: level two gives 42 on the step bar but costs 2 per move (21 moves per life), 1 lock, key starts at rotation 0 and the lock needs rotation 3 (three rotation-tile visits), 2 refill pickups, no moving tiles, springs or fog. 4383 states; shortest clear without losing a life: 45 moves, which is only possible by collecting refills on the way. Losing a life resets the key. So level two needs (a) repeated use of the same tile a counted number of times, (b) collecting refills before the bar empties. The explorer does neither on purpose: it prefers the least recently touched object (so it avoids re-using the tile) and it cannot see the bar (HUD mask).

### Why the rule discovery agent fails on Ghost Twin (g50t) (24-Sep-2026, 00:20 ET)

OpenMind: analyse, with at most 30 Ghost Twin traces, why his code does not work there. Used 30 of 43 plays (all replay exactly on the simulator). Language model: level one cleared in 10 of 30, first clear at action 21-168; shortest recorded clear: right x5, down, up, ACTION5, down x8, right x5.
Mechanics (game source + that clear): the arrows move the player one cell (6 px) on a path; ACTION5 rewinds the player to the level start, animated step by step, and turns the recorded path into a ghost that re-walks it in lockstep with the next run (up to 2 ghosts); a ghost standing on a switch keeps a door open; level clears when the player reaches the goal; a timer bar loses a column every 2 actions (about 128 actions per life); walls are off-path cells. Hidden state (the recorded paths) means the board alone does not determine the next board -- a BFS keyed on boards finds no clear.
Agent live (500 actions, 2 seeds, with and without the explorer): 0 levels. It learns the arrows as a d-pad with walls (colour 0) correctly. But (1) ACTION5 is pressed 95-197 times per play: its outcomes are many and varied, so novelty/salience keep choosing it, and each press rewinds the player to the start -- the player never gets beyond about 11 cells from the start; (2) the fitter reads ACTION5 as "move up 6" (the rewind animation ends one step back), so the explorer plans with ACTION5 as an arrow; (3) no rule template can express "go back along your own path and leave a copy that repeats it" (history-dependent, hidden state), so the ghost mechanic is invisible to the posterior; (4) the goal is behind a door that only a ghost on the switch opens, so touching objects cannot reach it.

### Hyperdimensional time model, roadmap stages 0-4 (24-Sep-2026, 01:30 ET)

OpenMind: back up the package (rulediscovery1__fepInspired_backup0, identical copy, verified with diff), then run the roadmap stages on 20 Ghost Twin plays. Code: rulediscovery1__fepInspired/hdc/ (vsa.py, stage0-4), tests/test_hdc_vsa.py; results/hdc/.
- Stage 0 ground truth: 20 plays, 1774 actions, 88 rewinds, 19 plays with a ghost; simulator matches every trace board.
- Stage 1 phasor VSA: 5/5 tests pass (bind/unbind exact, near-orthogonal, fractional-power shift exact, cleanup). Bundle capacity (64-value codebook): D=4096 perfect up to 200 bindings, 0.977 at 400.
- Stage 2 tape: first run at chance -- the no-move code was the all-ones vector, which a cyclic shift leaves unchanged, so it swamped every read-out. Fixed by binding every move to a random MOVE role. D=4096: read-back 1.000 at length 200, 0.995 at 400.
- Stage 3 synthetic ghost: decision is per object (first version wrongly treated a genuine lag-1 copier as a rival), with a "stands still" null per object (without it still objects matched blocked moves by chance). 200 episodes: ghost explained right 197, wrong 3; lag-1 follower right 172 (the misses are the move/action clock tie when the player is never blocked); decoys falsely explained 1 of 600; decision 8-9 actions after the rewind (roadmap target was 5: fewer observations let decoys through).
- Stage 4 real plays (boards only): perception fixes needed first (player chooser picked the player's 1-pixel centre mark; level start was taken after the first move). Then: 72 of 88 true rewinds detected (49 created a ghost); a copy of an earlier run found after 26 of those 49, median 8 actions; the found object is the real ghost in 22 of 26; ghost's next move predicted exactly 239 of 257 (93 %); clock chosen: player-move count 19, action count 7 (the game's own rule is the move count). Undecided: about 9 of 23 had fewer than 8 actions before the next rewind; the rest mostly short previous runs where the ghost soon stands still, so the null ties.
- Roadmap gate for stage 4 (found in >= 90 %, next move >= 90 %): prediction passes, finding does not yet.

### Hyperdimensional roadmap stages 5-7 (24-Sep-2026, ~02:45 ET)

OpenMind: "continue with the roadmap: 5, 6, 7". Stage 4's gate (ghost found in >= 90 %) was not met; continued as asked.
- Stage-4 decision rule retry: summed evidence (decide as soon as a copy beats "stands still" by a margin) decided faster (median 4-6 actions) but was worse on the real plays at every threshold tried (2.5 / 4 / 5.5); kept the original mean rule.
- Stage 5 (hdc/stage5_posterior.py): two-hypothesis posterior on the true ghost's move, counts (chain back-off) vs counts + tape rule with a 6.5-nat price, 20 plays, 707 ghost steps. All steps: 1.004 -> 0.948 nats/step. On the 257 steps where the tape rule had decided: 0.559 -> 0.405 (about a quarter less). The tape rule ends a play with most of the weight in only 3 of 19 plays (it is found only about half the time, and wrong-object decisions cost it). Not wired into the agent's own RuleSet (rule contexts carry no run history).
- Stage 6 (hdc/stage6_live.py, "park a ghost" controller): learns the rewind button from perception in every seed and stops the compulsive rewinding (mean presses per 500 actions: plain agent 144, explorer 76, parker 8). Level cleared: 0 of 10 seeds for all three arms (language model: 10 of 30 recorded plays). Blockers found on the way, three fixed: (1) the switch pad, its wire and the door are one same-colour component, so "stand on it" was met at a corner of the wire's box -> targets are now solid pads (3x3 erosion); (2) one bump into the door walled off every cell of that colour, including the wire along the corridor -> a colour is a parking wall only after 3 blocked places and if never walked on; (3) a reset wiped the tried parking spots. Open: on a one-ghost level every second rewind erases the ghost, and the controller cannot yet tell a making rewind from an erasing one; game overs are frequent (26 in 10 seeds) because each parking cycle burns the ~128-action timer.
- Stage 7 (hdc/stage7_resonator.py): resonator network vs brute force for (source sequence, lag), time bound by a phasor so lag is a binding. Brute force right 1.00 in 8 of 9 settings (0.53 at 50 sources x 32 lags with 4 observed steps); resonator 0.23-0.97, worse everywhere, and only cheaper at the largest size. Per the roadmap rule it does not enter. Spatial semantic pointers for walls: not attempted.

## Soft-agent roadmap, Track A (24-Sep-2026, "do it!")
Code: `rulediscovery1__fepInspired/soft/` (uncommitted). Backup first: `backupsOldVersions/rulediscovery1__fepInspired_feef72470160/`.

**A0 labels** (`soft/a0_labels.py`): exact simulator replays of recorded plays. ls20 20 plays / 3563 actions / 549 blocked arrow presses; g50t 20 / 1774 / 518; wa30 20 / 3564 / 564; sp80 7 / 625 / 58; cn04 5 / 222 / 75. Gate met.

**A1 common-fate objects** (`soft/a1_common_fate.py`), pair recall / precision vs engine sprite masks:
ls20 0.999 / 1.000 (pass); g50t 0.859 / 0.958; wa30 0.753 / 0.358 (carried boxes move exactly with the player while carried -- genuinely the same fate); cn04 0.705 / 1.000. Beats the type-level rule on every game. Gate (95 %) met only on Locksmith. Bug fixed on the way: the "any" count first included only pairs where both moved (recall 0.743 -> 0.999 after fix).

**A2 co-change links** (ad hoc, pad level from `hdc/stage6_live.pads`): switch pad and door pad co-vanish 70 times over 20 Ghost Twin plays; with per-play normalised strength co/sqrt(n_a n_b), switch<->door is a top-3 link in 12 of 20 plays. The other top links are HUD indicator pads and player-trail artefacts. Gate "most plays" borderline pass; "false links rare" fails until HUD/trail pads are excluded.

**A3 soft wall map** (`soft/a3_walls.py`): phasor place (x) colour bundles for blocked and free outcomes, predict-before-see.
| game | presses (blocked) | soft acc / blocked recall / false walls | colour rule acc / blocked recall / false walls |
|---|---|---|---|
| ls20 | 3442 (536) | 0.982 / 0.897 / 6 | 0.964 / 0.778 / 5 |
| g50t | 1542 (475) | 0.853 / 0.684 / 77 | 0.769 / 0.288 / 18 |
| wa30 | 2100 (431) | 0.822 / 0.394 / 112 | 0.837 / 0.244 / 17 |
| sp80 | 445 (27) | 0.939 / 0.037 / 1 | 0.939 / 0.000 / 0 |
| cn04 | 162 (61) | 0.907 / 0.820 / 4 | 0.864 / 0.672 / 2 |
Robust to margin (0.02-0.1) and colour weight (0.5-1). Better than the colour rule on ls20, g50t, cn04; tie sp80; slightly worse on wa30 (walls there depend on the carried box, not place/colour). Wire gate FAILS: 39 false walls on 142 free presses into colour-8 (wire/door/switch share colour 8; door is a real wall). Sharper place codes or dropping the colour-only term made it worse (40-57). Next fix idea: condition on A2's door state (door open/closed as a context bound into the query) rather than place alone.

**A4 gauges** (`soft/a4_gauges.py`, 24-Sep-2026 ~10:00 ET): regions found from boards only (cells that ever changed, grouped; per colour, a pixel count that moves one way in small steady ticks with rare jumps back), value as a fractional-power phasor code G**n, next value = G**n bound with a context-keyed change memory (context = steps since the last tick (x) empty/reset/body token; two memories, with and without that clock, the one with the better recent record answers), cleaned up against the value codebook. Scored from the step the gauge was found on; labels only certify which engine gauge it is (count affine in the label on >= 95 % of steps).
| game | gauge | found | found at step (median) | predicted steps | model exact | baseline "same change as last step" | region frozen when found | if contact events known |
|---|---|---|---|---|---|---|---|---|
| ls20 | step bar (colour 11, rows 60-63) | 19 / 19 | 6 | 3426 | 0.929 | 0.862 | 0.930 | 0.972 |
| ls20 | lives | 0 / 19 | - | - | - | - | - | - |
| g50t | timer (colour 9, bottom rows) | 19 / 19 | 11 | 1546 | 0.991 | 0.001 | 0.991 | 0.997 |
Gate: both found in every play (pass). Next value >= 95 %: Ghost Twin pass; Locksmith FAILS (0.929). Why: of the 243 Locksmith misses, all but 17 are events the bar's own history cannot foresee -- 55 actions that changed nothing on screen (and cost nothing), 50 free steps onto the key-rotation tile (engine skips the step count on that contact; the key icon changes on all 50), 68 refills to full (pickups, or a life lost at an empty bar), 28 level changes (refill, then the first tick at level two's double rate), 25 game over / reset, 17 other. With the contact events supplied (free step, refill, level change) it would be 0.972, so the gate needs B1/E1 (what touching a thing does), not a better gauge model. Lives drop at most twice per play, under the six-tick minimum, so they are never found. Ghost Twin's baseline is near zero only because the timer ticks every second action; the clock context learns that. Vector decode equals its exact symbolic twin on 0.999 / 1.000 of steps; freezing the region as first found changes nothing (0.930 / 0.991), so the hindsight in the final region is harmless. Bug found on the way: a plain delta rule on the shared memory vector made contexts fight over every element and stored weights stalled near a third of their size; fixed by subtracting only the context's own cleaned-up content (vector vs twin agreement 0.94 -> 0.999).
Other games (no engine labels): wa30 a bottom-row bar (colour 7, 14 of 19 plays; in the rest the bar merged with the play area into one whole-board region), next value 0.798 vs baseline 0.553; sp80 a top-row bar (colour 14) plus a colour-14 bottom-edge region in all 6 plays (not checked what it shows), 0.691 vs 0.622; cn04 a top-row bar (colour 4, 5 of 5 plays), 0.836 vs 0.304. Results: results/soft/a4.json, a4.md.

## Second backup + hyperdimensional integration request (24-Sep-2026 10:17 ET, OpenMind)
Backup before integrating the phasor/HDC pieces into the agent: `ARC3-Inference/backupsOldVersions/rulediscovery1__fepInspired_5fe717f335a8/` (suffix = content hash, diff -rq identical, includes results/). Integration + with/without comparison handed to a forked helper; results to `results/soft/integration_ab.md`.

## HDC integration A/B (24-Sep-2026, OpenMind 10:17 ET)
Code (uncommitted, backup `backupsOldVersions/rulediscovery1__fepInspired_5fe717f335a8/`): one switch `AgentConfig.use_hdc` (default off; off reproduces the first sweep action for action, spot-checked on three seeds) plus `hdc_pieces` for per-piece runs. New `hdc_bridge.py` keeps the online state (ghost tape via the stage-3/4 finder, soft wall map, revocable common fate) and freezes per-step values into `RuleContext` (tape / walls / fate), so replay scoring stays exact (new test). Wired in: `rules.TapeRule` (modifier, gated on the player-move clock in `RuleSet.predict`); `MoveRule` asks the soft wall map only where its colour sets are silent (colour-first guard; soft-first was worse offline on all three games); group `FATE` takes the sprite's parts from common fate instead of `co_movers`; the fitter proposes these; the explorer uses the fate sprite and the soft map in its search. B1 not done.

Live, exact simulator, 10 seeds x 500 actions per game per arm, touch vs touch_hdc (per game, never pooled):
| game | levels cleared (touch -> hdc) | game overs | rules' gain over counts, nats/step | seeds hdc ahead |
|---|---|---|---|---|
| Ghost Twin g50t | 0 -> 0 | 7 -> 8 | 0.313 -> 0.538 | 10/10 |
| Locksmith ls20 | 10 -> 10 (level 1 every play, same clear actions) | 9 -> 9 | 0.409 -> 0.419 | 4/10 |
| Warehouse wa30 | 0 -> 0 | 3 -> 3 | 0.234 -> 0.326 | 7/10 |
Pre-committed headline: levels cleared do not move. The prediction gain comes from common fate alone (Ghost Twin +0.215, Warehouse +0.104, Locksmith 0; Warehouse did not get worse, so it is not gated). Soft wall map live about neutral (offline as wired: g50t accuracy 0.769 -> 0.851, ls20 0.964 -> 0.987, wa30 0.837 -> 0.831 with 116 vs 17 false walls). Tape rule wired but idle live: never gained posterior weight (tape-only plays identical to plain touch in every reported figure); the agent's runs are short, so when the finder decides the copied run is used up and it predicts "stands still", which cannot beat the counts. Absolute posterior surprise is not like for like across arms (different paths): g50t 1.525 -> 1.610, ls20 1.230 -> 1.224, wa30 1.740 -> 1.739. Revocable fusion did not help grouping offline (wa30 precision 0.359 -> 0.352, recall lower everywhere); the live win is instance-level grouping, not revocability. Cost: Locksmith 20 -> 74 s per play (tape bookkeeping on respawns). Tests: 40 passed, 1 failed (the pre-existing test_salience_ranks_disagreement_first); no new failures. Full tables: `results/soft/integration_ab.md` (+ .json), offline per-piece `results/soft/integration_offline.md`. Next: permanent vs revocable fusion live; let the tape claim "stands still" and decide earlier; ignore death respawns as rewinds.

## Tensor-logic overhaul (24-Sep-2026, OpenMind 12:26 ET; helper Claude Opus 5.5)
Code (uncommitted; backup `backupsOldVersions/rulediscovery1__fepInspired_6e55c3332208/`): new package `rulediscovery1__fepInspired/tl/` -- `engine.py` (sparse relations, join / projection / step with a temperature, forward chaining to fixpoint, learnable multilinear tensor equations whose gradients are themselves tensor equations, Adam with an L1 description-length step; no torch), `relations.py` (perception as a relational database: colour, type, controlled piece, common-fate group, colours ahead per move direction, run into / stood on / next to / clicked / moved along with the controlled piece, changed last step, own history, previous run's tape; per-object effect targets from the tracker), `learner.py` (six join shapes into one softmax per object; structure switched on by the zero-gradient test, also on surprise spikes with a backward-chaining explanation; thresholding at T=0, pruning to weights that fix at least two decisions, per-rule temperature from support), `rule.py` (TLRule: the frozen program as a Rule, weights in its identity so replay stays exact, priced in the templates' currency, forward-chained prediction, abstains before never-met obstacles at T=0), `plan.py` (explorer reachability by forward chaining), `bridge.py`, `offline.py`, `report.py`, `verify_default.py`; hooks in rules.py, agent.py, hypotheses.py, explore.py, game_sweep.py. Switches `AgentConfig.use_tl / tl_templates / tl_plan`, default off; off reproduces the backup action for action (Locksmith, Ghost Twin, Warehouse Associates, two seeds, 500 actions) and the live touch arm reproduced the morning sweep exactly on all nine games. No language model at run time.

Offline (S2, 19 recorded plays per game, same steps for every arm; rules' gain over counts, nats/step): Locksmith templates 0.482 / added 0.538 / alone 0.390; Ghost Twin 0.468 / 0.574 / 0.498 (ghost steps 1.24 / 1.66 / 1.78, door steps 1.09 / 1.51 / 1.83); Warehouse Associates 0.946 / 0.984 / 0.896. Rediscovered with templates off: Locksmith arrows 75/76 right and both template wall colours as walls in every play; bars ticking ("shrank last step -> shrinks again"); Ghost Twin ghost equation on in 5 of 19 plays, true lag (previous run per player move, no shift) in 2; Warehouse pushing as "a piece next to the controlled piece moves with it" (learned mover only about half right there).

Live (S3, tag tl_slippery7, 9 games x 3 arms x 10 seeds x 500 actions; per game, touch / touch_tl / tl_only): levels -- Locksmith 10/10/10 (median first clear 48/49/48); Ghost Twin 0/0/1 (tl_only seed 8 at action 183: first Ghost Twin clear of this agent, one seed, cause not established); Deck Control 1/1/0; Sigil Caster 1/1/1 (at 158/308/378); Mirror Rendezvous, Skewer Kebabs, Toggle Navigator, Toggle Runes, Warehouse Associates 0 everywhere. Rules' gain: Locksmith 0.409/0.559/0.538; Ghost Twin 0.313/0.422/0.423; Warehouse Associates 0.234/0.292/0.058; Mirror Rendezvous 0.165/0.246/0.202; Sigil Caster 0.084/0.208/0.070; Skewer Kebabs 0.032/0.084/0.088; Deck Control 0.182/0.203/0.076; Toggle Navigator 0.02/0.02/0.0; Toggle Runes -0.02/0.008/0.009. One lever in both directions (every level change is one seed of ten): the learned mover makes the explorer walk where the templates had no mover -- Toggle Runes game overs 3/10/10 (0 -> ~115 trips per play), Toggle Navigator tl_only 4 -> 8, but Skewer Kebabs tl_only 9 -> 2, and it plausibly bought the Ghost Twin clear; not yet separated from the rules' predictions (next experiment). Plays 1.5-3.5x slower. Learned rules in the final MAP in most plays (tl_only 6-10 of 10 except Toggle Navigator / Toggle Runes). Surprise spikes switched on 10 of ~150 equations. Not built: invented predicates as a hidden layer. Tests 50 passed, 1 pre-existing failure. Report: `results/tl/report.md` (+ .json); offline `results/tl/s2_offline.md`. Next: keep the learned mover out of game-over walks, relational pushing for Warehouse, earlier ghost equation, more seeds on the Ghost Twin clear.
