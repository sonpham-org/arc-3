"""QSA sparse attention as fused Triton kernels (training: forward + backward).

Author: Claude Opus 5.5 (4-Oct-2026). The 4-Oct layer bench put the 12 indexed-attention layers at ~73% of a
115k-token training step (19.8 s fwd+bwd per layer), almost all of it in fast_qsa.sparse_attention's gathered copies
(float32 index_select of keys/values per 256-query chunk, float32 bmm, atomic index_add in backward). FlexAttention
was exact at 32k but dense-equivalent (the picks of 128 neighbouring queries cover every key tile) and overflowed
int32 indexing at 115k. Here every query reads only its own picks, straight from K/V:

  forward   one program per (query token, KV head): the token's G = H / KVH query heads ([16, D] with padding) walk its
            pick list (T <= 2051 key positions, -1 = empty) in BLOCK_N chunks: gathered K rows, s = q k^T (BF16 tensor
            cores, float32 accumulation), online softmax, o += p v. Writes O and the log-sum-exp.
  backward  same walk: dq accumulates in registers; dK / dV chunks (p^T dO, ds^T q) go to float32 buffers by atomic
            add (several queries pick the same keys), cast to the key/value dtype at the end.
Same picks, same math as the gather path; BF16 products with float32 accumulation instead of float32 throughout.
test_qsa_kernel.py compares both on random inputs (outputs and all three gradients).
"""
from __future__ import annotations

import os

import torch
import triton
import triton.language as tl

SEM = tl.constexpr(os.environ.get("ARC3_QSA_ATOMIC_SEM", "relaxed"))   # dK / dV atomics; "acq_rel" = Triton default
NEG = tl.constexpr(-1.0e30)                       # finite "minus infinity": no NaN when a whole chunk is empty


@triton.jit
def _qsa_fwd(Q, K, V, IDX, O, LSE, scale,
             s_qs, s_qh, s_ks, s_kh, s_vs, s_vh, s_os, s_oh, s_is, s_ls,
             T, G: tl.constexpr, GP: tl.constexpr, D: tl.constexpr, BLOCK_N: tl.constexpr):
    t = tl.program_id(0)
    h = tl.program_id(1)
    offs_g = tl.arange(0, GP)
    offs_d = tl.arange(0, D)
    gmask = offs_g < G
    heads = h * G + offs_g
    q = tl.load(Q + t * s_qs + heads[:, None] * s_qh + offs_d[None, :], mask=gmask[:, None], other=0.0)
    m_i = tl.full([GP], NEG, tl.float32)
    l_i = tl.zeros([GP], tl.float32)
    acc = tl.zeros([GP, D], tl.float32)
    for start in range(0, T, BLOCK_N):
        offs_n = start + tl.arange(0, BLOCK_N)
        kid = tl.load(IDX + t * s_is + offs_n, mask=offs_n < T, other=-1)
        valid = kid >= 0
        kc = tl.where(valid, kid, 0).to(tl.int64)
        k = tl.load(K + kc[:, None] * s_ks + h * s_kh + offs_d[None, :], mask=valid[:, None], other=0.0)
        s = tl.dot(q, tl.trans(k)) * scale
        s = tl.where(valid[None, :], s, NEG)
        m_new = tl.maximum(m_i, tl.max(s, 1))
        alpha = tl.exp(m_i - m_new)
        p = tl.exp(s - m_new[:, None])
        p = tl.where(valid[None, :], p, 0.0)
        l_i = l_i * alpha + tl.sum(p, 1)
        v = tl.load(V + kc[:, None] * s_vs + h * s_vh + offs_d[None, :], mask=valid[:, None], other=0.0)
        acc = acc * alpha[:, None] + tl.dot(p.to(v.dtype), v)
        m_i = m_new
    l_safe = tl.where(l_i > 0, l_i, 1.0)
    o = acc / l_safe[:, None]
    tl.store(O + t * s_os + heads[:, None] * s_oh + offs_d[None, :], o.to(O.dtype.element_ty), mask=gmask[:, None])
    tl.store(LSE + t * s_ls + heads, m_i + tl.log(l_safe), mask=gmask)


@triton.jit
def _qsa_bwd(Q, K, V, IDX, DO, LSE, DELTA, DQ, DK, DV, scale,
             s_qs, s_qh, s_ks, s_kh, s_vs, s_vh, s_dos, s_doh, s_is, s_ls, s_dqs, s_dqh, s_dks, s_dkh,
             T, G: tl.constexpr, GP: tl.constexpr, D: tl.constexpr, BLOCK_N: tl.constexpr):
    t = tl.program_id(0)
    h = tl.program_id(1)
    offs_g = tl.arange(0, GP)
    offs_d = tl.arange(0, D)
    gmask = offs_g < G
    heads = h * G + offs_g
    q = tl.load(Q + t * s_qs + heads[:, None] * s_qh + offs_d[None, :], mask=gmask[:, None], other=0.0)
    do = tl.load(DO + t * s_dos + heads[:, None] * s_doh + offs_d[None, :], mask=gmask[:, None], other=0.0)
    lse = tl.load(LSE + t * s_ls + heads, mask=gmask, other=0.0)
    delta = tl.load(DELTA + t * s_ls + heads, mask=gmask, other=0.0)
    dq = tl.zeros([GP, D], tl.float32)
    for start in range(0, T, BLOCK_N):
        offs_n = start + tl.arange(0, BLOCK_N)
        kid = tl.load(IDX + t * s_is + offs_n, mask=offs_n < T, other=-1)
        valid = kid >= 0
        kc = tl.where(valid, kid, 0).to(tl.int64)
        k = tl.load(K + kc[:, None] * s_ks + h * s_kh + offs_d[None, :], mask=valid[:, None], other=0.0)
        v = tl.load(V + kc[:, None] * s_vs + h * s_vh + offs_d[None, :], mask=valid[:, None], other=0.0)
        s = tl.dot(q, tl.trans(k)) * scale
        p = tl.exp(s - lse[:, None])
        p = tl.where(valid[None, :] & gmask[:, None], p, 0.0)
        dp = tl.dot(do, tl.trans(v))
        ds = p * (dp - delta[:, None])
        dq += tl.dot(ds.to(k.dtype), k)
        dv_c = tl.dot(tl.trans(p.to(do.dtype)), do)
        dk_c = tl.dot(tl.trans(ds.to(q.dtype)), q) * scale
        # relaxed: these adds only accumulate (nothing reads dK / dV until the kernel ends); the default acq_rel
        # semantics fence every add
        tl.atomic_add(DV + kc[:, None] * s_dks + h * s_dkh + offs_d[None, :], dv_c, mask=valid[:, None], sem=SEM)
        tl.atomic_add(DK + kc[:, None] * s_dks + h * s_dkh + offs_d[None, :], dk_c, mask=valid[:, None], sem=SEM)
    tl.store(DQ + t * s_dqs + heads[:, None] * s_dqh + offs_d[None, :], (dq * scale).to(DQ.dtype.element_ty),
             mask=gmask[:, None])


def _cfg(d: int) -> dict:
    return {"BLOCK_N": 64 if d <= 128 else 32, "num_warps": 4, "num_stages": 1}


def qsa_forward(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, idx: torch.Tensor, scale: float):
    """q [S, H, D], k/v [S, KVH, D] (contiguous in D), idx [S, T] int32 -> o [S, H, D], lse [S, H] float32."""
    s_len, h, d = q.shape
    kvh = k.shape[1]
    g = h // kvh
    gp = max(16, triton.next_power_of_2(g))
    o = torch.empty_like(q)
    lse = torch.empty(s_len, h, dtype=torch.float32, device=q.device)
    c = _cfg(d)
    with torch.cuda.device(q.device):           # a model split over GPUs: launch on the tensors' GPU, not cuda:0
        _launch_fwd(q, k, v, idx, o, lse, scale, s_len, kvh, g, gp, d, c)
    return o, lse


def _launch_fwd(q, k, v, idx, o, lse, scale, s_len, kvh, g, gp, d, c):
    _qsa_fwd[(s_len, kvh)](q, k, v, idx, o, lse, scale,
                           q.stride(0), q.stride(1), k.stride(0), k.stride(1), v.stride(0), v.stride(1),
                           o.stride(0), o.stride(1), idx.stride(0), lse.stride(0),
                           idx.shape[1], G=g, GP=gp, D=d, BLOCK_N=c["BLOCK_N"], num_warps=c["num_warps"],
                           num_stages=c["num_stages"])


def qsa_backward(q, k, v, idx, o, lse, do, scale):
    s_len, h, d = q.shape
    kvh = k.shape[1]
    g = h // kvh
    gp = max(16, triton.next_power_of_2(g))
    do = do.contiguous()
    delta = (do.float() * o.float()).sum(-1).contiguous()                  # [S, H]
    dq = torch.empty_like(q)
    dk = torch.zeros(k.shape, dtype=torch.float32, device=k.device)
    dv = torch.zeros(v.shape, dtype=torch.float32, device=v.device)
    c = _cfg(d)
    with torch.cuda.device(q.device):
        _qsa_bwd[(s_len, kvh)](q, k, v, idx, do, lse, delta, dq, dk, dv, scale,
                               q.stride(0), q.stride(1), k.stride(0), k.stride(1), v.stride(0), v.stride(1),
                               do.stride(0), do.stride(1), idx.stride(0), lse.stride(0), dq.stride(0), dq.stride(1),
                               dk.stride(0), dk.stride(1),
                               idx.shape[1], G=g, GP=gp, D=d, BLOCK_N=c["BLOCK_N"], num_warps=c["num_warps"],
                               num_stages=c["num_stages"])
    return dq, dk.to(k.dtype), dv.to(v.dtype)


class QSAAttention(torch.autograd.Function):
    @staticmethod
    def forward(ctx, q, k, v, idx, scale):
        q, k, v = q.contiguous(), k.contiguous(), v.contiguous()
        o, lse = qsa_forward(q, k, v, idx, scale)
        ctx.save_for_backward(q, k, v, idx, o, lse)
        ctx.scale = scale
        return o

    @staticmethod
    def backward(ctx, do):
        q, k, v, idx, o, lse = ctx.saved_tensors
        dq, dk, dv = qsa_backward(q, k, v, idx, o, lse, do, ctx.scale)
        return dq, dk, dv, None, None


def sparse_attention(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, idx: torch.Tensor, scale: float) -> torch.Tensor:
    """Drop-in for fast_qsa.sparse_attention: q [1, H, S, D], k/v [1, KVH, S, D] (rope applied), idx [S, T] int32
    -> [1, S, H, D]."""
    qs = q[0].transpose(0, 1)                     # [S, H, D]
    ks = k[0].transpose(0, 1)
    vs = v[0].transpose(0, 1)
    return QSAAttention.apply(qs, ks, vs, idx.contiguous(), scale).unsqueeze(0)
