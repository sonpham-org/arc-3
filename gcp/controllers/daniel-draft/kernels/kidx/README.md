# kidx: QSA indexer scoring per request in target verify (4-Oct-2026, Kernel optimizations thread)

Files (his 0.5.19+gd00d88efc8d6 wheel): `sglang/srt/layers/attention/qsa/mqa.py` (sha256 84a52bb2cf61),
`sglang/srt/layers/attention/qsa/qsa_indexer.py` (c35fcccd8571). Composes with kfast + kfuse8 + kq8 + khc.
**Conflicts with qsaring** (also patches qsa_indexer.py): a W>4 build needs a merged copy.

## What it does
His decode MQA kernel (`_tilelang_qsa_mqa_decode_kernel`, "kernel_kernel" in traces, grid [rows, pages]) gives every
query row its own CTA, so in target verify each request's 4 rows each re-read that request's compressed index keys.
Verify rows of one request are consecutive and share the request's pages (`_graph_speculative_layout`,
`_speculative_row_to_request`). `_tilelang_qsa_mqa_decode_grouped_kernel` (grid [rows / rows_per_req, pages]) loads each
64-key tile once per request (pages from the request's LAST row, the longest context), then runs his exact per-row
T.gemm / relu / reduce_sum for each row, so every logit is bit-identical. `qsa_indexer.forward_cuda` passes
`rows_per_req = spec_info.draft_token_num` in target verify only (decode / draft_extend unchanged).
Off-switch: `SGLANG_KIDX=0`.

## Evidence
- check_kidx.py (daniel-bench-kidx-1004): logits bitwise equal at 4 / 6 / 8 rows per request, with and without padding
  requests, earlier rows' page tables truncated; CUDA-graph replay equal. Cold timing (10 requests, 100-131k tokens):
  98 -> 61 us per layer (W4), 140 -> 66 (W6), 186 -> 73 (W8).
- In-server (daniel-bench-kidxs-1004 vs control daniel-bench-kprof2-1004, 10 lanes W4, 8-bit route), indexer GPU time
  at matched context per game: m10 (~81k tokens) 63 vs ~92 us/call (-0.37 ms/step), m20 (~43k) 42 vs ~55 us/call
  (-0.17 ms/step). About half of the new kernel overlaps other streams (24% before), so the wall gain is somewhat
  smaller. tok/s minutes 0-25: 832 vs 807, accept 2.983 vs 2.985 (one pair, inside noise). Grows with draft width.

- W8 (daniel-bench-kidxw8-1004 = kidxr patch set, 8-token drafts, vs daniel-bench-kw8rb-1004): indexer per call at the
  same profile minutes 153 -> 72 us (m10) and 90 -> 54 us (m18) (context not matched), about -0.5 to -1 ms GPU per
  step. tok/s 728 vs 733, accept 3.78 vs 3.81 (one pair, inside noise). serve.log clean.

## Use
    make_bench_notebook.py ... --patch-set .../kernels/kfast --patch-set .../kfuse8 --patch-set .../kq8 \
        --patch-set D:/codex-work/daniel-draft/kernels/kidx
