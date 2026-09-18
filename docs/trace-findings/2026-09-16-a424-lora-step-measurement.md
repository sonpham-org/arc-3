<!--
Author: Claude Opus 5 (Bubba subagent, arc3-a424-lora-step)
Date: 16-September-2026
PURPOSE: Measurement record for the ARC-3 LoRA training path on the DGX Spark gx10-a424
(NVIDIA GB10). Records the training stack, the LoRA target set and its verified trainable
parameter count, the gradient-flow blocker the prior bring-up hit, measured GPU step times and
peak memory on the REAL SFT corpus, whether chunked cross-entropy is necessary, and one-epoch
wall-clock extrapolations. Every number here is copied from output actually observed; anything
not observed is labelled unverified.
SRP/DRY check: Pass - the stack build is documented in 2026-09-16-a108-training-stack.md and the
corpus in 2026-09-16-arc3-sft-extraction.md; this file cites both and does not restate them.
-->

# a424 LoRA step measurement — Qwen3.8-27B on GB10

**Box:** `gx10-a424`, `ssh son@100.106.31.61` · aarch64 · NVIDIA GB10, sm_121 · 121 GiB unified
**Venv:** `/home/son/arc3-train-venv` · **Work dir:** `/home/son/arc3-a424-measure/`
**Status:** COMPLETE — 16-Sep-2026 ~23:10 UTC.

---

## Premise corrections against the brief

**1. Phase 1 was already done before this session started.** `/home/son/arc3-train-venv` existed
at 20:54 UTC with the exact a108 stack, and a prior session's `/home/son/arc3-train-a424/`
(`bringup.py`, `bringup.log`, `results.json`) had already completed Stages 1–2. No process was
running it (log last written 21:35 UTC, checked 21:38 — dead, not concurrent). Nothing of theirs
was edited; this session's work lives in a separate directory.

Verified stack, re-checked this session:

```
2.11.0+cu130 13.0 True
(12, 1) NVIDIA GB10
transformers 5.17.0 peft 0.21.0 trl 1.13.0 accel 1.15.0
```

`torch.cuda.is_available()` is **True**, capability `(12, 1)` = sm_121, device `NVIDIA GB10`.
`pillow 12.3.0` and `torchvision 0.26.0` were added this session for the multimodal path
(`--only-binary :all:` with the existing constraints file); torch re-printed afterwards as
`2.11.0+cu130`, unmoved.

**2. The BF16 download is not on the critical path, and the measurement did not wait for it.**
The brief sequenced Phase 2 after `Qwen/Qwen3.8-27B` finished downloading. That is unnecessary:
the already-local `unsloth/Qwen3.8-27B-NVFP4` checkpoint loaded with
`CompressedTensorsConfig(dequantize=True)` upcasts every LoRA target to a **plain BF16
`nn.Linear`** in memory — proven by the prior session's module probe and re-proven here. For a
step-time and peak-memory measurement the frozen base's quantisation error is irrelevant; the
tensors have identical shape and dtype. Measuring on NVFP4-dequantised saves ~2 h of idle time.
**Not cross-checked against the true BF16 checkpoint** unless it landed in time — see Limitations.

The download (PID 2077839) was left strictly alone throughout; it was only `du -sh`'d and its log
tailed. a108 was never contacted.

**3. `AutoModelForCausalLM` silently drops the vision tower.** The prior session loaded
`Qwen3_5ForCausalLM`, which reports `has vision tower: False` and 0 trainable vision params. That
satisfies "freeze the vision tower" only because the tower is absent — not the same claim, and a
text-only model cannot consume a corpus that is 355 inline PNGs. This session loads via
`AutoModelForImageTextToText`, so the tower is present and its frozen-ness is a real measurement.

**4. The chat template silently drops every chain of thought unless you remap the field.** The
extractor emits `reasoning` on assistant messages; `chat_template.jinja` reads
`message.reasoning_content` and renders `''` otherwise. Since 56 of 113 baseline assistant
messages have **no `content` at all** (reasoning + tool call only), a naive
`apply_chat_template` would render those turns as empty. The template also raises if
`tool_call.arguments` is a JSON string rather than a mapping. Both are handled in
`prep_probe.adapt()`; the fix is verified by the probe printing 6 `<think>` blocks for a
6-assistant-turn record and finding the reasoning text in the rendered output.

---

## Corpus token lengths — measured with real vision tokens

The extraction write-up's per-record totals used a **64 tokens/frame estimate**, flagged as such.
Run through the actual `Qwen3VLProcessor`, that estimate is **exactly right**: a 5-image record
expands to 320 image tokens, `320 / 5 = 64.0` per frame. Geometry confirms it — 256×256 frames at
`patch_size: 16` with `merge_size: 2` gives (256/16)²/4 = 64.

True lengths over all 41 records (text + real vision tokens), measured:

| | estimated (prior doc) | **measured (this session)** |
|---|---|---|
| min | 10,483 | **10,592** |
| p25 | 20,592 | **20,816** |
| median | 34,829 | **35,258** |
| p75 | 42,496 | **43,040** |
| p90 | 46,292 | **46,849** |
| max | 53,258 | **53,956** |
| total | 1,293,319 | **1,308,825** |
| over 65,536 | 0 / 41 | **0 / 41** |

The estimates were low by ~1%, entirely from chat-template scaffolding. **The conclusion holds:
zero records exceed a 64K budget**, and the largest is 53,956 tokens.

Corpus: 41 records / 381 assistant turns / 355 images, copied to
`/home/son/arc3-a424-measure/data/`.

---

## Model architecture

From `config.json`, confirmed at load:

```
architectures: ['Qwen3_5ForConditionalGeneration']   model_type: qwen3_5
text: 64 layers, full_attention_interval 4, hidden 5120, vocab 248,320
vision: depth 27, hidden 1152, patch 16, merge 2
```

So 16 of 64 layers are real attention (`self_attn.q/k/v/o_proj`) and 48 are gated-delta linear
attention (`linear_attn.in_proj_qkv / in_proj_z / out_proj`) — peft's default target set would
reach 16 of 64 layers and look healthy while missing three quarters of the model.

Measured LoRA counts, step times and memory follow.

---

## LoRA target set — verified against the multimodal model

Loaded via `AutoModelForImageTextToText` → `Qwen3_5ForConditionalGeneration`, 153.8 s.

```
top-level children: ['model', 'lm_head']
model.model children: ['visual', 'language_model']
vision tower present: True
vision blocks: 27 | vision params: 460,730,096
decoder layers: 64
total params: 28,294,494,304
param bytes by dtype (GiB): {'torch.bfloat16': 52.7, 'torch.float32': 0.0}
mem after load: cuda_alloc 52.70 GiB | cuda_peak 56.26 GiB | cuda_reserved 57.67 GiB
```

All seven target leaf names resolve to plain BF16 `nn.Linear` (non-BF16-Linear targets: `[]`), so
no on-disk BF16 round-trip is needed to attach LoRA.

```
LoRA-wrapped counts: {'out_proj': 48, 'in_proj_qkv': 48, 'in_proj_z': 48,
                      'q_proj': 16, 'k_proj': 16, 'v_proj': 16, 'o_proj': 16}
total wrapped modules: 208
trainable params: 39,583,744 || all params: 28,334,078,048 || trainable%: 0.1397
trainable params under visual: 0
vision/MTP leakage into LoRA targets: []
```

**`print_trainable_parameters()` reports exactly 39,583,744 — the ~39.6M estimate is matched to
the digit**, and it is unchanged from the text-only load even though the denominator grew by the
tower's 460.7M params. The vision tower is present and fully frozen (0 trainable vision
parameters), and no MTP or vision module leaked into the adapter set.

---

## Two blockers found, both fixed — and both produce the *same* error message

The prior bring-up died at `loss.backward()` with `RuntimeError: element 0 of tensors does not
require grad and does not have a grad_fn`. That message has **two independent causes here**, and
they masquerade as each other. This cost three runs to separate.

### Blocker 1 — `lm_head`'s forward is patched to run under `no_grad`

Bisecting the forward stack, arg by arg (all on a 256-token text batch):

| call | `requires_grad` | `grad_fn` |
|---|---|---|
| `Qwen3_5TextModel(input_ids, use_cache=False)` | True | `ToCopyBackward0` |
| `Qwen3_5TextModel(input_ids)` (cache default) | True | `ToCopyBackward0` |
| `Qwen3_5TextModel(inputs_embeds, use_cache=False)` | True | `ToCopyBackward0` |
| `Qwen3_5Model(input_ids, use_cache=False)` | True | `ToCopyBackward0` |
| `Qwen3_5Model(input_ids)` (cache default) | True | `ToCopyBackward0` |
| **`Qwen3_5ForConditionalGeneration(...).logits`** | **False** | **None** |
| `…` after `config.use_cache = False` | False | None |
| `PeftModel(...).logits` | False | None |

The graph survives the whole decoder and dies at the top. The only operation
`Qwen3_5ForConditionalGeneration.forward` performs between the two is
`logits = self.lm_head(hidden_states[...])`. Autopsy of that module:

```
type: Linear
module repr: Linear(in_features=5120, out_features=248320, bias=False)
weight: dtype torch.bfloat16 | shape (248320, 5120) | requires_grad False
        | is_inference False | is_leaf True | device cuda:0
forward hooks: []   forward pre-hooks: []
extra attrs: ['weight_scale', 'quantization_scheme', 'quantization_status']

hidden from mm(): requires_grad True  grad_fn ToCopyBackward0
  module_call                -> {'requires_grad': False, 'grad_fn': None}
  F.linear_on_weight         -> {'requires_grad': True,  'grad_fn': 'UnsafeViewBackward0'}
  F.linear_on_weight_clone   -> {'requires_grad': True,  'grad_fn': 'UnsafeViewBackward0'}
```

It reports as an ordinary `nn.Linear` with a real BF16 weight and **no hooks**, yet calling it
returns a detached tensor while `F.linear(x, lm_head.weight)` on *the same weight object*
returns a differentiable one. compressed-tensors has replaced the module's `forward` (the
leftover `quantization_scheme` / `quantization_status` attributes are the fingerprint), and the
replacement runs under `no_grad`.

**This is the trap the brief's "peft's default target_modules looks fine while losing" warning
is really about, one level up.** A checkpoint dequantised for fine-tuning presents plain BF16
`nn.Linear` targets — the prior session's module probe checked exactly that and passed — while
the output projection silently severs the graph. *The probe must cover `lm_head`, not just the
decoder projections.*

**Fix:** never call `lm_head(x)`; call `F.linear(x, lm_head.weight, lm_head.bias)`.

### Blocker 2 — a truncated smoke test has zero supervised tokens

With blocker 1 fixed, a 512-token slice of a real record still failed with the identical message.
Cause: the first ~1–2K tokens of every record are the system prompt and first user turn, so a
short prefix contains **no assistant span at all**. Label masking then leaves nothing supervised,
the chunked-CE accumulator returns its `zeros()` initial value, and `backward()` reports
"element 0 … does not require grad" — a *harness* bug wearing the costume of a model bug.

**Fix:** never truncate a record for a smoke test; assert `supervised_tokens > 0` and
`loss.requires_grad` before `backward()`. Both assertions are now in the script.

### Unified memory makes a CUDA over-allocation unsurvivable

Worth recording separately. GB10 memory is unified, so an over-allocation is **not** a catchable
`torch.OutOfMemoryError` — the kernel OOM killer fires against the whole box. One run at
22:25 UTC took the machine off the network and killed unrelated user processes:

```
Out of memory: Killed process 2096424 (python3)
Out of memory: Killed process 2519 (pipewire-pulse)
Out of memory: Killed process 2591 (xdg-document-po)
NVRM: Check failed: Out of memory [NV_ERR_NO_MEMORY] ... _memdescAllocInternal
```

The job was killed as soon as the box came back and the BF16 download was confirmed alive. The
final script caps the allocator at 0.86 of device total and refuses to begin any step with less
than 16 GiB `MemAvailable`. **Any future training job on this box needs that guard.**

---

## THE BLOCKER — gradient reaches only the output projections

This is the finding that matters most, and it outranks every timing number below.

Measured on a real record windowed to its first assistant span (301 supervised tokens, loss
0.8251), backward run from a freshly-zeroed state. **Identical, to the digit, with gradient
checkpointing off and on — so it is not a checkpointing artifact.**

`lora_B` gradients by module type (`n` = modules, `none` = `p.grad is None`):

| module | layers | `n` | grad is None | **nonzero grad** | Σ&#124;grad&#124; |
|---|---|---|---|---|---|
| `linear_attn.out_proj` | 48 | 48 | 0 | **48** | 69.856 |
| `self_attn.o_proj` | 16 | 16 | 0 | **16** | 39.150 |
| `linear_attn.in_proj_qkv` | 48 | 48 | 0 | **0** | 0.0 |
| `linear_attn.in_proj_z` | 48 | 48 | 0 | **0** | 0.0 |
| `self_attn.q_proj` | 16 | 16 | 0 | **0** | 0.0 |
| `self_attn.k_proj` | 16 | 16 | **16** | **0** | 0.0 |
| `self_attn.v_proj` | 16 | 16 | **16** | **0** | 0.0 |

**64 of 208 adapters receive a gradient. The other 144 receive zero or nothing at all.**

Bucket names were verified rather than assumed — the seven buckets sum to exactly 208 and each
holds real parameter names (e.g. `…language_model.layers.3.self_attn.k_proj.lora_B.default.weight`),
so this is not a bucketing error in the accounting.

**The one benign explanation, checked and excluded.** Every `lora_A` gradient is zero in this
table, including for `out_proj` and `o_proj` whose `lora_B` gradients are large. That is expected
and correct: peft zero-initialises `lora_B`, and `dL/dA = Bᵀ · dL/dy · xᵀ`, which is identically
zero while `B = 0`. On the first backward from initialisation *all* `lora_A` gradients must be
zero. So the `lora_A` column says nothing, and the `lora_B` column is the real signal.

**What the pattern means.** `o_proj` and `out_proj` are the only targeted modules that sit on the
residual path *outside* the attention / gated-delta core. Gradient reaching every one of them
while reaching none of the q/k/v or `in_proj_*` modules is the signature of **the attention and
linear-attention cores being a gradient dead-end**: `dL/d(hidden)` flows down the residual stream
through all 64 layers and into each output projection, but does not propagate back through the
attention operators to their input projections. The two distinct signatures inside one attention
module — `q_proj` gets an allocated all-zero gradient while `k_proj`/`v_proj` get no gradient
object at all — are consistent with a custom kernel whose backward is absent or returns zeros.

**Consequence for a real training round.** `lora_B` for the 144 input-projection adapters has
gradient exactly zero, so it stays at its zero initialisation forever; and because `dL/dA ∝ B`,
their `lora_A` can never start moving either. Those adapters are **permanently inert** — not
slow-learning, mathematically frozen. A run would proceed, show a falling loss from the 64 output
projections, and quietly train a fraction of the intended adapter. This is the same class of
failure the brief warns about for peft's default `target_modules`, but it is not fixed by
choosing better targets: the targets are correct (208 modules, 39,583,744 params, verified) and
the gradient does not arrive.

And the 64 adapters that *do* train are precisely the ones on the residual path, which means even
the working half cannot learn attention behaviour — it can only rescale each layer's output. So
the damage is not merely "144 inert"; the surviving 64 are not doing the thing LoRA-on-attention
exists to do.

**Not root-caused.** I did not isolate which kernel is responsible or whether a different
attention implementation (`attn_implementation="eager"`), a newer `fla`, or installing
`causal_conv1d` restores it. Measured on the NVFP4-dequantised checkpoint; **unverified against
the true BF16 checkpoint**, though the mechanism should not depend on the weights. *This must be
settled before any training round is worth starting.*

---

## Measured steps

Configuration for every row: **batch size 1, gradient accumulation 1** (one record = one
optimizer step), chunked cross-entropy at 2,048-token chunks with `torch.utils.checkpoint`
(`use_reentrant=False`), model-level gradient checkpointing on, AdamW lr 1e-4 over the 39,583,744
LoRA params. Real corpus records — real text, real inline PNGs, real vision tokens. Three timed
repetitions each; `median` reported.

| record | seq len | images | supervised tokens | times (s) | **median s** | **tokens/s** | **peak GPU mem** |
|---|---|---|---|---|---|---|---|
| `lp85-305b61c3/p0/L1` | 10,592 | 1 | 4,233 | 58.62 / 58.27 / 58.31 | **58.31** | **181.6** | **65.82 GiB** |
| `vc33-5430563c/p0/L2` | 20,816 | 5 | 12,538 | 132.52 / 119.59 / 118.66 | **119.59** | **174.1** | **74.20 GiB** |
| `sp80-589a99af/p0/L1` | 35,258 | 10 | 21,165 | 243.33 / 326.70 / 325.28 | **325.28** | **108.4** | **88.80 GiB** |
| `cd82-fb555c5d/p1/L1` | 46,849 | — | — | — | **OOM** | — | 97.22 GiB at failure |

Losses were 0.5418 / 0.6245 / 0.6516 — plausible for a model scored against its own generations,
but **no learning is claimed**; three steps on one record is a measurement, not a curve.

Caveat on the 35,258 row: the spread (243 s then 326 s twice) is wide. The box was down to
16.18 GiB available at that point, so the later repetitions were under memory pressure. The
median is reported; the best time was 243.33 s (145.0 tokens/s).

**Every number above was measured without the optimized `causal_conv1d` kernel.** transformers
logs `causal_conv1d_fn is falling back to its reference PyTorch implementation … much slower` on
every forward, and **48 of the 64 layers are gated-delta layers that depend on it**. These
throughputs are a floor for this box, not its capability. `fla` *is* installed
(`{'fla': True, 'causal_conv1d': False}`); installing `causal_conv1d` is the single most obvious
speed lever and was not attempted here.

### Does a ~53K-token record fit? **No.**

The ladder stopped at the first non-fit. The 46,849-token record raised a real, catchable
`torch.OutOfMemoryError`:

```
CUDA out of memory. Tried to allocate 1.07 GiB. GPU 0 has a total capacity of 121.63 GiB
of which 1.14 GiB is free. Including non-PyTorch memory, this process has 103.89 GiB in use.
104.60 GiB [allocator limit]
```

Honest reading: 104.60 GiB is **my** allocator cap (0.86 × 121.63). But physical free memory was
1.14 GiB and system `MemAvailable` was 7.91 GiB at that moment, so lifting the cap would not have
produced a comfortable fit — it would have handed the box to the kernel OOM killer, exactly as
happened earlier. **46,849 tokens does not fit with chunked CE + gradient checkpointing on a
121 GiB GB10.** The 53,956-token maximum record was therefore never attempted, and is reported as
**does not fit, by inference from the 46,849 failure** — not as a direct measurement.

Peak memory trend, measured: 65.82 → 74.20 → 88.80 GiB at 10,592 → 20,816 → 35,258 tokens, i.e.
**~0.82–1.01 GiB per 1,000 tokens** above a 52.7 GiB resident base. Extrapolating that slope
(*extrapolation, not measurement*) puts 53,956 tokens near **107 GiB**, above the cap and within
~15 GiB of the physical ceiling.

**This refutes the brief's projection.** The brief carried a prior estimate that with
fused/chunked CE "~64K was projected to fit at ~101G". Measured: chunked CE was used throughout
and the ceiling is between 35,258 and 46,849 tokens, not 64K. The prior estimate accounted for
the logits but not for the activation memory of 64 layers at long sequence.

### Was chunked CE necessary? **Yes — measured, not assumed.**

Naive full-sequence cross-entropy over the 248,320-wide vocabulary, same records, same everything
else:

| seq len | naive CE | step s | peak mem | vs chunked |
|---|---|---|---|---|
| 10,592 | **fits** | 60.95 | **89.41 GiB** | chunked: 58.31 s, 65.82 GiB → **23.6 GiB saved, and slightly faster** |
| 20,816 | **OOM** — tried to allocate 19.26 GiB | — | 95.54 GiB at failure | chunked: 119.59 s, 74.20 GiB |

So naive CE stops fitting **between 10,592 and 20,816 tokens**. The brief's claim was "between
16K and 20K"; this brackets it but does not pin it — I measured two points, not a threshold, and
the true cutoff is anywhere in that wider range. Chunked CE is **comparable in speed** — 60.95 s (single
run, naive) against 58.31 s (median of 3, chunked), well inside the spread seen elsewhere in this
table — and buys 23.6 GiB. The memory result carries the conclusion on its own: use chunked CE
unconditionally.

### Was gradient checkpointing necessary? **Yes.**

Same shortest record (10,592 tokens), chunked CE, checkpointing **disabled**:

```
OutOfMemoryError: Tried to allocate 704.00 MiB. 1.52 GiB free, 104.38 GiB in use.
peak 99.43 GiB, sys_avail 6.97 GiB
```

The corpus's *smallest* record does not fit without gradient checkpointing. **Both levers are
required, and both together still cap the usable sequence length below the corpus maximum.**

---

## Wall-clock extrapolations

**These are arithmetic from the measured step times above, not measurements.** Corpus totals:
41 records, 381 assistant turns, 1,308,825 tokens → 3,435 tokens per assistant turn.

Measured per-token cost is not linear: 5.505 ms/token at 10,592, 5.745 ms/token at 20,816,
9.226 ms/token at 35,258 — it degrades sharply past ~21K, from attention quadratic in the 16
full-attention layers plus memory pressure. Both ends are given rather than one blended figure.

| | at 5.5–5.7 ms/token (short-record regime) | at 9.2 ms/token (35K regime) |
|---|---|---|
| **one epoch, current 381-turn corpus** (1,308,825 tok) | **≈ 2.0–2.1 h** | **≈ 3.4 h** |
| **one epoch, 2,000-turn corpus** (≈ 6,870,000 tok) | **≈ 10.5–11.0 h** | **≈ 17.6 h** |

The 2,000-turn row assumes the same 3,435 tokens/turn density holds at scale.

Both rows are **optimistic in one direction and unachievable as stated in another**:

- Optimistic: they assume no `causal_conv1d` speedup. Installing it should move these materially.
- Unachievable as stated: **5 of the 41 records (245,189 tokens, 19% of the corpus) are at or
  above the 46,849-token OOM point and cannot be trained at all** in this configuration. A real
  epoch today covers 36 records / 1,063,636 tokens, or needs the long records split by level or
  turn first. 21 of 41 records are at or above 35,258 tokens, where the rate has already degraded
  to 9.2 ms/token — so the pessimistic column is the more honest planning number.

---

## Blockers that would stop a real training round

1. **144 of 208 LoRA adapters get no gradient** (§ THE BLOCKER). Permanently inert, silent, and
   not fixed by re-choosing targets. Root cause not established. **Settle this first.**
2. **19% of the corpus (5 records) cannot be trained** — they exceed the measured memory ceiling
   between 35,258 and 46,849 tokens. Needs record splitting, sequence parallelism, or offload.
3. **No OOM headroom, and OOM here is fatal to the box.** Unified memory means over-allocation
   invokes the kernel OOM killer, which already took a424 off the network once tonight and killed
   unrelated user processes. Any training job needs the allocator cap and `MemAvailable` floor
   used here.
4. **`causal_conv1d` is not installed**, so 48 of 64 layers run a reference implementation that
   transformers itself calls "much slower". Fixable, and the cheapest available speedup.
5. **Corpus size, unchanged from the extraction write-up.** 381 turns against a 2–5K target. Not a
   trainer problem, restated here only because the trainer is no longer the excuse.

## Limitations — what was NOT verified

- **Not cross-checked against the true BF16 checkpoint.** All measurements are on
  `unsloth/Qwen3.8-27B-NVFP4` dequantised to BF16 in memory. The BF16 download was still in
  flight (34 GiB of 55.6 GiB) when this was written. Shapes and dtypes are identical, so step time
  and memory should carry over; the gradient blocker *should* be checkpoint-independent but that
  is reasoning, not measurement.
- **53,956 tokens never attempted.** Reported as not fitting by inference from the 46,849 OOM.
- **Naive-CE cutoff not pinned**, only bracketed between 10,592 and 20,816.
- **No learning demonstrated, and none claimed.** Three timed steps per record.
- **No multi-record batching or gradient accumulation was measured** — every number is bs=1,
  accum=1.
- The 35,258-token timing has wide spread under memory pressure; treat it as indicative.

## Artifacts and hygiene

On a424, all under `/home/son/arc3-a424-measure/`: `prep_probe.py` (corpus→processor adapter and
token census), `gradhunt.py` / `measure2.py` (the bisect that found the `lm_head` cause),
`measure4.py` (final measurement), `gradtest.py` (gradient attribution), with `.log` and
`results*.json` / `gradtest.json` beside each.

- **No job was left running.** Verified after the last run: no process of mine alive, GPU 0%,
  3 GiB of 121 GiB used.
- **The BF16 download was never touched** — only `du -sh` and log tails. Note for the record: the
  original PID 2077839 was **replaced at 21:46 UTC by another party** with a new download process
  (PID 2086419, `max_workers=16`, its own venv). That was not me. It is alive and at 34 GiB.
- **a108 was never contacted at all** — not even a read.
- **Another session resumed work on a424 at ~23:15 UTC**, after mine had finished: PID
  2111866 running the prior session's `/home/son/arc3-train-a424/bringup.py`, holding
  59.5 GiB of GPU at 96% utilisation. Not my process, not touched. Anyone reading a busy GPU
  on a424 after that timestamp should not attribute it to this work. Worth flagging to
  whoever owns it: `bringup.py` calls `lm_head(...)` directly, so unless it has been edited
  it will hit Blocker 1 and die at `loss.backward()` exactly as before.
- The prior session's `/home/son/arc3-train-a424/` was left untouched; all work here is in a
  separate directory.
- **PR opened and left open: sonpham-org/arc-3 #31**, branch
  `fix/sft-chat-template-reasoning-field` off `origin/main` — the `reasoning` →
  `reasoning_content` adapter (`ARC3-Inference/distill/chat_adapter.py`) plus a CHANGELOG
  entry. That one function is not harness code: without it *any* consumer calling
  `apply_chat_template` on this corpus silently drops every chain of thought and renders 56
  of 113 baseline assistant turns empty, so it belongs next to `extract_sft.py` rather than
  only in this document. The repo has no CI, so there is nothing to report there.
- The measurement scripts themselves were deliberately **not** submitted — they are
  box-specific harnesses, not library code. The local checkout was returned to the branch it
  was on (`feat/sft-extraction-pipeline`) with its working tree unchanged.
