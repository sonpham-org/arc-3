"""CPU timeline of one decode iteration vs GPU activity (4-Oct-2026, daniel-draft; idle-GPU hunt).
Prints, for the CPU thread(s) that launch GPU work, the sequence of spans at a chosen depth (python_function /
user_annotation), plus every cudaStreamSynchronize / cudaGraphLaunch with its python caller chain, and the GPU
busy/idle state at those moments.
  python cpu_timeline.py PATH.trace.json.gz [--iter 10] [--maxdepth 6]"""
import argparse
import gzip
import json
from bisect import bisect_left
from collections import defaultdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--iter", type=int, default=10)
    ap.add_argument("--min-dur", type=float, default=150.0)
    a = ap.parse_args()
    ev = json.loads(gzip.open(a.trace, "rb").read())["traceEvents"]
    drafts = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") == "gpu_user_annotation"
                     and e["name"] == "draft" and e["dur"] > 1000], key=lambda e: e["ts"])
    its = [(x, y) for x, y in zip(drafts, drafts[1:]) if y["ts"] - x["ts"] < 80000]
    x, y = its[a.iter]
    t0, t1 = x["ts"] - 3000, y["ts"]
    gpu = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") in ("kernel", "gpu_memcpy", "gpu_memset")
                  and t0 <= e["ts"] < t1], key=lambda e: e["ts"])
    # GPU busy intervals
    busy = []
    for k in gpu:
        s, f = k["ts"], k["ts"] + k["dur"]
        if busy and s <= busy[-1][1]:
            busy[-1][1] = max(busy[-1][1], f)
        else:
            busy.append([s, f])
    idle = [(busy[i][1], busy[i + 1][0]) for i in range(len(busy) - 1) if busy[i + 1][0] - busy[i][1] > 30]
    print(f"iteration {a.iter}: {(y['ts'] - x['ts']) / 1e3:.2f} ms; GPU idle gaps > 30 us: "
          f"{sum(b - a_ for a_, b in idle) / 1e3:.2f} ms in {len(idle)} gaps")
    for s, f in idle:
        print(f"   idle {s - x['ts']:+9.0f} .. {f - x['ts']:+9.0f} us  ({f - s:6.0f} us)")
    rt = [e for e in ev if e.get("ph") == "X" and e.get("cat") == "cuda_runtime" and t0 <= e["ts"] < t1]
    tids = defaultdict(float)
    for e in rt:
        tids[e.get("tid")] += 1
    py = [e for e in ev if e.get("ph") == "X" and e.get("cat") in ("python_function", "user_annotation")
          and t0 <= e["ts"] < t1 and e["dur"] >= a.min_dur]
    for tid in sorted(tids, key=lambda t: -tids[t])[:3]:
        print(f"\n--- CPU thread {tid} ({int(tids[tid])} runtime calls in window): spans >= {a.min_dur:.0f} us, "
              f"outermost first per start time ---")
        lst = sorted([e for e in py if e.get("tid") == tid], key=lambda e: (e["ts"], -e["dur"]))
        stack = []
        for e in lst:
            while stack and e["ts"] >= stack[-1]["ts"] + stack[-1]["dur"]:
                stack.pop()
            depth = len(stack)
            stack.append(e)
            if depth <= 7:
                print(f"{'  ' * depth}{e['ts'] - x['ts']:+9.0f} {e['dur']:8.0f} us  {e['name'][:110]}")
        for e in sorted([r for r in rt if r.get("tid") == tid and ("Synchronize" in r["name"] or "GraphLaunch" in r["name"])],
                        key=lambda r: r["ts"]):
            print(f"   [rt] {e['ts'] - x['ts']:+9.0f} {e['dur']:8.0f} us  {e['name']}")


if __name__ == "__main__":
    main()
