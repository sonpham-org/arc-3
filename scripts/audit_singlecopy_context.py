"""Audit exact saved request contexts for the reviewed-theme single-copy run."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

START = (
    "Themes from other observed games (sidecar hypotheses; verify against this game's "
    "evidence before relying on them):"
)
END = "End of reviewed cross-game themes."


def iter_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_strings(item)


def main(run_dir: Path) -> None:
    request_files = sorted((run_dir / "runs").glob("*_requests.jsonl"))
    result = {
        "request_files": len(request_files),
        "requests": 0,
        "requests_exactly_one_start_and_end": 0,
        "requests_with_zero_markers": 0,
        "requests_with_multiple_markers": 0,
        "requests_with_mismatched_markers": 0,
        "requests_marker_only_in_last_user_message": 0,
        "per_game_requests": {},
        "start_count_distribution": Counter(),
        "end_count_distribution": Counter(),
        "violations": [],
    }
    for path in request_files:
        game = path.name.removesuffix("_requests.jsonl")
        game_count = 0
        with path.open(encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                messages = record.get("messages") or []
                strings = list(iter_strings(messages))
                start_count = sum(text.count(START) for text in strings)
                end_count = sum(text.count(END) for text in strings)
                result["requests"] += 1
                game_count += 1
                result["start_count_distribution"][start_count] += 1
                result["end_count_distribution"][end_count] += 1
                if start_count == 1 and end_count == 1:
                    result["requests_exactly_one_start_and_end"] += 1
                elif start_count == 0 and end_count == 0:
                    result["requests_with_zero_markers"] += 1
                elif start_count != end_count:
                    result["requests_with_mismatched_markers"] += 1
                else:
                    result["requests_with_multiple_markers"] += 1

                user_indexes = []
                marker_user_indexes = []
                for index, message in enumerate(messages):
                    if not isinstance(message, dict) or message.get("role") != "user":
                        continue
                    user_indexes.append(index)
                    text = "\n".join(iter_strings(message.get("content")))
                    if START in text or END in text:
                        marker_user_indexes.append(index)
                only_last = (
                    start_count == 1
                    and end_count == 1
                    and len(marker_user_indexes) == 1
                    and bool(user_indexes)
                    and marker_user_indexes[0] == user_indexes[-1]
                )
                if only_last:
                    result["requests_marker_only_in_last_user_message"] += 1
                if not only_last and len(result["violations"]) < 50:
                    result["violations"].append(
                        {
                            "file": path.name,
                            "line": line_no,
                            "analysis_step": record.get("analysis_step"),
                            "action": record.get("action"),
                            "start_count": start_count,
                            "end_count": end_count,
                            "user_indexes": user_indexes,
                            "marker_user_indexes": marker_user_indexes,
                        }
                    )
        result["per_game_requests"][game] = game_count

    result["start_count_distribution"] = dict(result["start_count_distribution"])
    result["end_count_distribution"] = dict(result["end_count_distribution"])
    result["single_copy_invariant_passed"] = (
        result["requests"] > 0
        and result["requests"] == result["requests_exactly_one_start_and_end"]
        and result["requests"] == result["requests_marker_only_in_last_user_message"]
    )
    target = run_dir / "singlecopy-context-audit.json"
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
