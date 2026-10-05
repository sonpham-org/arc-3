# kfast: faster small-batch dense kernels for Daniel's fork (3-Oct-2026, daniel-draft kernels)

Patch set for `make_bench_notebook.py --patch-set D:\codex-work\daniel-draft\kernels\kfast` (orig/ = his bytes,
sha-checked at install; patched/ = ours). No math changes: the same products and sums, computed by a different
kernel; outputs equal cuBLAS's bit for bit on the unsplit shapes and differ at bf16 rounding on the split ones
(closer to an fp32 reference than cuBLAS). Applies on top of qsaring + qsakv4 (`--kv4`); no file overlap.

| file | change | why |
|---|---|---|
| `sglang/kernels/ops/gemm/sm120_lowm_bf16_gemm.py` | adds a deterministic split-K "skinny" Triton GEMM, used for 9 <= m <= 64 rows on six TP1 shapes (GDN in_proj / out_proj, QSA qkv / o_proj, shared expert gate_up / down, router gate); his tuned path for m <= 8 and every other shape unchanged | a 13-lane verify step is m = 52 rows, which his fork sends to cuBLAS's sm80 kernels (his low-M kernel stops at m = 32) |
| `sglang/srt/layers/moe/fused_moe_triton/fused_marlin_moe.py` | unit-scale top-k sum through his JIT `moe_topk_sum` instead of `sgl_kernel.moe_sum_reduce` | same fp32 sequential sum (bitwise equal, checked), one vectorized pass |

Switches (server env): `SGLANG_KFAST_SKINNY=0`, `SGLANG_KFAST_TOPK_SUM=0`.

## Measured (RTX PRO 6000 Blackwell Server, his venv, cold weights, CUDA graphs)

DRAM read ceiling: 1,537 GB/s (Triton streaming read; torch sum 1,525). us per call, old -> new
(`check_kfast.py`, run daniel-bench-kfastchk-1003):

| shape (n x k) | m=13 (draft) | m=52 (13-lane verify) | calls/step |
|---|---|---|---|
| GDN in_proj 16480x2560 | 60.0 -> 57.2 | 61.5 -> 59.2 (1,425 GB/s) | 36 |
| QSA qkv 13312x2560 | 50.4 -> 47.1 | 50.7 -> 49.4 | 12 |
| out / o_proj 2560x6144 | 24.9 -> 24.1 | 26.3 -> 25.5 | 48 |
| shared gate_up 1280x2560 | 13.3 -> 7.5 | 10.2 -> 8.6 | 48 |
| shared down 2560x640 | 4.1 -> 4.1 | 6.0 -> 4.5 | 48 |
| router gate 512x2560 | 8.7 -> 5.2 | 6.7 -> 6.5 | 48 |
| top-k sum [52,10,2560] | 2.7 -> 1.7 | 5.7 -> 3.8 | 49 |

Expected saving: ~0.4 ms per decode iteration at 13 lanes (~1%). Checks all PASS: error vs fp32 reference,
determinism, CUDA-graph replay with fresh inputs (split-K counters reset), two shapes concurrently on two streams.

## In the server (13 lanes, --kv4, 131k window, us-central1-b, 3-Oct)

Profiler traces, median per decode iteration (draft + verify + draft_extend), dense GEMM kernels (cuBLAS + low-M +
skinny): control daniel-bench-kfctl-1003 m20 9.76 ms -> kfast daniel-bench-kfast2-1003 m10 9.12 / m16 9.16 ms
(about -0.6 ms); top-k sum 0.18 -> 0.14 ms. Whole iteration ~38-39 ms, moved more by routing / context (Marlin
16.4 vs 17.4 ms at those moments) than by this patch.

tok/s at 20 min: controls 796 (kfctl), 814 (k13ctl), 830 (ksctl); kfast 816, kfast2 812. At 40 min: kfctl 796,
kfast 814. The patch's ~1.6% GPU-time saving is inside the ~4% spread between identical control runs.

Greedy check (`../add_greedy_cell.py`, `../greedy_compare.py`; 13 prompts x 384 tokens, all in flight): two
identical control servers (kfctl vs kfctl2) agree for 12-18 tokens on average, mean |d logprob| 0.051-0.058 on the
common prefix; control vs kfast: 13-20 tokens, 0.059-0.081. Divergences are at near-tie tokens in both. Not
distinguishable from the server's own run-to-run nondeterminism (Marlin atomics, batch timing).

Tried and dropped: his split HyperConnection combine above 32 rows (4.13 -> 4.26 us at m=52: no gain); his fused
persistent HyperConnection mix at 64 rows (18.4 vs 19.0 us compiled chain); Marlin MoE knobs (below).

Full sweeps: `../bench/bench_dense.py` (run daniel-bench-kgemm-1003), `../bench/bench_moe.py` (daniel-bench-kmoe-1003).


4-Oct follow-up (not in this set, unchecked on GPU): a 65-128-row table for in_proj / qkv only (`../analysis/kfast128_candidate_sm120_lowm_bf16_gemm.py`; microbench daniel-bench-kd128-1004: 78 rows in_proj 66.3 -> 63.5 us, qkv 61.4 -> 54.9 us, about -0.2 ms per width-6 step).
