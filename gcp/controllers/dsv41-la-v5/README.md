<!--
Author: Claude Opus 5, for Son Pham
Date: 22-September-2026
PURPOSE: Make the DeepSeek-V4.1-Flash ceiling-run controller usable from any machine. Records what
each file is, how to reconstitute the arm from GCS, how to launch, and the sm_120 wall that stopped
the run so nobody spends another night rediscovering it.
SRP/DRY check: Pass. The experiment's rationale, memory arithmetic and outcome live in
docs/plans/2026-09-21-deepseek-v41-flash-ceiling-run.md and are cited, not restated. The harness
values come from plans/2026-09-21-loop-b-arms-on-the-submission-harness.md §1.
-->

# dsv41-la-v5 — DeepSeek-V4.1-Flash on the LA harness, 8x RTX PRO 6000

The controller behind `docs/plans/2026-09-21-deepseek-v41-flash-ceiling-run.md`. It takes the live
`la_v5_clean_return_a` arm (compaction v5 + 14-action clean-return + Loop A deletion, Flash-Next)
and swaps **only the model** to `nvidia/DeepSeek-V4.1-Flash-NVFP4`, served by vLLM at TP8.

**Read the outcome box in that plan before using any of this.** Six launches, zero games: vLLM's
V4.1 sparse attention is internally inconsistent on sm_120 (attention backends fix the KV block at
128, DeepGEMM's sm_120 indexer kernel accepts 32/64 —
[vllm#56702](https://github.com/vllm-project/vllm/issues/56702), closed as not planned), and the
community-patched path decodes at ~1 tok/s because CUDA graphs cannot capture the sparse-MLA + MoE
path there ([vllm#56892](https://github.com/vllm-project/vllm/issues/56892)). The machinery below is
correct and reusable; the *hardware+model pairing* is what failed.

## Files

| file | what it is |
|---|---|
| `derive_arm.py` | builds `dsv41_la_v5_clean_return_a` (7 lanes, 132 min — the Kaggle-parity ceiling arm) from the LA arm: rewrites the model/server block of `startup.sh`, re-pins `CONFIG_FLAGS.json`, re-registers `config_id` through the arm's own `contract.py`. |
| `derive_long.py` | builds `dsv41_la_v5_long` from that: 25 lanes, 5 h/game, 330 min suite, 8 h VM, expert parallel, sm_120 indexer overlay, 300 s capacity gate. Re-pins the runner and `runtime_probe.py` (both live outside the candidate bundle). |
| `launch.py` | `python launch.py --arm dsv41_la_v5_long [--dry-run] [--zones ...]` — uploads any missing receipts, then POSTs a Spot `g4-standard-384` instance body to the Compute API, walking zones on capacity errors. |
| `arms/dsv41_la_v5_long/` | the generated arm, minus the two blobs (see below): `startup.sh`, `runner.py`, `runtime_probe.py`, receipts, and an `instance-body.json` `launch.py` falls back to on a fresh checkout. |
| `SOURCE_ARM_MANIFEST.json` | the 10 GCS objects that reconstitute the **source** LA arm. |

`candidate.tgz` (477 KB) and `selftest.tgz` (548 KB) are deliberately **not** committed — they are
immutable GCS objects, listed in the manifest with their sha256.

## On a fresh machine

1. `gcloud auth login --update-adc`, project `cellensml`. On Windows/Git Bash gcloud needs
   `export CLOUDSDK_PYTHON=/c/python312/python.exe` (see the `gcloud-on-this-box` memory note).
2. To **launch the committed long arm** you need nothing else — `launch.py` uses the arm in this
   directory:
   ```bash
   python launch.py --arm dsv41_la_v5_long --dry-run    # inspect the body first
   ```
3. To **re-derive** (change lanes, clock, server flags), you need the source LA arm. Fetch each
   object in `SOURCE_ARM_MANIFEST.json` into `arms/la_v5_clean_return_a/<local>`, add that arm's
   `startup.sh` (instance metadata of run `g4run-la-v5-clean-return-a132-w7-20260921-a6a2145506`;
   keep a copy — it is not a GCS object), then point `SRC` in `derive_arm.py` at it and run
   `derive_arm.py` → `derive_long.py`.

## What was proven on the hardware

Worth keeping even though the run never played a game:

- The model **loads**: expert-parallel TP8, 38.64 GiB per GPU, weights in ~17 s, Engram tables
  CPU-offloaded at 11.8 GiB per rank (1417 GiB host RAM available).
- `--enable-expert-parallel` is **required**: plain TP8 dies with "Intermediate size padding for w1
  and w3 … NvFp4 backend FLASHINFER_CUTLASS not supported".
- KV dtype must be spelled `fp8`, not `fp8_e4m3` ("DeepseekV4 packed KV layouts only support fp8").
- The model-card image `deepseekv41-flash-0909` lacks the sm_120 sparse backend; `nightly` has it.
- `gcloud storage rsync` (snap 493) can crash in its final report and leave workers hung — the
  model copy is time-boxed per pass and verified against `model.safetensors.index.json` instead.
- 492 GiB copies GCS → local hyperdisk in ~3 min at ~8 GiB/s, same region.

Model stays staged at `gs://cellens-ai-artifacts/arc3-duck/model-flat/DeepSeek-V4.1-Flash-NVFP4`
(491 GiB, 48 shards, `.complete` marker present).

## If the ceiling run is revived

- **V4.1 on H200/B200** — the hardware the vLLM recipe actually tests (`a3-ultragpu-8g`); no
  overlays needed, TP4 + Engram CPU offload straight from the recipe. Check quota first.
- **DeepSeek V4 Flash (284B/13B) on this box** via
  [ormandj/vllm-deepseek-v4-flash-sm120](https://github.com/ormandj/vllm-deepseek-v4-flash-sm120) —
  pinned images with sm_120 fixes for vLLM and FlashInfer, proven on 2x RTX PRO 6000.
