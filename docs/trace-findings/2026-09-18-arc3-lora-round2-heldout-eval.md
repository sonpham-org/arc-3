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

### Results — the run completed

| | round 1 | **round 2** |
|---|---|---|
| optimiser steps | 8 / 8 | **58 / 58** |
| micro-steps (records) | 29 / 29 | **116 / 116** |
| wall clock | 4,319.4 s (1.20 h) | **17,166.9 s (4.77 h)** |
| measured throughput | 204.4 tok/s | **205.7 tok/s** |
| tokens processed | 882,826 | **3,531,304** |
| per-micro-step | median 165.3 s | median **164.8 s**, min 45.0, max 224.3 |
| peak GPU memory | 98.74 GiB | **98.89 GiB** (cap 104.60) |
| **records skipped by OOM / guard** | 0 | **0** |
| checkpoints saved | 4 | **7** (steps 8,16,24,32,40,48,56) + final |

**Estimated before the run, from round 1's measured 204.4 tok/s: 4.80 h. Actual: 4.77 h.**
(The trainer's built-in prior of 241.9 tok/s printed 4.06 h; that prior was measured at
10,592 tokens and throughput falls with sequence length, so it is optimistic. The measurement
wins, and it was the measurement that was right.)

Gradient census at steps 1, 5, 9, …, 57 — **208/208 `lora_B` nonzero at every census, and
208/208 `lora_A` from step 5 onward** (0/208 at step 1 is correct: `lora_B` starts at zero, so
`lora_A` has no signal path until it moves). The full adapter trained for the whole run.

### The step curve is still unreadable, and that is now a known property rather than a finding

| step | 1 | 9 | 17 | 25 | 33 | 41 | 49 | 57 | 58 |
|---|---|---|---|---|---|---|---|---|---|
| loss | 0.5685 | 0.5270 | 0.5589 | 0.4681 | 0.5239 | 0.5139 | 0.5763 | 0.4859 | 0.5344 |

First → last is 0.5685 → 0.5344, and with 58 points a downward drift is visible where round 1's
8 points showed none. But it still oscillates by more than it trends, for the reason round 1
identified: **each step's loss is dominated by which two records landed in its window.** Every
window here has `window: 2`, so there is no divisor artifact this round — round 1's phantom
0.1508 at step 8 has no counterpart.

**Do not read learning off this curve.** Read it off the next table.

### The same 29 records, four times — this is the training-side learning signal

The trainer's record order is fixed across epochs, so every record is re-visited once per epoch.
Grouped by record id that is a **paired** series: the same record at four points in training,
with the accumulation-window confound removed entirely. Computed by
`distill/analyze_micro_log.py` from the trainer's own `micro_log`.

| epoch | record-mean loss | token-weighted loss |
|---|---|---|
| 0 | 0.563282 | 0.553005 |
| 1 | 0.543141 | 0.537844 |
| 2 | 0.529996 | 0.528573 |
| 3 | **0.523572** | **0.524223** |

**Monotone down, on both weightings, on all four epochs.** Paired epoch 0 → 3:
**29 / 29 records improved, 0 worsened**, mean −0.039710, sd 0.032283, **t = −6.62**. All 29
records were present in every epoch — zero OOM skips — so the epoch means compare the identical
record set and cannot have moved by changing the sample.

This is training loss, so it shows the model fitting its training data and says nothing on its
own about generalisation. That is what the held-out eval is for.

### Round 2's held-out evaluation — queued, not yet measured

**Status: pending, and the reason is specific rather than an excuse.** Round 2's held-out
eval was launched at 21:31 UTC and was **killed by the kernel OOM killer during model load**
(`Out of memory: Killed process 1023047 (python)`, no Python traceback — a silent death that
reads like a crash and is not one).

Cause: a **LoRA round 3** training job for a different experiment (the windowed human-demo
corpus, PR #52) had a queue watching round 2's training PID. Round 2 exited at 21:31:32, round
3 launched at 21:33:32 after its 120 s settle — and this eval had started allocating inside
that window. Two concurrent 27B BF16 loads are ~108 GiB of weights alone on a 121.63 GiB
unified-memory box. Exactly the failure round 1's §7 warns about, arriving from the one
direction neither job could see: each had correctly checked that *training* was clear.

Round 3 peaks at 65.87 GiB and has ~4.9 h to run. A second 27B load does not fit beside it, and
killing a 178-step run of someone else's experiment to reclaim the GPU was not a trade worth
making. The eval is therefore **queued** behind round 3's PID, by the same pattern round 3 used
to queue behind round 2:

- script: `ARC3-Inference/distill/run_eval2_queued.sh`, deployed to
  `/home/son/arc3-round2/eval/run_eval2_queued.sh` — waits on PID 1023305, 180 s settle, then a
  guard against **any** other `train_lora.py` *or* `eval_lora.py` process. The guard re-arms
  rather than exiting: a collision costs a delay, not the evaluation.
- ledger: `/home/son/arc3-round2/eval/queue.log`
- output: `/home/son/arc3-round2/eval/eval2.json`, log `eval2.log`

Arms when it runs: `base`, `round1`, `round2` on the full 40 records; `round2-step8/16/32/48`
on a fixed 12-record length-spread subset, giving a dose-response ladder rather than two points.

#### How the result will be read — written down before the number exists

The discriminating statistic is **not** whether round 2 beats base. It will; round 1 already
does, on 40 of 40. It is the **paired `round2 − round1` delta on the same 40 records.** All
three outcomes are publishable, and committing to the reading now is the cheapest available
protection against fitting the interpretation to whatever lands:

| if | reading |
|---|---|
| **round2 clearly better than round1** | 7× the optimiser steps bought generalisation, not just training-set fit. The step-8/16/32/48 ladder should then show a monotone trend; if it does not, the endpoint is suspect. |
| **round2 ≈ round1** | 8 steps already captured the available headroom. That is the self-distillation ceiling of §4 being real and being hit — an informative negative, not a failure. |
| **round2 worse than round1** | Overfitting at 4 epochs on 29 records, exactly what 29/29 training-loss improvement also looks like. The ladder then localises where it turned, which is the most useful of the three outcomes. |

Note that the third row is fully consistent with everything measured so far. The training-side
result is *not* evidence against it.

#### The transferable finding: this box needs a GPU lock, not a longer settle

Two independent agents each checked the right thing — "is a training job running?" — each got the
right answer, and the box still died. Neither could see a *non-training* 27B load, because no
convention existed for announcing one. Lengthening settle windows does not fix that; it only
narrows the window in which it happens.

**Recommended next action, worth more than another decimal place of loss:** a single advisory
lock on a424 (e.g. `flock` on `/home/son/.gpu-a424.lock`) that *every* job taking the GPU
acquires, training and evaluation alike, with the holder's PID and command in the file. The
queue scripts already exist and already cooperate; they are just cooperating on the wrong
signal.

**What this means for the round's verdict:** the headline evaluation — a measured
adapter-vs-base comparison on held-out material — **exists and is complete** (§ *The headline*,
40/40 records, t = −14.81). What is outstanding is specifically the *round-2* adapter's
held-out number, i.e. whether 58 steps generalises better than 8. Until that file exists, **no
claim is made here about round 2 beating round 1 on held-out data.** The training-side evidence
above is consistent with it and is not a substitute for it.


---

## 6. What was NOT verified

Stated explicitly because a wrong green light costs more than a red one. Round 1 had ten; this
round closes five of them and adds its own.

**Closed by this round:**

- Round 1 #1 (*adapter never evaluated*) — **closed for round 1's adapter.** 40 held-out
  records, 40/40 improved, t = −14.81.
- Round 1 #2 (*adapter never loaded for inference*) — **closed.** It loads into a live model
  and changes generated text (§3).
- Round 1 #7 (*no held-out loss, overfitting unobservable*) — **closed.** There is now a
  held-out corpus, fenced and leakage-checked.
- Round 1 #8 (*multi-epoch behaviour unknown*) — **closed.** Four epochs, monotone per-epoch
  training loss on identical records, 29/29 improved.
- Round 1 #6 (*`tools/assert_lora_gradients.py` never run against the 27B*) — **still open as
  written**, but the trainer's in-run census passed at every one of 15 censuses across 58 steps.

**Open, and new:**

1. **Round 2's adapter has no held-out number yet.** The eval is queued behind round 3 (see
   above). Everything said here about round 2 is training-side. **If the queued eval shows round
   2 no better than round 1 on held-out loss, that is the result and it must be reported as
   such** — 58 steps of training-loss improvement on 29 records is exactly what overfitting also
   looks like.
2. **No ARC-3 score was measured, for any adapter.** Held-out cross-entropy is not a score. The
   adapter has never played a game. A CE improvement that does not convert into solved levels is
   entirely possible and is the outcome the next round has to test.
3. **Self-distillation bounds the whole result** (§4). The corpus is rejection-sampled from the
   same 27B being trained. Held-out CE measures policy sharpening toward its own successful
   trajectories, not capability gain.
4. **n = 40 held-out records over 6 games**, and 9 games / 29 records in training. Both are far
   too small to generalise from; `ft09` alone is 28% of the training corpus. The paired t is
   large because the effect is *consistent*, not because the corpus is big.
5. **The effect size is small and could be a style artifact.** −0.0117 nats is ~1.0% of
   perplexity. Some of it may be the adapter matching the corpus's *formatting* conventions
   rather than its reasoning — the generation round-trip's visible difference was a punctuation
   restructure. Nothing here separates those two.
6. **Correlation between record length and benefit is +0.562** — longer held-out records improve
   *less*. Unexplained. It may be dilution (a fixed-size behavioural change spread over more
   tokens) or it may be that the adapter helps early-game reasoning and not late. Not tested.
7. **The 11 over-cap records are still excluded** (round 1 #5, unchanged): 40 extracted → 29
   trained. The longest trajectories, plausibly the most valuable, remain unrepresented in
   training. Note the *eval* does not share this bias — it scores all 40 including a
   53,956-token record — so the training distribution is shorter than the eval distribution.
8. **Only the final and 7 laddered adapters were disk-verified for round 2** (416 tensors,
   208/208 nonzero both sides, 39,583,744 params, final md5 `a96009af37209122bbf62f669590d4dc`).
   The ladder checkpoints' *contents* were not each independently re-checked.
9. **The learning rate is still untuned** (round 1 #9). 1e-4 was held fixed on purpose so step
   count was the only variable. No sweep has been run, at any step count.
10. **`causal_conv1d` is still not installed** (round 1 #10), so all 48 gated-delta layers run a
    reference PyTorch fallback. Every throughput figure in this document is pessimistic by an
    unmeasured margin.
11. **PR #30's correctness is still verified by presence, not behaviour** (round 1 #3).
    `distill/verify_frames.py` was not run this round either.
12. **The `sft_batch.py` refactor is verified by one number**, not a test suite: round 2's
    micro-step 1 loss of 0.5440 reproduces round 1's exactly. That is a strong signal on the
    path it exercises and says nothing about paths it does not.
13. **The kg-lab-worker CPU lab was not disabled and was observed running before and after**
    (17 processes at launch). It is request-driven, so an idle count of 0 during the run is not
    evidence of breakage — and equally, **it was not positively verified to have completed work
    while training held memory.** The brief permitted fallback to the Mac Mini; whether it fell
    back was not measured.


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
- `ARC3-Inference/distill/results/2026-09-18-round2-train-report.json` — the round-2 training
  report: config, probe, corpus measurement, the 58-step log with its gradient censuses, and
  the 116-entry `micro_log` the per-epoch table is computed from.
- `ARC3-Inference/distill/results/2026-09-18-round2-epoch-summary.json` — the output of
  `distill/analyze_micro_log.py --json` on that report.
- `ARC3-Inference/distill/results/2026-09-18-eval2-*.json` — **not present yet.** Produced by
  the queued eval described above; land it here when `/home/son/arc3-round2/eval/eval2.json`
  exists.
