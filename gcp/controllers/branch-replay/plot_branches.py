"""Plot branch efficiency vs position in the level: action ratio and token ratio (branch / recording's
remainder) per checkpoint, one marker per branch, one panel per effort, coloured with the Cellens colour
map. usage: python plot_branches.py <pack_dir> <out.png> <results.jsonl ...>"""
import json, statistics as st, sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, r"D:\CodexBuild\CancerPredictionProd-latest-main\core")
from color_map import my_cmap  # noqa: E402

pack, out, files = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
plan = {j["job_id"]: j for j in json.loads((pack / "plan.json").read_text(encoding="utf-8"))}
rows = [json.loads(l) for f in files for l in Path(f).read_text(encoding="utf-8").splitlines() if l.strip()]
rows = [r for r in rows if r.get("status") == "done" and r.get("prefix_ok") and r["job_id"] in plan]
ctl = [r for r in rows if r["effort"] == "xhigh" and r["live_completion_tokens"]]
tpc = sum(r["live_completion_tokens"] for r in ctl) / max(1, sum(r["live_reasoning_chars"] + r["live_content_chars"] + r.get("live_tool_arg_chars", 0) for r in ctl)) if ctl else 0.32
EFFORTS = ["xhigh", "high", "medium", "low"]
COL = {e: my_cmap(x) for e, x in zip(EFFORTS, (0.08, 0.35, 0.65, 0.92))}
levels = sorted({(r["game_id"], r["level"]) for r in rows})

fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
for ax, key, label in ((axes[0], "action", "actions: branch / recording remainder"), (axes[1], "token", "completion tokens: branch / recording remainder (est.)")):
    for e in EFFORTS:
        xs, ys, xf, yf = [], [], [], []
        for r in rows:
            if r["effort"] != e: continue
            x = r["frac"]
            if key == "action":
                y = r["live_actions"] / r["orig_remaining_actions"] if r["orig_remaining_actions"] else None
            else:
                est = r["orig_remaining_chars"] * tpc
                y = r["live_completion_tokens"] / est if est else None
            if y is None: continue
            (xs if r["solved"] else xf).append(x); (ys if r["solved"] else yf).append(min(y, 4.0))
        ax.scatter(xs, ys, s=22, color=COL[e], alpha=0.75, label=f"{e} solved (n={len(xs)})")
        ax.scatter(xf, yf, s=34, marker="x", color=COL[e], alpha=0.9, label=f"{e} not solved within 2x (n={len(xf)})")
        # binned median of solved branches
        bins = defaultdict(list)
        for x, y in zip(xs, ys): bins[round(x * 5) / 5].append(y)
        bx = sorted(bins); ax.plot(bx, [st.median(bins[b]) for b in bx], color=COL[e], lw=2)
    ax.axhline(1.0, color="0.4", lw=1, ls="--"); ax.set_ylim(0, 4.1); ax.set_ylabel(label); ax.grid(alpha=0.25)
axes[0].legend(fontsize=7, ncol=4, loc="upper left"); axes[1].set_xlabel("checkpoint position in the level (turns replayed / turns in the recorded level)")
fig.suptitle(f"LA-CR hard-7 recording: branch efficiency vs where the effort switch happens ({len(rows)} branches, {len({r['group'] for r in rows})} checkpoints, {len(levels)} levels; lines = binned medians of solved branches; x = capped at 2x)", fontsize=10)
fig.tight_layout(); fig.savefig(out, dpi=140)

# per-level small multiples of the action ratio
fig2, axs = plt.subplots(3, 4, figsize=(16, 10), sharey=True)
for ax, (g, L) in zip(axs.flat, levels):
    for e in EFFORTS:
        rs = [r for r in rows if r["effort"] == e and r["game_id"] == g and r["level"] == L and r["orig_remaining_actions"]]
        ax.scatter([r["i"] for r in rs if r["solved"]], [min(r["live_actions"] / r["orig_remaining_actions"], 4) for r in rs if r["solved"]], s=18, color=COL[e], alpha=0.8, label=e)
        ax.scatter([r["i"] for r in rs if not r["solved"]], [min(r["live_actions"] / r["orig_remaining_actions"], 4) for r in rs if not r["solved"]], s=30, marker="x", color=COL[e])
    n = next(r["n_turns"] for r in rows if r["game_id"] == g and r["level"] == L)
    ax.axhline(1.0, color="0.4", lw=1, ls="--"); ax.set_title(f"{g[:4]} L{L} ({n} turns)", fontsize=9); ax.set_ylim(0, 4.1); ax.grid(alpha=0.25)
for ax in axs.flat[len(levels):]: ax.axis("off")
axs.flat[0].legend(fontsize=7); fig2.supxlabel("turn index i at which the branch switches effort"); fig2.supylabel("actions: branch / recording remainder (x = not solved within 2x)")
fig2.tight_layout(); fig2.savefig(out.with_name(out.stem + "_per_level.png"), dpi=130)
print("wrote", out, "and per-level figure;", len(rows), "branches; tokens/char", round(tpc, 3))
