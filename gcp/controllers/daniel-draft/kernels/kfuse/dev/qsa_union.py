"""daniel-draft kfuse (3-Oct-2026): QSA verify decode with each request's selected NVFP4 rows unpacked ONCE.

The W verify rows of one request (request-major layout: rows g*W .. g*W+W-1) select heavily overlapping positions.
U1 (mark): per row, every valid selected position p sets bit (1 << j) in masks[g, p] (atomic OR; j = row - g*W).
U2 (compact): per group, positions with a nonzero mask are compacted (ascending) into union[g, :] / umask[g, :]
          with their row bits, and the mask array is cleared again (CUDA-graph safe).
U3 (attend): per (group, kv head, split) the union positions are unpacked once (exact qsakv4 arithmetic) and used by
          all W*12 query heads of the group; row j only sees positions whose bit j is set, so every row attends to
          exactly its own selected set (the per-row kernel's set). Splits combine by the last to finish (fixed order).
"""
from __future__ import annotations

import torch
import triton
import triton.language as tl

from qsa_fused import _kf_unpack_v2


@triton.jit
def _kfu_mark_kernel(masks_ptr, topk_idx, seq_lens, valid_counts, idx_stride, max_pos,
                     W: tl.constexpr, BLOCK: tl.constexpr):
    row = tl.program_id(0)
    g = row // W
    j = row - g * W
    cols = tl.arange(0, BLOCK)
    length = tl.load(seq_lens + row)
    vcount = tl.load(valid_counts + row)
    pos = tl.load(topk_idx + row * idx_stride + cols, mask=cols < vcount, other=-1)
    valid = (cols < vcount) & (pos >= 0) & (pos < length)
    tl.atomic_or(masks_ptr + g.to(tl.int64) * max_pos + pos, (1 << j), mask=valid, sem="relaxed")


@triton.jit
def _kfu_compact_kernel(masks_ptr, union_ptr, umask_ptr, ucount_ptr, seq_lens, max_pos, max_union,
                        W: tl.constexpr, WP: tl.constexpr, CHUNK: tl.constexpr):
    g = tl.program_id(0)
    # the group's rows see positions < max(seq_len over its rows)
    rr = tl.arange(0, WP)
    lim = tl.max(tl.load(seq_lens + g * W + rr, mask=rr < W, other=0), 0)
    base = masks_ptr + g.to(tl.int64) * max_pos
    offs = tl.arange(0, CHUNK)
    n = 0
    for c in range(0, lim, CHUNK):
        p = c + offs
        pm = p < lim
        m = tl.load(base + p, mask=pm, other=0, cache_modifier=".cg")
        sel = m != 0
        idx = n + tl.cumsum(sel.to(tl.int32), 0) - 1
        ok = sel & (idx < max_union)
        tl.store(union_ptr + g * max_union + idx, p, mask=ok)
        tl.store(umask_ptr + g * max_union + idx, m, mask=ok)
        tl.store(base + p, 0, mask=sel)
        n += tl.sum(sel.to(tl.int32), 0)
    tl.store(ucount_ptr + g, tl.minimum(n, max_union))


@triton.jit
def _kfu_attend_kernel(
    q_ptr, out_ptr, ws_ptr, cnt_ptr,
    k_packed, v_packed, k_scales, v_scales, k_gs, v_gs,
    req_to_token, row_req, union_ptr, umask_ptr, ucount_ptr, max_union,
    sm_scale, stride_qr, stride_qh, stride_or, stride_oh, req_stride,
    W: tl.constexpr, HEADS_KV: tl.constexpr, GROUP: tl.constexpr, QP: tl.constexpr, HALF: tl.constexpr,
    BLOCK_N: tl.constexpr, SPLITS: tl.constexpr, NTHREADS: tl.constexpr, ROUND_FP8: tl.constexpr,
):
    g = tl.program_id(0)
    kvh = tl.program_id(1)
    sp = tl.program_id(2)
    qr = tl.arange(0, QP)              # q-row r = j * GROUP + h
    jr = qr // GROUP
    hr = qr - jr * GROUP
    rvalid = jr < W
    row = g * W + jr
    hq = kvh * GROUP + hr
    pairs = tl.arange(0, HALF)
    grp = tl.arange(0, HALF // 8)
    q_base = q_ptr + row[:, None] * stride_qr + hq[:, None] * stride_qh + 2 * pairs[None, :]
    q_even = tl.load(q_base, mask=rvalid[:, None], other=0.0)
    q_odd = tl.load(q_base + 1, mask=rvalid[:, None], other=0.0)
    req = tl.load(row_req + g * W).to(tl.int64)
    ucount = tl.load(ucount_ptr + g)
    per = tl.cdiv(tl.cdiv(ucount, SPLITS), BLOCK_N) * BLOCK_N
    c_lo = sp * per
    c_hi = tl.minimum(c_lo + per, ucount)
    m_i = tl.full([QP], float("-inf"), tl.float32)
    l_i = tl.zeros([QP], tl.float32)
    acc_e = tl.zeros([QP, HALF], tl.float32)
    acc_o = tl.zeros([QP, HALF], tl.float32)
    offs = tl.arange(0, BLOCK_N)
    for c in range(c_lo, c_hi, BLOCK_N):
        cols = c + offs
        cm = cols < c_hi
        pos = tl.load(union_ptr + g * max_union + cols, mask=cm, other=0)
        um = tl.load(umask_ptr + g * max_union + cols, mask=cm, other=0)
        slot = tl.load(req_to_token + req * req_stride + pos, mask=cm, other=0).to(tl.int64)
        k_lo, k_hi = _kf_unpack_v2(k_packed, k_scales, k_gs, slot, cm, kvh, pairs, grp, HEADS_KV, HALF,
                                   BLOCK_N, ROUND_FP8)
        s = tl.dot(q_even, tl.trans(k_lo)) + tl.dot(q_odd, tl.trans(k_hi))
        s = s * sm_scale
        allowed = ((um[None, :] >> jr[:, None]) & 1) != 0
        allowed = allowed & cm[None, :] & rvalid[:, None]
        s = tl.where(allowed, s, float("-inf"))
        m_new = tl.maximum(m_i, tl.max(s, 1))
        m_safe = tl.where(m_new == float("-inf"), 0.0, m_new)
        alpha = tl.exp(m_i - m_safe)
        p = tl.exp(s - m_safe[:, None])
        p_bf = p.to(tl.bfloat16)
        l_i = l_i * alpha + tl.sum(p_bf.to(tl.float32), 1)
        v_lo, v_hi = _kf_unpack_v2(v_packed, v_scales, v_gs, slot, cm, kvh, pairs, grp, HEADS_KV, HALF,
                                   BLOCK_N, ROUND_FP8)
        acc_e = acc_e * alpha[:, None] + tl.dot(p_bf, v_lo)
        acc_o = acc_o * alpha[:, None] + tl.dot(p_bf, v_hi)
        m_i = m_new
    o_base = out_ptr + row[:, None] * stride_or + hq[:, None] * stride_oh + 2 * pairs[None, :]
    PART: tl.constexpr = QP * (2 + 2 * HALF)
    base = ws_ptr + ((g * HEADS_KV + kvh) * SPLITS).to(tl.int64) * PART
    mine = base + sp * PART
    tl.store(mine + qr, m_i, cache_modifier=".cg")
    tl.store(mine + QP + qr, l_i, cache_modifier=".cg")
    a_off = 2 * QP + qr[:, None] * HALF + pairs[None, :]
    tl.store(mine + a_off, acc_e, cache_modifier=".cg")
    tl.store(mine + QP * HALF + a_off, acc_o, cache_modifier=".cg")
    _f = tl.inline_asm_elementwise("fence.acq_rel.gpu;\n\tmov.u32 $0, $1;", "=r,r", [tl.arange(0, NTHREADS)],
                                   dtype=tl.int32, is_pure=False, pack=1)
    tl.debug_barrier()
    ctr = cnt_ptr + g * HEADS_KV + kvh
    arrived = tl.atomic_add(ctr, 1, sem="acq_rel", scope="gpu")
    if arrived == SPLITS - 1:
        _g2 = tl.inline_asm_elementwise("fence.acq_rel.gpu;\n\tmov.u32 $0, $1;", "=r,r", [tl.arange(0, NTHREADS)],
                                        dtype=tl.int32, is_pure=False, pack=1)
        m_all = tl.full([QP], float("-inf"), tl.float32)
        for s_ in range(0, SPLITS):
            m_all = tl.maximum(m_all, tl.load(base + s_ * PART + qr, cache_modifier=".cg"))
        m_all_safe = tl.where(m_all == float("-inf"), 0.0, m_all)
        l_tot = tl.zeros([QP], tl.float32)
        o_e = tl.zeros([QP, HALF], tl.float32)
        o_o = tl.zeros([QP, HALF], tl.float32)
        for s_ in range(0, SPLITS):
            part = base + s_ * PART
            w = tl.exp(tl.load(part + qr, cache_modifier=".cg") - m_all_safe)
            l_tot += w * tl.load(part + QP + qr, cache_modifier=".cg")
            o_e += w[:, None] * tl.load(part + a_off, cache_modifier=".cg")
            o_o += w[:, None] * tl.load(part + QP * HALF + a_off, cache_modifier=".cg")
        inv = tl.where(l_tot > 0, 1.0 / l_tot, 0.0)
        tl.store(o_base, (o_e * inv[:, None]).to(tl.bfloat16), mask=rvalid[:, None])
        tl.store(o_base + 1, (o_o * inv[:, None]).to(tl.bfloat16), mask=rvalid[:, None])
        tl.atomic_xchg(ctr, 0, sem="relaxed", scope="gpu")


_KFU = {}


def qsa_nvfp4_union_decode(q, nvfp4, req_to_token, row_req, topk_indices, seq_lens, valid_counts, sm_scale, W,
                           max_pos, round_fp8=True, splits=8, block_n=32, warps=8, stages=2, capacity_groups=None):
    """Verify rows in request-major groups of W. max_pos: bound on positions (>= every seq_len)."""
    k_packed = nvfp4[0]
    rows, hq, d = q.shape
    assert rows % W == 0
    groups = rows // W
    heads_kv, half = k_packed.shape[1], k_packed.shape[2]
    group = hq // heads_kv
    qp = triton.next_power_of_2(W * group)
    topk = topk_indices.shape[1]
    max_union = W * topk
    capg = max(groups, capacity_groups or groups)
    key = (q.device, W, heads_kv, qp, half, splits, max_pos, topk)
    st = _KFU.get(key)
    if st is None or st["cap"] < capg:
        st = dict(cap=capg,
                  masks=torch.zeros(capg * max_pos, dtype=torch.int32, device=q.device),
                  union=torch.empty(capg * max_union, dtype=torch.int32, device=q.device),
                  umask=torch.empty(capg * max_union, dtype=torch.int32, device=q.device),
                  ucount=torch.empty(capg, dtype=torch.int32, device=q.device),
                  ws=torch.empty(capg * heads_kv * splits * qp * (2 + 2 * half), dtype=torch.float32, device=q.device),
                  cnt=torch.zeros(capg * heads_kv, dtype=torch.int32, device=q.device))
        _KFU[key] = st
    out = torch.empty_like(q)
    _kfu_mark_kernel[(rows,)](st["masks"], topk_indices, seq_lens, valid_counts, topk_indices.stride(0), max_pos,
                              W=W, BLOCK=triton.next_power_of_2(topk), num_warps=8)
    _kfu_compact_kernel[(groups,)](st["masks"], st["union"], st["umask"], st["ucount"], seq_lens, max_pos, max_union,
                                   W=W, WP=triton.next_power_of_2(W), CHUNK=4096, num_warps=8)
    k_packed, v_packed, k_scales, v_scales, k_gs, v_gs = nvfp4
    _kfu_attend_kernel[(groups, heads_kv, splits)](
        q, out, st["ws"], st["cnt"], k_packed, v_packed, k_scales, v_scales, k_gs, v_gs,
        req_to_token, row_req, st["union"], st["umask"], st["ucount"], max_union,
        float(sm_scale), q.stride(0), q.stride(1), out.stride(0), out.stride(1), req_to_token.stride(0),
        W=W, HEADS_KV=heads_kv, GROUP=group, QP=qp, HALF=half, BLOCK_N=block_n, SPLITS=splits,
        NTHREADS=32 * warps, ROUND_FP8=round_fp8, num_warps=warps, num_stages=stages)
    return out
