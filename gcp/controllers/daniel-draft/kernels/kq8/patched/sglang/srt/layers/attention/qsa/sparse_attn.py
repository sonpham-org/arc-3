"""Validated sparse GQA operators migrated from the QSA reference branch."""

from typing import Optional

import torch
import triton
import triton.language as tl

_H20_CONFIGS = [
    (32, (32, 8, 2)),
    (64, (64, 8, 2)),
    (1024, (32, 4, 2)),
    (float("inf"), (16, 1, 2)),
]
_L20_CONFIGS = [
    (32, (32, 8, 2)),
    (64, (64, 8, 2)),
    (128, (64, 4, 2)),
    (512, (32, 4, 2)),
    (float("inf"), (16, 1, 2)),
]


def _get_best_config(total_q: int):
    table = _H20_CONFIGS if "H20" in torch.cuda.get_device_name(0) else _L20_CONFIGS
    return next(cfg for limit, cfg in table if total_q <= limit)


@triton.jit
def _sparse_gqa_prefill(
    q,
    k,
    v,
    out,
    indices,
    cu_seqlens,
    scale,
    topk,
    sq_m: tl.constexpr,
    sq_h: tl.constexpr,
    sq_d: tl.constexpr,
    sk_n: tl.constexpr,
    sk_h: tl.constexpr,
    sk_d: tl.constexpr,
    sv_n: tl.constexpr,
    sv_h: tl.constexpr,
    sv_d: tl.constexpr,
    so_m: tl.constexpr,
    so_h: tl.constexpr,
    so_d: tl.constexpr,
    si_m: tl.constexpr,
    si_g: tl.constexpr,
    si_n: tl.constexpr,
    NUM_KV_HEADS: tl.constexpr,
    GROUP_SIZE: tl.constexpr,
    BLOCK_M: tl.constexpr,
    BLOCK_N: tl.constexpr,
    HEAD_DIM: tl.constexpr,
):
    batch_group = tl.program_id(1)
    group = batch_group % NUM_KV_HEADS
    batch = batch_group // NUM_KV_HEADS
    seq_start = tl.load(cu_seqlens + batch).to(tl.int64)
    seq_end = tl.load(cu_seqlens + batch + 1).to(tl.int64)
    query_relative = tl.program_id(0).to(tl.int64)
    query = seq_start + query_relative
    if query >= seq_end:
        return

    row_topk = tl.minimum(topk, query_relative + 1)
    row_limit = tl.minimum(topk, ((row_topk + BLOCK_N - 1) // BLOCK_N) * BLOCK_N)
    offs_h = tl.arange(0, BLOCK_M)
    offs_d = tl.arange(0, HEAD_DIM)
    head_start = group * GROUP_SIZE
    q_values = tl.load(
        q
        + query * sq_m
        + (head_start + offs_h[:, None]) * sq_h
        + offs_d[None, :] * sq_d,
        mask=(offs_h < GROUP_SIZE)[:, None],
        other=0.0,
    )
    q_values = (q_values * scale * 1.4426950408).to(q_values.dtype)
    k_base = k + seq_start * sk_n + group * sk_h
    v_base = v + seq_start * sv_n + group * sv_h
    idx_row = indices + query * si_m + group * si_g
    max_value = tl.full([BLOCK_M], -float("inf"), tl.float32)
    normalizer = tl.zeros([BLOCK_M], tl.float32)
    accumulator = tl.zeros([BLOCK_M, HEAD_DIM], tl.float32)
    offs_n = tl.arange(0, BLOCK_N)
    for start in range(0, row_limit, BLOCK_N):
        current = start + offs_n
        token = tl.load(idx_row + current * si_n, mask=current < topk, other=-1)
        valid = token >= 0
        keys = tl.load(
            k_base + token[None, :] * sk_n + offs_d[:, None] * sk_d,
            mask=valid[None, :],
            other=0.0,
        ).to(q_values.dtype)
        values = tl.load(
            v_base + token[:, None] * sv_n + offs_d[None, :] * sv_d,
            mask=valid[:, None],
            other=0.0,
        ).to(q_values.dtype)
        scores = tl.where(valid[None, :], tl.dot(q_values, keys), -float("inf"))
        next_max = tl.maximum(max_value, tl.max(scores, 1))
        alpha = tl.math.exp2(max_value - next_max)
        probabilities = tl.math.exp2(scores - next_max[:, None])
        accumulator = tl.dot(
            probabilities.to(values.dtype), values, accumulator * alpha[:, None]
        )
        normalizer = normalizer * alpha + tl.sum(probabilities, 1)
        max_value = next_max
    output = accumulator / normalizer[:, None]
    tl.store(
        out
        + query * so_m
        + (head_start + offs_h[:, None]) * so_h
        + offs_d[None, :] * so_d,
        output,
        mask=(offs_h < GROUP_SIZE)[:, None],
    )


def sparse_gqa_fwd_interface_triton(q, k, v, max_seqlen_k, indices, cu_seqlens, scale):
    total_q, num_q_heads, head_dim = q.shape
    num_kv_heads = k.shape[1]
    group_size = num_q_heads // num_kv_heads
    block_m = max(16, triton.next_power_of_2(group_size))
    block_n, warps, stages = _get_best_config(total_q)
    out = torch.empty_like(q)
    _sparse_gqa_prefill[(max_seqlen_k, (cu_seqlens.shape[0] - 1) * num_kv_heads)](
        q,
        k,
        v,
        out,
        indices,
        cu_seqlens,
        scale,
        indices.shape[-1],
        q.stride(0),
        q.stride(1),
        q.stride(2),
        k.stride(0),
        k.stride(1),
        k.stride(2),
        v.stride(0),
        v.stride(1),
        v.stride(2),
        out.stride(0),
        out.stride(1),
        out.stride(2),
        indices.stride(0),
        indices.stride(1) if indices.ndim == 3 else 0,
        indices.stride(2) if indices.ndim == 3 else indices.stride(1),
        NUM_KV_HEADS=num_kv_heads,
        GROUP_SIZE=group_size,
        BLOCK_M=block_m,
        BLOCK_N=block_n,
        HEAD_DIM=head_dim,
        num_warps=warps,
        num_stages=stages,
    )
    return out


@triton.jit
def _sparse_gqa_chunk_prefill(
    q,
    k,
    v,
    out,
    indices,
    cu_q,
    cu_k,
    kv_lens,
    scale,
    topk,
    sq_m: tl.constexpr,
    sq_h: tl.constexpr,
    sq_d: tl.constexpr,
    sk_n: tl.constexpr,
    sk_h: tl.constexpr,
    sk_d: tl.constexpr,
    sv_n: tl.constexpr,
    sv_h: tl.constexpr,
    sv_d: tl.constexpr,
    so_m: tl.constexpr,
    so_h: tl.constexpr,
    so_d: tl.constexpr,
    si_m: tl.constexpr,
    si_g: tl.constexpr,
    si_n: tl.constexpr,
    NUM_KV_HEADS: tl.constexpr,
    GROUP_SIZE: tl.constexpr,
    BLOCK_M: tl.constexpr,
    BLOCK_N: tl.constexpr,
    HEAD_DIM: tl.constexpr,
):
    query_relative = tl.program_id(0).to(tl.int64)
    batch_group = tl.program_id(1)
    group = batch_group % NUM_KV_HEADS
    batch = batch_group // NUM_KV_HEADS
    q_start = tl.load(cu_q + batch)
    q_end = tl.load(cu_q + batch + 1)
    query = (q_start + query_relative).to(tl.int64)
    if query >= q_end:
        return
    k_start = tl.load(cu_k + batch).to(tl.int64)
    kv_len = tl.load(kv_lens + batch).to(tl.int64)
    visible = query_relative + kv_len - (q_end - q_start) + 1
    row_topk = tl.minimum(topk, visible)
    row_limit = tl.minimum(topk, ((row_topk + BLOCK_N - 1) // BLOCK_N) * BLOCK_N)
    offs_h = tl.arange(0, BLOCK_M)
    offs_d = tl.arange(0, HEAD_DIM)
    q_values = tl.load(
        q
        + query * sq_m
        + (group * GROUP_SIZE + offs_h[:, None]) * sq_h
        + offs_d[None, :] * sq_d,
        mask=(offs_h < GROUP_SIZE)[:, None],
        other=0.0,
    )
    q_values = (q_values * scale * 1.4426950408).to(q_values.dtype)
    k_base = k + k_start * sk_n + group * sk_h
    v_base = v + k_start * sv_n + group * sv_h
    idx_row = indices + query * si_m + group * si_g
    max_value = tl.full([BLOCK_M], -float("inf"), tl.float32)
    normalizer = tl.zeros([BLOCK_M], tl.float32)
    accumulator = tl.zeros([BLOCK_M, HEAD_DIM], tl.float32)
    offs_n = tl.arange(0, BLOCK_N)
    for start in range(0, row_limit, BLOCK_N):
        current = start + offs_n
        token = tl.load(idx_row + current * si_n, mask=current < topk, other=-1)
        valid = token >= 0
        keys = tl.load(
            k_base + token[None, :] * sk_n + offs_d[:, None] * sk_d,
            mask=valid[None, :],
            other=0.0,
        ).to(q_values.dtype)
        values = tl.load(
            v_base + token[:, None] * sv_n + offs_d[None, :] * sv_d,
            mask=valid[:, None],
            other=0.0,
        ).to(q_values.dtype)
        scores = tl.where(valid[None, :], tl.dot(q_values, keys), -float("inf"))
        next_max = tl.maximum(max_value, tl.max(scores, 1))
        alpha = tl.math.exp2(max_value - next_max)
        probabilities = tl.math.exp2(scores - next_max[:, None])
        accumulator = tl.dot(
            probabilities.to(values.dtype), values, accumulator * alpha[:, None]
        )
        normalizer = normalizer * alpha + tl.sum(probabilities, 1)
        max_value = next_max
    output = accumulator / normalizer[:, None]
    tl.store(
        out
        + query * so_m
        + (group * GROUP_SIZE + offs_h[:, None]) * so_h
        + offs_d[None, :] * so_d,
        output,
        mask=(offs_h < GROUP_SIZE)[:, None],
    )


def sparse_gqa_fwd_interface_triton_ck(q, k, v, indices, cu_q, cu_k, kv_lens, scale):
    k, v = k.contiguous(), v.contiguous()
    total_q, num_q_heads, head_dim = q.shape
    num_kv_heads = k.shape[1]
    group_size = num_q_heads // num_kv_heads
    max_q = int((cu_q[1:] - cu_q[:-1]).max().item())
    block_m = max(16, triton.next_power_of_2(group_size))
    block_n, warps, stages = _get_best_config(total_q)
    out = torch.empty_like(q)
    _sparse_gqa_chunk_prefill[(max_q, (cu_q.shape[0] - 1) * num_kv_heads)](
        q,
        k,
        v,
        out,
        indices,
        cu_q,
        cu_k,
        kv_lens,
        scale,
        indices.shape[-1],
        q.stride(0),
        q.stride(1),
        q.stride(2),
        k.stride(0),
        k.stride(1),
        k.stride(2),
        v.stride(0),
        v.stride(1),
        v.stride(2),
        out.stride(0),
        out.stride(1),
        out.stride(2),
        indices.stride(0),
        indices.stride(1) if indices.ndim == 3 else 0,
        indices.stride(2) if indices.ndim == 3 else indices.stride(1),
        NUM_KV_HEADS=num_kv_heads,
        GROUP_SIZE=group_size,
        BLOCK_M=block_m,
        BLOCK_N=block_n,
        HEAD_DIM=head_dim,
        num_warps=warps,
        num_stages=stages,
    )
    return out


@triton.jit
def _fa2_valid_counts(
    seq_lens,
    indices,
    counts,
    topk: tl.constexpr,
    stride_i: tl.constexpr,
    BLOCK_TOPK: tl.constexpr,
):
    row = tl.program_id(0)
    cols = tl.arange(0, BLOCK_TOPK)
    length = tl.load(seq_lens + row)
    positions = tl.load(
        indices + row * stride_i + cols,
        mask=cols < topk,
        other=-1,
    )
    valid = (positions >= 0) & (positions < length)
    tl.store(counts + row, tl.sum(valid.to(tl.int32), axis=0))


@triton.jit
def _fa2_prefix_sum(counts, cu_k, batch, BLOCK_B: tl.constexpr):
    rows = tl.arange(0, BLOCK_B)
    valid_rows = rows < batch
    row_counts = tl.load(counts + rows, mask=valid_rows, other=0)
    tl.store(cu_k, 0)
    tl.store(cu_k + rows + 1, tl.cumsum(row_counts, 0), mask=valid_rows)


def qwen_sparse_fa2_cu_seqlens_triton(
    seq_lens, indices, counts, cu_k, batch, topk, block_b: Optional[int] = None
):
    block_b = block_b or triton.next_power_of_2(batch)
    # Count one request per program. The previous implementation formed a
    # [next_power_of_2(topk), next_power_of_2(batch)] tensor in one program;
    # topk=2051 and batch=512 therefore exceeded Triton's 1M-element limit.
    _fa2_valid_counts[(batch,)](
        seq_lens,
        indices,
        counts,
        topk,
        indices.stride(0),
        BLOCK_TOPK=triton.next_power_of_2(topk),
        num_warps=8,
    )
    # Prefix sum is only over the batch dimension and remains a small 1-D
    # tensor, including during CUDA graph capture.
    _fa2_prefix_sum[(1,)](
        counts,
        cu_k,
        batch,
        BLOCK_B=block_b,
        num_warps=8,
    )


@triton.jit
def _compact_kv(
    k,
    v,
    req_to_token,
    req_indices,
    indices,
    seq_lens,
    cu_k,
    out_k,
    out_v,
    topk: tl.constexpr,
    heads: tl.constexpr,
    dim: tl.constexpr,
    req_stride: tl.constexpr,
    idx_stride: tl.constexpr,
    BLOCK_TOPK: tl.constexpr,
    BLOCK_D: tl.constexpr,
):
    batch, head, block = tl.program_id(0), tl.program_id(1), tl.program_id(2)
    cols = block * BLOCK_TOPK + tl.arange(0, BLOCK_TOPK)
    dims = tl.arange(0, BLOCK_D)
    length = tl.load(seq_lens + batch)
    req = tl.load(req_indices + batch)
    pack_start = tl.load(cu_k + batch)
    valid_count = tl.load(cu_k + batch + 1) - pack_start
    positions = tl.load(indices + batch * idx_stride + cols, mask=cols < topk, other=-1)
    valid = (cols < valid_count) & (positions >= 0) & (positions < length)
    slots = tl.load(
        req_to_token + req * req_stride + tl.where(valid, positions, 0),
        mask=valid,
        other=0,
    )
    src = slots[:, None] * heads * dim + head * dim + dims[None, :]
    dst = (pack_start + cols)[:, None] * heads * dim + head * dim + dims[None, :]
    mask = valid[:, None] & (dims[None, :] < dim)
    tl.store(out_k + dst, tl.load(k + src, mask=mask, other=0.0), mask=mask)
    tl.store(out_v + dst, tl.load(v + src, mask=mask, other=0.0), mask=mask)


def qwen_sparse_valid_counts_triton(seq_lens, indices, counts, batch, topk):
    """Valid-count pass alone, for consumers that need per-row lengths but
    not the packed cu_seqlens prefix sum (trtllm paged decode packs rows at
    a fixed page-aligned stride instead)."""
    _fa2_valid_counts[(batch,)](
        seq_lens,
        indices,
        counts,
        topk,
        indices.stride(0),
        BLOCK_TOPK=triton.next_power_of_2(topk),
        num_warps=8,
    )


def qwen_sparse_kv_extraction_compact_triton(
    k, v, req_to_token, req_indices, indices, seq_lens, cu_k, out_k, out_v, batch, topk
):
    _, heads, dim = k.shape
    block_topk = 16
    _compact_kv[(batch, heads, triton.cdiv(topk, block_topk))](
        k,
        v,
        req_to_token,
        req_indices,
        indices,
        seq_lens,
        cu_k,
        out_k,
        out_v,
        topk,
        heads,
        dim,
        req_to_token.stride(0),
        indices.stride(0),
        BLOCK_TOPK=block_topk,
        BLOCK_D=triton.next_power_of_2(dim),
        num_warps=8,
    )


# --------------------------------------------------------------------------------------------------------------
# daniel-draft kfuse8 (4-Oct-2026): fused fp8 QSA sparse decode (see qwen_sparse_fp8_fused_decode_triton).
_K8_WS = {}


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


def qwen_sparse_fp8_fused_decode_triton(
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


__all__ = [
    "qwen_sparse_fa2_cu_seqlens_triton",
    "qwen_sparse_valid_counts_triton",
    "qwen_sparse_kv_extraction_compact_triton",
    "qwen_sparse_fp8_fused_decode_triton",
    "sparse_gqa_fwd_interface_triton",
    "sparse_gqa_fwd_interface_triton_ck",
]
