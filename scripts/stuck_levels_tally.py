#!/usr/bin/env python3
"""
Author: Claude Opus 5.5
Date: 06-October-2026
PURPOSE: Builds docs/static/data/stuck-levels.json for the "Stuck levels" tab of the Mode explorer
  (docs/mode-explorer.html). For each of the 25 public ARC-AGI-3 games it counts, per level, how many
  recorded runs cleared that level, and from that the "safe through" level (highest L where every level
  up to L was cleared in at least 90% of runs) and the "stuck" level (L + 1). Three groups of runs are
  kept apart and never pooled:
    franzen_stock  - Franzen-notebook line, stock per-turn prompt (Son's GCP runs, 2-3 Oct 2026):
                     the seven daniel-base runs published to the site (run-overview.json per run) and the
                     four no-coach "sbt06hic11" runs in the RL2 explore files.
    franzen_coach  - same line and runs-file source, but with the RL2 mode coach switching the per-turn
                     prompt; shown only as a side column because it is not the stock prompt.
    older          - Son's earlier harness (the 18.99 line, Flash-Next pruned, SGLang) at full context
                     (93k-100k per game), from the per-run summaries the site published.
  A run reporting N levels cleared levels 1..N in order, so the per-level clear rate is a survival curve:
  the rows are not independent trials. Games whose stuck level was mostly ended by the clock rather than
  by the model are flagged from the actions spent on that level.
  Inputs are local copies (they are not in git): read with `railway ssh --service arc3-viewer` from
  /srv/data/<run>/run-overview.json and /srv/data/_rl2/explore-<game>.json, and the summaries in
  ~/bubba-workspace/arc3-kaggle/site-run-summaries/.
  Usage: stuck_levels_tally.py --overviews DIR --explore DIR --older DIR --names games.json --out FILE
SRP/DRY check: Pass - only tallies existing run files; nicknames come from
  the local explainer-games registry (datasets/explainer-games/games.json in the main checkout, not in git).
"""
import argparse
import glob
import json
import os
import re
import statistics
from datetime import date

SAFE_RATE = 0.9
THIN_RUNS = 10          # fewer runs than this and the 90% rule needs every run to clear
CLOCK_ACTIONS = 150
NEAR_LINE = 0.75        # stuck level still cleared this often: a soft spot, not a wall     # median actions spent on the stuck level at or above this: likely clock, not a wall
OLDER_CONTEXT = re.compile(r"-c(9\d|1\d\d)k-")
FRANZEN_OVERVIEW = re.compile(r"_daniel-")


def nicknames(path):
    text = open(path).read()
    return dict(re.findall(r'"gameId":\s*"(\w{4})"[^{}]*?"informalName":\s*"([^"]+)"', text))


def explore_attempt_actions(row, level):
    """Actions spent on `level` (1-based) in an explore row whose turns are [turn, action_idx, level, _]."""
    start = next((t[1] for t in row["turns"] if t[2] == level), None)
    return None if start is None else max(0, row["end"] - start)


def load(args):
    """Returns {group: {game: [ {levels, total, attempt_actions(level)->int|None, run} ]}} and run lists."""
    groups = {"franzen_stock": {}, "franzen_coach": {}, "older": {}}
    runs = {g: set() for g in groups}

    def add(group, game, levels, total, run, actions_fn):
        groups[group].setdefault(game, []).append(
            {"levels": levels, "total": total, "run": run, "actions": actions_fn})
        runs[group].add(run)

    for f in sorted(glob.glob(os.path.join(args.overviews, "*.json"))):
        name = os.path.basename(f)[:-5]
        if not FRANZEN_OVERVIEW.search(name):
            continue
        for g in json.load(open(f))["games"]:
            apl = g.get("actions_per_level") or []
            add("franzen_stock", g["game_id"][:4], g["levels_completed"], g["total_levels"], name,
                lambda lv, apl=apl: apl[lv - 1] if 0 < lv <= len(apl) else None)

    totals = {}
    for f in sorted(glob.glob(os.path.join(args.explore, "explore-????.json"))):
        d = json.load(open(f))
        for r in d["rows"]:
            if r.get("lost"):
                continue  # run died before the clock ran out; its levels are not a result
            group = "franzen_stock" if "/" not in r["arm"] else "franzen_coach"
            add(group, d["game"], r["levels"], None, r["run"],
                lambda lv, r=r: explore_attempt_actions(r, lv))

    for f in sorted(glob.glob(os.path.join(args.older, "*.json"))):
        d = json.load(open(f))
        if not OLDER_CONTEXT.search(d.get("source", "")):
            continue
        for g in d["games"]:
            totals[g["game"]] = g["total_levels"]
            apl = g.get("actions_per_level") or []
            add("older", g["game"], g["levels_completed"], g["total_levels"], d["run"],
                lambda lv, apl=apl: apl[lv - 1] if 0 < lv <= len(apl) else None)

    for group in groups.values():  # explore rows carry no level count; take it from the other sources
        for game, rows in group.items():
            for row in rows:
                if row["total"] is None:
                    row["total"] = totals[game]
    return groups, {g: sorted(r) for g, r in runs.items()}


def tally(rows):
    n = len(rows)
    total = rows[0]["total"]
    per_level = []
    for lv in range(1, total + 1):
        cleared = sum(r["levels"] >= lv for r in rows)
        per_level.append({"level": lv, "cleared": cleared, "n": n, "rate": round(cleared / n, 3)})
    safe = 0
    for p in per_level:  # monotone by construction, so the first miss ends it
        if p["rate"] < SAFE_RATE:
            break
        safe = p["level"]
    stuck = safe + 1 if safe < total else None
    out = {
        "n": n,
        "safe_through": safe,
        "stuck_level": stuck,
        "median_levels": statistics.median(r["levels"] for r in rows),
        "best": max(r["levels"] for r in rows),
        "worst": min(r["levels"] for r in rows),
        "all_clear_runs": sum(r["levels"] >= total for r in rows),
        "per_level": per_level,
    }
    if stuck:
        stopped = [r for r in rows if r["levels"] == stuck - 1]
        spent = [a for a in (r["actions"](stuck) for r in stopped) if a is not None]
        out["stuck_rate"] = per_level[stuck - 1]["rate"]
        out["near_line"] = per_level[stuck - 1]["rate"] >= NEAR_LINE
        out["stopped_at_stuck"] = len(stopped)
        out["stuck_actions_median"] = statistics.median(spent) if spent else None
        out["clock_shaped"] = bool(spent) and statistics.median(spent) >= CLOCK_ACTIONS
    return out


def main():
    ap = argparse.ArgumentParser()
    for k in ("overviews", "explore", "older", "names", "out"):
        ap.add_argument("--" + k, required=True)
    args = ap.parse_args()
    names = nicknames(args.names)
    groups, runs = load(args)
    games = []
    for code in sorted(groups["franzen_stock"]):
        main_t = tally(groups["franzen_stock"][code])
        entry = {"game": code, "nickname": names.get(code, code), "levels": main_t["per_level"][-1]["level"],
                 "thin": main_t["n"] < THIN_RUNS, **main_t}
        for side in ("franzen_coach", "older"):
            if code in groups[side]:
                t = tally(groups[side][code])
                entry[side] = {k: t[k] for k in ("n", "safe_through", "stuck_level", "median_levels", "per_level")}
        games.append(entry)
    games.sort(key=lambda g: (g["safe_through"] / g["levels"], g["median_levels"] / g["levels"], g["game"]))
    doc = {
        "meta": {
            "author": "Claude Opus 5.5 (Bubba)",
            "date": date.today().strftime("%d-%B-%Y"),
            "built_by": "scripts/stuck_levels_tally.py",
            "rule": "safe_through = highest level L such that every level 1..L was cleared in at least 90% of "
                    "runs; stuck_level = L + 1 (null when every level clears in 90% of runs).",
            "thin_rule": f"Fewer than {THIN_RUNS} runs: at that size 90% means every single run, so one bad "
                         "run moves the stuck level. Read median_levels next to it.",
            "survival_note": "A run that cleared N levels cleared levels 1..N in order, so per-level rates fall "
                             "level by level by construction; they are not independent measurements.",
            "near_line_rule": f"near_line = the stuck level is still cleared in {int(NEAR_LINE * 100)}%+ of "
                              "runs: it missed the 90% bar by a run or two, so treat it as a soft spot.",
            "clock_rule": f"clock_shaped = the runs that stopped at the stuck level spent a median of "
                          f"{CLOCK_ACTIONS}+ actions on it before time ran out: grinding, not a wall at the "
                          "first move.",
            "groups": {
                "franzen_stock": {
                    "label": "Franzen-notebook line, stock prompt",
                    "detail": "Son's GCP runs of Daniel Franzen's public notebook with Son's tuned draft head "
                              "(2-Oct cache/draft variants) and his submission-shaped build sbt06hic11 (3-Oct, "
                              "no coach), all 25 games, 132-minute suite. Same harness and prompts as the 28.94 "
                              "and 31.63 notebooks; serving settings differ run to run; not Kaggle runs.",
                    "runs": runs["franzen_stock"],
                },
                "franzen_coach": {
                    "label": "Same line, RL2 mode coach on",
                    "detail": "sbt06hic11 with the RL2 coach switching the per-turn prompt (random 30/50/70% "
                              "stock, grader modes). Not the stock prompt: a side column only.",
                    "runs": runs["franzen_coach"],
                },
                "older": {
                    "label": "Older line (18.99 harness)",
                    "detail": "Son's earlier harness, Flash-Next with experts pruned, SGLang, 93k-100k context "
                              "per game, 27-Sep to 1-Oct GCP runs (includes the partial Franzen ports "
                              "danielv2/giant, which still run the old harness).",
                    "runs": runs["older"],
                },
            },
            "not_used": "Kaggle competition submissions report one total score, no per-game levels. Son's later "
                        "Franzen-line runs (4-Oct on, score-climb page) have totals only on the site; their "
                        "per-game files were not published, so they are not in this tally.",
        },
        "games": games,
    }
    with open(args.out, "w") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")
    for g in games:
        print(f'{g["nickname"]:22s} {g["game"]} n={g["n"]:2d} safe={g["safe_through"]}/{g["levels"]} '
              f'stuck={g["stuck_level"]} median={g["median_levels"]} clock={g.get("clock_shaped")} '
              f'older={g.get("older", {}).get("safe_through")} (n={g.get("older", {}).get("n")}) '
              f'coach={g.get("franzen_coach", {}).get("safe_through")}')


if __name__ == "__main__":
    main()
