"""GPU round trip of the nvfp4_qsa HiCache host tier (qsakv4h) on Daniel Franzen's fork.

Run in his venv on the GPU (RTX PRO 6000 / SM120), no server running, with the
qsaring + qsakv4 + qsakv4h patched files installed over his sglang:

    python test_hicache_nvfp4.py            # correctness, about a minute
    python test_hicache_nvfp4.py --bench    # also time nvfp4_qsa vs FP8 host transfers

What it builds is what build_hybrid_mamba_stack builds for the attention side (the
Mamba pool aside): the real QSATokenToKVPool with nvfp4_qsa KV (its full_kv_pool is
the MHATokenToKVPool + NVFP4QSAKVCacheMethod the server uses) and the MTP draft
QSATokenToKVPool, the host pool get_mha_host_pool_cls picks, the QSA compressed
sidecar host pool, a HostPoolGroup with the server's layer mappings (the packed draft
layer included) and the real HybridCacheController with its L2TransferEngine.

Each case writes random K/V through the pool's quantize-and-store path
(set_kv_buffer with the per-layer device global scales), backs 80 shuffled device
pages up with controller.write() into shuffled host pages, then requires:
  host      the host buffers hold exactly the device rows at the host slots (packed
            rows, block scales, draft rows) and every other host byte is untouched;
  round     after clobbering the device pages, controller.load() + start_loading()
            into 80 other device pages restores packed rows, block scales, draft rows
            and QSA compressed keys byte for byte, and no other device row changed.
Cases: kernel io + page_first (JIT kernels, and the sgl_kernel fallbacks), direct io +
page_first_direct; MTP draft FP8 / BF16 / inheriting nvfp4_qsa / none. 80 pages is
more than the 64-page staging chunk, so the staged write-back runs two chunks.
Also checked: the host bytes per token --hicache-size is split with, FP8 pools still
getting MHATokenToKVPoolHost and the old size formula, and the refusals.

Prints one JSON line; exit status 1 on any failure.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
import traceback
from types import SimpleNamespace

import torch

DEVICE = "cuda"
HEADS, DIM, PAGE = 2, 256, 64  # Qwen3.8-Flash-Next full-attention layers, page 64
LAYER_IDS = (3, 7, 11)  # absolute ids of three QSA layers (pool slots 0, 1, 2)
MODEL_LAYERS = 12  # transfer_layer_num: the linear-attention layers in between
GLOBAL_SCALES = {3: (0.5, 1.25), 7: (1.75, 0.6), 11: (1.0, 3.0), 0: (0.8, 1.6)}
QSA = dict(
    qsa_index_kv_heads=1,
    qsa_index_head_dim=128,
    qsa_compress_ratio=4,
    qsa_token_topk=2048,
    num_request_slots=8,
)
DEVICE_PAGES = 256  # device pool: 16384 tokens (+ the padding page)
HOST_RATIO = 2.0  # host pool: 2x the device pool, as --hicache-ratio
N_PAGES = 80  # pages per transfer; above the 64-page staging chunk
FILL = 0xA5  # host bytes no transfer may touch

RESULTS = {}


def record(name, passed, **fields):
    RESULTS[name] = {"passed": bool(passed), **fields}


def run(name, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except Exception as exc:  # report and keep going; the summary fails
        record(
            name,
            False,
            error=f"{type(exc).__name__}: {exc}",
            traceback=traceback.format_exc(limit=8)[-1500:],
        )


def as_bytes(t):
    return t.contiguous().view(torch.uint8)


# ---------------------------------------------------------------------------
# Pools, as the KV cache configurator builds them
# ---------------------------------------------------------------------------


def build_qsa_pool(kv, layer_ids, pages=DEVICE_PAGES):
    from sglang.srt.mem_cache.qsa_kv_pool import QSATokenToKVPool

    quant_method = None
    if kv == "nvfp4_qsa":
        from sglang.srt.layers.quantization.fp4_kv_cache_quant_method import (
            get_kv_cache_quant_method,
        )

        quant_method = get_kv_cache_quant_method(
            "nvfp4_qsa", num_layers=len(layer_ids), device=DEVICE
        )
        for layer_id in layer_ids:
            k_gs, v_gs = GLOBAL_SCALES.get(layer_id, (1.0, 1.0))
            quant_method.k_scales_gpu[layer_id].fill_(k_gs)
            quant_method.v_scales_gpu[layer_id].fill_(v_gs)
        dtype = torch.float4_e2m1fn_x2
    elif kv == "fp8":
        dtype = torch.float8_e4m3fn
    elif kv == "bf16":
        dtype = torch.bfloat16
    else:
        raise ValueError(kv)
    return QSATokenToKVPool(
        size=pages * PAGE,
        dtype=dtype,
        page_size=PAGE,
        head_num=HEADS,
        head_dim=DIM,
        full_attention_layer_ids=list(layer_ids),
        device=DEVICE,
        mamba_pool=None,  # stored only; the Mamba host pool is not under test
        quant_method=quant_method,
        **QSA,
    )


class StubAllocator:
    """The token_to_kv_pool_allocator the controller asks for the kvcache and for
    load destinations; alloc() hands out the slots the test chose."""

    def __init__(self, kvcache):
        self.kvcache = kvcache
        self.next_slots = None

    def get_kvcache(self):
        return self.kvcache

    def alloc(self, need_size):
        slots, self.next_slots = self.next_slots, None
        assert slots is not None and slots.numel() == need_size
        return slots

    def free(self, indices):
        pass


def build_stack(target, draft, layout, io_backend, jit=True, model_layers=MODEL_LAYERS):
    """build_hybrid_mamba_stack's KV + QSA-compressed entries and controller."""
    from sglang.srt.mem_cache.hicache_storage import PoolName
    from sglang.srt.mem_cache.hybrid_cache.hybrid_cache_controller import (
        HybridCacheController,
    )
    from sglang.srt.mem_cache.hybrid_cache.hybrid_pool_assembler import (
        _with_mtp_layer_mapping,
        build_pool_entry,
    )
    from sglang.srt.mem_cache.pool_host import HostPoolGroup
    from sglang.srt.mem_cache.pool_host.mha import get_mha_host_pool_cls
    from sglang.srt.mem_cache.pool_host.qsa import QSACompressedPoolHost

    kv_pool = target.full_kv_pool
    mtp_draft_device_pools = (draft.full_kv_pool,) if draft is not None else ()
    mtp_qsa_device_pools = (draft,) if draft is not None else ()
    kwargs = {}
    if mtp_draft_device_pools:  # build_kv_host_pool passes it only when present
        kwargs["mtp_draft_device_pools"] = mtp_draft_device_pools
    kv_host = get_mha_host_pool_cls(kv_pool)(
        kv_pool,
        HOST_RATIO,
        0,
        PAGE,
        layout,
        allocator_type="default",
        pool_label="kv",
        **kwargs,
    )
    if not jit:
        # Force the sgl_kernel paths (per-layer loads, transfer_kv_all_layer_lf_pf
        # write-back) before the group reads the flag.
        kv_host.can_use_write_back_jit = False
        kv_host.can_use_jit = False
        for segment in kv_host._segments:
            segment.can_use_jit = False
    full_layer_mapping = dict(target.full_attention_layer_id_mapping)
    if mtp_draft_device_pools:
        full_layer_mapping = _with_mtp_layer_mapping(
            full_layer_mapping,
            transfer_layer_start=model_layers,
            target_device_layer_num=kv_pool.layer_num,
            draft_layer_num=len(mtp_draft_device_pools),
        )
    qsa_host = QSACompressedPoolHost(
        target,
        kv_host,
        layout,
        draft_device_pools=mtp_qsa_device_pools,
        allocator_type="default",
    )
    group = HostPoolGroup(
        [
            build_pool_entry(
                name=PoolName.KV,
                host_pool=kv_host,
                device_pool=kv_pool,
                layer_mapping=full_layer_mapping,
                transfer_layer_num=model_layers + len(mtp_draft_device_pools),
                is_anchor=True,
                packed_draft_device_pools=mtp_draft_device_pools,
            ),
            build_pool_entry(
                name=PoolName.QSA_COMPRESSED,
                host_pool=qsa_host,
                device_pool=target,
                layer_mapping=full_layer_mapping,
                transfer_layer_num=model_layers + len(mtp_qsa_device_pools),
                packed_draft_device_pools=mtp_qsa_device_pools,
            ),
        ]
    )
    allocator = StubAllocator(target)
    controller = HybridCacheController(
        allocator,
        group,
        PAGE,
        None,
        load_cache_event=threading.Event(),
        write_policy="write_through",
        io_backend=io_backend,
        storage_backend=None,
        transfer_layer_num=model_layers,
    )
    return SimpleNamespace(
        kv_host=kv_host,
        qsa_host=qsa_host,
        group=group,
        allocator=allocator,
        controller=controller,
    )


def qsa_extra_pools():
    from sglang.srt.mem_cache.hicache_storage import PoolName, PoolTransfer

    # What the tree sends for the QSA compressed sidecar (indices ride the KV's).
    return [PoolTransfer(name=PoolName.QSA_COMPRESSED, indices_from_pool=PoolName.KV)]


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


def make_kv(rows, seed):
    g = torch.Generator(device="cpu").manual_seed(seed)
    x = torch.randn(rows, HEADS, DIM, generator=g)
    x[..., torch.randperm(DIM, generator=g)[:4]] *= 20.0  # outlier channels
    x *= torch.rand(rows, HEADS, 1, generator=g) * 4  # varied block scales
    return x.to(torch.bfloat16).to(DEVICE)


def pages_to_slots(pages, page_size=PAGE):
    return (pages[:, None] * page_size + torch.arange(page_size)).reshape(-1)


def write_kv(pool, layer_ids, slots, seed):
    """K/V through the pool's real write path (what the QSA backend's _save_kv calls)."""
    from sglang.srt.mem_cache.pool_host.mha import is_nvfp4_qsa_kv_pool

    nvfp4 = is_nvfp4_qsa_kv_pool(pool.full_kv_pool)
    for offset, layer_id in enumerate(layer_ids):
        k = make_kv(slots.numel(), seed + 2 * offset)
        v = make_kv(slots.numel(), seed + 2 * offset + 1)
        layer = SimpleNamespace(layer_id=layer_id)
        if nvfp4:
            pool.set_kv_buffer(layer, slots, k, v, k_scale=None, v_scale=None)
        else:
            pool.set_kv_buffer(layer, slots, k, v)


def device_kv_buffers(pool):
    """Every per-slot device buffer HiCache must carry for this pool's full layers."""
    full = pool.full_kv_pool
    buffers = {}
    for i in range(len(full.k_buffer)):
        buffers[f"k{i}"] = full.k_buffer[i]
        buffers[f"v{i}"] = full.v_buffer[i]
        if getattr(full, "k_scale_buffer", None) is not None:
            buffers[f"k_scale{i}"] = full.k_scale_buffer[i]
            buffers[f"v_scale{i}"] = full.v_scale_buffer[i]
    return buffers


def compressed_slots(pages):
    per_page = PAGE // QSA["qsa_compress_ratio"]
    return pages_to_slots(pages, per_page)


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_case(name, layout, io_backend, draft_kv, jit=True, seed=0):
    from sglang.srt.mem_cache.hybrid_cache.hybrid_pool_assembler import (
        _kv_host_bytes_per_token,
    )
    from sglang.srt.mem_cache.pool_host.mha import NVFP4QSAMHATokenToKVPoolHost

    target = build_qsa_pool("nvfp4_qsa", LAYER_IDS)
    draft = build_qsa_pool(draft_kv, (0,)) if draft_kv else None
    stack = build_stack(target, draft, layout, io_backend, jit=jit)
    kv_host, controller = stack.kv_host, stack.controller
    facts = {
        "host_class": type(kv_host).__name__,
        "can_use_write_back_jit": bool(kv_host.can_use_write_back_jit),
        "segments": [
            [s.name, s.num_layers, s.row_bytes, bool(s.page_major), bool(s.can_use_jit)]
            for s in kv_host._segments
        ],
    }
    ok = isinstance(kv_host, NVFP4QSAMHATokenToKVPoolHost)

    # Size accounting: what --hicache-size is split with == what is allocated.
    drafts = (draft.full_kv_pool,) if draft is not None else ()
    allocated = sum(t.numel() * t.element_size() for t in kv_host.kv_buffer)
    facts["size_per_token"] = kv_host.size_per_token
    facts["accounting_ok"] = bool(
        kv_host.size_per_token
        == NVFP4QSAMHATokenToKVPoolHost.host_bytes_per_token(target.full_kv_pool, drafts)
        == _kv_host_bytes_per_token(target.full_kv_pool, drafts)
        and allocated == kv_host.size * kv_host.size_per_token
    )

    # The segments cover exactly the device buffers the pools own.
    expected_ptrs = {t.data_ptr() for t in device_kv_buffers(target).values()}
    if draft is not None:
        expected_ptrs |= {t.data_ptr() for t in device_kv_buffers(draft).values()}
    segment_ptrs = {
        t.data_ptr()
        for s in kv_host._segments
        for t in s.device_k + s.device_v
    }
    facts["segments_cover_pools"] = segment_ptrs == expected_ptrs

    # Device pages: 80 to back up, 80 other ones to load into, the rest untouched.
    g = torch.Generator(device="cpu").manual_seed(1000 + seed)
    perm = torch.randperm(DEVICE_PAGES, generator=g) + 1  # page 0 is the padding page
    src_pages, dst_pages = perm[:N_PAGES], perm[N_PAGES : 2 * N_PAGES]
    src_slots = pages_to_slots(src_pages).to(DEVICE)
    dst_slots = pages_to_slots(dst_pages).to(DEVICE)
    src_cslots = compressed_slots(src_pages).to(DEVICE)
    dst_cslots = compressed_slots(dst_pages).to(DEVICE)

    pools = [("target", target, LAYER_IDS)]
    if draft is not None:
        pools.append(("draft", draft, (0,)))
    write_ok = True
    for tag, pool, layer_ids in pools:
        try:
            write_kv(pool, layer_ids, src_slots, seed=100 * seed + len(tag))
        except Exception as exc:  # fall back so the transfer paths still run
            write_ok = False
            facts[f"write_error_{tag}"] = f"{type(exc).__name__}: {exc}"
            for buffer in device_kv_buffers(pool).values():
                as_bytes(buffer)[src_slots] = torch.randint(
                    0, 256, as_bytes(buffer)[src_slots].shape,
                    dtype=torch.uint8, device=DEVICE,
                )
        for buffer in pool.qsa_compressed_k_buffer_pool:
            buffer[src_cslots] = torch.randn(
                buffer[src_cslots].shape, device=DEVICE
            ).to(buffer.dtype)
    torch.cuda.synchronize()
    facts["write_path_ok"] = write_ok
    scales_live = all(
        bool(as_bytes(t)[src_slots].any())
        for key, t in device_kv_buffers(target).items()
        if "scale" in key
    )
    facts["scales_nonzero"] = scales_live

    # Everything the round trip must reproduce, keyed by buffer.
    tracked = {}
    for tag, pool, _ in pools:
        for key, t in device_kv_buffers(pool).items():
            tracked[f"{tag}.{key}"] = (t, src_slots, dst_slots)
        for i, t in enumerate(pool.qsa_compressed_k_buffer_pool):
            tracked[f"{tag}.qsa{i}"] = (t, src_cslots, dst_cslots)
    expected_rows = {
        key: as_bytes(t[src]).clone() for key, (t, src, _) in tracked.items()
    }

    # Host: fill every host byte, shuffle the free list so the 80 host pages are
    # neither contiguous nor ordered.
    for s in kv_host._segments:
        as_bytes(s.host_k).fill_(FILL)
        as_bytes(s.host_v).fill_(FILL)
    held = kv_host.alloc(kv_host.logical_size)
    host_pages = torch.randperm(kv_host.page_num, generator=g)[:N_PAGES]
    for page in host_pages.tolist():
        kv_host.free(held[page * PAGE : (page + 1) * PAGE])

    # Back up: controller.write -> start_writing -> L2TransferEngine D2H.
    host_indices = controller.write(src_slots, node_id=1, extra_pools=qsa_extra_pools())
    torch.cuda.synchronize()
    host_ok = host_indices is not None and torch.equal(
        host_indices.cpu().reshape(-1, PAGE)[:, 0] // PAGE, host_pages
    )
    facts["host_pages_shuffled"] = host_ok
    host_cpu = host_indices.cpu()
    host_bad = []
    for s in kv_host._segments:
        for kind, device_list, host_buffer in (
            ("k", s.device_k, s.host_k),
            ("v", s.device_v, s.host_v),
        ):
            want = torch.full_like(as_bytes(host_buffer), FILL)
            for layer, device_buffer in enumerate(device_list):
                rows = as_bytes(device_buffer[src_slots]).cpu()
                if s.page_major:
                    want[host_cpu // PAGE, layer, host_cpu % PAGE] = rows
                else:
                    want[host_cpu, layer] = rows
            if not torch.equal(as_bytes(host_buffer), want):
                host_bad.append(f"{s.name}.{kind}")
    facts["host_layout_bad"] = host_bad

    # Clobber both page sets everywhere, then remember the whole device state.
    for key, (t, src, dst) in tracked.items():
        for slots in (src, dst):
            as_bytes(t)[slots] = torch.randint(
                0, 256, as_bytes(t)[slots].shape, dtype=torch.uint8, device=DEVICE
            )
    torch.cuda.synchronize()
    clobbered = {key: as_bytes(t).clone() for key, (t, _, _) in tracked.items()}

    # Load into other pages: controller.load -> start_loading -> per-layer H2D.
    stack.allocator.next_slots = dst_slots
    loaded = controller.load(host_indices, node_id=2, extra_pools=qsa_extra_pools())
    controller.start_loading()
    torch.cuda.synchronize()
    round_bad = []
    for key, (t, _, dst) in tracked.items():
        want = clobbered[key]
        want[dst] = expected_rows[key]
        if not torch.equal(as_bytes(t), want):
            round_bad.append(key)
    facts["round_trip_bad"] = round_bad
    facts["load_slots_ok"] = loaded is not None and torch.equal(loaded, dst_slots)

    ok = ok and all(
        facts[k]
        for k in (
            "accounting_ok",
            "segments_cover_pools",
            "write_path_ok",
            "scales_nonzero",
            "host_pages_shuffled",
            "load_slots_ok",
        )
    )
    ok = ok and not host_bad and not round_bad
    record(name, ok, layout=layout, io_backend=io_backend, draft=draft_kv, jit=jit, **facts)
    stack.group.destroy()
    del stack, target, draft
    torch.cuda.empty_cache()


def check_dispatch_and_refusals():
    from sglang.srt.mem_cache.hybrid_cache.hybrid_pool_assembler import (
        _kv_host_bytes_per_token,
    )
    from sglang.srt.mem_cache.pool_host.mha import (
        MHATokenToKVPoolHost,
        NVFP4QSAMHATokenToKVPoolHost,
        get_mha_host_pool_cls,
    )

    facts = {}
    fp8 = build_qsa_pool("fp8", LAYER_IDS, pages=8)
    fp8_draft = build_qsa_pool("fp8", (0,), pages=8)
    nv = build_qsa_pool("nvfp4_qsa", LAYER_IDS, pages=8)

    # FP8 keeps the old class and the old --hicache-size formula.
    facts["fp8_class_ok"] = get_mha_host_pool_cls(fp8.full_kv_pool) is MHATokenToKVPoolHost
    old_formula = DIM * HEADS * (len(LAYER_IDS) + 1) * 1 * 2
    facts["fp8_formula_ok"] = (
        _kv_host_bytes_per_token(fp8.full_kv_pool, (fp8_draft.full_kv_pool,))
        == old_formula
    )
    fp8_host = MHATokenToKVPoolHost(
        fp8.full_kv_pool,
        HOST_RATIO,
        0,
        PAGE,
        "page_first",
        mtp_draft_device_pools=(fp8_draft.full_kv_pool,),
    )
    facts["fp8_host_size_ok"] = fp8_host.size_per_token == old_formula
    fp8_host.destroy()
    facts["nvfp4_class_ok"] = (
        get_mha_host_pool_cls(nv.full_kv_pool) is NVFP4QSAMHATokenToKVPoolHost
    )

    # Per-token host bytes: target layers alone, and the production shape
    # (12 QSA layers + one FP8 MTP draft layer) from the same per-layer numbers.
    per_layer = NVFP4QSAMHATokenToKVPoolHost.host_bytes_per_token(nv.full_kv_pool) // len(
        LAYER_IDS
    )
    draft_row = 2 * HEADS * DIM  # FP8 K + V
    facts["nvfp4_bytes_per_target_layer"] = per_layer
    facts["production_bytes_per_token"] = {
        "nvfp4_qsa": 12 * per_layer + draft_row,
        "fp8": 13 * draft_row,
    }
    facts["per_layer_ok"] = per_layer == 2 * HEADS * (DIM // 2 + DIM // 16)

    refusals = {}
    for label, fn in (
        (
            "layer_first",
            lambda: NVFP4QSAMHATokenToKVPoolHost(
                nv.full_kv_pool, HOST_RATIO, 0, PAGE, "layer_first"
            ),
        ),
        (
            "page_head",
            lambda: NVFP4QSAMHATokenToKVPoolHost(
                nv.full_kv_pool, HOST_RATIO, 0, PAGE, "page_head"
            ),
        ),
        (
            "fp8_device_pool",
            lambda: NVFP4QSAMHATokenToKVPoolHost(
                fp8.full_kv_pool, HOST_RATIO, 0, PAGE, "page_first"
            ),
        ),
    ):
        try:
            fn()
            refusals[label] = "accepted"
        except (NotImplementedError, ValueError) as exc:
            refusals[label] = type(exc).__name__
    host = NVFP4QSAMHATokenToKVPoolHost(nv.full_kv_pool, HOST_RATIO, 0, PAGE, "page_first")
    probe = torch.arange(PAGE, dtype=torch.int64)
    for label, fn in (
        ("get_page_buffer_meta", lambda: host.get_page_buffer_meta(probe)),
        ("get_data_page", lambda: host.get_data_page(0)),
        ("set_from_flat_data_page", lambda: host.set_from_flat_data_page(0, probe)),
    ):
        try:
            fn()
            refusals[label] = "accepted"
        except NotImplementedError:
            refusals[label] = "NotImplementedError"
    host.destroy()
    facts["refusals"] = refusals
    passed = all(
        facts[k]
        for k in ("fp8_class_ok", "fp8_formula_ok", "fp8_host_size_ok", "nvfp4_class_ok", "per_layer_ok")
    ) and all(v != "accepted" for v in refusals.values())
    record("dispatch_and_refusals", passed, **facts)
    del fp8, fp8_draft, nv
    torch.cuda.empty_cache()


def bench(kv, pages, iters=5):
    """Median write and load time of `pages` pages, production layer counts."""
    layer_ids = tuple(range(3, 48, 4))  # 12 QSA layers
    target = build_qsa_pool(kv, layer_ids, pages=2 * pages + 8)
    draft = build_qsa_pool("fp8", (0,), pages=2 * pages + 8)
    stack = build_stack(target, draft, "page_first", "kernel", model_layers=48)
    perm = torch.randperm(2 * pages + 8) + 1
    src_slots = pages_to_slots(perm[:pages]).to(DEVICE)
    dst_slots = pages_to_slots(perm[pages : 2 * pages]).to(DEVICE)
    write_ms, load_ms = [], []
    for _ in range(iters):
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        host_indices = stack.controller.write(
            src_slots, node_id=1, extra_pools=qsa_extra_pools()
        )
        torch.cuda.synchronize()
        t1 = time.perf_counter()
        stack.allocator.next_slots = dst_slots
        stack.controller.load(host_indices, node_id=2, extra_pools=qsa_extra_pools())
        stack.controller.start_loading()
        torch.cuda.synchronize()
        t2 = time.perf_counter()
        stack.group.free(host_indices)
        write_ms.append((t1 - t0) * 1e3)
        load_ms.append((t2 - t1) * 1e3)
    tokens = pages * PAGE
    kv_bytes = tokens * stack.kv_host.size_per_token
    result = {
        "host_class": type(stack.kv_host).__name__,
        "tokens": tokens,
        "kv_host_bytes_per_token": stack.kv_host.size_per_token,
        "write_ms": round(sorted(write_ms)[iters // 2], 3),
        "load_ms": round(sorted(load_ms)[iters // 2], 3),
        "write_kv_gbps": round(kv_bytes / sorted(write_ms)[iters // 2] / 1e6, 2),
        "load_kv_gbps": round(kv_bytes / sorted(load_ms)[iters // 2] / 1e6, 2),
    }
    stack.group.destroy()
    del stack, target, draft
    torch.cuda.empty_cache()
    return result


def check_bench(pages):
    record(
        "bench",
        True,
        info=True,
        pages=pages,
        fp8=bench("fp8", pages),
        nvfp4_qsa=bench("nvfp4_qsa", pages),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--bench", action="store_true", help="time host transfers")
    parser.add_argument("--bench-pages", type=int, default=1024)
    args = parser.parse_args()

    if not torch.cuda.is_available():
        print(json.dumps({"summary": "hicache_nvfp4", "passed": False, "error": "no CUDA device"}))
        return 1
    if not hasattr(torch, "float4_e2m1fn_x2"):
        print(json.dumps({"summary": "hicache_nvfp4", "passed": False, "error": "torch without float4_e2m1fn_x2"}))
        return 1

    cases = (
        ("kernel_page_first_fp8_draft", "page_first", "kernel", "fp8", True),
        ("kernel_page_first_fp8_draft_nojit", "page_first", "kernel", "fp8", False),
        ("kernel_page_first_nvfp4_draft", "page_first", "kernel", "nvfp4_qsa", True),
        ("kernel_page_first_bf16_draft", "page_first", "kernel", "bf16", True),
        ("kernel_page_first_no_draft", "page_first", "kernel", None, True),
        ("direct_page_first_direct_fp8_draft", "page_first_direct", "direct", "fp8", True),
        ("direct_page_first_direct_nvfp4_draft", "page_first_direct", "direct", "nvfp4_qsa", True),
    )
    for seed, (name, layout, io_backend, draft_kv, jit) in enumerate(cases):
        run(name, check_case, name, layout, io_backend, draft_kv, jit=jit, seed=seed)
    run("dispatch_and_refusals", check_dispatch_and_refusals)
    if args.bench:
        run("bench", check_bench, args.bench_pages)

    failed = sorted(name for name, r in RESULTS.items() if not r["passed"])
    summary = {
        "summary": "hicache_nvfp4",
        "passed": not failed and bool(RESULTS),
        "failed": failed,
        "device": torch.cuda.get_device_name(0),
        "capability": list(torch.cuda.get_device_capability(0)),
        "checks": RESULTS,
    }
    print(json.dumps(summary, sort_keys=True, default=str), flush=True)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
