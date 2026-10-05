"""kgdn check (4-Oct-2026, Kernel optimizations thread). Pre-server script, free GPU, his venv.

The GDN target-verify region does 3 .contiguous() copies per linear-attention layer (q/k/v are torch.split views of
the conv output: qkv_dim 10240 > MAX_FUSED_QKV_SPLIT_DIM 8192), inside flashinfer's
gated_delta_rule_mtp_wy_output_only. flashinfer already has FLASHINFER_GDN_WY_STRIDED_QKV (default off): pass the
row stride and read q/k/v in place, documented bit-identical. Check, on realistic strided inputs:
1. bitwise: module flag off (copies) vs on (strided read), T = 4 and 8, B = 9 and 10;
2. CUDA-graph replay of the strided path with fresh inputs == eager copy path;
3. timing in CUDA graphs (36 calls = one step's layers), copy path vs strided path.
Last line {"verdict": ...}.
"""
import json
import time

import torch

DEV = torch.device("cuda")
T0 = time.time()
FAIL = []
H, HK, HV, KD = 16, 16, 48, 128
CONV = (H + HK + HV) * KD   # 10240


def emit(**kw):
    kw["t"] = round(time.time() - T0, 1)
    print(json.dumps(kw), flush=True)


def inputs(B, T, gen, pool=32):
    mixed = torch.randn(B * T, CONV, generator=gen, device=DEV).to(torch.bfloat16)
    ab = torch.randn(2, B * T, HV, generator=gen, device=DEV).to(torch.bfloat16)
    st = (torch.randn(pool, HV, KD, KD, generator=gen, device=DEV) * 0.05).to(torch.bfloat16)
    idx = torch.randperm(pool, generator=gen, device=DEV)[:B].to(torch.int32)
    A_log = (torch.rand(HV, generator=gen, device=DEV) * 2 - 3).float()
    dt_bias = (torch.randn(HV, generator=gen, device=DEV) * 0.5).to(torch.bfloat16)
    return dict(mixed=mixed, ab=ab, st=st, idx=idx, A_log=A_log, dt_bias=dt_bias, B=B, T=T)


def views(d):
    B, T, m = d["B"], d["T"], d["mixed"]
    q = m[:, : H * KD].view(B, T, H, KD)
    k = m[:, H * KD: (H + HK) * KD].view(B, T, HK, KD)
    v = m[:, (H + HK) * KD:].view(B, T, HV, KD)
    a = d["ab"][0].view(B, T, HV)
    b = d["ab"][1].view(B, T, HV)
    return q, k, v, a, b


def call(fn, d):
    q, k, v, a, b = views(d)
    return fn(A_log=d["A_log"], a=a, dt_bias=d["dt_bias"], q=q, k=k, v=v, b=b, initial_state_source=d["st"],
              initial_state_indices=d["idx"], output_state_indices=None, intermediate_states_buffer=None,
              disable_state_update=True, use_qk_l2norm_in_kernel=True, scale=None, output=None)


def graph_us(fns, reps=10):
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
    torch.cuda.synchronize()
    e0, e1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
    e0.record()
    for _ in range(reps):
        g.replay()
    e1.record()
    torch.cuda.synchronize()
    return e0.elapsed_time(e1) * 1e3 / (reps * len(fns))


def main():
    import flashinfer.gdn_kernels.gdn_decode_bf16_wy_output_only as W
    from flashinfer.gdn_kernels import gated_delta_rule_mtp_wy_output_only as fn
    emit(kind="env", native_t=W._NATIVE_T, native_ab=W._NATIVE_AB, strided_default=W._STRIDED_QKV)
    gen = torch.Generator(device=DEV).manual_seed(11)
    for T in (4, 8):
        for B in (10, 9):
            d = inputs(B, T, gen)
            W._STRIDED_QKV = False
            ref = call(fn, d).clone()
            W._STRIDED_QKV = True
            out = call(fn, d).clone()
            torch.cuda.synchronize()
            eq = bool(torch.equal(ref, out))
            emit(kind="bitwise", T=T, B=B, equal=eq, max_abs_diff=float((ref.float() - out.float()).abs().max()),
                 out_shape=list(out.shape))
            if not eq:
                FAIL.append(("bitwise", T, B))
    # graph replay, strided path
    d = inputs(10, 4, gen)
    W._STRIDED_QKV = True
    res = {}
    s = torch.cuda.Stream()
    s.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(s):
        call(fn, d)
    torch.cuda.current_stream().wait_stream(s)
    torch.cuda.synchronize()
    g = torch.cuda.CUDAGraph()
    with torch.cuda.graph(g):
        res["y"] = call(fn, d)
    ok = True
    for _ in range(3):
        d["mixed"].copy_(torch.randn_like(d["mixed"].float()).to(torch.bfloat16))
        d["ab"].copy_(torch.randn_like(d["ab"].float()).to(torch.bfloat16))
        g.replay()
        torch.cuda.synchronize()
        W._STRIDED_QKV = False
        ok &= bool(torch.equal(res["y"], call(fn, d)))
        W._STRIDED_QKV = True
    emit(kind="graph_replay", ok=ok)
    if not ok:
        FAIL.append(("graph",))
    # timing: 36 layers' worth of calls on distinct inputs
    for T in (4, 8):
        ds = [inputs(10, T, gen) for _ in range(36)]
        res_t = {}
        for flag in (False, True):
            W._STRIDED_QKV = flag
            res_t[flag] = graph_us([lambda i=i: call(fn, ds[i]) for i in range(36)])
        emit(kind="timing", T=T, B=10, copy_path_us=round(res_t[False], 2), strided_us=round(res_t[True], 2),
             saving_per_step_ms=round((res_t[False] - res_t[True]) * 36 / 1e3, 3))
        del ds
    emit(verdict="PASS" if not FAIL else "FAIL", fails=FAIL)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        emit(kind="error", err=repr(e)[:400], tb=traceback.format_exc()[-1800:])
        emit(verdict="FAIL")
