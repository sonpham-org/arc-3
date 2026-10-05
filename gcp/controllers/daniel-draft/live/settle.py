"""When does decode speed settle? (4-Oct-2026, daniel-draft; Son: "do you really need 65 minutes for a speed test?")

For finished Daniel-base runs: decode tok/s (mean over serve.log decode lines, as bench_report.py) in the first W minutes
of play, for W = 5..full, as a ratio to the run's full-play value; 10-min bins (does speed drift as contexts grow?);
spread of identical runs at each W; and arm-vs-arm ratios at each W against the full-run ratio.
serve.log files are cached in live/cache_serve/ (3 MB each).
  python settle.py
"""
import re
import statistics as st
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

G = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
B = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"
CACHE = Path(__file__).parent / "cache_serve"
TS = re.compile(r"^\[(\S+ \S+)\] Decode batch")
DEC = re.compile(r"#running-req: (\d+),.*?gen throughput \(token/s\): ([\d.]+)")
WINDOWS = [5, 10, 15, 20, 25, 30, 40, 50, 65, 90, 120]

GROUPS = {   # identical builds, full scored runs
    "8bit base 11/10 (sbt06tfrs)": [f"daniel-hicache-sbt06tfrs-{x}-1003" for x in "abcd"],
    "8bit no-RS 11/10 (sbt06tf)": [f"daniel-hicache-sbt06tf-{x}-1003" for x in "abcd"],
    "4bit 13 lanes ctl (kv4s13)": [f"daniel-ctx-kv4s13-{x}-1003" for x in "abcd"],
    "4bit 13 ship ctl (cctl)": [f"daniel-ctx-cctl-{x}-1003" for x in "ab"],
    "4bit 13 skip experts (cba4)": [f"daniel-ctx-cba4-{x}-1003" for x in "abcd"],
}
PAIRS = [("4bit 13 skip experts (cba4)", "4bit 13 ship ctl (cctl)"),
         ("8bit base 11/10 (sbt06tfrs)", "8bit no-RS 11/10 (sbt06tf)")]


def load(run):
    f = CACHE / f"{run}.serve.log"
    if not f.exists() or f.stat().st_size == 0:
        r = subprocess.run(G + ["storage", "cat", f"{B}/{run}/working/serve.log"], capture_output=True)
        f.write_bytes(r.stdout if r.returncode == 0 else b"")
    pts = []
    for l in f.read_text("utf-8", "replace").splitlines():
        m, d = TS.match(l), DEC.search(l)
        if m and d:
            pts.append((datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"), int(d.group(1)), float(d.group(2))))
    s = next((t for t, n, _ in pts if n >= 5), None)
    return [((t - s).total_seconds() / 60, v) for t, n, v in pts if s and t >= s]


def mean_upto(p, w):
    v = [x for m, x in p if m <= w]
    return sum(v) / len(v) if v else float("nan")


def main():
    CACHE.mkdir(exist_ok=True)
    runs = sorted({r for g in GROUPS.values() for r in g})
    with ThreadPoolExecutor(12) as ex:
        data = dict(zip(runs, ex.map(load, runs)))
    full = {r: mean_upto(p, 1e9) for r, p in data.items()}
    span = {r: (p[-1][0] if p else 0) for r, p in data.items()}

    print("1) Each run: tok/s in the first W minutes as % of its whole-run tok/s")
    print(f"{'run':36s} {'play':>5s} {'full':>5s} " + " ".join(f"{w:>5d}" for w in WINDOWS))
    for g, rs in GROUPS.items():
        for r in rs:
            p = data[r]
            if not p:
                print(f"{r:36s} no log"); continue
            cells = [f"{100 * mean_upto(p, w) / full[r] - 100:+5.1f}" if w <= span[r] + 1 else "    ." for w in WINDOWS]
            print(f"{r:36s} {span[r]:5.0f} {full[r]:5.0f} " + " ".join(cells))

    print("\n2) 10-minute bins, tok/s (does speed drift as games get longer?)")
    for g, rs in GROUPS.items():
        bins = []
        for b0 in range(0, 130, 10):
            vals = [st.mean(v) for r in rs if (v := [x for m, x in data[r] if b0 <= m < b0 + 10])]
            bins.append(f"{st.mean(vals):5.0f}" if vals else "    .")
        print(f"{g:32s} " + " ".join(bins))

    print("\n3) Spread of identical runs at each W (max-min as % of mean)")
    for g, rs in GROUPS.items():
        cells = []
        for w in WINDOWS:
            v = [mean_upto(data[r], w) for r in rs if data[r] and span[r] + 1 >= w]
            cells.append(f"{100 * (max(v) - min(v)) / st.mean(v):5.1f}" if len(v) >= 2 else "    .")
        print(f"{g:32s} " + " ".join(cells))

    print("\n4) Arm A / arm B tok/s at each W (group means)")
    for a, b in PAIRS:
        cells = []
        for w in WINDOWS + [1e9]:
            va = [mean_upto(data[r], w) for r in GROUPS[a] if data[r] and span[r] + 1 >= min(w, 130)]
            vb = [mean_upto(data[r], w) for r in GROUPS[b] if data[r] and span[r] + 1 >= min(w, 130)]
            cells.append(f"{100 * st.mean(va) / st.mean(vb) - 100:+5.1f}" if va and vb else "    .")
        print(f"{a[:20]} / {b[:20]}  " + " ".join(cells[:-1]) + f"  full {cells[-1]}")
    print("   W =", " ".join(f"{w:>5d}" for w in WINDOWS))


if __name__ == "__main__":
    main()
