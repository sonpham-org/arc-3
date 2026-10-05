"""Per-iteration decode stats from a bench run's profiler trace (3-Oct-2026, daniel-draft kernels).

An iteration = draft (3 MTP steps) + target verify + draft_extend, delimited by consecutive 'draft' GPU annotations.
Prints median iteration wall time, median GPU kernel-busy time, and per-iteration kernel ms for kernel families
(dense GEMM cuBLAS / skinny / Daniel low-M, Marlin, hc_combine, hc mix chain, top-k sum, others).
  python iter_stats.py RUN [RUN ...]       (traces fetched by live/profile_report.py's cache layout)
"""
import gzip
import json
import re
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

G = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
B = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"
CACHE = Path(r"D:\codex-work\daniel-draft\live\_profiles")
FAM = [
    ("marlin_moe", r"marlin"),
    ("skinny_gemm", r"_kfast_skinny_gemm_kernel"),
    ("lowm_gemm_daniel", r"_sm120_lowm_gemm_kernel"),
    ("cublas_gemm", r"cutlass_80|gemv|cublas|splitkreduce"),
    ("hc_combine", r"hc_combine"),
    ("hc_mix", r"hc_mix|triton_poi_fused_div_silu|triton_poi_fused_mean_mul_sigmoid"),
    ("topk_sum", r"moe_sum_reduce|topk_sum"),
    ("gdn", r"gdn|causal_conv1d|fused_qkvzba|layer_norm_fwd"),
    ("qsa", r"kernel_kernel|_compact_kv|kernel_mha|qsa|fast_topk|store_kvcache|_k8_fused|_k8u_|_kf_qsa"),
]
FRX = [(f, re.compile(p, re.I)) for f, p in FAM]


def fam(name):
    for f, rx in FRX:
        if rx.search(name):
            return f
    return "other"


def traces(run):
    dst = CACHE / run
    dst.mkdir(parents=True, exist_ok=True)
    subprocess.run(G + ["storage", "rsync", "-r", f"{B}/{run}/working/profile", str(dst)], capture_output=True, timeout=900)
    return sorted(dst.rglob("*.trace.json*"))


def stats(path):
    ev = json.loads(gzip.open(path, "rb").read())["traceEvents"]
    dr = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") == "gpu_user_annotation"
                 and e["name"] == "draft"], key=lambda e: (e["ts"], -e["dur"]))
    an = []   # top-level "draft" ranges only (at 7+ draft steps the per-step "draft" ranges also exceed 1 ms)
    for e in dr:
        if an and e["ts"] + e["dur"] <= an[-1]["ts"] + an[-1]["dur"]:
            continue
        an.append(e)
    an = [e for e in an if e["dur"] > 1000]
    if not an:   # spec decoding off (W1): iterations start at the top-level "step[..." GPU ranges
        st = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") == "gpu_user_annotation"
                     and e["name"].startswith("step[")], key=lambda e: (e["ts"], -e["dur"]))
        for e in st:
            if an and e["ts"] + e["dur"] <= an[-1]["ts"] + an[-1]["dur"]:
                continue
            an.append(e)
    verify = [e for e in ev if e.get("ph") == "X" and e.get("cat") == "gpu_user_annotation"
              and e["name"].startswith("step[TARGET_VERIFY") and e["dur"] > 5000]
    k = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") in ("kernel", "gpu_memcpy", "gpu_memset")],
               key=lambda e: e["ts"])
    its, busy, fams, bs = [], [], defaultdict(list), []
    j = 0
    for a, b in zip(an, an[1:]):
        if b["ts"] - a["ts"] > 80000:  # a prefill or stall in between: not a clean decode iteration
            continue
        while j < len(k) and k[j]["ts"] < a["ts"]:
            j += 1
        jj, f = j, defaultdict(float)
        while jj < len(k) and k[jj]["ts"] < b["ts"]:
            f[fam(k[jj]["name"])] += k[jj]["dur"]
            jj += 1
        its.append((b["ts"] - a["ts"]) / 1e3)
        busy.append(sum(f.values()) / 1e3)
        for kk in set(list(f) + [x for x, _ in FAM] + ["other"]):
            fams[kk].append(f.get(kk, 0.0) / 1e3)
        v = [e["name"] for e in verify if a["ts"] <= e["ts"] < b["ts"]]
        bs.append(v[0] if v else "?")
    if not its:
        return {"trace": path.name, "note": "no clean iterations"}
    return {"trace": path.parent.name, "iterations": len(its), "verify_batches": sorted(set(bs)),
            "iter_ms_median": round(statistics.median(its), 2), "busy_ms_median": round(statistics.median(busy), 2),
            "family_ms_median": {f: round(statistics.median(v), 3) for f, v in sorted(fams.items())}}


if __name__ == "__main__":
    for run in sys.argv[1:]:
        for p in traces(run):
            print(run, json.dumps(stats(p)))
