"""Per-iteration comparison of decode profiles across bench runs (5-Oct-2026, Kernel optimizations thread).
For each run and profile minute: median iteration wall / GPU union-busy / idle (ms), kernels per iteration, and the
per-iteration count + busy us of the kernel families kglue / klmh touch. Traces from live/_profiles/<run>/<minute>/.
  python compare_runs.py RUN [RUN ...] [--iters 8:32]
"""
import argparse
import gzip
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

CACHE = Path(r"D:\codex-work\daniel-draft\live\_profiles")
FAM = [  # (label, regex on kernel name, grid filter or None)
    ("hc_norm", r"grouped_gemma_rmsnorm_kernel", None),
    ("hc_apply_norm", r"kglue_hc_apply_norm", None),
    ("hc_combine*", r"hc_combine", None),
    ("hc_mix_chain", r"64x64_32x6_tn|relu_bf16_64x64_32x10_tn|splitKreduce_kernel<32, 16, int, float, __nv_bfloat16, float, __nv_bfloat16, false|triton_poi_fused_div_silu|triton_poi_fused_mean_mul_sigmoid", None),
    ("khc_mix", r"_khc_mix_|_kglue_mix_down_reduce", None),
    ("topk_sum", r"topk_sum_kernel", None),
    ("gate_sig", r"_fused_gate_sigmoid_mul_add|_kglue_topk_sum_gate", None),
    ("idx_fill", r"FillFunctor", "[1360, 1, 1]"),
    ("fill_g1", r"FillFunctor", "[1, 1, 1]"),
    ("kv_div", r"BUnaryFunctor", None),
    ("bf16_copy_g1", r"bfloat16_copy_kernel_cuda", "[1, 1, 1]"),
    ("lm_head", r"256x64_32x4_tn|BF16TripleBitmap|ZipGEMM|Bitmap", None),
    ("kfast", r"_kfast_skinny_gemm_kernel", None),
    ("marlin", r"Marlin", None),
    ("indexer", r"^kernel_kernel$", None),
    ("k8_attn", r"_k8_fused_kernel", None),
    ("topk_idx", r"fast_topk_kernel", None),
]
CONTENT = ("marlin", "indexer", "k8_attn", "topk_idx")   # time depends on routing / context, not on our changes


def iters(trace, lo, hi):
    ev = json.loads(gzip.open(trace, "rb").read())["traceEvents"]
    an = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") == "gpu_user_annotation"], key=lambda e: e["ts"])
    ks = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") in ("kernel", "gpu_memcpy", "gpu_memset")],
                key=lambda e: e["ts"])
    # iteration = from one long target-verify step annotation to the next (the 'draft' ranges split differently
    # once kernels launch with PDL)
    dr = []
    for e in an:   # the same range can be recorded on two streams: keep one per iteration
        if e["name"].startswith("step[TARGET_VERIFY") and e["dur"] > 8000 and (not dr or e["ts"] > dr[-1]["ts"] + 5000):
            dr.append(e)
    out = []
    for i in range(lo, min(hi, len(dr) - 1)):
        t0, t1 = dr[i]["ts"], dr[i + 1]["ts"]
        kk = [e for e in ks if t0 <= e["ts"] < t1]
        iv = sorted((e["ts"], e["ts"] + e["dur"]) for e in kk)
        union, cur_s, cur_e = 0.0, None, None
        for s, e in iv:
            if cur_e is None or s > cur_e:
                if cur_e is not None:
                    union += cur_e - cur_s
                cur_s, cur_e = s, e
            else:
                cur_e = max(cur_e, e)
        if cur_e is not None:
            union += cur_e - cur_s
        fam = defaultdict(lambda: [0, 0.0])
        for e in kk:
            g = str(e.get("args", {}).get("grid"))
            for lab, rx, gf in FAM:
                if re.search(rx, e["name"]) and (gf is None or g == gf):
                    fam[lab][0] += 1
                    fam[lab][1] += e["dur"]
        out.append(dict(wall=(t1 - t0) / 1e3, union=union / 1e3, n=len(kk), fam=fam))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--iters", default="8:32")
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.iters.split(":"))
    rows = {}
    for run in a.runs:
        for mdir in sorted((CACHE / run).glob("m*")):
            tr = sorted(mdir.glob("*.trace.json.gz"))
            if not tr:
                continue
            its = iters(tr[0], lo, hi)
            if not its:
                continue
            med = lambda f: statistics.median(f(x) for x in its)
            fam = {lab: (med(lambda x, l=lab: x["fam"][l][0] if l in x["fam"] else 0),
                         med(lambda x, l=lab: x["fam"][l][1] if l in x["fam"] else 0.0)) for lab, _, _ in FAM}
            rows[(run, mdir.name)] = dict(wall=med(lambda x: x["wall"]), union=med(lambda x: x["union"]),
                                          idle=med(lambda x: x["wall"] - x["union"]), n=med(lambda x: x["n"]), fam=fam)
    keys = list(rows)
    print(f"{'run':34s} {'min':4s} {'wall':>6s} {'busy':>6s} {'idle':>5s} {'kern':>5s} {'content':>7s} {'wall-content':>12s}")
    for k in keys:
        r = rows[k]
        c = sum(r["fam"][f][1] for f in CONTENT) / 1e3
        print(f"{k[0][:34]:34s} {k[1]:4s} {r['wall']:6.2f} {r['union']:6.2f} {r['idle']:5.2f} {r['n']:5.0f} {c:7.2f} "
              f"{r['wall'] - c:12.2f}")
    print("\nfamily: count / busy us per iteration (median)")
    print(f"{'family':14s}" + "".join(f" {k[0][-14:]+'/'+k[1]:>22s}" for k in keys))
    for lab, _, _ in FAM:
        print(f"{lab:14s}" + "".join(f" {rows[k]['fam'][lab][0]:8.0f} /{rows[k]['fam'][lab][1]:9.1f}  " for k in keys))


if __name__ == "__main__":
    main()
