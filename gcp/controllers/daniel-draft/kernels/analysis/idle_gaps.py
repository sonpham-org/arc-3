"""Where does the GPU sit idle in a decode iteration? (4-Oct-2026, daniel-draft kfuse; Son: the ~3.5 ms idle)

For each steady-state iteration (consecutive 'draft' GPU annotations < 80 ms apart) of a torch-profiler trace:
  - GPU idle gaps (no kernel / memcpy / memset on ANY stream) >= MIN_GAP_US
  - for each gap: the GPU op that ends it, the CPU runtime call that launched it (correlation id), how long before
    the gap's end the launch happened (launch-bound if the launch came late), and what the launching CPU thread was
    doing during the gap (innermost python_function / user_annotation spans active over the gap, by overlap)
  - synchronizing runtime calls (cudaStreamSynchronize, cudaEventSynchronize, cudaDeviceSynchronize, D2H memcpy)
    and their durations
Prints per-iteration idle totals and a ranked table of gap causes (ms per iteration).
  python idle_gaps.py PATH.trace.json.gz [--min-gap 10] [--iters 20]
"""
import argparse
import gzip
import json
import statistics
from bisect import bisect_left, bisect_right
from collections import defaultdict


def load(p):
    return json.loads(gzip.open(p, "rb").read() if p.endswith(".gz") else open(p, "rb").read())["traceEvents"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--min-gap", type=float, default=10.0)
    ap.add_argument("--iters", type=int, default=25)
    a = ap.parse_args()
    ev = load(a.trace)
    gpu = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") in ("kernel", "gpu_memcpy", "gpu_memset")],
                 key=lambda e: e["ts"])
    rt = [e for e in ev if e.get("ph") == "X" and e.get("cat") in ("cuda_runtime", "cuda_driver")]
    by_corr = {e["args"].get("correlation"): e for e in rt if "correlation" in e.get("args", {})}
    spans = [e for e in ev if e.get("ph") == "X" and e.get("cat") in ("python_function", "user_annotation", "cpu_op")]
    spans_by_tid = defaultdict(list)
    for e in spans:
        spans_by_tid[(e.get("pid"), e.get("tid"))].append(e)
    for k in spans_by_tid:
        spans_by_tid[k].sort(key=lambda e: e["ts"])
    starts_by_tid = {k: [e["ts"] for e in v] for k, v in spans_by_tid.items()}
    ann = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") == "gpu_user_annotation"
                  and e["name"] == "draft" and e["dur"] > 1000], key=lambda e: e["ts"])
    syncs = [e for e in rt if any(s in e["name"] for s in ("Synchronize", "cudaMemcpy", "cuMemcpyDtoH"))]
    gstarts = [e["ts"] for e in gpu]

    def active_spans(tid_key, t0, t1):
        """Spans on this CPU thread overlapping [t0, t1], innermost (shortest) first, with overlap us."""
        lst = spans_by_tid.get(tid_key, [])
        st = starts_by_tid.get(tid_key, [])
        i = bisect_right(st, t1)
        out = []
        for e in lst[max(0, i - 4000):i]:
            s, f = e["ts"], e["ts"] + e["dur"]
            ov = min(f, t1) - max(s, t0)
            if ov > 0:
                out.append((e["dur"], ov, e["name"]))
        out.sort()
        return out

    causes = defaultdict(float)
    cause_n = defaultdict(int)
    idle_per_iter, n_it = [], 0
    examples = defaultdict(list)
    sync_per_iter = defaultdict(float)
    for x, y in zip(ann, ann[1:]):
        if y["ts"] - x["ts"] > 80000:
            continue
        n_it += 1
        if n_it > a.iters:
            break
        lo, hi = bisect_left(gstarts, x["ts"]), bisect_left(gstarts, y["ts"])
        ks = gpu[lo:hi]
        idle = 0.0
        cur_end = ks[0]["ts"] + ks[0]["dur"] if ks else x["ts"]
        for k in ks[1:]:
            if k["ts"] > cur_end + a.min_gap:
                gap = k["ts"] - cur_end
                idle += gap
                c = by_corr.get(k["args"].get("correlation"))
                if c is None:
                    key = f"(no launch record) next={k['name'][:50]}"
                else:
                    late = (c["ts"] + c["dur"]) - cur_end  # launch completed this long after the GPU went idle
                    tid_key = (c.get("pid"), c.get("tid"))
                    act = active_spans(tid_key, cur_end, c["ts"])
                    inner = [n for d, ov, n in act if ov > 0.3 * gap][:3]
                    what = " < ".join(inner) if inner else "?"
                    kind = "launch-late" if late > 0.5 * gap else "launched-early(dep/stream wait)"
                    key = f"{kind} | {c['name'][:28]} | cpu: {what[:150]}"
                causes[key] += gap
                cause_n[key] += 1
                if len(examples[key]) < 2:
                    examples[key].append((round(gap, 1), k["name"][:60]))
            cur_end = max(cur_end, k["ts"] + k["dur"])
        idle_per_iter.append(idle / 1e3)
        for s in syncs:
            if x["ts"] <= s["ts"] < y["ts"]:
                sync_per_iter[s["name"]] += s["dur"]
    print(f"iterations {len(idle_per_iter)}: GPU idle per iteration median {statistics.median(idle_per_iter):.2f} ms "
          f"(min {min(idle_per_iter):.2f}, max {max(idle_per_iter):.2f}); gaps >= {a.min_gap} us")
    tot = sum(causes.values())
    print(f"\nranked gap causes (ms per iteration, count per iteration):")
    for k, v in sorted(causes.items(), key=lambda kv: -kv[1])[:25]:
        print(f"{v / 1e3 / len(idle_per_iter):7.3f} ms {cause_n[k] / len(idle_per_iter):6.1f}x  {k}  e.g. {examples[k]}")
    print(f"\nsynchronizing / memcpy runtime calls (CPU ms per iteration):")
    for k, v in sorted(sync_per_iter.items(), key=lambda kv: -kv[1])[:12]:
        print(f"{v / 1e3 / len(idle_per_iter):7.3f} ms  {k}")


if __name__ == "__main__":
    main()
