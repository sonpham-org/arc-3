"""Dense BF16 GEMM micro-benchmark on the real card (3-Oct-2026, daniel-draft kernels; Son: faster dense layers).

Runs in Daniel's venv on the free GPU (make_bench_notebook.py --pre-script). Every dense BF16 GEMM of one decode
verify step of Qwen3.8-Flash-Next (TP1), timed inside CUDA graphs with COLD weights (each graph walks R distinct
weight copies, >= 1 GB, so the 128 MB L2 cannot hold them; the server reads ~30 GB per step), at M = 13 / 40 / 52
token rows. Candidates: cuBLAS via F.linear (what his fork runs for M > 32), his sm120 low-M Triton GEMM (what it
runs for M <= 32; forced here at any M), and skinny_gemm.py (deterministic split-K) over a tactic sweep.
Also: a DRAM read-bandwidth reference, and the HyperConnection mix (his torch.compile chain vs his fused persistent
kernel at ROWS 64). Prints one JSON line per measurement and a summary line {"summary": ...}.
"""
import json
import math
import os
import sys
import time
import traceback

import torch
import torch.nn.functional as F
import triton
import triton.language as tl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skinny_gemm import skinny_gemm  # noqa: E402

DEV = torch.device("cuda")
T0 = time.time()
BUDGET_S = float(os.environ.get("DENSE_BUDGET_S", 1500))


def emit(**kw):
    kw["t"] = round(time.time() - T0, 1)
    print(json.dumps(kw), flush=True)


def graph_time(fns, reps=8, warm=2):
    """Capture fns (list of thunks) in one CUDA graph, replay; mean us per thunk."""
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
    for _ in range(warm):
        g.replay()
    torch.cuda.synchronize()
    e0, e1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
    e0.record()
    for _ in range(reps):
        g.replay()
    e1.record()
    torch.cuda.synchronize()
    us = e0.elapsed_time(e1) * 1e3 / (reps * len(fns))
    del g
    return us


# ---------------------------------------------------------------- DRAM read reference
@triton.jit
def _read_kernel(p, out, n, BLOCK: tl.constexpr):
    pid = tl.program_id(0)
    step = tl.num_programs(0) * BLOCK
    acc = tl.zeros([BLOCK], dtype=tl.float32)
    for i in range(pid * BLOCK, n, step):
        offs = i + tl.arange(0, BLOCK)
        acc += tl.load(p + offs, mask=offs < n, other=0.0, eviction_policy="evict_first").to(tl.float32)
    tl.store(out + pid, tl.sum(acc))


def bandwidth_ref():
    n = 1 << 30  # 2 GB of bf16
    buf = torch.empty(n, dtype=torch.bfloat16, device=DEV).normal_()
    sms = torch.cuda.get_device_properties(DEV).multi_processor_count
    res = {}
    for ctas_per_sm, block, warps in ((2, 4096, 8), (4, 4096, 8), (8, 2048, 4), (4, 8192, 8)):
        grid = sms * ctas_per_sm
        out = torch.empty(grid, dtype=torch.float32, device=DEV)
        f = lambda: _read_kernel[(grid,)](buf, out, n, BLOCK=block, num_warps=warps)  # noqa: E731
        us = graph_time([f], reps=10)
        res[f"triton_read_{ctas_per_sm}x{block}"] = round(2 * n / us / 1e3, 0)
    dst = torch.empty_like(buf)
    us = graph_time([lambda: dst.copy_(buf)], reps=10)
    res["torch_copy_rw"] = round(2 * 2 * n / us / 1e3, 0)
    us = graph_time([lambda: buf.sum()], reps=10)
    res["torch_sum"] = round(2 * n / us / 1e3, 0)
    del buf, dst
    torch.cuda.empty_cache()
    emit(kind="bandwidth_GBps", **res)
    return max(res.values())


# ---------------------------------------------------------------- shapes (TP1, from qwen3_5.py / qwen4_exp.py / config)
SHAPES = [  # name, N, K, calls per target verify step
    ("gdn_in_proj_qkvzba", 16480, 2560, 36),
    ("gdn_out_proj", 2560, 6144, 36),
    ("qsa_qkv_gate", 13312, 2560, 12),
    ("qsa_o_proj", 2560, 6144, 12),
    ("shared_gate_up", 1280, 2560, 48),
    ("shared_down", 2560, 640, 48),
    ("router_gate", 512, 2560, 48),
    ("hc_mix_down", 320, 10240, 96),
    ("hc_mix_up", 10240, 320, 96),
    ("draft_lm_head_hot64k", 65536, 2560, 3),
    ("lm_head", 248320, 2560, 1),
]
MS = [int(m) for m in os.environ.get("DENSE_MS", "52,40,13").split(",")]


def weights(N, K, total=1.0e9):
    wb = N * K * 2
    R = max(2, min(256, math.ceil(total / wb)))
    W = torch.empty((R, N, K), dtype=torch.bfloat16, device=DEV).normal_(0, 0.02)
    return W, R


def tactics(N, K, M):
    sms = 188
    out = []
    for bn in (32, 64, 128):
        for bk in ((64, 128) if M <= 64 else (32, 64)):
            if K % bk:
                continue
            nt = math.ceil(N / bn)
            for sp in (1, 2, 4, 5, 8, 10, 16, 20, 32):
                ctas = nt * sp
                if K % (sp * bk) or ctas > 6 * sms or (sp > 1 and nt >= 2 * sms):
                    continue
                out.append(dict(block_n=bn, block_k=bk, split=sp, warps=4, stages=3))
    return out


def run_gemms(bw_peak):
    only = os.environ.get('DENSE_SHAPES')
    shapes = [x for x in SHAPES if not only or x[0] in only.split(',')]
    from sglang.kernels.ops.gemm.sm120_lowm_bf16_gemm import sm120_lowm_bf16_gemm
    summary = {}
    for name, N, K, calls in shapes:
        if time.time() - T0 > BUDGET_S:
            emit(kind="skip", shape=name, why="budget")
            continue
        try:
            W, R = weights(N, K)
        except Exception as e:
            emit(kind="error", shape=name, err=repr(e)[:300]); continue
        wb = N * K * 2
        for M in MS:
            if time.time() - T0 > BUDGET_S:
                break
            x = torch.randn(M, K, dtype=torch.bfloat16, device=DEV)
            ref = (x.float() @ W[0].float().T)
            res = {}

            def timed(label, fn, tactic=None):
                try:
                    o = fn(x, W[0])
                    torch.cuda.synchronize()
                    err = ((o.float() - ref).abs().max() / ref.abs().max()).item()
                    us = graph_time([lambda r=r: fn(x, W[r]) for r in range(R)])
                    res[label] = dict(us=round(us, 2), gbps=round(wb / us / 1e3), err=round(err, 5), tactic=tactic)
                    return us
                except Exception as e:  # out of resources etc.
                    res[label] = dict(err_msg=repr(e)[:160], tactic=tactic)
                    return float("inf")

            timed("cublas", lambda a, b: F.linear(a, b))
            if wb <= 256e6:
                timed("lowm_daniel", lambda a, b: sm120_lowm_bf16_gemm(a, b))
            best = (float("inf"), None)
            if wb <= 256e6:
                for t in tactics(N, K, M):
                    us = timed("skinny " + json.dumps(t, sort_keys=True), lambda a, b, t=t: skinny_gemm(a, b, **t), t)
                    best = min(best, (us, json.dumps(t, sort_keys=True)), key=lambda z: z[0])
                if best[1] is not None:  # refine stages / warps around the best
                    b0 = json.loads(best[1])
                    for st, wp in ((2, 4), (4, 4), (5, 4), (3, 8), (4, 8)):
                        t = dict(b0, stages=st, warps=wp)
                        us = timed("skinny " + json.dumps(t, sort_keys=True), lambda a, b, t=t: skinny_gemm(a, b, **t), t)
                        best = min(best, (us, json.dumps(t, sort_keys=True)), key=lambda z: z[0])
            # bitwise agreement of the best skinny tactic with cuBLAS (fp-noise check)
            agree = None
            if best[1] is not None:
                t = json.loads(best[1])
                a = F.linear(x, W[0]); b = skinny_gemm(x, W[0], **t)
                agree = round((a == b).float().mean().item(), 4)
                # determinism: run twice
                b2 = skinny_gemm(x, W[0], **t)
                det = bool(torch.equal(b, b2))
            else:
                det = None
            cb = res.get("cublas", {}).get("us")
            lw = res.get("lowm_daniel", {}).get("us")
            row = dict(kind="gemm", shape=name, N=N, K=K, M=M, calls=calls, weight_MB=round(wb / 1e6, 1), R=R,
                       cublas_us=cb, lowm_us=lw, best_skinny_us=round(best[0], 2) if best[1] else None,
                       best_tactic=json.loads(best[1]) if best[1] else None,
                       cublas_GBps=round(wb / cb / 1e3) if cb else None,
                       skinny_GBps=round(wb / best[0] / 1e3) if best[1] else None,
                       peak_frac=round(wb / best[0] / 1e3 / bw_peak, 3) if best[1] else None,
                       skinny_vs_cublas_bitwise_equal=agree, skinny_deterministic=det)
            emit(**row)
            emit(kind="gemm_all", shape=name, M=M, results=res)
            summary[f"{name}@{M}"] = {k: row[k] for k in ("cublas_us", "lowm_us", "best_skinny_us", "best_tactic", "calls")}
            del x, ref
        del W
        torch.cuda.empty_cache()
    return summary


# ---------------------------------------------------------------- HyperConnection mix (whole op)
def run_hc_mix():
    from sglang.srt.layers.hc_mix_triton import _hc_mix_persistent_kernel, _get_counters

    def _mix_compute(xn, wd, wu, hc, hs):
        t = F.silu(F.linear(xn, wd) / hc)
        t = torch.sigmoid(F.linear(t, wu)).unflatten(-1, (hc, hs))
        return (t * xn.unflatten(-1, (hc, hs))).mean(dim=-2)

    comp = torch.compile(_mix_compute)
    hc, hs, lr = 4, 2560, 320
    R = 64
    Wd = torch.empty((R, lr, hc * hs), dtype=torch.bfloat16, device=DEV).normal_(0, 0.02)
    Wu = torch.empty((R, hc * hs, lr), dtype=torch.bfloat16, device=DEV).normal_(0, 0.02)
    sms = torch.cuda.get_device_properties(DEV).multi_processor_count
    out = {}
    for M in MS:
        x = torch.randn(M, hc * hs, dtype=torch.bfloat16, device=DEV)
        ref = _mix_compute(x.float(), Wd[0].float(), Wu[0].float(), hc, hs)
        res = {}
        try:
            o = comp(x, Wd[0], Wu[0], hc, hs).to(torch.bfloat16)
            res["compiled_err"] = round(((o.float() - ref).abs().max() / ref.abs().max()).item(), 5)
            res["compiled_us"] = round(graph_time([lambda r=r: comp(x, Wd[r], Wu[r], hc, hs) for r in range(R)]), 2)
        except Exception as e:
            res["compiled_err_msg"] = repr(e)[:300]

        def persistent(xx, wd, wu, rows_pad, bj=32, bk=256, warps=8):
            t_raw = torch.empty((rows_pad, lr), dtype=torch.float32, device=DEV)
            o = torch.empty((xx.shape[0], hs), dtype=torch.bfloat16, device=DEV)
            _hc_mix_persistent_kernel[(sms,)](xx, wd, wu, t_raw, o, _get_counters(DEV), wd, wu, hc * hs, lr, hs,
                                              xx.shape[0], sms, 1.0 / hc, ROWS=rows_pad, HC=hc, BLOCK_N=32,
                                              BLOCK_K=bk, BLOCK_J=bj, BLOCK_R=64, FP8_WEIGHT=False, num_warps=warps)
            return o
        rp = max(16, triton.next_power_of_2(M))
        for bj, bk, warps in ((32, 256, 8), (16, 128, 8), (32, 128, 4)):
            key = f"persistent_rows{rp}_bj{bj}_bk{bk}_w{warps}"
            try:
                o = persistent(x, Wd[0], Wu[0], rp, bj, bk, warps)
                res[key + "_err"] = round(((o.float() - ref).abs().max() / ref.abs().max()).item(), 5)
                res[key + "_us"] = round(graph_time([lambda r=r: persistent(x, Wd[r], Wu[r], rp, bj, bk, warps)
                                                     for r in range(R)]), 2)
            except Exception as e:
                res[key + "_err_msg"] = repr(e)[:300]
        emit(kind="hc_mix", M=M, weight_MB=round(2 * lr * hc * hs * 2 / 1e6, 1), **res)
        out[M] = res
    del Wd, Wu
    torch.cuda.empty_cache()
    return out


def main():
    emit(kind="env", gpu=torch.cuda.get_device_name(0), torch=torch.__version__, triton=triton.__version__,
         l2_MB=torch.cuda.get_device_properties(DEV).L2_cache_size / 2**20,
         sms=torch.cuda.get_device_properties(DEV).multi_processor_count, Ms=MS)
    summ = {}
    try:
        summ["bw_peak_GBps"] = bandwidth_ref()
    except Exception:
        emit(kind="error", where="bandwidth", tb=traceback.format_exc()[-1500:]); summ["bw_peak_GBps"] = 1700
    try:
        summ["hc_mix"] = run_hc_mix()
    except Exception:
        emit(kind="error", where="hc_mix", tb=traceback.format_exc()[-1500:])
    try:
        summ["gemm"] = run_gemms(summ["bw_peak_GBps"])
    except Exception:
        emit(kind="error", where="gemm", tb=traceback.format_exc()[-1500:])
    emit(summary=summ)


if __name__ == "__main__":
    main()
