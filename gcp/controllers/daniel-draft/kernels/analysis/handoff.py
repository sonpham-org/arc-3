"""Per-iteration wall clock, GPU idle and CPU-vs-GPU lead at each graph launch (4-Oct-2026, daniel-draft idle hunt).

wall      = period of the scheduler's run_batch (CPU user annotation), median
gpu_idle  = iteration time with no GPU activity on any stream (union), median
lead      = for each cudaGraphLaunch (draft / verify / draft_extend): GPU start of the graph's first kernel minus the
            end of the CPU launch call. > 0: the GPU was still busy with earlier work when the launch landed (CPU ahead);
            ~0 with an idle gap before it: the GPU waited for the CPU (launch on the critical path).
  python handoff.py PATH.trace.json.gz [...]
"""
import gzip
import json
import statistics
import sys
from bisect import bisect_left
from collections import defaultdict


def analyse(path):
    ev = json.loads(gzip.open(path, "rb").read())["traceEvents"]
    gpu = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") in ("kernel", "gpu_memcpy", "gpu_memset")],
                 key=lambda e: e["ts"])
    if not gpu:   # CUPTI off: the CPU-side scheduler period (wall per iteration) is still in the trace
        rb = sorted(e["ts"] for e in ev if e.get("ph") == "X" and e.get("cat") == "user_annotation"
                    and e["name"] == "scheduler.run_batch")
        w = [(b - a) / 1e3 for a, b in zip(rb, rb[1:]) if b - a < 80000]
        out = {"trace": path, "note": "no GPU events (CUPTI off)"}
        if w:
            out.update(iterations=len(w), wall_ms_median=round(statistics.median(w), 2))
        return out
    by_corr = defaultdict(list)
    for k in gpu:
        by_corr[k["args"].get("correlation")].append(k)
    rb = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") == "user_annotation"
                 and e["name"] == "scheduler.run_batch"], key=lambda e: e["ts"])
    starts = [e["ts"] for e in rb]
    walls = [(b - a) / 1e3 for a, b in zip(starts, starts[1:]) if b - a < 80000]
    gst = [k["ts"] for k in gpu]
    idles = []
    for a, b in zip(starts, starts[1:]):
        if b - a > 80000:
            continue
        ks = gpu[bisect_left(gst, a - 200000):bisect_left(gst, b)]
        busy = []
        for k in ks:
            s, f = max(k["ts"], a), min(k["ts"] + k["dur"], b)
            if f <= s:
                continue
            if busy and s <= busy[-1][1]:
                busy[-1][1] = max(busy[-1][1], f)
            else:
                busy.append([s, f])
        idles.append(((b - a) - sum(f - s for s, f in busy)) / 1e3)
    # graph launches: which graph (by the python caller name), lead
    py = [e for e in ev if e.get("ph") == "X" and e.get("cat") == "python_function"
          and ("execute" in e["name"] or "_replay_graph" in e["name"])]
    launches = [e for e in ev if e.get("ph") == "X" and e.get("cat") == "cuda_runtime" and e["name"] == "cudaGraphLaunch"]
    leads = defaultdict(list)
    for l in launches:
        ks = by_corr.get(l["args"].get("correlation"))
        if not ks:
            continue
        first = min(k["ts"] for k in ks)
        enc = [p for p in py if p.get("tid") == l.get("tid") and p["ts"] <= l["ts"] and p["ts"] + p["dur"] >= l["ts"]]
        enc.sort(key=lambda p: p["dur"])
        who = next((p["name"].split("/")[-1] for p in enc if "runner" in p["name"]), "?")
        # idle just before the graph's first kernel
        i = bisect_left(gst, first)
        prev_end = max((k["ts"] + k["dur"] for k in gpu[max(0, i - 400):i]), default=first)
        leads[who].append(((first - (l["ts"] + l["dur"])) / 1e3, max(0.0, first - prev_end) / 1e3, l["dur"] / 1e3))
    out = {"trace": path.split("/")[-1][:40], "iterations": len(walls), "wall_ms_median": round(statistics.median(walls), 2),
           "wall_ms_mean": round(statistics.mean(walls), 2), "gpu_idle_ms_median": round(statistics.median(idles), 2)}
    for who, v in leads.items():
        out[f"launch[{who[:40]}]"] = {"n": len(v), "lead_ms_median": round(statistics.median(x[0] for x in v), 3),
                                      "idle_before_ms_median": round(statistics.median(x[1] for x in v), 3),
                                      "launch_call_ms_median": round(statistics.median(x[2] for x in v), 3)}
    return out


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(json.dumps(analyse(p), indent=1))
