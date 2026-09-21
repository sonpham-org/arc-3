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

**Status: COMPLETE, and stopped short of the planned schedule.** The spec asked for n=3 per
arm. **n=1 is complete and matched across all three arms and is the result.** n=2 finished for
`base` and `round3` only; arm W's second pass was destroyed twice and the run was then stopped
because **the eval workload was rebooting the box** (§4.9). That was a stability decision, not
a measurement decision, and it was not the Boss's call to make because the interim never
reached him — see §7.

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

## 4. Results — the n=1 sweep

Parity checked mechanically with the oracle's `parity()` flatten and ignore set: every arm
against base pass 1 returns `unexpected_diffs = ['.model']`. **The only configuration
difference between the arms is which served model id the analyzer asks for.**

| arm | levels | score | actions | turns | timed-out turns | tool% | reasoning chars/turn | mean turn s |
|---|---|---|---|---|---|---|---|---|
| base | **3** | **7.778** | 58 | 49 | 26 | 100% | 2,456 | 807 |
| round3 | **3** | 6.971 | 152 | 76 | 15 | 100% | 1,946 | 503 |
| **round4W** | **1** | **2.778** | 57 | 55 | 13 | 100% | 2,429 | 709 |

Per game, levels cleared and score:

| game | base | round3 | round4W |
|---|---|---|---|
| ar25 | 1 / 2.778 | 0 / 0.000 | 0 / 0.000 |
| re86 | 0 / 0.000 | 0 / 0.000 | 0 / 0.000 |
| sb26 | 1 / 2.778 | 1 / 2.778 | 1 / 2.778 |
| su15 | 1 / 2.222 | 1 / 2.033 | 0 / 0.000 |
| tr87 | 0 / 0.000 | 0 / 0.000 | 0 / 0.000 |
| tu93 | 0 / 0.000 | 0 / 0.000 | 0 / 0.000 |
| vc33 | 0 / 0.000 | 1 / 2.160 | 0 / 0.000 |

All 21 game-runs terminated `cancelled` at the 90-minute cap. Tool validity is 100% of
answered turns in every arm — as in round 3, this is not a formatting or tool-use break.

### 4.1 The falsifier does not fire as written, and the reason matters

The spec's falsifier is:

> if arm W again shortens deliberation without improving clearance, the teacher is not the problem.

**Arm W did not shorten deliberation.** At 2,429 reasoning characters per answered turn it is
within 1% of base's 2,456, and well above round 3's 1,946. On the quantity round 3 was
supposed to have broken, **arm W looks like base, not like round 3.** The write-up appears to
have done what it was meant to do.

So the antecedent is false and the falsifier as phrased does not fire. What happened instead
is worse for the hypothesis, not better: **deliberation was restored to base levels and
clearance still went down** — 3 levels to 1, 7.778 to 2.778, at n=1. Round 4's premise was
that round 3 lost capability by losing the reasoning. Arm W got the reasoning back and did not
get the capability back. On this evidence, restoring rationale is not sufficient.

Stated precisely, because it is the whole point of the round: the spec offered a two-way test
and got a third outcome. The honest reading is not "the teacher is the problem" and not "the
teacher is not the problem," but **"deliberation length was never the mechanism"** — round 3's
shortened turns were a symptom that travelled with the regression, not its cause. Fixing the
symptom did not fix the outcome.

### 4.2 Round 3 did not collapse on this box

Round 3 scored 3 levels / 6.971, level with base on levels. On a108 it scored 2 against base's
7. **Its behavioural signature is intact** — shortest deliberation of the three arms, most
turns (76), and by far the most actions (152 against base's 58) — but the clearance loss is
absent.

This is recorded as an observation, not explained. Candidate accounts, none tested here:
a108 applied a BF16-trained adapter to NVFP4 weights whereas a424 applies it to the BF16
weights it was trained on; or this box's compressed turn budget compresses all arms toward
each other. **Unverified.** Distinguishing them needs a108, which was unavailable.

**This claim is under-powered and must not be quoted as established.** Round 3's own two
passes on this box were **3 levels and 1 level** (§4.4). A single 3-level pass is weak evidence
that round 3 "does not collapse here" when its very next pass landed at 1. The fair statement
is that round 3's a424 result is *not obviously a collapse*, and that its second pass is
indistinguishable from arm W's first. Round 3's a108 collapse may still be real; this run
neither confirms nor refutes it, and any suggestion that PR #59 was wrong would be over-reading
two passes.

### 4.3 What n=1 can and cannot support

These are single stochastic samples at temperature 1.0. Arm W is below base on 2 of 7 games
(ar25, su15), tied on 5, and ahead on none. Two games is not significant on a sign test.
**The direction is suggestive; the magnitude is not usable.**

### 4.4 The second passes, and why they are variance evidence rather than an arm comparison

`base` and `round3` each completed a second pass. **Arm W did not** — its pass 2 was destroyed
twice (§4.9). So there is no matched n=2 comparison, and none is offered:

| arm | pass 1 | pass 2 | levels | score |
|---|---|---|---|---|
| base | 3 lv / 7.778 | 2 lv / 5.556 | **[3, 2]** | [7.778, 5.556] |
| round3 | 3 lv / 6.971 | 1 lv / 2.778 | **[3, 1]** | [6.971, 2.778] |
| round4W | 1 lv / 2.778 | *(destroyed)* | **[1]** | [2.778] |

**Averaging base and round 3 over two passes and comparing that to arm W's single pass would
be an unmatched comparison, and the parity discipline applied everywhere else in this document
forbids it.** The second passes earn their place for one reason only, and it is an important
one:

> **The pass-to-pass spread inside an arm is about as large as the gap between arms.**
> Round 3 moved 3 → 1 across two passes of the *same* adapter on the *same* box. Arm W's single
> pass scored 1. On this evidence arm W's 1-level pass is not distinguishable from an ordinary
> low draw of an arm that also produces 3-level passes.

This is the single most important limitation on everything above. The n=1 *ordering*
(base ≥ round3 > round4W) is what this run supports. The *size* of arm W's deficit is not
established, and a reader who takes "3 levels to 1" as an effect size will be over-reading it.

---

## 4.9 Infrastructure: three destroyed passes, and the run being stopped

Three arm-W passes were destroyed. **None of them is in any table**, and all three run dirs are
preserved on a424 under `DISCARDED_` prefixes rather than deleted.

**1. `DISCARDED_vllmwedge_20260920_173604` — vLLM wedge.** About 90 seconds in, vLLM stopped
producing tokens: generation throughput 0.0 tok/s with 7 requests running, KV usage flat at
5.5%, and **no engine log line for 29 minutes** while the EngineCore process sat at 96% GPU and
296% CPU with its main thread in state `R` and all workers parked in `futex_do_wait`. That is a
wedge, not slow generation. Its four completed requests beforehand were unremarkable
(245–367 completion tokens, 77–110s), so nothing about the adapter's output explains it. Every
subsequent "timeout" in that run was a dead server. After a restart the pass was re-run in full
and completed `rc=0` with healthy generation — **the wedge did not reproduce**, so it is
recorded as a one-off on vLLM 0.24.0 and not as an arm-W property. The re-run
(`20260920_181652`) is the pass reported in §4.

**2 and 3. `DISCARDED_reboot_20260920_230111` and `DISCARDED_reboot2_20260921_000355` — the box
rebooted, twice.** a424 rebooted at **23:54** and again at **00:12**, each time killing the
arm-W pass in flight. `last -x reboot` shows no other reboot on this box since 30-Aug, so these
two are ours.

### The cause, and it is this eval's own configuration

From the kernel log of the boot in between:

```
Sep 21 00:01:53 gx10-a424 kernel: NVRM: nvCheckOkFailedNoLog: Check failed:
  Out of memory [NV_ERR_NO_MEMORY] (0x00000051)
  returned from _memdescAllocInternal(pMemDesc) @ mem_desc.c:1359
```

That fired during this eval's own vLLM start. The arithmetic behind it:

| | |
|---|---|
| host memory, total (unified) | **121 GB** |
| model weights, BF16 | **51.75 GiB** on disk, ~66 GB resident |
| KV cache at `gpu_memory_utilization: 0.85` | **43.56 GiB** |
| observed steady-state during passes | **109–111 GB used, swap active** |

**`gpu_memory_utilization: 0.85` is not survivable for a long run on this box.** It leaves
single-digit GB for the OS on a machine where GPU and host memory are the same pool. It held
for roughly eight hours and five passes, then stopped holding. This is a defect in how this
eval was configured, not a fault of a424, and it is the direct reason the run stopped.

**Recommendation for the next eval on a424:** drop `gpu_memory_utilization` to ~0.75 and
re-measure. The cost is a smaller KV cache and therefore fewer than 7 lanes, which scales wall
clock up in proportion — the spec's §8.3 already prices that at roughly 27h for 9 passes at 4
lanes. A slower schedule that finishes beats a faster one that reboots the box.

**Why the run stopped here rather than continuing at lower utilization.** Lowering utilization
changes the server configuration, so a sixth pass run that way would not be matched to the five
already banked — it would not produce the balanced n=2 it was meant to produce. Continuing at
0.85 meant continuing to crash someone else's machine. Neither option produced a comparable
arm-W pass 2, so the run was stopped and the box left clean.

### Server-level parity wrinkle across three boots

The server was booted three times from byte-identical configuration, and profiled a **different
KV cache each time** because a different amount of host memory was free. `run_config.json`
cannot show this, so it is recorded explicitly:

| boot | KV cache | max concurrency @ 102,985 | passes run under it |
|---|---|---|---|
| 1 | 679,103 tokens | **6.59x** | base-p1, round3-p1 |
| 2 | 732,835 tokens | **7.12x** | round4W-p1 |
| 3 | 638,805 tokens | **6.20x** | base-p2, round3-p2 |

All three are at or below the 7 lanes actually used. **Measured preemption was zero in every
pass**, so no pass is known to have been throttled by this — but the arms are not perfectly
matched at the server level, and arm W's reported pass ran under the *most* favourable of the
three. That direction matters: it cannot explain arm W scoring lower.

### Final state of a424

vLLM stopped, no compute processes on the GPU, **GPU utilization 0%**, memory back to
**3 GB used of 121**, stale server PID file removed, and the three `DISCARDED_` run dirs left
in place as evidence. `~/arc3-round2`, `~/arc3-round3` and the oracle `banked/` dirs were never
touched; nothing outside `~/arc3-round4/eval/` was written.

---

## 5. Verdict

**Arm W did not improve gameplay. On the one matched sweep this run completed, it was the
weakest of the three arms** — 1 level / 2.778 against base's 3 / 7.778 and round 3's 3 / 6.971,
on seven held-out games it was never trained on, with arms differing only in `.model`.

**The spec's falsifier does not fire, because its antecedent is false.** It required arm W to
shorten deliberation. Arm W matched base within 1% (2,429 vs 2,456 reasoning characters per
answered turn) and sat well above round 3's 1,946. The write-up did the thing it was designed
to do: it put the reasoning back.

**And clearance still fell.** That is the finding. Round 4's premise was that round 3 lost
capability *because* it lost the rationale, with shortened deliberation as the visible symptom.
Arm W restored the deliberation and did not restore the capability. The most defensible reading
is that **deliberation length was a symptom that travelled with round 3's regression, not its
mechanism** — so a fourth round aimed squarely at that symptom was aimed at the wrong thing.

What this does **not** establish:

- **Not a magnitude.** n=1. Round 3's own passes on this box ran [3, 1], a spread as large as
  the gap being measured. Arm W's single 1-level pass is not distinguishable from a low draw.
- **Not a formatting or tool-use failure.** Tool validity was 100% of answered turns in every
  arm, as in round 3.
- **Not a comparison to round 3's a108 numbers.** Different box, different weights. Base was
  re-run here precisely so that no such comparison is needed.
- **Not a verdict on the write-up corpus itself.** Only the final checkpoint (step 88) was
  tested. The checkpoint ladder (`adapter-step44`, `adapter-step22`) was scheduled after the
  main arms and **was never reached.** Given that round 2's gain was done by step 16 and step 48
  regressed, and that arm W ended at loss 0.0380 — round 3's neighbourhood — an over-training
  explanation for arm W's result **remains open and untested.** That is the single most
  valuable follow-up.

---

## 4.99 Appendix — base pass 1, per game

*(retained from the first commit)*

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

## 6. Not verified / open questions

- **The checkpoint ladder was never run.** `adapter-step44` and `adapter-step22` are untested.
  Over-training is an open explanation for arm W's result. Highest-value follow-up.
- **No matched n=2.** Arm W has one pass; base and round 3 have two. n=3 was never approached.
- a108 never returned, so this could not run on the box the spec names, and no cross-box
  comparison is available. Unverified: whether a424 and a108 would rank the arms the same way,
  and whether round 3's a108 collapse is a serving artifact.
- The distribution of intended output length above ~3,300 tokens is unmeasurable from these
  artifacts, because timed-out requests report no token count.
- The vLLM wedge (§4.9) has no root cause. It did not reproduce; it is unexplained, not fixed.

## 7. Process note: the interim never reached the Boss

The brief asked for an interim post to `#arc-3` after the n=1 sweep, and for the Boss to decide
n=2 versus n=3 against measured wall clock. **The n=1 sweep completed and the interim was
written, but every attempt to post it failed** — the agent's Discord tool returned
`MCP server "openclaw" is not connected` from roughly 19:00 UTC onward (the gateway itself was
healthy; the session's MCP bundle had dropped). Roughly ten attempts over six hours all failed.

Two consequences, stated plainly rather than papered over:

1. **The Boss never got the n=2-versus-n=3 decision he was supposed to make.** The run continued
   to n=2 by default, per the brief's instruction to proceed absent direction.
2. **The run then stopped on box instability, not on his call.** Had the interim landed, the
   recommendation in it was to stop at n=2 and spend the saved passes on the `adapter-step44`
   ladder arm. As it happened, neither the third passes nor the ladder were run.

Results were committed and pushed to PR #65 as they landed for exactly this reason, so the
measurements survived the comms failure.
