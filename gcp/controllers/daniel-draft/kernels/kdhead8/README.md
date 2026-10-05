# kdhead8: the drafter's hot-vocab lm_head in 8 bits (4-Oct-2026, daniel-draft kernels)

**Draft-only, not bit-lossless for the drafter:** it changes the proposal q a little, never the target's p.
Rejection sampling keeps the output distribution exact; the cost, if any, is acceptance length.

Patch set for `make_bench_notebook.py --rs --patch-set D:\codex-work\daniel-draft\kernels\kdhead8 --env
SGLANG_KDHEAD8=int8`. Two files:
- `sglang/srt/speculative/eagle_worker_v2.py` **supersedes the rs set's copy** (orig/ = his bytes; patched/ = rs's
  file + kdhead8), so it needs `--rs`. In `init_lm_head`, after the hot-vocab head is selected (a 65536 x 2560 bf16
  copy of the target's rows), `SGLANG_KDHEAD8=int8|fp8` re-stores it as 8-bit rows with one fp32 scale per row.
  Default `0` = off (his bf16 head, byte-for-byte his path).
- `sglang/kernels/ops/gemm/sm120_online_fp8.py` (his, orig sha-checked against the wheel): his logits processor
  already sends any lm_head whose weight carries a rowwise scale to `rowwise_fp8_lm_head_logits`; that function now
  sends a kdhead8-tagged head to a new Triton kernel (8-bit rows -> bf16 exactly, fp32 accumulate, row scale once) for
  up to 256 rows, so draft extend (10 x width rows) does not fall into his dequantize-everything path (> 32 rows).
  Untagged weights (his own SGLANG_SM120_ONLINE_MXFP8 path) are unchanged. int8 = symmetric per row, absmax / 127.

## Checked (runs daniel-bench-kchk2-1004 / kchk3-1004, `check_kdhead8.py`, real target lm_head rows at the ARC hot ids)

Kernel error vs fp32 math on the same 8-bit weights: bf16 output rounding only (rel 0.0039).

Draft-q quality vs the bf16 head (T 0.6, top-k 20, top-p 0.95; hidden states pointed at 1-4 vocab rows, three
confidence levels; "accept loss" = 1 - sum(min(q_bf16, q_8bit)), what a perfect draft would lose per token):

| format | logit error rms | top-1 agree | accept loss mean | accept loss p99 |
|---|---|---|---|---|
| int8 | 0.010-0.026 | 99.2-99.6% | 0.34-0.49% | 3.5-5.7% |
| fp8 e4m3 | 0.025-0.069 | 98.8-99.6% | 0.82-1.29% | 5.1-8.4% |

Time per call (CUDA graph, two head copies alternating so weights come from DRAM):

| rows | cuBLAS bf16 (served) | kdhead8 int8 |
|---|---|---|
| 10 (draft step) | 228 us | 116 us |
| 13 | 230 | 117 |
| 40 (draft extend, W4) | 238 | 132 |
| 80 (W8) | 247 | 188 |
| 160 (W16) | 273 | 264 |

Expected: -0.11 ms per draft step (= per extra position) and -0.06 to -0.11 ms per iteration in draft extend. Frees
168 MB. Bench A/B (accept length is the number to watch): see the session report.
