#!/usr/bin/env python3
"""Score a game's difficulty curve: does each level ask for more than the last?

Author: Claude Opus 5, 19-September-2026
Purpose: these games are training data. A game whose levels sit at one difficulty teaches a
model (or a person) one thing and then repeats it, and a game that jumps straight to hard
teaches nothing at all. The loop's final step shapes the curve, and this scores it.

Three sources of evidence:

- **Measured.** The winning trace's actions per level, which is what the game costs to solve.
  It is a proxy, not difficulty itself: a long dull level is long, not hard. That is why the
  shape below is declared and reviewed rather than inferred.
- **Declared.** `metadata.json` carries a `curriculum`: one entry per level with its role, the
  mechanics it introduces, and one line on what it asks that the level before did not.
- **Felt.** Someone plays the levels in order and rates what each one demands of them, 1 to 5,
  and says whether the game feels like it climbs. This is the judgement the other two serve:
  a game can read as a tidy rising ladder of action counts and still feel like the same puzzle
  eight times. Pass `--felt report.json`:
  `{"played_by": "...", "levels": [{"level": 1, "demand": 1, "what_it_adds": "...",
  "actions_taken": 9, "solved": true}, ...], "verdict": "climbs|flat|jumps", "notes": "..."}`.
  When it is given, the felt reading is a hard gate: the demands must rise and the verdict
  must be `climbs`, whatever the measured score says.

The roles, in order, with how many levels each may take:

    teach      1      the mechanic is visible; a couple of actions win; nothing can be lost
    stretch    0-2    the same mechanic, asked for harder: bigger map, more pieces, longer chain
    introduce  1      a second mechanic arrives, taught as plainly as the first
    combine    1-2    both mechanics in one problem, harder than either alone
    turn       1      one or two more mechanics, or a known rule changes, or the view hides
                      something the player was relying on
    compose    2      everything so far, at full size
    finale     0-1    the hardest level in the game; it may carry one last mechanic

`introduce` and `combine` may run twice for a longer game. Every introduced mechanic must
come back in a later level: a mechanic used once is a detour, not a curriculum.

Usage:
  python scripts/curve_score.py --source game.py --trace game.trace.json \
      --metadata metadata.json [--out curve.json] [--profile seed|glowup]
Exit status: 0 pass, 1 fail, 2 could not run.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOOL = "curve_score.py/1"
ROLES = ("teach", "stretch", "introduce", "combine", "turn", "compose", "finale")
LETTERS = {"teach": "T", "stretch": "S", "introduce": "I", "combine": "C", "turn": "X", "compose": "P", "finale": "F"}
# teach, then optional stretch, one or two introduce+combine cycles, a turn, two composes, an optional finale.
SHAPE = r"T S{0,2} (I C{1,2}){1,2} X P{2} F{0,1}"
PASS_MARK = 75
HARD_TREND = 0.5


def spearman(values: list[float]) -> float:
    """Rank correlation between level order and level cost, without scipy."""
    n = len(values)
    if n < 3:
        return 0.0
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:  # average the ranks of ties
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        shared = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = shared
        i = j + 1
    mean = (n + 1) / 2
    top = sum((i + 1 - mean) * (ranks[i] - mean) for i in range(n))
    bottom = (sum((i + 1 - mean) ** 2 for i in range(n)) * sum((r - mean) ** 2 for r in ranks)) ** 0.5
    return round(top / bottom, 3) if bottom else 0.0


def shape_of(curriculum: list[dict]) -> str:
    return "".join(LETTERS.get(str(entry.get("role", "")).lower(), "?") for entry in curriculum)


def shape_matches(letters: str) -> bool:
    import re

    return bool(re.fullmatch(SHAPE.replace(" ", ""), letters))


def check_shape(curriculum: list[dict], levels: int) -> tuple[int, dict[str, Any]]:
    if not curriculum:
        return 0, {"status": "fail", "detail": "metadata.json has no curriculum: declare each level's role, what it introduces, and what it asks that the level before did not"}
    if len(curriculum) != levels:
        return 0, {"status": "fail", "detail": f"curriculum covers {len(curriculum)} levels, the game has {levels}"}
    letters = shape_of(curriculum)
    unknown = sorted({str(e.get("role", "")) for e in curriculum if str(e.get("role", "")).lower() not in ROLES})
    if unknown:
        return 0, {"status": "fail", "detail": f"unknown roles {unknown}; use {list(ROLES)}"}
    if not shape_matches(letters):
        return 0, {"status": "fail", "detail": f"roles read {letters}, which is not the shape {SHAPE} (see this tool's header)"}
    introduced: dict[str, int] = {}
    for index, entry in enumerate(curriculum):
        for mechanic in entry.get("introduces") or []:
            introduced.setdefault(str(mechanic), index)
    if not introduced:
        return 10, {"status": "fail", "detail": "no level declares a mechanic it introduces"}
    later_use = {
        mechanic: any(mechanic in (e.get("uses") or e.get("introduces") or []) for e in curriculum[first + 1 :])
        for mechanic, first in introduced.items()
    }
    orphans = sorted(m for m, used in later_use.items() if not used)
    missing_why = [e.get("level", i + 1) for i, e in enumerate(curriculum[1:], 1) if not str(e.get("why_harder", "")).strip()]
    points = 25 - 8 * bool(orphans) - 5 * bool(missing_why)
    detail = f"roles {letters}; {len(introduced)} mechanics introduced"
    if orphans:
        detail += f"; introduced once and never used again: {orphans} (list them in a later level's `uses`)"
    if missing_why:
        detail += f"; no `why_harder` on levels {missing_why}"
    return max(0, points), {"status": "pass" if points == 25 else "warn", "detail": detail}


def check_felt(felt: dict) -> tuple[dict[str, Any], dict[str, Any]]:
    """The played reading: do the levels demand more as they go, and did it feel that way?"""
    levels = felt.get("levels") or []
    demands = [float(level.get("demand", 0)) for level in levels]
    verdict = str(felt.get("verdict", "")).lower()
    if len(demands) < 3:
        problem = {"status": "fail", "detail": "a felt report needs a demand rating for at least three levels"}
        return problem, problem
    trend = spearman(demands)
    rising = trend >= 0.5 and demands[-1] > demands[0]
    return (
        {"status": "pass" if rising else "fail",
         "detail": f"demand ratings {[int(d) for d in demands]} (rank correlation {trend}); they must rise"},
        {"status": "pass" if verdict == "climbs" else "fail",
         "detail": f"the player who played it says the difficulty {verdict or 'was not judged'}"
                   + (f": {felt['notes']}"[:200] if felt.get("notes") else "")},
    )


def score(actions: list[int], curriculum: list[dict], profile: str, felt: dict | None = None) -> dict[str, Any]:
    levels = len(actions)
    checks: dict[str, dict[str, Any]] = {}
    points = 0

    got, checks["shape"] = check_shape(curriculum, levels)
    points += got

    trend = spearman([float(a) for a in actions])
    trend_points = max(0, min(25, round((trend - 0.2) / 0.6 * 25)))
    checks["rising"] = {
        "status": "pass" if trend >= HARD_TREND else "fail",
        "detail": f"rank correlation between level order and actions is {trend} (needs {HARD_TREND}); actions per level: {actions}",
    }
    points += trend_points

    median = sorted(actions)[levels // 2]
    teach_ok = actions[0] <= 10 and actions[0] <= 0.5 * median
    checks["teach_first"] = {
        "status": "pass" if teach_ok else "fail",
        "detail": f"level 1 takes {actions[0]} actions; it must be at most 10 and at most half the median level ({median})",
    }
    points += 15 if teach_ok else 0

    third = max(1, levels // 3)
    early = sum(actions[:third]) / third
    late = sum(actions[-third:]) / third
    growth = round(late / early, 2) if early else 0
    growth_points = max(0, min(15, round((growth - 1.0) / 0.6 * 15)))
    checks["growth"] = {
        "status": "pass" if growth >= 1.6 else ("warn" if growth >= 1.2 else "fail"),
        "detail": f"the last third averages {late:.1f} actions against the first third's {early:.1f} ({growth}x; 1.6x is the target)",
    }
    points += growth_points

    flat = [i + 2 for i in range(levels - 2) if max(actions[i : i + 3]) <= 1.12 * min(actions[i : i + 3])]
    checks["no_plateau"] = {
        "status": "pass" if not flat else "warn",
        "detail": "no three levels in a row sit at one size" if not flat else f"levels around {flat} are within 12% of each other: the curve goes flat there",
    }
    points += 10 if not flat else 0

    hardest = max(actions)
    finale_ok = actions[-1] >= 0.9 * hardest
    checks["finale"] = {
        "status": "pass" if finale_ok else "warn",
        "detail": f"the last level takes {actions[-1]} actions against the game's longest {hardest}",
    }
    points += 10 if finale_ok else 0

    if felt:
        checks["felt_rising"], checks["felt_verdict"] = check_felt(felt)
    hard_gates = [checks["rising"]["status"] != "fail", checks["teach_first"]["status"] != "fail"]
    if profile != "seed":
        hard_gates.append(checks["shape"]["status"] != "fail")
    if felt:  # a played reading outranks the proxy: it is what "harder" means
        hard_gates += [checks["felt_rising"]["status"] == "pass", checks["felt_verdict"]["status"] == "pass"]
    return {
        "levels": levels,
        "actions_per_level": actions,
        "trend": trend,
        "growth": growth,
        "checks": checks,
        "score": points,
        "verdict": "pass" if points >= PASS_MARK and all(hard_gates) else "fail",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--trace", required=True, type=Path, help="the winning trace (arc3-trace/1)")
    parser.add_argument("--metadata", type=Path, help="metadata.json holding the declared curriculum")
    parser.add_argument("--source", type=Path, help="recorded in the report, for provenance")
    parser.add_argument("--profile", choices=("seed", "glowup"), default="glowup")
    parser.add_argument("--felt", type=Path, help="a played report: per-level demand ratings and whether it climbs")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    try:
        trace = json.loads(args.trace.read_text(encoding="utf-8"))
        actions = [len(level["actions"]) for level in trace["levels"]]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"curve_score: unreadable trace ({exc})", file=sys.stderr)
        return 2
    if len(actions) < 3:
        print("curve_score: a game needs at least three levels to have a curve", file=sys.stderr)
        return 2
    curriculum = []
    if args.metadata and args.metadata.exists():
        curriculum = json.loads(args.metadata.read_text(encoding="utf-8")).get("curriculum") or []

    report = {
        "tool": TOOL,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": args.source.name if args.source else None,
        "profile": args.profile,
        **score(actions, curriculum, args.profile, json.loads(args.felt.read_text(encoding="utf-8")) if args.felt else None),
    }
    if args.out:
        args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    width = max(len(name) for name in report["checks"])
    for name, check in report["checks"].items():
        print(f"  {check['status'].upper():4}  {name:<{width}}  {check['detail']}")
    print(f"curve: {report['score']}/100  {report['verdict'].upper()}  (trend {report['trend']}, growth {report['growth']}x, levels {report['levels']})")
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
