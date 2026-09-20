<!--
Author: Claude Opus 5 (Bubba sub-agent, label arc3-round4w-gameplay-eval)
Date: 20-September-2026
PURPOSE: Held-out gameplay evaluation of the round-4 arm-W LoRA adapter (the Boss's per-game
  write-up appended to the system prompt) against base and the round-3 adapter, on the seven
  fenced games. Records the box substitution forced by a108 being offline, the pre-flight
  gates run before any GPU hours were spent, the measured serving characteristics of a424,
  the per-arm gameplay numbers, and an explicit answer to the round-4 spec's falsifier.
SRP/DRY check: Pass -- the round-4 spec is docs/plans/2026-09-19-arc3-lora-round4-spec.md and
  is cited rather than restated; round 3's eval is docs/trace-findings/2026-09-19-arc3-round3-
  heldout-eval.md. Measurement is produced by the ARC3 harness; extraction and comparison are
  round4-arm-w-eval/collect_results.py and compare_arms.py. This file records method and
  numbers only.
-->

# ARC-3 round 4, arm W — held-out gameplay evaluation — 20-Sep-2026

**Status: IN PROGRESS.** This file is committed early on purpose, so the method and the
pre-flight measurements survive independently of whether the full pass schedule finishes.
Numbers are marked as they land. Anything not yet measured says so.

---

## 0. What is being tested

Arm W (PR #62, `ARC3-Inference/distill/writeup_to_sft.py`) retrains round 3's 89 human-replay
records with the Boss's full per-game write-up appended once to the system prompt. Round 3
trained on the same replays *without* the rationale and regressed gameplay hard: 7 levels to 2.
The round-4 spec's hypothesis is that the missing rationale, not the demonstrations, caused it.

The spec (§8.1) fixes the primary metric as **levels cleared and total score on the seven
fenced games** `ar25 re86 sb26 su15 tr87 tu93 vc33`, and states the falsifier:

> if arm W again shortens deliberation without improving clearance, the teacher is not the problem.

Held-out CE is explicitly *not* the metric (§8.2) and is not reported here as a result.

Training is not re-run and the corpus is not rebuilt. a424 `~/arc3-round4/ckpt/train_report.json`
records `rc=0`, 89 records, 2,281 turns, 89 steps, loss 0.2891 → 0.0380. The headline arm is
the final checkpoint `ckpt/adapter` (step 88).

---

## 1. The box substitution, and why no number here may be compared to round 3

The spec assumes gameplay runs on a108. **a108 was offline for the whole of this evaluation**
— Tailscale reported `offline, last seen 1h ago` and SSH timed out, re-checked several times
across the run. It never came back.

The eval therefore ran on **a424**, and that forces a second change. a108 served
`Qwen3.8-27B-NVFP4`; a424 has no NVFP4 copy of this model, only `Qwen3.8-27B-BF16`
(51.75 GiB of weights, `Qwen3_5ForConditionalGeneration`, dense). So:

- **Different box and different weights from round 3.** Round 3's 7-levels-base and
  2-levels-adapter numbers were measured on a108/NVFP4. **Nothing in this document may be
  compared against them.** `base` is re-run here as its own arm for exactly this reason, so
  all arms are matched on one box, one harness, one server process, one config.
- One thing is *better* than round 3: both adapters declare
  `base_model_name_or_path: /home/son/models/Qwen3.8-27B-BF16`, so here they are applied to
  the weights they were actually trained against. Round 3 applied a BF16-trained adapter to
  NVFP4 weights.

---

## 2. Pre-flight gates, run before any GPU hours were committed

### 2.1 The adapters are not a silent no-op on vLLM 0.24.0

This was the highest-probability way to get a confidently wrong answer. Round 3 documented
that for this architecture the LoRA packed-module mapping differs between vLLM 0.19.0 and
0.26.0, and that a no-op would present as "the adapter is neutral." a424 runs **vLLM 0.24.0**,
which neither round tested.

Resolved by measurement, using round 3's method — `/v1/completions`, greedy, `seed 0`,
identical prompt, token logprobs:

| arm | continuation | first six token logprobs |
|---|---|---|
| `qwen38-27b-bf16` | `' that the sum of the numbers'` | −1.435154, −1.701203, −2.826766, −0.027584, −0.598677, −0.703343 |
| `round4W` | `' that the sum of the numbers'` | −1.437091, −1.700912, −2.882107, −0.027578, −0.599402, −0.718204 |
| `round3` | `' that the sum of the numbers'` | −1.465341, −1.713144, −2.805110, −0.026607, −0.618752, −0.679176 |

All three arms differ from each other at every position. Both adapters are being applied.

Note the magnitude: **round4W's departure from base is smaller than round 3's** on this probe.
That is a single short prompt and is not evidence about gameplay, but it is recorded because
it was visible before any gameplay number was read.

**This also closes the prefix-caching objection.** Prefix caching is on and the arms run
sequentially against one server, so a reader should ask whether later arms are reading base's
cached KV. These three requests ran back-to-back on a byte-identical prompt and returned three
distinct results, which they could not do if the adapter were being bypassed by a cache hit.

### 2.2 Serving characteristics of a424, measured

| quantity | measured |
|---|---|
| decode, single stream | **4.51 tok/s** |
| decode, 7 concurrent lanes | **4.26 tok/s per lane**, 29.82 tok/s aggregate |
| implied rate in-harness, across prompts of 4.9k–24k tokens | flat **~3.7 tok/s** |
| GPU KV cache | 679,103 tokens |
| max concurrency at 102,985 context | **6.59x** |
| preemption events during base pass 1 | **0** |

Two consequences, both stated before the results:

- **Batching is nearly free** (4.26 vs 4.51 tok/s), so 7 lanes cost almost nothing per lane.
- **The harness rate does not degrade with prompt length** — a request with a 24k-token prompt
  showed the same ~3.7 tok/s as one with 4.9k. The bottleneck is decode, not prefill.
- Max concurrency 6.59x is below the 7 lanes used. a424 sits at 109/121 GB with swap already
  in use, so `gpu_memory_utilization` was **not** raised to buy headroom — thrashing a
  unified-memory box would be worse than occasional preemption. Preemption was then measured
  at zero for the pass that has completed, which shrinks this to a footnote.

### 2.3 Matched-pass parity

All arms run against **one vLLM process** with base and both adapters loaded as three served
model ids, so the only thing that changes between arms is which id the analyzer asks for.
Parity is checked mechanically with the ARC-3 oracle's own `parity()` flatten and ignore set
(`compare_arms.py`); the result is reported in §4.

---

## 3. The 900s read-timeout ceiling — the main caveat on this box

Base pass 1 lost **26 of 49 turns** to `request_error` read timeouts, costing 19,609s of the
37,800s total game budget. Round 3's a108 base lost 11 of 123. This is the clearest measure of
how much more compressed this box is.

The mechanism is arithmetic, not a fault: at the measured ~3.7 tok/s, a 900s analyzer timeout
truncates any turn that wants more than roughly **3,300 output tokens**. Median completed
request was 1,325 completion tokens, so typical turns finish; long deliberation turns do not.

Not all 26 are the ceiling. Counting the log, **19** hit the full 900s and **7** hit clamped
values (267, 300, 472, 515, 675, 768, 889s) — the harness shrinking a request's timeout to the
game's remaining budget. Those 7 are end-of-budget and would be unaffected by any timeout
setting.

**Raising the timeout was considered and rejected.** At 1800s, the same 3.7 timed-out turns per
game would cost 6,660s — more than the entire 5,400s per-game budget — and the payoff is
unmeasurable in advance, because timed-out requests report no `completion_tokens`. The
distribution above 3,300 tokens is unknown; the longest *completed* request was 3,076 tokens.

**The honest caveat this leaves.** The censoring is deliberation-length-dependent: an arm that
thinks less times out less and completes more turns. That mechanism favours a shorter-thinking
arm for reasons unrelated to capability. It is not hypothetical — round 3's adapter got 234
turns to base's 123 by exactly this route. It is also not sufficient to manufacture a win:
round 3 collapsed 7 levels → 2 *despite* that 90% turn advantage. Both arms face identical
censoring, so the comparison stays internally valid. Turns, deliberation and clearance are
reported as three separate columns per arm so a reader can see whether clearance moved with or
against turn count.

**Deliberation is reported in reasoning characters, not seconds.** Seconds on this box are just
characters ÷ 3.7 tok/s, so a seconds comparison against round 3's `307s → 162s` would be
measuring the GPU. The spec (§8.3) asks for reasoning per assistant turn, which is the
box-invariant quantity.

---

## 4. Results

*Pending — filled in as passes land. Base pass 1 is complete and is recorded below; the
remaining arms and passes are running.*

### Base, pass 1 (`runs/20260920_142058_r4w-a424-base-p1`, 14:20:58–15:58:41 UTC)

| game | lv | /total | score | actions | turns | err | tool% | mean reasoning chars |
|---|---|---|---|---|---|---|---|---|
| ar25 | 1 | 8 | 2.778 | 18 | 7 | 3 | 100% | 2,824 |
| re86 | 0 | 8 | 0.000 | 2 | 7 | 5 | 100% | 2,164 |
| sb26 | 1 | 8 | 2.778 | 9 | 8 | 4 | 100% | 1,636 |
| su15 | 1 | 9 | 2.222 | 23 | 9 | 3 | 100% | 2,477 |
| tr87 | 0 | 6 | 0.000 | 3 | 7 | 4 | 100% | 6,104 |
| tu93 | 0 | 9 | 0.000 | 0 | 5 | 4 | 100% | 509 |
| vc33 | 0 | 7 | 0.000 | 3 | 6 | 3 | 100% | 215 |
| **TOTAL** | **3** | 55 | **7.778** | 58 | 49 | 26 | **100%** | 2,456 |

All seven terminated `cancelled` at the 90-minute per-game cap. Tool validity is 100% of
answered turns, as in round 3.

**This pass doubles as the feasibility gate.** The question was whether a424 is so slow that
every arm floors at zero and a regression becomes invisible. At 3 levels / 7.778 there is
range in both directions — a round-3-style collapse would show, and so would a gain. The run
was allowed to continue on that basis.

---

## 5. Verdict

*Pending.*

## 6. Not verified / open questions

- a108 never returned, so this evaluation could not be run on the box the spec names, and no
  cross-box comparison is available. Unverified: whether a424 and a108 would rank the arms the
  same way.
- The distribution of intended output length above ~3,300 tokens is unmeasurable from these
  artifacts, because timed-out requests report no token count.
