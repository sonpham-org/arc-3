import gzip, json, sys, re
tr = json.loads(gzip.open(sys.argv[1], "rb").read()); ev = tr["traceEvents"]
an = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") == "gpu_user_annotation" and "Compiled" not in e["name"]], key=lambda e: e["ts"])
k = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") in ("kernel", "gpu_memcpy", "gpu_memset")], key=lambda e: e["ts"])
t0 = an[0]["ts"]
for e in an[200:260]:
    print(f"{(e['ts']-t0)/1e3:9.3f} {e['dur']/1e3:7.3f} {e['name'][:60]} tid={e.get('tid')}")
