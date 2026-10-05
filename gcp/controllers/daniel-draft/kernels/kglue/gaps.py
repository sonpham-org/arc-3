"""Fully idle GPU intervals per decode iteration, attributed to (kernel that ended, kernel that started) pairs
(5-Oct-2026, Kernel optimizations thread). python gaps.py TRACE [--iters 8:32] [--top 40]"""
import argparse, gzip, json, statistics
from collections import defaultdict
from exposed_names import short

ap = argparse.ArgumentParser(); ap.add_argument("trace"); ap.add_argument("--iters", default="8:32"); ap.add_argument("--top", type=int, default=40)
a = ap.parse_args()
ev = json.loads(gzip.open(a.trace, "rb").read())["traceEvents"]
an = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") == "gpu_user_annotation"], key=lambda e: e["ts"])
ks = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") in ("kernel", "gpu_memcpy", "gpu_memset")], key=lambda e: e["ts"])
dr = [e for e in an if e["name"] == "draft" and e["dur"] > 1000]
lo, hi = (int(x) for x in a.iters.split(":")); hi = min(hi, len(dr) - 1)
agg = defaultdict(lambda: [0, 0.0]); tot = []; buckets = defaultdict(float)
for i in range(lo, hi):
    t0, t1 = dr[i]["ts"], dr[i + 1]["ts"]
    kk = [e for e in ks if t0 <= e["ts"] < t1]
    end_max, last = t0, None; idle = 0.0
    for e in kk:
        if e["ts"] > end_max and last is not None:
            g = e["ts"] - end_max
            idle += g
            key = (short(last["name"])[:45], short(e["name"])[:45])
            agg[key][0] += 1; agg[key][1] += g
            buckets["<1us" if g < 1 else "1-2us" if g < 2 else "2-5us" if g < 5 else "5-20us" if g < 20 else ">20us"] += g
        if e["ts"] + e["dur"] > end_max:
            end_max = e["ts"] + e["dur"]; last = e
    tot.append(idle)
n = hi - lo
print(f"iterations {n}: idle median {statistics.median(tot)/1e3:.3f} ms; by gap size (ms/iter):",
      {k: round(v / n / 1e3, 3) for k, v in sorted(buckets.items())})
for (p, q), (c, g) in sorted(agg.items(), key=lambda x: -x[1][1])[: a.top]:
    print(f"  {g/n:7.1f} us/iter {c/n:6.1f}x  {p}  ->  {q}")
