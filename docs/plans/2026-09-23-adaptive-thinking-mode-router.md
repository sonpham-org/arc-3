<!--
Author: Claude Opus 5, for Son Pham
Date: 23-September-2026
PURPOSE: Design for Son's 23-Sep idea: stop trying to make each turn faster and instead spend
less thinking on turns where the game is already settled. Records the evidence that time still
buys score (132 vs 264 measured here), the three thinking modes the harness can already express
without a server change, the counterfactual-branch experiment that labels a turn as safe or not,
and the router that learns the switch. Also records the two prior results that constrain the
design and the four ways this can fail.
SRP/DRY check: Pass. The decision-step record is datasets/decision-steps/SCHEMA.md and is cited,
not restated. Harness values come from plans/2026-09-21-loop-b-arms-on-the-submission-harness.md
§1. The long-clock controller mechanics are gcp/controllers/dsv41-la-v5/README.md.
-->

# Adaptive thinking mode: spend the tokens where the game is not yet settled

**Requested by:** Son, 23-Sep-2026 — *"Maybe we cannot make it faster anymore, but maybe we can
make it strategically switch to medium or fast mode when things have been largely settled."*

**Status:** design + the measurements that motivate it. Nothing launched.

## 0. Why this is the right lever

Every long run dies on the wall clock, not on a decision (HARNESS-NOTES §1.7), so the currency is
**actions per run**. Two things measured for this plan, both from runs that already exist:

| clean-return, w7 | runs | mean score | total actions |
|---|---|---|---|
| 132 min | `…-74c4b3d97c`, `…-9677f73fbf`, `…-0cfc444a85` | 13.74 / 13.58 / 15.65 | 3,067 / 3,068 / 3,713 |
| 264 min | `…-df18d7c39d` (the only one of five that survived) | **25.07** | **7,129** |

Doubling the clock roughly doubled the actions and took the score from ~14.3 to 25.07. **There is
no ceiling visible at 264 minutes.** That justifies Son's step 2 (3x the clock) on its own, and it
also prices the router — but the marginal rate is worse than the average one, and the router is paid
at the margin: inside 132 minutes the harness scores a point per **229** actions, while the 3,846
*extra* actions the 264-minute run took bought 10.75 points, i.e. a point per **358** actions. Later
actions are worth ~35 % less than early ones (the 264 run's efficiency is 3.52 score/1k actions vs
4.36 at 132 min). Use **358 actions per point** for any router payoff estimate.

The same run gives the cost side: 4,505,797 generated tokens over 7,129 actions ≈ **632 generated
tokens per action**, at 284 tok/s aggregate across 7 lanes. Thinking is nearly all of that. So a
router that safely halves generated tokens on a fraction *f* of turns buys about `f/2` more actions
in the same clock — at f = 0.5, ~25 % more actions. On a 264-minute run that is ~1,780 extra actions
at the marginal rate of 358 actions/point, so **~5 points**, not the ~7 a naive average-rate estimate
gives. Worth having, and worth being honest that the router is paid in the cheapest actions.

**Which harness this rides on.** LA-CR (Loop A deletions on the shipped clean-return base) is the
best measured 132-minute harness: 18.01 / 19.24 mean score, 4 game wins across the pair, 5.19
score per 1k actions. Full census in §8.

## 1. What already constrains the design

Two results must not be rediscovered:

- **Global effort changes are neutral or worse.** The 22/23-Sep sweep moved reasoning effort,
  `xxhigh`, `nopreserve`, MTP, n-gram and 16k batch on LA-CR and none of them helped. So the win
  cannot come from lowering effort *on average*; it has to come from **selectivity**.
- **Thinking is the ingredient, and removing it is catastrophic.** The direct-agent arm with
  thinking off took 3,095 actions and cleared **0** levels; with thinking on it took 34 actions and
  cleared 1. More actions with no thought is worthless. The router must therefore be conservative:
  default HIGH, step down only on turns it is confident about, and the experiment must measure
  level clears, not action counts.

Together these say the same thing: the quantity to estimate is **per-turn**, and the null result of
a global knob is evidence *for* this design, not against it.

## 2. The three modes exist today — no server change

The tool agent's request builder already takes `thinking_override` and `max_tokens_override`
(`inference/agent/tool_agent.py:1586`), and `direct_agent.py:73` already defines what "medium"
means in this codebase. So:

| mode | how it is expressed | cost |
|---|---|---|
| **HIGH** (today's champion) | `thinking_override=None`, full `max_output` | ~632 gen tok/action |
| **MEDIUM** | `thinking_override=True`, `max_tokens_override=N` (N ≈ 1024–2048), retry once without thinking if `finish_reason == "length"` | target ~½ |
| **OFF** | `thinking_override=False` → sends `reasoning_effort: "none"` + `enable_thinking: false` | ~0 think tokens, **known catastrophic as a global setting** |

MEDIUM is a *token cap*, not a vendor effort level — that matters, because it works on Flash-Next
today and does not depend on the server honouring graded `reasoning_effort`.

## 3. Step 3 — what "store the context efficiently" has to mean

Two different requirements, and conflating them is the trap:

- **For labelling (step 4a, teacher-forced):** all that must be stored per turn is the **exact
  request** — messages, tools, sampling — which `_append_request_snapshot` already writes when
  `save_request_logs=True`. The champion runner sets it to **False**, so the mining run must turn
  it on, and its IO cost must be measured before the long run (§6.1).
- **For true branching (step 4b, divergent rollouts):** you must restore the **REPL** too. The
  python tool's sandbox state (`runtime_state.json`, saved helpers, `memory` ledger) is what makes
  turn *t+1* reproducible. Anything that re-runs the game from turn *t* without it is measuring a
  different agent.

Recommendation: **do 4a first**. It is ~100x cheaper, needs no state restore, and answers the
question the router actually asks ("would MEDIUM have chosen the same thing *here*?").

## 4. Step 4 — the counterfactual branch

For every logged turn *t* of the long run, replay the identical request under MEDIUM (and under OFF
as a floor), then label:

| label | definition | why |
|---|---|---|
| `action_same` | same action id and, for MOUSE, same cell | cheap, high precision, low recall — two different actions can both be fine |
| `ledger_same` | the `world_model` / memory update is semantically equal | catches "right move, lost the plot" |
| `expectation_same` | the `expected_observation` field agrees | the decision-step corpus already makes this the falsifiable unit (SCHEMA.md) — a turn where both modes predict the same next frame is a genuinely settled turn |

`safe(t) = action_same AND expectation_same`. Sample MEDIUM k=3 times per turn to separate "MEDIUM
is reliable here" from "MEDIUM got lucky once"; that also gives a confidence weight for training.

A rollout check (4b) on a **small sample only** — say 200 turns where `safe(t)` is true and 200
where it is false — re-runs the game forward N=10 actions from that turn in both modes and compares
levels cleared. That is what verifies the single-turn label predicts anything about outcomes, and
it is where the REPL restore has to work.

## 5. Step 5 — the router

Train in this order, cheapest first, and stop as soon as one works:

1. **Prior alone.** What fraction of turns are `safe`? If it is under ~20 % there is no prize and
   the project stops here for the price of one analysis.
2. **A logistic / GBM probe on cheap features**: turns since last level clear, actions since the
   frame last changed, whether the last action's `expected_observation` was confirmed, repeat-state
   count, level index, tokens the HIGH reply used, action-type entropy over the last k turns. All
   of these are computable **before** the HIGH reply exists, which is the whole point — the router
   must run *ahead* of the call it is deciding about.
3. **A LoRA head on the policy's own hidden states** only if (2) plateaus. Same tokenizer, same
   policy family, so it stays on-policy in the sense of Son's 15-Sep call: the router predicts a
   *mode*, never the content of a reply, so it does not reopen the no-teacher question.

**Serving shape:** whatever wins must be callable in <50 ms per turn, off the critical path, with a
fail-open default of HIGH. A 4B LoRA judge that costs a full generation per turn would eat the
prize it is trying to win.

## 6. Sequence

1. **Measure MEDIUM's real speed** on the existing serving stack — 200 replayed requests, HIGH vs
   MEDIUM vs OFF, tokens and latency per reply. **If MEDIUM is not meaningfully faster, stop.**
   No launch needed; this is a laptop-scale job against a served model.
2. **Cost the request logs**: turn `save_request_logs` on for one 132-minute run and measure the IO
   and disk. The long run is worthless if logging perturbs the thing being measured.
3. **The long run.** LA-CR, 396 min (3x), 7 lanes, request logs on. Reuse the long-clock controller
   (`gcp/controllers/dsv41-la-v5/`, which already lifts the runner's 2061 s/132 min/4 h pins) with
   Flash-Next in place of DeepSeek. **Not Spot, or accept retries:** four of the five 264-minute
   Spot runs died before finishing.
4. **Label** every turn (4a), then **verify** on the 400-turn rollout sample (4b).
5. **Train** the router in the order of §5, then run the paired arm: same clock, router on vs off.

## 7. How this fails

- **MEDIUM is not faster.** The cap binds on few replies, or the truncation retry costs a second
  call so often that it is a wash. Killed by step 6.1, cheaply.
- **`safe` turns are rare or unpredictable.** The prior is tiny, or the probe cannot beat it. Killed
  by §5.1–5.2, cheaply.
- **The single-turn label does not predict outcomes.** Turns labelled safe still lose levels ten
  actions later, because the damage from cheap thinking is cumulative, not local. This is the real
  scientific risk, and 4b is the only thing that catches it.
- **The router wins actions and loses levels.** The direct-agent result is exactly this failure at
  the extreme. The paired arm in §6.5 must be scored on levels/score, never on actions.

## 8. Harness census, 23-Sep (all w7, Flash-Next, 25 games)

Measured from each run's own `runs/summary.txt`, not from memory.

| harness | n | mean score | mean actions | score / 1k actions | wins |
|---|---|---|---|---|---|
| **LA-CR** (Loop A on clean-return) | 2 | **18.62** | 3,586 | 5.19 | **4** |
| LAB-v5 (Loop A+B on compaction v5) | 2 | 17.68 | 3,240 | **5.46** | 3 |
| LA-RF (LA + genre reframe) | 1 | 14.90 | 3,517 | 4.24 | 0 |
| clean-return — the 7.36 base | 3 | 14.32 | 3,283 | 4.36 | 1 |
| LA-v5 (Loop A on compaction v5) | 2 | 14.46 | 3,244 | 4.46 | 1 |
| LB-CR | 2 | 13.28 | 3,385 | 3.92 | 1 |
| LAB-CR | 2 | 13.23 | 3,298 | 4.01 | 1 |
| compaction-v5-clean-return | 2 | 12.66 | 3,281 | 3.86 | 0 |
| clean-return @ **264 min** | 1 | 25.07 | 7,129 | 3.52 | 2 |

LA-CR wins on total score; LAB-v5 is nominally the most action-efficient, but at n=2 each the gap
(5.46 vs 5.19) is inside the spread of the individual runs (6.26 / 4.72 against 5.33 / 5.07), so
treat them as tied on efficiency and separated on score.

The last row is the one that matters for §0: **efficiency falls as the clock grows.** Any plan that
buys actions must be scored against 358 actions/point, not 229.

### 8.1 The same census restricted to the hard seven

`bp35, g50t, lf52, ls20, sk48, tn36, wa30`. Score is the mean over those seven; actions and levels
are their totals. "ratio" is hard-seven efficiency divided by the same run's all-25 efficiency.

| harness | n | h7 score | h7 actions | h7 score/1k | h7 levels | ratio to all-25 |
|---|---|---|---|---|---|---|
| **compaction-v5-CR** | 2 | **4.23** | 1,006 | **4.20** | **9.0** | **1.09x** |
| LA-CR | 2 | 3.69 | 990 | 3.73 | 8.5 | 0.72x |
| LAB-v5 | 2 | 3.25 | 920 | 3.53 | 7.5 | 0.65x |
| clean-return (7.36 base) | 3 | 3.01 | 953 | 3.16 | 7.3 | 0.72x |
| LA-RF | 1 | 2.85 | 1,134 | 2.51 | 7.0 | 0.59x |
| LA-v5 | 2 | 2.59 | 984 | 2.63 | 7.0 | 0.59x |
| LAB-CR | 2 | 2.55 | 1,100 | 2.31 | 6.5 | 0.58x |
| LB-CR | 2 | 1.38 | 922 | 1.50 | 5.0 | 0.38x |
| clean-return @ **264 min** | 1 | **9.92** | 2,542 | 3.90 | **15.0** | 1.11x |

Three things follow, and the third changes §0.

1. **The overall ranking does not survive the restriction.** compaction-v5-CR is the *worst* harness
   overall (12.66) and the *best* on the hard seven — most efficient, most levels. LA-CR still leads
   among the arms that are also good overall, and LB-CR is last on both.
2. **Hard games are normally less efficient**, 0.58–0.72x the all-25 rate for most arms. The two
   exceptions are compaction v5 and the long clock, both above 1.0x.
3. **The marginal action is worth *more* on the hard seven, not less.** clean-return 132 → 264 took
   1,589 extra hard-seven actions and gained 6.91 hard-seven points: **230 actions per point**,
   against 358 for the all-25 marginal rate in §0. Time helps the hard games about twice as much as
   the easy ones (h7 score 3.01 → 9.92, a 3.3x lift, while all-25 went up only 1.75x).

**So the router should be priced and scored on the hard seven.** Its payoff there is ~230 actions
per point rather than 358, and the hard seven is the gate that arms are judged against anyway.

Caveat: n is 1–3 runs per arm and a single hard game swinging one level moves the h7 mean by ~1.4
points, so treat gaps under ~1 point as noise. The compaction-v5 result (n=2, both replicates
9 levels) is the one worth a dedicated repeat.

### 8.2 Cost per point — actions and tokens, all-25 and hard-seven

Score is the mean over the games in scope; actions and tokens are their totals, so "act/pt" and
"ktok/pt" are what one point of mean score costs. `tokens` in `summary.txt` is **generated** tokens
(25 games x ~180k = the header's total, and total/job-wallclock reproduces its tokens/sec).

| harness | n | score | act/pt | ktok/pt | tok/act | h7 score | h7 act/pt | h7 ktok/pt | h7 tok/act |
|---|---|---|---|---|---|---|---|---|---|
| **LA-CR** | 2 | **18.63** | **193** | **123** | 638 | 3.69 | 268 | 177 | 658 |
| LAB-v5 | 2 | 17.68 | 183 | 128 | 698 | 3.25 | 283 | 200 | 705 |
| LA-RF | 1 | 14.90 | 236 | 157 | 663 | 2.85 | 398 | 230 | 578 |
| LA-v5 | 2 | 14.47 | 224 | 157 | 698 | 2.59 | 381 | 244 | 641 |
| clean-return (7.36 base) | 3 | 14.33 | 229 | 169 | 737 | 3.01 | 316 | 223 | 705 |
| LB-CR | 2 | 13.28 | 255 | 175 | 685 | 1.38 | **666** | **477** | 716 |
| LAB-CR | 2 | 13.23 | 249 | 175 | 703 | 2.55 | 432 | 254 | 589 |
| **compaction-v5-CR** | 2 | 12.66 | 259 | 178 | 686 | **4.23** | **238** | **149** | 628 |
| clean-return @ **264 min** | 1 | **25.07** | 284 | 180 | 632 | **9.92** | 256 | 127 | **496** |

Marginal cost of the second 132 minutes (clean-return, 132 -> 264):

| scope | points gained | extra actions | act/pt | extra tokens | ktok/pt |
|---|---|---|---|---|---|
| all-25 | +10.74 | +3,846 | 358 | +2,088k | **194k** |
| hard-7 | +6.91 | +1,589 | 230 | +588k | **85k** |

Readings:

- **LA-CR is the cheapest harness per point overall** (193 actions / 123k tokens) and compaction-v5-CR
  is the cheapest **on the hard seven** (238 / 149k vs LA-CR's 268 / 177k). LB-CR is the outlier in
  the wrong direction: 666 actions and 477k tokens per hard-seven point, ~3.5x LA-CR.
- **Tokens per action barely move across arms** (~630–740). The arms differ in how many *points* their
  actions buy, not in what an action costs. So action-efficiency and token-efficiency rank the same
  harnesses, and the prompt edits are moving decision quality, not verbosity.
- **A hard-seven point is 2.3x cheaper in tokens at the margin** (85k vs 194k). Combined with §8.1,
  the long clock and the hard seven are the same bet.
- **The model already spends less per action late in a long game**: hard-seven tok/act falls to 496 at
  264 minutes against 628–705 for every 132-minute arm. That is weak but real evidence that "settled"
  turns exist and are *already* cheaper — the router's job is to find them earlier and deliberately,
  not to invent a phenomenon that does not occur.
