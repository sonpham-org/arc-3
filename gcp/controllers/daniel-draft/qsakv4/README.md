# qsakv4: 4-bit (NVFP4) KV cache for the QSA layers, on Daniel Franzen's SGLang fork

Port of our patch `0007-qsa-nvfp4-kv` (sglang-scored/kv4) to his "Pennyroyal" sglang 0.5.19+gd00d88efc8d6
(wheel `D:\codex-work\daniel-draft\wheel\sglang.whl`), on top of the `qsaring` patch. 3-Oct-2026.

**Status: written and checked on CPU only (every file compiles; no undefined names). Nothing here has run on a
GPU yet.** Run `test_qsa_nvfp4_daniel.py` in his venv on the RTX PRO 6000 before any benchmark.

## What it does

Only the 12 QSA full-attention layers (3, 7, ..., 47) have a KV cache; it goes from FP8 (12 KB per token) to NVFP4
(6.75 KB per token: packed E2M1 pairs, one FP8 E4M3 scale per 16 values, one FP32 global scale per layer). QSA never
reads the whole cache: it gathers the rows it selected (at most 2,048 + tail per query) into a scratch buffer and
attention reads the scratch. So 4-bit KV only changes the gathers: two new Triton kernels unpack exactly the selected
rows into the scratch, in FP8 by default. Every attention kernel downstream then sees the same FP8 data it reads today
with `--kv-cache-dtype fp8_e4m3`. Pools that are not `nvfp4_qsa` (FP8, BF16) take the original code paths unchanged.

Expected gain at the same memory: about +50% KV tokens (this is the server's own budget arithmetic; see "Memory
accounting"). Our tree measured +50% and decode speed unchanged (the 4-bit gather is 18% faster than the FP8 one).

## Install

`patched/` holds the 8 changed files, `orig/` the exact bytes from his wheel (LF, UTF-8). The backend file in
`patched/` is the **qsaring backend plus these changes**, so it needs qsaring's other four files installed too
(it passes `ring_size=` to qsaring's `metadata.py`). With `SGLANG_QSA_RING_SIZE` unset, the ring code is his
original layout.

Files to install (paths inside the wheel, `sglang/srt/...`):

```python
KV4_FILES = (
    "sglang/srt/layers/attention/qsa/sparse_attn.py",
    "sglang/srt/layers/attention/qwen_sparse_attn_backend.py",   # supersedes qsaring's copy
    "sglang/srt/layers/attention/flashinfer_backend.py",
    "sglang/srt/layers/quantization/fp4_kv_cache_quant_method.py",
    "sglang/srt/mem_cache/kv_cache_configurator.py",
    "sglang/srt/mem_cache/kv_cache_dtype.py",
    "sglang/srt/mem_cache/memory_pool.py",
    "sglang/srt/server_args.py",
)
QSARING_FILES_STILL_NEEDED = (   # from ../qsaring/patched/
    "sglang/srt/mem_cache/qsa_kv_pool.py",
    "sglang/srt/layers/attention/qsa/metadata.py",
    "sglang/srt/layers/attention/qsa/graph_metadata.py",
    "sglang/srt/layers/attention/qsa/qsa_indexer.py",
)
```

`make_bench_notebook.py` (not changed here) builds one shadow wheel from patch sets and asserts no file comes from
two sets. To use this: `add_set("qsaring", QSARING_FILES_STILL_NEEDED)` plus `add_set("qsakv4", KV4_FILES)`, and
`--kv nvfp4_qsa` (it already sends `--speculative-draft-kv-cache-dtype fp8_e4m3` separately). Every `orig/` file is
his wheel's exact bytes, so the sha check in the port cell holds.

## Server arguments

Change from his current command:

| his flag today | use |
|---|---|
| `--kv-cache-dtype fp8_e4m3` | `--kv-cache-dtype nvfp4_qsa` |
| `--speculative-draft-kv-cache-dtype fp8_e4m3` | keep it. His launcher passes `CFG["KVDTYPE"]` to both flags; the draft flag does not accept `nvfp4_qsa`, so the draft must be given `fp8_e4m3` explicitly (the bench builder already does) |
| `--enable-hierarchical-cache` (and its `--hicache-*` flags) | remove: refused (see below) |
| `--attention-backend flashinfer`, `--page-size 64`, CUDA graphs, mamba `extra_buffer`, `--gdn-mtp-cache-mode none` | unchanged |

The extra capacity shows up as more KV tokens at the same `--mem-fraction-static`; spend it with
`--context-length` / `--max-running-requests` / CUDA-graph max batch size as planned. If a run pins
`--max-total-tokens`, raise it.

Environment knobs (all optional):

| variable | effect |
|---|---|
| `SGLANG_NVFP4_QSA_SCRATCH=bf16` | unpack to BF16 instead of FP8: more precision, twice the scratch. Default `fp8`. Any other value raises at the first nvfp4_qsa read |
| `SGLANG_NVFP4_QSA_GLOBAL_SCALE=<x>` | one FP32 global scale for every layer (must be positive and finite). Default: checkpoint k/v scales if present, else 1.0. His AutoRound checkpoint has no k/v scale tensors, so 1.0 |
| `SGLANG_QSA_RING_SIZE` | qsaring, unchanged |

## What is refused, and why

`server_args` refuses `nvfp4_qsa` with any of these, with one clear message: `--enable-hierarchical-cache`,
`--enable-lmcache`, `--enable-flexkv`, `--disaggregation-mode prefill|decode`, `--enable-unified-memory`,
`--enable-page-major-kv-layout`. The first four copy pool bytes to a host tier, another server or storage without the
FP4 block-scale buffers (the host pool `pool_host/qsa.py`/`mha.py` has no scale buffers; the PD transfer registers
only K/V); a restored row would be read with wrong scales. The last two build a pool that bypasses the FP4 quant
method or changes its layout. It also refuses non-QSA models and non-Blackwell (SM100/SM120) GPUs. The KV cache
configurator repeats the non-QSA and hierarchical-cache refusals when the pool is built.

## Choice of dtype name: new `nvfp4_qsa`, his `nvfp4` untouched

His fork's FP4 KV machinery (quant-method registry, `kv_cache_dtype.py`, the configurator's FP4 pool build, the
pool's quantized write path) is byte-identical to the tree 0007 was cut against, so `nvfp4_qsa` ports unchanged as a
new registry entry. Reusing `nvfp4` would mean widening its access rules and the KV4 guard, and it would still
allocate the FP8 dequant workspace `nvfp4` declares for FlashInfer prefill (about 1 KB per token that QSA never
reads). A separate name keeps `nvfp4` exactly as it was for every other model. One behavior of `nvfp4` on QSA models
does change: it used to crash with a Triton `KeyError`; now the QSA backend raises a clear `NotImplementedError`
naming `nvfp4_qsa`.

His two earlier failures, located:
- The "KV4 guard" is `ServerArgs._handle_kv4_compatibility`: for `nvfp4` with a non-FA4 MHA model it asserts the
  attention backend is one of triton / torch_native / flex_attention / trtllm_mha. `nvfp4_qsa` returns before that
  list (QSA is chosen per model, not by `--attention-backend`).
- The `KeyError: float4_e2m1fn_x2` is not a table in his code: for a quantized pool `get_key_buffer` returns the
  packed rows viewed as `torch.float4_e2m1fn_x2`, and Triton's torch-dtype-to-Triton-type lookup has no entry for it
  when that view reaches `_compact_kv` / the chunk-prefill kernel. The nvfp4_qsa paths never call `get_key_buffer`
  on an FP4 pool; they take the raw packed uint8 rows and FP8 scales from `get_raw_kv_buffer`.

## Per-file changes

| file | change |
|---|---|
| `layers/attention/qsa/sparse_attn.py` | His file is byte-identical to our base, so 0007's kernels apply unchanged: `_compact_kv_nvfp4` (top-k gather + unpack, decode / verify / draft-extend) and `_gather_slots_nvfp4` (ordered slot gather + unpack, chunked prefill with a cached prefix), wrappers `qwen_sparse_kv_extraction_compact_nvfp4_triton` / `qwen_sparse_gather_slots_nvfp4_triton`. New vs 0007: the wrappers check every buffer's dtype, shape and contiguity (host-side asserts, they run at capture only), including that scales are viewed as FP8 E4M3 (a uint8 view would be read as integers) |
| `layers/attention/qwen_sparse_attn_backend.py` | From qsaring's version. `_nvfp4_kv(layer_id)` returns raw packed K/V, FP8 block scales and that layer's global scales (indexed by absolute layer id, as the write side does), or `None` for unquantized pools. `_save_kv` writes with `k_scale=None, v_scale=None` so the pool uses its per-layer device scales (the hybrid pool's float default 1.0 would ignore configured scales and build a host tensor during CUDA-graph capture). The three CUDA read paths branch on it (table below); both CPU paths raise for nvfp4_qsa. A quantized pool of any other recipe raises `NotImplementedError`. Scratch dtype from `SGLANG_NVFP4_QSA_SCRATCH`, read once and only for nvfp4_qsa pools |
| `layers/attention/flashinfer_backend.py` | With `--attention-backend flashinfer` the target builds a FlashInfer backend first and `attn_backend_wrapper` then installs QSA for every full-attention layer. FlashInfer's constructor would refuse the nvfp4_qsa pool (no FlashInfer access rule); it skips that check for `nvfp4_qsa` only. FlashInfer never reads this pool |
| `layers/quantization/fp4_kv_cache_quant_method.py` | Byte-identical to our base; 0007's `NVFP4QSAKVCacheMethod`: the NVFP4 recipe, access rules NATIVE_FP4 for backend `qsa` only (so no FP8 dequant workspace is allocated), global-scale table of at least 256 entries (the configurator sizes it by the 12 full-attention layers, but reads and writes index it by absolute layer id up to 47), `SGLANG_NVFP4_QSA_GLOBAL_SCALE` override (new: rejects non-positive / non-finite values) |
| `mem_cache/kv_cache_dtype.py` | `nvfp4_qsa` maps to `torch.float4_e2m1fn_x2` like `nvfp4`, so every torch-dtype-based FP4 branch (pool build, cell size) applies |
| `mem_cache/kv_cache_configurator.py` | `_build_fp4_quant_method`: `nvfp4_qsa` only for QSA models, and not with hierarchical cache |
| `mem_cache/memory_pool.py` | `MHATokenToKVPool.get_cpu_copy` / `load_cpu_copy` carry the block scales when the pool has them (0007 hunk; his code here is identical). In his fork only PD-decode retraction calls these, and PD is refused for nvfp4_qsa, so this is defense in depth. It also makes his `nvfp4` / older FP4 pools restore their scales (previously restored rows kept stale scales) |
| `server_args.py` | `nvfp4_qsa` choice and help; `_handle_kv4_compatibility` branch: SM100/SM120 only, QSA model only, the refusals above; FlashInfer allowed |

## KV read paths in his QSA backend, and what each does with nvfp4_qsa

| path | mode | today (FP8) | nvfp4_qsa |
|---|---|---|---|
| `forward_extend`, no cached prefix | prefill | attends over this chunk's own BF16 K/V; reads no cache | unchanged (writes the chunk quantized) |
| `forward_extend`, cached prefix | chunked prefill, radix hits | joined `gather_index` (his one-`index_select` version), `k_buffer.index_select` -> `sparse_gqa_fwd_interface_triton_ck` | same index, `_gather_slots_nvfp4` into a scratch of the same shape and (FP8) dtype -> same kernel |
| `_forward_paged_attention` -> `_forward_trtllm_sparse` | decode, target verify, draft extend (SM100/SM120 with FlashInfer trtllm decode) | valid counts, `_compact_kv` into page-strided FP8 scratch, trtllm decode | `_compact_kv_nvfp4` into the same scratch layout (head dim = packed dim x 2) |
| `_forward_paged_attention`, FA2/FA4 varlen fallback | same modes without trtllm decode | cu_seqlens, `_compact_kv`, `flash_attn_varlen_func` | `_compact_kv_nvfp4`, same scratch and kernel |
| `forward_extend` / `_forward_paged_attention` on CPU (`not q.is_cuda`) | reference only | `qsa_sparse_attention` on `get_key_buffer` | raises `NotImplementedError` |
| QSA indexer, `prefill_all_visible`, `QSAMTPSharedSparseIndices` | all | read only the BF16 index-key ring and compressed keys, never the K/V cache | unchanged |
| outside the backend: `move_kv_cache` | spec decode | per-buffer pointer/stride copy | already carries the scale buffers (his `_slot_move_pointer_buffers`) |
| `get_cpu_copy` / `load_cpu_copy` | PD-decode retraction | K/V only | carries scales (and PD is refused) |
| HiCache host pool, PD transfer, LMCache, FlexKV | | | refused at startup |

The MTP draft layer has its own pool; with `--speculative-draft-kv-cache-dtype fp8_e4m3` it is an FP8 pool and its
QSA backends (`QwenSparseMultiStepDraftBackend`, the draft runner's draft-extend backend) take the old paths. If the
draft were left to inherit `nvfp4_qsa`, the same nvfp4 branches would serve it (not tested).

CUDA graphs: nothing new syncs or allocates per replay. The write uses device-resident scale slices; the reads use
views of the pool and the scale table; the scratch is the existing per-backend cache (`_get_fa2_scratch`, allocated
at capture); the kernels take every changing value from device buffers.

## Memory accounting (unchanged, but read this before tuning `--mem-fraction-static`)

The pool sizer (`model_executor/pool_configurator.py`, not changed, same as our tree) prices an FP4 token as packed
data + block scales + **one FP8 dequant workspace row (1 KB) that nvfp4_qsa never allocates**, and it prices the MTP
draft layer at the target's per-layer cost (4-bit) although the draft pool is FP8. For this model, per token:

| | budgeted by the server | allocated |
|---|---|---|
| FP8 today | (12,288 + 768 QSA index) x 13/12 = 14,144 B | 13,056 target + 1,088 draft = 14,144 B |
| nvfp4_qsa | (6,144 + 768 scales + 1,024 workspace + 768 QSA index) x 13/12 = 9,429 B | 7,680 target + 1,088 draft = 8,768 B |

So the server sizes for 1.50x the tokens and keeps about 7% (661 B/token) unused. Do not remove the workspace term
alone: the draft term would then be under-budgeted by about 450 B/token.

## Not ported, or not sure

- **No GPU run yet.** The two Triton kernels are byte-identical to 0007's, which were bit-exact against FlashInfer's
  dequantizer on the RTX PRO 6000 (BF16 and FP8 scratch, global scales 1 and 0.01; mismatch fraction 0.0 everywhere
  in `gs://cellens-ai-artifacts/arc3-duck/lobotomy/kv4lab/results/unit.jsonl`).
  The backend wiring is new to his structure (his joined-index prefix gather, the stall-diagnostics hooks, the
  qsaring ring code) and is covered only by the new test.
- `SGLANG_NVFP4_QSA_SCRATCH=bf16` was a knob in our tree, not a benchmarked configuration. The test checks it for
  correctness only.
- Hierarchical cache with 4-bit KV is not ported: the host pool and its transfer kernels would need the two scale
  buffers per layer.
- Global scales are not calibrated (1.0). On SM100 (not SM120) the inherited loader multiplies checkpoint scales by 6
  (a TRT-LLM XQA convention); write and read use the same value, so it stays consistent, but SM100 is untested.
- The tokenwise QSA variant (Qwen3Next-DSA pool) goes through the same backend methods; it is allowed but untested.
- The test drives the real backend, kernels and quant method over a stand-in for `QSATokenToKVPool` (it mirrors
  `HybridLinearKVPool` / `MHATokenToKVPool` on the calls the backend makes). The real pool's code on those calls is
  unchanged from our tree, where 0007 served end to end; but a full server start with `nvfp4_qsa` is the first test
  of `server_args` and the configurator in his fork.

## Test

`test_qsa_nvfp4_daniel.py` runs in his venv on the GPU with the patched files installed and no server running:
`python test_qsa_nvfp4_daniel.py [--skip-speed]`. One JSON line per check, then one summary line; exit status 1 on
any failure. It checks: our pure-torch dequantizer against FlashInfer's; both kernels against it (FA-packed and
trtllm-strided gather layouts, int32/int64 slot ids, -1 padding, out-of-range positions, top-k 2,051, global scales
1 / 0.01 / 8 with FP8 clamping, guard rows untouched); the quant method (registry, access rules, no workspace, table
size, override, `--kv-cache-dtype` mapping for target and draft); the real write path read back; the backend's decode
and chunked-prefill-with-prefix outputs on the 4-bit pool equal to the outputs on an unquantized pool holding exactly
the unpacked rows (FP8 and BF16 scratch, two layers with different global scales); the CPU and foreign-recipe
guards; a CUDA-graph capture of the kernel-level decode gather and of the backend's `forward_decode` (KV write,
gather, attention), replayed with every input changed in place. It also prints, for information, the decode-output
error of an FP8 cache and of nvfp4_qsa against a BF16 cache, the NVFP4 round-trip error, and the gather speed at
19/28/34 lanes.
