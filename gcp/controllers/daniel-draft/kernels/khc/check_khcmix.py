"""khc fused HC mix check in the PATCHED install (4-Oct-2026, Kernel optimizations thread). Pre-server script, free GPU.

Real weights (layer-0 attention HyperConnection of the served model: input_mix_weight_down [320, 10240],
input_mix_weight_up [10240, 320], hc_norm.weight [2560]) and hc_norm-ed random inputs, at 17..64 rows:
1. accuracy: fused vs his compiled chain (GatedResidual._mix_compute) and both vs an fp32 reference;
   bitwise share with the compiled chain; determinism (two runs equal); CUDA-graph replay with fresh inputs;
   hc=5 (MTP layout, K = 12800) on synthetic weights
2. dispatch through the patched GatedResidual.mix: 16 rows -> his persistent kernel, 17..64 -> fused, 65 -> compiled
3. timing with COLD weights (R distinct weight copies > 3x L2 per graph walk): compiled chain vs fused
One JSON line per result; last line {"verdict": ...}.
"""
import glob
import json
import os
import struct
import time

import numpy as np
import torch

DEV = torch.device("cuda")
T0 = time.time()
FAIL = []
HC, HS, LR = 4, 2560, 320
MODEL_GLOB = "/kaggle/input/models/dfranzen/intel-qwen3.8-flash-next-w4a16-autoround/**/model.safetensors.index.json"


def emit(**kw):
    kw["t"] = round(time.time() - T0, 1)
    print(json.dumps(kw), flush=True)


def graph_time(fns, reps=10):
    s = torch.cuda.Stream()
    s.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(s):
        for f in fns[:2]:
            f()
    torch.cuda.current_stream().wait_stream(s)
    torch.cuda.synchronize()
    g = torch.cuda.CUDAGraph()
    with torch.cuda.graph(g):
        for f in fns:
            f()
    g.replay()
    g.replay()
    torch.cuda.synchronize()
    e0, e1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
    e0.record()
    for _ in range(reps):
        g.replay()
    e1.record()
    torch.cuda.synchronize()
    del g
    return e0.elapsed_time(e1) * 1e3 / (reps * len(fns))


def real_weights():
    idx = sorted(glob.glob(MODEL_GLOB, recursive=True))[0]
    d = os.path.dirname(idx)
    wm = json.load(open(idx))["weight_map"]
    pre = "model.language_model.layers.0.attn_hyper_connection."

    def t(name):
        path = os.path.join(d, wm[name])
        with open(path, "rb") as f:
            n = struct.unpack("<Q", f.read(8))[0]
            h = json.loads(f.read(n))
        m = h[name]
        o0, o1 = m["data_offsets"]
        a = np.memmap(path, dtype=np.uint16, mode="r", offset=8 + n + o0, shape=tuple(m["shape"]))
        return torch.from_numpy(np.ascontiguousarray(a).view(np.int16)).view(torch.bfloat16).to(DEV)

    return t(pre + "input_mix_weight_down.weight"), t(pre + "input_mix_weight_up.weight"), t(pre + "hc_norm.weight")


def make_module(hc, wd, wu, wn):
    import sglang.srt.layers.hyperconnection as H
    per_branch = wn.numel() == hc * HS   # the served model norms each branch with its own weights
    cfg = H.HyperConnectionConfig(hc_count=hc, hidden_size=HS, params_dtype=torch.bfloat16, hc_lowrank=LR,
                                  hc_per_branch_norm=per_branch)
    mod = H.GatedResidual(cfg, use_mix=True, use_combine=False)
    with torch.no_grad():
        mod.input_mix_weight_down.weight.copy_(wd)
        mod.input_mix_weight_up.weight.copy_(wu)
        # the server loads every parameter as bf16 on the GPU; the norm kernel accepts only that
        mod.hc_norm.weight.data = wn.to(device=DEV, dtype=torch.bfloat16).contiguous()
    return H, mod


def fp32_ref(x, wd, wu, hc):
    t = torch.nn.functional.silu((x.float() @ wd.float().T) / hc)
    g = torch.sigmoid(t @ wu.float().T)
    return (g.unflatten(-1, (hc, HS)) * x.float().unflatten(-1, (hc, HS))).mean(dim=-2)


def check_accuracy(H, mod, hc, wd, wu, label):
    for m in (17, 24, 32, 36, 40, 44, 48, 52, 64):
        hin = torch.randn(m, hc * HS, dtype=torch.bfloat16, device=DEV)
        with torch.no_grad():
            x = (mod.hc_norm(hin) if mod.config.hc_per_branch_norm
                 else mod.hc_norm(hin.unflatten(-1, (hc, HS))).flatten(-2)).contiguous()
            ok = H._khc_mix_ok(x, wd, wu)
            fused = H._khc_fused_mix(x, wd, wu, hc, HS)
            fused2 = H._khc_fused_mix(x, wd, wu, hc, HS)
            comp = mod._mix_compute(x, wd, wu, hc, HS).to(torch.bfloat16)
        torch.cuda.synchronize()
        ref = fp32_ref(x, wd, wu, hc)
        scale = ref.abs().max().item()
        e_f = (fused.float() - ref).abs().max().item() / scale
        e_c = (comp.float() - ref).abs().max().item() / scale
        d_fc = (fused.float() - comp.float()).abs().max().item() / scale
        eq = (fused == comp).float().mean().item()
        det = bool(torch.equal(fused, fused2))
        emit(kind="accuracy", hc=hc, weights=label, m=m, mix_ok=ok, fused_err_vs_fp32=round(e_f, 5),
             compiled_err_vs_fp32=round(e_c, 5), fused_vs_compiled=round(d_fc, 5), bitwise_equal=round(eq, 4),
             deterministic=det)
        # 1 bf16 ulp at the output scale is ~0.4% of max; fused must be no worse than ~2x the compiled chain's error
        if not ok or not det or e_f > max(2 * e_c, 0.01):
            FAIL.append(("accuracy", hc, m))


def check_graph(H, wd, wu, hc):
    m = 40
    x = torch.randn(m, hc * HS, dtype=torch.bfloat16, device=DEV)
    out = {}
    s = torch.cuda.Stream()
    s.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(s):
        H._khc_fused_mix(x, wd, wu, hc, HS)
    torch.cuda.current_stream().wait_stream(s)
    torch.cuda.synchronize()
    g = torch.cuda.CUDAGraph()
    with torch.cuda.graph(g):
        out["y"] = H._khc_fused_mix(x, wd, wu, hc, HS)
    ok = True
    for _ in range(3):
        x.copy_(torch.randn_like(x))
        g.replay()
        torch.cuda.synchronize()
        ok &= bool(torch.equal(out["y"], H._khc_fused_mix(x, wd, wu, hc, HS)))
    emit(kind="graph_replay", hc=hc, ok=ok)
    if not ok:
        FAIL.append(("graph", hc))


def check_dispatch(H, mod, hc):
    import sglang.srt.layers.hc_mix_triton as HT
    seen = []
    real_f, real_p = H._khc_fused_mix, H.fused_hc_mix
    H._khc_fused_mix = lambda *a, **k: (seen.append("khc"), real_f(*a, **k))[1]
    H.fused_hc_mix = lambda *a, **k: (seen.append("persistent"), real_p(*a, **k))[1]
    try:
        for m, want in ((16, "persistent"), (17, "khc"), (40, "khc"), (64, "khc"), (65, "compiled")):
            seen.clear()
            hin = torch.randn(m, hc * HS, dtype=torch.bfloat16, device=DEV)
            with torch.no_grad():
                mod.mix(hin)
            got = seen[0] if seen else "compiled"
            emit(kind="dispatch", hc=hc, m=m, path=got, expected=want,
                 persistent_enabled=bool(HT._FUSED_MIX_MAX_ROWS >= 16))
            if got != want and not (want == "persistent" and got == "compiled"):
                FAIL.append(("dispatch", m, got))
    finally:
        H._khc_fused_mix, H.fused_hc_mix = real_f, real_p


def check_timing(H, mod, wd, wu, hc):
    per_copy = (wd.numel() + wu.numel()) * 2
    R = max(16, int(3 * 128e6 / per_copy) + 1)
    wds = [wd.clone() for _ in range(R)]
    wus = [wu.clone() for _ in range(R)]
    for m in (24, 32, 40, 48, 52, 64):
        xs = [torch.randn(m, hc * HS, dtype=torch.bfloat16, device=DEV) for _ in range(R)]
        with torch.no_grad():
            tc = graph_time([lambda i=i: mod._mix_compute(xs[i], wds[i], wus[i], hc, HS) for i in range(R)])
            tf = graph_time([lambda i=i: H._khc_fused_mix(xs[i], wds[i], wus[i], hc, HS) for i in range(R)])
        emit(kind="timing_cold", hc=hc, m=m, R=R, compiled_us=round(tc, 2), fused_us=round(tf, 2),
             saving_us=round(tc - tf, 2), weight_GBps_fused=round(per_copy / tf / 1e3))
        del xs
    del wds, wus
    torch.cuda.empty_cache()


def main():
    try:
        wd, wu, wn = real_weights()
        emit(kind="weights", down=list(wd.shape), up=list(wu.shape), norm=list(wn.shape))
        H, mod = make_module(HC, wd, wu, wn)
        emit(kind="config", mix_max_rows=H._KHC_MIX_MAX_ROWS, slices=H._KHC_MIX_S)
        for f in (lambda: check_accuracy(H, mod, HC, wd, wu, "real"), lambda: check_graph(H, wd, wu, HC),
                  lambda: check_dispatch(H, mod, HC), lambda: check_timing(H, mod, wd, wu, HC)):
            try:
                f()
            except Exception as e:
                import traceback
                emit(kind="error", err=repr(e)[:400], tb=traceback.format_exc()[-1500:])
                FAIL.append(("exception",))
        # MTP layout: hc = 5 (K = 12800), synthetic weights at the real scale
        hc5 = HC + 1
        wd5 = (torch.randn(LR, hc5 * HS, device=DEV) * wd.float().std()).to(torch.bfloat16)
        wu5 = (torch.randn(hc5 * HS, LR, device=DEV) * wu.float().std()).to(torch.bfloat16)
        wn5 = torch.cat([wn, wn[:HS]]) if wn.numel() == HC * HS else wn
        H5, mod5 = make_module(hc5, wd5, wu5, wn5)
        check_accuracy(H5, mod5, hc5, wd5, wu5, "synthetic")
    except Exception as e:
        import traceback
        emit(kind="error", err=repr(e)[:400], tb=traceback.format_exc()[-2000:])
        FAIL.append(("fatal",))
    emit(verdict="PASS" if not FAIL else "FAIL", fails=FAIL[:20])


if __name__ == "__main__":
    main()
