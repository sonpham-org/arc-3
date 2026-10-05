"""Build kfuse/patched QSA files = qsakv4's patched files + the fused NVFP4 sparse decode (dev/qsa_fused.py, v2 path).

sparse_attn.py: + _kf_* kernels and qwen_sparse_nvfp4_fused_decode_triton (appended before __all__).
qwen_sparse_attn_backend.py: _forward_trtllm_sparse takes the fused kernel for nvfp4_qsa pools (bf16 q, head_dim
256); SGLANG_KFUSE_QSA=0 restores qsakv4's gather + XQA. orig/ = his wheel bytes (as in qsakv4/orig).
"""
import hashlib
import re
import zipfile
from pathlib import Path

ROOT = Path(r"D:\codex-work\daniel-draft\kernels\kfuse")
KV4 = Path(r"D:\codex-work\daniel-draft\qsakv4")
z = zipfile.ZipFile(r"D:\codex-work\daniel-draft\wheel\sglang.whl")
SA = "sglang/srt/layers/attention/qsa/sparse_attn.py"
BE = "sglang/srt/layers/attention/qwen_sparse_attn_backend.py"
for n in (SA, BE):
    orig = z.read(n)
    assert (KV4 / "orig" / n).read_bytes() == orig
    (ROOT / "orig" / n).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / "orig" / n).write_bytes(orig)

# ---- sparse_attn.py
s = (KV4 / "patched" / SA).read_bytes().decode("utf-8")
dev = (ROOT / "dev" / "qsa_fused.py").read_text(encoding="utf-8")
a = dev.index("@triton.jit\ndef _kf_unpack_v2(")
b = dev.index("_KF_WS = {}")
kern = dev[a:b]
# keep only the v2 unpack path
kern = kern.replace("    V2: tl.constexpr,\n", "")
kern = re.sub(r"        if V2:\n            (k_lo, k_hi|v_lo, v_hi) = _kf_unpack_v2\((.*?)\)\n        else:\n            .*?\n",
              lambda m: f"        {m.group(1)} = _kf_unpack_v2({m.group(2)})\n", kern, flags=re.S)
assert "_kf_unpack(" not in kern and "V2" not in kern, kern[:3000]
wrapper = '''_KF_WS = {}


def qwen_sparse_nvfp4_fused_decode_triton(
    q, nvfp4, req_to_token, row_req, topk_indices, seq_lens, valid_counts, sm_scale, round_fp8, capacity_rows
):
    """daniel-draft kfuse (3-Oct-2026): QSA sparse decode straight from nvfp4_qsa KV, one kernel per layer.

    Replaces the gather into an FP8 scratch (_compact_kv_nvfp4) + FlashInfer XQA: per (row, kv head, split) the
    row's selected positions are unpacked in registers with the gather's exact arithmetic (e2m1 * fp8 block scale
    * fp32 global scale, clamp +-448, FP8 E4M3 rounding when the scratch would be FP8), then XQA's math: bf16 Q x
    bf16 K with fp32 accumulation, online softmax, P rounded to bf16 for P x V and the row sum. Splits are combined
    by the last split to finish, in fixed order (deterministic; counters reset, CUDA-graph safe). Rows with no
    valid position output zeros. Measured on the RTX PRO 6000 (12 layers, cold NVFP4 pools, 52 verify rows):
    163 -> 85 us per layer; 13 rows: 51 -> 35 us; outputs within 1 bf16 ulp of the gather + XQA path."""
    k_packed, v_packed, k_scales, v_scales, k_gs, v_gs = nvfp4
    rows, hq, d = q.shape
    heads_kv, half = k_packed.shape[1], k_packed.shape[2]
    assert d == 2 * half and hq % heads_kv == 0 and q.stride(2) == 1
    group = hq // heads_kv
    gpad = max(16, triton.next_power_of_2(group))
    topk = topk_indices.shape[1]
    if rows <= 16:
        splits, block_n, warps, stages = 8, 64, 8, 2
    else:
        splits, block_n, warps, stages = 8, 32, 4, 3
    out = torch.empty_like(q)
    cols = triton.cdiv(triton.cdiv(topk, splits), block_n) * block_n
    cap = max(rows, capacity_rows)
    key = (q.device, heads_kv, gpad, half, splits)
    ws_cnt = _KF_WS.get(key)
    if ws_cnt is None or ws_cnt[1].numel() < cap * heads_kv:
        ws_cnt = (
            torch.empty(cap * heads_kv * splits * gpad * (2 + 2 * half), dtype=torch.float32, device=q.device),
            torch.zeros(cap * heads_kv, dtype=torch.int32, device=q.device),
        )
        _KF_WS[key] = ws_cnt
    ws, cnt = ws_cnt
    _kf_qsa_nvfp4_decode_kernel[(rows, heads_kv, splits)](
        q, out, ws, cnt, k_packed, v_packed, k_scales, v_scales, k_gs, v_gs,
        req_to_token, row_req, topk_indices, seq_lens, valid_counts, float(sm_scale),
        q.stride(0), q.stride(1), out.stride(0), out.stride(1),
        req_to_token.stride(0), topk_indices.stride(0), cols,
        HEADS_KV=heads_kv, GROUP=group, GROUP_PAD=gpad, HALF=half, BLOCK_N=block_n, SPLITS=splits,
        NTHREADS=32 * warps, ROUND_FP8=round_fp8, num_warps=warps, num_stages=stages,
    )
    return out


'''
anchor = "__all__ = ["
assert s.count(anchor) == 1
block = ("\n# " + "-" * 110 + "\n# daniel-draft kfuse (3-Oct-2026): fused NVFP4 QSA sparse decode (see "
         "qwen_sparse_nvfp4_fused_decode_triton).\n" + kern + wrapper)
s = s.replace(anchor, block + anchor)
s = s.replace('    "qwen_sparse_kv_extraction_compact_nvfp4_triton",\n',
              '    "qwen_sparse_kv_extraction_compact_nvfp4_triton",\n    "qwen_sparse_nvfp4_fused_decode_triton",\n', 1)
assert "qwen_sparse_nvfp4_fused_decode_triton\"," in s
compile(s, SA, "exec")
(ROOT / "patched" / SA).parent.mkdir(parents=True, exist_ok=True)
(ROOT / "patched" / SA).write_bytes(s.encode("utf-8"))

# ---- qwen_sparse_attn_backend.py
t = (KV4 / "patched" / BE).read_bytes().decode("utf-8")
old_imp = "    qwen_sparse_kv_extraction_compact_nvfp4_triton,\n"
assert t.count(old_imp) == 1
t = t.replace(old_imp, old_imp + "    qwen_sparse_nvfp4_fused_decode_triton,\n", 1)
old = '''        cu_strided, block_tables = self._get_trtllm_sparse_tables(
            batch, pages_per_row, page, device
        )
        capacity_rows = self._cuda_graph_max_tokens if metadata.is_cuda_graph else batch
'''
new = '''        capacity_rows = self._cuda_graph_max_tokens if metadata.is_cuda_graph else batch
        if (
            nvfp4 is not None
            and _KFUSE_QSA
            and q.dtype == torch.bfloat16
            and q.shape[-1] == 2 * k_buffer.shape[2]
        ):
            # daniel-draft kfuse: unpack the selected NVFP4 rows in registers inside the attention kernel (no FP8
            # scratch, no XQA): same values, same math, one kernel.
            output = qwen_sparse_nvfp4_fused_decode_triton(
                q.contiguous(),
                nvfp4,
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
                _nvfp4_qsa_scratch_dtype() == torch.float8_e4m3fn,
                max(int(capacity_rows or 0), batch),
            )
            return output.reshape(q.shape[0], -1)
        cu_strided, block_tables = self._get_trtllm_sparse_tables(
            batch, pages_per_row, page, device
        )
'''
assert t.count(old) == 1, t.count(old)
t = t.replace(old, new)
old2 = "_TRTLLM_SPARSE_PAGE_SIZE = 64\n"
assert t.count(old2) == 1
t = t.replace(old2, old2 + '# daniel-draft kfuse: fused NVFP4 sparse decode (SGLANG_KFUSE_QSA=0 restores gather + XQA)\n'
              '_KFUSE_QSA = os.environ.get("SGLANG_KFUSE_QSA", "1") == "1"\n', 1)
if not re.search(r"^import os$", t, re.M):
    t = t.replace("import ", "import os\nimport ", 1)
compile(t, BE, "exec")
(ROOT / "patched" / BE).write_bytes(t.encode("utf-8"))
print("ok", [hashlib.sha256((ROOT / "patched" / n).read_bytes()).hexdigest()[:12] for n in (SA, BE)])
