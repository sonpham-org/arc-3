"""GPU checks for kvshrink/draftkv4 (exact nvfp4_qsa KV budget + 4-bit MTP draft KV), 3-Oct-2026.

Run in Daniel Franzen's venv on the GPU (RTX PRO 6000 / SM120) with qsaring + qsakv4 + this
set installed and no server running (make_bench_notebook.py --pre-script; ship qsakv4's
test_qsa_nvfp4_daniel.py next to it with --pre-file, the backend checks reuse it):

    python test_kvshrink.py

One JSON line per check, then one summary line; exit status 1 on any failure. Checks:

  server_args        --speculative-draft-kv-cache-dtype accepts nvfp4_qsa; it is refused
                     without --kv-cache-dtype nvfp4_qsa; FP8 target + FP8 draft untouched.
  dtype_mapping      a draft worker given nvfp4_qsa resolves to the FP4 pool dtype and the
                     nvfp4_qsa quant method (no dequant workspace, scale table >= 256 slots);
                     fp8_e4m3 still resolves to FP8.
  pool_bytes         the REAL QSATokenToKVPool (target: 12 QSA layers; draft: 1 layer at
                     layer id 0), built as the KV cache configurator builds it, at two sizes:
                     marginal device bytes per token for nvfp4_qsa / fp8_e4m3 / bf16.
  budget             the patched DefaultPoolConfigurator (Qwen3.8-Flash-Next geometry, MTP
                     draft of 1 layer) prices exactly what pool_bytes measured, target +
                     draft, for draft fp8_e4m3 / nvfp4_qsa / inherited / bf16; with
                     SGLANG_QSA_EXACT_KV_BUDGET=0 it gives the old 9,429 B; FP8 pools keep
                     the generic 14,143 B.
  draft_pool_rw      the draft-shaped nvfp4_qsa pool (1 layer, layer id 0): set_kv_buffer with
                     the device global scale, read back through get_raw_kv_buffer and the
                     qsakv4 gather kernel: equal to the reference dequantizer; reconstruction
                     error of nvfp4 vs fp8 for the same K/V (info).
  draft_backend_*    qsakv4's backend checks re-run on a 1-layer pool at layer id 0 (the draft
                     layer): decode and chunked-prefill-with-prefix outputs on the nvfp4_qsa
                     pool equal those on an unquantized pool holding the unpacked rows; the
                     decode output error of an fp8 vs an nvfp4 draft cache against BF16 (info).
"""

from __future__ import annotations

import importlib
import json
import os
import sys
import traceback
from types import SimpleNamespace

import torch

DEVICE = "cuda"
HEADS, DIM, PAGE = 2, 256, 64
QSA_LAYERS = list(range(3, 48, 4))  # the 12 full-attention (QSA) layers of 48
TEXT = SimpleNamespace(  # the QSA fields of Qwen3.8-Flash-Next's text_config
    model_type="qwen4_exp_text",
    indexer_n_heads=4,
    indexer_kv_heads=1,
    indexer_head_dim=128,
    indexer_budget=2048,
    indexer_compress_ratio=4,
)
QSA_POOL_ARGS = dict(
    qsa_index_kv_heads=1,
    qsa_index_head_dim=128,
    qsa_compress_ratio=4,
    qsa_token_topk=2048,
    num_request_slots=16,
)
FP4 = getattr(torch, "float4_e2m1fn_x2", None)
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
    except Exception as exc:
        emit(name, passed=False, error=f"{type(exc).__name__}: {exc}",
             traceback=traceback.format_exc(limit=12))


# ---------------------------------------------------------------------------


def check_server_args():
    import argparse

    from sglang.srt.server_args import ServerArgs

    parser = argparse.ArgumentParser()
    ServerArgs.add_cli_args(parser)
    ns = parser.parse_args(
        ["--model-path", "dummy", "--speculative-draft-kv-cache-dtype", "nvfp4_qsa"]
    )
    accepts = ns.speculative_draft_kv_cache_dtype == "nvfp4_qsa"
    try:
        ServerArgs._handle_kv4_compatibility(
            SimpleNamespace(kv_cache_dtype="fp8_e4m3", speculative_draft_kv_cache_dtype="nvfp4_qsa")
        )
        refuses = False
    except ValueError:
        refuses = True
    ServerArgs._handle_kv4_compatibility(  # must not raise
        SimpleNamespace(kv_cache_dtype="fp8_e4m3", speculative_draft_kv_cache_dtype="fp8_e4m3")
    )
    emit("server_args", passed=accepts and refuses, cli_accepts_nvfp4_qsa=accepts,
         refuses_without_nvfp4_qsa_target=refuses)


def check_dtype_mapping():
    from sglang.srt.layers.quantization.fp4_kv_cache_quant_method import (
        NVFP4QSAKVCacheMethod,
        get_kv_cache_quant_method,
        resolve_kv_cache_quant,
    )
    from sglang.srt.mem_cache.kv_cache_dtype import configure_kv_cache_dtype

    common = dict(model=None, model_dtype=BF16, is_dflash=False,
                  speculative_draft_attention_backend=None, is_draft_worker=True,
                  server_args_kv_cache_dtype="nvfp4_qsa")
    d4 = configure_kv_cache_dtype(speculative_draft_kv_cache_dtype="nvfp4_qsa", **common)
    d8 = configure_kv_cache_dtype(speculative_draft_kv_cache_dtype="fp8_e4m3", **common)
    inherit = configure_kv_cache_dtype(speculative_draft_kv_cache_dtype=None, **common)
    qm = get_kv_cache_quant_method(resolve_kv_cache_quant(d4[0]), num_layers=1, device=DEVICE)
    facts = {
        "draft_nvfp4_ok": d4 == ("nvfp4_qsa", FP4),
        "draft_fp8_ok": d8 == ("fp8_e4m3", FP8),
        "draft_inherits_fp4": inherit[1] == FP4,
        "quant_method_ok": isinstance(qm, NVFP4QSAKVCacheMethod),
        "scale_table_ok": qm.k_scales_gpu.numel() >= 256,
        "no_workspace_ok": not qm.needs_dequant_workspace() and qm.dequant_workspace_dtype() is None,
    }
    emit("dtype_mapping", passed=all(facts.values()), **facts)


def _quant_method(num_layers, layer_scales):
    from sglang.srt.layers.quantization.fp4_kv_cache_quant_method import (
        get_kv_cache_quant_method,
    )

    qm = get_kv_cache_quant_method("nvfp4_qsa", num_layers=num_layers, device=DEVICE)
    for layer_id, (k_gs, v_gs) in layer_scales.items():
        qm.k_scales_gpu[layer_id].fill_(k_gs)
        qm.v_scales_gpu[layer_id].fill_(v_gs)
        qm.k_scales_float[layer_id] = k_gs
        qm.v_scales_float[layer_id] = v_gs
    return qm


def build_pool(kv, layer_ids, size, layer_scales=None):
    """A QSATokenToKVPool as KVCacheConfigurator._build_hybrid_linear_kv_pool builds it."""
    from sglang.srt.mem_cache.qsa_kv_pool import QSATokenToKVPool

    qm = None
    if kv == "nvfp4_qsa":
        qm = _quant_method(len(layer_ids), layer_scales or {})
        dtype = FP4
    else:
        dtype = {"fp8_e4m3": FP8, "bf16": BF16}[kv]
    return QSATokenToKVPool(
        size=size,
        dtype=dtype,
        page_size=PAGE,
        head_num=HEADS,
        head_dim=DIM,
        full_attention_layer_ids=list(layer_ids),
        device=DEVICE,
        mamba_pool=None,
        enable_kv_cache_copy=True,
        quant_method=qm,
        **QSA_POOL_ARGS,
    )


MEASURED = {}


def check_pool_bytes():
    sizes = (64 * 1024, 192 * 1024)
    cases = (("target", "nvfp4_qsa", QSA_LAYERS), ("target", "fp8_e4m3", QSA_LAYERS),
             ("draft", "nvfp4_qsa", [0]), ("draft", "fp8_e4m3", [0]), ("draft", "bf16", [0]))
    for role, kv, layers in cases:
        used = []
        for size in sizes:
            torch.cuda.synchronize()
            torch.cuda.empty_cache()
            before = torch.cuda.memory_allocated()
            pool = build_pool(kv, layers, size)
            torch.cuda.synchronize()
            used.append(torch.cuda.memory_allocated() - before)
            del pool
        per_token = (used[1] - used[0]) / (sizes[1] - sizes[0])
        MEASURED[(role, kv)] = per_token
        emit("pool_bytes", role=role, kv=kv, layers=len(layers), bytes_per_token=per_token,
             fixed_bytes=used[0] - per_token * sizes[0])


def check_budget():
    import sglang.srt.layers.cp.utils as cp_utils
    import sglang.srt.model_executor.pool_configurator as pc

    stubbed = ("mambaish_config", "get_parallel", "get_spec", "is_minimax_sparse", "is_deepseek_dsa")
    saved = {name: getattr(pc, name) for name in stubbed}
    saved_split = cp_utils.get_glm_dsa_layer_split_effective_num_layers
    saved_env = os.environ.get("SGLANG_QSA_EXACT_KV_BUDGET")
    model_config = SimpleNamespace(
        hf_config=TEXT, hf_text_config=TEXT, head_dim=DIM, v_head_dim=DIM, context_len=139264,
        get_num_kv_heads=lambda tp=1, dcp=1: HEADS,
    )

    def kvc(target):
        return SimpleNamespace(
            kv_cache_dtype_str=target,
            kv_cache_dtype={"nvfp4_qsa": FP4, "fp8_e4m3": FP8}[target],
            model_config=model_config,
            model_dtype=BF16,
            layer_info=SimpleNamespace(start_layer=0, end_layer=48, num_effective_layers=48),
            ps=SimpleNamespace(pp_size=1),
            server_args=SimpleNamespace(max_total_tokens=None),
            spec_algorithm=SimpleNamespace(is_eagle=lambda: True, is_standalone=lambda: False,
                                           is_dflash_family=lambda: False),
            is_draft_worker=False,
            spec_aux_config=SimpleNamespace(eagle_draft_num_layers=1),
            use_mla_backend=False,
        )

    m = MEASURED
    t4 = m.get(("target", "nvfp4_qsa"))
    cases = (  # target, draft flag, exact budget env, expected bytes/token
        ("nvfp4_qsa", "fp8_e4m3", "1", t4 and t4 + m[("draft", "fp8_e4m3")], 8768),
        ("nvfp4_qsa", "nvfp4_qsa", "1", t4 and t4 + m[("draft", "nvfp4_qsa")], 8320),
        ("nvfp4_qsa", None, "1", t4 and t4 + m[("draft", "nvfp4_qsa")], 8320),
        ("nvfp4_qsa", "bf16", "1", t4 and t4 + m[("draft", "bf16")], 9792),
        ("nvfp4_qsa", "fp8_e4m3", "0", None, 9429),  # the generic formula, unchanged
        # FP8 keeps the generic formula: int(13056 * (1 + 1/12)) = 14143 in floating point,
        # one byte under the 14,144 allocated (unchanged behavior, so not compared to the pools).
        ("fp8_e4m3", "fp8_e4m3", "1", None, 14143),
    )
    try:
        pc.mambaish_config = lambda mc: SimpleNamespace(full_attention_layer_ids=QSA_LAYERS)
        pc.get_parallel = lambda: SimpleNamespace(attn_tp_size=1, attn_dcp_size=1, attn_cp_size=1)
        pc.is_minimax_sparse = lambda cfg: False
        pc.is_deepseek_dsa = lambda cfg: False
        cp_utils.get_glm_dsa_layer_split_effective_num_layers = lambda runner, n: n
        for target, draft, env, measured, expected in cases:
            os.environ["SGLANG_QSA_EXACT_KV_BUDGET"] = env
            pc.get_spec = lambda d=draft: SimpleNamespace(speculative_draft_kv_cache_dtype=d)
            cell = pc.DefaultPoolConfigurator(kvc(target))._cell_size
            ok = cell == expected and (measured is None or abs(cell - measured) < 0.5)
            emit("budget", passed=ok, target=target, draft=draft, exact_env=env, cell=cell,
                 expected=expected, measured_alloc=measured,
                 tokens_at_live_budget=(1441984 * 9429 // cell) // 64 * 64)
    finally:
        for name, value in saved.items():
            setattr(pc, name, value)
        cp_utils.get_glm_dsa_layer_split_effective_num_layers = saved_split
        if saved_env is None:
            os.environ.pop("SGLANG_QSA_EXACT_KV_BUDGET", None)
        else:
            os.environ["SGLANG_QSA_EXACT_KV_BUDGET"] = saved_env


def _rel_rms(a, b):
    a, b = a.float(), b.float()
    return float((a - b).pow(2).mean().sqrt() / b.pow(2).mean().sqrt().clamp_min(1e-12))


def check_draft_pool_rw():
    from sglang.srt.layers.attention.qsa.sparse_attn import (
        qwen_sparse_gather_slots_nvfp4_triton,
    )

    T = _qsakv4_test()
    slots, rows = 8192, 3000
    pool = build_pool("nvfp4_qsa", [0], slots, layer_scales={0: (0.8, 1.6)})
    g = torch.Generator(device="cpu").manual_seed(7)
    loc = (torch.randperm(slots - 1, generator=g)[:rows] + 1).to(DEVICE)
    k = T.make_kv(rows, seed=11)
    v = T.make_kv(rows, seed=12)
    layer = SimpleNamespace(layer_id=0)
    pool.set_kv_buffer(layer, loc, k, v, None, None)  # None: the pool's device global scales
    kp, vp, ks, vs = pool.get_raw_kv_buffer(0)
    qm = pool.full_kv_pool.quant_method
    k_gs, v_gs = qm.k_scales_gpu[0:1], qm.v_scales_gpu[0:1]
    out_k = torch.empty(rows, HEADS, DIM, dtype=BF16, device=DEVICE)
    out_v = torch.empty_like(out_k)
    qwen_sparse_gather_slots_nvfp4_triton(kp, vp, ks, vs, k_gs, v_gs, loc, out_k, out_v)
    ref_k = T.ref_dequant_f32(kp[loc], ks[loc], k_gs).to(BF16)
    ref_v = T.ref_dequant_f32(vp[loc], vs[loc], v_gs).to(BF16)
    exact = torch.equal(out_k, ref_k) and torch.equal(out_v, ref_v)
    scales_ok = abs(float(k_gs) - 0.8) < 1e-6 and abs(float(v_gs) - 1.6) < 1e-6
    others = torch.ones(kp.shape[0], dtype=torch.bool, device=DEVICE)  # slots + padding page
    others[loc] = False
    untouched = bool((kp[others].view(torch.uint8) == 0).all())
    err4 = max(_rel_rms(out_k, k), _rel_rms(out_v, v))
    err8 = max(_rel_rms(k.to(FP8).to(BF16), k), _rel_rms(v.to(FP8).to(BF16), v))
    emit("draft_pool_rw", passed=exact and scales_ok and untouched and err4 < 0.15,
         read_back_exact=exact, global_scales_ok=scales_ok, untouched=untouched,
         rel_rms_nvfp4=err4, rel_rms_fp8=err8,
         is_quantized=bool(getattr(pool.full_kv_pool, "is_quantized_kv_cache", False)))


_T = None


def _qsakv4_test():
    """qsakv4's GPU test module (shipped with --pre-file), retargeted to the draft layer."""
    global _T
    if _T is None:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        _T = importlib.import_module("test_qsa_nvfp4_daniel")
        _T.LAYER_IDS = (0,)  # the MTP draft pool: one full-attention layer, layer id 0
        _T.GLOBAL_SCALES = {0: (0.8, 1.6)}
        _T.FLASHINFER = _T.have_flashinfer_nvfp4()
        _T.emit = lambda check, passed=None, **f: emit("draft_" + check, passed, **f)
    return _T


def check_draft_backend():
    T = _qsakv4_test()
    if not T.FLASHINFER:
        emit("draft_backend", passed=False, error="flashinfer nvfp4 quantizer missing")
        return
    for name, fn, arg in (("backend_decode", T.check_backend_decode, "fp8"),
                          ("backend_extend_prefix", T.check_backend_extend_prefix, "fp8"),
                          ("attention_error", T.check_attention_error, None)):
        try:
            fn(arg) if arg is not None else fn()
        except Exception as exc:
            emit("draft_" + name, passed=False, error=f"{type(exc).__name__}: {exc}",
                 traceback=traceback.format_exc(limit=12))
    T.set_scratch(None)


def main():
    if not torch.cuda.is_available():
        print(json.dumps({"summary": "kvshrink", "passed": False, "error": "no CUDA device"}))
        return 1
    emit("device", name=torch.cuda.get_device_name(0),
         capability=list(torch.cuda.get_device_capability(0)), torch=torch.__version__)
    run("server_args", check_server_args)
    run("dtype_mapping", check_dtype_mapping)
    run("pool_bytes", check_pool_bytes)
    run("budget", check_budget)
    run("draft_pool_rw", check_draft_pool_rw)
    run("draft_backend", check_draft_backend)
    failed = sorted({r["check"] for r in RESULTS if r.get("passed") is False})
    summary = {"summary": "kvshrink", "passed": not failed,
               "failed": failed, "checks": len([r for r in RESULTS if "passed" in r])}
    print(json.dumps(summary, sort_keys=True), flush=True)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
