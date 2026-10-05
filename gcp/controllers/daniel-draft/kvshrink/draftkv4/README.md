# draftkv4: exact nvfp4_qsa KV budget + 4-bit MTP draft KV (Daniel Franzen's SGLang fork)

3-Oct-2026. Patch set for `make_bench_notebook.py --kv4 --patch-set <this dir>`, on top of qsaring + qsakv4.
Goal: fewer bytes per cached token than qsakv4 already gives, with no decode tok/s cost.

## What it changes

Two independent things, each with an off switch:

1. **Exact pool budget for `nvfp4_qsa` (lossless, no kernel change).** The pool sizer
   (`model_executor/pool_configurator.py`) priced an nvfp4_qsa token at 9,429 B while the pools allocate
   8,768 B: it charged a one-layer FP8 dequant workspace (1,024 B/token) that the nvfp4_qsa quant method
   never allocates, and priced the MTP draft layer at 1/12 of the target's 4-bit cost although the draft
   pool is FP8. 661 B/token (7%) of the budget was left idle on the GPU. Now the target is priced without
   the workspace and the draft layer at its own dtype (+ its QSA index keys). Same memory, **+7.5% tokens**
   with the FP8 draft. Only `--kv-cache-dtype nvfp4_qsa` is affected; FP8/BF16 pools keep the old formula
   (which was already exact for them). `SGLANG_QSA_EXACT_KV_BUDGET=0` restores the old formula. A draft
   dtype with no exact formula falls back to the old total. Logged at startup:
   `nvfp4_qsa exact KV budget (kvshrink): target ... + draft ... = ... B/token; the generic formula gave ...`.
2. **MTP draft KV in NVFP4** (`--speculative-draft-kv-cache-dtype nvfp4_qsa`, `server_args.py`). The draft
   pool (1 QSA layer) goes from FP8 1,024 B/token to 576 B (packed E2M1 + FP8 block-16 scales), read by the
   same qsakv4 gather kernels as the target. With (1): 8,320 B/token, **+13.3% tokens** over today.
   Answers are unchanged (spec decoding verifies every draft token against the target); the only risk is a
   lower draft acceptance, i.e. fewer tokens per step. Refused unless the target is `nvfp4_qsa` too (same
   QSA-model / Blackwell / no-host-tier constraints).

Bench usage: `--patch-set D:\codex-work\daniel-draft\kvshrink\draftkv4 --env ARC3_SRV_DRAFT_KVDTYPE=nvfp4_qsa`
(without the `--env`, only change 1 applies: FP8 draft, exact budget).

## Files

| file (in the wheel) | change |
|---|---|
| `sglang/srt/model_executor/pool_configurator.py` | `qsa_exact_kv_budget_enabled`, `qsa_attention_kv_bytes_per_token`; `_compute_cell_size` skips the workspace term for nvfp4_qsa; `DefaultPoolConfigurator._qsa_exact_draft_cell_size` prices the EAGLE/MTP draft at `--speculative-draft-kv-cache-dtype` (None = follows the target) |
| `sglang/srt/server_args.py` | **qsakv4's patched file plus**: `nvfp4_qsa` in the draft dtype choices; `_handle_kv4_compatibility` refuses it without an nvfp4_qsa target. Supersedes qsakv4's copy (same original bytes), so this set is for `--kv4`, not `--kv4-host` (qsakv4h has its own server_args) |

`orig/` = his wheel's exact bytes (LF). No kernel, backend or pool class changes: the draft pool already goes
through `KVCacheConfigurator._build_fp4_quant_method` (nvfp4_qsa method, 256-slot scale table, layer id 0) and
the qsakv4 backend's nvfp4 branches (`_kv4_pool()` reads the quant method from whichever pool the backend owns;
the draft's `QwenSparseMultiStepDraftBackend` and draft-extend backends are `QwenSparseAttnBackend`s on the draft
pool). FlashInfer's constructor check reads the pool's quant method, so it skips the draft pool as it skips the
target's. `move_kv_cache` already carries scale buffers.

## Per-token bytes (Qwen3.8-Flash-Next: 12 QSA layers, 2 KV heads x 256, index keys 1 x 128 BF16 / ratio 4)

| component | FP8 today | nvfp4_qsa (qsakv4) | + this set |
|---|---|---|---|
| target K+V data, 12 layers | 12,288 | 6,144 | 6,144 |
| target FP8 block scales | 0 | 768 | 768 |
| target QSA compressed index keys | 768 | 768 | 768 |
| MTP draft K+V (1 layer) | 1,024 | 1,024 (FP8) | 576 (nvfp4) |
| draft QSA index keys | 64 | 64 | 64 |
| **allocated** | **14,144** | **8,768** | **8,320** |
| **budgeted by the sizer** | 14,144 | 9,429 | 8,320 |
| tokens at the live mem 0.96 / 13 lanes budget | (n/a) | 1,441,984 | 1,634,240 (1,550,656 with the FP8 draft) |

## Test

`test_kvshrink.py` (`--pre-script`, with `--pre-file D:\codex-work\daniel-draft\qsakv4\test_qsa_nvfp4_daniel.py`):
server_args choice + refusal, draft dtype mapping, marginal device bytes/token of the real `QSATokenToKVPool`
(target 12 layers, draft 1 layer, nvfp4/fp8/bf16), the patched `DefaultPoolConfigurator` against those measured
bytes for every draft dtype (and 9,429 with the switch off, 14,144 for FP8), a draft-shaped pool write/read
through the qsakv4 gather kernel, and qsakv4's backend decode / chunked-prefill checks re-run at layer id 0.

## Results (3-Oct-2026, one wave, us-central1-b, 13 lanes, mem 0.96, 131k window, 45-min bench)

Runs: control `daniel-bench-ksctl-1003` (`--kv4`, notebook `a93b04cf8bb6`), bench `daniel-bench-ksd4b-1003`
(`--kv4 --patch-set draftkv4 --env ARC3_SRV_DRAFT_KVDTYPE=nvfp4_qsa`, notebook `e8687490d214` = `76226193ad0e` plus
a line that saves a failed command's stderr; the first try `daniel-bench-ksd4-1003` died at the launcher's
`import sglang, torch` check before any of this code ran, and the identical retry passed it, so treated as transient).

GPU unit test (`working/pre_test_kvshrink.json`): real `QSATokenToKVPool` marginal bytes/token measured
7,680 (target nvfp4) / 13,056 (target fp8) / 640 (draft nvfp4) / 1,088 (draft fp8) / 2,112 (draft bf16); the patched
configurator gives exactly target + draft for every draft dtype, 9,429 with the switch off; draft-layer (id 0) backend
decode and chunked prefill bit-exact vs the unpacked pool. Two test bugs (FP8 expectation off by one: the generic
formula gives 14,143 in floating point; a mask one page short) are fixed in this copy.

| | control | bench (exact budget + 4-bit draft) |
|---|---|---|
| pool tokens | 1,441,984 | 1,634,240 (+13.3%) |
| free GPU after CUDA graphs | 5.03 GB | 4.13 GB (FP8 production at 0.96: 3.84-4.25) |
| decode tok/s, 45 matched min | 822 | 793 (-3.5%) |
| accept length | 2.830 | 2.729 (-3.6%; lower in all nine 5-min buckets) |
| accept rate | 0.610 | 0.576 |
| prefix hit | 93.0% | 93.7% |
| KV pool use mean / max | 0.53 / 0.90 | 0.46 / 0.75 |
| errors / OOM | none | none |

The earlier live run with the control's config (`daniel-ctx-kv4s13-b-1003`) gave accept 2.828, tok/s 820 over the
same window, so accept length repeats to 0.1% between identical runs; the 3.6% drop is the 4-bit draft KV.

**Verdict.** Change 1 (exact budget) is free capacity: no kernel or numerics change, the extra pool fills memory
that sat idle, and the server ran 45 min at the resulting 4.13 GB of free memory. With the FP8 draft it gives
1,550,656 tokens (+7.5%). Change 2 (4-bit draft KV) costs about 3.5% decode speed for +5.4% more tokens: do not
use it while speed is the constraint. Recommended: `--patch-set draftkv4` WITHOUT the draft env (FP8 draft).
Not run end to end in that exact combination (the bench ran both); the byte accounting for it is verified by the
unit test.
