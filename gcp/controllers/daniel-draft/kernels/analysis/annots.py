import gzip, json, sys
from collections import Counter
tr = json.loads(gzip.open(sys.argv[1], "rb").read()); ev = tr["traceEvents"]
an = [e for e in ev if e.get("ph") == "X" and e.get("cat") == "gpu_user_annotation"]
print(Counter(e["name"] for e in an).most_common(40))
ua = [e for e in ev if e.get("ph") == "X" and e.get("cat") == "user_annotation"]
print(Counter(e["name"] for e in ua).most_common(40))
