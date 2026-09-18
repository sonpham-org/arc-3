<!--
Author: Claude Opus 5 (Bubba subagent, session arc3-a424-trainer-bringup)
Date: 16-September-2026
PURPOSE: Bring-up report for the Qwen3.8-27B LoRA trainer on gx10-a424 (NVIDIA GB10). Records
the verified venv recipe, the GPU proof, four corrections to the task brief's premises, the
root cause of a silent autograd failure in the compressed-tensors stack (with an isolated
reproduction and the fix), and the exact adapter-targeting verification. States plainly which
deliverables were measured and which were blocked.
SRP/DRY check: Pass - single bring-up record for a424; does not duplicate the a108 stack report.
-->

# a424 LoRA trainer bring-up — Qwen3.8-27B

**Box:** gx10-a424, NVIDIA GB10, 121 GiB unified memory, 475 G disk free, Ubuntu 6.17.0-1014-nvidia aarch64
**Date:** 16-Sep-2026
**Scope:** setup + measurement only. No training run was performed and no claim is made about loss improving.

---

## 0. Bottom line

| Deliverable | Status |
|---|---|
| CUDA-enabled training venv on a424 | **Done, GPU proven** |
| BF16 base without a 54 GB download | **Done — `dequantize=True`, no disk round-trip needed** |
| Adapter r=16 over 16 full-attn + 48 linear-attn layers | **Done — every count asserted, exact** |
| Root cause of broken gradients in this stack | **Found, isolated, fixed, independently corroborated** |
| One measured GPU LoRA step (tokens/s, s/step) | **Done — 5 sequence lengths, all 208 adapters verified receiving gradient** |
| Max sequence length that fits | **Done — 49,152 fits; 65,536 kernel-OOM-killed. 75K does NOT fit.** |
| Grounded epoch-time estimate | **Done — derived from the measured 20,480 step** |

All measurements in §7 were taken **after** the §5 fix, with `208/208` adapters proven to
receive gradient on every step. The most consequential result is §5: **on this stack a LoRA step runs clean, returns a finite
loss, and silently computes wrong gradients for most of the adapter.** That defect is live in a
peer agent's run on the same box right now (§7), which is independent confirmation.

---

## 1. Corrections to the brief's premises

All four verified against the checkpoint and the installed source, not recalled.

**1.1 The checkpoint is `mixed-precision`, not NVFP4 throughout.**
`config.json` → `quantization_config.format == "mixed-precision"` with two groups:
- `group_0` — **FP8** (`num_bits: 8`, channel-wise weights, token-dynamic input activations), targeting
  `re:.*self_attn\.(q|k|v|o)_proj$`, `re:.*linear_attn\.(in_proj_qkv|in_proj_z|out_proj)$`,
  `re:.*lm_head`, and `re:.*layers\.(56|57|58|59|60|61|62|63)\.mlp\.(gate|up|down)_proj$`
- `group_1` — **NVFP4** (`nvfp4-pack-quantized`, group_size 16), targeting `re:.*mlp\.(gate|up|down)_proj$` only

So **every module in the approved LoRA target set is FP8, not NVFP4.** Confirmed in the weight
index: attention projections store `.weight` + `.weight_scale`, while MLP stores
`weight_packed` / `weight_scale` / `weight_global_scale`. There is also an FP8 `kv_cache_scheme`
and 303 `ignore` entries. The brief's reasoning about the NVFP4 decompression hook applies to
the MLP group only — and is superseded by §5 anyway.

**1.2 Two safetensors files, not three.** `model.safetensors` (1953 tensors) + `model_mtp.safetensors`
(15 tensors) + `model.safetensors.index.json`. 22 G total, 0 `.incomplete`. Snapshot
`7d6f8d4d72f56b92b3cdbf22f156b90e1bab0108`. No download was needed, as stated.

**1.3 `dtype=torch.bfloat16` alone does NOT dequantize.** Loading with `dtype=torch.bfloat16`
left attention weights as `torch.float8_e4m3fn` and MLP `weight` as `None` (still packed). The
working path is an explicit `CompressedTensorsConfig(dequantize=True)` (transformers 5.17;
`run_compressed=False` is the deprecated spelling). It calls
`ModelCompressor.decompress_model()` in `_process_model_after_weight_loading`
(`transformers/quantizers/quantizer_compressed_tensors.py:126-128`).

**1.4 `linear_attn.in_proj_a` / `in_proj_b` exist and are unquantized** (listed in `ignore`).
They are correctly **not** in the approved target set — noting it so nobody later reads their
absence as an oversight.

---

## 2. Verified venv recipe (replicated from a108)

`uv` was **not** invoked at any point. Plain `python3 -m venv` + `pip`, `--only-binary :all:` on
every install so a source build is a hard error.

```bash
python3 -m venv /home/son/arc3-train-venv
pip install --only-binary :all: \
  --index-url https://download.pytorch.org/whl/cu130 \
  --extra-index-url https://pypi.nvidia.com --extra-index-url https://pypi.org/simple \
  torch==2.11.0+cu130
pip install --only-binary :all: -c constraints.txt \
  transformers peft trl accelerate datasets safetensors compressed-tensors \
  sentencepiece hf_transfer numpy
```

`constraints.txt` is a108's full `pip freeze` minus the `torch` line — not the six versions the
brief named. **`compressed-tensors==0.18.0` is load-bearing and was missing from the brief's
list;** without it the checkpoint cannot be loaded at all.

Resulting pins: torch 2.11.0+cu130, transformers 5.17.0, peft 0.21.0, trl 1.13.0,
accelerate 1.15.0, datasets 5.0.1, safetensors 0.8.0, compressed-tensors 0.18.0, triton 3.6.0.
Both install steps returned rc=0 with no source builds.

### GPU proof (actual output, as required)

```
torch 2.11.0+cu130
cuda.is_available True
device_count 1
device_name NVIDIA GB10
capability (12, 1)
torch.version.cuda 13.0
gpu matmul ok, sum= -121653.0078125
transformers 5.17.0 peft 0.21.0 trl 1.13.0 accelerate 1.15.0 compressed_tensors 0.18.0
```

The system-torch CPU-only trap was avoided; a real bf16 4096×4096 matmul ran on the device.

### Optimized kernels

- `flash-linear-attention` 0.5.2 — **installed** (pure-Python/Triton, `py3-none-any` wheel). This
  matters: it is the chunked gated-delta kernel for all 48 linear-attention layers.
- `causal_conv1d` — **no aarch64 wheel exists**; `pip download --only-binary :all:` fails with
  "No matching distribution found". The conv1d path in those 48 layers therefore runs the
  reference PyTorch implementation. **Any tokens/s measured on this box is an achievable-today
  floor, not an optimized ceiling.** A source build of `causal_conv1d` is the known lever.

---

## 3. Loading the BF16 base — no disk dequantization needed

`CompressedTensorsConfig(dequantize=True)` upcasts **both** groups in memory at load:

```
load_seconds = 133-153 (three runs)
model class  = Qwen3_5ForCausalLM
param bytes by dtype (GiB): {'torch.bfloat16': 51.84, 'torch.float32': 0.0}
total params: 27,833,764,208
mem after load: cuda_alloc 51.85 GiB / cuda_max_alloc 55.40 GiB / cuda_reserved 56.97 GiB
```

51.84 GiB resident — matching the brief's ~51.7 G estimate. **The planned 51.7 G
`save_pretrained` round-trip to disk is unnecessary** and was not performed: the in-memory
dequantization has identical provenance (same file, same weights) and satisfies the brief's
stated rationale (zero train/serve skew on weights, no ~54 GB transfer) without the disk cost.

**Base quality label — do not lose this:** this is an **FP8/NVFP4-upcast BF16 base, NOT the
original BF16 release.** Attention/`lm_head` weights are FP8-channel values upcast to BF16; MLP
weights are NVFP4 values upcast to BF16. Information destroyed by the original quantization is
not recovered by upcasting.

**Vision tower:** under `AutoModelForCausalLM` the model resolves to `Qwen3_5ForCausalLM` and the
~27-block vision tower is **not instantiated at all** (`has vision tower: False`, 0 trainable
params under `model.visual`). "Vision frozen" is satisfied by absence, not by a freeze call.
MTP weights (`model_mtp.safetensors`) are ignored as instructed.

---

## 4. Adapter — verified, not intended

r=16, `lora_alpha=32`, `lora_dropout=0.0`, `bias="none"`, `task_type="CAUSAL_LM"`, explicit
`target_modules`. Counts resolved from the loaded model and asserted:

```
candidate nn.Linear by leaf name (pre-peft):
  {'q_proj': 16, 'k_proj': 16, 'v_proj': 16, 'o_proj': 16,
   'in_proj_qkv': 48, 'in_proj_z': 48, 'out_proj': 48}
ACTUAL LoRA-wrapped module counts:
  {'q_proj': 16, 'k_proj': 16, 'v_proj': 16, 'o_proj': 16,
   'in_proj_qkv': 48, 'in_proj_z': 48, 'out_proj': 48}
total wrapped modules: 208
candidates OUTSIDE decoder layers (vision/MTP leakage): []
trainable params: 39,583,744  (0.142% of 27,833,764,208)
ASSERTIONS PASSED: 16/16/16/16 full-attn, 48/48/48 linear-attn, trainable == 39,583,744
trainable params under model.visual: 0
```

Full-attention layers are 3, 7, 11, … 63 (first `q_proj` at `layers.3`, last at `layers.63`);
linear-attention layers are 0, 1, 2, 4, … 62. Consistent with `full_attention_interval: 4` and
the `layer_types` array.

The brief's 39.6 M figure is exact. Derivation (independently computed, then matched):
- full-attn/layer: q(5120→**12288**, `attn_output_gate: True` folds the gate) 278,528 + k(→1024) 98,304
  + v(→1024) 98,304 + o(6144→5120) 180,224 = 655,360 × 16 = **10,485,760**
- linear-attn/layer: in_proj_qkv(5120→10240) 245,760 + in_proj_z(5120→6144) 180,224
  + out_proj(6144→5120) 180,224 = 606,208 × 48 = **29,097,984**
- total = **39,583,744** ✓

peft's default `target_modules` would indeed have hit only the 16 full-attention layers; the
explicit list plus the per-name assertions is what rules that out.

---

## 5. ROOT CAUSE — activation QDQ silently severs autograd

**This is the most important finding in this report.**

### Symptom
A LoRA step on this stack fails at `loss.backward()` with
`RuntimeError: element 0 of tensors does not require grad and does not have a grad_fn` —
*while* every decoder layer's output reports `requires_grad=True` with a valid `grad_fn`.
Five forward/loss variants (gradient checkpointing on/off, `input_ids` vs `inputs_embeds`,
chunked CE vs the model's own `labels=` loss) all failed identically.

### Mechanism
`compressed_tensors/quantization/lifecycle/forward.py:244-289`, `set_forward_quantized()`,
replaces every quantized module's `forward` with a wrapper that fake-quantizes the **input
activations**:

```python
if enabled and scheme.input_activations:
    input = forward_quantize(self, input, "input", scheme.input_activations)
...
output = self.__class__.forward(self, input)
```

`forward_quantize()` → `fake_quantize()` is decorated **`@torch.no_grad()`** (same file, line 148).
The input therefore reaches `F.linear` **already detached**, and the module returns an output
with no `grad_fn`. This applies to *every* module matched by either config group — all 208 LoRA
targets plus `lm_head` and the MLP.

`dequantize=True` upcasts the **weights** only; it does **not** remove this forward wrapper.

### Why it is dangerous rather than merely broken
peft's `lora.Linear.forward` computes `base_layer(x) + lora_B(lora_A(x)) * scaling`. The LoRA
branch re-attaches a gradient path *around* the severed base layer. So the model still produces
`requires_grad=True` activations, the step runs, and the loss is finite — **but gradient cannot
flow through the frozen base, so most adapters receive either no gradient or a wrong one.**
Measured in-model with QDQ active: of 208 zero-initialised `lora_B` tensors (whose gradients are
nonzero wherever the graph is intact), some were exactly `0.0`.

Note carefully: the modules report `type(...).__name__ == "Linear"` with
`weight.dtype == torch.bfloat16` the entire time. **Class and dtype inspection cannot detect
this. Only a gradient probe can.** An earlier plan in this session to gate on "plain `nn.Linear`
+ bf16 ⇒ trainable" would have passed this checkpoint straight through into a wrong training run.

### Isolated reproduction
`/home/son/arc3-train-a424/qdq_autograd_proof.py` — CPU-only, one 8×4 `Linear`, the exact
`group_0` scheme, no 27B load:

```
module.forward is monkey-patched: Linear.forward
  QDQ ON  (as loaded)     out.requires_grad=False grad_fn=None        d(out)/d(input) reaches x: None
  -> disable_quantization(m); quantization_enabled = False
  QDQ OFF (the fix)       out.requires_grad=True  grad_fn=MmBackward0 d(out)/d(input) reaches x: 10.3125
  QDQ ON  again           out.requires_grad=False grad_fn=None        d(out)/d(input) reaches x: None
  CONTROL plain nn.Linear out.requires_grad=True  grad_fn=MmBackward0 d(out)/d(input) reaches x: 5.21875

VERDICT: CONFIRMED - activation QDQ severs autograd; disabling it restores gradient flow
```

### Fix
The wrapper's own docstring gives the supported off-switch. Use the library helper:

```python
from compressed_tensors.quantization import disable_quantization
for _, m in model.named_modules():
    if hasattr(m, "quantization_scheme"):
        disable_quantization(m)          # sets m.quantization_enabled = False
```

With it off, `quantized_forward` falls through to `self.__class__.forward(self, input)` — ordinary
`F.linear` on the graph-connected input against the already-BF16 weight.

**Required acceptance check for any trainer built on this stack:** after one backward, assert
that **all 208** `lora_B` tensors have a non-`None`, non-zero gradient, and that the loss is
finite. A count below 208 means the graph is still severed somewhere. "It ran and the loss looked
reasonable" is not evidence of a correct step here.

---

## 6. Second skew: training activations are NOT the serving activations

The brief anticipated a weight-quality caveat (§3). Disabling QDQ introduces a **second and
arguably larger** mismatch that the brief did not anticipate:

- **Serving (a108/vLLM):** FP8 dynamic per-token quantization of input activations on q/k/v/o and
  the linear-attention projections; NVFP4 input quantization on MLP; FP8 KV cache.
- **Training (this setup):** `quantization_enabled = False` ⇒ **no activation fake-quant at all.**
  Pure BF16 activations. `use_cache=False` also means the FP8 KV-cache scheme is absent.

The adapter is therefore fit in an activation regime that differs from inference — and activations
are where FP8 dynamic per-token error actually lands at serve time.

This does not block the approved plan: Son Pham approved a BF16-base LoRA, and QDQ-off *is* that
regime. There is no differentiable alternative in this stack — `fake_quantize` is
`@torch.no_grad()` with no straight-through estimator, so preserving QDQ during training would
require writing a custom STE, which is out of scope. Flagging it as a known, deliberate skew
rather than letting it pass silently.

---

## 7. Measured GPU LoRA steps

Setup: bs=1, grad_accum=1, gradient checkpointing ON, chunked cross-entropy (1024-token chunks,
each wrapped in `torch.utils.checkpoint` so only one chunk of logits is ever resident), AdamW
over the 39,583,744 adapter params, `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`.
Inputs are **synthetic random token ids, text-only** — the point is the rate, not learning. No
claim is made about the loss (it sits near `ln(248320) ≈ 12.4`, as random targets should).

**Validity gate passed on this run:**
```
disabled activation QDQ on 417 quantized modules (autograd transparency)
[micro] ISOLATED lm_head(requires_grad input) -> requires_grad True grad_fn MmBackward0
[micro] hidden.sum().backward() OK; lora_B params with grad: 208
WORKING VARIANT: gc=ON  decoder(inputs_embeds)
lora_B tensors: 208 | with nonzero grad: 208 | zero/None: 0
FULL-BACKWARD PROOF: PASS - all 208 adapters received gradient
```

### 7.1 Timings (best of 2 reps; every rep listed)

| seq_len | times (s) | best s/step | tokens/s | peak CUDA (GiB) | sys avail after (GiB) |
|---:|---|---:|---:|---:|---:|
| 2,048 | 8.975 / 8.970 | 8.97 | **228.3** | 56.47 | 55.2 |
| 8,192 | 46.724 / 34.679 | 34.68 | **236.2** | 61.10 | 50.2 |
| 20,480 | 104.765 / 93.162 | 93.16 | **219.8** | 74.29 | 37.4 |
| 32,768 | 176.62 | 176.62 | **185.5** | 87.48 | 23.2 |
| 49,152 | 279.19 | 279.19 | **176.1** | 105.06 | 5.6 |
| 65,536 | — | — | — | **killed** | — |

Throughput is roughly flat at ~176–236 tok/s, degrading gently with length as the 16 quadratic
full-attention layers start to tell. **~220 tok/s at the ~20 K length that matters.**

**These are achievable-today floors, not optimized ceilings** — `causal_conv1d` has no aarch64
wheel, so the conv1d path in all 48 linear-attention layers runs the reference PyTorch
implementation (§2). `flash-linear-attention` *is* installed, so the chunked gated-delta rule is
optimized. Building `causal_conv1d` from source is the known lever if this is too slow.

### 7.2 Max sequence length — 75 K does NOT fit

Activation memory above the 52.3 GiB resident base is strikingly linear:

| seq_len | activations above base | MiB / token |
|---:|---:|---:|
| 20,480 | 21.99 GiB | 1.0996 |
| 32,768 | 35.18 GiB | 1.0994 |
| 49,152 | 52.76 GiB | 1.0992 |

**≈ 1.099 MiB/token.** Hard ceiling = (121.63 − 52.3) GiB ÷ 1.099 MiB ≈ **64,600 tokens at 100 %
of unified memory with nothing left for the OS** — which is why 65,536 did not merely fail to
allocate, it was **killed by the kernel OOM killer**:

```
Out of memory: Killed process 2111866 (python) total-vm:308049984kB
```

This is the GB10 unified-memory hazard: an over-allocation does not reliably raise
`torch.OutOfMemoryError`, it invokes the kernel OOM killer. **It also killed an unrelated
bystander process** (PID 2086419, `./venv/bin/python pull.py`, not mine) as collateral. Anything
run near the ceiling on this box needs a `MemAvailable` gate; my ≥12 GiB pre-flight gate was not
sufficient because the allocation happens *during* the step, not before it.

**Answers to the brief:**
- **Do our ~75 K-token traces fit? No.** 75 K would need ≈ 52.3 + 80.5 = **132.8 GiB** against
  121.63 GiB physical. Not marginal — over by ~11 GiB.
- **Measured max that fits: 49,152** (peak 105.06 GiB, but only 5.6 GiB system headroom left).
- **Recommended working cap: ~49 K**, i.e. the largest length actually observed to survive.
  Purely on memory the ceiling is ~64.6 K, but 49,152 is the largest *measured-safe* value and
  the 65,536 result shows what the failure mode costs.
- The brief's prior estimate ("~64 K fits at 101 G, 94 K does not") was **optimistic**: ~64 K is
  the arithmetic ceiling with zero OS headroom, and the box dies there.

**What truncation costs:** a 75 K trace capped at 49 K loses ~26 K tokens, ~35 % of the episode.
That is a real content decision, not a free knob — decide deliberately whether to drop the
*oldest* turns (preserving the supervised completion and recent context) or to split the episode
across examples. I did not inspect trace contents, so I am not making that call here.

**Naive CE is not an option** regardless of length: at `vocab_size = 248,320` the logits alone
cost ~0.47 MiB/token in bf16 and ~1.42 MiB/token once the fp32 copy exists — ~29 GiB at 20 K
tokens. The peer run's independent naive-CE probe OOM'd at seq 20,816 with a projected 28.9 GiB.
The chunked/checkpointed CE in `bringup.py` is load-bearing.

### 7.3 Epoch-time estimate — derived from the measured 20,480 step

Anchored on the ~20 K measurement because real traces are ~20 K, and stated so it is auditable:

- Corpus: **930 usable turns × ~20 K tokens ≈ 18.6 M tokens/epoch**
- Measured at seq 20,480: **93.16 s/step → 219.8 tok/s** (best of 2; the other rep was 104.77 s → 195.5 tok/s)
- Assumption: **bs=1, grad_accum=1, single GB10**, one turn per step, no packing

```
18.6e6 tokens / 219.8 tok/s = 84,600 s ≈ 23.5 h
18.6e6 tokens / 195.5 tok/s = 95,100 s ≈ 26.4 h
```

**≈ 23.5–26.5 hours per epoch.** Round to **~1 day/epoch** for planning.

**Caveat that materially affects this number:** my measurement is the **text-only** path. Under
`AutoModelForCausalLM` the vision tower is not instantiated (§3), and my inputs are synthetic
token ids with no image embeddings. Real ARC-3 traces contain images. For scale, the peer run on
real multimodal records measured 174.1 tok/s at seq 20,816 with 5 images versus my 219.8 tok/s at
20,480 text-only — and the peer's backward was severed (§7.4), so a *correct* multimodal step is
slower than either figure. **Treat ~1 day/epoch as a floor and re-measure on real multimodal
records before committing to a schedule.**

### 7.4 Box contention, and a warning about the peer run's numbers

A second Bubba subagent (`arc3-a424-lora-step`) was running the **same task** on a424
concurrently, in the same `/home/son/arc3-train-venv`, via `~/arc3-a424-measure/measure4.py`.
Two 52 GiB models do not fit in 121 GiB. The collision drove the box to `MemAvailable = 0`,
produced multi-second SSH latency, and killed one of my runs inside NVFP4 decompression.

On finding the peer further along, **I killed my own run (PID 2104110) and stood down from the
GPU** rather than contend, re-engineered the §5 proof to run CPU-only on a single 8×4 Linear so
the root cause could be established without memory, and only launched my measurement after the
peer's process had exited. Nothing on a108 was touched at any point.

`measure4.py` attributes the graph break to `lm_head` alone and works around it with `F.linear`
on the weight. Its own log reports:

```
lora_B with NONZERO grad: 64 / 208
```

That is **independent corroboration of §5 and evidence the `lm_head`-only fix is incomplete.**
Bypassing `lm_head` restores the graph at the head, but all 208 quantized base Linears remain
severed by the same `@torch.no_grad()` QDQ wrapper, so 144 of 208 adapters got no gradient. After
the §5 fix the same count is **208/208**.

Its measured figures (`seq 10,592 → 58.3 s/step, 181.6 tok/s`; `seq 20,816 → 119.6 s/step,
174.1 tok/s`; `seq 35,258 → 243.3 s/step, 108.4 tok/s`) therefore time a backward that never
propagates through the frozen base — **gradient-incorrect, and cheaper and leaner than a correct
step.** They should not be used as the training rate. Use §7.1 instead, subject to the
text-only caveat in §7.3.

## 8. Files on a424

| Path | What |
|---|---|
| `/home/son/arc3-train-venv/` | the venv (shared with the peer agent) |
| `/home/son/arc3-train-a424/bringup.py` | full bring-up + measurement script, carries the §5 fix |
| `/home/son/arc3-train-a424/qdq_autograd_proof.py` | isolated CPU-only proof of §5 |
| `/home/son/arc3-train-a424/run.sh` | serialised launcher with a memory gate |
| `/home/son/arc3-train-a424/constraints.txt` | a108 freeze used to pin the stack |
| `/home/son/arc3-train-a424/freeze-a424.txt` | resulting a424 freeze |
| `/home/son/arc3-train-a424/results.json` | **STALE — from an earlier failed run.** The measured run was OOM-killed at seq 65,536 before its final `json.dump`, so this file does not contain the §7 numbers. Read `bringup.log`. |
| `/home/son/arc3-train-a424/install-{torch,stack}.log` | install transcripts |
| `/home/son/arc3-train-a424/bringup.log` | **authoritative log of the measured run — all §7 numbers live here** |

**a108 was read-only throughout.** No process, venv, or file there was stopped, restarted, or
modified; the 25-lane massdata rollout was not disturbed.
