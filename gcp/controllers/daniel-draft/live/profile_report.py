"""Decode-profile report for Daniel's server (3-Oct-2026, daniel-draft; Son: "faster MoE").

Reads torch-profiler traces written by make_bench_notebook.py --profile-at (working/profile/m<minute>/*.trace.json.gz,
CPU+GPU, N forward steps at >= slots-1 running requests) and prints, per trace: the profiled window, GPU busy time and
idle gaps, then GPU kernel time by category (MoE GEMMs, MoE routing, attention, linear-attention layers, dense GEMMs,
norms/elementwise, sampling/spec, memory) in ms per step and share of the window, and the top kernels by total time.
  python profile_report.py RUN [--top 25]          (downloads the run's profile/ folder to the scratch dir)
  python profile_report.py --local PATH.trace.json.gz [...]
"""
import argparse
import gzip
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

G = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
B = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"
CACHE = Path(r"D:\codex-work\daniel-draft\live\_profiles")

CATS = [  # first match wins; patterns are lower-case regexes over the kernel name
    ("moe_gemm", r"marlin|moe_wna16|fused_moe_kernel|grouped_gemm|cutlass_moe|moe_gemm"),
    ("moe_route", r"topk|top_k_softmax|moe_align|count_and_sort|moe_sum|expert|permute|unpermute|scatter_add|gather_moe"),
    ("linear_attn", r"gated_delta|delta_rule|chunk_|fused_recurrent|causal_conv|conv1d|fla_|gdn|mamba|ssm|selective|kda|l2norm"),
    ("attention", r"flashinfer|batchprefill|batchdecode|prefillwithkv|decodewithkv|attention|attn|qsa|indexer|sparse|mla|merge_state|rope|rotary"),
    ("sampling_spec", r"sampl|top_p|softmax|argmax|verify|accept|speculative|tree|multinomial|renorm|logits|penalt"),
    ("dense_gemm", r"gemm|gemv|cutlass|cublas|xmma|sm\d+_|lowm|matmul|ampere|hopper|blackwell|splitk|wgmma"),
    ("norm_elementwise", r"norm|elementwise|vectorized|act_and_mul|silu|gelu|add|mul|copy|fill|cast|index|cat|reduce|where|clamp"),
]
CRX = [(c, re.compile(p)) for c, p in CATS]


def category(name):
    n = name.lower()
    for c, rx in CRX:
        if rx.search(n):
            return c
    return "other"


def fetch(run):
    dst = CACHE / run
    dst.mkdir(parents=True, exist_ok=True)
    subprocess.run(G + ["storage", "rsync", "-r", f"{B}/{run}/working/profile", str(dst)], capture_output=True, timeout=900)
    return sorted(dst.rglob("*.trace.json*")), dst


def load(path):
    raw = gzip.open(path, "rb").read() if str(path).endswith(".gz") else Path(path).read_bytes()
    return json.loads(raw)


def report(path, top):
    tr = load(path)
    ev = tr["traceEvents"] if isinstance(tr, dict) else tr
    gpu = [e for e in ev if e.get("ph") == "X" and e.get("cat") in ("kernel", "gpu_memcpy", "gpu_memset")]
    # decode only: drop kernels inside prefill (EXTEND) step ranges; count verify iterations from CPU annotations
    pre = [(e["ts"], e["ts"] + e["dur"]) for e in ev if e.get("ph") == "X" and e.get("cat") == "gpu_user_annotation"
           and str(e.get("name", "")).startswith("step[EXTEND")]
    if pre:
        gpu = [e for e in gpu if not any(a <= e["ts"] < b for a, b in pre)]
    n_verify = sum(1 for e in ev if e.get("ph") == "X" and e.get("cat") == "user_annotation"
                   and str(e.get("name", "")).startswith("step[TARGET_VERIFY"))
    if not gpu:
        print(f"{path.name}: no GPU events"); return
    steps = [e for e in ev if e.get("ph") == "X" and re.search(r"ProfilerStep#|profiler_step", e.get("name", ""))]
    t0 = min(e["ts"] for e in gpu)
    t1 = max(e["ts"] + e["dur"] for e in gpu)
    win = (t1 - t0) / 1000.0
    # GPU busy = union of kernel intervals (streams can overlap)
    iv = sorted((e["ts"], e["ts"] + e["dur"]) for e in gpu)
    busy, cs, ce = 0.0, iv[0][0], iv[0][1]
    for s, e in iv[1:]:
        if s > ce:
            busy += ce - cs
            cs, ce = s, e
        else:
            ce = max(ce, e)
    busy = (busy + ce - cs) / 1000.0
    nsteps = n_verify or len(steps) or None
    by_cat, by_name, cnt = defaultdict(float), defaultdict(float), defaultdict(int)
    for e in gpu:
        c = "memory" if e["cat"] != "kernel" else category(e["name"])
        by_cat[c] += e["dur"] / 1000.0
        by_name[(c, e["name"][:110])] += e["dur"] / 1000.0
        cnt[(c, e["name"][:110])] += 1
    ksum = sum(by_cat.values())
    per = (lambda ms: ms / nsteps) if nsteps else (lambda ms: float("nan"))
    print(f"\n== {path.name}: window {win:.0f} ms, GPU busy {busy:.0f} ms ({busy / win:.0%}), idle {win - busy:.0f} ms; "
          f"kernel time {ksum:.0f} ms (prefill ranges dropped: {len(pre)}); verify iterations {nsteps}; kernel ms per "
          f"iteration {ksum / nsteps if nsteps else float('nan'):.1f}")
    print(f"{'category':18s} {'ms':>8s} {'ms/step':>8s} {'of busy':>8s}")
    for c, ms in sorted(by_cat.items(), key=lambda x: -x[1]):
        print(f"{c:18s} {ms:8.0f} {per(ms):8.2f} {ms / ksum:8.1%}")
    print(f"\ntop {top} kernels by total time:")
    for (c, n), ms in sorted(by_name.items(), key=lambda x: -x[1])[:top]:
        k = cnt[(c, n)]
        print(f"  {ms:7.1f} ms {k:6d}x {1000 * ms / k:8.1f} us  [{c}] {n}")
    other = sorted(((ms, n) for (c, n), ms in by_name.items() if c == "other"), reverse=True)[:8]
    if other:
        print("  uncategorised:", "; ".join(f"{n[:60]} {ms:.1f}" for ms, n in other))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run", nargs="?")
    ap.add_argument("--local", nargs="*", default=[])
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args()
    paths = [Path(p) for p in a.local]
    if a.run:
        found, dst = fetch(a.run)
        log = dst / "log.txt"
        if log.exists():
            print(log.read_text())
        paths += found
    if not paths:
        print("no traces found"); return 1
    for p in paths:
        report(p, a.top)


if __name__ == "__main__":
    sys.exit(main())
