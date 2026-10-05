"""kfast patch-set check in the PATCHED install (3-Oct-2026, daniel-draft kernels). Pre-server script, free GPU.

1. skinny GEMM (patched sglang/kernels/ops/gemm/sm120_lowm_bf16_gemm.py) on every tuned shape at m = 9..64:
   error vs an fp32 reference, bitwise share vs cuBLAS, run-to-run determinism, CUDA-graph replay with fresh inputs
   (split-K counters must reset), two shapes concurrently on two streams inside one graph (router gate + shared
   expert, as the model runs them); cold-weight CUDA-graph timing old path (cuBLAS for m > 32, his generic Triton
   tactic for m <= 32) vs new.
2. hc_combine: one-CTA-per-row kernel vs the split pair (patched: used up to 64 rows): time + max diff.
3. MoE top-k sum: sgl_kernel moe_sum_reduce(.., 1.0) vs JIT moe_topk_sum: time + bitwise equality.
One JSON line per result; last line {"verdict": ...}.
"""
import json
import math
import time
import traceback

import torch
import torch.nn.functional as F

DEV = torch.device("cuda")
T0 = time.time()
FAIL = []


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


def check_skinny():
    import sglang.kernels.ops.gemm.sm120_lowm_bf16_gemm as L
    assert hasattr(L, "_skinny_tactic"), "patched module not installed"
    gen = torch.Generator(device=DEV).manual_seed(1)
    for (n, k), _t in L._SKINNY_TACTICS.items():
        R = max(2, min(128, math.ceil(1.0e9 / (n * k * 2))))
        W = torch.empty((R, n, k), dtype=torch.bfloat16, device=DEV).normal_(0, 0.02, generator=gen)
        for m in (13, 40, 50, 52, 60, 64, 65, 70, 78, 80, 96, 128):
            row = {"n": n, "k": k, "m": m, "tactic": L._skinny_tactic(m, n, k), "dispatch": L.use_sm120_lowm_bf16_gemm(m, n, k)}
            if row["tactic"] is None and m > 32:
                continue  # production keeps cuBLAS here
            x = torch.randn(m, k, dtype=torch.bfloat16, device=DEV, generator=gen)
            ref = x.float() @ W[0].float().T
            y = L.sm120_lowm_bf16_gemm(x, W[0])
            y2 = L.sm120_lowm_bf16_gemm(x, W[0])
            cb = F.linear(x, W[0])
            torch.cuda.synchronize()
            row["rel_err"] = round(((y.float() - ref).abs().max() / ref.abs().max()).item(), 5)
            row["cublas_rel_err"] = round(((cb.float() - ref).abs().max() / ref.abs().max()).item(), 5)
            row["bitwise_vs_cublas"] = round((y == cb).float().mean().item(), 4)
            row["deterministic"] = bool(torch.equal(y, y2))
            # graph replay with fresh inputs
            xs = torch.zeros_like(x)
            g = torch.cuda.CUDAGraph()
            s = torch.cuda.Stream(); s.wait_stream(torch.cuda.current_stream())
            with torch.cuda.stream(s):
                L.sm120_lowm_bf16_gemm(xs, W[0])
            torch.cuda.current_stream().wait_stream(s)
            with torch.cuda.graph(g):
                yo = L.sm120_lowm_bf16_gemm(xs, W[0])
            ok = True
            for _ in range(3):
                xn = torch.randn(m, k, dtype=torch.bfloat16, device=DEV, generator=gen)
                xs.copy_(xn); g.replay(); torch.cuda.synchronize()
                ok &= bool(torch.equal(yo, L.sm120_lowm_bf16_gemm(xn, W[0])))
            row["graph_replay_ok"] = ok
            del g
            if row["rel_err"] > 2 * row["cublas_rel_err"] + 1e-3 or not row["deterministic"] or not ok:
                FAIL.append(("skinny", n, k, m))
            if m in (40, 50, 60, 70, 80, 96, 128):
                L._SKINNY_ON = False
                old = graph_time([lambda r=r: L.sm120_lowm_bf16_gemm(x, W[r]) if L.use_sm120_lowm_bf16_gemm(m, n, k)
                                  else F.linear(x, W[r]) for r in range(R)])
                L._SKINNY_ON = True
                new = graph_time([lambda r=r: L.sm120_lowm_bf16_gemm(x, W[r]) for r in range(R)])
                row.update(old_us=round(old, 2), new_us=round(new, 2), gbps_new=round(n * k * 2 / new / 1e3))
            emit(kind="skinny", **row)
        del W
        torch.cuda.empty_cache()
    # two shapes concurrently on two streams in one graph (router gate || shared expert gate_up), m = 52
    m = 52
    xr = torch.randn(m, 2560, dtype=torch.bfloat16, device=DEV)
    wg = torch.randn(512, 2560, dtype=torch.bfloat16, device=DEV) * 0.02
    wu = torch.randn(1280, 2560, dtype=torch.bfloat16, device=DEV) * 0.02
    side = torch.cuda.Stream()
    ref_g, ref_u = L.sm120_lowm_bf16_gemm(xr, wg), L.sm120_lowm_bf16_gemm(xr, wu)
    g = torch.cuda.CUDAGraph()
    with torch.cuda.graph(g):
        side.wait_stream(torch.cuda.current_stream())
        with torch.cuda.stream(side):
            og = [L.sm120_lowm_bf16_gemm(xr, wg) for _ in range(8)]
        ou = [L.sm120_lowm_bf16_gemm(xr, wu) for _ in range(8)]
        torch.cuda.current_stream().wait_stream(side)
    ok = True
    for _ in range(5):
        g.replay(); torch.cuda.synchronize()
        ok &= all(torch.equal(o, ref_g) for o in og) and all(torch.equal(o, ref_u) for o in ou)
    emit(kind="skinny_two_streams", ok=ok)
    if not ok:
        FAIL.append(("two_streams",))


def check_combine():
    from sglang.kernels.ops.elementwise import hc_combine as HC
    hc, hs = 4, 2560
    for m in (13, 40, 52, 64):
        y = torch.randn(m, hs, dtype=torch.bfloat16, device=DEV)
        r = torch.randn(m, hc * hs, dtype=torch.bfloat16, device=DEV)
        nr = torch.randn(m, hc * hs, dtype=torch.bfloat16, device=DEV)
        w = torch.randn(hc, hc * hs, dtype=torch.bfloat16, device=DEV) * 0.02
        a = HC.hc_combine(y, r, nr, w, hc, hs)
        b = HC.hc_combine_split(y, r, nr, w, hc, hs)
        torch.cuda.synchronize()
        ref = (r.float().unflatten(-1, (hc, hs)) + y.float().unsqueeze(-2) *
               (2 * torch.sigmoid((nr.float() @ w.float().T) / hc)).unsqueeze(-1)).flatten(-2)
        R = 64
        rs = [torch.randn(m, hc * hs, dtype=torch.bfloat16, device=DEV) for _ in range(R)]
        ta = graph_time([lambda i=i: HC.hc_combine(y, rs[i], nr, w, hc, hs) for i in range(R)])
        tb = graph_time([lambda i=i: HC.hc_combine_split(y, rs[i], nr, w, hc, hs) for i in range(R)])
        emit(kind="hc_combine", m=m, single_us=round(ta, 2), split_us=round(tb, 2),
             bitwise_equal=round((a == b).float().mean().item(), 4),
             max_diff_vs_ref_single=round((a.float() - ref).abs().max().item(), 4),
             max_diff_vs_ref_split=round((b.float() - ref).abs().max().item(), 4))


def check_topk_sum():
    from sgl_kernel import moe_sum_reduce
    from sglang.kernels.ops.moe.moe_topk_sum import moe_topk_sum
    for m in (13, 40, 52):
        x = (torch.randn(m, 10, 2560, device=DEV) * 0.3).bfloat16()
        a = torch.empty(m, 2560, dtype=torch.bfloat16, device=DEV)
        b = torch.empty_like(a)
        moe_sum_reduce(x, a, 1.0); moe_topk_sum(x, b); torch.cuda.synchronize()
        R = 64
        xs = [(torch.randn(m, 10, 2560, device=DEV) * 0.3).bfloat16() for _ in range(R)]
        ta = graph_time([lambda i=i: moe_sum_reduce(xs[i], a, 1.0) for i in range(R)])
        tb = graph_time([lambda i=i: moe_topk_sum(xs[i], b) for i in range(R)])
        eq = bool(torch.equal(a, b))
        emit(kind="topk_sum", m=m, moe_sum_reduce_us=round(ta, 2), moe_topk_sum_us=round(tb, 2), bitwise_equal=eq,
             max_diff=round((a.float() - b.float()).abs().max().item(), 6))
        if not eq:
            FAIL.append(("topk_sum", m))


def main():
    emit(kind="env", gpu=torch.cuda.get_device_name(0))
    for f in (check_skinny, check_combine, check_topk_sum):
        try:
            f()
        except Exception:
            FAIL.append((f.__name__, "exception"))
            emit(kind="error", where=f.__name__, tb=traceback.format_exc()[-2500:])
    emit(verdict="PASS" if not FAIL else "FAIL", fails=FAIL)


if __name__ == "__main__":
    main()
