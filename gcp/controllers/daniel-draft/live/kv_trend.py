"""KV-pool pressure trend of live Daniel-base runs (3-Oct-2026, daniel-draft; 4-bit KV lane sizing): per run, per
N-minute bucket of serve.log: running requests, decode tok/s, KV pool usage, prefill new vs cached tokens and the
prefix-cache hit share. A pool that is too small shows as usage ~0.98 with the hit share collapsing.
  python kv_trend.py RUN [RUN ...] [--bucket 5] [--last 6]
"""
import argparse
import re
import subprocess
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

G = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
B = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"
LINE = re.compile(r"^\[\S+ (\d\d):(\d\d):\d\d\] (Decode|Prefill) batch")
DEC = re.compile(r"#running-req: (\d+), #full token: \d+, full token usage: ([\d.]+).*?gen throughput \(token/s\): ([\d.]+)")
PRE = re.compile(r"#new-token: (\d+), #cached-token: (\d+)")


def cat(run):
    r = subprocess.run(G + ["storage", "cat", f"{B}/{run}/working/serve.log"], capture_output=True)
    return r.stdout.decode("utf-8", "replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--bucket", type=int, default=5)
    ap.add_argument("--last", type=int, default=6)
    a = ap.parse_args()
    with ThreadPoolExecutor(8) as ex:
        logs = dict(zip(a.runs, ex.map(cat, a.runs)))
    for run in a.runs:
        b = defaultdict(lambda: [0, 0.0, 0.0, 0.0, 0, 0])  # n, running, tok/s, usage, new, cached
        for line in logs[run].splitlines():
            m = LINE.match(line)
            if not m:
                continue
            mins = int(m.group(1)) * 60 + int(m.group(2))
            key = mins - mins % a.bucket
            row = b[key]
            if m.group(3) == "Decode":
                d = DEC.search(line)
                if d:
                    row[0] += 1
                    row[1] += int(d.group(1))
                    row[3] += float(d.group(2))
                    row[2] += float(d.group(3))
            else:
                p = PRE.search(line)
                if p:
                    row[4] += int(p.group(1))
                    row[5] += int(p.group(2))
        print(f"== {run}")
        for key in sorted(b)[-a.last:]:
            n, run_, tok, use, new, cached = b[key]
            hit = cached / (new + cached) if new + cached else float("nan")
            print(f"  {key // 60:02d}:{key % 60:02d} running {run_ / max(n, 1):5.1f} tok/s {tok / max(n, 1):5.0f} "
                  f"kv use {use / max(n, 1):4.2f} | prefill new {new // 1000:5d}k cached {cached // 1000:5d}k hit {hit:4.0%}")


if __name__ == "__main__":
    sys.exit(main())
