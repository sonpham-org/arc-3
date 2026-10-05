# SPDX-License-Identifier: Apache-2.0
"""SM120 (RTX PRO 6000 Blackwell / GeForce Blackwell) low-M BF16 GEMM.

cuBLAS under CUDA-graph capture serves the qwen3.5/qwen4 decode projections
(m <= 8, k in {1536, 2560}) with 1-warp split-K WMMA kernels that reach only
~20-70% of DRAM bandwidth on sm120 (measured 61.9 us for m=4, n=4120, k=2560
= 320 GB/s on an RTX PRO 6000). The SM100 CuTeDSL/split-K paths in
``unquant.py`` need tcgen05 and cannot run here. This module provides a plain
Triton split-K GEMV tuned per shape for sm120, dispatched from
``bf16_gemm_dispatch``.

Split-K partials are accumulated with fp32 atomics: non-deterministic
summation order, so this path is disabled under
``--enable-deterministic-inference`` (mirrors the SM100 split-K policy).
"""

from __future__ import annotations

from typing import Optional

import torch
import triton
import triton.language as tl

# (m, n, k) -> (split_k, block_n, block_k, num_warps, num_stages)
# Tuned on RTX PRO 6000 Blackwell (sm120, GDDR7 @ 13365 MHz) with HBM-cold
# weights and sequential (event-timed) launches; see qwen38fn/PERF_CEILING.md.
_SM120_TUNED_TACTICS: dict[tuple[int, int, int], tuple[int, int, int, int, int]] = {}

# Shapes eligible for the generic fallback tactic even when not in the table.
# Covers decode (m = bs <= 4), bs=1 target-verify (m = 4-5) and bs<=4 C4
# verify (m <= 16), plus small eager draft-extend batches.
_MAX_M = 32
_MIN_WEIGHT_BYTES = 512 * 1024  # below this, launch overhead dominates; keep cuBLAS
# Above this, cuBLAS GEMV/split-K already streams at ~94% of DRAM bandwidth
# (measured on the 1.27 GB lm_head); keep it.
_MAX_WEIGHT_BYTES = 128 * 1024 * 1024


@triton.jit
def _sm120_lowm_gemm_kernel(
    x_ptr,
    w_ptr,
    out_ptr,
    M,
    N,
    K,
    stride_xm,
    stride_xk,
    stride_wn,
    stride_wk,
    stride_om,
    stride_on,
    BLOCK_N: tl.constexpr,
    BLOCK_K: tl.constexpr,
    BLOCK_M: tl.constexpr,
    SPLIT_K: tl.constexpr,
    NUM_STAGES: tl.constexpr,
    OUT_BF16: tl.constexpr,
):
    pid_n = tl.program_id(0)
    pid_k = tl.program_id(1)
    rn = pid_n * BLOCK_N + tl.arange(0, BLOCK_N)
    rm = tl.arange(0, BLOCK_M)
    n_mask = rn < N
    m_mask = rm < M
    acc = tl.zeros((BLOCK_M, BLOCK_N), dtype=tl.float32)
    k_per = tl.cdiv(K, SPLIT_K)
    k_start = pid_k * k_per
    k_end = tl.minimum(k_start + k_per, K)
    for k0 in tl.range(k_start, k_end, BLOCK_K, num_stages=NUM_STAGES):
        rk = k0 + tl.arange(0, BLOCK_K)
        k_mask = rk < k_end
        xb = tl.load(
            x_ptr + rm[:, None] * stride_xm + rk[None, :] * stride_xk,
            mask=m_mask[:, None] & k_mask[None, :],
            other=0.0,
        )
        wb = tl.load(
            w_ptr + rn[:, None] * stride_wn + rk[None, :] * stride_wk,
            mask=n_mask[:, None] & k_mask[None, :],
            other=0.0,
        )
        acc += tl.dot(xb, tl.trans(wb), out_dtype=tl.float32)
    if OUT_BF16:
        tl.store(
            out_ptr + rm[:, None] * stride_om + rn[None, :] * stride_on,
            acc.to(tl.bfloat16),
            mask=m_mask[:, None] & n_mask[None, :],
        )
    else:
        tl.atomic_add(
            out_ptr + rm[:, None] * stride_om + rn[None, :] * stride_on,
            acc,
            mask=m_mask[:, None] & n_mask[None, :],
            sem="relaxed",
        )


def _generic_tactic(m: int, n: int, k: int) -> tuple[int, int, int, int, int]:
    """(1, 16, 128) measured best for the wide shapes (81% of DRAM bandwidth
    at m=4, n=4120, k=2560); split K only when 16-wide N tiles cannot fill
    the 188 sm120 SMs."""
    n_ctas = triton.cdiv(n, 16)
    split_k = 1
    while split_k < 16 and n_ctas * split_k < 128 and (k // (split_k * 2)) >= 256:
        split_k *= 2
    return (split_k, 16, 128, 4, 4)


# ---------------------------------------------------------------------------------------------------------------
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
# kglue (5-Oct-2026): launch the skinny kernel with PDL (see kernel). SGLANG_KGLUE_PDL=0 disables.
_KGLUE_PDL = _os.environ.get("SGLANG_KGLUE_PDL", "1") != "0"
_kglue_pdl_ok = None


def _kglue_use_pdl() -> bool:
    global _kglue_pdl_ok
    if _kglue_pdl_ok is None:
        try:
            from sglang.kernels.jit.utils import is_arch_support_pdl

            _kglue_pdl_ok = bool(_KGLUE_PDL and is_arch_support_pdl())
        except Exception:
            _kglue_pdl_ok = False
    return _kglue_pdl_ok
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
    USE_PDL: tl.constexpr = False,
):
    if USE_PDL:
        # kglue: launched early under PDL; wait for the previous grid before touching any memory
        tl.extra.cuda.gdc_wait()
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
        USE_PDL=_kglue_use_pdl(),
        num_warps=num_warps,
        **({"launch_pdl": True} if _kglue_use_pdl() else {}),
    )
    return out


def use_sm120_lowm_bf16_gemm(m: int, n: int, k: int) -> bool:
    if _skinny_tactic(m, n, k) is not None:
        return True
    return m <= _MAX_M and _MIN_WEIGHT_BYTES <= n * k * 2 <= _MAX_WEIGHT_BYTES


def sm120_lowm_bf16_gemm(x: torch.Tensor, weight: torch.Tensor) -> torch.Tensor:
    """out = x @ weight.T for bf16 x[m, k], weight[n, k]; bias-free, m <= 8."""
    x_2d = x.view(-1, x.shape[-1])
    m, k = x_2d.shape
    n = weight.shape[0]
    sk = _skinny_tactic(m, n, k)
    if sk is not None and x_2d.stride(1) == 1 and weight.stride(1) == 1:
        return _skinny_gemm(x_2d, weight, *sk).view(*x.shape[:-1], n)
    tactic = _SM120_TUNED_TACTICS.get((m, n, k)) or _generic_tactic(m, n, k)
    split_k, block_n, block_k, num_warps, num_stages = tactic
    block_m = max(16, triton.next_power_of_2(m))
    grid = (triton.cdiv(n, block_n), split_k)
    if split_k == 1:
        out = torch.empty((m, n), dtype=torch.bfloat16, device=x.device)
        _sm120_lowm_gemm_kernel[grid](
            x_2d,
            weight,
            out,
            m,
            n,
            k,
            x_2d.stride(0),
            x_2d.stride(1),
            weight.stride(0),
            weight.stride(1),
            out.stride(0),
            out.stride(1),
            BLOCK_N=block_n,
            BLOCK_K=block_k,
            BLOCK_M=block_m,
            SPLIT_K=1,
            NUM_STAGES=num_stages,
            OUT_BF16=True,
            num_warps=num_warps,
        )
    else:
        acc = torch.zeros((m, n), dtype=torch.float32, device=x.device)
        _sm120_lowm_gemm_kernel[grid](
            x_2d,
            weight,
            acc,
            m,
            n,
            k,
            x_2d.stride(0),
            x_2d.stride(1),
            weight.stride(0),
            weight.stride(1),
            acc.stride(0),
            acc.stride(1),
            BLOCK_N=block_n,
            BLOCK_K=block_k,
            BLOCK_M=block_m,
            SPLIT_K=split_k,
            NUM_STAGES=num_stages,
            OUT_BF16=False,
            num_warps=num_warps,
        )
        out = acc.to(torch.bfloat16)
    return out.view(*x.shape[:-1], n)


def precompile_sm120_lowm_tactics(device: Optional[torch.device] = None) -> None:
    """JIT-compile the tuned specializations before CUDA graph capture."""
    for m, n, k in _SM120_TUNED_TACTICS:
        x = torch.zeros(m, k, dtype=torch.bfloat16, device=device or "cuda")
        w = torch.zeros(n, k, dtype=torch.bfloat16, device=device or "cuda")
        sm120_lowm_bf16_gemm(x, w)
    # generic-tactic block sizes used by unlisted shapes
    torch.cuda.synchronize()
