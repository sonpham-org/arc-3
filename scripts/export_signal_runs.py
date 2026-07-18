"""Export docs/data/signals.json for the Signal-runs tab.

A "signal run" is a single-game robustness run -- ONE game played N times
(benchmark.json with n_passes > 1) to read the score distribution of a noisy
game (see gcp/single_game_startup.sh). Per-pass score is the ARC-AGI3 score:
each pass's final_score when set, else computed live from levels_completed /
actions (game.py:_compute_final_score), so an in-progress run still shows a
distribution. Writes per-run summary stats + the raw per-pass scores for the
box/whisker plot the tab renders.
"""

import glob
import json
import os
import statistics
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "data" / "signals.json"
_TERMINAL = {"won", "gave_up", "game_over", "crashed", "cancelled", "lost"}


def pass_score(g: dict) -> float:
    """ARC-AGI3 score for one pass; final_score if finalized, else live from levels/actions."""
    fs = g.get("final_score")
    if fs is not None:
        return round(float(fs), 3)
    base = g.get("base_actions_per_level")
    nlev = g.get("number_of_levels") or 0
    apl = g.get("actions_per_level") or []
    lc = g.get("levels_completed") or 0
    if not base or not nlev:
        return 0.0
    total = weights = maxw = 0.0
    for i in range(nlev):
        w = i + 1
        weights += w
        actions = apl[i] if i < len(apl) else 0
        baseline = base[i]
        ls = min(115.0, (baseline / actions) ** 2 * 100) if (i < lc and actions > 0) else 0.0
        if ls > 0:
            maxw += w
        total += ls * w
    return round(min(total / weights, maxw / weights * 100), 3) if weights else 0.0


def five_number(xs: list[float]) -> dict:
    xs = sorted(xs)
    n = len(xs)

    def q(p: float) -> float:
        if n == 1:
            return xs[0]
        idx = p * (n - 1)
        lo = int(idx)
        return xs[lo] + (idx - lo) * (xs[min(lo + 1, n - 1)] - xs[lo])

    return {
        "min": round(xs[0], 3), "q1": round(q(0.25), 3), "median": round(q(0.5), 3),
        "q3": round(q(0.75), 3), "max": round(xs[-1], 3),
        "mean": round(statistics.mean(xs), 3),
        "std": round(statistics.pstdev(xs), 3) if n > 1 else 0.0,
    }


runs = []
for bench_path in sorted(glob.glob("logs/*/benchmark.json")):
    run = os.path.basename(os.path.dirname(bench_path))
    try:
        bench = json.load(open(bench_path))
    except Exception:
        continue
    if (bench.get("n_passes") or 1) <= 1:
        continue  # multi-game scoreboard run, not a signal run
    gr = bench.get("game_runs", [])
    if not gr:
        continue
    scores = [pass_score(g) for g in gr]
    in_progress = any(
        g.get("final_score") is None and g.get("state") not in _TERMINAL for g in gr
    )
    runs.append({
        "run": run,
        "game": gr[0].get("game_id", "?"),
        "n_passes": len(gr),
        "levels_total": gr[0].get("number_of_levels") or 0,
        "in_progress": in_progress,
        "scores": scores,
        **five_number(scores),
    })

runs.sort(key=lambda r: -r["median"])
OUT.parent.mkdir(parents=True, exist_ok=True)
json.dump({"runs": runs}, open(OUT, "w"), indent=1)
print(f"wrote {len(runs)} signal run(s) -> {OUT}")
