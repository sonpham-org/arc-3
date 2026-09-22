<!--
Author: Claude Opus 5, for Son Pham
Date: 21-September-2026
PURPOSE: Launch spec for one ceiling measurement: the frozen 7.36 harness driven by
DeepSeek-V4.1-Flash (552B MoE, NVFP4) on 8x RTX PRO 6000 (GCP g4-standard-384) instead of the
27B. Records the model choice against the September 2026 open-weight field, the memory
arithmetic, what stays frozen, the smoke-then-full sequence, the risks, and what the run does and
does not answer. Scripts: gcp/stage_dsv41_flash*.sh, gcp/launch_dsv41_flash_8xrtx.sh,
gcp/v12dsv41_flash_startup.sh.
SRP/DRY check: Pass. Harness values are cited to the Loop B spec §1, not restated with reasons.
The no-teacher call is cited to finetune-readiness §9. The model-swap pattern is
gcp/v12gptoss_ffa7gnsg_startup.sh, extended, not copied into prose here.
-->

# DeepSeek-V4.1-Flash on the 7.36 harness, 8x RTX PRO 6000 — one ceiling run

> **CORRECTION 21-Sep (evening), verified against the Kaggle API (`competition_submissions`, field `url`):**
> the 7.36 submission (ref 56408939, 21-Sep 00:16 UTC) came from kernel
> `sonphamorg/arc3-flash-next-clean-return-swap50`, script version **351076929** — the
> **clean-return + search/scorer-removal + 50% swap** candidate (`kaggle-clean-return-swap50-20260919`),
> **not** compaction v5. `arc3-flash-next-compact-v5-clean-return` (351177460) has never been submitted.
> The same clean-return kernel version scored **5.54** the day before. Everything below that says
> "the 7.36 harness" therefore describes the **compaction-v5-clean-return** base, which is what the
> Loop B spec §1 (which this plan inherits) actually describes; their control pair
> (`compaction-v5-clean-return-{a,b}132`, 14.56 / 10.77) is the correct control for those arms, but
> the arms are one mechanism away from the shipped notebook. The shipped notebook's local 132-minute
> controls are the clean-return pair (`clean-return-{a,b}132`: 13.58 / 15.65 overall, 2.76 / 4.27 hard-seven).


> **OUTCOME 22-Sep 04:55 UTC — ramped down on Son's call. Six launches, zero games played.** The model
> itself loads fine on 8x RTX PRO 6000 (expert-parallel, 38.6 GiB/GPU, weights in 17 s) but this vLLM
> build's V4.1 sparse attention is internally inconsistent on sm_120: the V4.1 attention backends fix the
> KV block at 128 while DeepGEMM's sm_120 indexer kernel accepts only 32/64
> ([vllm#56702](https://github.com/vllm-project/vllm/issues/56702), closed as not planned). People who
> patched around it get **~1 tok/s per request** with `--enforce-eager` because CUDA graphs cannot capture
> the sparse-MLA+MoE path on sm_120 ([vllm#56892](https://github.com/vllm-project/vllm/issues/56892)) —
> unusable for a ceiling run. Failure ladder: #1 gcloud rsync hang (fixed) → #2 TP8 NVFP4 padding (EP
> fixes) → #3/#5 indexer block_kv assert → #4 kv dtype spelling `fp8` (fixed) → #6 no common block size
> (128 vs 64). Controller and derivations: `D:\codex-work\dsv41-la-v5-clean-return132-20260921\`.
> Model stays staged at `gs://cellens-ai-artifacts/arc3-duck/model-flat/DeepSeek-V4.1-Flash-NVFP4` (491 GiB).
> If revisited: run V4.1 on H200/B200 (the recipe's tested hardware), or run **DeepSeek V4 Flash** on this
> box via [ormandj/vllm-deepseek-v4-flash-sm120](https://github.com/ormandj/vllm-deepseek-v4-flash-sm120).

**Requested by:** Son, 21-Sep-2026 ("maybe try to run it with 8 RTX then. I just want to see how
good a strong model is").
**Status:** ramped down 22-Sep (see outcome box). Launched from this box; gcloud repaired 21-Sep.

## 0. What this run is for

Under the no-teacher call (`trace-findings/2026-09-15-qwen27b-finetune-readiness.md` §9) a big
model produces no training text. Its one legitimate job here is **inference-only ceiling
measurement**: same prompt, same clock, same 25 games, swap the model. If a 552B model clears the
hard seven where the 27B does not, the gap is model capacity and the RL/SFT track is the right
spend. If it also stalls on them, the harness is the ceiling and the oracle test's answer ("idea
or execution?", HARNESS-NOTES §4.1) is confirmed from the other side.

It trains nothing and produces nothing that may be trained on.

## 1. Why V4.1-Flash and not the others

Field as of 21-Sep-2026, sized against the two boxes GCP sells as "8x RTX":

| model | total / active | 8x RTX 5090 (256 GB) | 8x RTX PRO 6000 (768 GB) |
|---|---|---|---|
| Qwen3.8-27B (ours) | 27B dense | yes | yes |
| DeepSeek V4 Flash | 284B / 13B | 4-bit, thin KV | yes |
| **DeepSeek V4.1-Flash** (MIT, 10-Sep) | 552B / 8B prefill, 16B decode | no | **yes** |
| GLM-5.3 | 753B / 40B | no | 4-bit only, tight |
| Qwen3.8-Max | 2.4T / 95B | no | no (~1.2 TB at 4-bit) |
| Kimi K3 | 2.8T / 104B | no | no (1.56 TB MXFP4) |

V4.1-Flash is the strongest model that fits one 8-GPU box. It ships pre-quantized (FP8 dense,
4-bit experts); the `nvidia/…-NVFP4` build re-quantizes the experts to NVFP4 for Blackwell
kernels and is **492 GiB, 16 GiB larger than the source** — it is a speed build, not a fit build.
16B active on decode means the per-request latency that ends every one of our runs (HARNESS-NOTES
§1.7) should be *lower* than the 27B's, not higher, if the PCIe all-reduce does not eat it.

## 2. Memory arithmetic on g4-standard-384

The vLLM recipe CPU-offloads the Engram tables (196.6B params, ~183 GiB) to host RAM. So:

| | GiB |
|---|---|
| checkpoint on disk | 492 |
| Engram → host RAM (`--engram-config '{"cpu_offload":true}'`) | −183 |
| GPU-resident weights, across 8 GPUs | ~310 (≈39 per GPU) |
| KV budget at `gpu_memory_utilization 0.9`, FP8 KV | ~380 across 8 GPUs |

That KV budget (~14M tokens at ~23 KB/token FP8) means KV is nowhere near the constraint; the
ceiling run still uses **7 lanes** to match the baseline's queueing (§3). It also means 4x PRO 6000 (384 GB) is *marginally* possible
with ~35 GiB of KV total, which is not enough for 25 lanes of 100K context. 8x it is.

## 3. What is frozen

Every harness knob is the 7.36 candidate's own value, per the Loop B spec §1
(`plans/2026-09-21-loop-b-arms-on-the-submission-harness.md`): action cap 14 / return, compaction
v5 + half-context swap, `ARC3_PROMPT_ABLATE_SEARCH=1`, `time_only` budget guidance, context
102985, 2061 s per game, 132 min per run, all 25 games, no pending change carried.

Three things change, and each is recorded in the startup script:

1. **Model**: `nvidia/DeepSeek-V4.1-Flash-NVFP4`, served by vLLM nightly (recipe path) at TP8.
2. **Lanes**: 7, same as the baseline (Son, 21-Sep: keep queueing dynamics identical so the model is the only change). KV would allow 25+; a 25-lane run is a separate, labelled throughput arm, not the ceiling measurement.
3. **Sampling**: DeepSeek's recommended `temperature 1.0 / top_p 0.95 / top_k off` instead of
   Qwen's `0.6 / 0.95 / 20`. Running Qwen's sampler on DeepSeek would measure the wrong thing.

**Control:** the two completed 7.36 runs, `…-a132-w7-20260919-693e7fd43c` (14.56 overall / 4.93
hard-seven) and `…-b132-w7-20260919-0e59b2567b` (10.77 / 3.53). Scored paired per game against
those, per HARNESS-NOTES §1 rules.

## 4. Sequence

1. **Stage the model** (once, ~492 GiB HF → GCS, 30–60 min on an n2 with a 1.2 TB scratch disk):
   `gcp/stage_dsv41_flash.sh`. The VM deletes itself when `.complete` lands.
2. **Upload the 7.36 bundle** from the Codex checkout to
   `gs://cellens-ai-artifacts/arc3-duck/tufa-exact/bundle-kaggle-compact-v5-clean-return-20260919.tgz`.
   The launch script refuses to start without it.
3. **Smoke test** — hard seven, 20 min/game, one wave. Answers: does vLLM nightly bring up V4.1
   at TP8 on sm_120 at all, with or without the recipe's Blackwell sparse-MLA flags; what is the
   per-request latency at 25 lanes; does the harness parse its tool calls.
   ```
   RUN_ID=g4run-dsv41flash-smoke-$(date -u +%Y%m%d-%H%M) MIG_NAME=arc3-g4-dsv41flash \
   ARC3_GAME_SUBSET="bp35,g50t,lf52,ls20,sk48,tn36,wa30" MAX_RUNTIME_S_PER_GAME=1200 MAX_RUN_RUNTIME_MINUTES=30 \
   gcp/launch_dsv41_flash_8xrtx.sh
   ```
4. **Full run**, only if the smoke test served and scored: same command without the subset and
   clock overrides. Two runs if the first one is interesting, one if it is not.

## 5. Blockers and risks

**Blockers (why nothing launched today):**
- `gcloud` on this Windows checkout is broken (`ImportError: cannot import name
  'cache_update_ops'` — corrupt SDK). Repairable, but not silently.
- The 7.36 harness code is not in this repo: none of `ARC3_CONTEXT_COMPACTION`,
  `ARC3_ACTION_CAP`, `ARC3_HALF_CONTEXT_SWAP` exist in this checkout's `ARC3-Inference/`. The
  bundle must come from the Codex task.

**Found on Run #2 (22-Sep 03:00–03:02Z), fixed in the startup ladder:**
- `--indexer-kv-dtype mxfp4 --indexer-sparse-logits true` are vLLM-nightly flags; the pinned
  `deepseekv41-flash-0909` image fails argparse on them. Default off.
- Plain TP8 dies after weight load: `NotImplementedError: Intermediate size padding for w1 and w3,
  for FLASHINFER_CUTLASS NvFp4 backend`. `moe_intermediate_size` is 2304; at TP8 each rank gets 288,
  not a multiple of the 128 the block-scale swizzle needs, and only the TRTLLM path (B200-class
  kernels) can pad gated experts. sm_120 itself was fine: capability 12.0 detected, NVFP4 MoE
  backend chosen, Engram offloaded (11.8 GiB per rank, ~94 GiB total, not the 183 GiB estimated).
  Fix: `--enable-expert-parallel` (experts unsliced, no padding), fallback `--kernel-config
  '{"moe_backend":"marlin"}'`.

**Risks, in the order they would bite:**
1. **sm_120 kernels.** The recipe lists H100/H200/B200/B300/GB200/GB300 and never mentions RTX PRO
   6000. The startup tries the Blackwell sparse-MLA flags first and falls back to plain flags; if
   both fail, the server log lands in the bucket and that is the finding.
2. **Spot capacity for g4-standard-384** in us-central1-b. If it will not schedule, try
   us-central1-a/c or on-demand for the smoke test only.
3. **PCIe TP8 prefill on 94K-token prompts.** No NVLink. The smoke test's per-request latency
   decides whether the full run is worth 132 minutes.
4. **vLLM nightly drift.** The image digest is recorded to the bucket per run; a second run
   should pin `VLLM_IMAGE` to that digest.
5. **Tool-call parser.** `deepseek_v41` is the recipe's parser; if the harness's tool schema
   trips it, that shows up as zero valid actions in the smoke test, not as a crash.

## 6. What the result does and does not say

- A big hard-seven gain says model capacity is the limit *at this harness*; it does not say the
  27B can be trained there, and under the no-teacher call the traces are not training data.
- A flat result says the harness is the ceiling for a much stronger model too, which is the
  oracle test's hypothesis and would move the probe-phase idea (HARNESS-NOTES §4.2) up the list.
- Either way it is n=1 or n=2 on a benchmark whose seed variance alone is 3.33–6.67 %
  (`docs/how-this-feeds-kaggle.md`). Read it as a direction, not a number.
