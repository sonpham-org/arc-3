"""Skinny BF16 GEMM for sm120 decode/verify widths (3-Oct-2026, daniel-draft kernels; Son: faster dense layers).

out[M, N] = x[M, K] @ w[N, K]^T, bf16 in/out, fp32 accumulate, M <= 64.
Weights are the MMA "A" operand (BLOCK_N rows), tokens the "B" operand (BLOCK_M columns), so one CTA streams a
BLOCK_N x K weight panel once and reuses it for every token. Split-K is DETERMINISTIC: each k-slice CTA writes its
fp32 partial to a workspace, and the last CTA to finish an N-tile (per-tile arrival counter) sums the partials in
slice order 0..S-1 and writes bf16; it then resets the counter, so a captured CUDA graph replays cleanly.
Batch invariant for a fixed tactic: every output row only depends on its own input row.
"""
from __future__ import annotations

import torch
import triton
import triton.language as tl


@triton.jit
def _skinny_gemm_kernel(
    x_ptr, w_ptr, out_ptr, ws_ptr, cnt_ptr,
    M, N, K, K_PER,
    stride_xm, stride_wn, stride_om,
    BLOCK_M: tl.constexpr, BLOCK_N: tl.constexpr, BLOCK_K: tl.constexpr,
    SPLIT: tl.constexpr, NUM_STAGES: tl.constexpr, EVEN_N: tl.constexpr, NTHREADS: tl.constexpr,
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
            w = tl.load(w_ptrs, mask=n_mask[:, None], other=0.0, eviction_policy="evict_first")
        xb = tl.load(x_ptrs, mask=m_mask[None, :], other=0.0, eviction_policy="evict_last")
        acc = tl.dot(w, xb, acc)
        w_ptrs += BLOCK_K
        x_ptrs += BLOCK_K
    out_ptrs = out_ptr + rm[None, :] * stride_om + rn[:, None]
    o_mask = n_mask[:, None] & m_mask[None, :]
    if SPLIT:
        n_pad = tl.num_programs(0) * BLOCK_N
        ws_tile = ws_ptr + rn[:, None] * BLOCK_M + rm[None, :]  # [S, n_pad, BLOCK_M] fp32
        tl.store(ws_tile + pid_k * n_pad * BLOCK_M, acc, cache_modifier=".cg")
        # every thread fences its partial (gpu scope) before one thread signals arrival
        _f = tl.inline_asm_elementwise("fence.acq_rel.gpu;\n\tmov.u32 $0, $1;", "=r,r", [tl.arange(0, NTHREADS)],
                                       dtype=tl.int32, is_pure=False, pack=1)
        tl.debug_barrier()
        arrived = tl.atomic_add(cnt_ptr + pid_n, 1, sem="acq_rel", scope="gpu")
        if arrived == n_split - 1:
            _g = tl.inline_asm_elementwise("fence.acq_rel.gpu;\n\tmov.u32 $0, $1;", "=r,r", [tl.arange(0, NTHREADS)],
                                           dtype=tl.int32, is_pure=False, pack=1)
            tot = tl.zeros((BLOCK_N, BLOCK_M), dtype=tl.float32)
            for s in range(0, n_split):
                tot += tl.load(ws_tile + s * n_pad * BLOCK_M, cache_modifier=".cg")
            tl.store(out_ptrs, tot.to(tl.bfloat16), mask=o_mask)
            tl.atomic_xchg(cnt_ptr + pid_n, 0, sem="relaxed", scope="gpu")
    else:
        tl.store(out_ptrs, acc.to(tl.bfloat16), mask=o_mask)


_WS = {}


def _scratch(device, key, ws_elems, n_tiles):
    """Per-shape split-K workspace + arrival counters (distinct shapes may run concurrently on side streams)."""
    ws, cnt = _WS.get(key, (None, None))
    if ws is None or ws.numel() < ws_elems:
        ws = torch.empty(ws_elems, dtype=torch.float32, device=device)
    if cnt is None or cnt.numel() < n_tiles:
        cnt = torch.zeros(n_tiles, dtype=torch.int32, device=device)
    _WS[key] = (ws, cnt)
    return ws, cnt


def skinny_gemm(x: torch.Tensor, w: torch.Tensor, block_n=64, block_k=128, split=1, warps=4, stages=3,
                out: torch.Tensor | None = None) -> torch.Tensor:
    """x[..., K] @ w[N, K]^T. split must divide K into multiples of block_k."""
    x2 = x.reshape(-1, x.shape[-1])
    m, k = x2.shape
    n = w.shape[0]
    assert m <= 128 and x2.stride(1) == 1 and w.stride(1) == 1
    assert k % (split * block_k) == 0, (k, split, block_k)
    block_m = max(16, triton.next_power_of_2(m))
    n_tiles = triton.cdiv(n, block_n)
    if out is None:
        out = torch.empty((m, n), dtype=torch.bfloat16, device=x.device)
    if split > 1:
        ws, cnt = _scratch(x.device, (x.device, n, k, block_n, block_m, split), split * n_tiles * block_n * block_m, n_tiles)
    else:
        ws, cnt = out, out
    _skinny_gemm_kernel[(n_tiles, split)](
        x2, w, out, ws, cnt, m, n, k, k // split, x2.stride(0), w.stride(0), out.stride(0),
        BLOCK_M=block_m, BLOCK_N=block_n, BLOCK_K=block_k, SPLIT=split > 1, NUM_STAGES=stages,
        EVEN_N=(n % block_n == 0), NTHREADS=32 * warps, num_warps=warps)
    return out.view(*x.shape[:-1], n)
