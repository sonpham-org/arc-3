"""Byte-exact emulations of the HiCache transfer kernels the host pool calls.

Offsets follow sglang/kernels/aot/csrc/kvcacheio/transfer.cu (sgl_kernel) and
sglang/kernels/jit/csrc/kvcacheio/{hicache,relayout,staged_write_back}.cuh plus
their Python wrappers in sglang/kernels/ops/kvcache/hicache.py. Every copy is
bounds-checked against the allocation its address belongs to, so a wrong item
size or layout dim fails loudly instead of corrupting a neighbour.
"""

from __future__ import annotations

import ctypes

import fake_torch as torch

CALLS = []  # (kernel name, details) for coverage reporting
JIT_OK = {"one": True, "staged": True}


def _copy(dst, src, nbytes, what):
    s0, s1, slabel = torch.allocation_of(src)
    d0, d1, dlabel = torch.allocation_of(dst)
    if not (src + nbytes <= s1):
        raise AssertionError(f"{what}: source overrun in {slabel} ({src - s0}+{nbytes} > {s1 - s0})")
    if not (dst + nbytes <= d1):
        raise AssertionError(f"{what}: destination overrun in {dlabel} ({dst - d0}+{nbytes} > {d1 - d0})")
    ctypes.memmove(dst, src, nbytes)


def _idx(t, *, cuda=None, dtypes=(torch.int64,)):
    if cuda is not None:
        assert t.is_cuda == cuda, f"indices on wrong device: {t.device}"
    assert t.dtype in dtypes, f"indices dtype {t.dtype}"
    assert t.dim() == 1
    return [int(x) for x in t.a.tolist()]


# ----------------------------------------------------------------------------
# sgl_kernel.kvcacheio (AOT): transfer_kv_launcher checks + offset functions
# ----------------------------------------------------------------------------


def _launcher_checks(src_indices, dst_indices, item_size):
    src = _idx(src_indices, cuda=True)
    dst = _idx(dst_indices, cuda=True)
    assert len(src) == len(dst), "Source and destination indices must have the same length"
    assert item_size % 8 == 0, "Item byte size must be divisible by 8"
    assert len(src) > 0, "empty transfer would divide by zero in transfer_kv_launcher"
    return src, dst


def transfer_kv_per_layer_pf_lf(src_k, dst_k, src_v, dst_v, src_indices, dst_indices,
                                layer_id, item_size, src_layout_dim, block_quota=2,
                                num_warps_per_block=32):
    CALLS.append(("sgl.per_layer_pf_lf", item_size))
    src, dst = _launcher_checks(src_indices, dst_indices, item_size)
    for s, d in zip(src, dst):
        for a, b in ((src_k, dst_k), (src_v, dst_v)):
            # get_global_offset_pf(src) / get_global_offset_lf(dst, layer 0 dim 0)
            _copy(b.data_ptr() + d * item_size,
                  a.data_ptr() + s * src_layout_dim + layer_id * item_size,
                  item_size, "transfer_kv_per_layer_pf_lf")


def transfer_kv_all_layer_lf_pf(src_k_layers, dst_k, src_v_layers, dst_v, src_indices,
                                dst_indices, item_size, dst_layout_dim, num_layers,
                                block_quota=2, num_warps_per_block=32):
    CALLS.append(("sgl.all_layer_lf_pf", item_size))
    assert num_layers == src_k_layers.size(0), "num_layers mismatch"
    assert src_k_layers.dtype is torch.uint64 and src_k_layers.is_cuda
    src, dst = _launcher_checks(src_indices, dst_indices, item_size)
    k_tbl = [int(x) for x in src_k_layers.a.tolist()]
    v_tbl = [int(x) for x in src_v_layers.a.tolist()]
    for s, d in zip(src, dst):
        for layer in range(num_layers):
            for tbl, b in ((k_tbl, dst_k), (v_tbl, dst_v)):
                # get_global_offset_lf_tbl(src) / get_global_offset_pf(dst)
                _copy(b.data_ptr() + d * dst_layout_dim + layer * item_size,
                      tbl[layer] + s * item_size,
                      item_size, "transfer_kv_all_layer_lf_pf")


def transfer_kv_per_layer(*args, **kwargs):
    raise AssertionError("layer_first path is not expected for nvfp4_qsa")


transfer_kv_all_layer = transfer_kv_per_layer
transfer_kv_all_layer_lf_ph = transfer_kv_per_layer
transfer_kv_per_layer_ph_lf = transfer_kv_per_layer
transfer_kv_direct = transfer_kv_per_layer
transfer_kv_per_layer_mla = transfer_kv_per_layer
transfer_kv_per_layer_mla_pf_lf = transfer_kv_per_layer
transfer_kv_all_layer_mla = transfer_kv_per_layer
transfer_kv_all_layer_mla_lf_pf = transfer_kv_per_layer


def _direct_indices(t):
    return [int(x) for x in t.a.tolist()]  # the op calls .cpu() itself


def transfer_kv_all_layer_direct_lf_pf(src_ptrs, dst_ptrs, src_indices, dst_indices, page_size):
    CALLS.append(("sgl.direct_lf_pf", page_size))
    src = _direct_indices(src_indices)
    dst = _direct_indices(dst_indices)
    assert len(src) == len(dst) and len(src) % page_size == 0
    is_mla = len(dst_ptrs) == 1
    num_layers = len(src_ptrs) if is_mla else len(src_ptrs) // 2
    elem = dst_ptrs[0].element_size()
    dst_stride0, dst_stride1 = dst_ptrs[0].stride(0), dst_ptrs[0].stride(1)
    src_stride0 = src_ptrs[0].stride(0)
    copy_bytes = page_size * src_stride0 * elem
    for i in range(len(src) // page_size):
        s_index = src[i * page_size]
        d_index = dst[i * page_size] // page_size
        for j in range(num_layers):
            pairs = [(src_ptrs[j], dst_ptrs[0])]
            if not is_mla:
                pairs.append((src_ptrs[j + num_layers], dst_ptrs[1]))
            for a, b in pairs:
                # batch path (strides) ...
                _copy(b.data_ptr() + d_index * dst_stride0 * elem + j * dst_stride1 * elem,
                      a.data_ptr() + s_index * src_stride0 * elem,
                      copy_bytes, "transfer_kv_all_layer_direct_lf_pf")
                # ... and the fallback's copy_ needs equal shapes
                dst_view = b[d_index][j][0:page_size]
                src_view = a[s_index : s_index + page_size]
                assert dst_view.shape == src_view.shape, (dst_view.shape, src_view.shape)
                assert b.dtype == a.dtype


def transfer_kv_per_layer_direct_pf_lf(src_ptrs, dst_ptrs, src_indices, dst_indices, layer_id, page_size):
    CALLS.append(("sgl.direct_pf_lf", page_size))
    src = _direct_indices(src_indices)
    dst = _direct_indices(dst_indices)
    assert len(src) == len(dst) and len(src) % page_size == 0
    is_mla = len(src_ptrs) == 1
    num_layers = len(dst_ptrs) if is_mla else len(dst_ptrs) // 2
    elem = src_ptrs[0].element_size()
    src_stride0, src_stride1 = src_ptrs[0].stride(0), src_ptrs[0].stride(1)
    dst_stride0 = dst_ptrs[0].stride(0)
    copy_bytes = page_size * dst_stride0 * elem
    for i in range(len(src) // page_size):
        s_index = src[i * page_size] // page_size
        d_index = dst[i * page_size]
        for j in range(num_layers):
            pairs = [(src_ptrs[0], dst_ptrs[j])]
            if not is_mla:
                pairs.append((src_ptrs[1], dst_ptrs[j + num_layers]))
            for a, b in pairs:
                _copy(b.data_ptr() + d_index * dst_stride0 * elem,
                      a.data_ptr() + s_index * src_stride0 * elem + (layer_id + j) * src_stride1 * elem,
                      copy_bytes, "transfer_kv_per_layer_direct_pf_lf")
                src_view = a[s_index][layer_id + j][0:page_size]
                dst_view = b[d_index : d_index + page_size]
                assert dst_view.shape == src_view.shape, (dst_view.shape, src_view.shape)
                assert b.dtype == a.dtype


# ----------------------------------------------------------------------------
# sglang.kernels.ops.kvcache.hicache (JIT)
# ----------------------------------------------------------------------------


def _default_unroll(element_size):
    if element_size <= 512:
        return 4
    if element_size <= 1024:
        return 2
    return 1


def can_use_hicache_jit_kernel(*, element_size, unroll=None, block_quota=None):
    if element_size % 128 != 0:
        return False
    unroll = unroll or _default_unroll(element_size)
    k_num_threads = 32 // unroll
    assert 128 % k_num_threads == 0
    return JIT_OK["one"]


def can_use_write_back_jit_kernel(*, element_size, unroll=None, block_quota=None):
    if element_size % 16 != 0:
        return False
    return JIT_OK["staged"]


def _matcher_2d(t, D):
    # TensorMatcher({-1, D}).with_strides({N, 1})
    assert t.dim() == 2 and t.size(1) == D, (t.shape, D)
    assert t.stride(1) == 1 or t.size(1) == 1
    return t.stride(0)


def transfer_hicache_one_layer(k_cache_dst, v_cache_dst, indices_dst, k_cache_src, v_cache_src,
                               indices_src, *, element_dim=None, unroll=None, block_quota=None):
    CALLS.append(("jit.one_layer", element_dim))
    element_dim = element_dim or k_cache_dst.size(-1)
    k_cache_src = k_cache_src.view(-1, element_dim)
    v_cache_src = v_cache_src.view(-1, element_dim)
    k_cache_dst = k_cache_dst.view(-1, element_dim)
    v_cache_dst = v_cache_dst.view(-1, element_dim)
    element_size = element_dim * k_cache_dst.element_size()
    assert element_size % 128 == 0, "load_vec needs a multiple of 128 bytes"
    dtype = k_cache_dst.dtype
    assert k_cache_src.dtype == v_cache_src.dtype == v_cache_dst.dtype == dtype
    n_src = _matcher_2d(k_cache_src, element_dim)
    assert _matcher_2d(v_cache_src, element_dim) == n_src
    m_dst = _matcher_2d(k_cache_dst, element_dim)
    assert _matcher_2d(v_cache_dst, element_dim) == m_dst
    assert indices_src.dtype == indices_dst.dtype
    src = _idx(indices_src, cuda=True, dtypes=(torch.int32, torch.int64))
    dst = _idx(indices_dst, cuda=True, dtypes=(torch.int32, torch.int64))
    assert len(src) == len(dst)
    isz = dtype.itemsize
    for s, d in zip(src, dst):
        for a, b in ((k_cache_src, k_cache_dst), (v_cache_src, v_cache_dst)):
            src_addr = a.data_ptr() + s * n_src * isz
            dst_addr = b.data_ptr() + d * m_dst * isz
            pkg = 128 // (32 // (unroll or _default_unroll(element_size)))
            assert src_addr % pkg == 0 and dst_addr % pkg == 0, "misaligned vector access"
            _copy(dst_addr, src_addr, element_size, "transfer_hicache_one_layer")


def transfer_hicache_all_layer(*args, **kwargs):
    raise AssertionError("layer_first JIT path is not expected for nvfp4_qsa")


transfer_hicache_all_layer_mla = transfer_hicache_all_layer
transfer_hicache_one_layer_mla = transfer_hicache_all_layer
transfer_hicache_all_layer_mla_staged_lf_pf = transfer_hicache_all_layer


def transfer_hicache_all_layer_staged_lf_pf(k_ptr_src, v_ptr_src, src_indices, dst_indices,
                                            staging_k, staging_v, dst_k, dst_v, *, page_size,
                                            element_size=None, unroll=None, block_quota=None):
    CALLS.append(("jit.staged_lf_pf", staging_k[0, 0].numel()))
    element_dim = staging_k[0, 0].numel()
    element_size = element_size or (element_dim * staging_k.element_size())
    src_page_indices = src_indices[::page_size].contiguous()
    staging_page_capacity = staging_k.shape[0] // page_size
    staging_k = staging_k.view(staging_k.shape[0], staging_k.shape[1], -1)
    staging_v = staging_v.view(staging_v.shape[0], staging_v.shape[1], -1)
    dst_k = dst_k.view(dst_k.shape[0], dst_k.shape[1], -1)
    dst_v = dst_v.view(dst_v.shape[0], dst_v.shape[1], -1)
    num_pages = src_page_indices.numel()
    for page_begin in range(0, num_pages, staging_page_capacity):
        chunk_pages = min(staging_page_capacity, num_pages - page_begin)
        chunk_tokens = chunk_pages * page_size
        _run_staged(dst_k, dst_v,
                    dst_indices[page_begin * page_size : (page_begin + chunk_pages) * page_size],
                    staging_k[:chunk_tokens], staging_v[:chunk_tokens],
                    src_page_indices[page_begin : page_begin + chunk_pages],
                    k_ptr_src, v_ptr_src, page_size, element_size)


def _run_staged(k_dst, v_dst, dst_indices_cpu, staging_k, staging_v, page_indices_src,
                k_ptr_src, v_ptr_src, page_size, k_element_size):
    T, N, D = staging_k.shape
    for st in (staging_k, staging_v):
        assert st.shape == (T, N, D) and st.is_contiguous() and st.is_cuda
    for d in (k_dst, v_dst):
        assert d.dim() == 3 and d.shape[1:] == (N, D) and d.is_contiguous() and not d.is_cuda
    for tbl in (k_ptr_src, v_ptr_src):
        assert tbl.shape == (N,) and tbl.dtype is torch.uint64 and tbl.is_cuda
    pages = _idx(page_indices_src, cuda=True, dtypes=(torch.int32, torch.int64))
    dsts = _idx(dst_indices_cpu, cuda=False, dtypes=(torch.int64,))
    assert dst_indices_cpu.is_contiguous()
    assert T == len(pages) * page_size and len(dsts) == T, "staging token count mismatch"
    assert k_element_size == D * staging_k.element_size(), "element size mismatch"
    assert k_element_size % 16 == 0
    E = k_element_size
    for tbl_t, st in ((k_ptr_src, staging_k), (v_ptr_src, staging_v)):
        tbl = [int(x) for x in tbl_t.a.tolist()]
        # hicache_relayout_kernel: staging[p * ps + t, layer] <- src[layer][page + t]
        for p, src_page in enumerate(pages):
            for t in range(page_size):
                for layer in range(N):
                    _copy(st.data_ptr() + ((p * page_size + t) * N + layer) * E,
                          tbl[layer] + (src_page + t) * E, E, "hicache_relayout_kernel")
    for st, d in ((staging_k, k_dst), (staging_v, v_dst)):
        elem = st.element_size()
        src_page_bytes = page_size * st.stride(0) * elem
        dst_page_bytes = page_size * d.stride(0) * elem
        assert src_page_bytes == dst_page_bytes, "Source and destination page spans must match"
        for p in range(len(pages)):
            _copy(d.data_ptr() + dsts[p * page_size] * d.stride(0) * elem,
                  st.data_ptr() + p * page_size * st.stride(0) * elem,
                  src_page_bytes, "copy_page_first_pages")
