"""Draft-width cost curve (4-Oct-2026, daniel-draft kernels): per run, medians over its profiler traces of
wall ms per iteration (scheduler period), GPU idle, and GPU kernel ms per iteration by category
(experts = Marlin, attention = QSA family, dense = cuBLAS + skinny + low-M, GDN, misc = rest).
Also from serve.log (works when CUPTI failed): log_ms = median over decode log lines with >= 9 running of
1000 x accept len / per-slot gen tok/s (an upper bound on the iteration: prefill time inside the interval counts);
tok/s and accept over the same window (play minutes 5-25).
  python curve.py RUN:W [RUN:W ...]"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import handoff  # noqa: E402
sys.path.insert(0, r"D:\codex-work\daniel-draft\live")
import bench_report as BR  # noqa: E402


DEC0 = __import__("re").compile(r"#running-req: (\d+), #full token: \d+, full token usage: ([\d.]+), mamba num: \d+, "
                                r"mamba usage: ([\d.]+), (?:accept len: ([\d.]+))?.*?gen throughput \(token/s\): ([\d.]+)")


def log_ms(run, skip_min=5, until_min=25):
    """Play window = first decode with >= 5 running; minutes skip_min..until_min of it (coordinator 4-Oct: the
    first 5 min are warm-up, 20 matched minutes are enough for kernel/width speed)."""
    from datetime import datetime
    ms, accs, tps, t0 = [], [], [], None
    for l in BR.cat(f"{BR.B}/{run}/working/serve.log").splitlines():
        ts, m = BR.TS.match(l), BR.DEC.search(l) or DEC0.search(l)
        if not (ts and m):
            continue
        t = datetime.strptime(ts.group(1), "%Y-%m-%d %H:%M:%S")
        if t0 is None:
            if int(m.group(1)) < 5:
                continue
            t0 = t
        mins = (t - t0).total_seconds() / 60
        if not skip_min <= mins <= until_min:
            continue
        acc, tp = float(m.group(4) or 1.0), float(m.group(5))   # spec off (W1): no accept len -> 1
        accs.append(acc); tps.append(tp)
        if int(m.group(1)) >= 9 and tp > 0:
            ms.append(1000 * acc / (tp / int(m.group(1))))
    if not ms:
        return {}
    return dict(log_ms=round(statistics.median(ms), 2), accept=round(statistics.mean(accs), 3), tok_s=round(statistics.mean(tps)))
import iter_stats as I  # noqa: E402

CAT = {"experts": ["marlin_moe"], "attention": ["qsa"], "dense": ["cublas_gemm", "skinny_gemm", "lowm_gemm_daniel"],
       "gdn": ["gdn"], "misc": ["hc_combine", "hc_mix", "topk_sum", "other"]}
rows = []
for arg in sys.argv[1:]:
    run, w = arg.split(":")
    traces = I.traces(run)
    per, cpu_walls = [], []
    for p in traces:
        s = I.stats(p)
        h = handoff.analyse(str(p))
        if "family_ms_median" not in s:
            if "wall_ms_median" in h:
                cpu_walls.append(h["wall_ms_median"])
            continue
        f = s["family_ms_median"]
        per.append(dict(wall=h["wall_ms_median"], idle=h["gpu_idle_ms_median"], busy=s["busy_ms_median"],
                        **{c: sum(f.get(x, 0.0) for x in xs) for c, xs in CAT.items()}))
    r = {k: round(statistics.median(x[k] for x in per), 2) for k in per[0]} if per else {}
    if not per and cpu_walls:   # CUPTI off: wall per iteration from the CPU-side scheduler period only
        r["wall"] = round(statistics.median(cpu_walls), 2)
    r.update(run=run, W=int(w), traces=len(per), **log_ms(run))
    rows.append(r)
rows.sort(key=lambda r: r["W"])
cols = ["W", "traces", "wall", "idle", "busy", "experts", "attention", "dense", "gdn", "misc", "log_ms", "accept", "tok_s"]
print(" ".join(f"{c:>9s}" for c in cols) + "  run")
for r in rows:
    print(" ".join(f"{r.get(c, '-'):>9}" for c in cols) + f"  {r['run']}")
full = [r for r in rows if r["traces"]]
if len(full) >= 2 and full[-1]["W"] != full[0]["W"]:
    a, b = full[0], full[-1]
    dw = b["W"] - a["W"]
    print("ms per extra position (first->last):", {c: round((b[c] - a[c]) / dw, 2) for c in cols[2:11]})
