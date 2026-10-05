# qsakv4h: HiCache host tier for the 4-bit QSA KV cache (nvfp4_qsa), on Daniel Franzen's SGLang fork

Adds `--enable-hierarchical-cache` to `--kv-cache-dtype nvfp4_qsa` (qsakv4) on his "Pennyroyal" sglang
0.5.19+gd00d88efc8d6 (wheel `D:\codex-work\daniel-draft\wheel\sglang.whl`). 3-Oct-2026.

**Status: written, compile-checked, and run through a CPU emulation of every transfer path (below). Nothing
here has run on a GPU yet.** Run `test_hicache_nvfp4.py` in his venv on the RTX PRO 6000 before any benchmark.

## Why

Without a host tier, 16 lanes x 131k context on 4-bit KV fills the 1.15M-token device pool and the prefix
hit rate falls from 95% to 5%. With FP8 KV his host tier (`--hicache-size 32`, write-through, kernel io,
page_first) carries 11 actors on 10 slots. qsakv4 refused HiCache because the host pool had no room for the
FP4 block scales: a restored row would have been read with stale scales.

## Install

`patched/` holds 4 files, `orig/` the exact bytes of the same 4 files from his wheel (LF, UTF-8).
`server_args.py` and `kv_cache_configurator.py` are **qsakv4's patched versions plus these changes**, so they
replace qsakv4's copies; qsakv4's other six files and qsaring's four are still needed.

```python
KV4H_FILES = (
    "sglang/srt/mem_cache/pool_host/mha.py",
    "sglang/srt/mem_cache/hybrid_cache/hybrid_pool_assembler.py",
    "sglang/srt/mem_cache/kv_cache_configurator.py",   # supersedes qsakv4's copy
    "sglang/srt/server_args.py",                       # supersedes qsakv4's copy
)
QSAKV4_FILES_STILL_NEEDED = (                          # from ../qsakv4/patched/
    "sglang/srt/layers/attention/qsa/sparse_attn.py",
    "sglang/srt/layers/attention/qwen_sparse_attn_backend.py",
    "sglang/srt/layers/attention/flashinfer_backend.py",
    "sglang/srt/layers/quantization/fp4_kv_cache_quant_method.py",
    "sglang/srt/mem_cache/kv_cache_dtype.py",
    "sglang/srt/mem_cache/memory_pool.py",
)
QSARING_FILES_STILL_NEEDED = (                         # from ../qsaring/patched/
    "sglang/srt/mem_cache/qsa_kv_pool.py",
    "sglang/srt/layers/attention/qsa/metadata.py",
    "sglang/srt/layers/attention/qsa/graph_metadata.py",
    "sglang/srt/layers/attention/qsa/qsa_indexer.py",
)
```

For `make_bench_notebook.py` (one file per set): `add_set("qsaring", QSARING_FILES_STILL_NEEDED)`,
`add_set("qsakv4", QSAKV4_FILES_STILL_NEEDED)`, `add_set("qsakv4h", KV4H_FILES)`.

## Server arguments

His FP8 host-tier command with one change:

| flag | value |
|---|---|
| `--kv-cache-dtype` | `nvfp4_qsa` (was `fp8_e4m3`) |
| `--speculative-draft-kv-cache-dtype` | `fp8_e4m3` (keep; see qsakv4) |
| `--enable-hierarchical-cache --hicache-size 32 --hicache-write-policy write_through --hicache-io-backend kernel --hicache-mem-layout page_first` | unchanged |

Per token the KV host tier now costs 7,936 bytes instead of 13,312 (12 QSA layers at 576 B + the FP8 draft
layer at 1,024 B, K and V), so the same `--hicache-size` holds about 1.6x the tokens (the QSA index-key sidecar
and the Mamba share are unchanged). `--hicache-io-backend direct` (page_first_direct) also works.

Refused at startup with nvfp4_qsa (new): `--hicache-storage-backend` (any L3, so also `--hicache-host-memory-mode
buffer_only`), `--hicache-mem-layout` other than page_first / page_first_direct, `--hicache-io-backend
kernel_ascend`. Still refused (qsakv4): LMCache, FlexKV, PD disaggregation, unified memory, page-major KV.

## How the host pool carries the scales

`get_mha_host_pool_cls` returns the new `NVFP4QSAMHATokenToKVPoolHost` (pool_host/mha.py) for a device pool
whose quant method is `nvfp4_qsa`; every other pool gets the classes it got before. Rows of different widths
cannot share one host row (the transfer kernels take one item size per call), so each kind of row gets its own
host K/V pair and moves with the existing kernels at its own item size, for the same slot lists:

| kind | device buffer per layer | host layout (page_first) | B/token, K+V, production | write-back (D2H) | load (H2D, per layer) |
|---|---|---|---|---|---|
| packed E2M1 rows | `k_buffer[l]` [slots, 2, 128] u8 | [tokens, 12, 2, 128] | 6,144 | the FP8 pool's staged JIT write-back (relayout + batched copy) | JIT one-layer copy, 256-B token rows |
| FP8 block scales | `k_scale_buffer[l]` [slots, 2, 16] u8 | [pages, 12, 64, 2, 16] | 768 | `transfer_kv_all_layer_lf_pf`, 2-KB page items | JIT one-layer copy, 2-KB page elements |
| MTP draft rows (FP8) | draft `k_buffer[0]` [slots, 2, 256] u8 | [tokens, 1, 2, 256] | 1,024 | `transfer_kv_all_layer_lf_pf`, 512-B rows | JIT one-layer copy, 512-B rows (as FP8 today) |

- **Scales move per page.** The JIT copy works in 128-byte units, so a 32-byte scale row cannot be one; the
  sgl_kernel fallback would pay one PCIe round trip per 32 bytes. A page of scales (64 x 32 = 2 KB) is one JIT
  element. HiCache always moves whole pages (the paged allocator, the staged write-back and the QSA compressed
  sidecar already rely on it), so the page ids are `indices[::64] // 64` of the same lists.
- **Scale and draft write-back use one `transfer_kv_all_layer_lf_pf` launch each** instead of the staged kernel:
  their pages (24 KB, 32 KB) are below the staged kernel's 128-KB batched-copy threshold, where it falls back to
  two `cudaMemcpyAsync` per page on the scheduler thread. That kernel reads host indices on the device; the
  controller hands this pool CPU host indices (for the staged rows, `can_use_write_back_jit`), so the pool copies
  them to the GPU once per write-back, on the D2H stream, ordered before the kernels (8 bytes per token, no device
  sync; the same copy `move_indices` makes for the other pools).
- **Draft:** host layer `12 + d`, exactly where the FP8 pool packs it, so the controller's packed-draft load
  (`_l2_load_transfers`, `is_draft=True`) and the layer mappers are unchanged. An FP8/BF16 draft is its own kind;
  a draft that inherited `nvfp4_qsa` (draft flag omitted) is packed into the rows + scales kinds.
- **Fallbacks:** if a JIT module does not build, loads use `transfer_kv_per_layer_pf_lf` and the row write-back
  uses `transfer_kv_all_layer_lf_pf` (the FP8 pool's own fallbacks). With `--hicache-io-backend direct`
  (page_first_direct) every kind is per page and moves with `transfer_kv_all_layer_direct_lf_pf` /
  `transfer_kv_per_layer_direct_pf_lf`.
- **Ordering:** a layer's rows and scales are loaded before the controller records that layer's event, and the
  QSA backend reads both through `get_raw_kv_buffer`, which waits on it; a write-back's rows, scales and draft
  are all on the D2H stream before its finish event. Nothing is captured in CUDA graphs; no new host sync.
- The per-layer FP32 global scales stay in the quant method on the device; nothing to copy.

## Per-file changes

| file | change |
|---|---|
| `mem_cache/pool_host/mha.py` | New `is_nvfp4_qsa_kv_pool`, `_HostKVSegment` and `NVFP4QSAMHATokenToKVPoolHost(MHATokenToKVPoolHost)`: per-kind host buffers (allocated, pinned and unregistered like the FP8 pool's), size per token counting rows + scales + draft rows, `load_to_device_per_layer` / `backup_from_device_all_layer` for kernel io + page_first and direct io + page_first_direct, staging buffers for the rows only. Raises a clear error for layer_first / page_head layouts, other io backends, other quantized draft recipes, mixed draft formats, non slot-major (HND) pools, and every L3 storage hook (`get_page_buffer_meta`, `get_data_page`, ...). `get_mha_host_pool_cls` picks it for nvfp4_qsa pools only; the FP8 / BF16 / asymmetric classes are untouched. |
| `mem_cache/hybrid_cache/hybrid_pool_assembler.py` | `build_hybrid_mamba_stack` splits `--hicache-size` between Mamba and KV + QSA keys with a per-token KV price that assumed full rows for every layer (13,312 B); for nvfp4_qsa that over-sized the host pools by about 4% of the budget. Now `_kv_host_bytes_per_token` asks the nvfp4_qsa pool class for its real per-token bytes; for every other pool it returns the old formula unchanged. |
| `mem_cache/kv_cache_configurator.py` | (qsakv4's version) the nvfp4_qsa refusal of `--enable-hierarchical-cache` removed. |
| `server_args.py` | (qsakv4's version) `--enable-hierarchical-cache` removed from the nvfp4_qsa refusal list; new refusal, with HiCache on, of `--hicache-storage-backend`, layouts other than page_first / page_first_direct and io backends other than kernel / direct. |

## Not ported, or not sure

- **No GPU run yet.** The CPU emulation checks this class's layouts, index and layer bookkeeping and the byte
  offsets each kernel computes, against transcriptions of his `transfer.cu` / `hicache.cuh` / `relayout.cuh` /
  `staged_write_back.cuh`; it does not run the kernels, torch's view rules (numpy views stand in) or the
  controller. `test_hicache_nvfp4.py` covers those on the GPU.
- The first start compiles three more JIT modules (one-layer copy for 256-B and 2-KB elements, staged write-back
  for 256 B; the 512-B one exists for FP8). If one fails to build it logs a warning and that kind falls back to
  sgl_kernel (correct, slower).
- **Speed is not measured.** Expect write-back no slower than FP8 (the bulk is the same staged kernel at half the
  bytes; two extra small kernels) and loads faster (about 60% of the bytes, scales in 2-KB pieces).
  `python test_hicache_nvfp4.py --bench` times 1,024 pages, nvfp4_qsa against FP8, with production layer counts.
- **L3 storage is not ported** (refused): each page would need three more objects (rows, scales, draft) in the
  storage backends' page/key schemes.
- layer_first and page_head are refused; they are unreachable for this model anyway (the Mamba host pool accepts
  only page_first / page_first_direct).
- The tokenwise QSA variant (`QwenDSATokenToKVPool`): his HiCache stack does not back up its per-token index keys
  (`dsa_index_k_buffer_pool`), with or without this patch. Not touched; HiCache with that variant is untested.
- A draft that inherits `nvfp4_qsa` is handled but only tested here (emulation + GPU test), never served.

## Test

`test_hicache_nvfp4.py` runs in his venv on the GPU with qsaring + qsakv4 + qsakv4h installed and no server
running: `python test_hicache_nvfp4.py [--bench]`. It prints one JSON line and exits 1 on any failure. It builds
the attention side of `build_hybrid_mamba_stack` (no Mamba pool): the real `QSATokenToKVPool` with nvfp4_qsa
(3 QSA layers, distinct global scales) and its MTP draft pool, the host pool `get_mha_host_pool_cls` picks, the
QSA compressed sidecar, a `HostPoolGroup` with the server's layer mappings (packed draft included) and the real
`HybridCacheController`. Per case it writes random K/V through the real quantize-and-store path, backs 80
shuffled device pages up with `controller.write()` into shuffled host pages (two staging chunks), checks every
host byte (rows, scales, draft rows where they belong, all else untouched), clobbers the device, loads into 80
other pages with `controller.load()` + `start_loading()`, and requires byte equality of packed rows, block
scales, draft rows and QSA compressed keys, with every other device row untouched. Cases: kernel + page_first
(JIT, and forced sgl_kernel fallbacks), direct + page_first_direct; draft FP8, BF16, inherited nvfp4_qsa, none.
Also: size accounting (what `--hicache-size` is split with == what is allocated), FP8 pools still getting
`MHATokenToKVPoolHost` and the old formula, and the refusals.

## CPU emulation

`cpu_emulation/` (numpy only; `python run_emu.py`, then `python mutate.py`) loads his unchanged
`pool_host/base.py` and `common.py` and the patched `mha.py` over a minimal numpy stand-in for torch, with the
kernels emulated byte for byte and every copy bounds-checked against its allocation. All 12 path combinations
(kernel/page_first with JIT and with fallbacks, direct/page_first_direct; draft FP8, BF16, nvfp4_qsa, none)
round-trip exactly with the host bytes where the layout says, and the refusals hold. `mutate.py` plants five
bugs (swapped page ids, wrong item size, dropped scale load, draft layer off by one, staging layer count); each
makes cases fail. Re-run both after editing `mha.py`.
