# Confidence, context, quantization, and offloading

Reviewed 5 September 2026. These are research findings and proposed experiments, not measured deployment improvements. Main-model GPU allocation and KV capacity must not be reduced to accommodate a helper model.

## What the traces say about overfitting

There is evidence of overgeneralizing an observation during play. In WA30 Standard, action 835 treats a white entity as removed; action 905 revisits whether the visual event was only a released crate. Action 1023 corrects a mistaken interpretation of the valid goal region. A detailed persistent plan can therefore preserve a wrong model. [WA30 replay](https://arcprize.org/replay/be78fcef-1244-4cf8-b680-0a5e4e8f9afe?frame=1030&reasoning=decision).

This is different from benchmark contamination. These public recordings cannot reveal whether a game was in training. ARC Prize uses its Semi-Private set for the headline result, requires zero-retention agreements, and explicitly acknowledges possible leakage through API exposure. Neither the score nor a plausible-looking trace proves the absence of contamination. [Testing policy](https://arcprize.org/policy).

The useful execution rule is conditional: **trust a tested transition rule while its conditions still hold**. Knowing how movement works does not establish that the destination or object identity is understood.

- Track successful and failed next-state predictions, the conditions tested, and unresolved exceptions.
- Enter cheap execution for an established plan; inspect each settled observation and leave execution on a contradiction, new mechanic, unexpected collision, changed condition, or level transition.
- Check predicted object changes and relevant timing/phase, rather than expecting the full image to match. A HUD step counter can change while the board does not. Do not discard HUD information or assume a board mask is correct without evidence.
- Preserve game-wide rules across levels, but replace coordinates and recheck applicability. Update the compact record in existing planning calls; an extra model call on every turn would defeat the token objective.

No fixed success count is claimed to establish reliability. Any threshold is a heuristic to calibrate against observed failures. The proposed controller should not require Qwen to generate and debug a full game simulator.

## Current Flash Next serving evidence

Saved log `arc3-g4-q38-kwbase-long6h-r1-vllm.log` records:

| Item | Recorded value |
|---|---|
| Served checkpoint | `RadixArk/Qwen3.8-Flash-Next-NVFP4` |
| Runtime | `v0.1.dev20073+g8e685d198` |
| Weight quantization | `modelopt_fp4`; routed experts are NVFP4 |
| Main KV setting | `auto`, model dtype BF16 |
| Maximum model length | 32,768 |
| Maximum sequences / batched tokens | 22 / 6,144 |
| GPU memory utilization | 0.965 |
| Model-loading GPU memory | 74.04 GiB |
| Available KV pool | 13.74 GiB; 476,446 reported cache tokens |

The best-serving launcher already keeps the large PLE n-gram embedding table in CPU RAM in native FP8 using a pinned lookup patch. Older BF16 conversion comments are superseded by that override. This is lookup offloading, not offloading routed expert computation. The checkpoint's disk size includes those host-resident tables and must not be compared directly with GPU weight residency. [Checkpoint quantization scope](https://huggingface.co/RadixArk/Qwen3.8-Flash-Next-NVFP4).

Local provenance in the originating task: `work/transition-observer/optimization/arc3-g4-q38-kwbase-long6h-r1-vllm.log` lines 33, 470, 481, 501-502; `work/cpu-toolkit-eval/launcher/launch_engine.ps1` best-serving overrides; `outputs/cpu-toolkit/evaluation/run-r1/launch-state.json`. These saved artifacts are not new live measurements and do not establish the identity of the score-13 harness.

Both model families support 262,144 native context tokens. Our 32k is a serving/harness choice, not Flash Next's architectural maximum. The present pool has approximately 14.54 full 32k, 7.27 full 64k, or 3.63 full 128k request equivalents. Those are arithmetic divisions of the reported pool, not tested concurrent capacities. Prefix sharing, recurrent-state allocation, block layout, request lengths, output headroom, and a new startup profile affect the actual result. Increasing maximum length alone does not create more cache or guarantee unchanged throughput. [Flash Next model/config](https://huggingface.co/Qwen/Qwen3.8-Flash-Next/blob/de4b8e4d43b917e7706784d8bb445c9af86a3540/config.json).

## Would Qwen3.8-27B free more room?

Yes for weights, with an important cache tradeoff. These are exact totals of published safetensors files, **not measured resident GPU memory**:

| 27B checkpoint | Bytes on disk | GiB |
|---|---:|---:|
| [Qwen BF16](https://huggingface.co/Qwen/Qwen3.8-27B/tree/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0) | 55,563,006,776 | 51.75 |
| [Qwen FP8](https://huggingface.co/Qwen/Qwen3.8-27B-FP8/tree/017b9c7af6b5689d5dd426a76e0bc077eb5ca20a) | 30,866,866,928 | 28.75 |
| [RadixArk NVFP4](https://huggingface.co/RadixArk/Qwen3.8-27B-NVFP4/tree/319f741cce68d7914884900c138a1fbb70a42f30) | 21,921,697,280 | 20.42 |

The 27B is dense: 48 Gated DeltaNet layers and 16 full-attention layers, with four KV heads of dimension 256. Flash Next has 36 Gated DeltaNet layers and 12 QSA layers, with two KV heads of dimension 256 plus a sparse indexer. Its core MoE activates about 6B of 125B parameters per token; additional n-gram embeddings and MTP are separate. Dense 27B is not necessarily faster despite its smaller total size. Active parameter counts are not a measured latency ratio. [27B configuration](https://huggingface.co/Qwen/Qwen3.8-27B/blob/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0/config.json), [Flash Next model card](https://huggingface.co/Qwen/Qwen3.8-Flash-Next).

For main attention K/V alone, bytes per token are `2 * attention_layers * KV_heads * head_dimension * bytes_per_element`:

| Configuration | Main K/V per token | One 65,536-token sequence | One 131,072-token sequence |
|---|---:|---:|---:|
| Flash Next BF16 | 24 KiB | 1.5 GiB | 3 GiB |
| 27B BF16 KV | 64 KiB | 4 GiB | 8 GiB |
| 27B FP8 KV | 32 KiB | 2 GiB | 4 GiB |

These exclude the sparse-indexer cache, recurrent states, padding, vision activations, CUDA graphs, workspaces and allocator overhead. Thus 27B needs about 2.67 times the **main** KV bytes per token at equal precision. Savings from BF16 27B weights alone do not imply a comparable multiple of cached tokens.

At 22 simultaneously full 128k sequences, 27B needs 176 GiB of BF16 main KV, or 88 GiB even with FP8 KV, before weights and overhead. That does not fit this GPU. At 22 full 64k sequences, FP8 main KV is 44 GiB; together with a roughly 29 GiB FP8 checkpoint, that is a plausible configuration to profile, not a verified fit or speed claim.

The official [vLLM 27B recipe](https://recipes.vllm.ai/Qwen/Qwen3.8-27B) explicitly demonstrates FP8 KV and recommends an **Inferact** NVFP4 checkpoint. Its validated scope is text serving; our complete image/tool workload still needs profiling. The RadixArk size above belongs to a different quantized release, validated by its publisher under SGLang; do not attribute its exact size or compatibility to the Inferact recipe.

## Additional quantization and expert RAM

Weight quantization is already active for Flash Next's routed experts. Attention, shared experts and other components have a different precision policy. More aggressive weight quantization is a new quality/kernel experiment, not a second free 2x reduction.

KV quantization is more directly relevant to context capacity, but Flash Next has a specific obstacle: [vLLM RFC #54426](https://github.com/vllm-project/vllm/issues/54426) reports a BF16-only main-cache guard on the same `8e685d198` build. The contributor's experimental QSA FP8 patch reports about 1.79x cache capacity on one GB10, with no long-run soak or prefix-hit/miss comparison. This is an upstream observation, not a failure reproduced locally or a validated RTX PRO 6000 result. FP4 KV is separate work. Generic vLLM support for a dtype does not establish support for QSA.

Experts can in principle reside in host RAM. Current upstream vLLM provides selective weight-offload/prefetch controls, but these normally leave matrix computation on the GPU and move/access host weights over the interconnect. Prefetch consumes buffers; static parameter selection is not a perfect cache of future router choices. Because routing changes across tokens and games, many experts may be needed across a batch, and transferring weights can reduce the amount of useful reasoning completed before the deadline. Compatibility with our pinned NVFP4/QSA/PLE runtime remains unverified. [Offload configuration](https://docs.vllm.ai/en/latest/configuration/engine_args/#offloadconfig), [UVA source](https://github.com/vllm-project/vllm/blob/main/vllm/model_executor/offloader/uva.py), [prefetch source](https://github.com/vllm-project/vllm/blob/main/vllm/model_executor/offloader/prefetch.py).

KTransformers also supports actual heterogeneous CPU/GPU expert computation, but Flash Next's complete multimodal/QSA/PLE/NVFP4 path was not verified. That is an engine integration project. No local offload latency or score gain has been measured. [Project](https://github.com/kvcache-ai/ktransformers).

## Experiment order

1. Test compact persistent state plus conditional execution on the verified score-13 baseline. Preserve the current allocation. Measure generated reasoning tokens, repeated experiments, prediction errors, solved levels, and score by the same deadline.
2. Test 64k Flash Next with an explicit aggregate cache/concurrency budget. Use a 32k control at the same concurrency to isolate context length, and retain the original serving profile as a throughput reference. Extend harness retention too; a larger server limit with unchanged eviction gains little.
3. Profile 27B FP8 weights + FP8 KV as the simpler smaller-model comparison, followed by a validated NVFP4 checkpoint if quality warrants it. Compare completed work and ARC outcomes, not just tokens per second or a booting server.
4. Evaluate Flash Next QSA FP8 as a separate kernel/correctness experiment before any live adoption. Rank expert offload later because additional host traffic competes with the fixed time budget.

Keep game IDs, seeds, cumulative generated-token accounting and deadlines fixed; replicate promising results. Report per-game and ex-ft09 results in accordance with the repository's scoring convention, and validate generalization on held-out mechanics rather than selecting solely on the public demonstrations. The 108k/game target is generated-token budget; retained input context is a different quantity.
