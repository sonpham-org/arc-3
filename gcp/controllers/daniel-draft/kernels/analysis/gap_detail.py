"""Detail of the largest GPU idle gaps: what every CPU thread was doing (innermost spans) during the gap.
  python gap_detail.py PATH.trace.json.gz [--top 6] [--iters 12]"""
import argparse
import gzip
import json
from bisect import bisect_left
from collections import defaultdict


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--top", type=int, default=6)
    ap.add_argument("--iters", type=int, default=12)
    a = ap.parse_args()
    ev = json.loads(gzip.open(a.trace, "rb").read())["traceEvents"]
    gpu = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") in ("kernel", "gpu_memcpy", "gpu_memset")],
                 key=lambda e: e["ts"])
    rt = {e["args"].get("correlation"): e for e in ev if e.get("ph") == "X" and e.get("cat") in ("cuda_runtime", "cuda_driver")
          and "correlation" in e.get("args", {})}
    spans = [e for e in ev if e.get("ph") == "X" and e.get("cat") in ("python_function", "user_annotation", "cpu_op", "cuda_runtime")]
    ann = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") == "gpu_user_annotation"
                  and e["name"] in ("draft", "draft_extend") or (e.get("cat") == "gpu_user_annotation" and e["name"].startswith("step[TARGET"))],
                 key=lambda e: e["ts"])
    drafts = [e for e in ann if e["name"] == "draft" and e["dur"] > 1000]
    gst = [e["ts"] for e in gpu]
    gaps = []
    n = 0
    for x, y in zip(drafts, drafts[1:]):
        if y["ts"] - x["ts"] > 80000:
            continue
        n += 1
        if n > a.iters:
            break
        ks = gpu[bisect_left(gst, x["ts"]):bisect_left(gst, y["ts"])]
        cur = ks[0]["ts"] + ks[0]["dur"]
        prev = ks[0]
        for k in ks[1:]:
            if k["ts"] > cur + 30:
                gaps.append((k["ts"] - cur, cur, k, prev, x["ts"]))
            if k["ts"] + k["dur"] > cur:
                cur, prev = k["ts"] + k["dur"], k
    gaps.sort(key=lambda g: -g[0])
    for gap, g0, k, prev, it0 in gaps[:a.top]:
        g1 = g0 + gap
        c = rt.get(k["args"].get("correlation"))
        print(f"\n=== gap {gap:.0f} us at iter+{(g0 - it0) / 1e3:.2f} ms; before: {prev['name'][:60]} | after: {k['name'][:60]}"
              f" | launched by {c['name'] if c else '?'} at gap+{(c['ts'] - g0) if c else 0:.0f} us on tid {c.get('tid') if c else '?'}")
        by_tid = defaultdict(list)
        for e in spans:
            s, f = e["ts"], e["ts"] + e["dur"]
            ov = min(f, g1) - max(s, g0)
            if ov > 0.05 * gap and e["dur"] < 20 * gap:
                by_tid[e.get("tid")].append((e["dur"], ov, s - g0, e["name"][:110]))
        for tid, lst in by_tid.items():
            lst.sort()
            print(f"  tid {tid}:")
            for d, ov, st, nm in lst[:7]:
                print(f"     dur {d:8.0f} us  overlap {ov:7.0f}  start {st:+8.0f}  {nm}")


if __name__ == "__main__":
    main()
