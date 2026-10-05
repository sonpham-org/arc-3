"""HyperConnection mix micro-benchmark + closeness check (3-Oct-2026, daniel-draft kfuse). Pre-server script.

Reference: his GatedResidual._mix_compute under torch.compile (what a 13-lane verify runs today). Candidate:
hc_mix_fused (kfast skinny down GEMM + one up/epilogue kernel). Cold weights: 64 (down, up) pairs = 840 MB in one
CUDA graph. M = 52 (verify), 40, 26, 13. Checks: max/mean abs diff vs the compiled chain and vs an fp32 reference,
determinism, graph replay.
"""
import json
import os
import sys
import time
import traceback

import torch
import torch.nn.functional as F

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hc_mix_fused import hc_mix_fused  # noqa: E402

DEV = torch.device("cuda")
T0 = time.time()
HC, HS, LR = 4, 2560, 320


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
    g.replay(); g.replay()
    torch.cuda.synchronize()
    e0, e1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
    e0.record()
    for _ in range(reps):
        g.replay()
    e1.record()
    torch.cuda.synchronize()
    del g
    return e0.elapsed_time(e1) * 1e3 / (reps * len(fns))


def main():
    import sglang.kernels.ops.gemm.sm120_lowm_bf16_gemm as L  # patched by kfast: _skinny_gemm

    def _mix_compute(xn, wd, wu, hc, hs):
        t = F.silu(F.linear(xn, wd) / hc)
        t = torch.sigmoid(F.linear(t, wu)).unflatten(-1, (hc, hs))
        return (t * xn.unflatten(-1, (hc, hs))).mean(dim=-2)

    comp = torch.compile(_mix_compute)
    R = 64
    gen = torch.Generator(device=DEV).manual_seed(0)
    Wd = (torch.randn(R, LR, HC * HS, device=DEV, generator=gen) * 0.01).bfloat16()
    Wu = (torch.randn(R, HC * HS, LR, device=DEV, generator=gen) * 0.05).bfloat16()
    fails = []
    for m in (52, 40, 26, 13):
        x = torch.randn(m, HC * HS, device=DEV, generator=gen).bfloat16()
        ref = comp(x, Wd[0], Wu[0], HC, HS).to(torch.bfloat16)
        exact = _mix_compute(x.float(), Wd[0].float(), Wu[0].float(), HC, HS)
        t_comp = graph_time([lambda r=r: comp(x, Wd[r], Wu[r], HC, HS) for r in range(R)])
        emit(kind="hc_ref", m=m, compiled_us=round(t_comp, 2),
             compiled_vs_fp32=round((ref.float() - exact).abs().max().item(), 5))
        best = None
        for dn in ((16, 128, 16, 4, 3), (16, 128, 20, 4, 3), (16, 256, 10, 4, 3), (32, 128, 10, 4, 3),
                   (16, 128, 8, 4, 3), (32, 128, 8, 8, 4)):
            for bj, br, w, st in ((16, 64, 4, 2), (16, 32, 4, 2), (32, 64, 4, 2), (16, 64, 8, 2), (16, 64, 4, 3),
                                  (16, 160, 4, 1)):
                if 320 % br:
                    continue
                down = lambda a, b, dn=dn: L._skinny_gemm(a, b, *dn)  # noqa: E731
                try:
                    o = hc_mix_fused(x, Wd[0], Wu[0], HC, HS, down, bj, br, w, st)
                    o2 = hc_mix_fused(x, Wd[0], Wu[0], HC, HS, down, bj, br, w, st)
                    torch.cuda.synchronize()
                    us = graph_time([lambda r=r: hc_mix_fused(x, Wd[r], Wu[r], HC, HS, down, bj, br, w, st)
                                     for r in range(R)])
                    row = dict(kind="hc_fused", m=m, down=dn, up=(bj, br, w, st), us=round(us, 2),
                               compiled_us=round(t_comp, 2),
                               max_diff_vs_compiled=round((o.float() - ref.float()).abs().max().item(), 5),
                               mean_diff_vs_compiled=round((o.float() - ref.float()).abs().mean().item(), 7),
                               fused_vs_fp32=round((o.float() - exact).abs().max().item(), 5),
                               deterministic=bool(torch.equal(o, o2)))
                    emit(**row)
                    if not row["deterministic"] or row["fused_vs_fp32"] > 2 * (ref.float() - exact).abs().max().item() + 0.01:
                        fails.append((m, dn, (bj, br, w, st)))
                    if best is None or us < best[0]:
                        best = (us, dn, (bj, br, w, st))
                except Exception:
                    emit(kind="error", m=m, down=dn, up=(bj, br, w, st), tb=traceback.format_exc()[-1500:])
        emit(kind="hc_best", m=m, compiled_us=round(t_comp, 2), best_us=round(best[0], 2) if best else None,
             best_down=best[1] if best else None, best_up=best[2] if best else None)
    emit(verdict="PASS" if not fails else "FAIL", fails=fails[:10])


if __name__ == "__main__":
    try:
        main()
    except Exception:
        emit(kind="fatal", tb=traceback.format_exc()[-4000:])
