"""daniel-draft kfuse8 (4-Oct-2026): QSA sparse decode straight from an fp8_e4m3 KV pool (no scratch, no XQA).

Today (his fork, fp8 KV): per decode / verify row the ~2,050 selected K/V rows are copied into a page-aligned FP8
scratch (_compact_kv) and FlashInfer XQA (kernel_mha) reads the scratch. These kernels read the pool rows directly:
fp8 -> bf16 is exact, then XQA's math: bf16 Q x bf16 K with fp32 accumulation, scale, online softmax, P rounded to
bf16 for P x V and for the row sum, fp32 accumulation; splits combined by the last split to finish (fixed order).

  qsa_fp8_fused_decode   one program per (row, kv head, split)
  qsa_fp8_union_decode   gather-once: one program per (request, kv head, split, V-dim half) over the union of the
                         request's W verify rows' selections (rows in request-major groups of W); row j only sees
                         positions whose bit j is set, i.e. exactly its own selected set.
"""
from __future__ import annotations

import torch
import triton
import triton.language as tl


@triton.jit
def _k8_fence(NTHREADS: tl.constexpr):
    return tl.inline_asm_elementwise("fence.acq_rel.gpu;\n\tmov.u32 $0, $1;", "=r,r", [tl.arange(0, NTHREADS)],
                                     dtype=tl.int32, is_pure=False, pack=1)


@triton.jit
def _k8_combine(ws_ptr, cnt_ptr, ctr_idx, base, qr, dd, m_i, l_i, acc, o_ptrs, o_mask, sp,
                SPLITS: tl.constexpr, QP: tl.constexpr, DV: tl.constexpr, NTHREADS: tl.constexpr):
    PART: tl.constexpr = QP * (2 + DV)
    mine = base + sp * PART
    a_off = 2 * QP + qr[:, None] * DV + dd[None, :]
    tl.store(mine + qr, m_i, cache_modifier=".cg")
    tl.store(mine + QP + qr, l_i, cache_modifier=".cg")
    tl.store(mine + a_off, acc, cache_modifier=".cg")
    _f = _k8_fence(NTHREADS)
    tl.debug_barrier()
    ctr = cnt_ptr + ctr_idx
    arrived = tl.atomic_add(ctr, 1, sem="acq_rel", scope="gpu")
    if arrived == SPLITS - 1:
        _g = _k8_fence(NTHREADS)
        m_all = tl.full([QP], float("-inf"), tl.float32)
        for s_ in range(0, SPLITS):
            m_all = tl.maximum(m_all, tl.load(base + s_ * PART + qr, cache_modifier=".cg"))
        m_safe = tl.where(m_all == float("-inf"), 0.0, m_all)
        l_tot = tl.zeros([QP], tl.float32)
        o = tl.zeros([QP, DV], tl.float32)
        for s_ in range(0, SPLITS):
            part = base + s_ * PART
            w = tl.exp(tl.load(part + qr, cache_modifier=".cg") - m_safe)
            l_tot += w * tl.load(part + QP + qr, cache_modifier=".cg")
            o += w[:, None] * tl.load(part + a_off, cache_modifier=".cg")
        inv = tl.where(l_tot > 0, 1.0 / l_tot, 0.0)
        tl.store(o_ptrs, (o * inv[:, None]).to(tl.bfloat16), mask=o_mask)
        tl.atomic_xchg(ctr, 0, sem="relaxed", scope="gpu")


@triton.jit
def _k8_fused_kernel(
    q_ptr, out_ptr, ws_ptr, cnt_ptr, k_buf, v_buf,
    req_to_token, row_req, topk_idx, seq_lens, valid_counts,
    sm_scale, stride_qr, stride_qh, stride_or, stride_oh, req_stride, idx_stride, cols_per_split,
    HEADS_KV: tl.constexpr, GROUP: tl.constexpr, QP: tl.constexpr, D: tl.constexpr,
    BLOCK_N: tl.constexpr, SPLITS: tl.constexpr, NTHREADS: tl.constexpr,
):
    row = tl.program_id(0)
    kvh = tl.program_id(1)
    sp = tl.program_id(2)
    qr = tl.arange(0, QP)
    hmask = qr < GROUP
    hq = kvh * GROUP + qr
    dd = tl.arange(0, D)
    q = tl.load(q_ptr + row * stride_qr + hq[:, None] * stride_qh + dd[None, :], mask=hmask[:, None], other=0.0)
    length = tl.load(seq_lens + row)
    req = tl.load(row_req + row).to(tl.int64)
    vcount = tl.load(valid_counts + row)
    m_i = tl.full([QP], float("-inf"), tl.float32)
    l_i = tl.zeros([QP], tl.float32)
    acc = tl.zeros([QP, D], tl.float32)
    c_lo = sp * cols_per_split
    c_hi = tl.minimum(c_lo + cols_per_split, vcount)
    offs = tl.arange(0, BLOCK_N)
    for c in range(c_lo, c_hi, BLOCK_N):
        cols = c + offs
        cm = cols < c_hi
        pos = tl.load(topk_idx + row * idx_stride + cols, mask=cm, other=-1)
        valid = cm & (pos >= 0) & (pos < length)
        slot = tl.load(req_to_token + req * req_stride + tl.where(valid, pos, 0), mask=valid, other=0).to(tl.int64)
        src = slot[:, None] * (HEADS_KV * D) + kvh * D + dd[None, :]
        k = tl.load(k_buf + src, mask=valid[:, None], other=0.0).to(tl.bfloat16)
        s = tl.dot(q, tl.trans(k)) * sm_scale
        s = tl.where(valid[None, :], s, float("-inf"))
        m_new = tl.maximum(m_i, tl.max(s, 1))
        m_safe = tl.where(m_new == float("-inf"), 0.0, m_new)
        alpha = tl.exp(m_i - m_safe)
        p_bf = tl.exp(s - m_safe[:, None]).to(tl.bfloat16)
        l_i = l_i * alpha + tl.sum(p_bf.to(tl.float32), 1)
        v = tl.load(v_buf + src, mask=valid[:, None], other=0.0).to(tl.bfloat16)
        acc = acc * alpha[:, None] + tl.dot(p_bf, v)
        m_i = m_new
    o_ptrs = out_ptr + row * stride_or + hq[:, None] * stride_oh + dd[None, :]
    if SPLITS == 1:
        inv = tl.where(l_i > 0, 1.0 / l_i, 0.0)
        tl.store(o_ptrs, (acc * inv[:, None]).to(tl.bfloat16), mask=hmask[:, None])
    else:
        base = ws_ptr + ((row * HEADS_KV + kvh) * SPLITS).to(tl.int64) * (QP * (2 + D))
        _k8_combine(ws_ptr, cnt_ptr, row * HEADS_KV + kvh, base, qr, dd, m_i, l_i, acc, o_ptrs, hmask[:, None], sp,
                    SPLITS, QP, D, NTHREADS)


_K8_WS = {}


def _k8_ws(device, key, nparts, part_elems, nctr):
    st = _K8_WS.get(key)
    if st is None or st[1].numel() < nctr:
        st = (torch.empty(nparts * part_elems, dtype=torch.float32, device=device),
              torch.zeros(nctr, dtype=torch.int32, device=device))
        _K8_WS[key] = st
    return st


def qsa_fp8_fused_decode(q, k_buf, v_buf, req_to_token, row_req, topk_indices, seq_lens, valid_counts, sm_scale,
                         splits=8, block_n=32, warps=4, stages=2, capacity_rows=None):
    rows, hq, d = q.shape
    heads_kv = k_buf.shape[1]
    assert k_buf.shape[2] == d and hq % heads_kv == 0 and q.stride(2) == 1
    group = hq // heads_kv
    qp = max(16, triton.next_power_of_2(group))
    topk = topk_indices.shape[1]
    out = torch.empty_like(q)
    cols = triton.cdiv(triton.cdiv(topk, splits), block_n) * block_n
    cap = max(rows, capacity_rows or rows)
    ws, cnt = _k8_ws(q.device, ("row", heads_kv, qp, d, splits), cap * heads_kv * splits, qp * (2 + d), cap * heads_kv)
    _k8_fused_kernel[(rows, heads_kv, splits)](
        q, out, ws, cnt, k_buf, v_buf, req_to_token, row_req, topk_indices, seq_lens, valid_counts, float(sm_scale),
        q.stride(0), q.stride(1), out.stride(0), out.stride(1), req_to_token.stride(0), topk_indices.stride(0), cols,
        HEADS_KV=heads_kv, GROUP=group, QP=qp, D=d, BLOCK_N=block_n, SPLITS=splits, NTHREADS=32 * warps,
        num_warps=warps, num_stages=stages)
    return out


# ------------------------------------------------------------------------------------------------- gather-once
@triton.jit
def _k8u_mark_kernel(masks_ptr, topk_idx, seq_lens, valid_counts, idx_stride, max_pos,
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
def _k8u_compact_kernel(masks_ptr, union_ptr, umask_ptr, ucount_ptr, seq_lens, max_pos, max_union,
                        W: tl.constexpr, WP: tl.constexpr, CHUNK: tl.constexpr):
    g = tl.program_id(0)
    rr = tl.arange(0, WP)
    lim = tl.max(tl.load(seq_lens + g * W + rr, mask=rr < W, other=0), 0)
    base = masks_ptr + g.to(tl.int64) * max_pos
    offs = tl.arange(0, CHUNK)
    n = 0
    for c in range(0, lim, CHUNK):
        p = c + offs
        m = tl.load(base + p, mask=p < lim, other=0, cache_modifier=".cg")
        sel = m != 0
        idx = n + tl.cumsum(sel.to(tl.int32), 0) - 1
        ok = sel & (idx < max_union)
        tl.store(union_ptr + g * max_union + idx, p, mask=ok)
        tl.store(umask_ptr + g * max_union + idx, m, mask=ok)
        tl.store(base + p, 0, mask=sel)
        n += tl.sum(sel.to(tl.int32), 0)
    tl.store(ucount_ptr + g, tl.minimum(n, max_union))


@triton.jit
def _k8u_attend_kernel(
    q_ptr, out_ptr, ws_ptr, cnt_ptr, k_buf, v_buf, req_to_token, row_req,
    union_ptr, umask_ptr, ucount_ptr, max_union,
    sm_scale, stride_qr, stride_qh, stride_or, stride_oh, req_stride,
    W: tl.constexpr, HEADS_KV: tl.constexpr, GROUP: tl.constexpr, QP: tl.constexpr, D: tl.constexpr,
    DSPLIT: tl.constexpr, BLOCK_N: tl.constexpr, SPLITS: tl.constexpr, NTHREADS: tl.constexpr,
):
    g = tl.program_id(0)
    kvh_ds = tl.program_id(1)
    kvh = kvh_ds // DSPLIT
    ds = kvh_ds - kvh * DSPLIT
    sp = tl.program_id(2)
    DV: tl.constexpr = D // DSPLIT
    qr = tl.arange(0, QP)
    jr = qr // GROUP
    hr = qr - jr * GROUP
    rvalid = jr < W
    row = g * W + jr
    hq = kvh * GROUP + hr
    dd = tl.arange(0, D)
    dv = ds * DV + tl.arange(0, DV)
    q = tl.load(q_ptr + row[:, None] * stride_qr + hq[:, None] * stride_qh + dd[None, :], mask=rvalid[:, None], other=0.0)
    req = tl.load(row_req + g * W).to(tl.int64)
    ucount = tl.load(ucount_ptr + g)
    per = tl.cdiv(tl.cdiv(ucount, SPLITS), BLOCK_N) * BLOCK_N
    c_lo = sp * per
    c_hi = tl.minimum(c_lo + per, ucount)
    m_i = tl.full([QP], float("-inf"), tl.float32)
    l_i = tl.zeros([QP], tl.float32)
    acc = tl.zeros([QP, DV], tl.float32)
    offs = tl.arange(0, BLOCK_N)
    for c in range(c_lo, c_hi, BLOCK_N):
        cols = c + offs
        cm = cols < c_hi
        pos = tl.load(union_ptr + g * max_union + cols, mask=cm, other=0)
        um = tl.load(umask_ptr + g * max_union + cols, mask=cm, other=0)
        slot = tl.load(req_to_token + req * req_stride + pos, mask=cm, other=0).to(tl.int64)
        rowbase = slot[:, None] * (HEADS_KV * D) + kvh * D
        k = tl.load(k_buf + rowbase + dd[None, :], mask=cm[:, None], other=0.0).to(tl.bfloat16)
        s = tl.dot(q, tl.trans(k)) * sm_scale
        allowed = (((um[None, :] >> jr[:, None]) & 1) != 0) & cm[None, :] & rvalid[:, None]
        s = tl.where(allowed, s, float("-inf"))
        m_new = tl.maximum(m_i, tl.max(s, 1))
        m_safe = tl.where(m_new == float("-inf"), 0.0, m_new)
        alpha = tl.exp(m_i - m_safe)
        p_bf = tl.exp(s - m_safe[:, None]).to(tl.bfloat16)
        l_i = l_i * alpha + tl.sum(p_bf.to(tl.float32), 1)
        v = tl.load(v_buf + rowbase + dv[None, :], mask=cm[:, None], other=0.0).to(tl.bfloat16)
        acc = acc * alpha[:, None] + tl.dot(p_bf, v)
        m_i = m_new
    o_ptrs = out_ptr + row[:, None] * stride_or + hq[:, None] * stride_oh + dv[None, :]
    base = ws_ptr + (((g * HEADS_KV + kvh) * DSPLIT + ds) * SPLITS).to(tl.int64) * (QP * (2 + DV))
    _k8_combine(ws_ptr, cnt_ptr, (g * HEADS_KV + kvh) * DSPLIT + ds, base, qr, tl.arange(0, DV), m_i, l_i, acc,
                o_ptrs, rvalid[:, None], sp, SPLITS, QP, DV, NTHREADS)


def qsa_fp8_union_decode(q, k_buf, v_buf, req_to_token, row_req, topk_indices, seq_lens, valid_counts, sm_scale, W,
                         max_pos, splits=8, block_n=32, warps=8, stages=2, dsplit=2, capacity_groups=None):
    rows, hq, d = q.shape
    assert rows % W == 0
    groups = rows // W
    heads_kv = k_buf.shape[1]
    group = hq // heads_kv
    qp = triton.next_power_of_2(W * group)
    topk = topk_indices.shape[1]
    max_union = W * topk
    capg = max(groups, capacity_groups or groups)
    key = ("union", W, heads_kv, qp, d, dsplit, splits, max_pos, topk)
    st = _K8_WS.get(key)
    if st is None or st["cap"] < capg:
        dv = d // dsplit
        st = dict(cap=capg,
                  masks=torch.zeros(capg * max_pos, dtype=torch.int32, device=q.device),
                  union=torch.empty(capg * max_union, dtype=torch.int32, device=q.device),
                  umask=torch.empty(capg * max_union, dtype=torch.int32, device=q.device),
                  ucount=torch.empty(capg, dtype=torch.int32, device=q.device),
                  ws=torch.empty(capg * heads_kv * dsplit * splits * qp * (2 + dv), dtype=torch.float32,
                                 device=q.device),
                  cnt=torch.zeros(capg * heads_kv * dsplit, dtype=torch.int32, device=q.device))
        _K8_WS[key] = st
    out = torch.empty_like(q)
    _k8u_mark_kernel[(rows,)](st["masks"], topk_indices, seq_lens, valid_counts, topk_indices.stride(0), max_pos,
                              W=W, BLOCK=triton.next_power_of_2(topk), num_warps=8)
    _k8u_compact_kernel[(groups,)](st["masks"], st["union"], st["umask"], st["ucount"], seq_lens, max_pos, max_union,
                                   W=W, WP=triton.next_power_of_2(W), CHUNK=4096, num_warps=8)
    _k8u_attend_kernel[(groups, heads_kv * dsplit, splits)](
        q, out, st["ws"], st["cnt"], k_buf, v_buf, req_to_token, row_req, st["union"], st["umask"], st["ucount"],
        max_union, float(sm_scale), q.stride(0), q.stride(1), out.stride(0), out.stride(1), req_to_token.stride(0),
        W=W, HEADS_KV=heads_kv, GROUP=group, QP=qp, D=d, DSPLIT=dsplit, BLOCK_N=block_n, SPLITS=splits,
        NTHREADS=32 * warps, num_warps=warps, num_stages=stages)
    return out
