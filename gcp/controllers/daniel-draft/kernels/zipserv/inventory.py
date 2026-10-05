"""Kernel inventory of one decode iteration from a torch-profiler trace (4-Oct-2026, Kernel optimizations thread).

Iteration = from one top-level 'draft' GPU annotation to the next (draft + target verify + draft_extend), kept when
< 80 ms (steady decode). Per iteration (medians over iterations):
  - wall, union-busy (any stream), idle
  - per stream: kernels, busy ms, and the summed gaps between consecutive kernels ON THAT STREAM (launch latency
    inside graphs, what PDL can hide), split into gaps < 5 us / 5-50 us / > 50 us
  - kernels by duration bucket (< 5, 5-10, 10-50, 50-200, > 200 us): count and ms (small kernels = fusion targets)
  - top kernel names: calls per iteration, mean us, ms per iteration, category (live/profile_report.py's CATS)
  python inventory.py TRACE.json.gz [--top 45] [--json out.json]
"""
import argparse
import gzip
import json
import re
import statistics as st
import sys
from bisect import bisect_left
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, r"D:\codex-work\daniel-draft\live")
from profile_report import CATS  # noqa: E402


def cat(name):
    n = name.lower()
    for c, pat in CATS:
        if re.search(pat, n):
            return c
    return "other"


def short(name):
    n = re.sub(r"<.*", "", name)
    n = re.sub(r"\(.*", "", n)
    return n[:70]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--top", type=int, default=45)
    ap.add_argument("--json")
    a = ap.parse_args()
    ev = json.loads(gzip.open(a.trace, "rb").read())["traceEvents"]
    ks = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") in ("kernel", "gpu_memcpy", "gpu_memset")],
                key=lambda e: e["ts"])
    ann = sorted([e for e in ev if e.get("ph") == "X" and e.get("cat") == "gpu_user_annotation" and e["name"] == "draft"],
                 key=lambda e: e["ts"])
    # top-level draft annotations only (nested ones start inside a previous one)
    tops = []
    for e in ann:
        if tops and e["ts"] < tops[-1]["ts"] + tops[-1]["dur"]:
            continue
        tops.append(e)
    starts = [e["ts"] for e in tops]
    kst = [k["ts"] for k in ks]
    its = []
    for a0, a1 in zip(starts, starts[1:]):
        if a1 - a0 > 80000:
            continue
        sub = ks[bisect_left(kst, a0):bisect_left(kst, a1)]
        if not sub:
            continue
        busy, cur = 0.0, None
        for k in sub:
            s, f = max(k["ts"], a0), min(k["ts"] + k["dur"], a1)
            if cur and s <= cur[1]:
                cur[1] = max(cur[1], f)
            else:
                if cur:
                    busy += cur[1] - cur[0]
                cur = [s, f]
        busy += cur[1] - cur[0]
        per_stream = defaultdict(list)
        for k in sub:
            per_stream[k["args"].get("stream")].append(k)
        sinfo = {}
        for sid, lst in per_stream.items():
            g = [max(0.0, b["ts"] - (p["ts"] + p["dur"])) for p, b in zip(lst, lst[1:])]
            sinfo[sid] = dict(n=len(lst), busy=sum(k["dur"] for k in lst) / 1e3,
                              gap_lt5=sum(x for x in g if x < 5) / 1e3, n_lt5=sum(1 for x in g if x < 5),
                              gap_5_50=sum(x for x in g if 5 <= x < 50) / 1e3,
                              gap_gt50=sum(x for x in g if x >= 50) / 1e3)
        buckets = defaultdict(lambda: [0, 0.0])
        names = defaultdict(lambda: [0, 0.0])
        cats = defaultdict(float)
        for k in sub:
            d = k["dur"]
            b = "<5us" if d < 5 else "5-10us" if d < 10 else "10-50us" if d < 50 else "50-200us" if d < 200 else ">200us"
            buckets[b][0] += 1
            buckets[b][1] += d / 1e3
            nm = short(k["name"])
            names[nm][0] += 1
            names[nm][1] += d / 1e3
            cats[cat(k["name"])] += d / 1e3
        its.append(dict(wall=(a1 - a0) / 1e3, busy=busy / 1e3, idle=(a1 - a0 - busy) / 1e3, n=len(sub), streams=sinfo,
                        buckets=dict(buckets), names=dict(names), cats=dict(cats)))
    if not its:
        print("no steady iterations found")
        return
    med = lambda xs: round(st.median(xs), 3)
    print(f"{Path(a.trace).name}: {len(its)} iterations | wall {med([i['wall'] for i in its])} ms | union busy "
          f"{med([i['busy'] for i in its])} | idle {med([i['idle'] for i in its])} | kernels {med([i['n'] for i in its])}")
    sids = sorted({s for i in its for s in i["streams"]}, key=lambda s: -st.median([i["streams"].get(s, {}).get("n", 0) for i in its]))
    print("stream   kernels   busy_ms   gaps<5us(ms,n)   gaps5-50us   gaps>50us")
    for s in sids[:12]:
        g = lambda f: med([i["streams"].get(s, {}).get(f, 0) for i in its])
        print(f"{str(s):>6} {g('n'):9} {g('busy'):9} {g('gap_lt5'):9} ({g('n_lt5')}) {g('gap_5_50'):11} {g('gap_gt50'):10}")
    print("duration bucket   kernels/iter   ms/iter")
    for b in ("<5us", "5-10us", "10-50us", "50-200us", ">200us"):
        print(f"{b:>10} {med([i['buckets'].get(b, [0, 0])[0] for i in its]):14} {med([i['buckets'].get(b, [0, 0])[1] for i in its]):10}")
    print("category ms/iter:", {c: med([i["cats"].get(c, 0) for i in its]) for c in sorted({c for i in its for c in i["cats"]})})
    allnames = defaultdict(list)
    for i in its:
        for nm, (c, ms) in i["names"].items():
            allnames[nm].append((c, ms))
    rows = []
    for nm, v in allnames.items():
        c = st.median([x[0] for x in v] + [0] * (len(its) - len(v)))
        ms = st.median([x[1] for x in v] + [0] * (len(its) - len(v)))
        rows.append((ms, c, nm))
    rows.sort(reverse=True)
    print(f"{'ms/iter':>8} {'calls':>6} {'mean_us':>8}  category          kernel")
    for ms, c, nm in rows[:a.top]:
        print(f"{ms:8.3f} {c:6.0f} {1e3 * ms / c if c else 0:8.1f}  {cat(nm):16}  {nm}")
    if a.json:
        Path(a.json).write_text(json.dumps(dict(trace=a.trace, iterations=its), default=str))


if __name__ == "__main__":
    main()
