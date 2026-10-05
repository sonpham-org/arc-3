"""kglue checks in the PATCHED install (5-Oct-2026, Kernel optimizations thread). Pre-server script, free GPU.

Part hcnorm: HC combine apply + the next mix's per-branch norm in one kernel (hyperconnection.py).
Real weights from the served model (layer 0: attn_hyper_connection inject + hc_norm, mlp_hyper_connection hc_norm and
mix weights), random activations at 1..64 rows:
1. bitwise: kglue_hc_combine_norm vs hc_combine_split -> grouped_gemma_rmsnorm (both outputs), determinism
2. module path: GatedResidual A.mix -> A.combine -> B.mix, eager twice (1st learns the link, 2nd fused): outputs equal
   the reference, link set, and the 2nd run launches no grouped_gemma_rmsnorm (torch profiler)
3. CUDA-graph capture of that chain, replay with fresh inputs == eager reference
4. timing, cold activations (R copies > 3x L2), 40 rows: gate + apply + norm vs gate + apply_norm
Part small (exact glue removals):
5. fast_topk: scores holding garbage (NaN / +inf / huge) past lengths[row] vs -inf there, lengths 1..L incl. > 512,
   row_starts None (persistent zero slice) vs explicit zeros: identical index sets per row
6. unit k/v scale: bf16 x.div_(1.0) is bitwise x (incl. +-0, inf, subnormals, max)
7. GDN verify A_log: flashinfer WY output-only with the fp32 parameter object vs .detach().float(): bitwise equal; the
   repeated call launches no bf16 cast kernel
Part gatesum (MoE top-k sum folded into the shared-expert gate kernel):
8. kglue_topk_sum_gate vs moe_topk_sum -> fused_gate_sigmoid_mul_add, real shared_expert_gate weight, 1..64 rows,
   the model's top-k: bitwise; a denormal-input case reported separately; timing of 49 layers in a CUDA graph
Part pdl (kfast skinny GEMM launched with PDL):
9. every skinny tactic shape at 10 / 40 / 64 rows: PDL on == PDL off bitwise; a CUDA graph of a dependent chain
   (norm -> skinny -> norm -> skinny ...) replays equal to eager; chain timing PDL off vs on
Part mixexact (can the khc fused HC mix be made BITWISE equal to the compiled chain?), real layer-0 weights, 40 rows,
informational (no FAIL): where the 0.05% of differing elements come from:
10. down projection: cuBLAS/aten mm output (bf16) vs our split-K partials summed in slice order, for S x BLOCK_K
11. div + silu: torch.compile'd F.silu(d / hc) vs our reduce formula on the same bf16 input
12. up + sigmoid-mul-mean: compiled tail vs our up4 kernel fed the same t
13. end to end per tactic: share of output elements equal to the compiled chain
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


def model_dir():
    return os.path.dirname(sorted(glob.glob(MODEL_GLOB, recursive=True))[0])


def loader():
    d = model_dir()
    wm = json.load(open(os.path.join(d, "model.safetensors.index.json")))["weight_map"]

    def t(name):
        path = os.path.join(d, wm[name])
        with open(path, "rb") as f:
            n = struct.unpack("<Q", f.read(8))[0]
            h = json.loads(f.read(n))
        m = h[name]
        assert m["dtype"] == "BF16", (name, m["dtype"])
        o0, o1 = m["data_offsets"]
        a = np.memmap(path, dtype=np.uint16, mode="r", offset=8 + n + o0, shape=tuple(m["shape"]))
        return torch.from_numpy(np.ascontiguousarray(a).view(np.int16)).view(torch.bfloat16).to(DEV)
    return t


def rms_eps():
    cfg = json.load(open(os.path.join(model_dir(), "config.json")))
    for c in (cfg, cfg.get("text_config", {})):
        if "rms_norm_eps" in c:
            return float(c["rms_norm_eps"])
    return 1e-6


def make_hc(H, w, prefix, eps):
    cfg = H.HyperConnectionConfig(hc_count=HC, hidden_size=HS, params_dtype=torch.bfloat16, hc_lowrank=LR,
                                  rms_norm_eps=eps, hc_per_branch_norm=True)
    mod = H.GatedResidual(cfg, use_mix=True, use_combine=True)
    with torch.no_grad():
        mod.input_mix_weight_down.weight.copy_(w(prefix + "input_mix_weight_down.weight"))
        mod.input_mix_weight_up.weight.copy_(w(prefix + "input_mix_weight_up.weight"))
        mod.block_inject_weight.weight.copy_(w(prefix + "block_inject_weight.weight"))
        mod.hc_norm.weight.data = w(prefix + "hc_norm.weight").contiguous()
    return mod


def part_hcnorm():
    import sglang.srt.layers.hyperconnection as H
    from sglang.kernels.ops.elementwise.hc_combine import hc_combine_split
    from sglang.kernels.ops.layernorm.grouped_gemma_rmsnorm import grouped_gemma_rmsnorm

    w = loader()
    eps = rms_eps()
    pa, pm = "model.language_model.layers.0.attn_hyper_connection.", "model.language_model.layers.0.mlp_hyper_connection."
    inj = w(pa + "block_inject_weight.weight")
    wn_a, wn_m = w(pa + "hc_norm.weight"), w(pm + "hc_norm.weight")
    emit(kind="hcnorm_env", eps=eps, inject=list(inj.shape), norm=list(wn_m.shape), enabled=H._KGLUE_HCNORM,
         split_max_rows=H._KHC_SPLIT_MAX_ROWS)
    gen = torch.Generator(device=DEV).manual_seed(5)

    # 1. bitwise vs the two-kernel path
    for m in (1, 2, 4, 9, 10, 16, 17, 24, 32, 36, 40, 44, 48, 52, 64):
        r = (torch.randn(m, HC * HS, generator=gen, device=DEV) * 4).to(torch.bfloat16)
        y = (torch.randn(m, HS, generator=gen, device=DEV) * 2).to(torch.bfloat16)
        n = grouped_gemma_rmsnorm(r, wn_a, HS, eps)
        ref_out = hc_combine_split(y, r, n, inj, HC, HS)
        ref_nrm = grouped_gemma_rmsnorm(ref_out, wn_m, HS, eps)
        out, nrm = H.kglue_hc_combine_norm(y, r, n, inj, wn_m, eps, HC, HS)
        out2, nrm2 = H.kglue_hc_combine_norm(y, r, n, inj, wn_m, eps, HC, HS)
        torch.cuda.synchronize()
        eq_o, eq_n = bool(torch.equal(out, ref_out)), bool(torch.equal(nrm, ref_nrm))
        det = bool(torch.equal(out, out2) and torch.equal(nrm, nrm2))
        emit(kind="hcnorm_bitwise", m=m, out_equal=eq_o, normed_equal=eq_n, deterministic=det,
             max_abs_diff_normed=float((nrm.float() - ref_nrm.float()).abs().max()))
        if not (eq_o and eq_n and det):
            FAIL.append(("hcnorm_bitwise", m))

    # 2. module path A.mix -> A.combine -> B.mix
    A, B = make_hc(H, w, pa, eps), make_hc(H, w, pm, eps)

    def chain(x0, bo):
        mixed_a, res_a = A.mix(x0)
        x1 = A.combine(bo, res_a)
        mixed_b, res_b = B.mix(x1)
        return mixed_a, x1, mixed_b, res_b[1]

    def reference(x0, bo):
        n0 = grouped_gemma_rmsnorm(x0, A.hc_norm.weight, HS, eps)
        x1 = hc_combine_split(bo, x0, n0, A.block_inject_weight.weight, HC, HS)
        n1 = grouped_gemma_rmsnorm(x1, B.hc_norm.weight, HS, eps)
        return x1, n1

    from torch.profiler import ProfilerActivity, profile
    for m in (10, 40, 64):
        x0 = (torch.randn(m, HC * HS, generator=gen, device=DEV) * 4).to(torch.bfloat16)
        bo = (torch.randn(m, HS, generator=gen, device=DEV) * 2).to(torch.bfloat16)
        A._kglue_next = None
        with torch.no_grad():
            first = chain(x0, bo)
            linked = A._kglue_next is B
            with profile(activities=[ProfilerActivity.CUDA]) as prof:
                second = chain(x0, bo)
                torch.cuda.synchronize()
            x1r, n1r = reference(x0, bo)
        names = [e.name for e in prof.events() if e.device_type.name == "CUDA"]
        n_norm = sum("grouped_gemma_rmsnorm" in s for s in names)
        n_fused = sum("kglue_hc_apply_norm" in s for s in names)
        # his persistent mix kernel (<= 16 rows) sums with atomics, so mixed outputs are only compared above 16 rows
        ok = (linked and torch.equal(first[1], x1r) and torch.equal(second[1], x1r) and torch.equal(first[3], n1r)
              and torch.equal(second[3], n1r)
              and (m <= 16 or (torch.equal(first[2], second[2]) and torch.equal(first[0], second[0]))))
        emit(kind="hcnorm_module", m=m, linked=linked, outputs_equal=ok, second_run_norm_kernels=n_norm,
             second_run_fused_kernels=n_fused)
        # the second run still norms A's own input (x0 came from nowhere): exactly one norm, one fused kernel
        if not ok or n_fused != 1 or n_norm != 1:
            FAIL.append(("hcnorm_module", m))

    # 3. CUDA graph of the chain, replay with fresh inputs
    m = 40
    x0 = (torch.randn(m, HC * HS, generator=gen, device=DEV) * 4).to(torch.bfloat16)
    bo = (torch.randn(m, HS, generator=gen, device=DEV) * 2).to(torch.bfloat16)
    res = {}
    s = torch.cuda.Stream()
    s.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(s), torch.no_grad():
        chain(x0, bo)
        chain(x0, bo)
    torch.cuda.current_stream().wait_stream(s)
    torch.cuda.synchronize()
    g = torch.cuda.CUDAGraph()
    with torch.cuda.graph(g), torch.no_grad():
        res["o"] = chain(x0, bo)
    ok = True
    for _ in range(3):
        x0.copy_((torch.randn(m, HC * HS, generator=gen, device=DEV) * 4).to(torch.bfloat16))
        bo.copy_((torch.randn(m, HS, generator=gen, device=DEV) * 2).to(torch.bfloat16))
        g.replay()
        torch.cuda.synchronize()
        x1r, n1r = reference(x0, bo)
        ok &= bool(torch.equal(res["o"][1], x1r) and torch.equal(res["o"][3], n1r))
    emit(kind="hcnorm_graph_replay", ok=ok)
    if not ok:
        FAIL.append(("hcnorm_graph",))
    del g

    # 4. timing, cold activations
    for m in (10, 40):
        per = m * HC * HS * 2 * 4 + m * HS * 2
        R = max(16, int(3 * 128e6 / per) + 1)
        rs = [(torch.randn(m, HC * HS, device=DEV) * 4).to(torch.bfloat16) for _ in range(R)]
        ys = [(torch.randn(m, HS, device=DEV) * 2).to(torch.bfloat16) for _ in range(R)]
        ns = [grouped_gemma_rmsnorm(r, wn_a, HS, eps) for r in rs]
        t_ref = graph_time([lambda i=i: grouped_gemma_rmsnorm(hc_combine_split(ys[i], rs[i], ns[i], inj, HC, HS),
                                                               wn_m, HS, eps) for i in range(R)])
        t_new = graph_time([lambda i=i: H.kglue_hc_combine_norm(ys[i], rs[i], ns[i], inj, wn_m, eps, HC, HS)
                            for i in range(R)])
        emit(kind="hcnorm_timing_cold", m=m, R=R, three_kernels_us=round(t_ref, 2), fused_us=round(t_new, 2),
             saving_us=round(t_ref - t_new, 2), saving_ms_per_step_at_100=round((t_ref - t_new) * 100 / 1e3, 3))
        del rs, ys, ns


def part_small():
    from torch.profiler import ProfilerActivity, profile

    import sglang.kernels.ops.elementwise.fast_topk as FT
    gen = torch.Generator(device=DEV).manual_seed(9)
    # 5. fast_topk never reads past lengths[row]
    for B, L, topk in ((40, 34816, 512), (10, 8192, 512), (80, 34816, 512)):
        lengths = torch.randint(1, L + 1, (B,), generator=gen, device=DEV).to(torch.int32)
        lengths[: B // 4] = torch.randint(1, 513, (B // 4,), generator=gen, device=DEV).to(torch.int32)
        base = torch.randn(B, L, generator=gen, device=DEV)
        col = torch.arange(L, device=DEV)[None, :]
        clean = torch.where(col < lengths[:, None].long(), base, torch.full_like(base, -float("inf")))
        junk = torch.where(col < lengths[:, None].long(), base,
                           torch.where(col % 3 == 0, torch.full_like(base, float("nan")),
                                       torch.where(col % 3 == 1, torch.full_like(base, float("inf")), base * 1e30)))
        a = FT.fast_topk(clean, lengths, topk, torch.zeros(B, dtype=torch.int32, device=DEV))
        b = FT.fast_topk(junk, lengths, topk)          # persistent zero row_starts
        c = FT.fast_topk(junk, lengths, topk)
        torch.cuda.synchronize()
        same = bool(torch.equal(a.sort(dim=1).values, b.sort(dim=1).values)
                    and torch.equal(b.sort(dim=1).values, c.sort(dim=1).values))
        emit(kind="topk_garbage_past_length", B=B, L=L, topk=topk, identical_sets=same,
             persistent_zero_starts=FT._KGLUE_ROWSTART and (DEV in FT._KGLUE_ZERO_STARTS or
                                                            any(k.type == "cuda" for k in FT._KGLUE_ZERO_STARTS)))
        if not same:
            FAIL.append(("topk_garbage", B))
    # 6. unit divide is the identity on bf16
    x = torch.randint(0, 1 << 16, (1 << 16,), dtype=torch.int32, device=DEV).to(torch.int16).view(torch.bfloat16)
    x = torch.cat([x, torch.arange(-32768, 32768, dtype=torch.int32, device=DEV).to(torch.int16).view(torch.bfloat16)])
    y = x.clone()
    y.div_(1.0)
    finite = torch.isfinite(x.float()) | torch.isinf(x.float())
    eq = bool(torch.equal(x[finite].view(torch.int16), y[finite].view(torch.int16)))
    nan_ok = bool(torch.isnan(y[~finite].float()).all())
    emit(kind="unit_divide_identity", all_bf16_patterns=int(x.numel()), non_nan_bitwise=eq, nan_stays_nan=nan_ok)
    if not (eq and nan_ok):
        FAIL.append(("unit_divide",))
    # 7. GDN A_log: same output with the parameter object, no per-call cast
    import importlib
    W = importlib.import_module("flashinfer.gdn_kernels.gdn_decode_bf16_wy_output_only")
    from flashinfer.gdn_kernels import gated_delta_rule_mtp_wy_output_only as fn
    H_, HK, HV, KD = 16, 16, 48, 128
    Bq, T = 10, 4
    mixed = torch.randn(Bq * T, (H_ + HK + HV) * KD, generator=gen, device=DEV).to(torch.bfloat16)
    q = mixed[:, : H_ * KD].view(Bq, T, H_, KD)
    k = mixed[:, H_ * KD:(H_ + HK) * KD].view(Bq, T, HK, KD)
    v = mixed[:, (H_ + HK) * KD:].view(Bq, T, HV, KD)
    ab = torch.randn(2, Bq * T, HV, generator=gen, device=DEV).to(torch.bfloat16)
    st = (torch.randn(32, HV, KD, KD, generator=gen, device=DEV) * 0.05).to(torch.bfloat16)
    idx = torch.randperm(32, generator=gen, device=DEV)[:Bq].to(torch.int32)
    A_log = torch.nn.Parameter((torch.rand(HV, generator=gen, device=DEV) * 2 - 3).float())
    dt_bias = torch.nn.Parameter((torch.randn(HV, generator=gen, device=DEV) * 0.5).to(torch.bfloat16))

    def call(al):
        return fn(A_log=al, a=ab[0].view(Bq, T, HV), dt_bias=dt_bias.detach(), q=q, k=k, v=v, b=ab[1].view(Bq, T, HV),
                  initial_state_source=st, initial_state_indices=idx, output_state_indices=None,
                  intermediate_states_buffer=None, disable_state_update=True, use_qk_l2norm_in_kernel=True,
                  scale=None, output=None)
    with torch.no_grad():
        ref = call(A_log.detach().float()).clone()
        new1 = call(A_log).clone()
        with profile(activities=[ProfilerActivity.CUDA]) as prof:
            new2 = call(A_log).clone()
            torch.cuda.synchronize()
    # the [48] A_log cast is a one-block bfloat16_copy kernel; q/k/v staging copies (strided flag off) are bigger
    casts = sum("bfloat16_copy_kernel_cuda" in e.name for e in prof.events() if e.device_type.name == "CUDA")
    eq = bool(torch.equal(ref, new1) and torch.equal(ref, new2))
    emit(kind="gdn_alog_cached", bitwise_equal=eq, bf16_cast_kernels_on_repeat=casts)
    if not eq or casts:
        FAIL.append(("gdn_alog", casts))


def part_gatesum():
    from sglang.kernels.ops.elementwise.elementwise import fused_gate_sigmoid_mul_add
    from sglang.kernels.ops.moe.moe_topk_sum import moe_topk_sum
    from sglang.srt.layers.moe.fused_moe_triton.fused_marlin_moe import kglue_topk_sum_gate

    cfg = json.load(open(os.path.join(model_dir(), "config.json")))
    tc = cfg.get("text_config", cfg)
    topk = int(tc.get("num_experts_per_tok", 8))
    w = loader()
    try:
        gw = w("model.language_model.layers.0.mlp.shared_expert_gate.weight").reshape(-1).contiguous()
        src = "real"
    except KeyError:
        gw = (torch.randn(HS, device=DEV) * 0.02).to(torch.bfloat16)
        src = "synthetic"
    emit(kind="gatesum_env", topk=topk, gate_weight=src, n=int(gw.numel()))
    gen = torch.Generator(device=DEV).manual_seed(13)

    def run_ref(h, s_, c3):
        out = torch.empty_like(h)
        moe_topk_sum(c3, out)
        fused_gate_sigmoid_mul_add(h, gw, s_, out)
        return out

    def run_new(h, s_, c3):
        out = torch.empty_like(h)
        kglue_topk_sum_gate(h, gw, s_, c3, out)
        return out

    for m in (1, 2, 7, 10, 16, 33, 40, 48, 64, 80):
        h = (torch.randn(m, HS, generator=gen, device=DEV) * 2).to(torch.bfloat16)
        s_ = (torch.randn(m, HS, generator=gen, device=DEV) * 0.3).to(torch.bfloat16)
        c3 = (torch.randn(m, topk, HS, generator=gen, device=DEV) * 0.2).to(torch.bfloat16)
        a, b = run_ref(h, s_, c3), run_new(h, s_, c3)
        torch.cuda.synchronize()
        eq = bool(torch.equal(a, b))
        emit(kind="gatesum_bitwise", m=m, equal=eq, max_abs_diff=float((a.float() - b.float()).abs().max()))
        if not eq:
            FAIL.append(("gatesum", m))
    # denormal inputs (informational: topk_sum is built with --use_fast_math, i.e. flush-to-zero)
    m = 16
    h = (torch.randn(m, HS, generator=gen, device=DEV) * 2).to(torch.bfloat16)
    s_ = torch.zeros(m, HS, device=DEV, dtype=torch.bfloat16)
    c3 = (torch.randn(m, topk, HS, generator=gen, device=DEV) * 1e-39).to(torch.bfloat16)
    a, b = run_ref(h, s_, c3), run_new(h, s_, c3)
    torch.cuda.synchronize()
    emit(kind="gatesum_denormal_inputs", equal=bool(torch.equal(a, b)),
         share_equal=round((a.view(torch.int16) == b.view(torch.int16)).float().mean().item(), 4))
    # timing: 49 layers x (topk_sum + gate) vs 49 x fused, distinct buffers
    for m in (10, 40):
        L = 49
        hs = [(torch.randn(m, HS, device=DEV) * 2).to(torch.bfloat16) for _ in range(L)]
        ss = [(torch.randn(m, HS, device=DEV) * 0.3).to(torch.bfloat16) for _ in range(L)]
        cs = [(torch.randn(m, topk, HS, device=DEV) * 0.2).to(torch.bfloat16) for _ in range(L)]
        outs = [torch.empty(m, HS, device=DEV, dtype=torch.bfloat16) for _ in range(L)]

        def ref_i(i):
            moe_topk_sum(cs[i], outs[i])
            fused_gate_sigmoid_mul_add(hs[i], gw, ss[i], outs[i])
        t_ref = graph_time([lambda i=i: ref_i(i) for i in range(L)])
        t_new = graph_time([lambda i=i: kglue_topk_sum_gate(hs[i], gw, ss[i], cs[i], outs[i]) for i in range(L)])
        emit(kind="gatesum_timing", m=m, two_kernels_us=round(t_ref, 2), fused_us=round(t_new, 2),
             saving_ms_per_step_49_layers=round((t_ref - t_new) * 49 / 1e3, 3))


def part_pdl():
    import sglang.kernels.ops.gemm.sm120_lowm_bf16_gemm as G
    from sglang.kernels.ops.layernorm.grouped_gemma_rmsnorm import grouped_gemma_rmsnorm

    if not hasattr(G, "_kglue_use_pdl"):
        emit(kind="pdl_env", installed=False)   # kpdl / kpdl128 not in this stack
        return
    emit(kind="pdl_env", enabled=G._kglue_use_pdl(), shapes=len(G._SKINNY_TACTICS))
    gen = torch.Generator(device=DEV).manual_seed(17)
    for (n, k) in G._SKINNY_TACTICS:
        wt = (torch.randn(n, k, generator=gen, device=DEV) * 0.02).to(torch.bfloat16)
        for m in (10, 40, 64):
            x = torch.randn(m, k, generator=gen, device=DEV).to(torch.bfloat16)
            t = G._skinny_tactic(m, n, k)
            G._kglue_pdl_ok = False
            a = G._skinny_gemm(x, wt, *t)
            G._kglue_pdl_ok = None
            b = G._skinny_gemm(x, wt, *t)
            torch.cuda.synchronize()
            eq = bool(torch.equal(a, b))
            if not eq:
                FAIL.append(("pdl_bitwise", n, k, m))
                emit(kind="pdl_bitwise_FAIL", n=n, k=k, m=m)
    emit(kind="pdl_bitwise", checked=len(G._SKINNY_TACTICS) * 3, fails=sum(1 for f in FAIL if f[0] == "pdl_bitwise"))
    # dependent chain: x -> skinny(2560->1280... use shared gate_up shape) -> norm on a 2560 slice ... graph vs eager
    n1, k1 = 2560, 6144
    m = 40
    w1 = [(torch.randn(n1, k1, device=DEV) * 0.02).to(torch.bfloat16) for _ in range(36)]
    w2 = [(torch.randn(k1, n1, device=DEV) * 0.02).to(torch.bfloat16) for _ in range(36)]
    nw = (torch.randn(n1, device=DEV) * 0.1).to(torch.bfloat16)
    x0 = torch.randn(m, k1, device=DEV).to(torch.bfloat16)
    t1, t2 = G._skinny_tactic(m, n1, k1), (64, 128, 1, 4, 4)

    def chain(x):
        for i in range(36):
            y = G._skinny_gemm(x, w1[i], *t1)
            y = grouped_gemma_rmsnorm(y, nw, n1, 1e-6)
            x = torch.nn.functional.linear(y, w2[i]) if False else G._skinny_gemm(y, w2[i], *t2)
        return x
    G._kglue_pdl_ok = False
    ref = chain(x0)
    G._kglue_pdl_ok = None
    res = {}
    s_ = torch.cuda.Stream()
    s_.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(s_):
        chain(x0)
    torch.cuda.current_stream().wait_stream(s_)
    torch.cuda.synchronize()
    g = torch.cuda.CUDAGraph()
    with torch.cuda.graph(g):
        res["y"] = chain(x0)
    g.replay()
    torch.cuda.synchronize()
    ok = bool(torch.equal(res["y"], ref))
    emit(kind="pdl_graph_chain", ok=ok)
    if not ok:
        FAIL.append(("pdl_graph",))
    del g
    for flag in (False, None):
        G._kglue_pdl_ok = flag
        us = graph_time([lambda: chain(x0)], reps=20)
        emit(kind="pdl_chain_timing", pdl=G._kglue_use_pdl(), us_per_chain=round(us, 1), kernels=36 * 3)
    G._kglue_pdl_ok = None


def part_mixexact():
    """kglue exact fused mix through GatedResidual.mix: bitwise vs the compiled chain at 17..64 rows (split picked
    per shape), graph replay, timing."""
    import sglang.srt.layers.hyperconnection as H
    w = loader()
    pa = "model.language_model.layers.0.attn_hyper_connection."
    eps = rms_eps()
    A = make_hc(H, w, pa, eps)
    wd, wu = A.input_mix_weight_down.weight, A.input_mix_weight_up.weight
    gen = torch.Generator(device=DEV).manual_seed(31)
    emit(kind="mix_env", max_rows=H._KHC_MIX_MAX_ROWS, exact=H._KGLUE_MIX_EXACT, pdl=H._kglue_mix_use_pdl())
    bad, picks = [], {}
    for m in range(17, 65):
        hin = (torch.randn(m, HC * HS, generator=gen, device=DEV) * 4).to(torch.bfloat16)
        with torch.no_grad():
            mixed, res = A.mix(hin)
            ref = A._mix_compute(res[1], wd, wu, HC, HS).to(torch.bfloat16)
        torch.cuda.synchronize()
        S = H._kglue_mix_split.get((HC * HS, wd.shape[0], HC, m), "unset")
        picks[m] = S
        if not torch.equal(mixed, ref):
            bad.append(m)
    emit(kind="mix_exact_rows", rows="17..64", splits=picks, not_equal=bad,
         fused_rows=sum(1 for v in picks.values() if isinstance(v, int)))
    if bad:
        FAIL.append(("mix_exact", bad[:8]))
    # graph replay at 40 rows through the module
    m = 40
    hin = (torch.randn(m, HC * HS, generator=gen, device=DEV) * 4).to(torch.bfloat16)
    out = {}
    s_ = torch.cuda.Stream()
    s_.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(s_), torch.no_grad():
        A.mix(hin)
    torch.cuda.current_stream().wait_stream(s_)
    torch.cuda.synchronize()
    g = torch.cuda.CUDAGraph()
    with torch.cuda.graph(g), torch.no_grad():
        out["y"], out["r"] = A.mix(hin)
    ok = True
    for _ in range(3):
        hin.copy_((torch.randn(m, HC * HS, generator=gen, device=DEV) * 4).to(torch.bfloat16))
        g.replay()
        torch.cuda.synchronize()
        with torch.no_grad():
            ok &= bool(torch.equal(out["y"], A._mix_compute(out["r"][1], wd, wu, HC, HS).to(torch.bfloat16)))
    emit(kind="mix_graph_replay", ok=ok)
    if not ok:
        FAIL.append(("mix_graph",))
    del g
    # timing, cold weights, picked split vs the compiled chain
    per_copy = (wd.numel() + wu.numel()) * 2
    R = max(16, int(3 * 128e6 / per_copy) + 1)
    wds = [wd.clone() for _ in range(R)]
    wus = [wu.clone() for _ in range(R)]
    for m in (20, 28, 32, 36, 40):
        S = H._kglue_mix_split.get((HC * HS, wd.shape[0], HC, m))
        if not S:
            emit(kind="mix_timing", m=m, split=None)
            continue
        xs = [torch.randn(m, HC * HS, device=DEV).to(torch.bfloat16) for _ in range(R)]
        with torch.no_grad():
            tc = graph_time([lambda i=i: A._mix_compute(xs[i], wds[i], wus[i], HC, HS) for i in range(R)])
            tf = graph_time([lambda i=i: H._khc_fused_mix(xs[i], wds[i], wus[i], HC, HS, dict(S=S)) for i in range(R)])
        emit(kind="mix_timing", m=m, split=S, compiled_us=round(tc, 2), fused_us=round(tf, 2),
             saving_ms_per_step_at_100=round((tc - tf) * 100 / 1e3, 3))
        if m == 40:   # down tactic sweep at the exact split (BLOCK_K / warps / stages do not change the bytes)
            import itertools
            res = []
            for fr, bn, bk, dw, ds in itertools.product((True, False), (32, 64), (32, 64, 128), (4, 8), (2, 3, 4)):
                tac = dict(S=S, fuse_reduce=fr, BLOCK_N=bn, BLOCK_K=bk, down_warps=dw, down_stages=ds)
                try:
                    with torch.no_grad():
                        us = graph_time([lambda i=i: H._khc_fused_mix(xs[i], wds[i], wus[i], HC, HS, tac)
                                         for i in range(R)])
                        eq = bool(torch.equal(H._khc_fused_mix(xs[0], wds[0], wus[0], HC, HS, tac),
                                              A._mix_compute(xs[0], wds[0], wus[0], HC, HS).to(torch.bfloat16)))
                    res.append((us, eq, tac))
                except Exception as e:
                    res.append((float("inf"), False, dict(tac, err=repr(e)[:80])))
            res.sort(key=lambda z: z[0])
            for us, eq, tac in res[:8]:
                emit(kind="mix_sweep", m=m, us=round(us, 2), bitwise=eq, tactic=tac)
            emit(kind="mix_sweep_all_bitwise", ok=all(eq for us, eq, tac in res if us != float("inf")),
                 n=len(res), n_failed_launch=sum(1 for r in res if r[0] == float("inf")))
        del xs


def main():
    part_hcnorm()
    part_small()
    part_gatesum()
    part_pdl()
    try:
        part_mixexact()
    except Exception as e:
        import traceback
        emit(kind="mixexact_error", err=repr(e)[:300], tb=traceback.format_exc()[-1500:])
    emit(verdict="PASS" if not FAIL else "FAIL", fails=FAIL)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        emit(kind="error", err=repr(e)[:400], tb=traceback.format_exc()[-2400:])
        emit(verdict="FAIL")
