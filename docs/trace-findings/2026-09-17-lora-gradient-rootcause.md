<!--
Author: Claude Opus 5 (Bubba subagent, arc3-lora-grad-rootcause)
Date: 16-September-2026 (filed under the 17-Sep doc date requested in the brief)
PURPOSE: Root-cause analysis of the ARC-3 LoRA gradient blocker recorded in
2026-09-16-a424-lora-step-measurement.md, where only 64 of 208 LoRA adapters received a
lora_B gradient on the Qwen3.8-27B NVFP4 checkpoint. Establishes the cause by CPU-only
experiment on a tiny randomly-initialised model of the same architecture plus a read of the
compressed-tensors and transformers source, gives the fix, and lists explicitly what was not
verified. No GPU was touched: a424's GPU was occupied by another agent's job throughout.
SRP/DRY check: Pass - the measurement that found the blocker is 2026-09-16-a424-lora-step-
measurement.md and is cited, not restated; the training stack is 2026-09-16-a108-training-
stack.md. This file adds only the root cause and the fix.
-->

# ARC-3 LoRA gradient blocker — root cause

**Date:** 16-Sep-2026, 23:00–23:45 ET · **Box:** `gx10-a424` (`ssh son@100.106.31.61`), **CPU only**
**Probe:** `~/bubba-workspace/arc3-run/lora-rootcause/tiny_grad.py` (also at
`/home/son/arc3-lora-rootcause/tiny_grad.py`; per-run JSON beside it)
**Status:** ROOT CAUSE ESTABLISHED. Fix identified and verified in simulation; **not executed
against the 27B checkpoint** — that needs the GPU, which was off-limits this session.

---

## Answer in one paragraph

The LoRA targets are not the problem and neither is the model architecture. The NVFP4
checkpoint's `quantization_config` quantizes **input activations** on exactly the seven
projections we target, plus `lm_head`. compressed-tensors implements that by replacing each
targeted module's `forward` with one that calls `forward_quantize(...)` on the incoming
activation, and `forward_quantize` runs under `@torch.no_grad()`. **That detaches the input.**
Gradient therefore cannot cross any of the 208 LoRA-wrapped modules. The only reason 64 of them
get a gradient anyway is that `self_attn.o_proj` and `linear_attn.out_proj` write straight onto
the residual stream, so upstream gradient reaches *their own output* through the residual path
without ever having to traverse a quantized module. `loading with dequantize=True` does not help:
it decompresses the **weights** and leaves the activation fake-quant forward in place.

---

## Method — what was run, and where

Constraints honoured: a424's GPU was never touched (`CUDA_VISIBLE_DEVICES=""` on every command,
plus `assert not torch.cuda.is_available()` at the top of the probe); a108 was never contacted;
no weights were downloaded; nothing belonging to another process was killed. All work ran
`nice -n 19` with `OMP_NUM_THREADS=4` on a424's CPU, in the existing
`/home/son/arc3-train-venv` (transformers 5.17.0 / peft 0.21.0 / torch 2.11.0) so that library
versions are not a confound.

A tiny `Qwen3_5ForConditionalGeneration` was built **from the real 27B config** with only the
size fields shrunk. Preserved verbatim: `model_type`, `full_attention_interval: 4`,
`attn_output_gate: true`, `output_gate_type`, `head_dim: 256`, `partial_rotary_factor: 0.25`,
`mrope_section [11,11,10]`, `linear_conv_kernel_dim: 4`, `linear_key_head_dim`/
`linear_value_head_dim: 128`, `mamba_ssm_dtype: float32`, `mtp_num_hidden_layers: 1`. Shrunk:
`hidden_size` 5120→256, `intermediate_size` 17408→512, `num_attention_heads` 24→2,
`num_key_value_heads` 4→1, `vocab_size` 248320→1000, `num_hidden_layers` 64→8 with
`layer_types` truncated to `[linear,linear,linear,full] × 2`, `linear_num_key_heads` 16→2 and
`linear_num_value_heads` 48→6 (the 1:3 ratio preserved), vision `depth` 27→1 with text-only
input. That gives 6 linear-attention layers and 2 full-attention layers — 26 LoRA modules under
`language_model`, wrapped from the identical 7-name target list, every one confirmed to be a
peft `Linear` with `lora_B.default.weight.requires_grad == True`.

One forward + backward on 96 random tokens with the back 48 supervised, grads cleared to `None`
and asserted `None` before every backward, loss built the same way the a424 harness builds it
(`mm(input_ids, use_cache=…)` then `F.linear(h, lm_head.weight)` then chunk-free CE).

---

## Result 1 — the tiny model does NOT reproduce the failure

Every configuration swept gives **nonzero `lora_B` gradient on all 26 adapters**. `n`/`none`/
`nonzero` columns as in the original table; `sum|g|` is over `lora_B` only.

| run | attn (resolved) | use_cache | grad ckpt | dtype | in_proj_qkv | in_proj_z | out_proj | q_proj | k_proj | v_proj | o_proj |
|---|---|---|---|---|---|---|---|---|---|---|---|
| t1 | **eager** | False | off | fp32 | 6/6 | 6/6 | 6/6 | 2/2 | 2/2 | 2/2 | 2/2 |
| s2 | **sdpa** | False | off | fp32 | 6/6 | 6/6 | 6/6 | 2/2 | 2/2 | 2/2 | 2/2 |
| s3 | eager | **True** | off | fp32 | 6/6 | 6/6 | 6/6 | 2/2 | 2/2 | 2/2 | 2/2 |
| s4 | eager | False | **non-reentrant** | fp32 | 6/6 | 6/6 | 6/6 | 2/2 | 2/2 | 2/2 | 2/2 |
| s5 | eager | False | off | **bf16** | 6/6 | 6/6 | 6/6 | 2/2 | 2/2 | 2/2 | 2/2 |
| s6 | sdpa | False | off | bf16 | 6/6 | 6/6 | 6/6 | 2/2 | 2/2 | 2/2 | 2/2 |
| s7 | sdpa | True→False* | non-reentrant | bf16 | 6/6 | 6/6 | 6/6 | 2/2 | 2/2 | 2/2 | 2/2 |

(cells are `nonzero / n`; `none` was 0 everywhere. *transformers logs
"`use_cache=True` is incompatible with gradient checkpointing. Setting `use_cache=False`".)

The resolved attention implementation was **printed, not assumed**, on every run — `'eager'` and
`'sdpa'` respectively, matching what was requested.

So: the architecture, peft 0.21.0's wrapping, the gated-delta reference kernel, `use_cache`,
`attn_implementation` and gradient checkpointing are **all cleared**. None of them can produce
the 64/208 pattern.

**Caveat the brief asked for and I am honouring:** a non-reproduction on tiny-CPU does *not* by
itself prove "harness bug". `fla` warns `Triton is not supported on current platform, roll back
to CPU`, so the CPU run exercises a different linear-attention code path than the GPU run did
(see Result 3). The conclusion below rests on the source read and the positive reproduction in
Result 2, not on this negative alone.

---

## Result 2 — the failure reproduces exactly when the base layer's input is detached

Hypothesis: the prior session found `lm_head.forward` had been replaced by compressed-tensors
with something that runs under `no_grad`, and fixed it by calling `F.linear` on the raw weight.
That fix treated the symptom at one module. The same replacement is installed on **every**
quantized module — it just doesn't raise there, because peft's added `lora_B(lora_A(x))` branch
keeps the output's `requires_grad` alive. And `lora_B` is zero-initialised, so the surviving
branch propagates **exactly zero** back to `x`.

Simulated on the tiny model by patching each LoRA base layer's forward so that only the *input*
passes through a `torch.no_grad()` region — faithful to `forward_quantize`, which quantizes the
activation and leaves the matmul alone:

| module | n | grad is None | **nonzero grad** | Σ&#124;grad&#124; |
|---|---|---|---|---|
| `linear_attn.out_proj` | 6 | 0 | **6** | 12.037 |
| `self_attn.o_proj` | 2 | 0 | **2** | 15.167 |
| `linear_attn.in_proj_qkv` | 6 | 0 | **0** | 0.0 |
| `linear_attn.in_proj_z` | 6 | 0 | **0** | 0.0 |
| `self_attn.q_proj` | 2 | 0 | **0** | 0.0 |
| `self_attn.k_proj` | 2 | 0 | **0** | 0.0 |
| `self_attn.v_proj` | 2 | 0 | **0** | 0.0 |

**That is the a424 pattern, module-for-module** (a424: `out_proj` 48/48 and `o_proj` 16/16
nonzero; `in_proj_qkv`, `in_proj_z`, `q_proj`, `k_proj`, `v_proj` all zero). Identical under
`eager` and `sdpa`. Tensor-level hooks on the projection outputs show why: the hook on
`out_proj`'s output fires with `|g| = 428`, the hook on `in_proj_qkv`'s output fires with
`|g| = 0.0` — the graph edge exists, the value travelling down it is zero.

### Why o_proj and out_proj are the survivors

`hidden = hidden + self_attn(...)` and `hidden = hidden + linear_attn(...)`. `o_proj` /
`out_proj` produce those addends, so gradient reaches their **outputs** along the residual
identity path without crossing a quantized module. Everything else in the block sits *behind*
`o_proj`/`out_proj`, so its gradient must pass through one — and cannot.

---

## Result 3 — the source, read rather than inferred

**`config.json` of `unsloth/Qwen3.8-27B-NVFP4`, `quantization_config.config_groups`:**

```
group_0 targets = ['re:.*self_attn\.(q|k|v|o)_proj$',
                   're:.*linear_attn\.(in_proj_qkv|in_proj_z|out_proj)$',
                   're:.*lm_head',
                   're:.*layers\.(56|57|58|59|60|61|62|63)\.mlp\.(gate|up|down)_proj$']
        input_activations.dynamic = True      output_activations = None
group_1 targets = ['re:.*mlp\.(gate|up|down)_proj$']
        input_activations.dynamic = 'local'   output_activations = None
quantization_status = 'compressed'   format = 'mixed-precision'
```

`group_0`'s target list **is** our LoRA target list, plus `lm_head`. The `ignore` list covers the
whole vision tower, `in_proj_a`, `in_proj_b`, the gated norms and `mtp.*` — none of the seven.

**`compressed_tensors/quantization/lifecycle/forward.py` (v0.18.0):**

```python
def set_forward_quantized(module):
    def quantized_forward(self, input):
        ...
        if enabled and scheme.input_activations:
            input = forward_quantize(self, input, "input", scheme.input_activations)   # <-- here
        ...
        with patch_attr(weight, "data", weight_data):
            output = self.__class__.forward(self, input)
        return output
    module.forward = quantized_forward.__get__(module)
```

`forward_quantize` returns `fake_quantize(...)`, and line 148 of the same file is
`@torch.no_grad()` directly above `def fake_quantize(` (`_process_quantization` at 185 carries it
too). A tensor returned from a `no_grad` region is a fresh leaf: **the input is detached.** There
is no straight-through estimator on the activation fake-quant.

**`transformers/quantizers/quantizer_compressed_tensors.py`:** `_process_model_before_weight_loading`
calls `apply_quantization_config(model, remaining_config, run_compressed=False)` — that is what
installs the patched forwards — and `_process_model_after_weight_loading` calls only
`self.compressor.decompress_model(model)` when `dequantize=True`. **Decompressing the weights does
not remove the forward patch.** `is_qat_trainable()` returns `True` for this configuration, which
is how the path presents itself as fine-tunable while silently having no gradient at the
activation.

This also explains the prior session's "Blocker 1" as the *same* bug: `lm_head` is in `group_0`,
its input is detached, so its output carried no `grad_fn` at all, and there was no LoRA branch on
it to disguise the fact.

**One secondary detail not explained — open question, with the check named.** On a424,
`k_proj` and `v_proj` reported `p.grad is None` (16/16 each) where `q_proj` reported an allocated
all-zero grad. In the CPU simulation all five starved buckets report allocated-zero, none report
`None`. So the mechanism above accounts for "no gradient", but the `None`-versus-zero split is a
downstream artifact of the GPU run and I have two candidates and no evidence separating them: the
fused CUDA SDPA backward returning undefined grads for `key`/`value` at exactly-zero
`grad_output`, or accelerate's dispatch (`device_map="cuda:0"` installs hooks, and
`Qwen3_5GatedDeltaNet.forward` carries `@force_accelerate_hooks("conv1d")`). **The discriminating
check is one read-only line on the next session:** print `hasattr(mod, "_hf_hook")` for one leaf
of each of the seven target types and see whether `k_proj`/`v_proj` differ from `q_proj`. This
does not block and does not change the fix.

**`fla` is in play on the GPU and was not exercised on CPU.** The hub-kernel decorator
`@use_kernel_func_from_hub_with_fallback("chunk_gated_delta_rule", "fla")` binds fla's Triton
kernel unconditionally whenever `fla` is importable, with no opt-out flag; a424's `gradtest.log`
carries the fallback warning for `causal_conv1d_fn` but **not** for `chunk_gated_delta_rule`, so
fla's kernel ran there. On CPU, fla raises `RuntimeError: 0 active drivers` and the probe
explicitly unbinds it to `__wrapped__` (the reference PyTorch path). fla is therefore **not
cleared for the GPU**, only shown to be unnecessary as an explanation — the detached-input
mechanism already accounts for all 144 dead adapters on its own.

---

## The fix

**Preferred — train on the true BF16 checkpoint.** `/home/son/models/Qwen3.8-27B-BF16` (the
55.6 GB pull that was in flight tonight; leave it alone until it finishes) carries no
`quantization_config`, so no forward is patched and no activation is detached. This is the clean
fix and it needs no code.

**If the NVFP4 checkpoint must be used**, disable the fake-quant on every module that carries a
compressed-tensors scheme, immediately after `from_pretrained` and before `get_peft_model`:

```python
for m in model.modules():
    if getattr(m, "quantization_scheme", None) is not None:
        m.quantization_enabled = False      # honoured by quantized_forward; falls through to
                                            # nn.Linear.forward, which is differentiable
```

`quantized_forward` reads `getattr(self, "quantization_enabled", True)` and, when false, skips
both the input and weight QDQ and calls `self.__class__.forward(self, input)` directly. The fallthrough
is safe on the weight path for two independent reasons. First, `quantized_forward` only fake-quants
the weight when `status < COMPRESSED`, and this checkpoint's status *is* `compressed`, so the weight
QDQ was already being skipped — turning `enabled` off changes nothing there. Second, the prior
session's `lm_head` autopsy is direct evidence that `decompress_model` leaves a module
`nn.Linear.forward` can consume: it reported `Linear(in_features=5120, out_features=248320,
bias=False)` with a real BF16 `weight` of shape `(248320, 5120)`, and `F.linear(x, lm_head.weight)`
on that same weight object returned a correct differentiable tensor. The leftover `weight_scale` /
`quantization_scheme` / `quantization_status` attributes are inert once `enabled` is false. With
`dequantize=True` the weights are already plain BF16, so skipping QDQ is also the numerically
correct thing to do for a BF16 LoRA — it removes activation rounding that has no business being
in a fine-tune. Side benefit: `lm_head` becomes differentiable again, so the
`F.linear(x, lm_head.weight)` workaround is no longer needed (harmless to keep).

**Do not rely on `attn_implementation`, `use_cache`, gradient checkpointing, `fla` or
`causal_conv1d` as the lever.** All were swept and none of them moves this.

**Verified how far:** the mechanism is reproduced in simulation and read in the source. The fix
line itself is a one-line consequence of that source read and **has not been executed against the
27B**, because that requires the GPU. Run the pre-flight below as the first thing on the next GPU
session; it is designed to be cheap and to fail loudly.

---

## Pre-flight assertion

Ship `tools/assert_lora_gradients.py` (this PR) and call it before any training round. It asserts that **every** LoRA `lora_B` parameter receives
a nonzero gradient on one backward and prints the per-bucket table when it doesn't. It
deliberately checks `lora_B` only: `lora_A`'s gradient is `∝ B` and is identically zero on the
first backward from peft's zero-init, so an all-zero `lora_A` column is expected and proves
nothing.

---

## What I did NOT verify

1. **The fix on the real 27B.** Not run. GPU off-limits (another agent's job at 96%; a424 has
   unified memory and an over-allocation takes the box down). Everything about the fix is
   source-read plus simulation.
2. **The BF16 checkpoint's gradient behaviour.** Not loaded; the download was still in flight.
   Asserted only from the absence of a `quantization_config` in
   `/home/son/models/Qwen3.8-27B-BF16/config.json`.
3. **fla's Triton `chunk_gated_delta_rule` backward on GB10/sm_121.** Cannot run on CPU. It may
   also be broken; the detached-input mechanism makes it unnecessary as an explanation but does
   not exonerate it. Re-check after the fix: if `in_proj_qkv` is still dead while `q_proj` has
   come back, fla is the next suspect.
4. **`causal_conv1d`.** Not installed on a424 and not installed by me. Its absence is a speed
   issue, not a gradient issue — the reference `causal_conv1d_fn` is plain `F.conv1d` and is
   differentiable.
5. **The `None`-versus-zero split on `k_proj`/`v_proj`.** Explanation offered above is a
   hypothesis, unverified.
6. **Vision-tower gradient flow.** The tiny model ran text-only with `vision depth=1`. The tower
   is frozen by design, but no image actually passed through it in these runs.
7. **Whether the 64 surviving adapters were learning anything useful.** Out of scope; the point
   is that 144 were mathematically inert.

---

## Files

- Pre-flight + its CPU self-test: `tools/assert_lora_gradients.py --self-test` (this PR)
- Sweep probe (not in this repo): `~/bubba-workspace/arc3-run/lora-rootcause/tiny_grad.py`, mirrored
  on a424 at `/home/son/arc3-lora-rootcause/tiny_grad.py`
- Per-run JSON on a424: `~/arc3-lora-rootcause/{t1,s2..s7,D-eager,D-sdpa,F}.json`
- Prior measurement that found the blocker: Bubba's workspace,
  `docs/2026-09-16-a424-lora-step-measurement.md` (not in this repo)
