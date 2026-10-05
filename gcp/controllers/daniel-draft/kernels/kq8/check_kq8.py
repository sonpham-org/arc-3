"""kq8 / kq8r check in the PATCHED install (4-Oct-2026, daniel-draft kfuse8): bench_qsa8.py with the installed
qsa.sparse_attn.qwen_sparse_fp8_fused_decode_triton (its own tactics) as the per-row candidate; union skipped.
Pre-only use: it runs FlashInfer XQA as the reference (do not put it before a server start)."""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench_qsa8
from sglang.srt.layers.attention.qsa import sparse_attn as S


def fused(q, k, v, r2t, row_req, idx, seq, vcnt, scale, **cfg):
    return S.qwen_sparse_fp8_fused_decode_triton(q, k, v, r2t, row_req, idx, seq, vcnt, scale, q.shape[0])


bench_qsa8.qsa_fp8_fused_decode = fused
bench_qsa8.qsa_fp8_union_decode = None
print(json.dumps({"part": "kq8", "installed": S.__file__}), flush=True)
_orig_main = bench_qsa8.main
bench_qsa8.main()
