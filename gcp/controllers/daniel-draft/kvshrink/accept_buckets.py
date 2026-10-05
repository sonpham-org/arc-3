"""Accept length and decode tok/s per N-minute bucket of play, side by side (kvshrink, 3-Oct-2026).

Same window rule as live/bench_report.py (play starts at the first decode line with >= 5 requests running).
  python accept_buckets.py RUN [RUN ...] [--bucket 5] [--minutes 45]
"""
import argparse
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

G = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
B = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"
TS = re.compile(r"^\[(\S+ \S+)\] Decode batch")
DEC = re.compile(r"#running-req: (\d+),.*?accept len: ([\d.]+), accept rate: ([\d.]+).*?gen throughput \(token/s\): ([\d.]+)")


def rows(run):
    txt = subprocess.run(G + ["storage", "cat", f"{B}/{run}/working/serve.log"], capture_output=True).stdout.decode("utf-8", "replace")
    out = []
    for line in txt.splitlines():
        m, d = TS.match(line), DEC.search(line)
        if m and d:
            out.append((datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"), int(d.group(1)), float(d.group(2)),
                        float(d.group(3)), float(d.group(4))))
    start = next((r[0] for r in out if r[1] >= 5), None)
    return [((t - start).total_seconds() / 60, n, a, ar, tps) for t, n, a, ar, tps in out if start and t >= start]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--bucket", type=int, default=5)
    ap.add_argument("--minutes", type=float, default=45)
    a = ap.parse_args()
    with ThreadPoolExecutor(len(a.runs)) as ex:
        data = dict(zip(a.runs, ex.map(rows, a.runs)))
    nb = int(a.minutes // a.bucket)
    print("bucket(min) " + " ".join(f"{r[-14:]:>24s}" for r in a.runs) + "   (accept len / tok/s / busy)")
    for b in range(nb):
        cells = []
        for r in a.runs:
            sel = [x for x in data[r] if b * a.bucket <= x[0] < (b + 1) * a.bucket]
            if not sel:
                cells.append(f"{'-':>24s}"); continue
            n = len(sel)
            cells.append(f"{sum(x[2] for x in sel) / n:6.3f} {sum(x[4] for x in sel) / n:6.0f} {sum(x[1] for x in sel) / n:5.1f}    ")
        print(f"{b * a.bucket:3d}-{(b + 1) * a.bucket:<3d}     " + " ".join(cells))
    for r in a.runs:
        sel = [x for x in data[r] if x[0] < a.minutes]
        n = max(len(sel), 1)
        print(f"{r}: {len(sel)} decode lines, accept {sum(x[2] for x in sel) / n:.3f}, accept rate {sum(x[3] for x in sel) / n:.3f}, "
              f"tok/s {sum(x[4] for x in sel) / n:.0f}, busy {sum(x[1] for x in sel) / n:.2f}, played {max((x[0] for x in sel), default=0):.0f} min")


if __name__ == "__main__":
    main()
