# zipserv/: lossless BF16 weight compression check + decode kernel inventory (4-Oct-2026)

Kernel optimizations thread (Son 4-Oct: "start with the profile run and the ZipServ histogram", then "do the ZipServ
speed test too"). Stack measured: Daniel's 8-bit shipping route (sbt06tf + RS + hicache 32, 10 slots, kfast + kfuse8 + kq8).

## Verdict
ZipServ (ASPLOS '26, TCA-TBE / ZipGEMM, github.com/HPMLL/ZipServ_ASPLOS26): **not worth integrating now.**
- Gate 1 PASSED: 96.6% of the BF16 decode weights fall in each matrix's best 7-consecutive-exponent window
  (11.27 bits/weight, ~30% fewer bytes; big matrices 96.9%, drafter 96.7%). Run daniel-bench-kprof-1004.
- Gate 2 FAILED except for the output layers (run daniel-bench-kzip-1004, real weights, CUDA graphs over cold copies,
  same method as ../bench/bench_dense.py; our cuBLAS numbers reproduce its run kgemm-1003 within 1-3%):
  ZipGEMM decodes at only ~1.0-1.25 TB/s of compressed bytes on sm_120, so it ties kfast on the big projections
  (in_proj 58 vs 59 us, only with split-K, whose BF16 partial sums add ~0.4-0.8% max rel error) and loses on
  every small shape (shared expert, router, HC mix 2-3x slower). Wins: lm_head 890 -> 722 us and the drafter's hot
  64k head 236 -> 211 us (x3), both BIT-IDENTICAL to cuBLAS at split 1: ~0.24 ms per step (~0.8%).
- ZipServ bugs seen: illegal memory access when Split_K exceeds what K tiles evenly (K=640 split 6, K=320 split 4,
  M=1280/512 split 12); launcher sizes shared memory with a function-static from the first call (one matrix per
  process is safe).

## Kernel inventory (pure decode, trace daniel-bench-kq8tb-1004 m30, 10 lanes, width 4, ~30.8 ms/step)
- Experts (Marlin) 14.7 ms: at the card's DRAM limit, no lossless room.
- HyperConnection chain ~2.9 ms: 7 kernels per boundary (combine 6.8 + norm 1.7 + down GEMM 7.0 + splitK reduce 2.4
  + silu 0.9 + up GEMM 6.8 + sigmoid 1.6 us) x ~100 boundaries; floor from bytes (13.1 MB per boundary) ~0.9 ms.
- QSA indexer scoring (mqa.py tilelang decode kernel, "kernel_kernel") 1.0 ms: grid = verify rows, so the 4 verify
  tokens of a sequence each re-read that sequence's compressed index keys (78 us per layer vs ~40 floor).
- GPU fully idle ~0.9 ms per step; launch gaps inside graphs are only ~0.3-0.6 us each.
- Target lm_head 0.89 ms (92% of DRAM speed), drafter hot head ~0.7 ms per step (3 calls).

## Files
- exp_hist.py: pre-script, per-tensor BF16 exponent histograms -> working/zipserv_hist.json
- zs_bench.cu, zs_run.py, zipserv_src.tgz: ZipServ build (venv nvcc 13.0, sm_120) + harness, pre-only run
- inventory.py: per-iteration kernel inventory of a torch-profiler trace (streams, gaps, size buckets, top kernels)
- watch_kprof.py: run watcher; deletes the VM only after "finish (...)" AND status TERMINATED
- Infra finding (runner, fixed by Main 4-Oct): snapd's systemd reload ~5 min after boot cut the container's GPU
  access ("CUDA-capable device(s) is/are busy or unavailable" / NVML); runner now passes --device for /dev/nvidia*.
