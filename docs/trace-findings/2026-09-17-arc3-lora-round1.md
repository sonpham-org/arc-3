<!--
Author: Claude Opus 5 (Bubba subagent, arc3-lora-round1)
Date: 17-September-2026
PURPOSE: Record of the first real LoRA training round for ARC-3 distillation on gx10-a424
(NVIDIA GB10). Covers corpus extraction and the held-out test-set fence, the gradient
pre-flight, the sequence-length ceiling (which the brief had wrong), training configuration
and results, and an explicit list of what was NOT verified. Written so round 2 does not
re-derive any of it.
SRP/DRY check: Pass -- the root cause of the gradient bug lives in
docs/2026-09-17-lora-gradient-rootcause.md and the step/memory measurements in
docs/2026-09-16-a424-lora-step-measurement.md. This file only records round 1.
-->

# ARC-3 LoRA round 1 — 17-Sep-2026, gx10-a424

**Status:** **completed** — 8/8 steps, 1.20 h, adapter saved. Pipeline verified end to end; **no learning signal in the loss**, and the adapter is unevaluated. See [Results](#5b-results--attempt-3-completed) and [What was NOT verified](#6-what-was-not-verified). **Box:** `gx10-a424` (`son@100.106.31.61`), NVIDIA GB10,
121.63 GiB unified memory. **Base:** `/home/son/models/Qwen3.8-27B-BF16`.
**Code:** PR [sonpham-org/arc-3#35](https://github.com/sonpham-org/arc-3/pull/35).

---

## 1. Pre-flight — cited, not re-run

The brief allowed the pre-flight to be satisfied by the BF16 gradient census if that census
proved 208/208. It did. `/home/son/arc3-lora-bf16-step/step_bf16.log`, run 11:52–12:00 EDT
17-Sep on the real 27B BF16 checkpoint:

| check | result |
|---|---|
| LoRA modules matched | **208** (q/k/v/o × 16 attention + in_proj_qkv/in_proj_z/out_proj × 48 gated-delta) |
| trainable params | **39,583,744** (0.1445% of 27,396,312,304) — matches the brief exactly |
| trainable vision params | **0** (tower frozen) |
| `lora_B` nonzero gradient, backward 1 | **208 / 208** |
| `lora_A` nonzero gradient, backward 2 | **208 / 208** |
| median full step (seq 10,592) | 43.79 s → **241.9 tok/s** |
| peak GPU memory | 64.25 GiB |

`lora_A` reading 0/208 at backward 1 is correct, not a failure: `lora_B` initialises to zero, so
`lora_A` has no signal path until `lora_B` moves off it. Backward 2, after one optimiser step,
shows all 208 live.

`tools/assert_lora_gradients.py` was therefore **not** run as a standalone script. Instead the
same assertion is folded into the trainer's own step 0 (PR #35), which is strictly stronger: a
separate pre-flight leaves a gap between the run that passed and the run that matters, and a
silent gradient failure looks exactly like a normal loss curve.

---

## 2. Corpus

Extracted by `distill/extract_sft.py` at `origin/main` + PR #35, from the two 16-Sep rollout
runs. PR #30 (the fix for records pairing each decision with the board *after* the move) is
present — commit `0b1657f8c`, and verified by checksum on the box, not assumed.

> **The existing corpora on a424 were not reusable.** `/home/son/arc3-a424-measure/data/*.jsonl`
> were built 16-Sep 21:40. PR #30 merged 17-Sep 07:45. The fix commit predates the files but was
> on a branch, so whether those files carry it is unverifiable. They also carry no fence. Re-extracted.

Source artifacts were pulled from a108 **read-only** (rsync pull; a108's vLLM PID 765547 never
touched) and staged to a424. Tailscale ACL blocks a424→a108 directly, so they routed via the Mac.

### Test-set fence

The seven held-out games — `vc33, ar25, sb26, re86, su15, tr87, tu93` — are excluded by the new
`--exclude-games` flag, which drops at **game** granularity *before* the image renderer runs.
Filtering the output JSONL afterwards would have been too late: the excluded records' board PNGs
would already exist on disk.

The match is on the **bare game code**, not the full id. Artifacts name games `ar25-0c556536`; a
4-char fence list compared against full ids matches nothing and passes silently.

Measured by extracting twice, with and without `--exclude-games`:

| | unfenced | **fenced** | dropped by the fence |
|---|---|---|---|
| **training records** | 80 | **40** | **40 (50.0%)** |
| assistant (trainable) turns | 738 | 440 | **298 (40.4%)** |
| (game,pass) pairs contributing | 64 | 36 | 28 |
| games contributing | 18 | 12 | **6** |

**The fence costs half the corpus.** That is the number the brief asked for, and it is the single
most consequential fact for round 2: the held-out games are disproportionately ones the model
actually solves, so rejection sampling and the fence compete for the same records.

It also explains the "~600–800 trainable turns" expectation — that matches the **unfenced** 738
almost exactly. The estimate was made without the fence applied.

Separately, the extractor reports **35 (game,pass) pairs** refused by the fence —
`ar25:5, re86:5, sb26:5, su15:5, tr87:5, tu93:5, vc33:5`. That is the *void-check* number, not
the corpus-cost number: it counts every fenced game-pass including those rejection sampling
would have discarded anyway. **All seven codes appear in it**, which is the point — a zero for any
code would have meant a broken matcher rather than a clean corpus.

Verified directly against the run artifacts: of the seven fenced codes, **six** (`ar25, re86,
sb26, su15, tu93, vc33`) solve at least one level and would have contributed records.
**`tr87` solves nothing in either run**, so it contributes zero records fenced or not — its 5
refused game-passes are real fence activity but cost the corpus nothing.

**Independently verified**: `grep -c` over the final JSONL for each of the seven codes returns
**0** for all seven. That check shares no code with the filter that produced the file.

### Scale — substantially smaller than the brief expected

The brief anticipated ~600–800 trainable turns. Actual, after the fence and the sequence cap:

| | |
|---|---|
| records after fence | 40 (440 assistant turns), 12 games |
| dropped over the measured 43,687-token cap | **11** (see §3 — the cap was wrong twice before it was measured) |
| **records actually trained** | **29 / 247 turns / 228 images**, 9 games |
| total tokens trained (real multimodal) | **882,826** |
| token min / median / max, trained | 10,592 / 33,803 / 43,687 |
| games represented | cn04, ft09, ka59, lf52, lp85, ls20, r11l, s5i5, sp80 (+bp35/cd82/wa30 lost to the cap) |

Two reasons for the shortfall, both real rather than pipeline bugs: rejection sampling at level
granularity discards unsolved levels aggressively (125 game-runs → 80 records), and the fence
then removes exactly half of what survives, because the held-out games are disproportionately
ones the model actually solves.

Token counts are measured **through the real processor**, not a text tokenizer — one board PNG
per decision turn expands into a large vision-token block, and a text-only count undercounts by
enough to admit a record that then blows the memory ceiling.

---

## 3. The sequence ceiling — the brief's 49,152 is wrong

The brief stated "max safe seq len is 49,152". **It is not, for training.** The first round-1
attempt OOMed on the first micro-step at a 46,849-token record:

```
torch.OutOfMemoryError: Tried to allocate 1.52 GiB. 104.60 GiB allowed;
96.31 GiB allocated by PyTorch, 7.43 GiB reserved but unallocated.
```

This was already known and had simply not been carried into the brief.
`docs/2026-09-16-a424-lora-step-measurement.md` states it directly: *"46,849 tokens does not fit
with chunked CE + gradient checkpointing on a 121 GiB GB10"*, and brackets the ceiling **between
35,258 (peak 88.80 GiB, fits) and 46,849 (does not fit)**.

Precisely what each figure measured:

| figure | what it actually was |
|---|---|
| 65,536 | kernel-OOM-killed the box, 16-Sep. True, and the reason for the allocator cap. |
| 49,152 | **not a measurement.** No record of that length was ever run; it sits inside the already-published fails-band. |
| 46,849 | measured **does not fit**, twice — 16-Sep and again 17-Sep. |
| 35,258 | measured **fits**, peak 88.80 GiB. Largest length directly confirmed. |

Two mitigations, then the ceiling is measured rather than guessed a third time:

- `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`, set before torch initialises its
  allocator. 7.43 GiB of the 104.6 GiB cap was reserved-but-unallocated fragmentation.
- a **descending probe**: full fwd+bwd on the longest records, longest first, until one fits.
  First success ends the probe and sets the cap; every success records a peak-memory point.

`set_per_process_memory_fraction(0.86)` was left exactly as-is and deliberately not raised to buy
headroom — that cap is what turned a box-killing kernel OOM into a catchable
`torch.OutOfMemoryError`. Nothing else on the box died in either failure.

---

## 4. Training configuration

| | | |
|---|---|---|
| base | `Qwen3.8-27B-BF16` | **not** NVFP4 — it fake-quantises input activations under `no_grad`, severing gradient on 144 of 208 adapters |
| model class | `AutoModelForImageTextToText` | `AutoModelForCausalLM` silently drops the vision tower |
| LoRA | r=16, α=32, dropout 0.0 | 208 modules, 39,583,744 params — asserted at step 0, hard stop on mismatch |
| vision tower | frozen | this round adapts the reasoning policy, not perception |
| batch | bs=1, **grad_accum=4** | see below |
| lr / schedule | 1e-4, cosine, no warmup | LoRA starts as an identity map (`lora_B`=0), so there is no early instability to warm past, and at <10 steps a warmup would consume the run |
| loss | chunked CE, 2048-token chunks | required — naive CE OOMs at ~20K |
| gradient checkpointing | on | required — off OOMs at 10K |
| grad clip | 1.0 | |
| epochs | 1 | as briefed |

**grad_accum changed from the briefed 8 to 4.** At 29 records, accum=8 yields 4 optimiser steps —
too few for a cosine schedule to mean anything or for a loss curve to be readable. accum=4 gives
8. This is a deviation from the brief and is flagged as such. In hindsight it did not go far
enough: even 8 steps produced no trend (§5b).

**Micro-step 1 is pinned to the shortest record**, then the rest shuffled (seed 0). In the failed
attempt a long record OOMed inside the first backward, so the step-0 census never executed. The
pre-flight assertion must fire before the run's riskiest allocation.

**OOM handling:** a caught OOM skips the record *and discards the whole accumulation window*. A
backward that dies partway leaves some parameters holding gradients that are not a valid partial
sum; stepping on them would quietly train on garbage.

---

## 5. Attempt 2 — the memory floor was inconsistent with the allocator cap

Attempt 2 probed successfully and trained, then **aborted at optimiser step 3 of 8** — not on an
OOM, but on the trainer's own `MemAvailable` guard:

```
MemoryError: refusing micro-step 13: only 12.3 GiB MemAvailable (floor 16.0)
```

**The floor was unreachable by construction.** `set_per_process_memory_fraction(0.86)` caps torch
at 104.6 GiB of the box's 121.63 GiB. So `MemAvailable` can never exceed ~17 GiB while torch sits
near its cap, and ~13 GiB once the ~4 GiB of resident system processes are counted. A 16.0 GiB
floor cannot be satisfied for the longest records. It was never a safety boundary at this cap —
it was a latent abort waiting for a long record.

The log settles it: **micro-step 13 completed successfully at 12.3 GiB avail** (43,055 tokens,
loss 0.4866, 215.8 s). The box tolerated it fine; the guard refused the *next* one.

`MemAvailable` fell monotonically — 22.49 → 20.08 → 17.86 → 17.82 → 16.16 → 12.30 GiB — because
the shuffle happened to place the long records late, so allocator pressure ramped through the
run. Not a leak: the allocator legitimately holds up to its cap.

Three fixes, all in PR #35:

1. **Floor lowered to 8.0 GiB.** Defensible because the *cap*, not the floor, is what bounds this
   process — torch cannot allocate past 104.6 GiB, so this process cannot drive the box to kernel
   OOM. **This depends on the box staying quiet**: the 16.0 figure dates from the 16-Sep incident
   when a 56 GB download was in flight. Current bystanders are hermes-agent and two monitor
   scripts, ~100 MB combined. If something large is running, raise it back.
2. **The floor is now non-fatal.** `MemoryError` is caught in the same handler as
   `torch.OutOfMemoryError`: skip the record, discard the accumulation window, count it, carry
   on. A trip now costs one record instead of the whole run, which matters more than the value.
3. **`gc.collect()` + `empty_cache()` before every micro-step**, via a helper that deliberately
   does *not* touch gradients. (A `zero_grad` here would wipe the accumulation window and turn
   every grad_accum window into a single-record step — with a loss curve that still looked
   perfectly normal.) Plus **periodic step-tagged adapter saves**, because attempt 2 spent 29
   minutes of GPU on 3 real optimiser steps and died holding no model artifact at all.

### Measured throughput — the number that has been missing

From attempt 2's 13 completed micro-steps and 3 optimiser steps, before the abort:

| | |
|---|---|
| **measured throughput** | **198–205 tok/s** (204.6 → 200.0 → 198.3 across steps 1–3) |
| per-micro-step time | 44.8 s @ 10,592 tok … 215.8 s @ 43,055 tok; **median ~180 s** at these lengths |
| probe: 43,687 tokens | **fits**, peak **98.45 GiB**, 228.0 s → 191.6 tok/s |
| peak GPU memory, steps 1→3 | 88.50 → 90.88 → 94.53 GiB |
| measured cap | **43,687 tokens** (with `expandable_segments`) |
| corpus at that cap | 29 records / 882,826 tokens → **8 optimiser steps** at grad_accum=4 |
| projected 1-epoch wall clock | **~1.2 h** |

Throughput falls with sequence length (236 tok/s at 10.6K vs ~192 at 43K) — attention cost is
superlinear. All of it is **pessimistic**: `causal_conv1d` is not installed, so all 48
gated-delta layers run a reference PyTorch fallback on every forward.

> **The brief asked for a measured ETA after ~20 steps. At this corpus size 20 optimiser steps do
> not exist** — 29 records at grad_accum=4 is 8 steps total. The numbers above are that
> deliverable in the form the corpus permits.

Loss over the 3 completed steps: **0.5764 → 0.5866 → 0.5664**. Three points, one of them upward.
That is not a trend and is not presented as one.

Gradient census during the real run (not just the standalone probe):

| after | `lora_B` nonzero | `lora_A` nonzero |
|---|---|---|
| micro-step 1 (fresh adapter) | **208 / 208** | 0 / 208 — correct, `lora_B` is still zero |
| step 1 (pre-`opt.step`) | 208 / 208 | 0 / 208 — correct, same reason |
| **step 3** | **208 / 208** | **208 / 208** — the full adapter is training |

Micro-step 1 loss was **0.5440** against the standalone census's **0.544** on the same record —
identical, so the trainer reproduces the proven path exactly.

---

## 5b. Results — attempt 3 (completed)

**The round completed.** All 8 optimiser steps, all 29 records, **zero OOMs, zero guard trips,
zero skipped records**. Nothing else on either box was disturbed.

| | |
|---|---|
| optimiser steps | **8 / 8** |
| micro-steps (records) | **29 / 29** |
| wall clock | **4,319.4 s = 1.20 h** |
| **measured throughput** | **204.4 tok/s** |
| per-micro-step | median **165.3 s**, min 44.8 s (10,592 tok), max 219.7 s (43,687 tok) |
| tokens processed | 882,826 |
| trained content | 29 records / **247 assistant turns** / 228 images |
| peak GPU memory | 88.50 → **98.74 GiB** (cap 104.60) |
| records skipped by OOM / guard | **0** |
| final adapter | `/home/son/arc3-round1/ckpt/adapter` (171 MB) |
| intermediate adapters | `adapter-step2`, `-step4`, `-step6`, `-step8` |

The 1.20 h actual against the 1.01 h prior estimate — the prior used 241.9 tok/s measured at
10,592 tokens, and throughput falls with sequence length.

### Loss curve

Read `mean` — it is the per-record figure. `fixed` divides by the constant `grad_accum=4`, so
step 8's window of 1 (29 = 7×4 + 1) is under-weighted by 4×. **Step 8's 0.1508 is an artifact of
that divisor, not a sudden improvement.**

| step | window | loss (mean) | loss (fixed) | lr | peak GiB |
|---|---|---|---|---|---|
| 1 | 4 | 0.5764 | 0.5764 | 9.62e-05 | 88.50 |
| 2 | 4 | 0.5866 | 0.5866 | 8.54e-05 | 90.88 |
| 3 | 4 | 0.5661 | 0.5661 | 6.91e-05 | 94.53 |
| 4 | 4 | 0.6047 | 0.6047 | 5.00e-05 | 98.06 |
| 5 | 4 | 0.5211 | 0.5211 | 3.09e-05 | 98.06 |
| 6 | 4 | 0.5576 | 0.5576 | 1.46e-05 | 98.44 |
| 7 | 4 | 0.5422 | 0.5422 | 3.81e-06 | 98.44 |
| 8 | **1** | **0.6033** | *0.1508* | 0.00e+00 | 98.74 |

**There is no learning signal in this curve.** 0.5764 → 0.6033, oscillating between 0.521 and
0.605 with no trend. Eight steps over 29 records at lr 1e-4 is not enough to move a 27B model,
and each step's loss is dominated by which four records happened to land in its window — the
spread *within* a window (0.4866 to 0.6599 across individual records) is larger than any
step-to-step difference. **This round demonstrates that the pipeline works, not that the model
learned anything.**

### Gradient census — the thing that actually had to pass

| after | `lora_B` nonzero | `lora_A` nonzero |
|---|---|---|
| micro-step 1, fresh adapter (**the pre-flight**) | **208 / 208** | 0 / 208 — correct, `lora_B` is still zero |
| step 1 (pre-`opt.step`) | 208 / 208 | 0 / 208 — correct, same reason |
| steps 3, 5, 7 | **208 / 208** | **208 / 208** |

Micro-step 1 loss **0.5440** matched the standalone census's **0.544** on the same record, and
attempts 2 and 3 produced byte-identical step-1–3 losses. The path is deterministic.

### The saved adapter was inspected, not just written

Read back from `adapter_model.safetensors`:

| | |
|---|---|
| tensors | **416** (208 `lora_A` + 208 `lora_B`) |
| **nonzero** | **208 / 208 `lora_A`, 208 / 208 `lora_B`** |
| parameters | **39,583,744** — matches expectation exactly |
| config | r=16, α=32, all 7 target module types |

`lora_B` being nonzero on disk is the point: it initialises to zero, so a saved adapter with
`lora_B` still zero would be an identity map — a 171 MB file that changes nothing. It moved.

---

## 6. What was NOT verified

Stated explicitly because a wrong green light costs more than a red one.

1. **The adapter has not been evaluated.** No ARC-3 score, no held-out eval on the seven fenced
   games, no comparison against the base model. Whether this LoRA helps, does nothing, or hurts
   is **unknown** — and since the loss curve is flat, "does nothing" is the hypothesis to beat.
   A nonzero gradient is not evidence of capability gain.
2. **The adapter has not been loaded for inference.** Its *contents* were verified on disk (416
   tensors, all nonzero, correct shapes and config), but it was never loaded back into a model or
   into the serving stack. A clean round-trip is untested.
3. **PR #30's correctness was verified by presence, not behaviour.** The commit is in the tree and
   the source on the box matches the Mac's by checksum. The claim that observations now align with
   the pre-move board was not independently re-derived; `distill/verify_frames.py` was not run.
4. **Only 9 of the 25 games are represented**, several by a single record — `cn04:2, ft09:8,
   ka59:1, lf52:1, lp85:5, ls20:3, r11l:3, s5i5:4, sp80:2`. The corpus is far too small to
   generalise from, and per-game coverage is lopsided (ft09 alone is 28% of it).
5. **The 11 over-cap records are excluded, not represented** (40 extracted → 29 trained). They
   are the longest trajectories, so the training distribution is biased toward shorter games, and
   the longest reasoning chains — plausibly the most valuable ones — are exactly what is missing.
6. **`tools/assert_lora_gradients.py` was never executed against the 27B.** Its assertion is
   reimplemented inside the trainer and passes there; the script itself remains tested only
   against a tiny CPU model.
7. **No eval/validation split within the training corpus.** Loss is training loss only. There is
   no held-out loss, so overfitting cannot be observed from these numbers.
8. **Multi-epoch behaviour unknown.** One epoch only. Given the flat loss, more epochs (the box
   has the headroom — 1.2 h each) is the obvious next experiment, but it was not run.
9. **The learning rate was not tuned.** 1e-4 was taken from the brief and the earlier probes. No
   sweep was run, so a flat loss at 8 steps does not distinguish "lr too low" from "too few steps"
   from "corpus too small".
10. **`causal_conv1d` is not installed**, so all 48 gated-delta layers fall back to a reference
   PyTorch implementation on every forward. Every throughput number here is correspondingly
   pessimistic, by an unmeasured margin.

---

## 7. Reproduce

```bash
# on gx10-a424, with the GPU otherwise idle
cd /home/son/arc3-round1/src/ARC3-Inference
/home/son/arc3-train-venv/bin/python distill/extract_sft.py \
  --run-dir /home/son/arc3-round1/runs/20260915_230835_qwen38-27b-baseline-25g \
  --run-dir /home/son/arc3-round1/runs/20260916_102724_qwen38-27b-massdata-25g-4p \
  --out /home/son/arc3-round1/data/sft_fenced.jsonl \
  --granularity level --upscale 4 --style plain --inline-images \
  --exclude-games "vc33,ar25,sb26,re86,su15,tr87,tu93"

/home/son/arc3-train-venv/bin/python -u distill/train_lora.py \
  --corpus /home/son/arc3-round1/data/sft_fenced.jsonl \
  --out-dir /home/son/arc3-round1/ckpt \
  --epochs 1 --grad-accum 4 --lr 1e-4 --schedule cosine --census-every 2 --seed 0 --probe
```

**Never run this concurrently with another GPU job.** GB10 memory is unified; a second
allocation invokes the kernel OOM killer and takes bystander processes down with it. This
already destroyed a 56 GB download twice on 16-Sep.
