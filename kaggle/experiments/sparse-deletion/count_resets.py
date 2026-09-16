"""
Author: Claude Opus 5
Date: 16-September-2026
PURPOSE: Report RESET use per game and pass next to level clears, which is the number Dr.
Fable's RESET-guard decision rule needs ("clears up with the rate held" vs "rate at the
cap"). Reads a downloaded Kaggle job output directory: artifacts/*_events.jsonl for executed
actions, and the job log's RESET_GUARD lines (arm I only) for refused requests, which never
reach the events file. A RESET whose preceding event is in GAME_OVER is the harness
auto-reset; any other RESET was the model's choice. Works on every arm, so the arm-B control
reports model RESETs too (it could always type one; jobs 1, 2, 4 and 10 never did).
Usage: python count_resets.py <job output dir> [<job output dir> ...]
SRP/DRY check: Pass - counting only; the guard lives in build_bundles.py.
"""

import collections
import json
import re
import sys
from pathlib import Path

REFUSED = re.compile(r"RESET_GUARD refused game=(\S+) pass=(\d+)")


def count(job_dir: Path) -> dict:
    rows = collections.defaultdict(lambda: collections.Counter())
    for path in sorted((job_dir / "artifacts").glob("*_events.jsonl")):
        game, _, pass_part = path.name.removesuffix("_events.jsonl").rpartition("_p")
        key = (game, int(pass_part))
        prev_state = None
        for line in path.open():
            event = json.loads(line)
            if event.get("type") == "action":
                rows[key]["actions"] += 1
                if event.get("action_name") == "RESET":
                    rows[key]["auto" if prev_state == "GAME_OVER" else "model"] += 1
            if "score" in event:
                rows[key]["levels"] = max(rows[key]["levels"], int(event["score"]))
            if "state" in event:
                prev_state = event["state"]
    for log in job_dir.glob("*.log"):
        if log.name.startswith("vllm"):
            continue
        for match in REFUSED.finditer(log.read_text(errors="replace")):
            rows[(match.group(1), int(match.group(2)))]["refused"] += 1
    return rows


def report(job_dir: Path) -> None:
    rows = count(job_dir)
    print(f"== {job_dir}")
    print(f"{'game':<16}{'pass':>5}{'levels':>8}{'actions':>9}{'model':>7}{'refused':>9}{'auto':>6}{'model/100':>11}")
    totals = collections.Counter()
    for (game, pass_index), c in sorted(rows.items()):
        rate = 100.0 * c["model"] / c["actions"] if c["actions"] else 0.0
        print(f"{game:<16}{pass_index:>5}{c['levels']:>8}{c['actions']:>9}{c['model']:>7}"
              f"{c['refused']:>9}{c['auto']:>6}{rate:>11.1f}")
        totals.update({k: c[k] for k in ("levels", "actions", "model", "refused", "auto")})
        if pass_index <= 2:
            totals["levels_p0_2"] += c["levels"]
    print(f"total: levels={totals['levels']} (passes 0-2: {totals['levels_p0_2']}) "
          f"actions={totals['actions']} model_resets={totals['model']} "
          f"refused={totals['refused']} auto_resets={totals['auto']}")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        report(Path(arg))
