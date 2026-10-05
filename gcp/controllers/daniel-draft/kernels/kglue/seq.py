"""Kernel sequence of one decode iteration with readable names (5-Oct-2026). python seq.py TRACE [iter] > out"""
import gzip, json, sys, re
from exposed_names import short
ev = json.loads(gzip.open(sys.argv[1], "rb").read())["traceEvents"]
an = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") == "gpu_user_annotation"], key=lambda e: e["ts"])
ks = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") in ("kernel", "gpu_memcpy", "gpu_memset")], key=lambda e: e["ts"])
dr = [e for e in an if e["name"] == "draft" and e["dur"] > 1000]
i = int(sys.argv[2]) if len(sys.argv) > 2 else 20
t0, t1 = dr[i]["ts"], dr[i + 1]["ts"]
for a in an:
    if t0 <= a["ts"] < t1 and a["dur"] > 50: print(f"# annot {(a['ts']-t0)/1e3:8.3f} +{a['dur']/1e3:.3f} {a['name'][:60]}")
for n, e in enumerate(k for k in ks if t0 <= k["ts"] < t1):
    g = e.get("args", {}).get("grid"); s = e.get("args", {}).get("stream")
    print(f"{n:5d} {(e['ts']-t0)/1e3:8.3f} {e['dur']:6.1f} s{s} {short(e['name'])[:80]} g={g}")
