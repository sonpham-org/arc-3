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
also prices the router: in this regime roughly **250 extra actions ≈ 1 point of mean score**.

The same run gives the cost side: 4,505,797 generated tokens over 7,129 actions ≈ **632 generated
tokens per action**, at 284 tok/s aggregate across 7 lanes. Thinking is nearly all of that. So a
router that safely halves generated tokens on a fraction *f* of turns buys about `f/2` more actions
in the same clock — at f = 0.5, ~25 % more actions, worth ~7 points at the 264-minute operating
point if the conversion above holds.

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
