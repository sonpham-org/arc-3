"""Kernel table from a torch-profiler trace: per kernel name count, total ms, mean us, grid/block; plus CUDA-graph info."""
import gzip, json, sys, re
from collections import defaultdict
p = sys.argv[1]
tr = json.loads(gzip.open(p, "rb").read())
ev = tr["traceEvents"]
cats = defaultdict(int)
for e in ev:
    cats[(e.get("ph"), e.get("cat"))] += 1
print(sorted(cats.items(), key=lambda x: -x[1])[:30])
k = [e for e in ev if e.get("ph") == "X" and e.get("cat") in ("kernel", "gpu_memcpy", "gpu_memset")]
t0 = min(e["ts"] for e in k); t1 = max(e["ts"] + e["dur"] for e in k)
print("window ms", (t1 - t0) / 1e3, "kernels", len(k))
agg = defaultdict(lambda: [0, 0.0, set()])
for e in k:
    a = agg[e["name"]]
    a[0] += 1; a[1] += e["dur"]
    args = e.get("args", {})
    a[2].add((str(args.get("grid")), str(args.get("block"))))
tot = sum(v[1] for v in agg.values())
print("total kernel ms", tot / 1e3)
for n, (c, d, gb) in sorted(agg.items(), key=lambda x: -x[1][1])[:int(sys.argv[2]) if len(sys.argv) > 2 else 60]:
    print(f"{d/1e3:9.2f} ms {c:6d} x {d/c:8.1f} us  {n[:150]}  {list(gb)[:3]}")
