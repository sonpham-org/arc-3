"""Side-by-side serving stats of Daniel-base runs over a MATCHED window of play (2-Oct-2026, daniel-draft).
Per run, over its first N minutes of decoding (N = --minutes, or the shortest run so far): mean busy server slots, share
of logs with all 10 busy, mean server queue, accept len, decode tok/s, generated tokens per minute (decode tok/s x
interval: prefill stalls lower it), prompt-cache hit, recomputed prompt tokens per minute.
  python fleet_compare.py [--minutes N] RUN [RUN ...]
"""
import argparse
import re
import subprocess
from datetime import datetime

G = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
B = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"
TS = re.compile(r"^\[(\S+ \S+)\] (Decode|Prefill) batch")
DEC = re.compile(r"#running-req: (\d+).*?accept len: ([\d.]+).*?gen throughput \(token/s\): ([\d.]+)(?:.*?#queue-req: (\d+))?")
PRE = re.compile(r"#new-token: (\d+), #cached-token: (\d+)")


def load(run):
    out = subprocess.run(G + ["storage", "cat", f"{B}/{run}/working/serve.log"], capture_output=True).stdout
    ev = []
    for l in out.decode("utf-8", "replace").splitlines():
        m = TS.match(l)
        if m:
            ev.append((datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"), m.group(2), l))
    return ev


def stats(ev, minutes):
    dec = [(t, l) for t, k, l in ev if k == "Decode"]
    if not dec:
        return None
    t0 = dec[0][0]
    inwin = lambda t: (t - t0).total_seconds() <= minutes * 60  # noqa: E731
    rows, gen, prev, new, cached = [], 0.0, None, 0, 0
    for t, k, l in ev:
        if not inwin(t) or t < t0:
            continue
        if k == "Decode":
            m = DEC.search(l)
            run, acc, tps, q = int(m.group(1)), float(m.group(2)), float(m.group(3)), int(m.group(4) or 0)
            rows.append((run, acc, tps, q))
            if prev is not None and 0 < (t - prev).total_seconds() <= 10:
                gen += tps * (t - prev).total_seconds()
            prev = t
        else:
            m = PRE.search(l)
            new += int(m.group(1)); cached += int(m.group(2))
    n = len(rows)
    span = min(minutes, (dec[-1][0] - t0).total_seconds() / 60)
    return {"min": span, "busy": sum(r[0] for r in rows) / n, "all10": sum(r[0] >= 10 for r in rows) / n,
            "queue": sum(r[3] for r in rows) / n, "accept": sum(r[1] for r in rows) / n, "tps": sum(r[2] for r in rows) / n,
            "gen_per_min": gen / max(span, 1e-9), "hit": cached / max(1, new + cached), "recompute_per_min": new / max(span, 1e-9)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float)
    ap.add_argument("runs", nargs="+")
    a = ap.parse_args()
    evs = {r: load(r) for r in a.runs}
    spans = [((d[-1][0] - d[0][0]).total_seconds() / 60) for d in
             ([(t, l) for t, k, l in ev if k == "Decode"] for ev in evs.values()) if d]
    minutes = a.minutes or min(spans)
    print(f"window: first {minutes:.0f} min of decoding")
    print(f"{'run':34s} {'busy':>5s} {'all10':>6s} {'queue':>5s} {'accept':>6s} {'tok/s':>6s} {'gen/min':>8s} {'hit':>6s} {'recomp/min':>10s}")
    for r, ev in evs.items():
        s = stats(ev, minutes)
        if s is None:
            print(f"{r:34s} no decode logs yet"); continue
        print(f"{r:34s} {s['busy']:5.2f} {s['all10']:6.0%} {s['queue']:5.2f} {s['accept']:6.3f} {s['tps']:6.0f} "
              f"{s['gen_per_min'] / 1e3:7.1f}k {s['hit']:6.1%} {s['recompute_per_min'] / 1e3:9.0f}k")


if __name__ == "__main__":
    main()
