"""Score RL eval panels (plan 9g): Daniel-notebook runs that play a few games several times each (bm.n_passes).

  C:/Python312/python.exe score_panel.py <run id> [<run id> ...] [--vs <run id> ...]

Reads gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs/<run id>/working/artifacts/*_viewer_data.json (the runner
syncs them every 5 minutes, so a game still playing shows its levels so far). score_daniel_run.py and
arc3_firestore_scores.score_row keep one result per game; here repeats of a game stay apart by their pass_index.
Runs before --vs are one arm (pooled, e.g. base over two waves), runs after it the other (e.g. the LoRA).

Prints, per game: levels in every repeat, mean levels, mean score (the score-table ruler). Per arm: the panel's total
levels (sum over games of mean levels) with its standard error, sqrt(sum over games of variance / repeats). With two
arms: the difference and its standard error. Single games swing 1 <-> 7 levels between runs; read the totals.
"""
import json
import math
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))   # gcp/
import arc3_firestore_scores as fs  # noqa: E402

GCLOUD = [r"C:\python312\python.exe", r"C:\Users\celle\AppData\Local\Google\Cloud SDK\google-cloud-sdk\lib\gcloud.py"]
RUNS = "gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs"
# a finished all-25 run ends with every game "won" or "gave_up"; the rest are listed in case
FINAL = {"won", "gave_up", "lost", "game_over", "timeout", "finished", "error", "cancelled", "failed"}


def viewers(run_id):
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(GCLOUD + ["storage", "cp", f"{RUNS}/{run_id}/working/artifacts/*_viewer_data.json", tmp],
                           capture_output=True, text=True)
        files = sorted(Path(tmp).glob("*_viewer_data.json"))
        if not files:
            print(f"{run_id}: no viewer data yet ({r.stderr.strip()[-160:]})")
        return [json.loads(p.read_text(encoding="utf-8")) for p in files]


def arm_results(run_ids):
    """{game: [(levels, score, actions, status, run_id, pass_index), ...]} over every run of the arm."""
    out = defaultdict(list)
    for run_id in run_ids:
        for v in viewers(run_id):
            gid = v.get("game_id")
            if gid not in fs.observer.BASE_ACTIONS:
                continue
            levels = int(v.get("levels_completed") or 0)
            actions = [int(x) for x in v.get("actions_per_level") or []]
            score = fs.observer.game_score(levels, actions, fs.observer.BASE_ACTIONS[gid])
            out[gid.split("-")[0]].append((levels, score, sum(actions), str(v.get("status") or ""), run_id,
                                           v.get("pass_index")))
    return out


def summary(res):
    rows, total, var = {}, 0.0, 0.0
    for g, xs in sorted(res.items()):
        lv = [x[0] for x in xs]
        n = len(lv)
        m = sum(lv) / n
        s2 = sum((x - m) ** 2 for x in lv) / (n - 1) if n > 1 else float("nan")
        rows[g] = {"n": n, "levels": lv, "mean": m, "var": s2, "score": sum(x[1] for x in xs) / n,
                   "playing": sum(x[3].lower() not in FINAL for x in xs)}
        total += m
        var += s2 / n if n > 1 else float("nan")
    return rows, total, math.sqrt(var) if var == var else float("nan")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    a_ids, b_ids = (args[:args.index("--vs")], args[args.index("--vs") + 1:]) if "--vs" in args else (args, [])
    arms = [("A", a_ids, arm_results(a_ids))] + ([("B", b_ids, arm_results(b_ids))] if b_ids else [])
    sums = {}
    for name, ids, res in arms:
        rows, total, se = summary(res)
        sums[name] = (rows, total, se)
        print(f"\narm {name}: {' '.join(ids)}")
        print(f"{'game':6} {'n':>2} {'mean lv':>7} {'score':>6}  levels per repeat")
        for g, r in rows.items():
            print(f"{g:6} {r['n']:2} {r['mean']:7.2f} {r['score']:6.1f}  {r['levels']}"
                  + (f"  ({r['playing']} still playing)" if r["playing"] else ""))
        print(f"panel total levels {total:.1f} +- {se:.1f} (standard error)")
    if len(arms) == 2:
        (ra, ta, sa), (rb, tb, sb) = sums["A"], sums["B"]
        print(f"\nB - A: total levels {tb - ta:+.1f} +- {math.sqrt(sa ** 2 + sb ** 2):.1f}")
        for g in sorted(set(ra) | set(rb)):
            if g in ra and g in rb:
                print(f"  {g:6} {rb[g]['mean'] - ra[g]['mean']:+5.2f} levels, {rb[g]['score'] - ra[g]['score']:+6.1f} score")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
