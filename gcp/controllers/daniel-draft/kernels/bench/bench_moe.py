"""MoE W4A16 Marlin micro-benchmark on the real card (3-Oct-2026, daniel-draft kernels; Son: tune the MoE kernel).

Runs in Daniel's venv on the free GPU (make_bench_notebook.py --pre-script). Qwen3.8-Flash-Next routed experts:
E=512, hidden 2560, expert intermediate 640, top-10, AutoRound int4 sym g128 (Marlin uint4b8). Random Marlin-format
weights for NL layers (cold: each layer has its own 1.26 GB of experts), REAL routing (routing_sample.npy: 13 lanes x
4 consecutive tokens per verify step, from daniel-bench-route10-1003). Times, inside CUDA graphs over the NL layers:
  base     his fused_marlin_moe as served (align + gate_up GEMM + silu*mul + down GEMM + sum), per layer
  gemms    the two Marlin GEMMs alone, per layer (+ achieved GB/s over the distinct experts' bytes)
  knobs    moe_block_size 8/16, use_atomic_add on/off
  variants JIT copies of his Marlin MoE source with: pipeline stages 4/6/8, forced thread config, forced blocks/SM,
           extra tile configs (k128 n64 128 threads; k64 n256 256 threads)
Prints one JSON line per measurement and {"summary": ...}.
"""
import json
import os
import re
import shutil
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import torch

DEV = torch.device("cuda")
T0 = time.time()
E, H, I, TOPK, G = 512, 2560, 640, 10, 128
NL = int(os.environ.get("MOE_LAYERS", 6))
STEPS = [int(s) for s in os.environ.get("MOE_STEPS", "0,3,6,9").split(",")]
TS = [int(t) for t in os.environ.get("MOE_TS", "52,40").split(",")]
EXPERT_BYTES = (3 * H * I) // 2 + 3 * H * I // G * 2  # int4 + bf16 scales
W1_BYTES = (2 * H * I) // 2 + 2 * H * I // G * 2
W2_BYTES = (H * I) // 2 + H * I // G * 2
HERE = Path(os.path.dirname(os.path.abspath(__file__)))


def emit(**kw):
    kw["t"] = round(time.time() - T0, 1)
    print(json.dumps(kw), flush=True)


def graph_time(fn, reps=8, warm=2):
    s = torch.cuda.Stream()
    s.wait_stream(torch.cuda.current_stream())
    with torch.cuda.stream(s):
        fn()
    torch.cuda.current_stream().wait_stream(s)
    torch.cuda.synchronize()
    g = torch.cuda.CUDAGraph()
    with torch.cuda.graph(g):
        fn()
    for _ in range(warm):
        g.replay()
    torch.cuda.synchronize()
    e0, e1 = torch.cuda.Event(enable_timing=True), torch.cuda.Event(enable_timing=True)
    e0.record()
    for _ in range(reps):
        g.replay()
    e1.record()
    torch.cuda.synchronize()
    del g
    return e0.elapsed_time(e1) * 1e3 / reps


def make_variant(tag, stages=4, extra_cfgs=False):
    """Copy his Marlin MoE JIT source into /kaggle/working/mvar_<tag>, with: pipe_stages from MV_PIPE_STAGES, env
    overrides MV_CFG (only consider small-batch config i) and MV_BPS (blocks per SM), uint4b8 g128 instantiations
    only (fast compile), optionally extra small-batch tile configs."""
    import sglang.kernels as sk
    from sglang.kernels.jit.utils import load_jit, make_cpp_args
    src = Path(sk.__file__).parent / "jit" / "csrc" / "gemm"
    dst = Path(f"/kaggle/working/mvar_{tag}") / "gemm"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src / "marlin", dst / "marlin")
    shutil.copytree(src / "marlin_moe", dst / "marlin_moe")
    m = (dst / "marlin" / "marlin.cuh").read_text()
    old = "static constexpr int pipe_stages = 4;"
    assert old in m
    m = m.replace(old, "#ifndef MV_PIPE_STAGES\n#define MV_PIPE_STAGES 4\n#endif\n"
                       "static constexpr int pipe_stages = MV_PIPE_STAGES;")
    (dst / "marlin" / "marlin.cuh").write_text(m)
    c = (dst / "marlin_moe" / "moe_wna16_marlin.cuh").read_text()
    c = c.replace("#include \"kernel.h\"", "#include <cstdlib>\n#include \"kernel.h\"", 1)
    if extra_cfgs:
        old = "    {128, 128, 256},\n    {64, 128, 128}};"
        assert old in c
        c = c.replace(old, "    {128, 128, 256},\n    {64, 128, 128},\n    {128, 64, 128},\n    {64, 256, 256}};", 1)
    # env overrides inside determine_exec_config
    old = "    thread_config_t th_config = thread_configs[i];\n"
    assert old in c
    c = c.replace(old, old + "    if (std::getenv(\"MV_CFG\") && i != std::atoi(std::getenv(\"MV_CFG\"))) continue;\n", 1)
    old = "  return exec_cfg;\n}"
    assert old in c
    c = c.replace(old, "  if (std::getenv(\"MV_BPS\") && exec_cfg.tb_cfg.thread_k != -1) exec_cfg.blocks_per_sm = "
                       "std::atoi(std::getenv(\"MV_BPS\"));\n" + old, 1)
    # trim instantiations: uint4b8, thread_m_blocks 1, group_blocks 8 (g128) and 2 (g32, his MTP layer)
    a = c.index("  COMMON_GET_IF(host::kU4)\n")
    b = c.index("  return kernel;\n}", a)
    cfgs = [(8, 8, 256), (8, 4, 128)] + ([(4, 8, 128), (16, 4, 256)] if extra_cfgs else [])
    inst = "".join(f"  _GET_IF(host::kU4B8, 1, {nb}, {kb}, {m8}, {gb}, {th}, false)\n"
                   for nb, kb, th in cfgs for m8 in ("true", "false") for gb in (8, 2))
    c = c[:a] + inst + "\n" + c[b:]
    (dst / "marlin_moe" / "moe_wna16_marlin.cuh").write_text(c)
    t = time.time()
    args = make_cpp_args(torch.bfloat16, False, False)
    mod = load_jit(f"moe_wna16_marlin_mv{tag}", *args, cuda_files=[str(dst / "marlin_moe" / "moe_wna16_marlin.cuh")],
                   cuda_wrappers=[("moe_wna16_marlin_gemm", f"moe_wna16_marlin_gemm<{args}>")],
                   extra_cuda_cflags=[f"-DMV_PIPE_STAGES={stages}"])
    emit(kind="variant_built", tag=tag, stages=stages, extra_cfgs=extra_cfgs, seconds=round(time.time() - t))
    return mod


def main():
    from sgl_kernel import moe_sum_reduce
    from sgl_kernel.scalar_type import scalar_types
    import sglang.kernels.ops.moe.moe_wna16_marlin as mw
    from sglang.kernels.ops.activation.activation import silu_and_mul
    from sglang.srt.layers.moe.fused_moe_triton import moe_align_block_size
    from sglang.srt.layers.moe.fused_moe_triton.fused_marlin_moe import fused_marlin_moe

    routing = np.load(HERE / "routing_sample.npy")  # [S, 48, 52, 10] int16
    emit(kind="env", gpu=torch.cuda.get_device_name(0), NL=NL, steps=STEPS, Ts=TS, routing=list(routing.shape),
         expert_MB=EXPERT_BYTES / 1e6)
    gen = torch.Generator(device=DEV).manual_seed(0)
    W1 = [torch.randint(-2**31, 2**31 - 1, (E, H // 16, 2 * I * 2), dtype=torch.int32, device=DEV, generator=gen)
          for _ in range(NL)]
    W2 = [torch.randint(-2**31, 2**31 - 1, (E, I // 16, H * 2), dtype=torch.int32, device=DEV, generator=gen)
          for _ in range(NL)]
    S1 = [(torch.rand((E, H // G, 2 * I), device=DEV, generator=gen) * 0.002 + 0.001).bfloat16() for _ in range(NL)]
    S2 = [(torch.rand((E, I // G, H), device=DEV, generator=gen) * 0.002 + 0.001).bfloat16() for _ in range(NL)]
    ws = torch.zeros(188 * 4, dtype=torch.int32, device=DEV)
    orig_jit = mw._jit_moe_wna16_marlin_module

    def case(T, step):
        ids = [torch.from_numpy(routing[step, l, :T].astype(np.int32)).to(DEV) for l in range(NL)]
        tw = [torch.softmax(torch.randn(T, TOPK, device=DEV, generator=gen), -1) for _ in range(NL)]
        x = (torch.randn(T, H, device=DEV, generator=gen) * 0.5).bfloat16()
        distinct = [len(np.unique(routing[step, l, :T])) for l in range(NL)]
        return ids, tw, x, distinct

    def served(T, ids, tw, x):
        g = torch.zeros(T, E, device=DEV, dtype=torch.float32)
        def run():
            for l in range(NL):
                fused_marlin_moe(hidden_states=x, w1=W1[l], w2=W2[l], w1_scale=S1[l], w2_scale=S2[l], gating_output=g,
                                 topk_weights=tw[l], topk_ids=ids[l], global_num_experts=E, workspace=ws, num_bits=4,
                                 is_k_full=True, inplace=False, activation="silu", is_gated=True)
        return run

    def mine(T, ids, tw, x, block_m=8, atomic=True, part="all", outs=None):
        """Mirror of fused_marlin_moe (same calls), with knobs; part = all | gemm1 | gemm2."""
        pre = []
        for l in range(NL):
            st, ex, npad = moe_align_block_size(ids[l], block_m, E)
            pre.append((st, ex, npad))
        c1 = torch.zeros((T * TOPK, 2 * I), dtype=torch.bfloat16, device=DEV)
        c2 = torch.zeros((T * TOPK, I), dtype=torch.bfloat16, device=DEV)
        c3 = torch.zeros((T * TOPK, H), dtype=torch.bfloat16, device=DEV)
        out = torch.empty_like(x)
        def run():
            for l in range(NL):
                st, ex, npad = pre[l]
                if part in ("all", "gemm1"):
                    if atomic:
                        c1.zero_()
                    mw.moe_wna16_marlin_gemm(x, c1, W1[l], None, S1[l], None, None, None, None, ws, st, ex, npad,
                                             tw[l], moe_block_size=block_m, top_k=TOPK, mul_topk_weights=False,
                                             is_ep=False, b_q_type=scalar_types.uint4b8, size_m=T, size_n=2 * I,
                                             size_k=H, is_k_full=True, use_atomic_add=atomic, use_fp32_reduce=True,
                                             is_zp_float=False)
                if part == "all":
                    silu_and_mul(c1, c2)
                if part in ("all", "gemm2"):
                    if atomic:
                        c3.zero_()
                    mw.moe_wna16_marlin_gemm(c2, c3, W2[l], None, S2[l], None, None, None, None, ws, st, ex, npad,
                                             tw[l], moe_block_size=block_m, top_k=1, mul_topk_weights=True,
                                             is_ep=False, b_q_type=scalar_types.uint4b8, size_m=T * TOPK, size_n=H,
                                             size_k=I, is_k_full=True, use_atomic_add=atomic, use_fp32_reduce=True,
                                             is_zp_float=False)
                if part == "all":
                    moe_sum_reduce(c3.view(T, TOPK, H), out, 1.0)
                    if outs is not None and l == 0:
                        outs.append(out.clone())
        return run, out

    summary = {}
    variants = [("orig", None)]
    try:
        variants.append(("s4", make_variant("s4", 4, extra_cfgs=True)))
    except Exception:
        emit(kind="error", where="variant s4", tb=traceback.format_exc()[-2500:])
        try:
            variants.append(("s4n", make_variant("s4n", 4, extra_cfgs=False)))
        except Exception:
            emit(kind="error", where="variant s4n", tb=traceback.format_exc()[-2500:])
    for st in (6, 8):
        try:
            variants.append((f"s{st}", make_variant(f"s{st}", st, extra_cfgs=False)))
        except Exception:
            emit(kind="error", where=f"variant s{st}", tb=traceback.format_exc()[-2500:])

    for T in TS:
        for step in STEPS:
            ids, tw, x, distinct = case(T, step)
            nbytes = sum(distinct) * EXPERT_BYTES
            n1, n2 = sum(distinct) * W1_BYTES, sum(distinct) * W2_BYTES
            row = dict(kind="moe", T=T, step=step, distinct=distinct, GB_per_layer=round(nbytes / NL / 1e9, 3))
            mw._jit_moe_wna16_marlin_module = orig_jit
            try:
                us = graph_time(served(T, ids, tw, x)) / NL
                row["served_us"] = round(us, 1); row["served_GBps"] = round(nbytes / NL / us / 1e3)
            except Exception:
                emit(kind="error", where="served", tb=traceback.format_exc()[-2000:])
            ref = []
            r, _ = mine(T, ids, tw, x, outs=ref); r(); torch.cuda.synchronize()
            ref0 = ref[0]
            for tag, mod in variants:
                mw._jit_moe_wna16_marlin_module = orig_jit if mod is None else (lambda *a, _m=mod: _m)
                knobs = [dict()]
                if tag == "orig":
                    knobs = [dict(), dict(block_m=16), dict(atomic=False)]
                elif tag in ("s4", "s4n"):
                    nc = 4 if tag == "s4" else 2
                    knobs = ([dict(env={"MV_CFG": str(i)}) for i in range(nc)] +
                             [dict(env={"MV_BPS": str(b)}) for b in (1, 2, 4)] +
                             [dict(env={"MV_CFG": "1", "MV_BPS": "4"}), dict(env={"MV_CFG": "1", "MV_BPS": "2"})])
                else:
                    knobs = [dict(), dict(env={"MV_BPS": "1"}), dict(env={"MV_BPS": "2"}), dict(env={"MV_CFG": "1"})]
                for kn in knobs:
                    env = kn.pop("env", {})
                    for k in ("MV_CFG", "MV_BPS"):
                        os.environ.pop(k, None)
                    os.environ.update(env)
                    label = tag + ("" if not kn and not env else " " + json.dumps({**kn, **env}, sort_keys=True))
                    try:
                        res = {}
                        for part, nb in (("gemm1", n1), ("gemm2", n2), ("all", nbytes)):
                            outs = [] if part == "all" else None
                            r, _ = mine(T, ids, tw, x, part=part, outs=outs, **kn)
                            us = graph_time(r) / NL
                            res[part + "_us"] = round(us, 1); res[part + "_GBps"] = round(nb / NL / us / 1e3)
                        o = []
                        r, _ = mine(T, ids, tw, x, outs=o, **kn); r(); torch.cuda.synchronize()
                        res["maxdiff_vs_ref"] = round((o[0].float() - ref0.float()).abs().max().item() /
                                                      max(ref0.float().abs().max().item(), 1e-9), 5)
                        emit(kind="moe_variant", T=T, step=step, label=label, **res)
                        summary.setdefault(f"T{T}", {}).setdefault(label, []).append(res["all_us"])
                    except Exception:
                        emit(kind="error", where=label, T=T, step=step, tb=traceback.format_exc()[-1500:])
            for k in ("MV_CFG", "MV_BPS"):
                os.environ.pop(k, None)
            mw._jit_moe_wna16_marlin_module = orig_jit
            emit(**row)
            summary.setdefault(f"T{T}", {}).setdefault("served", []).append(row.get("served_us"))
            summary.setdefault(f"T{T}", {}).setdefault("GB_per_layer", []).append(row["GB_per_layer"])
    emit(summary={T: {k: round(float(np.mean([v for v in vs if v is not None])), 2) if vs else None
                      for k, vs in d.items()} for T, d in summary.items()})


if __name__ == "__main__":
    try:
        main()
    except Exception:
        emit(kind="fatal", tb=traceback.format_exc()[-3000:])
