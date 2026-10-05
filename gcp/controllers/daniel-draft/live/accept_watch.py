"""Live accept length / gen throughput from Daniel-base runs' serve.log (2-Oct-2026, daniel-draft A/B).
Per run: whole-run decode-log means, and the MATCHED window = each run's first N minutes of decoding, N = the shortest
decoding time among the runs that have started (early game phases accept differently, so compare like with like).
The capture run's first 30 min of tok/s carry capture overhead; its acceptance is unaffected.
  python accept_watch.py RUN [RUN ...]
"""
import re
import subprocess
import sys
from datetime import datetime

G = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
B = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"
PAT = re.compile(r"^\[(\S+ \S+)\] Decode batch, #running-req: (\d+).*?accept len: ([\d.]+).*?gen throughput \(token/s\): ([\d.]+)")


def cat(url):
    r = subprocess.run(G + ["storage", "cat", url], capture_output=True)
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else ""


def main(runs):
    data, phases = {}, {}
    for run in runs:
        data[run] = [(datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"), int(m.group(2)), float(m.group(3)), float(m.group(4)))
                     for m in (PAT.match(l) for l in cat(f"{B}/{run}/working/serve.log").splitlines()) if m]
        phases[run] = (cat(f"{B}/{run}/phases.tsv").strip().splitlines() or ["?"])[-1].split("\t")[-1]
    started = {r: v for r, v in data.items() if v}
    N = min(((v[-1][0] - v[0][0]).total_seconds() for v in started.values()), default=0)
    mean = lambda xs, i: sum(x[i] for x in xs) / len(xs)  # noqa: E731
    print(f"matched window: first {N / 60:.0f} min of decoding", flush=True)
    for run in runs:
        rows = data[run]
        if not rows:
            print(f"  {run}: no decode logs yet | phase {phases[run]}", flush=True)
            continue
        t0 = rows[0][0]
        w = [r for r in rows if (r[0] - t0).total_seconds() <= N]
        print(f"  {run}: matched accept {mean(w, 2):.3f} tok/s {mean(w, 3):.0f} | whole {((rows[-1][0] - t0).total_seconds() / 60):.0f} min"
              f" accept {mean(rows, 2):.3f} tok/s {mean(rows, 3):.0f} | phase {phases[run]}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
