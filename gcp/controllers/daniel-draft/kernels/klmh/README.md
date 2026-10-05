# klmh: target lm_head through ZipServ on a losslessly compressed copy (5-Oct-2026, Kernel optimizations thread)

One file: `sglang/srt/layers/logits_processor.py` (his wheel). Built by build_klmh.py (embeds our C shim
../zslm/zslm.cu + ZipServ's sources, Apache-2.0, github.com/HPMLL/ZipServ_ASPLOS26, as a base64 tgz).
Switch: SGLANG_KLMH=0. SGLANG_KLMH_MIN_FREE_GB (default 2.0): free memory required after the allocation.

## What it does
The target lm_head (248,320 x 2,560 bf16 = 1.27 GB) is read once per decode step at ~1.43 TB/s (890 us). ZipServ's
TCA-TBE format stores it in 0.84 GB without loss; ZipGEMM decodes on the fly. At the first eligible eager call (2..64
rows, not capturing: the graph warm-up) the module builds libzslm.so with sglang's nvcc (~10 s, cached in
$SGLANG_KLMH_DIR or the temp dir), compresses on the host (~13 s), uploads, and self-checks 2 / 8 / 40 rows bitwise
against torch.matmul (any mismatch: off). 1-row calls (a lone prefill's last token) stay on torch.matmul: cuBLAS
uses a GEMV there and ZipGEMM differs from it on 0.12% of logits by one bf16 step. The dense weight is kept.

## Evidence
- zslm-1005 / klmh-1005 pre-checks (served weight): bitwise equal to torch.matmul at 2..64 rows; 1 and 65 rows fall
  back; CUDA-graph replay equal; 899 -> 724 us at 40 rows, 852 -> 664 at 10.
- In-server (daniel-bench-klmh-1005 vs daniel-bench-kctl-1005): lm_head 889 -> 701 us per decode iteration
  (-0.19 ms), serve.log "klmh: on, ... 0.84 GB (host 12.7 s), self-check bitwise ..., 13.5 s total", no errors.
  Greedy vs control 0.033 / 0.041 (floor 0.051 / 0.058).
- Cost: +0.84 GB GPU memory (taken from the ~3.8 GB the 0.96 mem fraction leaves; KV pool unchanged) and ~25 s
  once at startup (build + compression).
