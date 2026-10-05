# khc: HyperConnection combine / mix (4-Oct-2026, Kernel optimizations thread)

One file: `sglang/srt/layers/hyperconnection.py` (his 0.5.19+gd00d88efc8d6 wheel, sha256 0e5431d5eee3).

| change | status | switch |
|---|---|---|
| split HC combine (his `hc_combine_gate` + `hc_combine_apply`, bit-identical by construction) used up to 64 rows (his cap 32), shared fp32 partials sized for 64 rows on first use (CUDA-graph pointer stays stable) | **READY**, lossless | `SGLANG_KHC_SPLIT_MAX_ROWS=32` restores his cap |
| fused HC low-rank mix for 17..64 rows (down split-K partials -> fixed-order reduce + silu -> up4 (t loaded once for all 4 branches) + sigmoid + mean; no atomics) | **READY, near-exact (not bitwise)**: -0.34 ms/step in-server, greedy inside cross-server noise. **OFF by default** | `SGLANG_KHC_MIX_MAX_ROWS=64` turns it on |

## Evidence
- kfast's 3-Oct bench said the split combine gains nothing above 32 rows (4.13 vs 4.26 us at 52 rows), but timed
  L2-warm buffers. Cold (check_khc.py, daniel-bench-khc-1004 pre-script): 40 rows single 6.85 -> split 5.58 us,
  bitwise equal at 10..64 rows, dispatch takes the split path up to 64 rows, one 64-row partials buffer.
- In-server (daniel-bench-khc-1004 vs control daniel-bench-kprof2-1004, 10 lanes, W4, 8-bit route, kfast + kfuse8 + kq8):
  hc_combine 98 x 6.9 us = 0.68 ms/step -> gate 0.30 + apply 0.19 = 0.49 ms/step (**-0.2 ms GPU per step**).
  tok/s minutes 0-25: 818 vs 807 (control), accept 2.97 vs 2.99 (one pair: inside run-to-run noise). serve.log clean.
- Fused mix (check_khcmix.py, daniel-bench-khcmix3-1004): bitwise equal to the compiled chain at 17..64 rows on real
  weights (hc=4), ~99% at hc=5, deterministic, graph-replay safe; cold time 20.0 vs 19.4 us at 40 rows (first tactic).
  Tactic sweep (check_khcmix_tune.py, daniel-bench-khctune-1004): our down kernel beats cuBLAS (7.3 vs 9.0 us) but our
  up kernel loses (11.0 vs 7.0 + 1.6 us), whole mix 19.3-19.6 us = parity. Next: rebuild the up kernel to load t once
  for all hc groups (est. ~8 us -> ~16 us per boundary, ~0.3 ms/step).

- up4 rebuild (5-Oct, patched sha256 808b34296f57; check_khcmix.py on daniel-bench-khcmixs-1004): cold 20.0 -> 16.2 us at
  40 rows (-3.6 us/boundary, 17..64 rows all -3.6 to -4.3 us). NOT bitwise: 99.93-99.98% of elements equal the
  compiled chain (split-K summation order differs), error vs fp32 identical to the compiled chain's (0.0022-0.0029),
  deterministic, graph-replay safe.
- In-server (daniel-bench-khcmixs-1004, `SGLANG_KHC_MIX_MAX_ROWS=64`, vs daniel-bench-khc-1004, same stack): mix kernels
  per boundary 7.0 + 6.8 (cuBLAS down / up) + 2.4 (splitK reduce) + 1.5 + 0.9 (inductor) = 18.6 us -> 6.8 + 7.3 + 1.15
  = 15.25 us; 100 boundaries per step = **-0.34 ms GPU per step** (both profiles). serve.log clean.
- Greedy (10 prompts x 384 tokens, greedy_compare.py vs daniel-bench-kq8tb-1004): mean |dlogprob| 0.068 / 0.056
  (pass 1 / 2), max 0.49 / 0.60. Two IDENTICAL control servers (kfctl vs kfctl2-1003) give 0.051 / 0.058, max
  0.62 / 0.48, and bit-identical kq8 (kq8ctlb vs kq8tb) 0.063 / 0.052, max 0.73 / 0.45: inside cross-server noise.

## Use
    make_bench_notebook.py ... --patch-set D:/codex-work/daniel-draft/kernels/kfast --patch-set .../kfuse8 \
        --patch-set .../kq8 --patch-set D:/codex-work/daniel-draft/kernels/khc
Checks: check_khc.py (combine), check_khcmix.py (+ check_khcmix_tune.py with check_khcmix.py as --pre-file).
