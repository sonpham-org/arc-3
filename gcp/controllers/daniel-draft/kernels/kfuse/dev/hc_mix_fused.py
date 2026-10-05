"""daniel-draft kfuse (3-Oct-2026): HyperConnection mix for 9..64 rows in two kernels.

GatedResidual._mix_compute (torch.compile) at a 13-lane verify (52 rows) runs six kernels: cuBLAS down GEMM
(320 x 10240) + its split-K reduce, two inductor elementwise kernels, cuBLAS up GEMM (10240 x 320), and the inductor
sigmoid*x mean (~20 us; the 13 MB of weights alone need ~8.6 us at the card's 1,537 GB/s).
Here: (1) down = the kfast deterministic split-K skinny GEMM (bf16 out, like cuBLAS); (2) one kernel computes
s = bf16(silu(t / hc)), u_g = bf16(s @ Wu[g]^T) for the 4 branches of a column block, gate = sigmoid(u_g), and
out = bf16(sum_g(gate * xn_g) * (1/hc)) -- the same rounding points as the compiled chain (bf16 GEMM outputs).
"""
from __future__ import annotations

import torch
import triton
import triton.language as tl


@triton.jit
def _kf_hc_up_kernel(
    t_ptr, xn_ptr, wu_ptr, out_ptr, M, inv_hc,
    stride_tm, stride_xm, stride_om,
    LR: tl.constexpr, HC: tl.constexpr, HS: tl.constexpr,
    BLOCK_M: tl.constexpr, BLOCK_J: tl.constexpr, BLOCK_R: tl.constexpr,
):
    pid = tl.program_id(0)
    rj = pid * BLOCK_J + tl.arange(0, BLOCK_J)
    rm = tl.arange(0, BLOCK_M)
    rr = tl.arange(0, BLOCK_R)
    m_mask = rm < M
    acc0 = tl.zeros((BLOCK_J, BLOCK_M), tl.float32)
    acc1 = tl.zeros((BLOCK_J, BLOCK_M), tl.float32)
    acc2 = tl.zeros((BLOCK_J, BLOCK_M), tl.float32)
    acc3 = tl.zeros((BLOCK_J, BLOCK_M), tl.float32)
    for r0 in tl.static_range(0, LR, BLOCK_R):
        r = r0 + rr
        t = tl.load(t_ptr + rm[None, :] * stride_tm + r[:, None], mask=m_mask[None, :], other=0.0).to(tl.float32)
        a = t * inv_hc
        s = (a * tl.sigmoid(a)).to(tl.bfloat16)  # [BLOCK_R, BLOCK_M]
        w0 = tl.load(wu_ptr + (0 * HS + rj)[:, None] * LR + r[None, :])
        acc0 = tl.dot(w0, s, acc0)
        w1 = tl.load(wu_ptr + (1 * HS + rj)[:, None] * LR + r[None, :])
        acc1 = tl.dot(w1, s, acc1)
        w2 = tl.load(wu_ptr + (2 * HS + rj)[:, None] * LR + r[None, :])
        acc2 = tl.dot(w2, s, acc2)
        w3 = tl.load(wu_ptr + (3 * HS + rj)[:, None] * LR + r[None, :])
        acc3 = tl.dot(w3, s, acc3)
    xb = xn_ptr + rm[None, :] * stride_xm + rj[:, None]
    xm = m_mask[None, :]
    o = tl.sigmoid(acc0.to(tl.bfloat16).to(tl.float32)) * tl.load(xb + 0 * HS, mask=xm, other=0.0).to(tl.float32)
    o += tl.sigmoid(acc1.to(tl.bfloat16).to(tl.float32)) * tl.load(xb + 1 * HS, mask=xm, other=0.0).to(tl.float32)
    o += tl.sigmoid(acc2.to(tl.bfloat16).to(tl.float32)) * tl.load(xb + 2 * HS, mask=xm, other=0.0).to(tl.float32)
    o += tl.sigmoid(acc3.to(tl.bfloat16).to(tl.float32)) * tl.load(xb + 3 * HS, mask=xm, other=0.0).to(tl.float32)
    o = o * inv_hc
    tl.store(out_ptr + rm[None, :] * stride_om + rj[:, None], o.to(tl.bfloat16), mask=xm)


def hc_mix_fused(xn, w_down, w_up, hc, hs, down_fn, block_j=16, block_r=64, warps=4, stages=2):
    """xn [M, hc*hs] bf16 (normed), w_down [lr, hc*hs], w_up [hc*hs, lr] -> [M, hs] bf16.
    down_fn(x, w) -> bf16 [M, lr] (the deterministic skinny GEMM)."""
    assert hc == 4
    m = xn.shape[0]
    lr = w_down.shape[0]
    t = down_fn(xn, w_down)
    out = torch.empty((m, hs), dtype=torch.bfloat16, device=xn.device)
    _kf_hc_up_kernel[(triton.cdiv(hs, block_j),)](
        t, xn, w_up, out, m, 1.0 / hc, t.stride(0), xn.stride(0), out.stride(0),
        LR=lr, HC=hc, HS=hs, BLOCK_M=max(16, triton.next_power_of_2(m)), BLOCK_J=block_j, BLOCK_R=block_r,
        num_warps=warps, num_stages=stages)
    return out
