"""Tactic sweep for the khc fused HC mix (4-Oct-2026, Kernel optimizations thread). Pre-server script, free GPU.
Needs check_khcmix.py as a --pre-file (helpers). At 40 (and 48) rows, COLD weights (R copies > 3x L2):
  references: cuBLAS down (F.linear x @ W_down^T), cuBLAS up (F.linear t @ W_up^T), the full compiled chain
  sweeps: our down kernel (S, BLOCK_N, BLOCK_K, warps, stages), reduce (S), up kernel (BLOCK_J, BLOCK_R, warps, stages)
  best combination end to end + bitwise check vs the compiled chain.
Emits the reference numbers, the top 6 per stage, and the best full; last line {"verdict": ...}.
"""
import itertools
import json
import time

import torch
import torch.nn.functional as F

import check_khcmix as C

DEV = C.DEV
T0 = time.time()


def emit(**kw):
    kw["t"] = round(time.time() - T0, 1)
    print(json.dumps(kw), flush=True)


def main():
    wd, wu, wn = C.real_weights()
    H, mod = C.make_module(C.HC, wd, wu, wn)
    hc, hs = C.HC, C.HS
    per_copy = (wd.numel() + wu.numel()) * 2
    R = max(16, int(3 * 128e6 / per_copy) + 1)
    wds = [wd.clone() for _ in range(R)]
    wus = [wu.clone() for _ in range(R)]
    K = wd.shape[1]
    for m in (40, 48):
        xs = [torch.randn(m, hc * hs, dtype=torch.bfloat16, device=DEV) for _ in range(R)]
        ts = [torch.randn(m, wd.shape[0], dtype=torch.bfloat16, device=DEV) for _ in range(R)]
        with torch.no_grad():
            ref = dict(
                cublas_down=C.graph_time([lambda i=i: F.linear(xs[i], wds[i]) for i in range(R)]),
                cublas_up=C.graph_time([lambda i=i: F.linear(ts[i], wus[i]) for i in range(R)]),
                compiled_chain=C.graph_time([lambda i=i: mod._mix_compute(xs[i], wds[i], wus[i], hc, hs)
                                             for i in range(R)]))
        emit(kind="reference", m=m, **{k: round(v, 2) for k, v in ref.items()})

        def tm(tac):
            try:
                return C.graph_time([lambda i=i: H._khc_fused_mix(xs[i], wds[i], wus[i], hc, hs, tac) for i in range(R)])
            except Exception as e:  # out of resources etc.
                return float("inf")

        down = []
        for S, bn, bk, w, st in itertools.product((10, 20, 40, 80), (32, 64), (64, 128, 256), (4, 8), (2, 3, 4)):
            if (K // S) % bk or K % S:
                continue
            tac = dict(stage="down", S=S, BLOCK_N=bn, BLOCK_K=bk, down_warps=w, down_stages=st)
            down.append((tm(tac), tac))
        red = {}
        for S in (10, 20, 40, 80):
            red[S] = tm(dict(stage="reduce", S=S))
        emit(kind="reduce", m=m, us_by_S={str(S): round(us, 2) for S, us in red.items()})
        down.sort(key=lambda z: z[0] + red[z[1]["S"]])   # pick by down + its reduce
        for us, tac in down[:6]:
            emit(kind="down", m=m, us=round(us, 2), with_reduce_us=round(us + red[tac["S"]], 2), tactic=tac)
        best_down = down[0][1]
        up = []
        for u4, bj, br, w, st in itertools.product((True, False), (16, 32), (32, 64, 128), (2, 4, 8), (2, 3, 4)):
            tac = dict(stage="up", up4=u4, BLOCK_J=bj, BLOCK_R=br, up_warps=w, up_stages=st)
            up.append((tm(tac), tac))
        up.sort(key=lambda z: z[0])
        for us, tac in up[:6]:
            emit(kind="up", m=m, us=round(us, 2), tactic=tac)
        full = {k: v for k, v in best_down.items() if k != "stage"}
        full.update({k: v for k, v in up[0][1].items() if k != "stage"})
        full_us = tm(full)
        x = xs[0]
        with torch.no_grad():
            a = H._khc_fused_mix(x, wd, wu, hc, hs, full)
            b = mod._mix_compute(x, wd, wu, hc, hs).to(torch.bfloat16)
        emit(kind="best_full", m=m, us=round(full_us, 2), compiled_us=round(ref["compiled_chain"], 2),
             saving_us=round(ref["compiled_chain"] - full_us, 2), bitwise_equal=round((a == b).float().mean().item(), 4),
             tactic=full)
        del xs, ts
    emit(verdict="PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        emit(kind="error", err=repr(e)[:400], tb=traceback.format_exc()[-1800:])
        emit(verdict="FAIL")
