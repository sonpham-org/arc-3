"""Exposed GPU time per kernel class (5-Oct-2026, Kernel optimizations thread).
For each decode iteration (between consecutive 'draft' annotations) and each kernel: exposed = the part of its run where
no OTHER kernel is running (a proxy for what removing it would save; overlapped side-stream work is free-ish).
Prints per (kernel, grid, stream-role) totals per iteration: count, busy us, exposed us; median over iterations.
Also iteration wall, busy, union-busy, idle.
  python exposed.py TRACE.json.gz [--iters 10:30] [--top 80] [--glue]
"""
import argparse, gzip, json, re, statistics
from collections import defaultdict

MAJOR = re.compile(r"Marlin|_kfast_skinny|gdn_wide_vec|kernel_kernel$|_k8_fused|GdnDecodeKernel|gdn_decode_bf16|"
                   r"cutlass_80_tensorop|cutlass_80_wmma|Kernel2|_hc_mix_persistent|hc_combine|_khc_mix|causal_conv1d|"
                   r"sampling|speculative_sampling|fast_topk|qsa_index|RadixTopK")

def short(n):
    n2 = re.sub(r"\(.*", "", n)
    m = re.search(r"cutlass_80_\w+", n2)
    if m: return m.group(0).replace("cutlass_80_", "c80_")
    if "Marlin<" in n2: return "Marlin"
    m = re.search(r"at::native::(\w+)<.*?at::native::(?:\(anonymous namespace\)::)?(\w+)", n)
    if m: return f"aten::{m.group(1)}/{m.group(2)}"
    return n2.replace("void ", "")[:70]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("trace"); ap.add_argument("--iters", default="8:32")
    ap.add_argument("--top", type=int, default=80); ap.add_argument("--glue", action="store_true")
    a = ap.parse_args()
    ev = json.loads(gzip.open(a.trace, "rb").read())["traceEvents"]
    an = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") == "gpu_user_annotation"], key=lambda e: e["ts"])
    ks = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") in ("kernel", "gpu_memcpy", "gpu_memset")], key=lambda e: e["ts"])
    dr = [e for e in an if e["name"] == "draft" and e["dur"] > 1000]
    lo, hi = (int(x) for x in a.iters.split(":"))
    hi = min(hi, len(dr) - 1)
    per = defaultdict(lambda: defaultdict(list))   # key -> metric -> per-iter values
    its = []
    for i in range(lo, hi):
        t0, t1 = dr[i]["ts"], dr[i + 1]["ts"]
        kk = [e for e in ks if t0 <= e["ts"] < t1]
        # sweep: coverage count over time
        pts = []
        for j, e in enumerate(kk):
            pts.append((e["ts"], 1, j)); pts.append((e["ts"] + e["dur"], -1, j))
        pts.sort(key=lambda p: (p[0], p[1]))
        active = set(); last = None; expo = defaultdict(float); union = 0.0
        for t, d, j in pts:
            if last is not None and active:
                span = t - last
                union += span
                if len(active) == 1:
                    expo[next(iter(active))] += span
            if d == 1: active.add(j)
            else: active.discard(j)
            last = t
        its.append(dict(wall=(t1 - t0), busy=sum(e["dur"] for e in kk), union=union, n=len(kk)))
        acc = defaultdict(lambda: [0, 0.0, 0.0])
        for j, e in enumerate(kk):
            key = (short(e["name"]), str(e.get("args", {}).get("grid")), "major" if MAJOR.search(e["name"]) else "glue")
            acc[key][0] += 1; acc[key][1] += e["dur"]; acc[key][2] += expo[j]
        for key, (c, b, x) in acc.items():
            per[key]["n"].append(c); per[key]["busy"].append(b); per[key]["exp"].append(x)
    N = len(its)
    med = lambda xs: statistics.median(xs + [0] * (N - len(xs)))
    print(f"iterations {N}: wall {med([x['wall'] for x in its])/1e3:.2f} ms, busy {med([x['busy'] for x in its])/1e3:.2f}, "
          f"union {med([x['union'] for x in its])/1e3:.2f}, idle {med([x['wall']-x['union'] for x in its])/1e3:.2f}, "
          f"kernels {med([x['n'] for x in its]):.0f}")
    rows = [(k, med(v["n"]), med(v["busy"]), med(v["exp"])) for k, v in per.items()]
    for cls in ("glue", "major"):
        sel = [r for r in rows if r[0][2] == cls]
        print(f"\n== {cls}: n {sum(r[1] for r in sel):.0f}, busy {sum(r[2] for r in sel)/1e3:.2f} ms, exposed {sum(r[3] for r in sel)/1e3:.2f} ms")
        if cls == "major" and a.glue: continue
        for k, n, b, x in sorted(sel, key=lambda r: -r[3])[: a.top]:
            print(f"  {x:8.1f} exp {b:8.1f} busy {n:5.0f}x  {k[0][:72]}  g={k[1]}")

main()
