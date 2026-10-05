"""kconv patch-set check in the PATCHED install (4-Oct-2026, daniel-draft kernels). Pre-server script, free GPU.

causal_conv1d_update, target-verify chain case (his GDN verify call: x (bs, dim, W) token-major, conv_state pool
(lines, dim, 3) with dim stride 1, conv_state_indices, intermediate_conv_window (lines, W, dim, 3), out= a persistent
token-major buffer, SiLU, no bias, no eagle tree): his kernel (module flag _KCONV_ON = False) vs the kconv kernel at
several channel blocks. Bitwise equality of out, the rolled conv states and the intermediate windows (and untouched
rows untouched), a PAD slot row, out=None, CUDA-graph replay with fresh inputs; time per call in a CUDA graph over 36
layer copies (as the 36 GDN layers of one verify). One JSON line per result; last line {"verdict": ...}.
"""
import json
import time
import traceback

import torch

DEV = torch.device("cuda")
T0 = time.time()
FAIL = []
DIM, WIDTH, LINES = 10240, 4, 64


def emit(**kw):
    kw["t"] = round(time.time() - T0, 1)
    print(json.dumps(kw), flush=True)


def make(bs, W, seed, pad_row=None, layers=1, layout="server"):
    """layout "server": his pools as served (memory_pool.py): conv state (lines, dim, 3) contiguous and the
    deduplicated sliding-window intermediate (phys (lines, dim, W + 2), as_strided view (lines, W, dim, 3) with
    step stride = win stride = 1). layout "dense": conv state dim-stride 1, dense (lines, W, dim, 3) windows."""
    g = torch.Generator(device=DEV).manual_seed(seed)
    out = []
    for _ in range(layers):
        x_tm = torch.randn((bs, W, DIM), generator=g, device=DEV).to(torch.bfloat16)  # token-major like mixed_qkv
        x = x_tm.transpose(1, 2)  # (bs, dim, W), stride_x_token = dim
        w = (torch.randn((DIM, WIDTH), generator=g, device=DEV) * 0.5).to(torch.bfloat16)
        if layout == "server":
            cs = torch.randn((LINES, DIM, WIDTH - 1), generator=g, device=DEV).to(torch.bfloat16)
            phys = torch.randn((LINES, DIM, W + WIDTH - 2), generator=g, device=DEV).to(torch.bfloat16)
        else:
            cs = torch.randn((LINES, WIDTH - 1, DIM), generator=g, device=DEV).to(torch.bfloat16).transpose(1, 2)
            phys = torch.randn((LINES, W, DIM, WIDTH - 1), generator=g, device=DEV).to(torch.bfloat16)
        perm = torch.randperm(LINES - 1, generator=g, device=DEV)[: 2 * bs] + 1
        csi = perm[:bs].to(torch.int32)
        isi = perm[bs:].to(torch.int32)
        if pad_row is not None:
            csi[pad_row] = -1
        pbuf = torch.empty((LINES, W, DIM), dtype=torch.bfloat16, device=DEV)
        out.append(dict(x=x, w=w, cs=cs, phys=phys, layout=layout, W=W, csi=csi, isi=isi, pbuf=pbuf))
    return out


def icw(d):
    p = d["phys"]
    if d["layout"] == "server":
        return p.as_strided((p.shape[0], d["W"], DIM, WIDTH - 1), (p.stride(0), 1, p.stride(1), 1))
    return p


def run(C, d, on, bn=None, use_out=True):
    C._KCONV_ON = on
    if bn:
        C._KCONV_BLOCK_N = bn
    bs = d["x"].shape[0]
    return C.causal_conv1d_update(d["x"], d["cs"], d["w"], None, "silu", conv_state_indices=d["csi"],
                                  intermediate_conv_window=icw(d), intermediate_state_indices=d["isi"],
                                  out=d["pbuf"][:bs].transpose(1, 2) if use_out else None)


def clone(d):
    e = dict(d)
    for k in ("cs", "phys"):
        e[k] = d[k].clone()
    e["pbuf"] = torch.zeros_like(d["pbuf"])
    return e


def exact(C, bs, W, bn, pad_row=None, use_out=True, seed=1, layout="server"):
    d = make(bs, W, seed, pad_row, layout=layout)[0]
    a, b = clone(d), clone(d)
    oa = run(C, a, False, use_out=use_out).clone()
    ob = run(C, b, True, bn, use_out=use_out).clone()
    torch.cuda.synchronize()
    res = dict(out=torch.equal(oa, ob), conv_state=torch.equal(a["cs"], b["cs"]), inter=torch.equal(a["phys"], b["phys"]),
               out_maxdiff=float((oa.float() - ob.float()).abs().max()))
    ok = res["out"] and res["conv_state"] and res["inter"]
    emit(kind="exact", layout=layout, bs=bs, W=W, block_n=bn, pad_row=pad_row, out_arg=use_out, ok=ok, **res)
    if not ok:
        FAIL.append(("exact", layout, bs, W, bn, pad_row, use_out))


def graph_replay(C, bs, W, bn):
    """Capture once on static buffers, replay with fresh inputs: equal to eager his-kernel results each time."""
    d = make(bs, W, 7)[0]
    C._KCONV_ON = True
    C._KCONV_BLOCK_N = bn
    for _ in range(2):
        run(C, clone(d), True, bn)
    s = torch.cuda.Stream()
    s.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(s):
        run(C, d, True, bn)
    torch.cuda.current_stream().wait_stream(s)
    torch.cuda.synchronize()
    gr = torch.cuda.CUDAGraph()
    with torch.cuda.graph(gr):
        o = run(C, d, True, bn)
    oks = []
    for seed in (11, 12, 13):
        f = make(bs, W, seed)[0]
        ref = clone(f)
        ro = run(C, ref, False).clone()
        for k in ("x", "w", "cs", "phys", "csi", "isi"):
            d[k].copy_(f[k])
        gr.replay()
        torch.cuda.synchronize()
        oks.append(bool(torch.equal(o, ro) and torch.equal(d["cs"], ref["cs"]) and torch.equal(d["phys"], ref["phys"])))
    emit(kind="graph_replay", bs=bs, W=W, block_n=bn, ok=all(oks), per_replay=oks)
    if not all(oks):
        FAIL.append(("graph", bs, W, bn))


def timing(C, bs, W, cfgs, reps=20, layout="server"):
    L = make(bs, W, 3, layers=36, layout=layout)
    res = {}
    for label, on, bn, warps in cfgs:
        C._KCONV_ON, C._KCONV_WARPS = on, warps
        if bn:
            C._KCONV_BLOCK_N = bn
        fns = [lambda d=d: run(C, d, on, bn) for d in L]
        for f in fns[:2]:
            f()
        torch.cuda.synchronize()
        s = torch.cuda.Stream()
        s.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(s):
            for f in fns[:2]:
                f()
        torch.cuda.current_stream().wait_stream(s)
        torch.cuda.synchronize()
        gr = torch.cuda.CUDAGraph()
        with torch.cuda.graph(gr):
            for f in fns:
                f()
        gr.replay()
        torch.cuda.synchronize()
        e0, e1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
        e0.record()
        for _ in range(reps):
            gr.replay()
        e1.record()
        torch.cuda.synchronize()
        res[label] = round(e0.elapsed_time(e1) * 1e3 / (reps * len(fns)), 2)
        del gr
    C._KCONV_WARPS = 4
    emit(kind="timing_us_per_call", layout=layout, bs=bs, W=W, **res)
    return res


def main():
    import sglang.kernels.ops.mamba.causal_conv1d_triton as C
    assert hasattr(C, "_kconv_update_chain_kernel"), "kconv not installed"
    emit(kind="env", gpu=torch.cuda.get_device_name(), torch=torch.__version__,
         triton=__import__("triton").__version__, default_block_n=C._KCONV_BLOCK_N, on=C._KCONV_ON)
    for layout in ("server", "dense"):
        for W in (2, 3, 4, 5, 8, 12, 16):
            for bn in (32, 64, 128, 256):
                try:
                    exact(C, 10, W, bn, layout=layout)
                except Exception:
                    FAIL.append(("exact-crash", layout, W, bn))
                    emit(kind="error", where=f"exact {layout} W{W} bn{bn}", tb=traceback.format_exc()[-3000:])
    for args in ((10, 8, 64, 3, True), (10, 4, 64, None, False), (1, 8, 64, None, True), (7, 16, 128, 0, True)):
        try:
            exact(C, args[0], args[1], args[2], pad_row=args[3], use_out=args[4], seed=5)
        except Exception:
            FAIL.append(("exact-crash", args))
            emit(kind="error", where=f"exact {args}", tb=traceback.format_exc()[-3000:])
    for W in (4, 8, 16):
        try:
            graph_replay(C, 10, W, 64)
        except Exception:
            FAIL.append(("graph-crash", W))
            emit(kind="error", where=f"graph W{W}", tb=traceback.format_exc()[-3000:])
    best = {}
    for W in (4, 6, 8, 12, 16):
        cfgs = [("his", False, None, 4)] + [(f"k{bn}w{wp}", True, bn, wp) for bn in (32, 64, 128, 256) for wp in (1, 2, 4)]
        try:
            if W in (8, 16):
                timing(C, 10, W, cfgs[:1] + [c for c in cfgs if c[0] == "k64w4"], layout="dense")
            r = timing(C, 10, W, cfgs)
            k = min((v, k) for k, v in r.items() if k != "his")
            best[W] = dict(his=r["his"], best=k[1], best_us=k[0], k64w4=r.get("k64w4"))
        except Exception:
            emit(kind="error", where=f"timing W{W}", tb=traceback.format_exc()[-3000:])
    emit(kind="summary", best=best)
    emit(verdict="PASS" if not FAIL else "FAIL", failures=[str(f) for f in FAIL][:20])


if __name__ == "__main__":
    try:
        main()
    except Exception:
        emit(verdict="FAIL", error=traceback.format_exc()[-4000:])
