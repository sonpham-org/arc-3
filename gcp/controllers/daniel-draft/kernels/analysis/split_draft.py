"""Per-iteration split of the decode step into draft / draft_extend / target verify (4-Oct-2026, daniel-draft
kernels; width curve for DFlash). GPU-side ranges from the gpu_user_annotation "draft" (top level) and
"draft_extend" ranges; verify = top-level draft start to next top-level draft start minus both.
  python split_draft.py RUN:W [RUN:W ...]"""
import gzip
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import iter_stats as I  # noqa: E402


def top(ev, name):
    dr = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") == "gpu_user_annotation" and e["name"] == name],
                key=lambda e: (e["ts"], -e["dur"]))
    out = []
    for e in dr:
        if out and e["ts"] + e["dur"] <= out[-1]["ts"] + out[-1]["dur"]:
            continue
        out.append(e)
    return out


for arg in sys.argv[1:]:
    run, w = arg.split(":")
    res = []
    for p in I.traces(run):
        ev = json.loads(gzip.open(p, "rb").read())["traceEvents"]
        d = [e for e in top(ev, "draft") if e["dur"] > 300]
        x = top(ev, "draft_extend")
        for a, b in zip(d, d[1:]):
            it = (b["ts"] - a["ts"]) / 1e3
            if it > 80:
                continue
            de = sum(e["dur"] for e in x if a["ts"] <= e["ts"] < b["ts"]) / 1e3
            res.append((it, a["dur"] / 1e3, de, it - a["dur"] / 1e3 - de))
    if not res:
        print(run, "no GPU ranges"); continue
    m = [round(statistics.median(r[i] for r in res), 2) for i in range(4)]
    print(f"W={w:>3s} iter {m[0]:6.2f}  draft {m[1]:5.2f}  draft_extend {m[2]:5.2f}  verify+rest {m[3]:6.2f}  n={len(res)}  {run}")
