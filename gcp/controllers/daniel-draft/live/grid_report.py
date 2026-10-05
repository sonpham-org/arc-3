"""Context-window grid report (3-Oct-2026, daniel-draft; Son: "the trade-off between context window and quality").

Per slot count S (harness window 131k x 10/S): the valid runs' scores (our ruler: arc3_firestore_scores.score_row via
score_daniel_run.viewers), levels, actions, tokens generated, tokens per action, decode tok/s and per-slot tok/s over
the whole gameplay window (bench_report), each run's liveness (dead_server gap). Runs whose server died before the end
(gap > 3 min or a crash line) are listed but left out of the means.
  python grid_report.py RUN [RUN ...]       (slot count from the run id: daniel-ctx-sNN-... ; hicache-sb11-* = 10)
"""
import re
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, r"D:\codex-work\daniel-base-20261001")
sys.path.insert(0, r"D:\codex-work\daniel-draft\live")
import score_daniel_run as sdr  # noqa: E402
import bench_report as br  # noqa: E402

CRASH = re.compile(r"Scheduler hit an exception|crashed with exit code|OutOfMemoryError")


def slots(run):
    m = re.search(r"daniel-ctx-s(\d+)-", run)
    return int(m.group(1)) if m else 10


def one(run):
    v = sdr.viewers(run)
    s = sdr.fs.score_row(v) if v else None
    log = br.cat(f"{br.B}/{run}/working/serve.log")
    crashed = bool(CRASH.search(log))
    dec = re.findall(r"^\[(\S+ \S+)\] Decode batch", log, re.M)
    ph = br.cat(f"{br.B}/{run}/phases.tsv")
    fin = [l.split("\t")[0] for l in ph.splitlines() if "finish" in l]
    from datetime import datetime
    gap = None
    if dec and fin:
        gap = (datetime.strptime(fin[-1], "%Y-%m-%dT%H:%M:%SZ") - datetime.strptime(dec[-1], "%Y-%m-%d %H:%M:%S")).total_seconds() / 60
    serving = br.report(run)
    return run, s, crashed, gap, serving


def main():
    runs = sys.argv[1:]
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(one, runs))
    by = {}
    print(f"{'run':30s} {'S':>3s} {'score':>6s} {'lvls':>4s} {'acts':>5s} {'tok/s':>6s} {'/slot':>6s} {'Mtok':>6s} "
          f"{'tok/act':>7s} {'gap':>5s} note")
    for run, s, crashed, gap, sv in sorted(res, key=lambda r: (slots(r[0]), r[0])):
        S = slots(run)
        if not s or "note" in sv:
            print(f"{run:30s} {S:3d} no score/serving data ({sv.get('note', '')})"); continue
        mtok = sv["gen_per_min"] * sv["min"] / 1e6
        valid = not crashed and gap is not None and gap <= 3
        note = "" if valid else ("SERVER DIED" if crashed else f"gap {gap}")
        print(f"{run:30s} {S:3d} {s['all25']:6.2f} {s['levels']:4d} {s['actions']:5d} {sv['tok_s']:6.0f} {sv['per_slot']:6.1f} "
              f"{mtok:6.2f} {mtok * 1e6 / max(s['actions'], 1):7.0f} {gap if gap is not None else float('nan'):5.1f} {note}")
        if valid:
            by.setdefault(S, []).append((s["all25"], s["levels"], s["actions"], sv["tok_s"], sv["per_slot"], mtok * 1e6 / max(s["actions"], 1), s["hard7"]))
    print("\nper slot count (valid runs only): window = 131k x 10/S")
    print(f"{'S':>3s} {'window':>7s} {'n':>2s} {'score':>13s} {'hard7':>6s} {'levels':>7s} {'actions':>8s} {'tok/s':>6s} {'/slot':>6s} {'tok/act':>7s}")
    for S in sorted(by):
        rows = by[S]
        m = lambda i: statistics.mean(r[i] for r in rows)  # noqa: E731
        sd = statistics.stdev([r[0] for r in rows]) if len(rows) > 1 else float("nan")
        print(f"{S:3d} {131072 * 10 // S / 1000:6.0f}k {len(rows):2d} {m(0):6.1f} +-{sd:4.1f} {m(6):6.1f} {m(1):7.1f} {m(2):8.0f} "
              f"{m(3):6.0f} {m(4):6.1f} {m(5):7.0f}")


if __name__ == "__main__":
    main()
