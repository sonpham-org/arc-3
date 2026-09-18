"""Multi-pass A/B comparison for the ARC-3 compact-reasoning experiment.

Consumes the per-run `style_table.json` files written by `style_analyze.py` (one per
one-pass run) and reports, per arm:

  * every pass's own numbers, so nothing is hidden behind an average
  * the arm mean and spread (sample sd, min, max) for score, levels and the efficiency
    metrics
  * the between-arm delta computed BOTH with and without a named game -- `sb26-7fbdac44`
    carried the entire apparent gain in the 17-Sep single-pass run, so excluding it is
    mandatory, not optional
  * a paired-by-game test on per-game mean score. Between-game variance is enormous
    (scores span 0 to 26) and drops out of a paired test entirely, so this is where the
    statistical power is -- not in comparing two scalar sums with n=3 per arm.
  * the per-game, per-pass score distribution, which is what distinguishes "the jackpot
    fires more often under compact" from "one pass got a lucky roll".

Significance is a two-sided sign-flip (randomisation) test on the paired per-game
differences: under the null the arm label is exchangeable within a game, so flipping the
sign of each game's difference is an equally likely outcome. No scipy dependency and no
normality assumption.

Author: Claude Opus 5 (Bubba sub-agent, label arc3-style-multipass)
Date: 18-September-2026
PURPOSE: Turn N one-pass run directories per arm into a mean-and-spread A/B report with an
explicit sb26-excluded arm, a paired per-game test, and per-pass efficiency metrics.
SRP/DRY check: Pass -- style_analyze.py already extracts per-run per-game metrics and is
reused unchanged; this script only aggregates across runs and does not re-parse artifacts.
"""
import argparse
import json
import math
import os
import random
import statistics
import sys

SCALARS = [
    ("score_sum", "score sum"),
    ("scoring_games", "scoring games"),
    ("levels_cleared", "levels cleared"),
    ("total_actions", "env actions"),
    ("tokens_per_action_overall", "tokens/action"),
    ("llm_responses", "llm responses"),
    ("total_generated_tokens", "generated tokens"),
    ("reasoning_chars_mean", "reasoning chars mean"),
    ("reasoning_chars_median", "reasoning chars median"),
    ("selftalk_frac_pooled", "selftalk frac"),
]


def load_arm(dirs):
    passes = []
    for d in dirs:
        p = os.path.join(d, "style_table.json")
        if not os.path.exists(p):
            sys.exit(f"missing {p} -- run style_analyze.py on {d} first")
        t = json.load(open(p))
        t["_dir"] = d
        t["_name"] = os.path.basename(os.path.normpath(d))
        passes.append(t)
    return passes


def recompute_summary(p, exclude):
    """Re-derive the arm-level scalars from per-game rows, optionally dropping games.

    Pooled character/self-talk statistics are weighted by each game's response count so
    that dropping a game gives the same answer as never having run it.
    """
    rows = [r for r in p["per_game"] if r["game"] not in exclude]
    resp = sum(r["llm_responses"] for r in rows)
    blocks = sum(r["reasoning_blocks"] for r in rows)
    acts = sum(r["actions"] for r in rows)
    gen = sum(r["generated_tokens"] for r in rows)
    scores = [r["official_score"] for r in rows if isinstance(r["official_score"], (int, float))]
    wchars = sum((r["reasoning_chars_mean"] or 0) * r["reasoning_blocks"] for r in rows)
    wself = sum((r["selftalk_frac"] or 0) * r["reasoning_blocks"] for r in rows)
    return {
        "score_sum": round(sum(scores), 2),
        "scoring_games": sum(1 for s in scores if s > 0),
        "levels_cleared": sum(r["levels_completed"] for r in rows),
        "total_actions": acts,
        "total_generated_tokens": gen,
        "tokens_per_action_overall": round(gen / acts, 1) if acts else None,
        "llm_responses": resp,
        "reasoning_blocks": blocks,
        "reasoning_chars_mean": round(wchars / blocks, 1) if blocks else None,
        # medians cannot be re-pooled from per-game means; carry the run's own value and
        # only trust it when nothing is excluded
        "reasoning_chars_median": p["summary"].get("reasoning_chars_median") if not exclude else None,
        "selftalk_frac_pooled": round(wself / blocks, 4) if blocks else None,
        "games": len(rows),
    }


def spread(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    if not vals:
        return None
    m = statistics.fmean(vals)
    sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
    return {"n": len(vals), "mean": m, "sd": sd, "min": min(vals), "max": max(vals),
            "cv": (sd / m) if m else None}


def fmt(v, w=10, p=2):
    if v is None:
        return "n/a".rjust(w)
    if isinstance(v, float):
        return f"{v:.{p}f}".rjust(w)
    return str(v).rjust(w)


def signflip_test(diffs, iters=200000, seed=0):
    """Two-sided randomisation test on paired differences. Returns (mean_diff, p)."""
    diffs = [d for d in diffs if d is not None]
    if not diffs:
        return None, None
    obs = abs(statistics.fmean(diffs))
    rng = random.Random(seed)
    hits = 0
    n = len(diffs)
    for _ in range(iters):
        s = 0.0
        for d in diffs:
            s += d if rng.random() < 0.5 else -d
        if abs(s / n) >= obs - 1e-12:
            hits += 1
    # +1 correction keeps p strictly positive (Phipson & Smyth)
    return statistics.fmean(diffs), (hits + 1) / (iters + 1)


def per_game_means(passes, exclude):
    """game -> (mean score across passes, [per-pass scores])"""
    out = {}
    for p in passes:
        for r in p["per_game"]:
            if r["game"] in exclude:
                continue
            s = r["official_score"]
            if isinstance(s, (int, float)):
                out.setdefault(r["game"], []).append(s)
    return out


def per_game_levels(passes, exclude):
    out = {}
    for p in passes:
        for r in p["per_game"]:
            if r["game"] in exclude:
                continue
            out.setdefault(r["game"], []).append(r["levels_completed"])
    return out


def report_arm(name, passes, exclude, lines):
    lines.append(f"\n### arm: {name}   passes: {len(passes)}"
                 + (f"   EXCLUDING {sorted(exclude)}" if exclude else ""))
    sums = [recompute_summary(p, exclude) for p in passes]
    hdr = f"{'pass':<34}" + "".join(lbl[:13].rjust(14) for _, lbl in SCALARS)
    lines.append(hdr)
    for p, s in zip(passes, sums):
        lines.append(f"{p['_name'][:33]:<34}" + "".join(fmt(s.get(k), 14, 3) for k, _ in SCALARS))
    lines.append("-" * len(hdr))
    for stat in ("mean", "sd", "min", "max"):
        row = f"{stat.upper():<34}"
        for k, _ in SCALARS:
            sp = spread([s.get(k) for s in sums])
            row += fmt(sp[stat] if sp else None, 14, 3)
        lines.append(row)
    row = f"{'CV (sd/mean)':<34}"
    for k, _ in SCALARS:
        sp = spread([s.get(k) for s in sums])
        row += fmt(sp["cv"] if sp and sp["cv"] is not None else None, 14, 3)
    lines.append(row)
    return sums


def compare(base_passes, comp_passes, exclude, lines):
    tag = "ALL GAMES" if not exclude else f"EXCLUDING {sorted(exclude)}"
    lines.append(f"\n{'=' * 100}\n## COMPARISON -- {tag}\n{'=' * 100}")
    bsum = report_arm("baseline", base_passes, exclude, lines)
    csum = report_arm("compact", comp_passes, exclude, lines)

    lines.append(f"\n{'metric':<26}{'baseline mean':>16}{'compact mean':>16}"
                 f"{'delta':>12}{'delta %':>10}{'overlap?':>10}")
    for k, lbl in SCALARS:
        b = spread([s.get(k) for s in bsum])
        c = spread([s.get(k) for s in csum])
        if not b or not c:
            continue
        d = c["mean"] - b["mean"]
        pct = (d / b["mean"] * 100) if b["mean"] else None
        ov = "YES" if not (b["max"] < c["min"] or c["max"] < b["min"]) else "no"
        lines.append(f"{lbl:<26}{fmt(b['mean'],16,3)}{fmt(c['mean'],16,3)}"
                     f"{fmt(d,12,3)}{fmt(pct,10,1)}{ov:>10}")
    lines.append("\n'overlap? YES' means the two arms' per-pass ranges intersect: with this "
                 "pass count\nthe arms are NOT distinguishable on that metric.")

    # paired per-game test on mean score
    bg = per_game_means(base_passes, exclude)
    cg = per_game_means(comp_passes, exclude)
    games = sorted(set(bg) & set(cg))
    diffs = [statistics.fmean(cg[g]) - statistics.fmean(bg[g]) for g in games]
    md, p = signflip_test(diffs)
    lines.append(f"\nPAIRED per-game mean score, {len(games)} games paired:")
    lines.append(f"  mean per-game difference (compact - baseline): {md:+.3f}")
    lines.append(f"  games compact better: {sum(1 for d in diffs if d > 1e-9)}   "
                 f"tied: {sum(1 for d in diffs if abs(d) <= 1e-9)}   "
                 f"worse: {sum(1 for d in diffs if d < -1e-9)}")
    lines.append(f"  two-sided sign-flip p = {p:.4f}  (200k permutations, seed 0)")

    bl = per_game_levels(base_passes, exclude)
    cl = per_game_levels(comp_passes, exclude)
    ldiffs = [statistics.fmean(cl[g]) - statistics.fmean(bl[g]) for g in games]
    lmd, lp = signflip_test(ldiffs)
    lines.append(f"  paired mean per-game LEVELS difference: {lmd:+.3f}, "
                 f"sign-flip p = {lp:.4f}")
    return {"games": games, "score_diffs": diffs, "score_p": p, "level_p": lp,
            "score_mean_diff": md, "level_mean_diff": lmd}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", nargs="+", required=True)
    ap.add_argument("--compact", nargs="+", required=True)
    ap.add_argument("--exclude", nargs="*", default=["sb26-7fbdac44"],
                    help="games to drop in the second comparison (default: sb26-7fbdac44)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    base = load_arm(a.baseline)
    comp = load_arm(a.compact)
    lines = ["ARC-3 compact-reasoning multi-pass A/B",
             f"baseline passes: {[p['_name'] for p in base]}",
             f"compact  passes: {[p['_name'] for p in comp]}"]

    r_all = compare(base, comp, set(), lines)
    r_ex = compare(base, comp, set(a.exclude), lines)

    # per-game, per-pass distribution -- the jackpot-rate question
    lines.append(f"\n{'=' * 100}\n## PER-GAME, PER-PASS SCORES (the jackpot-rate check)\n{'=' * 100}")
    bg = per_game_means(base, set())
    cg = per_game_means(comp, set())
    lines.append(f"{'game':<18}{'baseline passes':<34}{'compact passes':<34}"
                 f"{'b.mean':>9}{'c.mean':>9}")
    for g in sorted(set(bg) | set(cg)):
        bs = bg.get(g, [])
        cs = cg.get(g, [])
        lines.append(f"{g:<18}"
                     + (" / ".join(f"{s:.2f}" for s in bs))[:33].ljust(34)
                     + (" / ".join(f"{s:.2f}" for s in cs))[:33].ljust(34)
                     + fmt(statistics.fmean(bs) if bs else None, 9, 2)
                     + fmt(statistics.fmean(cs) if cs else None, 9, 2))

    text = "\n".join(lines)
    print(text)
    if a.out:
        open(a.out, "w").write(text + "\n")
        json.dump({"all": {k: v for k, v in r_all.items() if k != "games"},
                   "excluded": {k: v for k, v in r_ex.items() if k != "games"}},
                  open(a.out + ".json", "w"), indent=2)
        print(f"\n# wrote {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
