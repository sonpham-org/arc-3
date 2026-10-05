"""Build kfast/patched/.../sm120_lowm_bf16_gemm.py from his original + the skinny kernel (bench/skinny_gemm.py)."""
from pathlib import Path

ROOT = Path(r"D:\codex-work\daniel-draft\kernels\kfast")
REL = "sglang/kernels/ops/gemm/sm120_lowm_bf16_gemm.py"
s = (ROOT / "orig" / REL).read_bytes().decode("utf-8")
assert "\r" not in s

old = """def use_sm120_lowm_bf16_gemm(m: int, n: int, k: int) -> bool:
    return m <= _MAX_M and _MIN_WEIGHT_BYTES <= n * k * 2 <= _MAX_WEIGHT_BYTES
"""
new = """def use_sm120_lowm_bf16_gemm(m: int, n: int, k: int) -> bool:
    if _skinny_tactic(m, n, k) is not None:
        return True
    return m <= _MAX_M and _MIN_WEIGHT_BYTES <= n * k * 2 <= _MAX_WEIGHT_BYTES
"""
assert s.count(old) == 1
s = s.replace(old, new)

old = '''    """out = x @ weight.T for bf16 x[m, k], weight[n, k]; bias-free, m <= 8."""
    x_2d = x.view(-1, x.shape[-1])
    m, k = x_2d.shape
    n = weight.shape[0]
'''
new = '''    """out = x @ weight.T for bf16 x[m, k], weight[n, k]; bias-free, m <= 8."""
    x_2d = x.view(-1, x.shape[-1])
    m, k = x_2d.shape
    n = weight.shape[0]
    sk = _skinny_tactic(m, n, k)
    if sk is not None and x_2d.stride(1) == 1 and weight.stride(1) == 1:
        return _skinny_gemm(x_2d, weight, *sk).view(*x.shape[:-1], n)
'''
assert s.count(old) == 1
s = s.replace(old, new)

add = r'''# ---------------------------------------------------------------------------------------------------------------
# daniel-draft kfast (3-Oct-2026): skinny GEMM for 9 <= m <= 64 (spec-decode verify of 3-16 lanes x 4 tokens,
# draft-extend, 9-16-lane draft steps) on the Qwen3.8-Flash-Next TP1 projection shapes. Weights are the MMA "A"
# operand (BLOCK_N rows), tokens the "B" operand, so each CTA streams its weight panel from DRAM once for all rows.
# Split-K is DETERMINISTIC (no fp32 atomics): each k-slice CTA stores its fp32 partial, and the last CTA to arrive
# on an N-tile sums the partials in slice order and writes bf16, then resets the tile's counter (CUDA-graph safe).
# Unsplit tactics give bit-identical outputs to cuBLAS's sm80 kernels (same fp32 k-order); split ones differ from
# cuBLAS's split-K reduce at bf16 rounding only. Cold-weight CUDA-graph timings on the RTX PRO 6000 (us, m=52,
# cuBLAS -> skinny): in_proj 61.7->59.1, qkv 50.8->49.4, out/o_proj 26.4->25.6, shared gate_up 10.3->8.6,
# shared down 6.1->4.6, router gate 6.8->6.6 (kernels/bench/bench_dense.py, run daniel-bench-kgemm-1003).
# m <= 8 keeps the tuned generic tactic above. SGLANG_KFAST_SKINNY=0 disables.
import os as _os

_SKINNY_ON = _os.environ.get("SGLANG_KFAST_SKINNY", "1") == "1"
_SKINNY_MIN_M = 9
_SKINNY_MAX_M = 64
# (n, k) -> (tactic for m <= 16, tactic for 17 <= m <= 64); tactic = (block_n, block_k, split, num_warps, num_stages)
_SKINNY_TACTICS: dict = {
    (16480, 2560): ((32, 128, 1, 4, 4), (64, 128, 1, 4, 4)),  # GDN fused in_proj_qkvz + in_proj_ba
    (13312, 2560): ((32, 128, 1, 4, 3), (32, 64, 1, 4, 3)),  # QSA qkv (+ output gate)
    (2560, 6144): ((32, 128, 4, 4, 3), (32, 128, 4, 4, 3)),  # GDN out_proj, QSA o_proj
    (1280, 2560): ((32, 128, 4, 4, 5), (32, 128, 4, 8, 3)),  # shared expert gate_up
    (2560, 640): ((32, 128, 1, 4, 4), (32, 128, 1, 8, 4)),  # shared expert down
    (512, 2560): ((32, 128, 5, 4, 4), (32, 128, 5, 8, 4)),  # router gate
}


def _skinny_tactic(m: int, n: int, k: int):
    if not _SKINNY_ON or m < _SKINNY_MIN_M or m > _SKINNY_MAX_M:
        return None
    t = _SKINNY_TACTICS.get((n, k))
    if t is None:
        return None
    return t[0] if m <= 16 else t[1]


@triton.jit
def _kfast_skinny_gemm_kernel(
    x_ptr,
    w_ptr,
    out_ptr,
    ws_ptr,
    cnt_ptr,
    M,
    N,
    K,
    K_PER,
    stride_xm,
    stride_wn,
    stride_om,
    BLOCK_M: tl.constexpr,
    BLOCK_N: tl.constexpr,
    BLOCK_K: tl.constexpr,
    SPLIT: tl.constexpr,
    NUM_STAGES: tl.constexpr,
    EVEN_N: tl.constexpr,
    NTHREADS: tl.constexpr,
):
    pid_n = tl.program_id(0)
    pid_k = tl.program_id(1)
    n_split = tl.num_programs(1)
    rn = pid_n * BLOCK_N + tl.arange(0, BLOCK_N)
    rm = tl.arange(0, BLOCK_M)
    rk = tl.arange(0, BLOCK_K)
    n_mask = rn < N
    m_mask = rm < M
    k_lo = pid_k * K_PER
    w_ptrs = w_ptr + rn[:, None].to(tl.int64) * stride_wn + (k_lo + rk)[None, :]
    x_ptrs = x_ptr + rm[None, :] * stride_xm + (k_lo + rk)[:, None]
    acc = tl.zeros((BLOCK_N, BLOCK_M), dtype=tl.float32)
    for _k in tl.range(0, K_PER, BLOCK_K, num_stages=NUM_STAGES):
        if EVEN_N:
            w = tl.load(w_ptrs, eviction_policy="evict_first")
        else:
            w = tl.load(
                w_ptrs, mask=n_mask[:, None], other=0.0, eviction_policy="evict_first"
            )
        xb = tl.load(
            x_ptrs, mask=m_mask[None, :], other=0.0, eviction_policy="evict_last"
        )
        acc = tl.dot(w, xb, acc)
        w_ptrs += BLOCK_K
        x_ptrs += BLOCK_K
    out_ptrs = out_ptr + rm[None, :] * stride_om + rn[:, None]
    o_mask = n_mask[:, None] & m_mask[None, :]
    if SPLIT:
        n_pad = tl.num_programs(0) * BLOCK_N
        ws_tile = ws_ptr + rn[:, None] * BLOCK_M + rm[None, :]  # [S, n_pad, BLOCK_M] fp32
        tl.store(ws_tile + pid_k * n_pad * BLOCK_M, acc, cache_modifier=".cg")
        # every thread fences its partial at gpu scope before one thread signals arrival
        _f = tl.inline_asm_elementwise(
            "fence.acq_rel.gpu;\n\tmov.u32 $0, $1;",
            "=r,r",
            [tl.arange(0, NTHREADS)],
            dtype=tl.int32,
            is_pure=False,
            pack=1,
        )
        tl.debug_barrier()
        arrived = tl.atomic_add(cnt_ptr + pid_n, 1, sem="acq_rel", scope="gpu")
        if arrived == n_split - 1:
            _g = tl.inline_asm_elementwise(
                "fence.acq_rel.gpu;\n\tmov.u32 $0, $1;",
                "=r,r",
                [tl.arange(0, NTHREADS)],
                dtype=tl.int32,
                is_pure=False,
                pack=1,
            )
            tot = tl.zeros((BLOCK_N, BLOCK_M), dtype=tl.float32)
            for s in range(0, n_split):
                tot += tl.load(ws_tile + s * n_pad * BLOCK_M, cache_modifier=".cg")
            tl.store(out_ptrs, tot.to(tl.bfloat16), mask=o_mask)
            tl.atomic_xchg(cnt_ptr + pid_n, 0, sem="relaxed", scope="gpu")
    else:
        tl.store(out_ptrs, acc.to(tl.bfloat16), mask=o_mask)


# Split-K workspace + arrival counters, one pair per (device, shape, tile): distinct shapes may run concurrently on
# side streams (router gate vs shared expert); the same shape never does. First use is the eager warm-up before
# CUDA-graph capture, so these stay outside the graph pools.
_SKINNY_WS: dict = {}


def _skinny_gemm(x_2d, weight, block_n, block_k, split, num_warps, num_stages):
    m, k = x_2d.shape
    n = weight.shape[0]
    block_m = max(16, triton.next_power_of_2(m))
    n_tiles = triton.cdiv(n, block_n)
    out = torch.empty((m, n), dtype=torch.bfloat16, device=x_2d.device)
    if split > 1:
        key = (x_2d.device, n, k, block_n, block_m, split)
        ws_cnt = _SKINNY_WS.get(key)
        if ws_cnt is None:
            ws_cnt = (
                torch.empty(
                    split * n_tiles * block_n * block_m,
                    dtype=torch.float32,
                    device=x_2d.device,
                ),
                torch.zeros(n_tiles, dtype=torch.int32, device=x_2d.device),
            )
            _SKINNY_WS[key] = ws_cnt
        ws, cnt = ws_cnt
    else:
        ws, cnt = out, out
    _kfast_skinny_gemm_kernel[(n_tiles, split)](
        x_2d,
        weight,
        out,
        ws,
        cnt,
        m,
        n,
        k,
        k // split,
        x_2d.stride(0),
        weight.stride(0),
        out.stride(0),
        BLOCK_M=block_m,
        BLOCK_N=block_n,
        BLOCK_K=block_k,
        SPLIT=split > 1,
        NUM_STAGES=num_stages,
        EVEN_N=(n % block_n == 0),
        NTHREADS=32 * num_warps,
        num_warps=num_warps,
    )
    return out


'''
anchor = "def use_sm120_lowm_bf16_gemm("
assert s.count(anchor) == 1
s = s.replace(anchor, add + anchor)
out = ROOT / "patched" / REL
out.write_bytes(s.encode("utf-8"))
compile(s, REL, "exec")
print("ok", out, len(s))
