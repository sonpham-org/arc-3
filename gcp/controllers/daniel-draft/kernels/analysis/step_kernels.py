import gzip, json, sys, re
from collections import defaultdict
tr = json.loads(gzip.open(sys.argv[1], "rb").read()); ev = tr["traceEvents"]
an = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") == "gpu_user_annotation" and "Compiled" not in e["name"]], key=lambda e: e["ts"])
k = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") in ("kernel", "gpu_memcpy", "gpu_memset")], key=lambda e: e["ts"])
# pick the iteration: 'draft' on tid 13 index N, until the next 'draft' on main tid
dr = [e for e in an if e["name"] == "draft" and e["dur"] > 1000]
i = int(sys.argv[2]) if len(sys.argv) > 2 else len(dr) // 2
a, b = dr[i]["ts"], dr[i + 1]["ts"]
ks = [e for e in k if a <= e["ts"] < b]
def short(n):
    n = re.sub(r"\(.*", "", n)
    m = re.search(r"cutlass_80_\w+", n)
    if m: return m.group(0).replace("cutlass_80_", "c80_")
    if "Marlin<" in n:
        return "Marlin" + re.search(r"Marlin<([^>]*)>", n).group(1).split(",", 3)[-1][:40]
    return n[:60]
print("iteration", (b - a) / 1e3, "ms, kernels", len(ks), "busy", sum(e["dur"] for e in ks) / 1e3)
mode = sys.argv[3] if len(sys.argv) > 3 else "seq"
if mode == "seq":
    t0 = a
    prev = None; run = 0
    for e in ks:
        g = e.get("args", {}).get("grid"); bl = e.get("args", {}).get("block")
        print(f"{(e['ts']-t0)/1e3:8.3f} {e['dur']:7.1f} {short(e['name'])} g={g} b={bl} s={e.get('args',{}).get('stream')}")
else:
    agg = defaultdict(lambda: [0, 0.0])
    for e in ks:
        key = (short(e["name"]), str(e.get("args", {}).get("grid")))
        agg[key][0] += 1; agg[key][1] += e["dur"]
    for key, (c, d) in sorted(agg.items(), key=lambda x: -x[1][1]):
        print(f"{d:9.1f} us {c:4d} x {d/c:7.1f}  {key[0]}  g={key[1]}")
