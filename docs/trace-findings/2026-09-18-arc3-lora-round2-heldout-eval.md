<!--
Author: Claude Opus 5 (Bubba subagent, arc3-lora-round2)
Date: 18-September-2026
PURPOSE: Round 2 of ARC-3 LoRA distillation on gx10-a424 (NVIDIA GB10). Round 1 trained an
adapter and never evaluated it; this round's headline is that evaluation. Covers the held-out
eval corpus (the inverse of round 1's fence), the evaluator's design, the base-vs-adapter
result -- which overturns round 1's own stated hypothesis -- the larger training run, and an
explicit list of what was NOT verified.
SRP/DRY check: Pass -- round 1 is recorded in docs/trace-findings/2026-09-17-arc3-lora-round1.md
and the gradient root cause in docs/trace-findings/2026-09-17-lora-gradient-rootcause.md. This
file cites both and restates neither. The sequence-ceiling measurement lives in
docs/trace-findings/2026-09-16-a424-lora-step-measurement.md.
-->

# ARC-3 LoRA round 2 — the held-out evaluation — 18-Sep-2026, gx10-a424

**Box:** `gx10-a424` (`son@100.106.31.61`), NVIDIA GB10, 121.63 GiB unified memory.
**Base:** `/home/son/models/Qwen3.8-27B-BF16`.
**Round 1:** [`2026-09-17-arc3-lora-round1.md`](2026-09-17-arc3-lora-round1.md) — 8 optimiser
steps, 1.20 h, flat loss, adapter never evaluated.

---

## The headline

**Round 1's adapter works, and round 1 could not have known it.**

Round 1 ended with a flat training-loss curve (0.5764 → 0.6033, no trend) and wrote down the
honest conclusion available at the time: *"'does nothing' is the hypothesis to beat."* That
hypothesis is now beaten. Measured on 40 held-out records from 6 games the adapter has never
seen:

| arm | token-weighted loss | perplexity | records improved |
|---|---|---|---|
| base (adapters disabled) | **0.558503** | 1.7481 | — |
| round-1 adapter | **0.548397** | 1.7305 | **40 / 40** |

Paired per-record delta: **mean −0.011662**, sd 0.004981, se 0.000788, **t = −14.81 (n=40)**.
Range −0.025151 to −0.004964. **Not one record got worse.**

A 40/40 sign count is p < 1e-12 under a sign test. The effect is *small* — about 1.0% off
perplexity — but it is not noise, and it is uniform: all six held-out games improve, and the
worst single record still improves.

> **The flat training curve was a measurement artifact, not a statement about the model.**
> Round 1 read learning off 8 step-losses whose windows contained different records each time;
> its own note that the within-window spread (0.4866–0.6599) exceeded any step-to-step
> difference was the tell. Eight optimiser steps *did* move a 27B measurably. The training
> curve simply had no power to see it, and a held-out paired comparison does.

Source: `/home/son/arc3-round1/eval/eval1.json` (`summary`), produced by
`ARC3-Inference/distill/eval_lora.py`.

---

## 1. The held-out corpus is the exact complement of round 1's fence

Round 1 fenced seven game codes (`vc33, ar25, sb26, re86, su15, tr87, tu93`) out of training.
Round 2 evaluates on exactly those games, built with a new `--only-games` flag that is the
**same matcher read the other way round** — same code, same before-the-renderer placement. An
eval set assembled by a second, independently written filter could silently disagree with the
training fence and leak a trained-on game into the held-out numbers.

The arithmetic checks out against round 1's measured fence cost, which is the point of quoting
it:

| | unfenced (round 1) | training (round 1) | **held-out (round 2)** | train + heldout |
|---|---|---|---|---|
| records | 80 | 40 | **40** | 80 ✓ |
| assistant turns | 738 | 440 | **298** | 738 ✓ |
| (game,pass) pairs | 64 | 36 | **28** | 64 ✓ |

**Independently verified, sharing no code with the filter that produced either file:** the two
JSONLs have **zero overlapping game codes** and **zero overlapping record ids**.

- training games: `bp35, cd82, cn04, ft09, ka59, lf52, lp85, ls20, r11l, s5i5, sp80, wa30`
- held-out games: `ar25:7, re86:8, sb26:8, su15:5, tu93:3, vc33:9` — 40 records

`tr87` contributes zero records, as round 1 measured: the extractor warns
`selected codes never seen in these runs: ['tr87']`. Six of seven fenced codes carry the eval.

### Held-out corpus scale

| | |
|---|---|
| records / turns / images | 40 / 298 / 120 unique |
| total tokens (through the real processor) | **1,031,188** |
| supervised tokens | **557,157** |
| token min / median / max | 8,353 / 24,738 / **53,956** |
| records per level | L1:28, L2:10, L3:1, L4:1 |

### Fence integrity: `as66` was checked, not assumed

`extract_sft.py --exclude-games`' own help text says the test-only game `as66` must be in the
fence list *when the run played it*. Round 1's seven-code fence did not include it. Checked
directly against both run dirs: the 25 game codes present are
`ar25 bp35 cd82 cn04 dc22 ft09 g50t ka59 lf52 lp85 ls20 m0r0 r11l re86 s5i5 sb26 sc25 sk48
sp80 su15 tn36 tr87 tu93 vc33 wa30` — **`as66` is not among them**, and `grep -rl as66` over
`~/arc3-round1/` returns nothing. Round 1's fence was complete for these runs. (Context:
[`2026-09-15-as66-the-withdrawn-26th-game.md`](2026-09-15-as66-the-withdrawn-26th-game.md).)

---

## 2. Why the evaluator is built the way it is

`distill/eval_lora.py`. Four design choices carry the result:

**One model, adapters toggled.** The 27B is loaded once and arms are switched with PEFT's
multi-adapter API; the `base` arm is `disable_adapter()` on those same weights. Base is
therefore *not a second model* — it is this model with the delta switched off, scoring a
bit-identical batch. Two processes would re-encode 120 board PNGs and any preprocessing
nondeterminism would land in the delta and read as learning.

**One scoring code path.** The assistant-span label mask, the image-token mask and the chunked
CE over a detached `lm_head` were extracted into `distill/sft_batch.py`, which the **trainer**
now imports too. Two hand-kept copies of a label mask that drift by one token produce a loss
delta that looks like learning and is arithmetic. *Verified behaviour-preserving:* round 2's
micro-step 1 loss is **0.5440**, byte-identical to round 1's micro-step 1 and to the
17-Sep standalone BF16 census on the same record.

**Records outer, arms inner.** One encode per record, every arm scored on it before it is
discarded, incremental JSON after each. A crash at record 30 leaves 29 usable *paired* rows.

**Paired statistics, and a token-weighted headline.** With 40 records the between-record spread
swamps any plausible effect, so the informative statistic is the paired sign count, not a
difference of two means. The headline aggregate is Σ CE ÷ Σ supervised tokens; the record-mean
is reported beside it and is a different number (0.570347 vs 0.558503 for base). Round 1's
phantom step-8 loss of 0.1508 was exactly this class of divisor slip.

**A gate that refuses to report a model compared with itself.** Before scoring, one record is
run through every arm; if any adapter arm scores *bit-identically* to base, the adapter is not
being applied and the run aborts rather than publishing a null. It passed:

```
base    loss 0.897728 over 2511 supervised tokens
round1  loss 0.874247 over 2511 supervised tokens
gate PASSED
```

**Eval is not bound by the 43,687-token training cap.** Forward-only under `no_grad` stores no
activations, gradients or optimiser state: the 53,956-token record peaked at **61.53 GiB**
against training's 98.74 GiB. Capping the eval at the training cap would have rebuilt round 1's
long-record bias *inside the measurement meant to detect it*. All 40 records scored, zero OOMs,
zero skips.

---

## 3. The inference round-trip (round 1's NOT-VERIFIED #2)

The adapter loads into a live model and changes generated text. Greedy, 96 tokens, on held-out
record `sb26-7fbdac44/p2/L3` (6,816-token prompt), full `AutoModelForImageTextToText` with KV
cache — not the loss path:

- **base:** `… magenta, pink, blue, orange — wait, that's 8). Let me count from the image: red, green, purple, yellow, magenta, pink, blue, orange = 8 slots.`
- **round-1 adapter:** `… magenta, pink, blue, orange — wait, that's 8. Let me count from the image: red, green, purple, yellow, magenta, pink, blue, orange = 8 slots).`

The difference is small and structural (the self-correction is re-bracketed as a parenthetical
rather than a new sentence) — which is what a −0.0117-nat adapter should look like. The point
is the boolean: `differs_from_base: {"round1": true}`. The adapter round-trips.

---

## 4. How big *should* the effect be?

Stated before the round-2 number lands, so it cannot be fitted to it.

This corpus is rejection-sampled from **the same 27B being fine-tuned**. It is
self-distillation / rejection-sampled RFT, not distillation from a stronger teacher. Held-out CE
therefore measures *"did the adapter sharpen the policy toward its own successful trajectories
on unseen games"* — **not** *"did the model get better at ARC-3."* The base model already
generates these trajectories, so the achievable headroom is bounded and small by construction.
A −0.01 held-out delta is a plausible fraction of the whole available gain. Correspondingly, a
*large* delta on a 29-record corpus would be more suspicious than encouraging.

**Held-out CE is not an ARC-3 score and must not be reported as one.**

---

## 5. Round 2's training run

Round 1's 8 optimiser steps is the thing being fixed. Wall clock is set by epochs × tokens and
not by `grad_accum`, so halving the accumulation buys 7× the updates for the same GPU time.

| | round 1 | **round 2** | why |
|---|---|---|---|
| epochs | 1 | **4** | the box has the headroom; round 1's own next-experiment note |
| grad_accum | 4 | **2** | free updates — same tokens, same wall clock |
| **optimiser steps** | **8** | **58** | 7.25× |
| micro-steps | 29 | **116** | 29 records × 4 |
| tokens | 882,826 | **3,531,304** | |
| lr / schedule | 1e-4 cosine | **1e-4 cosine, unchanged** | see below |
| save-every | 2 | **8** | an evaluable ladder: steps 8/16/…/56 |

**The learning rate was deliberately not changed.** Round 1's NOT-VERIFIED #9 says a flat curve
at 8 steps cannot separate "lr too low" from "too few steps". Changing only the step count
resolves exactly one of those cleanly; changing both would resolve neither.

**Corpus reproduces round 1 exactly** — 29 records / 247 turns / 228 images / 882,826 tokens,
the same 11 records dropped over the cap, the same 9 games. The probe re-measured the ceiling
independently and landed on the same number: **43,687 tokens fits, peak 98.45 GiB**.

Pre-flight at step 0, on a fresh adapter, before the run's riskiest allocation:

```
census lora_A: 0 / 208 nonzero      <- correct: lora_B is still zero, so A has no signal path
census lora_B: 208 / 208 nonzero
PRE-FLIGHT PASS
```

### Results

**PLACEHOLDER — filled in when the run completes.**

---

## 6. What was NOT verified

**PLACEHOLDER**

---

## 7. Reproduce

```bash
# on gx10-a424, GPU otherwise idle. The training corpus is round 1's, unchanged.
cd /home/son/arc3-round1/src/ARC3-Inference

# held-out eval corpus -- the inverse fence
/home/son/arc3-train-venv/bin/python distill/extract_sft.py \
  --run-dir /home/son/arc3-round1/runs/20260915_230835_qwen38-27b-baseline-25g \
  --run-dir /home/son/arc3-round1/runs/20260916_102724_qwen38-27b-massdata-25g-4p \
  --out /home/son/arc3-round1/data/sft_heldout.jsonl \
  --granularity level --upscale 4 --style plain --inline-images --filter-seed 0 \
  --only-games "vc33,ar25,sb26,re86,su15,tr87,tu93"

# round 2 training
/home/son/arc3-train-venv/bin/python -u distill/train_lora.py \
  --corpus /home/son/arc3-round1/data/sft_fenced.jsonl \
  --out-dir /home/son/arc3-round2/ckpt \
  --epochs 4 --grad-accum 2 --lr 1e-4 --schedule cosine \
  --census-every 4 --save-every 8 --seed 0 --probe

# evaluation
/home/son/arc3-train-venv/bin/python -u distill/eval_lora.py \
  --corpus /home/son/arc3-round1/data/sft_heldout.jsonl \
  --adapter round1=/home/son/arc3-round1/ckpt/adapter \
  --out /home/son/arc3-round1/eval/eval1.json --gen-tokens 96
```

**Never run training concurrently with another GPU job.** GB10 memory is unified; a second
allocation invokes the kernel OOM killer and takes bystander processes with it.

---

## 8. Raw results in this repo

Every number above is traceable to a committed file, not to a log on a box that may be wiped:

- `ARC3-Inference/distill/results/2026-09-18-eval1-base-vs-round1.json` — the full eval-1
  report: per-record base and adapter loss, paired deltas, the sanity gate, the generation
  round-trip, corpus stats, timings and peak memory.
