#!/usr/bin/env python3
"""Read-only, minute-resolution ARC3 score observer.

This process is deliberately outside the gameplay harness. It only reads the
small ``*_viewer_data.json`` sidecars and writes its own files under a separate
output directory. It never imports the solver, mutates benchmark state, calls
the model, or participates in action scheduling.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_ACTIONS: dict[str, list[int]] = {
    "m0r0-492f87ba": [30, 111, 203, 26, 500, 237],
    "tr87-cd924810": [54, 58, 40, 45, 71, 146],
    "ka59-38d34dbb": [28, 109, 51, 51, 33, 132, 326],
    "cd82-fb555c5d": [55, 8, 41, 21, 23, 23],
    "vc33-5430563c": [7, 18, 44, 61, 131, 34, 152],
    "cn04-2fe56bfb": [29, 54, 85, 300, 208, 113],
    "bp35-0a0ad940": [21, 48, 44, 38, 33, 87, 86, 131, 163],
    "wa30-ee6fef47": [71, 119, 183, 98, 368, 68, 79, 442, 415],
    "ar25-0c556536": [32, 50, 75, 37, 89, 159, 233, 73],
    "tn36-ef4dde99": [32, 72, 26, 40, 30, 55, 62],
    "sb26-7fbdac44": [18, 28, 18, 19, 31, 23, 58, 18],
    "r11l-495a7899": [22, 33, 51, 26, 52, 49],
    "ft09-0d8bbf25": [43, 12, 23, 28, 65, 37],
    "lp85-305b61c3": [17, 38, 31, 16, 41, 60, 26, 159],
    "sp80-589a99af": [39, 58, 25, 148, 96, 152],
    "dc22-fdcac232": [59, 102, 67, 98, 324, 578],
    "lf52-271a04aa": [32, 81, 60, 71, 205, 148, 244, 109, 164, 225],
    "ls20-9607627b": [22, 123, 73, 84, 96, 192, 186],
    "tu93-0768757b": [19, 16, 34, 42, 123, 80, 14, 23, 111],
    "g50t-5849a774": [78, 175, 179, 230, 96, 54, 67],
    "sk48-d8078629": [61, 177, 101, 103, 230, 181, 125, 92],
    "re86-8af5384d": [26, 42, 86, 108, 189, 139, 424, 241],
    "sc25-635fd71a": [36, 6, 32, 83, 143, 50],
    "s5i5-18d95033": [20, 89, 106, 54, 162, 38, 86, 83],
    "su15-1944f8ab": [22, 42, 26, 115, 36, 31, 8, 40, 41],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def game_score(levels_completed: int, actions: list[int], baseline: list[int]) -> float:
    total_score = 0.0
    total_weights = 0
    completed_weights = 0
    for index, base in enumerate(baseline):
        weight = index + 1
        total_weights += weight
        used = actions[index] if index < len(actions) else 0
        if index < levels_completed and used > 0:
            level_score = min(115.0, (base / used) ** 2 * 100.0)
            completed_weights += weight
            total_score += level_score * weight
    if not total_weights:
        return 0.0
    return min(total_score / total_weights, completed_weights / total_weights * 100.0)


def read_snapshot(artifacts_dir: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    read_errors: list[str] = []
    paths = sorted(artifacts_dir.glob("*_viewer_data.json"))
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            game_id = str(data["game_id"])
            baseline = BASE_ACTIONS.get(game_id)
            if baseline is None:
                continue
            actions = [int(value) for value in (data.get("actions_per_level") or [])]
            levels = max(0, int(data.get("levels_completed") or 0))
            rows.append(
                {
                    "game_id": game_id,
                    "score": game_score(levels, actions, baseline),
                    "levels": levels,
                    "actions": sum(actions),
                    "status": data.get("status"),
                }
            )
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            # A writer may be replacing a sidecar at this exact instant. Skip it
            # for this sample and try again on the next minute boundary.
            read_errors.append(f"{path.name}: {type(exc).__name__}")

    scores = [float(row["score"]) for row in rows]
    padded_scores = scores + [0.0] * (len(BASE_ACTIONS) - len(scores))
    return {
        "games_reported": len(rows),
        "mean_score": sum(scores) / len(BASE_ACTIONS),
        "median_score": statistics.median(padded_scores),
        "total_levels": sum(int(row["levels"]) for row in rows),
        "total_actions": sum(int(row["actions"]) for row in rows),
        "positive_games": sum(float(row["score"]) > 0 for row in rows),
        "wins": sum(str(row.get("status") or "").upper() == "WIN" for row in rows),
        "sidecars_seen": len(paths),
        "read_error_count": len(read_errors),
        "read_errors": read_errors,
    }


def atomic_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, separators=(",", ":")) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def observe(artifacts_dir: Path, output_dir: Path, minute: int, elapsed: float) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "observer": "read_only_viewer_sidecars",
        "minute": minute,
        "gameplay_elapsed_seconds": round(elapsed, 3),
        "observed_at_utc": utc_now(),
    }
    payload.update(read_snapshot(artifacts_dir))
    append_jsonl(output_dir / "score-minute.jsonl", payload)
    atomic_json(output_dir / "score-latest.json", payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--once", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.interval_seconds <= 0:
        raise SystemExit("--interval-seconds must be positive")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    atomic_json(
        args.output_dir / "observer-meta.json",
        {
            "schema_version": 1,
            "observer": "read_only_viewer_sidecars",
            "started_at_utc": utc_now(),
            "interval_seconds": args.interval_seconds,
            "artifacts_dir": str(args.artifacts_dir),
            "output_dir": str(args.output_dir),
            "isolation": "reads viewer sidecars only; writes observer directory only",
        },
    )

    if args.once:
        print(json.dumps(observe(args.artifacts_dir, args.output_dir, 0, 0.0), separators=(",", ":")), flush=True)
        return 0

    stop = False

    def request_stop(_signum: int, _frame: Any) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    started = time.monotonic()
    minute = 0
    print(json.dumps(observe(args.artifacts_dir, args.output_dir, minute, 0.0), separators=(",", ":")), flush=True)
    while not stop:
        next_boundary = started + (minute + 1) * args.interval_seconds
        remaining = next_boundary - time.monotonic()
        if remaining > 0:
            time.sleep(min(remaining, 1.0))
            continue
        minute += 1
        elapsed = time.monotonic() - started
        print(json.dumps(observe(args.artifacts_dir, args.output_dir, minute, elapsed), separators=(",", ":")), flush=True)

    final_payload = {
        **read_snapshot(args.artifacts_dir),
        "schema_version": 1,
        "observer": "read_only_viewer_sidecars",
        "minute": int((time.monotonic() - started) // args.interval_seconds),
        "gameplay_elapsed_seconds": round(time.monotonic() - started, 3),
        "observed_at_utc": utc_now(),
        "final": True,
    }
    atomic_json(args.output_dir / "score-final.json", final_payload)
    atomic_json(args.output_dir / "score-latest.json", final_payload)
    print(json.dumps(final_payload, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
