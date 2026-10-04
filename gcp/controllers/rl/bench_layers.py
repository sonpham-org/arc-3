"""Where a training step's time goes, one decoder layer at a time (4-Oct-2026, Son: "optimize the recipe to the
teeth first"; the 039 profile showed the experts' math was ~8% of a 115k-token step and could not say which part of
the model the rest came from).

One GPU, no device map, no accelerate hooks: one linear-attention layer and one full-attention layer built from the
real config with their real BF16 weights (/opt/m/bf16) and Daniel's GPTQ experts (/opt/m/daniel), the LoRA injected
on the trainer's targets, and the trainer's own patched code paths (fast_qsa decoder / attention forward, offloaded
layer checkpoint, nvfp4_experts dequant + grouped_mm). Per layer type and sequence length it times, forward alone and
forward + backward (CUDA-synchronised wall clock, best of --reps):
  hc_mix      the attention-side hyper-connection mix (token-chunked like the trainer)
  core        linear_attn (GDN) or self_attn (QSA selection + gathered attention)
  moe         the MoE block (router, unpack every routed expert, grouped_mm, shared expert)
  dequant     the expert unpack alone (once per forward and once per backward replay in the trainer)
  layer       the whole decoder layer under the trainer's offloaded checkpoint (what a step runs 48 times)
plus one torch.profiler table per layer type (top ops by self CUDA time), and which linear-attention kernels the
model code picked (fla / causal_conv1d or the PyTorch reference).

  /usr/bin/python3.12 bench_layers.py --model /mnt/snap/opt/m/bf16 --experts /mnt/snap/opt/m/daniel \
      --tokens 4096,115000 --out /tmp/bench.json
Estimate of a step: 36 x layer(linear_attention) + 12 x layer(indexed_attention) at the record's length (+ head and
loss, small). Triton kernels (fla, the rotary) need the Python headers on the box (python3.12-dev).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import traceback
from pathlib import Path

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fast_qsa  # noqa: E402
import nvfp4_experts  # noqa: E402

BENCH_TARGETS = (r".*(self_attn\.(q_proj|k_proj|v_proj|o_proj)|linear_attn\.(in_proj_qkv|in_proj_z|out_proj)"
                 r"|mlp\.shared_expert\.(gate_proj|up_proj|down_proj))")
DEV = torch.device("cuda:0")


def _m():
    from transformers.models.qwen4_exp import modeling_qwen4_exp as m
    return m


def text_config(model_dir: str):
    from transformers import AutoConfig
    cfg = AutoConfig.from_pretrained(model_dir)
    return cfg.get_text_config() if hasattr(cfg, "get_text_config") else cfg.text_config


def build_layer(tc, idx: int, model_dir: str, experts_dir: str, rank: int, alpha: int, lora_dtype: str = "fp32"):
    """One decoder layer on the GPU with its real weights (PLE dropped: its 51B table lives on the CPU in training)."""
    from accelerate import init_empty_weights
    from accelerate.utils import set_module_tensor_to_device
    from safetensors import safe_open
    m = _m()
    nvfp4_experts.install_placeholder()
    torch.set_default_dtype(torch.bfloat16)          # from_pretrained(dtype=bf16): params bf16 unless kept in fp32
    try:
        with init_empty_weights():
            layer = m.Qwen4ExpTextDecoderLayer(tc, layer_idx=idx)
    finally:
        torch.set_default_dtype(torch.float32)
    if getattr(layer, "ple", None) is not None:
        layer.ple = None
    keep32 = set()
    for name in dir(m):
        obj = getattr(m, name)
        if isinstance(obj, type):
            keep32 |= set(getattr(obj, "_keep_in_fp32_modules", None) or [])
            keep32 |= set(getattr(obj, "_keep_in_fp32_modules_strict", None) or [])
    wm = json.loads((Path(model_dir) / "model.safetensors.index.json").read_text())["weight_map"]
    pre = f"model.language_model.layers.{idx}."
    missing, by_file = [], {}
    names = [n for n, _ in layer.named_parameters()] + [n for n, b in layer.named_buffers() if b is not None]
    for n in names:
        if pre + n in wm:
            by_file.setdefault(wm[pre + n], []).append(n)
        else:
            missing.append(n)
    fp32 = []
    with_dtype = {}
    for f, ns in by_file.items():
        with safe_open(str(Path(model_dir) / f), framework="pt") as sf:
            for n in ns:
                t = sf.get_tensor(pre + n)
                if t.is_floating_point():
                    want = torch.float32 if any(k in n.split(".") for k in keep32) else torch.bfloat16
                    if want == torch.float32:
                        fp32.append(n)
                    t = t.to(want)
                    with_dtype[n] = want
                set_module_tensor_to_device(layer, n, DEV, value=t, dtype=with_dtype.get(n))
    still_meta = [n for n, p in layer.named_parameters() if p.device.type == "meta"]
    for n in still_meta:                                      # anything the checkpoint lacks: random (reported)
        p = dict(layer.named_parameters())[n]
        set_module_tensor_to_device(layer, n, DEV, value=torch.randn(p.shape, dtype=torch.bfloat16) * 0.02,
                                    dtype=torch.bfloat16)
    dtypes = {}
    for n, p in layer.named_parameters():
        dtypes[str(p.dtype)] = dtypes.get(str(p.dtype), 0) + 1
    ex = layer.mlp.experts
    packed = nvfp4_experts.read_layer_gptq(experts_dir, idx, ex.num_experts, json.loads(
        (Path(experts_dir) / "model.safetensors.index.json").read_text())["weight_map"])
    for k, v in packed.items():
        setattr(ex, k, v.to(DEV))
    ex.fmt = "gptq"
    for p in layer.parameters():
        p.requires_grad_(False)
    from peft import LoraConfig, inject_adapter_in_model
    layer = inject_adapter_in_model(LoraConfig(r=rank, lora_alpha=alpha, lora_dropout=0.0, bias="none",
                                               target_modules=BENCH_TARGETS), layer)
    # lora_train builds the adapter with get_peft_model, whose autocast_adapter_dtype=True keeps adapter weights in
    # float32 on a BF16 model (each LoRA call then casts its input to float32); --lora-dtype bf16 measures the other way
    want = torch.float32 if lora_dtype == "fp32" else torch.bfloat16
    for n, p in layer.named_parameters():
        if "lora_" in n:
            p.data = p.data.to(DEV, want)
            p.requires_grad_(True)
    layer.train()
    n_lora = sum(1 for n, _ in layer.named_modules() if n.endswith("lora_A"))
    return layer, {"missing_in_ckpt": [n for n in missing if ".experts." not in n][:20], "random": still_meta[:20],
                   "lora_modules": n_lora, "layer_type": layer.layer_type, "keep_in_fp32": sorted(keep32),
                   "fp32_params": fp32[:20], "param_dtypes": dtypes}


def rotary(tc, s: int):
    """(cos, sin) for positions 0..s-1, as the text model hands them to its layers."""
    m = _m()
    cls = next(getattr(m, n) for n in dir(m) if n.endswith("RotaryEmbedding") and "Text" in n)
    rot = cls(config=tc).to(DEV)
    x = torch.zeros(1, s, 8, dtype=torch.bfloat16, device=DEV)
    pid = torch.arange(s, device=DEV)[None]
    tried = []
    for ids in (pid, pid[None].expand(3, 1, s), pid[None].expand(4, 1, s)):
        try:
            cos, sin = rot(x, ids)
        except Exception as exc:                               # noqa: BLE001 - try the next position-id layout
            tried.append(f"{tuple(ids.shape)}: {type(exc).__name__}")
            continue
        if cos.dim() == 3 and cos.shape[0] == 1 and cos.shape[1] == s:     # [1, S, D], what fast_qsa indexes
            return cos.to(torch.bfloat16), sin.to(torch.bfloat16)
        tried.append(f"{tuple(ids.shape)}: cos {tuple(cos.shape)}")
    raise RuntimeError(f"could not get [1, S, D] rotary tables: {tried}")


def timed(fn, reps: int) -> float:
    best = math.inf
    for _ in range(reps):
        torch.cuda.synchronize()
        t = time.perf_counter()
        fn()
        torch.cuda.synchronize()
        best = min(best, time.perf_counter() - t)
    return round(best, 3)


def bench_one(layer, tc, s: int, reps: int, profile: bool) -> dict:
    hc = int(getattr(tc, "hc_count", 4) or 4)
    h = tc.hidden_size
    out: dict = {"tokens": s}
    torch.manual_seed(0)
    x_full = (torch.randn(1, s, hc * h, device=DEV, dtype=torch.bfloat16) * 0.5)
    x_core = (torch.randn(1, s, h, device=DEV, dtype=torch.bfloat16) * 0.5)
    pe = rotary(tc, s) if layer.layer_type != "linear_attention" else None

    def fwd_bwd(f, x):
        def run():
            xx = x.detach().requires_grad_(True)
            y = f(xx)
            y = y[0] if isinstance(y, tuple) else y
            y.backward(torch.ones_like(y) * 1e-3)
        return run

    def fwd(f, x):
        def run():
            with torch.no_grad():
                f(x)
        return run

    def hc_mix(xx):
        return fast_qsa._tokenwise(lambda t: layer.attn_hyper_connection(t)[0], xx)

    if layer.layer_type == "linear_attention":
        def core(xx):
            return layer.linear_attn(xx, cache_params=None, attention_mask=None)
    else:
        def core(xx):
            return layer.self_attn(xx, pe, attention_mask=None, past_key_values=None)[0]

    def moe(xx):
        return layer.mlp(xx)

    def whole(xx):
        run = fast_qsa.offload_checkpoint_for(0)
        return run(lambda t: layer(t, pe, attention_mask=None), xx)

    parts = [("hc_mix", hc_mix, x_full), ("core", core, x_core), ("moe", moe, x_core), ("layer", whole, x_full)]
    for name, f, x in parts:
        try:
            out[f"{name}_fwd_s"] = timed(fwd(f, x), reps)
            out[f"{name}_fwdbwd_s"] = timed(fwd_bwd(f, x), reps)
        except Exception as exc:                               # noqa: BLE001 - report and go on
            out[f"{name}_error"] = f"{type(exc).__name__}: {exc}"[:400]
            traceback.print_exc()
        torch.cuda.empty_cache()
    try:
        out["dequant_s"] = timed(lambda: layer.mlp.experts.weights(), reps)
    except Exception as exc:                                   # noqa: BLE001
        out["dequant_error"] = f"{type(exc).__name__}: {exc}"[:300]
    out["peak_gib"] = round(torch.cuda.max_memory_allocated() / 2**30, 1)
    torch.cuda.reset_peak_memory_stats()
    if profile:
        from torch.profiler import ProfilerActivity, profile as prof
        try:
            with prof(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA]) as p:
                fwd_bwd(whole, x_full)()
                torch.cuda.synchronize()
            out["profile"] = p.key_averages().table(sort_by="self_cuda_time_total", row_limit=25, max_name_column_width=70)
            ev = p.key_averages()
            out["kernel_launches"] = int(sum(e.count for e in ev if e.key in ("cudaLaunchKernel", "cudaLaunchKernelExC")))
        except Exception as exc:                               # noqa: BLE001
            out["profile_error"] = f"{type(exc).__name__}: {exc}"[:300]
    return out


def flex_check(layer, tc, s: int, reps: int) -> dict:
    """Indexed-attention layer only: the flex path against the gather path on the same input (output and LoRA
    gradients), then the flex path's times. Same picks by construction (one selection routine)."""
    out: dict = {"tokens": s}
    torch.manual_seed(1)
    x = torch.randn(1, s, tc.hidden_size, device=DEV, dtype=torch.bfloat16) * 0.5
    pe = rotary(tc, s)
    lora = [p for n, p in layer.named_parameters() if "lora_" in n and "self_attn" in n]

    def run(impl):
        fast_qsa.ATTN_IMPL = impl
        for p in lora:
            p.grad = None
        xx = x.detach().requires_grad_(True)
        y = layer.self_attn(xx, pe, attention_mask=None, past_key_values=None)[0]
        y.float().pow(2).mean().backward()
        return y.detach().float(), [p.grad.detach().float().clone() for p in lora], xx.grad.detach().float()

    try:
        yg, gg, xg = run("gather")
        yf, gf, xf = run("flex")
        rel = lambda a, b: float((a - b).abs().max() / b.abs().max().clamp_min(1e-12))
        out["out_rel_maxdiff"] = round(rel(yf, yg), 5)
        out["out_cos"] = round(float(torch.nn.functional.cosine_similarity(yf.flatten(), yg.flatten(), dim=0)), 6)
        out["xgrad_rel_maxdiff"] = round(rel(xf, xg), 5)
        out["lora_grad_cos_min"] = round(min(float(torch.nn.functional.cosine_similarity(a.flatten(), b.flatten(), dim=0))
                                             for a, b in zip(gf, gg)), 6)
    except Exception as exc:                                   # noqa: BLE001
        out["compare_error"] = f"{type(exc).__name__}: {exc}"[:600]
        traceback.print_exc()
    fast_qsa.ATTN_IMPL = "flex"
    try:
        core = lambda xx: layer.self_attn(xx, pe, attention_mask=None, past_key_values=None)[0]

        def fb():
            xx = x.detach().requires_grad_(True)
            core(xx).backward(torch.ones(1, s, tc.hidden_size, device=DEV, dtype=torch.bfloat16) * 1e-3)

        def fo():
            with torch.no_grad():
                core(x)
        fo()                                                   # compile outside the timing
        fb()
        out["flex_core_fwd_s"] = timed(fo, reps)
        out["flex_core_fwdbwd_s"] = timed(fb, reps)
        hc = int(getattr(tc, "hc_count", 4) or 4)
        xf_ = torch.randn(1, s, hc * tc.hidden_size, device=DEV, dtype=torch.bfloat16) * 0.5

        def lb():
            xx = xf_.detach().requires_grad_(True)
            y = fast_qsa.offload_checkpoint_for(0)(lambda t: layer(t, pe, attention_mask=None), xx)
            y.backward(torch.ones_like(y) * 1e-3)
        out["flex_layer_fwdbwd_s"] = timed(lb, reps)
        out["tiles"] = fast_qsa._FLEX.get("last")             # key tiles computed vs a dense causal pass
    except Exception as exc:                                   # noqa: BLE001
        out["flex_time_error"] = f"{type(exc).__name__}: {exc}"[:600]
        traceback.print_exc()
    fast_qsa.ATTN_IMPL = "gather"
    out["peak_gib"] = round(torch.cuda.max_memory_allocated() / 2**30, 1)
    torch.cuda.reset_peak_memory_stats()
    return out


def hc_check(layer, tc, s: int, reps: int) -> dict:
    """The compiled hyper-connection mix (fast_qsa.hc_mix) against the module: outputs, gradient, times."""
    hc = int(getattr(tc, "hc_count", 4) or 4)
    torch.manual_seed(2)
    x = torch.randn(1, s, hc * tc.hidden_size, device=DEV, dtype=torch.bfloat16) * 0.5
    mod = layer.attn_hyper_connection
    out: dict = {"tokens": s}

    def module(xx):
        m_, _, w_ = mod(xx)
        return m_, w_

    def compiled(xx):
        return fast_qsa.hc_mix(mod, xx)

    def run(f):
        xx = x.detach().requires_grad_(True)
        y = fast_qsa._tokenwise(f, xx)
        (y[0].float().pow(2).mean() + y[1].float().pow(2).mean()).backward()
        return y[0].detach().float(), y[1].detach().float(), xx.grad.detach().float()

    try:
        a_, b_ = run(module), run(compiled)
        for name, u, v in zip(("mixed", "inj", "xgrad"), b_, a_):
            out[f"{name}_rel_maxdiff"] = round(float((u - v).abs().max() / v.abs().max().clamp_min(1e-12)), 5)
        for name, f in (("module", module), ("compiled", compiled)):
            def fb(f=f):
                xx = x.detach().requires_grad_(True)
                y = fast_qsa._tokenwise(f, xx)
                (y[0].float().sum() + y[1].float().sum()).backward()
            out[f"{name}_fwdbwd_s"] = timed(fb, reps)
    except Exception as exc:                                   # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"[:600]
        traceback.print_exc()
    return out


def kernels_in_use(layer) -> dict:
    la = getattr(layer, "linear_attn", None)
    if la is None:
        return {}
    got = {}
    for k, v in vars(la).items():
        if callable(v) and any(s in k for s in ("chunk", "conv", "recurrent", "gated", "norm")):
            got[k] = f"{getattr(v, '__module__', '?')}.{getattr(v, '__name__', type(v).__name__)}"
    try:
        import fla  # noqa: F401
        got["fla_import"] = getattr(fla, "__version__", "ok")
    except Exception as exc:                                   # noqa: BLE001
        got["fla_import"] = f"no: {exc}"[:120]
    try:
        import causal_conv1d  # noqa: F401
        got["causal_conv1d_import"] = "ok"
    except Exception as exc:                                   # noqa: BLE001
        got["causal_conv1d_import"] = f"no: {exc}"[:120]
    return got


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--experts", required=True)
    ap.add_argument("--tokens", default="4096,115000")
    ap.add_argument("--layers", default="0,3", help="layer indices to build (0 = linear attention, 3 = full)")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--rank", type=int, default=32)
    ap.add_argument("--alpha", type=int, default=64)
    ap.add_argument("--no-profile", action="store_true")
    ap.add_argument("--flex-check", default="", help="indexed-attention layers: flex vs gather at these lengths, "
                    "e.g. 32768,115000 (then the plain timing runs are skipped unless --tokens is given)")
    ap.add_argument("--hc-check", default="", help="compiled hyper-connection mix vs the module at these lengths")
    ap.add_argument("--lora-dtype", choices=("fp32", "bf16"), default="fp32", help="fp32 = what lora_train gets")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    fast_qsa.install(None, offload=True)
    tc = text_config(a.model)
    res = {"lora_dtype": a.lora_dtype, "torch": torch.__version__, "gpu": torch.cuda.get_device_name(0),
           "env": {k: v for k, v in os.environ.items() if k.startswith("ARC3_")}, "layers": {}}
    import transformers
    res["transformers"] = transformers.__version__
    for idx in [int(x) for x in a.layers.split(",")]:
        t0 = time.time()
        layer, info = build_layer(tc, idx, a.model, a.experts, a.rank, a.alpha, a.lora_dtype)
        info["build_s"] = round(time.time() - t0, 1)
        info["kernels"] = kernels_in_use(layer)
        print(f"layer {idx}: {json.dumps(info)}", flush=True)
        runs = []
        if a.hc_check:
            for s in [int(x) for x in a.hc_check.split(",")]:
                hcr = hc_check(layer, tc, s, a.reps)
                print(json.dumps(hcr), flush=True)
                res.setdefault("hc", []).append(dict(hcr, layer=idx))
        if a.flex_check and info["layer_type"] != "linear_attention":
            for s in [int(x) for x in a.flex_check.split(",")]:
                fc = flex_check(layer, tc, s, a.reps)
                print(json.dumps(fc), flush=True)
                res.setdefault("flex", []).append(dict(fc, layer=idx))
        for s in [int(x) for x in a.tokens.split(",") if x]:
            r = bench_one(layer, tc, s, a.reps, profile=not a.no_profile and s == max(int(x) for x in a.tokens.split(",")))
            print(json.dumps({k: v for k, v in r.items() if k != "profile"}), flush=True)
            if "profile" in r:
                print(r["profile"], flush=True)
            runs.append(r)
        res["layers"][str(idx)] = {"info": info, "runs": runs}
        del layer
        torch.cuda.empty_cache()
        Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    counts: dict[str, int] = {}
    for t in tc.layer_types:
        counts[t] = counts.get(t, 0) + 1
    est = {}
    for idx, d in res["layers"].items():
        for r in d["runs"]:
            est.setdefault(r["tokens"], {})[d["info"]["layer_type"]] = r.get("layer_fwdbwd_s")
    res["layer_counts"] = counts
    res["step_estimate_s"] = {s: (round(sum(counts[k] * v[k] for k in counts), 1)
                                  if all(v.get(k) for k in counts) else None) for s, v in est.items()}
    print(f"step estimate ({counts}, fwd+bwd under the offloaded checkpoint):", res["step_estimate_s"], flush=True)
    Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
