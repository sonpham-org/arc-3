"""khc patch-set check in the PATCHED install (4-Oct-2026, Kernel optimizations thread). Pre-server script, free GPU.

khc raises his split HyperConnection combine cap (hyperconnection.py) from 32 to 64 rows. kfast's 3-Oct check found no
gain at 52 rows (single 4.13 vs split 4.26 us), but timed L2-WARM buffers (64 x 0.8 MB residuals); in the server the
combine reads data the MoE layer just evicted and takes ~6.4 us. Here:
1. dispatch: the patched GatedResidual.combine takes the split path at 40 rows (call counter), partials buffer sized
   for 64 rows on first use, and its output is bitwise equal to his single-CTA kernel at every row count;
2. timing, single vs split, WARM (kfast's method) and COLD (distinct buffers > 3x L2 per graph walk) at 10..64 rows.
One JSON line per result; last line {"verdict": ...}.
"""
import json
import time

import torch

DEV = torch.device("cuda")
T0 = time.time()
FAIL = []
HC, HS = 4, 2560


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


def check_dispatch():
    import sglang.srt.layers.hyperconnection as H
    from sglang.kernels.ops.elementwise import hc_combine as HCmod
    assert hasattr(H, "_KHC_SPLIT_MAX_ROWS"), "patched hyperconnection.py not installed"
    calls = {"split": 0}
    real_split = HCmod.hc_combine_split

    def counting(*a, **k):
        calls["split"] += 1
        return real_split(*a, **k)

    HCmod.hc_combine_split = counting
    try:
        cfg = H.HyperConnectionConfig(hc_count=HC, hidden_size=HS, params_dtype=torch.bfloat16, hc_lowrank=320)
        mod = H.GatedResidual(cfg, use_mix=False, use_combine=True)
        with torch.no_grad():
            mod.block_inject_weight.weight.normal_(0, 0.02)
        emit(kind="dispatch_setup", jit_combine_ok=mod._jit_combine_ok, split_combine_ok=mod._split_combine_ok,
             cap=H._KHC_SPLIT_MAX_ROWS)
        for m in (10, 40, 64, 10, 52, 65):   # 10 after 40/64 must not shrink or move the buffer
            y = torch.randn(m, HS, dtype=torch.bfloat16, device=DEV)
            r = torch.randn(m, HC * HS, dtype=torch.bfloat16, device=DEV)
            nr = torch.randn(m, HC * HS, dtype=torch.bfloat16, device=DEV)
            before = calls["split"]
            with torch.no_grad():
                out = mod.combine(y, (r, nr))
                ref = HCmod.hc_combine(y, r, nr, mod.block_inject_weight.weight, HC, HS)
            torch.cuda.synchronize()
            buf = HCmod._partials_cache.get((r.device, HC))
            used_split = calls["split"] > before
            eq = bool(torch.equal(out, ref))
            emit(kind="dispatch", m=m, used_split=used_split, bitwise_equal_to_single=eq,
                 partials_rows=None if buf is None else int(buf.shape[0]), partials_ptr=None if buf is None else buf.data_ptr())
            if not eq or used_split != (m <= H._KHC_SPLIT_MAX_ROWS):
                FAIL.append(("dispatch", m))
    finally:
        HCmod.hc_combine_split = real_split


def check_timing():
    from sglang.kernels.ops.elementwise import hc_combine as HC_
    w = torch.randn(HC, HC * HS, dtype=torch.bfloat16, device=DEV) * 0.02
    for m in (10, 32, 36, 40, 44, 48, 52, 64):
        per_call = (m * HC * HS * 2) * 3 + m * HS * 2           # r + nr + out + y bytes
        for mode, R in (("warm", 64), ("cold", max(64, int(3 * 128e6 / per_call) + 1))):
            ys = [torch.randn(m, HS, dtype=torch.bfloat16, device=DEV) for _ in range(R)] if mode == "cold" else \
                [torch.randn(m, HS, dtype=torch.bfloat16, device=DEV)] * R
            rs = [torch.randn(m, HC * HS, dtype=torch.bfloat16, device=DEV) for _ in range(R)]
            ns = [torch.randn(m, HC * HS, dtype=torch.bfloat16, device=DEV) for _ in range(R)] if mode == "cold" else \
                [torch.randn(m, HC * HS, dtype=torch.bfloat16, device=DEV)] * R
            outs = [torch.empty(m, HC * HS, dtype=torch.bfloat16, device=DEV) for _ in range(R)] if mode == "cold" \
                else [None] * R
            ta = graph_time([lambda i=i: HC_.hc_combine(ys[i], rs[i], ns[i], w, HC, HS, out=outs[i]) for i in range(R)])
            tb = graph_time([lambda i=i: HC_.hc_combine_split(ys[i], rs[i], ns[i], w, HC, HS, out=outs[i])
                             for i in range(R)])
            a = HC_.hc_combine(ys[0], rs[0], ns[0], w, HC, HS)
            b = HC_.hc_combine_split(ys[0], rs[0], ns[0], w, HC, HS)
            emit(kind="hc_combine_time", m=m, mode=mode, R=R, single_us=round(ta, 2), split_us=round(tb, 2),
                 saving_us=round(ta - tb, 2), bitwise_equal=bool(torch.equal(a, b)))
            if not torch.equal(a, b):
                FAIL.append(("timing_equal", m, mode))
            del ys, rs, ns, outs
            torch.cuda.empty_cache()


def main():
    for f in (check_dispatch, check_timing):
        try:
            f()
        except Exception as e:
            import traceback
            emit(kind="error", where=f.__name__, err=repr(e)[:400], tb=traceback.format_exc()[-1500:])
            FAIL.append((f.__name__, "exception"))
    emit(verdict="PASS" if not FAIL else "FAIL", fails=FAIL[:20])


if __name__ == "__main__":
    main()
