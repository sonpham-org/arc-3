<!--
Author: Claude Opus 5 (Bubba subagent, arc3-lora-bf16-first-step)
Date: 17-September-2026
PURPOSE: Record the first real LoRA forward+backward training step for ARC-3 against the TRUE
BF16 Qwen3.8-27B checkpoint on gx10-a424 (NVIDIA GB10), and the verdict on the LoRA gradient
blocker from 2026-09-16-a424-lora-step-measurement.md / 2026-09-17-lora-gradient-rootcause.md.
Result: 208/208 lora_B adapters receive a nonzero gradient. The blocker is gone. Carries the
measured step time, peak memory, loss trajectory over four steps, and an explicit list of what
was NOT verified.
SRP/DRY check: Pass - the blocker is documented in 2026-09-16-a424-lora-step-measurement.md and
root-caused in 2026-09-17-lora-gradient-rootcause.md; both are cited, not restated. The corpus
adapter and the memory guards are reused from the earlier harness rather than rewritten. This
file adds only the BF16 run and its result.
-->

# a424 BF16 LoRA first step — the gradient blocker is gone

**Date:** 17-Sep-2026, 11:46–12:20 UTC (07:46–08:20 ET) · **Box:** `gx10-a424` (`ssh son@100.106.31.61`)
**GPU:** NVIDIA GB10, capability (12,1) = sm_121, 121.6 GiB unified · **Venv:** `/home/son/arc3-train-venv`
(torch 2.11.0+cu130 / transformers 5.17.0 / peft 0.21.0)
**Work dir (created by this run, nothing else in `/home/son` touched):** `/home/son/arc3-lora-bf16-step/`

---

## Headline

**208 of 208 LoRA adapters received a nonzero `lora_B` gradient on the first backward.** The
144 permanently-inert adapters reported in `2026-09-16-a424-lora-step-measurement.md` are all
alive on the BF16 checkpoint. The fix predicted in `2026-09-17-lora-gradient-rootcause.md` —
"train on the true BF16 pull, it carries no `quantization_config` so no forward is patched and no
activation is detached" — is confirmed by execution, not by reasoning.

Exactly **one variable** was changed against the prior measurement (`measure4.py`): the
checkpoint. Same `AutoModelForImageTextToText`, same `device_map="cuda:0"`, same 7-name LoRA
target list, same record, same chunked cross-entropy at 2,048, same gradient checkpointing, same
allocator cap and `MemAvailable` floor. That is what makes the 208/208 attributable.

---

## Gradient census

Real ARC-3 SFT record `20260915_230835_qwen38-27b-baseline-25g/lp85-305b61c3/p0/L1`, **full
record, not sliced** — 10,592 tokens, 1 real inline PNG, 4,233 supervised tokens. bs=1,
grad_accum=1. Grads cleared to `None` before each backward.

### Backward 1 — fresh adapter (`lora_B` is the signal)

| module | n | grad is None | **nonzero grad** | Σ&#124;grad&#124; | prior NVFP4 result |
|---|---|---|---|---|---|
| `linear_attn.in_proj_qkv` | 48 | 0 | **48** | 277.503 | 0 nonzero |
| `linear_attn.in_proj_z` | 48 | 0 | **48** | 148.676 | 0 nonzero |
| `linear_attn.out_proj` | 48 | 0 | **48** | 148.303 | 48 nonzero |
| `self_attn.q_proj` | 16 | 0 | **16** | 151.711 | 0 nonzero |
| `self_attn.k_proj` | 16 | 0 | **16** | 26.794 | 0, grad was `None` |
| `self_attn.v_proj` | 16 | 0 | **16** | 67.755 | 0, grad was `None` |
| `self_attn.o_proj` | 16 | 0 | **16** | 61.405 | 16 nonzero |
| **total** | **208** | **0** | **208** | | **64 / 208** |

`lora_A` was **0/208 nonzero** here, and that is the correct and expected result, not a partial
failure: peft zero-initialises `lora_B`, and `dL/dA ∝ B`, so every `lora_A` gradient is
identically zero on the first backward from initialisation. The `lora_A` column proves nothing on
its own — which is why backward 2 exists.

Loss **0.5440**. The prior NVFP4-dequantised run on the same record reported 0.5418; 0.4% apart,
as expected from quantisation error on a frozen base.

### Backward 2 — after one AdamW step, with `B` off zero

`opt.step()` moved `lora_B` off zero in every bucket (Σ|w| after the step: `in_proj_qkv` 782.4,
`in_proj_z` 469.3, `out_proj` 392.4, `q_proj` 313.6, `o_proj` 130.9, `k_proj` 26.2, `v_proj` 26.2).
A second backward on the same batch then gives:

- **`lora_B`: 208/208 nonzero** (Σ|g| 13.7 – 146.0 by bucket)
- **`lora_A`: 208/208 nonzero** (Σ|g| `k_proj` 0.644 … `in_proj_qkv` 6.826)

This is the check that upgrades "gradient arrives" to "the adapter can actually move." Both
factors of every adapter now have gradient. Nothing is mathematically frozen.

### Sanity checks that had to pass before the census was trusted

- `config.json` has **no `quantization_config`** (asserted at load).
- For one leaf of each of the 7 target types **plus `lm_head`**: `"forward" not in vars(mod)`
  (compressed-tensors patches via an *instance* attribute, so this is the crisp test) and
  `quantization_scheme is None`, and no `weight_scale` attribute. All eight clean.
- **`lm_head(x)` is differentiable again** — `requires_grad True` from the module call, where the
  NVFP4 checkpoint returned a detached tensor. Blocker 1 from the prior measurement is gone at
  source. (`F.linear` on the weight is still what the chunked-CE path uses, because chunked CE
  needs the weight anyway.)
- The 7 `lora_B` buckets sum to exactly 208, with a real parameter name printed per bucket, all
  under `language_model` — so the count is not a bucketing artifact. 0 trainable vision params.
- `print_trainable_parameters()`: **39,583,744 trainable / 27,396,312,304 total (0.1445%)** —
  trainable matches the prior run to the digit. The denominator is smaller than the NVFP4 run's
  28,294,494,304 because that checkpoint carried quantisation scale tensors as parameters.

---

## Measured step cost

Timed full steps (forward + chunked CE + backward + AdamW), bs=1, grad_accum=1, gradient
checkpointing on, CE chunk 2,048:

| | value |
|---|---|
| model load (cold page cache, 18 shards) | **365.7 s** |
| resident after base load | 50.96 GiB alloc / 51.01 GiB reserved |
| resident after LoRA wrap | 51.11 GiB alloc |
| fwd+bwd only (backward 1 / 2) | 45.63 s / 43.58 s |
| **full step, 3 reps** | 44.09 / 43.72 / **43.79 s median** |
| **throughput** | **241.9 tokens/s** (10,592 tok / 43.79 s) |
| **peak GPU memory** | **64.25 GiB** (torch `max_memory_allocated`), 69.32 GiB reserved |
| system `MemAvailable` at the floor of the run | **45.05 GiB** |

**Losses fell monotonically across the four backwards on the same batch: 0.5440 → 0.5328 →
0.5109 → 0.4855.** That is four steps on one record — it is evidence the optimiser is connected,
**not** a learning curve, and no learning is claimed.

The prior NVFP4-dequantised run on the same record reported 58.31 s median / 181.6 tok/s /
65.82 GiB peak, against 43.79 s / 241.9 tok/s / 64.25 GiB here. The memory figures are directly
comparable. **The speed difference is not attributable to the checkpoint alone** and no cause is
claimed for it: that run shared a424 with a concurrent 34 GiB download and another session's job
and its own write-up flags memory pressure distorting its timings, whereas this run had the box to
itself at 117 GiB `MemAvailable`.

`causal_conv1d` is still not installed (transformers logs the reference-implementation fallback on
every forward, and 48 of 64 layers are gated-delta layers). These numbers are a floor for this box.

**`fla`'s Triton `chunk_gated_delta_rule` is now cleared as a suspect.** Its fallback warning does
*not* appear in the log — only `causal_conv1d_fn`'s does — so fla's kernel bound and ran on
sm_121, and `in_proj_qkv` / `in_proj_z` got full gradient through it. Item 3 on the root-cause
doc's "not verified" list is closed. The contingency branch in the script (unbind fla to
`__wrapped__` and re-run) was therefore never entered.

---

## Is a full training run feasible on this box?

At the configuration measured — **bs=1, grad_accum=1, seq 10,592, chunked CE, gradient
checkpointing** — yes, with ~45 GiB of system `MemAvailable` headroom and a 64.25 GiB peak against
a 104.6 GiB allocator cap. Nothing about the run was close to the edge.

That headroom does **not** extend to the whole corpus, and this run did not re-test the ceiling.
The prior measurement found, on this same box and configuration, that a 46,849-token record OOMs
and 21 of 41 records sit at or above 35,258 tokens where throughput had already degraded. BF16's
~1.6 GiB saving at 10.6K tokens does not plausibly close a gap that large. **5 of 41 records (19%
of the corpus) should still be assumed untrainable without splitting**, and the long-record
ceiling is unmeasured on BF16. Deliberately not tested: an over-allocation on GB10's unified
memory invokes the kernel OOM killer rather than raising, and it took a424 off the network once
on 16-Sep. A length ladder on BF16 is the right next measurement, run the same guarded way.

Headroom read from `max_memory_allocated()` is optimistic on unified memory — the 16-Sep OOM
showed 103.89 GiB process-resident against much lower allocator numbers. The `MemAvailable`
column above is the number to plan against.

---

## Exact commands

```bash
# 1. pre-flight, CPU only: does the BF16 checkpoint's own chat template + tokenizer render this
#    corpus identically to the unsloth NVFP4 snapshot the prior measurement used?
ssh son@100.106.31.61
mkdir -p ~/arc3-lora-bf16-step
cp ~/arc3-a424-measure/prep_probe.py ~/arc3-lora-bf16-step/prep_probe_src.py   # copy, original untouched
cd ~/arc3-lora-bf16-step
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES="" OMP_NUM_THREADS=4 nice -n 19 \
  /home/son/arc3-train-venv/bin/python prep_bf16.py

# 2. the step itself, detached (load alone is ~6 min; a foreground kill mid-load strands 51 GiB)
cd ~/arc3-lora-bf16-step && PYTHONDONTWRITEBYTECODE=1 \
  nohup /home/son/arc3-train-venv/bin/python -u step_bf16.py > step_bf16.log 2>&1 &
```

### Why the pre-flight was necessary

The BF16 checkpoint ships a **different** `chat_template.jinja`, `tokenizer_config.json` and
`tokenizer.json` from the unsloth NVFP4 snapshot (`diff` confirms all three). Unsloth's template
merges multiple system messages and drops a `raise_exception('No user query found in messages.')`
on the `multi_step_tool` path that this corpus's tool calls could have tripped. Measured rather
than assumed:

- Both tokenizers: `Qwen2Tokenizer`, 248,077 tokens, identical ids on a probe string.
- **41/41 records render byte-identical** under the two templates, and **0 raise**.
- Re-measured token lengths: min **10,592**, median **35,258**, max **53,956**, total
  **1,308,825** — identical to the prior measurement's numbers. So `corpus_lengths.json`, the
  "shortest record" pick, and every prior length conclusion carry over unchanged.

Shard integrity before loading: 18/18 shards present, `ls -l` sum 55,563,006,776 B against the
index's `total_size` 55,562,855,904 B (the 150,872 B excess is the safetensors headers), 1,199
tensors in the weight map, no missing file. The `du -sh` figure of 66 G is not the model: 15 G of it is a
`.cache/` subdirectory of download blobs (measured), which `from_pretrained` does not read.

---

## What was NOT verified

1. **Any sequence length other than 10,592 tokens, on BF16.** No length ladder was run. The
   corpus ceiling (between 35,258 and 46,849 tokens on NVFP4) is carried over from the prior
   measurement by inference, not re-measured. Deliberate — an OOM here takes the box down.
2. **Multi-record batching or gradient accumulation.** Every number is bs=1, accum=1.
3. **Any actual learning.** Four backwards on one record with a falling loss. That is an
   optimiser-connectivity check. No held-out evaluation, no second record, no epoch.
4. **Gradient checkpointing off, or `attn_implementation` variants.** Only the one configuration
   was run, on purpose — one variable changed.
5. **The vision tower's own gradient flow.** One real PNG passed through it and it is confirmed
   frozen (0 trainable vision params), but no gradient was expected or checked inside the tower.
6. **Numerical agreement with the NVFP4 base beyond the loss.** 0.5440 vs 0.5418 on the same
   record is a one-point comparison.
7. **`causal_conv1d` installed.** Still absent; the speed ceiling of this box is unmeasured.
8. **The `None`-versus-zero split on `k_proj`/`v_proj`** seen on NVFP4 (open question 5 in the
   root-cause doc). It cannot recur here — nothing is `None` — so the question is now moot for
   the BF16 path and remains unanswered for NVFP4.
9. **The alternative NVFP4 fix** (`m.quantization_enabled = False`) proposed in the root-cause
   doc. Not executed; the BF16 route made it unnecessary.

---

## Hygiene

- a424's GPU was re-verified free (zero compute processes) immediately before the launch.
- **a108 was never contacted.** No process belonging to anyone else was killed or signalled.
- Nothing outside `/home/son/arc3-lora-bf16-step/` was written. `prep_probe.py` was **copied**
  out of `~/arc3-a424-measure/`, not imported in place, and `PYTHONDONTWRITEBYTECODE=1` was set
  so no `.pyc` landed in the other run's directory.
- **No job left running.** Verified after completion: no process alive, GPU compute-apps list
  empty, box back to 117 GiB `MemAvailable`.

## Artifacts

On a424, `/home/son/arc3-lora-bf16-step/`: `step_bf16.py`, `step_bf16.log`, `step_bf16.json`,
`prep_bf16.py`, `prep_bf16.json`, `prep_probe_src.py`.
Mirrored on the Mac Mini at `~/bubba-workspace/arc3-run/lora-bf16-step/` (log with the weight-loading
progress bar stripped).
