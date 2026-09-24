#!/usr/bin/env python3
# Author: Claude Opus 5.5 (Bubba)
# Date: 23-September-2026
# PURPOSE: Offline test of the active-inference "count-based novelty bonus / inhibition of return"
#   idea (bubba-workspace/docs/2026-09-23-active-inference-ideas-for-arc3.md) before anyone builds
#   it: do level attempts the agent SOLVED show more exploration of untried actions early in the
#   level than attempts it FAILED? Reads the harness's per-run `artifacts/*_events.jsonl` (one JSON
#   row per action with the post-action board, action name/display, board_changed, level_completed,
#   game_over) from existing run directories only -- it launches nothing and writes only its own
#   results. Splits every play into level attempts (ended by a level clear, a game over, a RESET, or
#   the end of the log), maps each action to a per-game-type "context" (button id, button id per
#   coarse board state, or the clicked object/coarse cell for MOUSE clicks, taken from the board
#   BEFORE the click), and measures over the first N actions (N = 10, 20, 40; only attempts that
#   lasted at least N actions): first-time-in-context fraction, longest same-context streak,
#   no-change rate, repeats of a context already known to do nothing, and how soon each valid
#   action was first tried. Compares solved vs failed attempts within each game, both raw and
#   level-matched (same game and same level index, which removes the "solves are early levels"
#   confound). Flash-Next (Kaggle) and dense 27B (Jethro / Mini) are never pooled.
#   Game nicknames come from bubba-workspace/skills/arc3-games/scripts/arc3_games.py.
# SRP/DRY check: Pass -- searched distill/ (extract_sft, corpus_stats, verify_frames,
#   recordings_to_sft) and bubba-workspace; nothing segments events into level attempts or measures
#   action novelty. Nickname lookup is imported from the arc3-games skill, not duplicated.
"""Novelty of early actions in solved vs failed ARC-3 level attempts.

Usage:
    python distill/novelty_vs_solves.py                       # default run sets, markdown to stdout
    python distill/novelty_vs_solves.py --out results/novelty_vs_solves

Writes attempts.csv (one row per attempt x N) and summary.json into --out.
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import importlib.util
import json
import os
import random
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

HOME = Path.home()
WINDOWS = (10, 20, 40)
BLOCK = 8                 # coarse cell size on the 64x64 board
BACKGROUND_AREA = 512     # a clicked component bigger than 1/8 of the board is treated as background
MIN_SOLVED_FOR_CALL = 3   # fewer solved attempts than this in a cell -> "too thin"
SHUFFLES = 400            # within-level label shuffles for the noise band
GAP_CALL = 0.02           # smallest level-matched gap in new-context share that gets a direction

# Run directories per model family. Each dir must hold artifacts/*_events.jsonl.
# arc3-sft/runs-jethro is a copy of Jethro runs and is left out to avoid double counting;
# "oracle" runs on the Mini were fed scripted help and are left out as not the agent's own play.
RUN_SETS = {
    "Flash-Next (Kaggle)": [
        str(HOME / "arc3-job-output/*"),
        str(HOME / "bubba-workspace/arc3-kaggle/best-7.36/output"),
        str(HOME / "bubba-workspace/arc3-kaggle/arms/results/arm*/output"),
    ],
    "dense 27B (Jethro / Mini)": [
        str(HOME / "bubba-workspace/arc3-novelty-data/jethro/*"),   # rsync'd read-only from ~/arc3-nosp/runs
        str(HOME / "GitHub/arc-3/ARC3-Inference/runs/*"),
        str(HOME / "bubba-workspace/arc3-sft/runs/*"),
    ],
}
EXCLUDE_RUN_PATTERNS = ("oracle",)

NAME_TO_ID = {"UP": "ACTION1", "DOWN": "ACTION2", "LEFT": "ACTION3", "RIGHT": "ACTION4",
              "SPACE": "ACTION5", "MOUSE": "ACTION6", "ACTION7": "ACTION7"}
MOUSE_RE = re.compile(r"row=(\d+),\s*col=(\d+)")
VALID_RE = re.compile(r"Valid actions right now: ([A-Z0-9, ]+)")


def load_nicknames() -> dict:
    path = HOME / "bubba-workspace/skills/arc3-games/scripts/arc3_games.py"
    spec = importlib.util.spec_from_file_location("arc3_games", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.names()


# ---------------------------------------------------------------- contexts

def component_key(board, r, c):
    """Bounding box of the 4-connected same-colour component under (r, c) in the pre-click board.

    Colour is left out of the key on purpose: toggle-style games recolour the clicked object, and a
    second click on the same object must still count as a repeat.
    """
    h, w = len(board), len(board[0])
    if not (0 <= r < h and 0 <= c < w):
        return ("off", r // BLOCK, c // BLOCK)
    colour = board[r][c]
    seen = {(r, c)}
    stack = [(r, c)]
    r0 = r1 = r
    c0 = c1 = c
    while stack:
        y, x = stack.pop()
        r0, r1, c0, c1 = min(r0, y), max(r1, y), min(c0, x), max(c1, x)
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in seen and board[ny][nx] == colour:
                seen.add((ny, nx))
                stack.append((ny, nx))
                if len(seen) > BACKGROUND_AREA:
                    return ("bg", r // BLOCK, c // BLOCK)
    return ("obj", r0, c0, r1, c1)


def coarse_signature(board) -> str:
    """Mode colour of every BLOCK x BLOCK cell: a board-state key that a one-pixel step counter
    or progress bar does not perturb, unlike an exact board hash."""
    h, w = len(board), len(board[0])
    cells = []
    for by in range(0, h, BLOCK):
        for bx in range(0, w, BLOCK):
            cnt = Counter(board[y][x] for y in range(by, min(by + BLOCK, h))
                          for x in range(bx, min(bx + BLOCK, w)))
            cells.append(cnt.most_common(1)[0][0])
    return hashlib.md5(bytes(cells)).hexdigest()[:12]


# ---------------------------------------------------------------- segmentation

def parse_events(path: str):
    """Yield (valid_actions, attempts) for one play file."""
    valid = None
    attempts = []
    cur = None
    board = None
    attempt_no_by_level = Counter()

    def start(level, kind):
        attempt_no_by_level[level] += 1
        return {"level": level, "retry": attempt_no_by_level[level] - 1, "steps": [], "start": kind}

    def close(outcome):
        nonlocal cur
        if cur is not None and cur["steps"]:
            cur["outcome"] = outcome
            attempts.append(cur)
        cur = None

    with open(path) as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = row.get("type")
            if kind == "analysis" and valid is None:
                m = VALID_RE.search(row.get("transcript") or "")
                if m:
                    valid = [NAME_TO_ID.get(t.strip(), t.strip()) for t in m.group(1).split(",") if t.strip()]
                continue
            if kind == "initial":
                board = row.get("board")
                cur = start(row.get("level", 1), "initial")
                continue
            if kind != "action":
                continue
            name = row.get("action_name")
            post = row.get("board")
            if name == "RESET":
                close("reset")
                board = post
                cur = start(row.get("level", 1), "reset")
                continue
            if cur is None:
                cur = start(row.get("level", 1), "after_end")
            pre = board
            if name == "ACTION6":
                m = MOUSE_RE.search(row.get("action_display", ""))
                r, c = (int(m.group(1)), int(m.group(2))) if m else (-1, -1)
                obj = component_key(pre, r, c) if pre else ("nopre", r // BLOCK, c // BLOCK)
                block = ("blk", r // BLOCK, c // BLOCK)
                ctx_main, ctx_alt = ("M",) + obj, ("M",) + block
            else:
                ctx_main = (name,)
                ctx_alt = (name, coarse_signature(pre) if pre else "nopre")
            cur["steps"].append({"action": name, "ctx": ctx_main, "ctx_alt": ctx_alt,
                                 "changed": bool(row.get("board_changed"))})
            board = post
            if row.get("level_completed"):
                close("solved")
                cur = start(row.get("level", 1), "level_start")
            elif row.get("game_over"):
                close("died")
                cur = start(row.get("level", 1), "game_over")
    close("truncated")
    return valid, attempts


# ---------------------------------------------------------------- metrics

def window_metrics(steps, n, valid):
    w = steps[:n]
    seen, seen_alt = set(), set()
    dead = set()           # contexts already seen to change nothing
    novel = novel_alt = 0
    dead_repeats = 0
    longest = run = 0
    prev = None
    first_try = {}
    for i, s in enumerate(w):
        if s["ctx"] not in seen:
            novel += 1
            seen.add(s["ctx"])
        if s["ctx_alt"] not in seen_alt:
            novel_alt += 1
            seen_alt.add(s["ctx_alt"])
        if s["ctx"] in dead:
            dead_repeats += 1
        if not s["changed"]:
            dead.add(s["ctx"])
        run = run + 1 if s["ctx"] == prev else 1
        longest = max(longest, run)
        prev = s["ctx"]
        first_try.setdefault(s["action"], i + 1)
    out = {
        "novel_frac": novel / n,
        "novel_alt_frac": novel_alt / n,
        "longest_streak": longest,
        "nochange_rate": sum(not s["changed"] for s in w) / n,
        "dead_repeat_rate": dead_repeats / n,
    }
    buttons = [a for a in (valid or []) if a != "ACTION6"]
    if len(valid or []) > 1:
        tried = [first_try.get(a, n + 1) for a in valid]
        out["valid_coverage"] = sum(t <= n for t in tried) / len(valid)
        out["mean_first_try"] = sum(tried) / len(tried)
    if buttons:
        out["button_coverage"] = sum(a in first_try for a in buttons) / len(buttons)
    return out


def game_type(valid):
    if not valid:
        return "unknown"
    has_mouse = "ACTION6" in valid
    arrows = [a for a in valid if a in ("ACTION1", "ACTION2", "ACTION3", "ACTION4")]
    if has_mouse and not arrows:
        return "click"
    if not has_mouse:
        return "button"
    return "mixed"


# ---------------------------------------------------------------- driver

def collect(run_globs):
    plays = []
    seen_dirs = set()
    for pattern in run_globs:
        for d in sorted(glob.glob(pattern)):
            if any(p in d for p in EXCLUDE_RUN_PATTERNS):
                continue
            key = os.path.basename(d.rstrip("/"))
            if key in seen_dirs and key not in ("output",):
                continue
            seen_dirs.add(key)
            for f in sorted(glob.glob(os.path.join(d, "artifacts", "*_events.jsonl"))):
                plays.append((d, f))
    return plays


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def analyse(family, run_globs, nick):
    plays = collect(run_globs)
    valid_by_game = {}
    rows = []
    for run_dir, f in plays:
        game = os.path.basename(f)[:4]
        valid, attempts = parse_events(f)
        if valid:
            valid_by_game.setdefault(game, valid)
        for a_i, att in enumerate(attempts):
            run = os.path.basename(run_dir.rstrip("/")) if not run_dir.endswith("output") else run_dir.split("/")[-2]
            for n in WINDOWS:
                if len(att["steps"]) < n:
                    continue
                m = window_metrics(att["steps"], n, valid or valid_by_game.get(game))
                rows.append({"family": family, "run": run,
                             "file": os.path.basename(f), "game": game, "level": att["level"],
                             "retry": att["retry"], "outcome": att["outcome"],
                             "solved": att["outcome"] == "solved", "length": len(att["steps"]),
                             "N": n, **m})
            rows.append({"family": family, "run": run, "file": os.path.basename(f), "game": game,
                         "level": att["level"], "outcome": att["outcome"],
                         "solved": att["outcome"] == "solved", "length": len(att["steps"]), "N": 0})
    return rows, valid_by_game


METRICS = ("novel_frac", "novel_alt_frac", "longest_streak", "nochange_rate", "dead_repeat_rate",
           "valid_coverage", "mean_first_try")


def summarise(rows, valid_by_game, nick):
    """Per game and N: solved vs failed means, and the level-matched difference."""
    out = {}
    games = sorted({r["game"] for r in rows})
    for g in games:
        g_rows = [r for r in rows if r["game"] == g]
        all_att = [r for r in g_rows if r["N"] == 0]
        entry = {
            "nickname": nick.get(g, "UNKNOWN"),
            "type": game_type(valid_by_game.get(g)),
            "attempts": len(all_att),
            "solved_attempts": sum(r["solved"] for r in all_att),
            "solved_median_length": statistics.median([r["length"] for r in all_att if r["solved"]]) if any(r["solved"] for r in all_att) else None,
            "by_N": {},
        }
        for n in WINDOWS:
            w = [r for r in g_rows if r["N"] == n]
            sol = [r for r in w if r["solved"]]
            fail = [r for r in w if not r["solved"]]
            cell = {"n_solved": len(sol), "n_failed": len(fail),
                    "solved_mean_level": mean([r["level"] for r in sol]),
                    "failed_mean_level": mean([r["level"] for r in fail])}
            for k in METRICS:
                cell[f"solved_{k}"] = mean([r[k] for r in sol if k in r])
                cell[f"failed_{k}"] = mean([r[k] for r in fail if k in r])
            diffs, n_levels, n_sol_matched = matched_diffs(w)
            cell["matched_levels"] = n_levels
            cell["matched_solved"] = n_sol_matched
            for k in METRICS:
                cell[f"matched_diff_{k}"] = diffs.get(k)
            cell["thin"] = n_sol_matched < MIN_SOLVED_FOR_CALL
            # First tries only: drops retries after a game over or RESET.
            ft, _, ft_sol = matched_diffs([r for r in w if r["retry"] == 0])
            cell["firsttry_matched_diff_novel_frac"] = ft.get("novel_frac")
            cell["firsttry_matched_solved"] = ft_sol
            # Noise band: shuffle solved/failed labels within each level, keep the 5th-95th
            # percentile of the resulting gap. A real gap should sit outside it.
            cell["shuffle_band_novel_frac"] = shuffle_band(w) if n_levels else None
            entry["by_N"][n] = cell
        out[g] = entry
    return out


def matched_diffs(w):
    """Level-matched solved-minus-failed gap: per level that has both outcomes, difference of
    means; then the plain average across those levels."""
    matched = defaultdict(list)
    n_levels = n_sol = 0
    for lvl in sorted({r["level"] for r in w}):
        ls = [r for r in w if r["level"] == lvl and r["solved"]]
        lf = [r for r in w if r["level"] == lvl and not r["solved"]]
        if not ls or not lf:
            continue
        n_levels += 1
        n_sol += len(ls)
        for k in METRICS:
            a = [r[k] for r in ls if k in r]
            b = [r[k] for r in lf if k in r]
            if a and b:
                matched[k].append(mean(a) - mean(b))
    return {k: mean(v) for k, v in matched.items() if v}, n_levels, n_sol


def shuffle_band(w, key="novel_frac"):
    rng = random.Random(0)
    by_level = defaultdict(list)
    for r in w:
        by_level[r["level"]].append(r)
    gaps = []
    for _ in range(SHUFFLES):
        per_level = []
        for rows in by_level.values():
            k = sum(r["solved"] for r in rows)
            if k == 0 or k == len(rows):
                continue
            vals = [r[key] for r in rows]
            rng.shuffle(vals)
            per_level.append(mean(vals[:k]) - mean(vals[k:]))
        if per_level:
            gaps.append(mean(per_level))
    gaps.sort()
    return (gaps[int(0.05 * len(gaps))], gaps[int(0.95 * len(gaps)) - 1]) if gaps else None


def call_for(c):
    """Direction of the level-matched gap in new-context share, or why there is none.

    "(inside noise)" is appended when the gap sits inside the within-level shuffle band."""
    d = c["matched_diff_novel_frac"]
    if c["n_solved"] == 0:
        return "no solves"
    if c["thin"] or d is None:
        return "too thin"
    if abs(d) <= GAP_CALL:
        return "no gap"
    word = "solved explore more" if d > 0 else "failed explore more"
    lo_hi = c.get("shuffle_band_novel_frac")
    if lo_hi and lo_hi[0] <= d <= lo_hi[1]:
        word += " (inside noise)"
    return word


def band(c):
    b = c.get("shuffle_band_novel_frac")
    return f"{b[0]:+.3f} to {b[1]:+.3f}" if b else "-"


def fmt(x, digits=2):
    return "-" if x is None else (f"{x:.{digits}f}" if isinstance(x, float) else str(x))


def markdown(family, summary):
    lines = [f"### {family}", ""]
    for n in WINDOWS:
        lines += [f"**First {n} actions of the level** (attempts that lasted at least {n} actions)", "",
                  "| Game | Type | Solved / failed attempts | Mean level solved / failed | New-context share solved / failed | Level-matched difference (solved minus failed) | Longest streak solved / failed | No-change share solved / failed | Repeats of a known dud solved / failed | Level-matched no-change difference | Shuffle noise band | Level-matched difference, first tries only | Call |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for g, e in sorted(summary.items(), key=lambda kv: kv[1]["nickname"]):
            c = e["by_N"][n]
            if c["n_solved"] + c["n_failed"] == 0:
                continue
            d = c["matched_diff_novel_frac"]
            call = call_for(c)
            lines.append(
                f"| {e['nickname']} | {e['type']} | {c['n_solved']} / {c['n_failed']} "
                f"| {fmt(c['solved_mean_level'],1)} / {fmt(c['failed_mean_level'],1)} "
                f"| {fmt(c['solved_novel_frac'])} / {fmt(c['failed_novel_frac'])} "
                f"| {fmt(d,3) if d is not None else '-'} (levels {c['matched_levels']}, solved {c['matched_solved']}) "
                f"| {fmt(c['solved_longest_streak'],1)} / {fmt(c['failed_longest_streak'],1)} "
                f"| {fmt(c['solved_nochange_rate'])} / {fmt(c['failed_nochange_rate'])} "
                f"| {fmt(c['solved_dead_repeat_rate'])} / {fmt(c['failed_dead_repeat_rate'])} "
                f"| {fmt(c['matched_diff_nochange_rate'],3) if c['matched_diff_nochange_rate'] is not None else '-'} "
                f"| {band(c)} | {fmt(c['firsttry_matched_diff_novel_frac'],3) if c['firsttry_matched_diff_novel_frac'] is not None else '-'} "
                f"| {call} |")
        lines.append("")
    # Secondary context (button id x coarse board, or coarse click cell) and action coverage at N=10.
    lines += ["**Alternative context and action coverage, first 10 actions**", "",
              "| Game | Type | New alt-context share solved / failed | Level-matched alt difference | Valid actions tried solved / failed | Mean first-try position solved / failed |",
              "|---|---|---|---|---|---|"]
    for g, e in sorted(summary.items(), key=lambda kv: kv[1]["nickname"]):
        c = e["by_N"][10]
        if c["n_solved"] == 0:
            continue
        lines.append(f"| {e['nickname']} | {e['type']} | {fmt(c['solved_novel_alt_frac'])} / {fmt(c['failed_novel_alt_frac'])} "
                     f"| {fmt(c['matched_diff_novel_alt_frac'],3) if c['matched_diff_novel_alt_frac'] is not None else '-'} "
                     f"| {fmt(c['solved_valid_coverage'])} / {fmt(c['failed_valid_coverage'])} "
                     f"| {fmt(c['solved_mean_first_try'],1)} / {fmt(c['failed_mean_first_try'],1)} |")
    lines.append("")
    return "\n".join(lines)


def tally(summary, n):
    """Count games by direction of the level-matched novelty gap, split by game type."""
    t = defaultdict(Counter)
    for e in summary.values():
        t[e["type"]][call_for(e["by_N"][n])] += 1
    return {k: dict(v) for k, v in t.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(Path(__file__).parent / "results/novelty_vs_solves"))
    args = ap.parse_args()
    nick = load_nicknames()
    os.makedirs(args.out, exist_ok=True)
    report = {}
    all_rows = []
    for family, globs_ in RUN_SETS.items():
        rows, valid = analyse(family, globs_, nick)
        all_rows += rows
        summary = summarise(rows, valid, nick)
        report[family] = {"games": summary, "tally": {n: tally(summary, n) for n in WINDOWS},
                          "plays": len({(r["run"], r["file"]) for r in rows if r["N"] == 0}),
                          "attempts": sum(r["N"] == 0 for r in rows),
                          "solved_attempts": sum(r["N"] == 0 and r["solved"] for r in rows)}
        print(markdown(family, summary))
        for n in WINDOWS:
            print(f"Tally at first {n} ({family}):", json.dumps(report[family]["tally"][n]))
        print()
    with open(os.path.join(args.out, "summary.json"), "w") as fh:
        json.dump(report, fh, indent=1, default=str)
    keys = sorted({k for r in all_rows for k in r})
    with open(os.path.join(args.out, "attempts.csv"), "w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=keys)
        wr.writeheader()
        wr.writerows(all_rows)


if __name__ == "__main__":
    main()
