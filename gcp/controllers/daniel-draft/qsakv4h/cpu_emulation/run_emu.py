"""CPU emulation (numpy only, no torch, no GPU) of every nvfp4_qsa host-pool transfer path.

Loads the real pool_host/base.py and pool_host/common.py from Daniel's wheel and the
patched pool_host/mha.py, with fake_torch standing in for torch and fake_kernels for
the CUDA kernels (byte-exact offset emulation, bounds-checked).

    python run_emu.py   # prints JSON; "failed": [] when every path round-trips
    python mutate.py    # each deliberate bug must make some case fail
"""

from __future__ import annotations

import importlib.util
import json
import random
import sys
import types
from types import SimpleNamespace

import numpy as np

import os  # noqa: E402

sys.dont_write_bytecode = True  # never leave .pyc next to the wheel or patched sources

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import fake_kernels  # noqa: E402
import fake_torch  # noqa: E402

# Daniel's wheel, extracted; base.py and common.py are loaded from it unchanged.
WHEEL = os.environ.get("SGLANG_SRT_DIR", r"D:\codex-work\daniel-draft\wheel\full\sglang\srt")
PATCHED = os.path.join(HERE, "..", "patched", "sglang", "srt")


def module(name, **attrs):
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod


def package(name):
    mod = module(name)
    mod.__path__ = []
    return mod


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# --- stub module graph -------------------------------------------------------
sys.modules["torch"] = fake_torch
for pkg in (
    "sglang",
    "sglang.srt",
    "sglang.srt.mem_cache",
    "sglang.srt.mem_cache.pool_host",
    "sglang.srt.mem_cache.storage",
    "sglang.srt.distributed",
    "sglang.kernels",
    "sglang.kernels.ops",
    "sglang.kernels.ops.kvcache",
    "sgl_kernel",
):
    package(pkg)


class _Env:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


module("sglang.srt.environ", envs=SimpleNamespace(SGLANG_HICACHE_TORCH_PINNED_ALLOC=_Env(False)))
module(
    "sglang.srt.utils",
    is_cuda=lambda: True,
    is_hip=lambda: False,
    is_npu=lambda: False,
    is_xpu=lambda: False,
    is_mps=lambda: False,
)
module("sglang.srt.runtime_context", get_parallel=lambda: SimpleNamespace(config=SimpleNamespace(nnodes=1)))
module("sglang.srt.distributed.parallel_state", get_world_group=lambda: None)


class KVCache:  # annotation-only stand-ins
    pass


module(
    "sglang.srt.mem_cache.memory_pool",
    KVCache=KVCache,
    MHATokenToKVPool=KVCache,
    MHATokenToKOnlyPool=KVCache,
)


def alloc_mmap(dims, dtype):
    return fake_torch.zeros(dims, dtype=dtype, device="cpu")


module("sglang.srt.mem_cache.storage.mmap", alloc_mmap=alloc_mmap)
module("sglang.kernels.ops.kvcache.hicache", **{
    k: getattr(fake_kernels, k)
    for k in (
        "can_use_hicache_jit_kernel",
        "can_use_write_back_jit_kernel",
        "transfer_hicache_all_layer",
        "transfer_hicache_all_layer_mla",
        "transfer_hicache_all_layer_mla_staged_lf_pf",
        "transfer_hicache_all_layer_staged_lf_pf",
        "transfer_hicache_one_layer",
        "transfer_hicache_one_layer_mla",
    )
})
module("sgl_kernel.kvcacheio", **{
    k: getattr(fake_kernels, k)
    for k in dir(fake_kernels)
    if k.startswith("transfer_kv")
})
# The budget check is the server's, not under test; this laptop has little free RAM.
module("psutil", virtual_memory=lambda: SimpleNamespace(available=1 << 40))

common = load("sglang.srt.mem_cache.pool_host.common", os.path.join(WHEEL, "mem_cache", "pool_host", "common.py"))
base = load("sglang.srt.mem_cache.pool_host.base", os.path.join(WHEEL, "mem_cache", "pool_host", "base.py"))

mha = load(
    "sglang.srt.mem_cache.pool_host.mha",
    os.environ.get("MHA_PATH", os.path.join(PATCHED, "mem_cache", "pool_host", "mha.py")),
)

torch = fake_torch
HEADS, DIM, PAGE = 2, 256, 64


# --- fake device pools (MHATokenToKVPool's attributes the host pool reads) ----
def fake_pool(kind, layers, pages):
    size = pages * PAGE
    rows = size + PAGE
    p = SimpleNamespace(
        size=size,
        page_size=PAGE,
        head_num=HEADS,
        head_dim=DIM,
        v_head_dim=DIM,
        layer_num=layers,
        start_layer=0,
        end_layer=layers - 1,
        device="cuda",
        layer_shard_enabled=False,
        k_scale_buffer=None,
        v_scale_buffer=None,
    )
    if kind == "nvfp4_qsa":
        p.quant_method = SimpleNamespace(name="nvfp4_qsa")
        p.is_quantized_kv_cache = True
        p.dtype = torch.float4_e2m1fn_x2
        p.store_dtype = torch.uint8
        p.k_buffer = [torch.zeros(rows, HEADS, DIM // 2, dtype=torch.uint8, device="cuda") for _ in range(layers)]
        p.v_buffer = [torch.zeros(rows, HEADS, DIM // 2, dtype=torch.uint8, device="cuda") for _ in range(layers)]
        p.k_scale_buffer = [torch.zeros(rows, HEADS, DIM // 16, dtype=torch.uint8, device="cuda") for _ in range(layers)]
        p.v_scale_buffer = [torch.zeros(rows, HEADS, DIM // 16, dtype=torch.uint8, device="cuda") for _ in range(layers)]
    else:
        p.quant_method = SimpleNamespace(name="unquantized")
        p.is_quantized_kv_cache = False
        if kind == "fp8":
            p.dtype, p.store_dtype = torch.float8_e4m3fn, torch.uint8
        elif kind == "bf16":
            p.dtype = p.store_dtype = torch.bfloat16
        else:
            raise ValueError(kind)
        p.k_buffer = [torch.zeros(rows, HEADS, DIM, dtype=p.store_dtype, device="cuda") for _ in range(layers)]
        p.v_buffer = [torch.zeros(rows, HEADS, DIM, dtype=p.store_dtype, device="cuda") for _ in range(layers)]
    return p


def buffers_of(pool):
    out = {}
    for i in range(len(pool.k_buffer)):
        out[f"k{i}"] = pool.k_buffer[i]
        out[f"v{i}"] = pool.v_buffer[i]
        if pool.k_scale_buffer is not None:
            out[f"ks{i}"] = pool.k_scale_buffer[i]
            out[f"vs{i}"] = pool.v_scale_buffer[i]
    return out


def as_bytes(t):
    return t.contiguous().view(torch.uint8)


def slots_of(pages):
    return (np.asarray(pages)[:, None] * PAGE + np.arange(PAGE)).reshape(-1)


def run_case(layout, io_backend, draft_kind, jit, target_layers=3, dev_pages=40, n_pages=10, seed=0):
    rng = np.random.default_rng(seed)
    fake_torch.reset_allocations()
    fake_kernels.JIT_OK["one"] = jit
    fake_kernels.JIT_OK["staged"] = jit
    fake_kernels.CALLS.clear()
    target = fake_pool("nvfp4_qsa", target_layers, dev_pages)
    drafts = (fake_pool(draft_kind, 1, dev_pages),) if draft_kind else ()
    kwargs = {"mtp_draft_device_pools": drafts} if drafts else {}
    host = mha.get_mha_host_pool_cls(target)(
        target, 2.0, 0, PAGE, layout, pin_memory=False, allocator_type="default", pool_label="kv", **kwargs
    )
    assert isinstance(host, mha.NVFP4QSAMHATokenToKVPoolHost)
    staged_capacity = host.staging_page_capacity
    # Make the staging chunk smaller than the transfer so chunking runs.
    if host.can_use_write_back_jit:
        host.staging_page_capacity = 4
        host.staging_token_capacity = 4 * PAGE
        host.staging_k_buffer = host.staging_k_buffer[: 4 * PAGE]
        host.staging_v_buffer = host.staging_v_buffer[: 4 * PAGE]

    allocated = sum(t.numel() * t.element_size() for t in host.kv_buffer)
    assert allocated == host.size * host.size_per_token, (allocated, host.size, host.size_per_token)
    assert host.size_per_token == mha.NVFP4QSAMHATokenToKVPoolHost.host_bytes_per_token(target, drafts)

    perm = rng.permutation(dev_pages) + 1
    src_pages, dst_pages = perm[:n_pages], perm[n_pages : 2 * n_pages]
    src = torch.tensor(slots_of(src_pages), dtype=torch.int64, device="cuda")
    dst = torch.tensor(slots_of(dst_pages), dtype=torch.int64, device="cuda")
    host_pages = rng.permutation(host.page_num)[:n_pages]
    hidx = torch.tensor(slots_of(host_pages), dtype=torch.int64, device="cpu")

    tracked = {}
    for tag, pool in [("t", target)] + [(f"d{i}", d) for i, d in enumerate(drafts)]:
        for key, t in buffers_of(pool).items():
            tracked[f"{tag}.{key}"] = t
            b = as_bytes(t)
            b.a[...] = rng.integers(0, 256, b.a.shape, dtype=np.uint8)
    expected = {k: as_bytes(t)[src].clone() for k, t in tracked.items()}
    for s in host._segments:
        as_bytes(s.host_k).fill_(0xA5)
        as_bytes(s.host_v).fill_(0xA5)

    # Index placement as the controller does it.
    if io_backend == "kernel":
        backup_host = hidx if host.can_use_write_back_jit else hidx.to("cuda")
        backup_dev = src
    else:
        backup_host, backup_dev = hidx, src.cpu()
    host.backup_from_device_all_layer(target, backup_host, backup_dev, io_backend)

    # White box: host bytes exactly the device rows at the host slots, nothing else.
    hs = hidx.a
    for s in host._segments:
        for dev_list, hb in ((s.device_k, s.host_k), (s.device_v, s.host_v)):
            want = np.full_like(as_bytes(hb).a, 0xA5)
            for layer, dev_buf in enumerate(dev_list):
                rows = as_bytes(dev_buf).a[src.a]
                if s.page_major:
                    want[hs // PAGE, layer, hs % PAGE] = rows
                else:
                    want[hs, layer] = rows
            assert np.array_equal(as_bytes(hb).a, want), f"host layout mismatch in {s.name}"

    # Clobber both page sets, then load into dst.
    for t in tracked.values():
        b = as_bytes(t)
        for sl in (src, dst):
            b.a[sl.a] = rng.integers(0, 256, b.a[sl.a].shape, dtype=np.uint8)
    clobbered = {k: as_bytes(t).clone() for k, t in tracked.items()}
    if io_backend == "kernel":
        load_host, load_dev = hidx.to("cuda"), dst
    else:
        load_host, load_dev = hidx, dst.cpu()
    for layer in range(target.layer_num):
        host.load_to_device_per_layer(target, load_host, load_dev, layer, io_backend)
    for depth, d in enumerate(drafts):
        host.load_to_device_per_layer(
            d, load_host, load_dev, target.layer_num + depth, io_backend, is_draft=True
        )
    bad = []
    for k, t in tracked.items():
        want = clobbered[k].a.copy()
        want[dst.a] = expected[k].a
        if not np.array_equal(as_bytes(t).a, want):
            bad.append(k)
    assert not bad, f"round trip mismatch: {bad}"
    kernels = sorted({c[0] for c in fake_kernels.CALLS})
    return {
        "segments": [[s.name, s.num_layers, s.row_bytes, s.page_major, s.can_use_jit] for s in host._segments],
        "write_back_jit": host.can_use_write_back_jit,
        "staging_capacity_pages": staged_capacity,
        "size_per_token": host.size_per_token,
        "kernels": kernels,
    }


def run_refusals():
    out = {}
    target = fake_pool("nvfp4_qsa", 2, 8)
    for layout in ("layer_first", "page_head"):
        try:
            mha.NVFP4QSAMHATokenToKVPoolHost(target, 2.0, 0, PAGE, layout, pin_memory=False)
            out[layout] = "accepted"
        except NotImplementedError:
            out[layout] = "refused"
    fp8 = fake_pool("fp8", 2, 8)
    out["fp8_class"] = mha.get_mha_host_pool_cls(fp8).__name__
    try:
        mha.NVFP4QSAMHATokenToKVPoolHost(fp8, 2.0, 0, PAGE, "page_first", pin_memory=False)
        out["fp8_pool"] = "accepted"
    except ValueError:
        out["fp8_pool"] = "refused"
    host = mha.NVFP4QSAMHATokenToKVPoolHost(target, 2.0, 0, PAGE, "page_first", pin_memory=False)
    for name, fn in (
        ("get_page_buffer_meta", lambda: host.get_page_buffer_meta(torch.arange(PAGE))),
        ("get_data_page", lambda: host.get_data_page(0)),
        ("get_dummy_flat_data_page", lambda: host.get_dummy_flat_data_page()),
    ):
        try:
            fn()
            out[name] = "accepted"
        except NotImplementedError:
            out[name] = "refused"
    # Empty transfers are no-ops (the sgl_kernel launcher would divide by zero).
    empty = torch.tensor([], dtype=torch.int64, device="cuda")
    host.backup_from_device_all_layer(target, empty, empty, "kernel")
    host.load_to_device_per_layer(target, empty, empty, 0, "kernel")
    out["empty_ok"] = True
    # Production geometry per token: 12 nvfp4 layers + one FP8 draft layer.
    prod = mha.NVFP4QSAMHATokenToKVPoolHost.host_bytes_per_token(
        fake_pool("nvfp4_qsa", 12, 2), (fake_pool("fp8", 1, 2),)
    )
    out["production_bytes_per_token"] = prod
    return out


results = {}
cases = []
for layout, io in (("page_first", "kernel"), ("page_first_direct", "direct")):
    for draft in ("fp8", "nvfp4_qsa", "bf16", None):
        for jit in ((True, False) if io == "kernel" else (True,)):
            cases.append((layout, io, draft, jit))
failed = []
for i, (layout, io, draft, jit) in enumerate(cases):
    name = f"{io}/{layout}/draft={draft}/jit={jit}"
    try:
        results[name] = run_case(layout, io, draft, jit, seed=i)
    except Exception as exc:
        import traceback

        results[name] = {"error": f"{type(exc).__name__}: {exc}", "tb": traceback.format_exc(limit=6)}
        failed.append(name)
try:
    results["refusals"] = run_refusals()
except Exception as exc:
    import traceback

    results["refusals"] = {"error": f"{type(exc).__name__}: {exc}", "tb": traceback.format_exc(limit=6)}
    failed.append("refusals")
print(json.dumps({"failed": failed, "results": results}, indent=1, default=str))
