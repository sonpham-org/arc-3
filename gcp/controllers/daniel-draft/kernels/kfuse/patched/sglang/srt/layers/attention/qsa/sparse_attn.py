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


# NVFP4 KV storage (--kv-cache-dtype nvfp4_qsa): K/V rows are packed E2M1 pairs,
# shape [slots, heads, dim // 2] uint8 (element 2i in the low nibble), with one
# FP8 E4M3 block scale per 16 elements, shape [slots, heads, dim // 16], and one
# FP32 global scale per layer: value = e2m1 * block_scale * global_scale.  QSA
# only ever reads the selected rows, so the kernels below unpack exactly those
# rows into the scratch dtype the existing attention kernels already consume.
@triton.jit
def _e2m1_to_f32(nibble):
    magnitude = nibble & 7
    exponent = (magnitude >> 1).to(tl.float32)
    mantissa = (magnitude & 1).to(tl.float32)
    normal = tl.exp2(exponent - 1.0) * (1.0 + 0.5 * mantissa)
    value = tl.where(magnitude < 2, 0.5 * mantissa, normal)
    return tl.where((nibble & 8) != 0, -value, value)


@triton.jit
def _nvfp4_unpack_rows(
    packed,
    block_scales,
    global_scale,
    slots,
    valid,
    head,
    out,
    dst_rows,
    heads: tl.constexpr,
    half: tl.constexpr,
    BLOCK_H: tl.constexpr,
    CLAMP_FP8: tl.constexpr,
):
    pairs = tl.arange(0, BLOCK_H)
    mask = valid[:, None] & (pairs[None, :] < half)
    src = slots[:, None] * (heads * half) + head * half + pairs[None, :]
    scale_src = slots[:, None] * (heads * (half // 8)) + head * (half // 8) + pairs[None, :] // 8
    raw = tl.load(packed + src, mask=mask, other=0).to(tl.int32)
    scale = tl.load(block_scales + scale_src, mask=mask, other=0.0).to(tl.float32)
    scale = scale * tl.load(global_scale)
    low = _e2m1_to_f32(raw & 15) * scale
    high = _e2m1_to_f32(raw >> 4) * scale
    if CLAMP_FP8:
        low = tl.minimum(tl.maximum(low, -448.0), 448.0)
        high = tl.minimum(tl.maximum(high, -448.0), 448.0)
    dst = dst_rows[:, None] * (heads * 2 * half) + head * (2 * half) + 2 * pairs[None, :]
    tl.store(out + dst, low.to(out.dtype.element_ty), mask=mask)
    tl.store(out + dst + 1, high.to(out.dtype.element_ty), mask=mask)


@triton.jit
def _compact_kv_nvfp4(
    k_packed,
    v_packed,
    k_block_scales,
    v_block_scales,
    k_global_scale,
    v_global_scale,
    req_to_token,
    req_indices,
    indices,
    seq_lens,
    cu_k,
    out_k,
    out_v,
    topk: tl.constexpr,
    heads: tl.constexpr,
    half: tl.constexpr,
    req_stride: tl.constexpr,
    idx_stride: tl.constexpr,
    BLOCK_TOPK: tl.constexpr,
    BLOCK_H: tl.constexpr,
    CLAMP_FP8: tl.constexpr,
):
    batch, head, block = tl.program_id(0), tl.program_id(1), tl.program_id(2)
    cols = block * BLOCK_TOPK + tl.arange(0, BLOCK_TOPK)
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
    ).to(tl.int64)
    dst_rows = (pack_start + cols).to(tl.int64)
    _nvfp4_unpack_rows(
        k_packed, k_block_scales, k_global_scale, slots, valid, head, out_k, dst_rows,
        heads, half, BLOCK_H, CLAMP_FP8,
    )
    _nvfp4_unpack_rows(
        v_packed, v_block_scales, v_global_scale, slots, valid, head, out_v, dst_rows,
        heads, half, BLOCK_H, CLAMP_FP8,
    )


@triton.jit
def _gather_slots_nvfp4(
    k_packed,
    v_packed,
    k_block_scales,
    v_block_scales,
    k_global_scale,
    v_global_scale,
    slot_ids,
    num_rows,
    out_k,
    out_v,
    heads: tl.constexpr,
    half: tl.constexpr,
    BLOCK_ROWS: tl.constexpr,
    BLOCK_H: tl.constexpr,
    CLAMP_FP8: tl.constexpr,
):
    block, head = tl.program_id(0), tl.program_id(1)
    rows = block * BLOCK_ROWS + tl.arange(0, BLOCK_ROWS)
    valid = rows < num_rows
    slots = tl.load(slot_ids + rows, mask=valid, other=0).to(tl.int64)
    dst_rows = rows.to(tl.int64)
    _nvfp4_unpack_rows(
        k_packed, k_block_scales, k_global_scale, slots, valid, head, out_k, dst_rows,
        heads, half, BLOCK_H, CLAMP_FP8,
    )
    _nvfp4_unpack_rows(
        v_packed, v_block_scales, v_global_scale, slots, valid, head, out_v, dst_rows,
        heads, half, BLOCK_H, CLAMP_FP8,
    )


def _check_nvfp4_kv(
    k_packed,
    v_packed,
    k_block_scales,
    v_block_scales,
    k_global_scale,
    v_global_scale,
    out_k,
    out_v,
):
    # Host-side layout checks only (they run once at CUDA-graph capture).  The
    # kernels address every buffer as a dense row-major array, and a scale
    # buffer viewed as uint8 instead of FP8 E4M3 would be read as integers.
    slots, heads, half = k_packed.shape
    for packed in (k_packed, v_packed):
        assert packed.dtype == torch.uint8 and packed.is_contiguous()
        assert packed.shape == k_packed.shape
    for scales in (k_block_scales, v_block_scales):
        assert scales.dtype == torch.float8_e4m3fn and scales.is_contiguous()
        assert tuple(scales.shape) == (slots, heads, half // 8), (
            "NVFP4 KV expects one FP8 E4M3 block scale per 16 elements"
        )
    for global_scale in (k_global_scale, v_global_scale):
        assert global_scale.dtype == torch.float32 and global_scale.numel() >= 1
        assert global_scale.device == k_packed.device
    for out in (out_k, out_v):
        assert out.dtype in (torch.float8_e4m3fn, torch.bfloat16)
        assert out.is_contiguous() and out.dim() == 3
        assert out.shape[1] == heads and out.shape[2] == 2 * half
    assert out_v.shape == out_k.shape and out_v.dtype == out_k.dtype
    return heads, half


def qwen_sparse_kv_extraction_compact_nvfp4_triton(
    k_packed,
    v_packed,
    k_block_scales,
    v_block_scales,
    k_global_scale,
    v_global_scale,
    req_to_token,
    req_indices,
    indices,
    seq_lens,
    cu_k,
    out_k,
    out_v,
    batch,
    topk,
):
    """`qwen_sparse_kv_extraction_compact_triton` for NVFP4 KV storage: the
    selected rows are unpacked into `out_k` / `out_v` (FP8 E4M3 or BF16)."""
    heads, half = _check_nvfp4_kv(
        k_packed,
        v_packed,
        k_block_scales,
        v_block_scales,
        k_global_scale,
        v_global_scale,
        out_k,
        out_v,
    )
    assert req_to_token.stride(1) == 1 and indices.stride(1) == 1
    block_topk = 16
    _compact_kv_nvfp4[(batch, heads, triton.cdiv(topk, block_topk))](
        k_packed,
        v_packed,
        k_block_scales,
        v_block_scales,
        k_global_scale,
        v_global_scale,
        req_to_token,
        req_indices,
        indices,
        seq_lens,
        cu_k,
        out_k,
        out_v,
        topk,
        heads,
        half,
        req_to_token.stride(0),
        indices.stride(0),
        BLOCK_TOPK=block_topk,
        BLOCK_H=triton.next_power_of_2(half),
        CLAMP_FP8=out_k.dtype == torch.float8_e4m3fn,
        num_warps=8,
    )


def qwen_sparse_gather_slots_nvfp4_triton(
    k_packed,
    v_packed,
    k_block_scales,
    v_block_scales,
    k_global_scale,
    v_global_scale,
    slot_ids,
    out_k,
    out_v,
):
    """Unpack the NVFP4 KV rows at `slot_ids` (in order) into `out_k` / `out_v`."""
    heads, half = _check_nvfp4_kv(
        k_packed,
        v_packed,
        k_block_scales,
        v_block_scales,
        k_global_scale,
        v_global_scale,
        out_k,
        out_v,
    )
    assert slot_ids.dim() == 1 and slot_ids.is_contiguous()
    assert not slot_ids.is_floating_point()
    assert out_k.shape[0] >= slot_ids.numel()
    num_rows = slot_ids.numel()
    if num_rows == 0:
        return
    block_rows = 16
    _gather_slots_nvfp4[(triton.cdiv(num_rows, block_rows), heads)](
        k_packed,
        v_packed,
        k_block_scales,
        v_block_scales,
        k_global_scale,
        v_global_scale,
        slot_ids,
        num_rows,
        out_k,
        out_v,
        heads,
        half,
        BLOCK_ROWS=block_rows,
        BLOCK_H=triton.next_power_of_2(half),
        CLAMP_FP8=out_k.dtype == torch.float8_e4m3fn,
        num_warps=8,
    )



# --------------------------------------------------------------------------------------------------------------
# daniel-draft kfuse (3-Oct-2026): fused NVFP4 QSA sparse decode (see qwen_sparse_nvfp4_fused_decode_triton).
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
        k_lo, k_hi = _kf_unpack_v2(k_packed, k_scales, k_gs, slot, valid, kvh, pairs, grp, HEADS_KV, HALF,
                                       BLOCK_N, ROUND_FP8)
        s = tl.dot(q_even, tl.trans(k_lo)) + tl.dot(q_odd, tl.trans(k_hi))
        s = s * sm_scale
        s = tl.where(valid[None, :], s, float("-inf"))
        m_new = tl.maximum(m_i, tl.max(s, 1))
        m_safe = tl.where(m_new == float("-inf"), 0.0, m_new)
        alpha = tl.exp(m_i - m_safe)
        p = tl.exp(s - m_safe[:, None])
        p_bf = p.to(tl.bfloat16)
        l_i = l_i * alpha + tl.sum(p_bf.to(tl.float32), 1)
        v_lo, v_hi = _kf_unpack_v2(v_packed, v_scales, v_gs, slot, valid, kvh, pairs, grp, HEADS_KV, HALF,
                                       BLOCK_N, ROUND_FP8)
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


__all__ = [
    "qwen_sparse_fa2_cu_seqlens_triton",
    "qwen_sparse_valid_counts_triton",
    "qwen_sparse_kv_extraction_compact_triton",
    "qwen_sparse_kv_extraction_compact_nvfp4_triton",
    "qwen_sparse_nvfp4_fused_decode_triton",
    "qwen_sparse_gather_slots_nvfp4_triton",
    "sparse_gqa_fwd_interface_triton",
    "sparse_gqa_fwd_interface_triton_ck",
]
