"""GPU checks for the nvfp4_qsa KV port to Daniel Franzen's SGLang fork (qsakv4).

Run inside his venv, with the qsakv4 patched files installed over his sglang, on the
GPU (RTX PRO 6000 / SM120 or SM100), with no server running:

    python test_qsa_nvfp4_daniel.py               # every check, one JSON line each
    python test_qsa_nvfp4_daniel.py --skip-speed  # without the gather timing

The last line is one JSON summary; the exit status is 1 if any pass/fail check fails
or raises.  Checks:

  reference_vs_flashinfer  our pure-torch NVFP4 dequantizer (the reference for every
                           kernel check) agrees with FlashInfer's (skipped without it).
  kernels_match_reference  both new Triton kernels (_compact_kv_nvfp4: top-k gather,
                           FA-packed and trtllm-strided layouts; _gather_slots_nvfp4:
                           full-context gather) reproduce the reference rows into BF16
                           and FP8 scratch, with -1 padding, out-of-range positions and
                           a non-power-of-two top-k, at global scales 1, 0.01 and 8
                           (the last saturates the FP8 scratch clamp).
  quant_method             nvfp4_qsa registry entry, access rules, no dequant
                           workspace, scale table size, SGLANG_NVFP4_QSA_GLOBAL_SCALE,
                           --kv-cache-dtype mapping (target nvfp4_qsa, draft fp8_e4m3).
  pool_write_read          the real write path (NVFP4QSAKVCacheMethod.create_buffers +
                           quantize_and_store with the device global scale) read back
                           through the kernels.
  graph_kernel_gather      CUDA-graph capture of valid counts + the strided top-k gather
                           (the trtllm decode layout); replays after every input changed
                           in place must match an eager reference.
  backend_*                QwenSparseAttnBackend itself on a stand-in QSA pool: decode
                           and chunked-prefill-with-prefix outputs on the nvfp4_qsa pool
                           must equal the outputs on an unquantized pool holding exactly
                           the rows the kernels unpack (FP8 and BF16 scratch); guards for
                           CPU paths and foreign FP4 recipes; a CUDA-graph capture of
                           forward_decode including the KV write.
  attention_error          (info) decode output error vs a BF16 cache: FP8 cache (what
                           the fork stores today) against nvfp4_qsa.
  nvfp4_error / speed      (info) relative RMS error; gather timing at 19/28/34 lanes.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import traceback
from types import SimpleNamespace

import torch

HEADS, DIM, Q_HEADS = 2, 256, 24  # Qwen3.8-Flash-Next full-attention layers
TOPK = 2051  # indexer budget 2048 plus the 3-column verify / MTP tail
LAYER_IDS = (3, 7)  # absolute ids of two QSA layers (the pool maps them to 0, 1)
# Distinct non-unit global scales per absolute layer id: a read or write that indexed
# the scale table by the pool-local id would pick the wrong (unit) scale.
GLOBAL_SCALES = {3: (0.5, 1.25), 7: (1.75, 0.6)}
DEVICE = "cuda"
FP8 = torch.float8_e4m3fn
BF16 = torch.bfloat16

RESULTS = []


def emit(check, passed=None, **fields):
    record = {"check": check, **fields}
    if passed is not None:
        record["passed"] = bool(passed)
    RESULTS.append(record)
    print(json.dumps(record, sort_keys=True, default=str), flush=True)


def run(name, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except Exception as exc:  # report and keep going; the summary fails
        emit(
            name,
            passed=False,
            error=f"{type(exc).__name__}: {exc}",
            traceback=traceback.format_exc(limit=12),
        )


# ---------------------------------------------------------------------------
# NVFP4 reference (pure torch) and data
# ---------------------------------------------------------------------------

_E2M1 = (0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0) + (
    -0.0, -0.5, -1.0, -1.5, -2.0, -3.0, -4.0, -6.0,
)
_E2M1_BOUNDS = (0.25, 0.75, 1.25, 1.75, 2.5, 3.5, 5.0)


def have_flashinfer_nvfp4() -> bool:
    try:
        from flashinfer import nvfp4_kv_dequantize, nvfp4_kv_quantize  # noqa: F401

        return True
    except Exception:
        return False


FLASHINFER = False  # set in main()


def ref_dequant_f32(packed, scales, global_scale):
    """value = e2m1 * (block_scale * global_scale) in FP32, the kernels' order.

    packed [..., dim // 2] uint8 (element 2i in the low nibble), scales
    [..., dim // 16] FP8 E4M3, global_scale a 1-element FP32 tensor.
    """
    table = torch.tensor(_E2M1, dtype=torch.float32, device=packed.device)
    p = packed.view(torch.uint8).long()
    values = torch.stack((table[p & 15], table[p >> 4]), dim=-1).flatten(-2)
    scale = scales.view(FP8).float() * global_scale.float().reshape(-1)[0]
    return values * scale.repeat_interleave(16, dim=-1)


def to_scratch(x_f32, dtype):
    if dtype == FP8:
        x_f32 = x_f32.clamp(-448.0, 448.0)  # the kernels' FP8 saturation
    return x_f32.to(dtype)


def torch_quantize(x, global_scale):
    """Pure-torch NVFP4 quantizer, used only when FlashInfer is not importable."""
    gs = global_scale.float().reshape(-1)[0]
    xf = x.float()
    blocks = xf.reshape(*xf.shape[:-1], xf.shape[-1] // 16, 16)
    amax = blocks.abs().amax(dim=-1)
    block_scale = (amax / (6.0 * gs)).clamp(max=448.0).to(FP8)
    denom = (block_scale.float() * gs).unsqueeze(-1)
    q = torch.where(denom > 0, blocks / denom.clamp_min(1e-30), torch.zeros_like(blocks))
    bounds = torch.tensor(_E2M1_BOUNDS, device=x.device)
    magnitude = (q.abs().unsqueeze(-1) >= bounds).sum(-1)
    nibbles = (magnitude | ((q < 0).long() << 3)).reshape(xf.shape).to(torch.uint8)
    packed = nibbles[..., 0::2] | (nibbles[..., 1::2] << 4)
    return packed.contiguous(), block_scale.contiguous()


def quantize(x, global_scale):
    """(packed uint8, block scales FP8) via SGLang's NVFP4 quantizer (FlashInfer)."""
    if FLASHINFER:
        from sglang.srt.layers.quantization.kvfp4_tensor import NVFP4KVQuantizeUtil

        packed, scales, _ = NVFP4KVQuantizeUtil.quantize(x.contiguous(), global_scale)
        return packed.view(torch.uint8).contiguous(), scales.view(FP8).contiguous()
    return torch_quantize(x, global_scale)


def make_kv(rows, seed, outlier_channels=4, outlier_scale=20.0, data_scale=1.0):
    g = torch.Generator(device="cpu").manual_seed(seed)
    x = torch.randn(rows, HEADS, DIM, generator=g)
    channels = torch.randperm(DIM, generator=g)[:outlier_channels]
    x[..., channels] *= outlier_scale
    return (x * data_scale).to(BF16).to(DEVICE)


def gs_tensor(value):
    return torch.tensor([value], dtype=torch.float32, device=DEVICE)


def compare(got, want):
    """Mismatch fraction, max relative difference (relative to |want|, floored) and
    the fraction of non-finite values on either side (NaN would hide in the diff)."""
    got, want = got.float(), want.float()
    if not got.numel():
        return {"mismatch_fraction": 0.0, "max_rel_diff": 0.0, "nonfinite_fraction": 0.0}
    nonfinite = ~(torch.isfinite(got) & torch.isfinite(want))
    diff = torch.where(nonfinite, torch.zeros_like(got), (got - want).abs())
    scale = want.abs().clamp_min(1e-6)
    return {
        "mismatch_fraction": float((diff > 0).float().mean()),
        "max_rel_diff": float((diff / scale).max()),
        "nonfinite_fraction": float(nonfinite.float().mean()),
    }


def scratch_ok(stats, dtype):
    if stats["nonfinite_fraction"] != 0.0:
        return False
    if dtype == BF16:
        return stats["mismatch_fraction"] == 0.0
    # FP8: kernel and reference both round the same FP32 value to nearest even
    # after the same clamp (the 0007 GPU run was bit-exact); allow rare ties one
    # FP8 step apart (an FP8 E4M3 step is at most 12.5%).
    return stats["mismatch_fraction"] <= 1e-3 and stats["max_rel_diff"] <= 0.13


def build_decode_case(batch, slots, width, lens, seed, include_last=True):
    """req_to_token rows 1..batch (row 0 is the reserved padding request) and top-k
    rows that follow the indexer's contract: in-range positions first, then a few
    out-of-range positions, then -1 padding."""
    g = torch.Generator(device="cpu").manual_seed(seed)
    lens = torch.as_tensor(lens, dtype=torch.int64)
    assert int(lens.max()) <= width
    req_to_token = torch.zeros(batch + 1, width, dtype=torch.int32)
    for b in range(batch):
        req_to_token[b + 1] = (torch.randperm(slots - 1, generator=g)[:width] + 1).to(
            torch.int32
        )
    indices = torch.full((batch, TOPK), -1, dtype=torch.int32)
    for b in range(batch):
        length = int(lens[b])
        n = min(TOPK, length)
        perm = torch.randperm(length, generator=g)[:n]
        if include_last:  # the newest token first, as decode attends to it
            hit = (perm == length - 1).nonzero().flatten()
            if hit.numel():
                j = int(hit[0])
                perm[0], perm[j] = int(perm[j]), int(perm[0])
            else:
                perm[0] = length - 1
        indices[b, :n] = perm.to(torch.int32)
        tail = min(3, TOPK - n)
        if tail:
            indices[b, n : n + tail] = length + torch.arange(tail, dtype=torch.int32)
    return (
        lens.to(torch.int32).to(DEVICE),
        req_to_token.to(DEVICE),
        indices.to(DEVICE),
    )


def selected_slots(req_rows, req_to_token, indices, lens):
    """Per row, the KV slots the gather must read, in top-k column order."""
    out = []
    for b in range(indices.shape[0]):
        row = indices[b].long()
        length = int(lens[b])
        valid = (row >= 0) & (row < length)
        count = int(valid.sum())
        assert bool(valid[:count].all()), "test case breaks the valid-first contract"
        out.append(req_to_token[int(req_rows[b]), row[:count]].long())
    return out


# ---------------------------------------------------------------------------
# 1. reference vs FlashInfer, 2. kernels vs reference
# ---------------------------------------------------------------------------


def check_reference_vs_flashinfer():
    if not FLASHINFER:
        emit("reference_vs_flashinfer", skipped="flashinfer nvfp4_kv_* not importable")
        return
    from sglang.srt.layers.quantization.kvfp4_tensor import NVFP4KVQuantizeUtil

    x = make_kv(4096, seed=11)
    for value in (1.0, 0.01, 1.75):
        gs = gs_tensor(value)
        packed, scales = quantize(x, gs)
        ours = ref_dequant_f32(packed, scales, gs).to(BF16)
        theirs = NVFP4KVQuantizeUtil.dequantize(packed, scales, gs, dtype=BF16)
        stats = compare(ours, theirs.reshape(ours.shape))
        if value == 1.0:  # every product is exact in FP32: must agree bit for bit
            passed = stats["mismatch_fraction"] == 0.0
        else:  # FP32 product order may differ by one BF16 step on ties
            passed = stats["mismatch_fraction"] <= 1e-3 and stats["max_rel_diff"] <= 0.01
        passed = passed and stats["nonfinite_fraction"] == 0.0
        emit("reference_vs_flashinfer", passed=passed, global_scale=value, **stats)


def check_kernels_match_reference(global_scale, data_scale, seed):
    from sglang.srt.layers.attention.qsa.sparse_attn import (
        qwen_sparse_fa2_cu_seqlens_triton,
        qwen_sparse_gather_slots_nvfp4_triton,
        qwen_sparse_kv_extraction_compact_nvfp4_triton,
    )

    slots, batch, width = 8192, 4, 4096
    gs = gs_tensor(global_scale)
    k = make_kv(slots, seed=seed, data_scale=data_scale)
    v = make_kv(slots, seed=seed + 1, data_scale=data_scale)
    kp, ks = quantize(k, gs)
    vp, vs = quantize(v, gs)
    k_ref, v_ref = ref_dequant_f32(kp, ks, gs), ref_dequant_f32(vp, vs, gs)

    lens, req_to_token, indices = build_decode_case(
        batch, slots, width, lens=[1500, 4000, TOPK, 37], seed=seed + 2
    )
    req_rows = torch.arange(1, batch + 1, dtype=torch.int32, device=DEVICE)
    counts = torch.empty(batch, dtype=torch.int32, device=DEVICE)
    cu = torch.empty(batch + 1, dtype=torch.int32, device=DEVICE)
    qwen_sparse_fa2_cu_seqlens_triton(lens, indices, counts, cu, batch, TOPK)
    want_slots = selected_slots(req_rows, req_to_token, indices, lens)
    want_counts = [int(s.numel()) for s in want_slots]
    counts_ok = counts.tolist() == want_counts
    total = sum(want_counts)
    flat_slots = torch.cat(want_slots)
    page = 64
    stride = -(-TOPK // page) * page
    cu_strided = torch.arange(batch + 1, dtype=torch.int32, device=DEVICE) * stride

    for scratch in (BF16, FP8):
        want_k = to_scratch(k_ref[flat_slots], scratch)
        want_v = to_scratch(v_ref[flat_slots], scratch)
        stats, untouched = {}, True

        # FA layout (cu = prefix sum of valid counts), plus guard rows after it.
        out_k = torch.zeros(total + 7, HEADS, DIM, dtype=scratch, device=DEVICE)
        out_v = torch.zeros_like(out_k)
        qwen_sparse_kv_extraction_compact_nvfp4_triton(
            kp, vp, ks, vs, gs, gs, req_to_token, req_rows, indices, lens, cu,
            out_k, out_v, batch, TOPK,
        )
        s_k, s_v = compare(out_k[:total], want_k), compare(out_v[:total], want_v)
        stats["compact_fa"] = _worst(s_k, s_v)
        untouched &= bool((out_k[total:].float() == 0).all() and (out_v[total:].float() == 0).all())

        # trtllm layout: row b starts at b * stride, rows past its count untouched.
        out_k = torch.zeros(batch * stride, HEADS, DIM, dtype=scratch, device=DEVICE)
        out_v = torch.zeros_like(out_k)
        qwen_sparse_kv_extraction_compact_nvfp4_triton(
            kp, vp, ks, vs, gs, gs, req_to_token, req_rows, indices, lens, cu_strided,
            out_k, out_v, batch, TOPK,
        )
        got_k = torch.cat([out_k[b * stride : b * stride + n] for b, n in enumerate(want_counts)])
        got_v = torch.cat([out_v[b * stride : b * stride + n] for b, n in enumerate(want_counts)])
        stats["compact_strided"] = _worst(compare(got_k, want_k), compare(got_v, want_v))
        for b, n in enumerate(want_counts):
            untouched &= bool((out_k[b * stride + n : (b + 1) * stride].float() == 0).all())

        # Full-context slot gather (chunked prefill), int64 and int32 slot ids.
        for name, ids in (("gather_slots_i64", flat_slots), ("gather_slots_i32", flat_slots.to(torch.int32))):
            out_k = torch.zeros(total + 5, HEADS, DIM, dtype=scratch, device=DEVICE)
            out_v = torch.zeros_like(out_k)
            qwen_sparse_gather_slots_nvfp4_triton(
                kp, vp, ks, vs, gs, gs, ids.contiguous(), out_k, out_v
            )
            stats[name] = _worst(compare(out_k[:total], want_k), compare(out_v[:total], want_v))
            untouched &= bool((out_k[total:].float() == 0).all())

        passed = counts_ok and untouched and all(scratch_ok(s, scratch) for s in stats.values())
        emit(
            "kernels_match_reference",
            passed=passed,
            global_scale=global_scale,
            data_scale=data_scale,
            scratch=str(scratch),
            counts_ok=counts_ok,
            untouched_rows_ok=untouched,
            fp8_clamped_fraction=float((to_scratch(k_ref[flat_slots], FP8).float().abs() >= 448).float().mean()),
            **stats,
        )


def _worst(a, b):
    return {key: max(a[key], b[key]) for key in a}


# ---------------------------------------------------------------------------
# 3. quant method, 4. pool write path
# ---------------------------------------------------------------------------


def new_quant_method(num_layers=len(LAYER_IDS), scales=True):
    from sglang.srt.layers.quantization.fp4_kv_cache_quant_method import (
        get_kv_cache_quant_method,
    )

    qm = get_kv_cache_quant_method("nvfp4_qsa", num_layers=num_layers, device=DEVICE)
    if scales:
        for layer_id, (k_gs, v_gs) in GLOBAL_SCALES.items():
            qm.k_scales_gpu[layer_id] = k_gs
            qm.v_scales_gpu[layer_id] = v_gs
            qm.k_scales_float[layer_id] = k_gs
            qm.v_scales_float[layer_id] = v_gs
    return qm


def check_quant_method():
    from sglang.srt.layers.quantization.fp4_kv_cache_quant_method import (
        KVCacheAttentionAccessKind,
        NVFP4QSAKVCacheMethod,
        resolve_kv_cache_quant,
    )
    from sglang.srt.mem_cache.kv_cache_dtype import configure_kv_cache_dtype

    facts = {}
    qm = new_quant_method(num_layers=12, scales=False)
    facts["class_ok"] = isinstance(qm, NVFP4QSAKVCacheMethod) and qm.name == "nvfp4_qsa"
    facts["resolve_ok"] = resolve_kv_cache_quant("nvfp4_qsa") == "nvfp4_qsa"
    facts["scale_table_size"] = int(qm.k_scales_gpu.numel())
    facts["scale_table_ok"] = qm.k_scales_gpu.numel() >= 256 and qm.v_scales_gpu.numel() >= 256
    facts["no_dequant_workspace"] = (
        not qm.needs_dequant_workspace() and qm.dequant_workspace_dtype() is None
    )
    facts["no_plain_dequant_read"] = not qm.needs_plain_kv_dequant_read()
    facts["storage_uint8"] = qm.kv_storage_dtype() == torch.uint8
    facts["scale_view_fp8"] = qm.scale_buffer_view_dtype() == FP8
    access_ok = True
    for phase in ("prefill", "decode"):
        access = qm.resolve_attention_access(phase, "qsa")
        access_ok &= access is not None and access.kind == KVCacheAttentionAccessKind.NATIVE_FP4
        access_ok &= qm.resolve_attention_access(phase, "flashinfer") is None
    facts["access_rules_ok"] = access_ok

    previous = os.environ.get("SGLANG_NVFP4_QSA_GLOBAL_SCALE")
    try:
        os.environ["SGLANG_NVFP4_QSA_GLOBAL_SCALE"] = "0.75"
        qm.load_scales_from_model(SimpleNamespace(layers=[]))
        facts["override_ok"] = bool(
            (qm.k_scales_gpu == 0.75).all() and (qm.v_scales_gpu == 0.75).all()
        ) and set(qm.k_scales_float) == {0.75}
        os.environ["SGLANG_NVFP4_QSA_GLOBAL_SCALE"] = "-1"
        try:
            qm.load_scales_from_model(SimpleNamespace(layers=[]))
            facts["override_rejects_negative"] = False
        except ValueError:
            facts["override_rejects_negative"] = True
    finally:
        if previous is None:
            os.environ.pop("SGLANG_NVFP4_QSA_GLOBAL_SCALE", None)
        else:
            os.environ["SGLANG_NVFP4_QSA_GLOBAL_SCALE"] = previous

    common = dict(
        model=None,
        model_dtype=BF16,
        is_dflash=False,
        speculative_draft_attention_backend=None,
    )
    target = configure_kv_cache_dtype(
        server_args_kv_cache_dtype="nvfp4_qsa", is_draft_worker=False, **common
    )
    draft = configure_kv_cache_dtype(
        server_args_kv_cache_dtype="nvfp4_qsa",
        is_draft_worker=True,
        speculative_draft_kv_cache_dtype="fp8_e4m3",
        **common,
    )
    facts["target_dtype"] = str(target[1])
    facts["draft_dtype"] = str(draft)
    facts["dtype_mapping_ok"] = (
        target[1] == getattr(torch, "float4_e2m1fn_x2", None)
        and draft == ("fp8_e4m3", FP8)
    )
    passed = all(v for k, v in facts.items() if k.endswith("_ok") or k in (
        "no_dequant_workspace", "no_plain_dequant_read", "storage_uint8",
        "scale_view_fp8", "override_rejects_negative",
    ))
    emit("quant_method", passed=passed, **facts)


def check_pool_write_read():
    from sglang.srt.layers.attention.qsa.sparse_attn import (
        qwen_sparse_gather_slots_nvfp4_triton,
    )

    slots, rows = 4096, 777
    qm = new_quant_method()
    buffers = qm.create_buffers(slots, HEADS, DIM, len(LAYER_IDS), DEVICE)
    facts = {
        "no_dq_buffers": buffers.get("dq_k_buffer") is None and buffers.get("dq_v_buffer") is None,
        "packed_shape_ok": all(
            t.shape == (slots, HEADS, DIM // 2) and t.dtype == torch.uint8
            for t in buffers["k_buffer"] + buffers["v_buffer"]
        ),
        "scale_shape_ok": all(
            t.shape == (slots, HEADS, DIM // 16) and t.dtype == torch.uint8
            for t in buffers["k_scale_buffer"] + buffers["v_scale_buffer"]
        ),
    }
    for local, layer_id in enumerate(LAYER_IDS):
        g = torch.Generator(device="cpu").manual_seed(50 + layer_id)
        loc = (torch.randperm(slots - 1, generator=g)[:rows] + 1).to(DEVICE)
        k = make_kv(rows, seed=60 + layer_id)
        v = make_kv(rows, seed=70 + layer_id)
        k_gs = qm.k_scales_gpu[layer_id : layer_id + 1]
        v_gs = qm.v_scales_gpu[layer_id : layer_id + 1]
        kb, vb = buffers["k_buffer"][local], buffers["v_buffer"][local]
        ksb, vsb = buffers["k_scale_buffer"][local], buffers["v_scale_buffer"][local]
        # Exactly what MHATokenToKVPool._set_quantized_kv_buffer calls.
        qm.quantize_and_store(kb, vb, ksb, vsb, loc, k, v, k_gs, v_gs)
        kp_direct, ks_direct = quantize(k, k_gs)
        vp_direct, vs_direct = quantize(v, v_gs)
        stored_ok = bool(
            torch.equal(kb[loc], kp_direct)
            and torch.equal(ksb[loc], ks_direct.view(torch.uint8))
            and torch.equal(vb[loc], vp_direct)
            and torch.equal(vsb[loc], vs_direct.view(torch.uint8))
        )
        others = torch.ones(slots, dtype=torch.bool, device=DEVICE)
        others[loc] = False
        untouched_ok = bool((kb[others] == 0).all() and (ksb[others] == 0).all())
        out_k = torch.empty(rows, HEADS, DIM, dtype=BF16, device=DEVICE)
        out_v = torch.empty_like(out_k)
        qwen_sparse_gather_slots_nvfp4_triton(
            kb, vb, ksb.view(FP8), vsb.view(FP8), k_gs, v_gs, loc, out_k, out_v
        )
        exact = _worst(
            compare(out_k, ref_dequant_f32(kb[loc], ksb[loc], k_gs).to(BF16)),
            compare(out_v, ref_dequant_f32(vb[loc], vsb[loc], v_gs).to(BF16)),
        )
        rel_rms_k = _rel_rms(out_k, k)
        rel_rms_v = _rel_rms(out_v, v)
        layer_ok = stored_ok and untouched_ok and scratch_ok(exact, BF16)
        layer_ok &= rel_rms_k < 0.15 and rel_rms_v < 0.15
        emit(
            "pool_write_read",
            passed=layer_ok and all(facts.values()),
            layer_id=layer_id,
            global_scales=[float(k_gs), float(v_gs)],
            stored_ok=stored_ok,
            untouched_ok=untouched_ok,
            read_back_mismatch_fraction=exact["mismatch_fraction"],
            rel_rms_k=rel_rms_k,
            rel_rms_v=rel_rms_v,
            **facts,
        )


def _rel_rms(a, b):
    a, b = a.float(), b.float()
    return float((a - b).pow(2).mean().sqrt() / b.pow(2).mean().sqrt().clamp_min(1e-12))


# ---------------------------------------------------------------------------
# 5. CUDA graph: kernel-level decode gather
# ---------------------------------------------------------------------------


def check_graph_kernel_gather():
    from sglang.srt.layers.attention.qsa.sparse_attn import (
        qwen_sparse_kv_extraction_compact_nvfp4_triton,
        qwen_sparse_valid_counts_triton,
    )

    slots, batch, width = 16384, 6, 6000
    page = 64
    stride = -(-TOPK // page) * page
    gs_k, gs_v = gs_tensor(1.0), gs_tensor(1.0)
    kp = torch.zeros(slots, HEADS, DIM // 2, dtype=torch.uint8, device=DEVICE)
    vp = torch.zeros_like(kp)
    ks = torch.zeros(slots, HEADS, DIM // 16, dtype=FP8, device=DEVICE)
    vs = torch.zeros_like(ks)
    seq_lens = torch.ones(batch, dtype=torch.int32, device=DEVICE)
    req_to_token = torch.zeros(batch + 1, width, dtype=torch.int32, device=DEVICE)
    req_rows = torch.arange(1, batch + 1, dtype=torch.int32, device=DEVICE)
    indices = torch.full((batch, TOPK), -1, dtype=torch.int32, device=DEVICE)
    counts = torch.zeros(batch, dtype=torch.int32, device=DEVICE)
    cu_strided = torch.arange(batch + 1, dtype=torch.int32, device=DEVICE) * stride
    out_k = torch.zeros(batch * stride, HEADS, DIM, dtype=FP8, device=DEVICE)
    out_v = torch.zeros_like(out_k)

    def fill(trial):
        lens = [37, TOPK, 5999, 900, 2048, 4000] if trial % 2 else [4000, 1, 2500, 64, 5000, 3]
        new_lens, new_rtt, new_idx = build_decode_case(batch, slots, width, lens, seed=200 + trial)
        seq_lens.copy_(new_lens)
        req_to_token.copy_(new_rtt)
        indices.copy_(new_idx)
        for buffer, (packed, scales) in (((kp, ks), quantize(make_kv(slots, 300 + trial), gs_k)),
                                         ((vp, vs), quantize(make_kv(slots, 400 + trial), gs_v))):
            buffer[0].copy_(packed)
            buffer[1].copy_(scales)
        gs_k.fill_(0.5 + trial)  # device scalars change between replays too
        gs_v.fill_(1.0 / (1 + trial))

    def step():
        qwen_sparse_valid_counts_triton(seq_lens, indices, counts, batch, TOPK)
        qwen_sparse_kv_extraction_compact_nvfp4_triton(
            kp, vp, ks, vs, gs_k, gs_v, req_to_token, req_rows, indices, seq_lens,
            cu_strided, out_k, out_v, batch, TOPK,
        )

    fill(0)
    side = torch.cuda.Stream()
    side.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(side):
        for _ in range(2):
            step()
    torch.cuda.current_stream().wait_stream(side)
    torch.cuda.synchronize()
    graph = torch.cuda.CUDAGraph()
    with torch.cuda.graph(graph):
        step()
    torch.cuda.synchronize()

    for trial in (1, 2, 3):
        fill(trial)
        out_k.zero_()
        out_v.zero_()
        graph.replay()
        torch.cuda.synchronize()
        want_slots = selected_slots(req_rows, req_to_token, indices, seq_lens)
        want_counts = [int(s.numel()) for s in want_slots]
        flat = torch.cat(want_slots)
        want_k = to_scratch(ref_dequant_f32(kp[flat], ks[flat], gs_k), FP8)
        want_v = to_scratch(ref_dequant_f32(vp[flat], vs[flat], gs_v), FP8)
        got_k = torch.cat([out_k[b * stride : b * stride + n] for b, n in enumerate(want_counts)])
        got_v = torch.cat([out_v[b * stride : b * stride + n] for b, n in enumerate(want_counts)])
        stats = _worst(compare(got_k, want_k), compare(got_v, want_v))
        counts_ok = counts.tolist() == want_counts
        ok = counts_ok and scratch_ok(stats, FP8)
        emit("graph_kernel_gather", passed=ok, trial=trial, counts=want_counts, counts_ok=counts_ok, **stats)


# ---------------------------------------------------------------------------
# 6. QwenSparseAttnBackend on a stand-in QSA pool
# ---------------------------------------------------------------------------


class StandInQSAPool:
    """The QSATokenToKVPool calls QwenSparseAttnBackend makes, over real buffers.

    nvfp4_qsa: buffers from NVFP4QSAKVCacheMethod.create_buffers; writes follow
    HybridLinearKVPool.set_kv_buffer (float scale defaults) and
    MHATokenToKVPool._quantized_scales (None -> per-layer device scales indexed by
    the ABSOLUTE layer id); raw reads follow get_raw_kv_buffer (scales viewed as
    FP8 E4M3).  Unquantized: one [slots, heads, dim] buffer per layer.
    """

    def __init__(self, slots, quant_method=None, dtype=FP8):
        self.layer_map = {layer_id: i for i, layer_id in enumerate(LAYER_IDS)}
        self.quant_method = quant_method
        self.full_kv_pool = SimpleNamespace(
            is_quantized_kv_cache=quant_method is not None,
            quant_method=quant_method,
        )
        n = len(LAYER_IDS)
        if quant_method is not None:
            buffers = quant_method.create_buffers(slots, HEADS, DIM, n, DEVICE)
            self.k_buffer, self.v_buffer = buffers["k_buffer"], buffers["v_buffer"]
            self.k_scale_buffer = buffers["k_scale_buffer"]
            self.v_scale_buffer = buffers["v_scale_buffer"]
        else:
            self.k_buffer = [
                torch.zeros(slots, HEADS, DIM, dtype=dtype, device=DEVICE) for _ in range(n)
            ]
            self.v_buffer = [torch.zeros_like(t) for t in self.k_buffer]

    def _local(self, layer_id):
        return self.layer_map[layer_id]

    def get_key_buffer(self, layer_id):
        assert self.quant_method is None, "packed FP4 pool read through get_key_buffer"
        return self.k_buffer[self._local(layer_id)]

    def get_value_buffer(self, layer_id):
        assert self.quant_method is None, "packed FP4 pool read through get_value_buffer"
        return self.v_buffer[self._local(layer_id)]

    def get_raw_kv_buffer(self, layer_id):
        i = self._local(layer_id)
        view = self.quant_method.scale_buffer_view_dtype()
        return (
            self.k_buffer[i],
            self.v_buffer[i],
            self.k_scale_buffer[i].view(view),
            self.v_scale_buffer[i].view(view),
        )

    def set_kv_buffer(self, layer, loc, cache_k, cache_v, k_scale=1.0, v_scale=1.0):
        i = self._local(layer.layer_id)
        if self.quant_method is None:
            self.k_buffer[i][loc] = cache_k.to(self.k_buffer[i].dtype)
            self.v_buffer[i][loc] = cache_v.to(self.v_buffer[i].dtype)
            return
        if k_scale is None:
            k_scale = self.quant_method.k_scales_gpu[layer.layer_id : layer.layer_id + 1]
            v_scale = self.quant_method.v_scales_gpu[layer.layer_id : layer.layer_id + 1]
        self.quant_method.quantize_and_store(
            self.k_buffer[i], self.v_buffer[i], self.k_scale_buffer[i],
            self.v_scale_buffer[i], loc, cache_k, cache_v, k_scale, v_scale,
        )


def unpacked_pool(fp4_pool, slots, dtype):
    """An unquantized stand-in pool holding exactly the rows the kernels unpack."""
    from sglang.srt.layers.attention.qsa.sparse_attn import (
        qwen_sparse_gather_slots_nvfp4_triton,
    )

    ref = StandInQSAPool(slots, dtype=dtype)
    all_slots = torch.arange(slots, dtype=torch.int64, device=DEVICE)
    for layer_id in LAYER_IDS:
        i = fp4_pool._local(layer_id)
        kp, vp, ks, vs = fp4_pool.get_raw_kv_buffer(layer_id)
        qm = fp4_pool.quant_method
        qwen_sparse_gather_slots_nvfp4_triton(
            kp, vp, ks, vs,
            qm.k_scales_gpu[layer_id : layer_id + 1],
            qm.v_scales_gpu[layer_id : layer_id + 1],
            all_slots, ref.k_buffer[i], ref.v_buffer[i],
        )
    return ref


def make_backend(pool, req_to_token):
    from sglang.srt.layers.attention.qwen_sparse_attn_backend import (
        QwenSparseAttnBackend,
    )

    backend = QwenSparseAttnBackend(None)
    backend.token_to_kv_pool = pool
    backend.req_to_token_pool = SimpleNamespace(req_to_token=req_to_token)
    backend.req_to_token = req_to_token
    backend.device = torch.device(DEVICE)
    return backend


def decode_metadata(seq_lens, req_rows, graph=None):
    from sglang.srt.layers.attention.qwen_sparse_attn_backend import (
        QwenSparseAttnMetadata,
    )

    batch = seq_lens.numel()
    fields = dict(
        sequence_lengths=seq_lens,
        token_to_batch_idx=torch.arange(batch, dtype=torch.int32, device=DEVICE),
        token_slot_table=torch.zeros((batch, 1), dtype=torch.int32, device=DEVICE),
        indexer_metadata=None,  # not read by the attention paths under test
        row_req_pool_indices=req_rows,
    )
    if graph is not None:
        fields.update(
            is_cuda_graph=True,
            fa2_valid_counts=graph["valid_counts"],
            fa2_cu_seqlens_k=graph["cu_k"],
            fa2_cu_seqlens_q=graph["cu_q"],
        )
    return QwenSparseAttnMetadata(**fields)


def layer_of(layer_id):
    return SimpleNamespace(
        layer_id=layer_id,
        tp_q_head_num=Q_HEADS,
        tp_k_head_num=HEADS,
        tp_v_head_num=HEADS,
        head_dim=DIM,
        scaling=DIM ** -0.5,
    )


def fill_pool(pool, backend, slots, seed):
    """Write random K/V into every slot of every layer through backend._save_kv."""
    loc = torch.arange(slots, dtype=torch.int64, device=DEVICE)
    for layer_id in LAYER_IDS:
        k = make_kv(slots, seed=seed + layer_id)
        v = make_kv(slots, seed=seed + 100 + layer_id)
        backend._save_kv(layer_of(layer_id), loc, k, v)


def set_scratch(value):
    import sglang.srt.layers.attention.qwen_sparse_attn_backend as qsa_backend

    if value is None:
        os.environ.pop("SGLANG_NVFP4_QSA_SCRATCH", None)
    else:
        os.environ["SGLANG_NVFP4_QSA_SCRATCH"] = value
    qsa_backend._nvfp4_qsa_scratch_dtype.cache_clear()
    return qsa_backend._nvfp4_qsa_scratch_dtype()


def output_stats(got, want):
    got, want = got.float(), want.float()
    diff = (got - want).abs()
    return {
        "bit_exact": bool(torch.equal(got, want)),
        "max_abs_diff": float(diff.max()),
        "rel_max_diff": float(diff.max() / want.abs().max().clamp_min(1e-12)),
        "finite": bool(torch.isfinite(got).all()),
    }


def outputs_ok(stats):
    # Identical bytes reach identical kernels; allow only reduction-order noise.
    return stats["finite"] and stats["rel_max_diff"] <= 1e-2


def check_backend_decode(scratch_env):
    from sglang.srt.model_executor.forward_batch_info import ForwardMode

    scratch = set_scratch(scratch_env)
    slots, batch, width = 12288, 5, 6000
    qm = new_quant_method()
    lens, req_to_token, indices = build_decode_case(
        batch, slots, width, lens=[37, TOPK, 5999, 900, 4000], seed=17
    )
    pool4 = StandInQSAPool(slots, quant_method=qm)
    backend4 = make_backend(pool4, req_to_token)
    fill_pool(pool4, backend4, slots, seed=1000)
    ref_pool = unpacked_pool(pool4, slots, scratch)
    backend_ref = make_backend(ref_pool, req_to_token)
    req_rows = torch.arange(1, batch + 1, dtype=torch.int32, device=DEVICE)
    g = torch.Generator(device="cpu").manual_seed(23)
    q = torch.randn(batch, Q_HEADS * DIM, generator=g).to(BF16).to(DEVICE)
    fb = SimpleNamespace(
        forward_mode=ForwardMode.DECODE,
        out_cache_loc=None,
        req_pool_indices=req_rows.long(),
    )
    for layer_id in LAYER_IDS:
        outs = []
        for backend in (backend4, backend_ref):
            backend.forward_metadata = decode_metadata(lens, req_rows)
            outs.append(
                backend.forward_decode(
                    q, None, None, layer_of(layer_id), fb,
                    save_kv_cache=False, topk_indices=indices,
                )
            )
        stats = output_stats(outs[0], outs[1])
        emit("backend_decode", passed=outputs_ok(stats), scratch=str(scratch), layer_id=layer_id, **stats)


def check_backend_extend_prefix(scratch_env):
    from sglang.srt.model_executor.forward_batch_info import ForwardMode

    scratch = set_scratch(scratch_env)
    slots, width = 12288, 5000
    prefix_lens, extend_lens = [1500, 3100, 64], [37, 300, 1]
    seq_lens = [p + e for p, e in zip(prefix_lens, extend_lens)]
    batch = len(seq_lens)
    qm = new_quant_method()
    _, req_to_token, _ = build_decode_case(batch, slots, width, lens=seq_lens, seed=31)
    pool4 = StandInQSAPool(slots, quant_method=qm)
    backend4 = make_backend(pool4, req_to_token)
    fill_pool(pool4, backend4, slots, seed=2000)
    backend_ref = make_backend(unpacked_pool(pool4, slots, scratch), req_to_token)

    # One top-k row per query token, valid-first: query at position p sees p + 1.
    g = torch.Generator(device="cpu").manual_seed(37)
    rows = []
    for p0, e in zip(prefix_lens, extend_lens):
        for j in range(e):
            visible = p0 + j + 1
            n = min(TOPK, visible)
            row = torch.full((TOPK,), -1, dtype=torch.int32)
            row[:n] = torch.randperm(visible, generator=g)[:n].to(torch.int32)
            rows.append(row)
    indices = torch.stack(rows).to(DEVICE)
    total_q = indices.shape[0]
    q = torch.randn(total_q, Q_HEADS * DIM, generator=g).to(BF16).to(DEVICE)
    fb = SimpleNamespace(
        forward_mode=ForwardMode.EXTEND,
        extend_seq_lens_cpu=extend_lens,
        seq_lens_cpu=seq_lens,
        extend_seq_lens=torch.tensor(extend_lens, dtype=torch.int32, device=DEVICE),
        req_pool_indices=torch.arange(1, batch + 1, dtype=torch.int64, device=DEVICE),
        out_cache_loc=None,
    )
    for layer_id in LAYER_IDS:
        outs = [
            backend.forward_extend(
                q, None, None, layer_of(layer_id), fb,
                save_kv_cache=False, topk_indices=indices,
            )
            for backend in (backend4, backend_ref)
        ]
        stats = output_stats(outs[0], outs[1])
        emit(
            "backend_extend_prefix",
            passed=outputs_ok(stats),
            scratch=str(scratch),
            layer_id=layer_id,
            query_rows=total_q,
            **stats,
        )


def check_backend_guards():
    from sglang.srt.layers.quantization.fp4_kv_cache_quant_method import (
        NVFP4KVCacheMethod,
    )
    from sglang.srt.model_executor.forward_batch_info import ForwardMode

    set_scratch(None)
    slots = 256
    req_to_token = torch.zeros(2, 64, dtype=torch.int32, device=DEVICE)
    facts = {}

    unquantized = make_backend(StandInQSAPool(slots), req_to_token)
    facts["unquantized_takes_old_path"] = unquantized._nvfp4_kv(LAYER_IDS[0]) is None

    pool4 = StandInQSAPool(slots, quant_method=new_quant_method())
    backend4 = make_backend(pool4, req_to_token)
    raw = backend4._nvfp4_kv(7)
    facts["global_scale_absolute_id"] = math.isclose(
        float(raw[4]), GLOBAL_SCALES[7][0], rel_tol=1e-6
    ) and math.isclose(float(raw[5]), GLOBAL_SCALES[7][1], rel_tol=1e-6)
    try:
        backend4._require_unquantized_kv("test path")
        facts["cpu_paths_refuse_fp4"] = False
    except NotImplementedError:
        facts["cpu_paths_refuse_fp4"] = True
    try:  # a CPU query on an FP4 pool must raise, not read packed bytes
        backend4.forward_metadata = None
        backend4.forward_decode(
            torch.zeros(1, Q_HEADS * DIM, dtype=BF16),
            None, None, layer_of(7),
            SimpleNamespace(forward_mode=ForwardMode.DECODE, out_cache_loc=None,
                            req_pool_indices=torch.ones(1, dtype=torch.int64)),
            save_kv_cache=False,
            topk_indices=torch.zeros(1, TOPK, dtype=torch.int32),
        )
        facts["cpu_decode_refuses_fp4"] = False
    except NotImplementedError:
        facts["cpu_decode_refuses_fp4"] = True

    foreign = StandInQSAPool(slots, quant_method=NVFP4KVCacheMethod(len(LAYER_IDS), DEVICE))
    try:
        make_backend(foreign, req_to_token)._nvfp4_kv(7)
        facts["foreign_fp4_recipe_refused"] = False
    except NotImplementedError:
        facts["foreign_fp4_recipe_refused"] = True
    emit("backend_guards", passed=all(facts.values()), **facts)


def check_backend_decode_cuda_graph():
    """Capture forward_decode (KV write + gather + attention) on the nvfp4_qsa pool,
    then replay with every input changed in place."""
    from sglang.srt.model_executor.forward_batch_info import ForwardMode

    scratch = set_scratch(None)
    slots, batch, width = 16384, 6, 6000
    layer_id = 7
    layer = layer_of(layer_id)
    qm = new_quant_method()
    pool4 = StandInQSAPool(slots, quant_method=qm)
    req_to_token = torch.zeros(batch + 1, width, dtype=torch.int32, device=DEVICE)
    backend4 = make_backend(pool4, req_to_token)
    fill_pool(pool4, backend4, slots, seed=3000)
    backend4._cuda_graph_max_tokens = batch

    seq_lens = torch.ones(batch, dtype=torch.int32, device=DEVICE)
    req_rows = torch.arange(1, batch + 1, dtype=torch.int32, device=DEVICE)
    indices = torch.full((batch, TOPK), -1, dtype=torch.int32, device=DEVICE)
    q = torch.zeros(batch, Q_HEADS * DIM, dtype=BF16, device=DEVICE)
    k_new = torch.zeros(batch, HEADS, DIM, dtype=BF16, device=DEVICE)
    v_new = torch.zeros_like(k_new)
    loc = torch.zeros(batch, dtype=torch.int64, device=DEVICE)
    graph_buffers = {
        "valid_counts": torch.zeros(batch, dtype=torch.int32, device=DEVICE),
        "cu_k": torch.zeros(batch + 1, dtype=torch.int32, device=DEVICE),
        "cu_q": torch.arange(batch + 1, dtype=torch.int32, device=DEVICE),
    }
    backend4.forward_metadata = decode_metadata(seq_lens, req_rows, graph=graph_buffers)
    fb = SimpleNamespace(
        forward_mode=ForwardMode.DECODE,
        out_cache_loc=loc,
        req_pool_indices=req_rows.long(),
    )

    def fill(trial):
        lens = [37, TOPK, 5999, 900, 2048, 4000] if trial % 2 else [4000, 2, 2500, 64, 5000, 3]
        new_lens, new_rtt, new_idx = build_decode_case(batch, slots, width, lens, seed=500 + trial)
        # The new token of row b sits at position len_b - 1 (selected first) in a
        # distinct slot per row, so the step's writes never collide.
        g = torch.Generator(device="cpu").manual_seed(600 + trial)
        new_loc = (torch.randperm(slots - 1, generator=g)[:batch] + 1).to(DEVICE)
        rows = torch.arange(1, batch + 1, device=DEVICE)
        new_rtt[rows, new_lens.long() - 1] = new_loc.to(torch.int32)
        seq_lens.copy_(new_lens)
        req_to_token.copy_(new_rtt)
        indices.copy_(new_idx)
        loc.copy_(new_loc)
        q.copy_(torch.randn(batch, Q_HEADS * DIM, generator=g).to(BF16))
        k_new.copy_(make_kv(batch, seed=700 + trial))
        v_new.copy_(make_kv(batch, seed=800 + trial))

    def step():
        return backend4.forward_decode(
            q, k_new, v_new, layer, fb, save_kv_cache=True, topk_indices=indices
        )

    fill(0)
    side = torch.cuda.Stream()
    side.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(side):
        for _ in range(2):
            step()
    torch.cuda.current_stream().wait_stream(side)
    torch.cuda.synchronize()
    graph = torch.cuda.CUDAGraph()
    with torch.cuda.graph(graph):
        out_static = step()
    torch.cuda.synchronize()

    for trial in (1, 2, 3):
        fill(trial)
        graph.replay()
        torch.cuda.synchronize()
        # The replay wrote this step's K/V with the layer's device global scale.
        k_gs = qm.k_scales_gpu[layer_id : layer_id + 1]
        v_gs = qm.v_scales_gpu[layer_id : layer_id + 1]
        kp, vp, ks, vs = pool4.get_raw_kv_buffer(layer_id)
        want_kp, want_ks = quantize(k_new, k_gs)
        want_vp, want_vs = quantize(v_new, v_gs)
        write_ok = bool(
            torch.equal(kp[loc], want_kp) and torch.equal(ks[loc].view(torch.uint8), want_ks.view(torch.uint8))
            and torch.equal(vp[loc], want_vp) and torch.equal(vs[loc].view(torch.uint8), want_vs.view(torch.uint8))
        )
        # Eager reference on an unquantized pool holding the unpacked rows.
        backend_ref = make_backend(unpacked_pool(pool4, slots, scratch), req_to_token)
        backend_ref.forward_metadata = decode_metadata(seq_lens.clone(), req_rows.clone())
        out_ref = backend_ref.forward_decode(
            q, None, None, layer,
            SimpleNamespace(forward_mode=ForwardMode.DECODE, out_cache_loc=None,
                            req_pool_indices=req_rows.long()),
            save_kv_cache=False, topk_indices=indices,
        )
        stats = output_stats(out_static, out_ref)
        emit(
            "backend_decode_cuda_graph",
            passed=write_ok and outputs_ok(stats),
            trial=trial,
            scratch=str(scratch),
            kv_write_ok=write_ok,
            **stats,
        )


def check_attention_error():
    """Informational: decode output vs a BF16 cache, FP8 cache against nvfp4_qsa."""
    from sglang.srt.model_executor.forward_batch_info import ForwardMode

    scratch = set_scratch(None)
    slots, batch, width = 12288, 5, 6000
    lens, req_to_token, indices = build_decode_case(
        batch, slots, width, lens=[2000, TOPK, 5999, 900, 4000], seed=41
    )
    req_rows = torch.arange(1, batch + 1, dtype=torch.int32, device=DEVICE)
    pools = {
        "bf16": StandInQSAPool(slots, dtype=BF16),
        "fp8_e4m3": StandInQSAPool(slots, dtype=FP8),
        "nvfp4_qsa": StandInQSAPool(slots, quant_method=new_quant_method()),
    }
    backends = {name: make_backend(pool, req_to_token) for name, pool in pools.items()}
    for backend in backends.values():
        fill_pool(backend.token_to_kv_pool, backend, slots, seed=4000)  # same source K/V
    g = torch.Generator(device="cpu").manual_seed(43)
    q = torch.randn(batch, Q_HEADS * DIM, generator=g).to(BF16).to(DEVICE)
    fb = SimpleNamespace(forward_mode=ForwardMode.DECODE, out_cache_loc=None,
                         req_pool_indices=req_rows.long())
    for layer_id in LAYER_IDS:
        outs = {}
        for name, backend in backends.items():
            backend.forward_metadata = decode_metadata(lens, req_rows)
            outs[name] = backend.forward_decode(
                q, None, None, layer_of(layer_id), fb,
                save_kv_cache=False, topk_indices=indices,
            ).float()
        emit(
            "attention_error",
            layer_id=layer_id,
            scratch=str(scratch),
            rel_rms_fp8_cache=_rel_rms(outs["fp8_e4m3"], outs["bf16"]),
            rel_rms_nvfp4_qsa=_rel_rms(outs["nvfp4_qsa"], outs["bf16"]),
        )


# ---------------------------------------------------------------------------
# 7. error and speed (informational)
# ---------------------------------------------------------------------------


def check_error():
    x = make_kv(65536, seed=3)
    for value in (1.0, float(x.float().abs().max()) / (6.0 * 448.0)):
        gs = gs_tensor(value)
        packed, scales = quantize(x, gs)
        emit("nvfp4_error", global_scale=value, rel_rms=_rel_rms(ref_dequant_f32(packed, scales, gs), x))
    emit("fp8_e4m3_error", rel_rms=_rel_rms(x.to(FP8).to(BF16), x))


def time_ms(fn, iters=50):
    for _ in range(5):
        fn()
    torch.cuda.synchronize()
    start = time.perf_counter()
    for _ in range(iters):
        fn()
    torch.cuda.synchronize()
    return (time.perf_counter() - start) * 1000.0 / iters


def check_speed():
    from sglang.srt.layers.attention.qsa.sparse_attn import (
        qwen_sparse_kv_extraction_compact_nvfp4_triton,
        qwen_sparse_kv_extraction_compact_triton,
    )

    slots, context = 1 << 20, 100_000
    fp8_k = torch.zeros(slots, HEADS, DIM, dtype=FP8, device=DEVICE)
    fp8_v = torch.zeros_like(fp8_k)
    packed = torch.zeros(slots, HEADS, DIM // 2, dtype=torch.uint8, device=DEVICE)
    scales = torch.ones(slots, HEADS, DIM // 16, dtype=FP8, device=DEVICE)
    gs = gs_tensor(1.0)
    for lanes in (19, 28, 34):
        rows = lanes * 4  # target verify: 4 tokens per lane
        seq_lens = torch.full((rows,), context, dtype=torch.int32, device=DEVICE)
        req_to_token = torch.randint(0, slots, (rows, context), dtype=torch.int32, device=DEVICE)
        req_indices = torch.arange(rows, dtype=torch.int32, device=DEVICE)
        indices = torch.randint(0, context, (rows, TOPK), dtype=torch.int32, device=DEVICE)
        cu = torch.arange(rows + 1, dtype=torch.int32, device=DEVICE) * TOPK
        out_k = torch.empty(rows * TOPK, HEADS, DIM, dtype=FP8, device=DEVICE)
        out_v = torch.empty_like(out_k)
        fp8_ms = time_ms(lambda: qwen_sparse_kv_extraction_compact_triton(
            fp8_k, fp8_v, req_to_token, req_indices, indices, seq_lens, cu, out_k, out_v, rows, TOPK))
        nvfp4_ms = time_ms(lambda: qwen_sparse_kv_extraction_compact_nvfp4_triton(
            packed, packed, scales, scales, gs, gs, req_to_token, req_indices, indices, seq_lens,
            cu, out_k, out_v, rows, TOPK))
        emit("gather_speed_per_layer", lanes=lanes, rows=rows, fp8_ms=round(fp8_ms, 4),
             nvfp4_ms=round(nvfp4_ms, 4), decode_step_ms_12_layers_nvfp4=round(12 * nvfp4_ms, 3))
        del req_to_token, indices, out_k, out_v
    del fp8_k, fp8_v, packed, scales
    torch.cuda.empty_cache()


# ---------------------------------------------------------------------------


def main():
    global FLASHINFER
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--skip-speed", action="store_true")
    args = parser.parse_args()

    if not torch.cuda.is_available():
        print(json.dumps({"summary": "qsa_nvfp4_daniel", "passed": False, "error": "no CUDA device"}))
        return 1
    FLASHINFER = have_flashinfer_nvfp4()
    capability = list(torch.cuda.get_device_capability(0))
    try:
        import triton

        triton_version = triton.__version__
    except Exception:
        triton_version = None
    emit(
        "device",
        name=torch.cuda.get_device_name(0),
        capability=capability,
        torch=torch.__version__,
        triton=triton_version,
        flashinfer_nvfp4=FLASHINFER,
        note=None if capability[0] in (10, 12) else "nvfp4_qsa is meant for SM100/SM120",
    )
    previous_scratch = os.environ.get("SGLANG_NVFP4_QSA_SCRATCH")

    run("reference_vs_flashinfer", check_reference_vs_flashinfer)
    for global_scale, data_scale, seed in ((1.0, 1.0, 1), (0.01, 1.0, 5), (8.0, 50.0, 9)):
        run("kernels_match_reference", check_kernels_match_reference, global_scale, data_scale, seed)
    run("quant_method", check_quant_method)
    # Eager checks first; the CUDA-graph captures run after them so a failed
    # capture cannot take the eager results down with it.
    if FLASHINFER:
        run("pool_write_read", check_pool_write_read)
        for scratch_env in ("fp8", "bf16"):
            run("backend_decode", check_backend_decode, scratch_env)
            run("backend_extend_prefix", check_backend_extend_prefix, scratch_env)
        run("backend_guards", check_backend_guards)
        run("attention_error", check_attention_error)
    else:
        emit("pool_write_read", passed=False,
             error="flashinfer.nvfp4_kv_quantize missing: the nvfp4_qsa write path needs it")
    run("graph_kernel_gather", check_graph_kernel_gather)
    if FLASHINFER:
        run("backend_decode_cuda_graph", check_backend_decode_cuda_graph)
    if previous_scratch is None:
        os.environ.pop("SGLANG_NVFP4_QSA_SCRATCH", None)
    else:
        os.environ["SGLANG_NVFP4_QSA_SCRATCH"] = previous_scratch
    run("nvfp4_error", check_error)
    if not args.skip_speed:
        run("gather_speed", check_speed)

    failed = sorted({r["check"] for r in RESULTS if r.get("passed") is False})
    checked = sorted({r["check"] for r in RESULTS if "passed" in r})
    skipped = sorted({r["check"] for r in RESULTS if "skipped" in r})
    summary = {
        "summary": "qsa_nvfp4_daniel",
        "passed": not failed and bool(checked),
        "failed": failed,
        "skipped": skipped,
        "checks": len([r for r in RESULTS if "passed" in r]),
        "device": torch.cuda.get_device_name(0),
        "capability": capability,
        "flashinfer_nvfp4": FLASHINFER,
    }
    print(json.dumps(summary, sort_keys=True), flush=True)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
