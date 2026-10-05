# kfuse: fused / de-wasted decode kernels for Daniel's fork (3/4-Oct-2026, daniel-draft kernels)

Patch set for `make_bench_notebook.py --kv4 --patch-set ...\kfast --patch-set ...\kvshrink\draftkv4
--patch-set D:\codex-work\daniel-draft\kernels\kfuse`. `orig/` = his wheel bytes; `patched/` = ours. The two QSA
files supersede qsakv4's copies and carry all of qsakv4's (and through it qsaring's) changes. Built by
`dev/make_kfuse_gdn.py` and `dev/make_kfuse_qsa.py` from his wheel / qsakv4's files + `dev/*.py`.

| file | change | switch |
|---|---|---|
| `sglang/srt/layers/attention/hybrid_linear_attn_backend.py` | RecoverSSM commit (after every verify, 36 GDN layers): the boundary pass (mamba radix tracking) and graph pad rows point rows that need no output at the reserved padding slot 0, yet each such CTA read and wrote a full 48x128x128 state. The recovery launches now use a copy of flashinfer's `gdn_decode_bf16_state` (source loaded at runtime, one guard added to `gdn_wide_vec_kernel`) that skips CTAs whose output slot is 0. | `SGLANG_KFUSE_GDN_SKIP=0` |
| `sglang/srt/layers/attention/qsa/sparse_attn.py` | + `qwen_sparse_nvfp4_fused_decode_triton`: QSA sparse decode straight from nvfp4_qsa KV: unpack in registers (qsakv4's exact arithmetic incl. the FP8 rounding), XQA's math (bf16 QK, bf16 P, fp32 accumulation), deterministic split combine | |
| `sglang/srt/layers/attention/qwen_sparse_attn_backend.py` | `_forward_trtllm_sparse` uses it for nvfp4_qsa pools instead of gather-into-FP8-scratch + XQA | `SGLANG_KFUSE_QSA=0` |
| `sglang/srt/model_executor/forward_batch_info.py` | `compute_spec_mrope_positions`: on mixed (image) batches the M-RoPE deltas were uploaded with a pageable `.to(device)` that blocked the host until the GPU stream drained (~1 ms before every verify, ~30 ms before every draft_extend), serializing the 1.1 ms verify graph launch behind the draft. Now a fresh pinned tensor per call + `non_blocking=True` (same values; the caching host allocator holds the block until the copy ran; nothing reads the deltas on the host). | `SGLANG_KFUSE_ASYNC_MROPE=0` (`SGLANG_KFUSE_MROPE_CHECK=1`: diagnostic bit-compare, adds a sync every 64 uploads) |

Slot 0 is never a request slot (MambaSlotAllocator hands out 1..size), so skipping it changes nothing anyone reads.

## Micro-benchmarks (RTX PRO 6000, his venv, cold data, CUDA graphs)

| item | before | after | check |
|---|---|---|---|
| GDN commit, 36 layers, 13 rows, 1 row crossing a track boundary | 1.67 ms | 1.22 ms | every non-zero slot bit-identical; slot 0 no longer written |
| same, no row crossing / all 13 crossing | 1.62 / 1.99 ms | 1.08 / 2.00 ms | |
| QSA attention per layer, 52 verify rows (13 x 4) | 163 us | 85 us | <= 1 bf16 ulp vs gather+XQA; closer to an fp32 reference; deterministic; graph replay ok |
| QSA attention per layer, 13 draft rows | 51 us | 35 us | same |

Runs: daniel-bench-kgdn2-1003 (GDN), daniel-bench-kqsa2-1003 (QSA), and in the patched install
daniel-bench-kfuse-1004 (pre-script `check_kfuse.py`: PASS).

Dropped: HyperConnection mix fused into two kernels (skinny down GEMM + one up/sigmoid/mean kernel): 23.7 us vs
19.2 us for his compiled chain at 52 rows (daniel-bench-khc-1003), so not shipped.

## Server A/B results

- kfuse (GDN skip + QSA fused) vs kfast+draftkv4 control (daniel-bench-kfuse-1004 vs kfuctl-1004, 13 lanes, --kv4):
  GPU kernel time per iteration 39.3 -> 36.7-37.3 ms, wall per iteration 39.2-39.5 -> 38.2-38.6 ms, tok/s at 20/40 min
  806-809 -> 836-837. Greedy check: cross-run divergence like two identical controls.
- mrope fix (daniel-bench-kmrope-1004 vs kmrctl-1004: same kfuse build, SGLANG_KFUSE_ASYNC_MROPE=1 vs 0): tok/s at
  20/40 min 842/845 -> 873/869 (+3%); compute_spec_mrope_positions 1.17 -> 0.16 ms CPU; acceptance unchanged.
  Exactness in one server on real mixed image batches (daniel-bench-kmrchk-1004, SGLANG_KFUSE_MROPE_CHECK=1: every
  async upload kept with its host source, compared bit for bit every 64 uploads): 40,448 uploads, 0 mismatches.
- With the fix, the GPU no longer waits for the host (daniel-bench-kidle-1004, profiles at 10 and 20 min): GPU idle
  between draft starts median 0.00 ms per iteration (0.86 ms counted from run_batch to run_batch, incl. scheduling
  stalls; 2.6 / 3.6 ms before), the CPU launches each graph ~30-60 ms before the GPU reaches it (the 1.1 ms verify
  graph launch is hidden), the host now waits ~27 ms per iteration in cudaEventSynchronize: the step is GPU-bound.
  Wall per iteration 33.3-35.2 ms median (39.2-39.5 before kfuse + fix). The remaining eager prep and QSA metadata
  launches cost < 0.06 ms per iteration combined, so they were not changed.

## Harness caveat

Pre-scripts that run FlashInfer's XQA decode (bench_qsa.py, check_kfuse.py) leave the container without GPU access
after they exit ("Failed to initialize NVML: Unknown Error"; daniel-bench-kgpu-1004 isolates it: GPU fine after
bench_gdn.py, gone after bench_qsa.py). The server then fails its first attempt and the runner's second attempt (new
container) works. Serving with kfuse is not affected (kfuse-1004 served 45 min, and its kv4_test subprocess ran XQA
fine while the server held the GPU). Don't put XQA-based checks before a server start.

## Combined A/B (4-Oct-2026, one wave, 13 lanes, 45 min)

`--kv4` alone (daniel-bench-kallctl-1004) vs `--kv4` + kfast + draftkv4 + kfuse with async mrope
(daniel-bench-kall-1004): tok/s at 20 / 40 min 797 / 802 -> 857 / 871 (+7.5% / +8.6%); wall per iteration
(scheduler timeline, median) 40.5 / 39.4 -> 34.1 / 35.2 ms; GPU idle per iteration 3.7 / 3.8 -> 0.8 / 0.4 ms;
acceptance 2.79-2.82 both. Greedy check: control vs test common prefix 14-30 tokens, mean |dlogprob| 0.051-0.065;
each server vs itself 28-40 tokens, 0.031-0.032 (at the size of the run-to-run noise seen between identical builds).

Builder flags (test arm):
`make_bench_notebook.py --base-early D:/codex-work/daniel-base-20261001/variants/subbuild/ctl/early.py --slots 13
--gate 13 --kv4 --memfrac 0.96 --window 131072 --minutes 45 --patch-set D:/codex-work/daniel-draft/kernels/kfast
--patch-set D:/codex-work/daniel-draft/kvshrink/draftkv4 --patch-set D:/codex-work/daniel-draft/kernels/kfuse`
