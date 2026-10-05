"""daniel-draft kfuse (3-Oct-2026): fused QSA sparse decode straight from NVFP4 KV.

Today (qsakv4, trtllm/XQA path) every decode / verify row of a QSA layer first unpacks its ~2,050 selected K/V rows
from NVFP4 into an FP8 scratch (`_compact_kv_nvfp4`, ~1 MB per row) and then XQA's `kernel_mha` reads that scratch.
This kernel does both in one pass: per (row, kv head, split) it walks the row's selected positions, unpacks K and V
in registers with the SAME arithmetic as the gather (e2m1 * fp8 block scale * fp32 global scale, clamp to +-448,
round to FP8 E4M3 when the scratch is FP8), and runs XQA's math: bf16 Q x bf16(K) with fp32 accumulation, scale,
online softmax, P rounded to bf16 for P x V (and for the row sum), fp32 accumulation. Splits are combined by the
last split to finish (fixed order: deterministic), then each row's output is written in bf16.
The head dim is handled as even/odd halves (the packed byte holds elements 2i, 2i+1), so no interleave is needed.
"""
from __future__ import annotations

import torch
import triton
import triton.language as tl


@triton.jit
def _kf_e2m1_to_f32(nibble):
    magnitude = nibble & 7
    exponent = (magnitude >> 1).to(tl.float32)
    mantissa = (magnitude & 1).to(tl.float32)
    normal = tl.exp2(exponent - 1.0) * (1.0 + 0.5 * mantissa)
    value = tl.where(magnitude < 2, 0.5 * mantissa, normal)
    return tl.where((nibble & 8) != 0, -value, value)


@triton.jit
def _kf_unpack(packed, block_scales, global_scale, slots, valid, kvh, pairs,
               HEADS_KV: tl.constexpr, HALF: tl.constexpr, ROUND_FP8: tl.constexpr):
    mask = valid[:, None]
    src = slots[:, None] * (HEADS_KV * HALF) + kvh * HALF + pairs[None, :]
    scale_src = slots[:, None] * (HEADS_KV * (HALF // 8)) + kvh * (HALF // 8) + pairs[None, :] // 8
    raw = tl.load(packed + src, mask=mask, other=0).to(tl.int32)
    scale = tl.load(block_scales + scale_src, mask=mask, other=0.0).to(tl.float32)
    scale = scale * tl.load(global_scale)
    low = _kf_e2m1_to_f32(raw & 15) * scale
    high = _kf_e2m1_to_f32(raw >> 4) * scale
    if ROUND_FP8:
        low = tl.minimum(tl.maximum(low, -448.0), 448.0).to(tl.float8e4nv)
        high = tl.minimum(tl.maximum(high, -448.0), 448.0).to(tl.float8e4nv)
    return low.to(tl.bfloat16), high.to(tl.bfloat16)


@triton.jit
def _kf_unpack_v2(packed, block_scales, global_scale, slots, valid, kvh, pairs, grp,
                  HEADS_KV: tl.constexpr, HALF: tl.constexpr, BLOCK_N: tl.constexpr, ROUND_FP8: tl.constexpr):
    """Same values as _kf_unpack: e2m1 magnitudes x2 come from a nibble LUT (0,1,2,3,4,6,8,12), the 0.5 is folded
    into the (exact) per-group scale, the sign is OR-ed into the fp32 bits; one rounding (e2m1 * (s * g))."""
    mask = valid[:, None]
    src = slots[:, None] * (HEADS_KV * HALF) + kvh * HALF + pairs[None, :]
    raw = tl.load(packed + src, mask=mask, other=0).to(tl.int32)
    scale_src = slots[:, None] * (HEADS_KV * (HALF // 8)) + kvh * (HALF // 8) + grp[None, :]
    sg = tl.load(block_scales + scale_src, mask=mask, other=0.0).to(tl.float32) * tl.load(global_scale)
    sg = sg * 0.5
    sgb = tl.reshape(tl.broadcast_to(sg[:, :, None], [BLOCK_N, HALF // 8, 8]), [BLOCK_N, HALF])
    lo_n = raw & 15
    hi_n = (raw >> 4) & 15
    lo = ((-932957680 >> ((lo_n & 7) << 2)) & 15).to(tl.float32)
    hi = ((-932957680 >> ((hi_n & 7) << 2)) & 15).to(tl.float32)
    lo = (lo.to(tl.int32, bitcast=True) | ((lo_n & 8) << 28)).to(tl.float32, bitcast=True) * sgb
    hi = (hi.to(tl.int32, bitcast=True) | ((hi_n & 8) << 28)).to(tl.float32, bitcast=True) * sgb
    if ROUND_FP8:
        lo = tl.minimum(tl.maximum(lo, -448.0), 448.0).to(tl.float8e4nv)
        hi = tl.minimum(tl.maximum(hi, -448.0), 448.0).to(tl.float8e4nv)
    return lo.to(tl.bfloat16), hi.to(tl.bfloat16)


@triton.jit
def _kf_qsa_nvfp4_decode_kernel(
    q_ptr, out_ptr, ws_ptr, cnt_ptr,
    k_packed, v_packed, k_scales, v_scales, k_gs, v_gs,
    req_to_token, row_req, topk_idx, seq_lens, valid_counts,
    sm_scale,
    stride_qr, stride_qh, stride_or, stride_oh,
    req_stride, idx_stride, cols_per_split,
    HEADS_KV: tl.constexpr, GROUP: tl.constexpr, GROUP_PAD: tl.constexpr, HALF: tl.constexpr,
    BLOCK_N: tl.constexpr, SPLITS: tl.constexpr, NTHREADS: tl.constexpr, ROUND_FP8: tl.constexpr,
    V2: tl.constexpr,
):
    row = tl.program_id(0)
    kvh = tl.program_id(1)
    sp = tl.program_id(2)
    g = tl.arange(0, GROUP_PAD)
    hmask = g < GROUP
    hq = kvh * GROUP + g
    pairs = tl.arange(0, HALF)
    grp = tl.arange(0, HALF // 8)
    q_base = q_ptr + row * stride_qr + hq[:, None] * stride_qh + 2 * pairs[None, :]
    q_even = tl.load(q_base, mask=hmask[:, None], other=0.0)
    q_odd = tl.load(q_base + 1, mask=hmask[:, None], other=0.0)
    length = tl.load(seq_lens + row)
    req = tl.load(row_req + row).to(tl.int64)
    vcount = tl.load(valid_counts + row)
    m_i = tl.full([GROUP_PAD], float("-inf"), tl.float32)
    l_i = tl.zeros([GROUP_PAD], tl.float32)
    acc_e = tl.zeros([GROUP_PAD, HALF], tl.float32)
    acc_o = tl.zeros([GROUP_PAD, HALF], tl.float32)
    c_lo = sp * cols_per_split
    c_hi = tl.minimum(c_lo + cols_per_split, vcount)
    offs = tl.arange(0, BLOCK_N)
    for c in range(c_lo, c_hi, BLOCK_N):
        cols = c + offs
        cm = cols < c_hi
        pos = tl.load(topk_idx + row * idx_stride + cols, mask=cm, other=-1)
        valid = cm & (pos >= 0) & (pos < length)
        slot = tl.load(req_to_token + req * req_stride + tl.where(valid, pos, 0), mask=valid, other=0).to(tl.int64)
        if V2:
            k_lo, k_hi = _kf_unpack_v2(k_packed, k_scales, k_gs, slot, valid, kvh, pairs, grp, HEADS_KV, HALF,
                                       BLOCK_N, ROUND_FP8)
        else:
            k_lo, k_hi = _kf_unpack(k_packed, k_scales, k_gs, slot, valid, kvh, pairs, HEADS_KV, HALF, ROUND_FP8)
        s = tl.dot(q_even, tl.trans(k_lo)) + tl.dot(q_odd, tl.trans(k_hi))
        s = s * sm_scale
        s = tl.where(valid[None, :], s, float("-inf"))
        m_new = tl.maximum(m_i, tl.max(s, 1))
        m_safe = tl.where(m_new == float("-inf"), 0.0, m_new)
        alpha = tl.exp(m_i - m_safe)
        p = tl.exp(s - m_safe[:, None])
        p_bf = p.to(tl.bfloat16)
        l_i = l_i * alpha + tl.sum(p_bf.to(tl.float32), 1)
        if V2:
            v_lo, v_hi = _kf_unpack_v2(v_packed, v_scales, v_gs, slot, valid, kvh, pairs, grp, HEADS_KV, HALF,
                                       BLOCK_N, ROUND_FP8)
        else:
            v_lo, v_hi = _kf_unpack(v_packed, v_scales, v_gs, slot, valid, kvh, pairs, HEADS_KV, HALF, ROUND_FP8)
        acc_e = acc_e * alpha[:, None] + tl.dot(p_bf, v_lo)
        acc_o = acc_o * alpha[:, None] + tl.dot(p_bf, v_hi)
        m_i = m_new
    o_base = out_ptr + row * stride_or + hq[:, None] * stride_oh + 2 * pairs[None, :]
    if SPLITS == 1:
        inv = tl.where(l_i > 0, 1.0 / l_i, 0.0)
        tl.store(o_base, (acc_e * inv[:, None]).to(tl.bfloat16), mask=hmask[:, None])
        tl.store(o_base + 1, (acc_o * inv[:, None]).to(tl.bfloat16), mask=hmask[:, None])
    else:
        # workspace per (row, kvh): SPLITS x [m (GP), l (GP), acc_e (GP x HALF), acc_o (GP x HALF)] fp32
        PART: tl.constexpr = GROUP_PAD * (2 + 2 * HALF)
        base = ws_ptr + ((row * HEADS_KV + kvh) * SPLITS).to(tl.int64) * PART
        mine = base + sp * PART
        tl.store(mine + g, m_i, cache_modifier=".cg")
        tl.store(mine + GROUP_PAD + g, l_i, cache_modifier=".cg")
        a_off = 2 * GROUP_PAD + g[:, None] * HALF + pairs[None, :]
        tl.store(mine + a_off, acc_e, cache_modifier=".cg")
        tl.store(mine + GROUP_PAD * HALF + a_off, acc_o, cache_modifier=".cg")
        _f = tl.inline_asm_elementwise("fence.acq_rel.gpu;\n\tmov.u32 $0, $1;", "=r,r", [tl.arange(0, NTHREADS)],
                                       dtype=tl.int32, is_pure=False, pack=1)
        tl.debug_barrier()
        ctr = cnt_ptr + row * HEADS_KV + kvh
        arrived = tl.atomic_add(ctr, 1, sem="acq_rel", scope="gpu")
        if arrived == SPLITS - 1:
            _g = tl.inline_asm_elementwise("fence.acq_rel.gpu;\n\tmov.u32 $0, $1;", "=r,r", [tl.arange(0, NTHREADS)],
                                           dtype=tl.int32, is_pure=False, pack=1)
            m_all = tl.full([GROUP_PAD], float("-inf"), tl.float32)
            for s_ in range(0, SPLITS):
                m_all = tl.maximum(m_all, tl.load(base + s_ * PART + g, cache_modifier=".cg"))
            m_all_safe = tl.where(m_all == float("-inf"), 0.0, m_all)
            l_tot = tl.zeros([GROUP_PAD], tl.float32)
            o_e = tl.zeros([GROUP_PAD, HALF], tl.float32)
            o_o = tl.zeros([GROUP_PAD, HALF], tl.float32)
            for s_ in range(0, SPLITS):
                part = base + s_ * PART
                w = tl.exp(tl.load(part + g, cache_modifier=".cg") - m_all_safe)
                l_tot += w * tl.load(part + GROUP_PAD + g, cache_modifier=".cg")
                o_e += w[:, None] * tl.load(part + a_off, cache_modifier=".cg")
                o_o += w[:, None] * tl.load(part + GROUP_PAD * HALF + a_off, cache_modifier=".cg")
            inv = tl.where(l_tot > 0, 1.0 / l_tot, 0.0)
            tl.store(o_base, (o_e * inv[:, None]).to(tl.bfloat16), mask=hmask[:, None])
            tl.store(o_base + 1, (o_o * inv[:, None]).to(tl.bfloat16), mask=hmask[:, None])
            tl.atomic_xchg(ctr, 0, sem="relaxed", scope="gpu")


_KF_WS = {}


def qsa_nvfp4_fused_decode(q, nvfp4, req_to_token, row_req, topk_indices, seq_lens, valid_counts, sm_scale,
                           round_fp8=True, splits=4, block_n=32, warps=4, stages=2, out=None, capacity_rows=None,
                           v2=True):
    """q [rows, Hq, D] bf16 -> out [rows, Hq, D] bf16; nvfp4 = (k_packed, v_packed, k_scales, v_scales, k_gs, v_gs)."""
    k_packed, v_packed, k_scales, v_scales, k_gs, v_gs = nvfp4
    rows, hq, d = q.shape
    heads_kv, half = k_packed.shape[1], k_packed.shape[2]
    assert d == 2 * half and hq % heads_kv == 0
    group = hq // heads_kv
    gpad = max(16, triton.next_power_of_2(group))
    topk = topk_indices.shape[1]
    if out is None:
        out = torch.empty_like(q)
    cols = triton.cdiv(triton.cdiv(topk, splits), block_n) * block_n
    if splits > 1:
        cap = max(rows, capacity_rows or rows)
        key = (q.device, heads_kv, gpad, half, splits)
        ws_cnt = _KF_WS.get(key)
        if ws_cnt is None or ws_cnt[1].numel() < cap * heads_kv:
            ws_cnt = (torch.empty(cap * heads_kv * splits * gpad * (2 + 2 * half), dtype=torch.float32, device=q.device),
                      torch.zeros(cap * heads_kv, dtype=torch.int32, device=q.device))
            _KF_WS[key] = ws_cnt
        ws, cnt = ws_cnt
    else:
        ws, cnt = out, out
    _kf_qsa_nvfp4_decode_kernel[(rows, heads_kv, splits)](
        q, out, ws, cnt, k_packed, v_packed, k_scales, v_scales, k_gs, v_gs,
        req_to_token, row_req, topk_indices, seq_lens, valid_counts, float(sm_scale),
        q.stride(0), q.stride(1), out.stride(0), out.stride(1),
        req_to_token.stride(0), topk_indices.stride(0), cols,
        HEADS_KV=heads_kv, GROUP=group, GROUP_PAD=gpad, HALF=half, BLOCK_N=block_n, SPLITS=splits,
        NTHREADS=32 * warps, ROUND_FP8=round_fp8, V2=v2, num_warps=warps, num_stages=stages)
    return out
