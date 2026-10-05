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


__all__ = [
    "qwen_sparse_fa2_cu_seqlens_triton",
    "qwen_sparse_valid_counts_triton",
    "qwen_sparse_kv_extraction_compact_triton",
    "qwen_sparse_kv_extraction_compact_nvfp4_triton",
    "qwen_sparse_gather_slots_nvfp4_triton",
    "sparse_gqa_fwd_interface_triton",
    "sparse_gqa_fwd_interface_triton_ck",
]
