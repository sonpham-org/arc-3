"""Build the 8-bit QSA patch sets (4-Oct-2026, daniel-draft kfuse8):

  kq8   his ORIGINAL qsa/sparse_attn.py + qwen_sparse_attn_backend.py, + the fused fp8 sparse decode (width 4, no qsaring)
  kq8r  same sparse_attn.py; the backend is qsaring's patched backend + the same dispatch (use with --qsa-ring R:
        supersedes qsaring's backend, carries all of qsaring's changes)

Kernel = dev/qsa_fp8.py's per-row path (_k8_fence, _k8_combine, _k8_fused_kernel). Dispatch in _forward_trtllm_sparse:
fp8_e4m3 pool + bf16 q -> one fused kernel instead of _compact_kv into an FP8 scratch + XQA.
SGLANG_KFUSE_QSA8=0 restores his path.
"""
import hashlib
import re
import zipfile
from pathlib import Path

K = Path(r"D:\codex-work\daniel-draft\kernels")
WHEEL = zipfile.ZipFile(r"D:\codex-work\daniel-draft\wheel\sglang.whl")
SA = "sglang/srt/layers/attention/qsa/sparse_attn.py"
BE = "sglang/srt/layers/attention/qwen_sparse_attn_backend.py"
RING_BE = Path(r"D:\codex-work\daniel-draft\qsaring\patched") / BE

dev = (K / "kfuse" / "dev" / "qsa_fp8.py").read_text(encoding="utf-8")
a = dev.index("@triton.jit\ndef _k8_fence(")
b = dev.index("def _k8_ws(")
kern = dev[a:b]
assert "_k8u_" not in kern
wrapper = '''def qwen_sparse_fp8_fused_decode_triton(
    q, k_buffer, v_buffer, req_to_token, row_req, topk_indices, seq_lens, valid_counts, sm_scale, capacity_rows
):
    """daniel-draft kfuse8 (4-Oct-2026): QSA sparse decode straight from an fp8_e4m3 KV pool, one kernel per layer.

    Replaces _compact_kv into a page-aligned FP8 scratch + FlashInfer XQA: per (row, kv head, split) the row's
    selected pool rows are read directly (fp8 -> bf16 is exact) and XQA's math runs in registers: bf16 Q x bf16 K
    with fp32 accumulation, online softmax, P rounded to bf16 for P x V and the row sum. Splits are combined by
    the last split to finish, in fixed order (deterministic; counters reset: CUDA-graph safe). Rows with no valid
    position output zeros. RTX PRO 6000, 12 cold layers, 10 requests: 40 verify rows 80 -> 50 us per layer, 60 rows
    178 -> 68 us, 80 rows 262 -> 76 us; within 1 bf16 ulp of the scratch + XQA path, closer to an fp32 reference."""
    rows, hq, d = q.shape
    heads_kv = k_buffer.shape[1]
    group = hq // heads_kv
    qp = max(16, triton.next_power_of_2(group))
    topk = topk_indices.shape[1]
    if rows <= 16:
        splits, block_n, warps, stages = 8, 64, 8, 2
    else:
        splits, block_n, warps, stages = 8, 32, 4, 3
    out = torch.empty_like(q)
    cols = triton.cdiv(triton.cdiv(topk, splits), block_n) * block_n
    cap = max(rows, capacity_rows)
    key = (q.device, heads_kv, qp, d, splits)
    st = _K8_WS.get(key)
    if st is None or st[1].numel() < cap * heads_kv:
        st = (
            torch.empty(cap * heads_kv * splits * qp * (2 + d), dtype=torch.float32, device=q.device),
            torch.zeros(cap * heads_kv, dtype=torch.int32, device=q.device),
        )
        _K8_WS[key] = st
    ws, cnt = st
    _k8_fused_kernel[(rows, heads_kv, splits)](
        q, out, ws, cnt, k_buffer, v_buffer, req_to_token, row_req, topk_indices, seq_lens, valid_counts,
        float(sm_scale), q.stride(0), q.stride(1), out.stride(0), out.stride(1), req_to_token.stride(0),
        topk_indices.stride(0), cols,
        HEADS_KV=heads_kv, GROUP=group, QP=qp, D=d, BLOCK_N=block_n, SPLITS=splits, NTHREADS=32 * warps,
        num_warps=warps, num_stages=stages,
    )
    return out


'''
DISPATCH = '''        if (
            _KFUSE_QSA8
            and k_buffer.dtype == torch.float8_e4m3fn
            and q.dtype == torch.bfloat16
            and k_buffer.dim() == 3
            and q.shape[-1] == k_buffer.shape[2]
            and k_buffer.is_contiguous()
            and v_buffer.is_contiguous()
        ):
            # daniel-draft kfuse8: read the selected fp8 rows in the attention kernel (no scratch, no XQA).
            output = qwen_sparse_fp8_fused_decode_triton(
                q.contiguous(),
                k_buffer,
                v_buffer,
                self.req_to_token_pool.req_to_token,
                (
                    metadata.row_req_pool_indices
                    if metadata.row_req_pool_indices is not None
                    else forward_batch.req_pool_indices
                ),
                topk_indices,
                sequence_lens,
                valid_counts,
                layer.scaling,
                max(int(self._cuda_graph_max_tokens if metadata.is_cuda_graph else batch), batch),
            )
            return output.reshape(q.shape[0], -1)
'''
ANCHOR = '''        qwen_sparse_valid_counts_triton(
            sequence_lens, topk_indices, valid_counts, batch, topk
        )
        cu_strided, block_tables = self._get_trtllm_sparse_tables(
'''


def build_sparse_attn():
    s = WHEEL.read(SA).decode("utf-8")
    assert "\r" not in s
    block = ("# " + "-" * 110 + "\n# daniel-draft kfuse8 (4-Oct-2026): fused fp8 QSA sparse decode (see "
             "qwen_sparse_fp8_fused_decode_triton).\n_K8_WS = {}\n\n\n" + kern + wrapper)
    anchor = "__all__ = ["
    assert s.count(anchor) == 1
    s = s.replace(anchor, block + anchor)
    s = s.replace('    "qwen_sparse_kv_extraction_compact_triton",\n',
                  '    "qwen_sparse_kv_extraction_compact_triton",\n    "qwen_sparse_fp8_fused_decode_triton",\n', 1)
    compile(s, SA, "exec")
    return s


def patch_backend(t):
    old_imp = "    qwen_sparse_kv_extraction_compact_triton,\n"
    assert t.count(old_imp) == 1
    t = t.replace(old_imp, old_imp + "    qwen_sparse_fp8_fused_decode_triton,\n", 1)
    assert t.count(ANCHOR) == 1, t.count(ANCHOR)
    head, tail = ANCHOR.split("        cu_strided, block_tables")
    t = t.replace(ANCHOR, head + DISPATCH + "        cu_strided, block_tables" + tail)
    old2 = "_TRTLLM_SPARSE_PAGE_SIZE = 64\n"
    assert t.count(old2) == 1
    t = t.replace(old2, old2 + '# daniel-draft kfuse8: fused fp8 sparse decode (SGLANG_KFUSE_QSA8=0 restores scratch + XQA)\n'
                  '_KFUSE_QSA8 = __import__("os").environ.get("SGLANG_KFUSE_QSA8", "1") == "1"\n', 1)
    compile(t, BE, "exec")
    return t


def write(setname, files):
    root = K / setname
    for n, new in files.items():
        (root / "orig" / n).parent.mkdir(parents=True, exist_ok=True)
        (root / "patched" / n).parent.mkdir(parents=True, exist_ok=True)
        (root / "orig" / n).write_bytes(WHEEL.read(n))
        (root / "patched" / n).write_bytes(new.encode("utf-8"))
    print(setname, {n: hashlib.sha256((root / "patched" / n).read_bytes()).hexdigest()[:12] for n in files})


sa = build_sparse_attn()
write("kq8", {SA: sa, BE: patch_backend(WHEEL.read(BE).decode("utf-8"))})
ring = RING_BE.read_bytes().decode("utf-8")
assert "\r" not in ring
write("kq8r", {SA: sa, BE: patch_backend(ring)})
