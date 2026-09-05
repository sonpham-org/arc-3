"""Read-only analysis of the immutable ARC3 champion-matrix artifacts in GCS."""

from __future__ import annotations

import json
import os
import statistics
import urllib.parse
from collections import Counter
from datetime import datetime

import requests


BUCKET = "cellens-ai-artifacts"
ROOT = "arc3-duck"
RUNS = {
    "baseline": "g4run-q38-kwbase-ab5-20260905-005421",
    "stall140": "g4run-q38-kwstall140-ab4-20260904-235921",
    "baseline_dynamic_slack": "g4run-q38-kwbase-ds-ab4-20260904-235925",
    "stall140_dynamic_slack": "g4run-q38-kwstall-ds-ab4-20260904-235923",
    "reflection_v3": "g4run-q38-kwbase-refv3-ab4-20260904-235925",
    "refinement": "g4run-q38-kwbase-refine-ab4-20260904-235923",
    "baseline_dynamic_slack_r2": "g4run-q38-kwbase-ds-r2-20260905-015136",
    "stall140_dynamic_slack_r2": "g4run-q38-kwstall-ds-r2-20260905-015136",
}


def get_text(run_id: str, relative_path: str) -> str:
    token = os.environ["ARC3_TOKEN"]
    name = f"{ROOT}/{run_id}/{relative_path}"
    encoded = urllib.parse.quote(name, safe="")
    url = f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o/{encoded}?alt=media"
    response = requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=90,
    )
    response.raise_for_status()
    return response.text


def game_row(game: dict, benchmark_start: datetime) -> dict:
    history = game.get("history") or []
    actions_per_level = [int(value) for value in game.get("actions_per_level") or []]
    started_at = datetime.fromisoformat(game["started_at"])
    return {
        "game_id": game["game_id"],
        "state": game.get("state"),
        "score": float(game.get("final_score") or 0.0),
        "levels": int(game.get("levels_completed") or 0),
        "total_levels": int(game.get("number_of_levels") or 0),
        "actions": sum(actions_per_level),
        "max_level_actions": max(actions_per_level, default=0),
        "tokens": sum(int(item.get("generated_tokens") or 0) for item in history),
        "wallclock_seconds": float(game.get("final_wallclock_seconds") or 0.0),
        "start_offset_seconds": (started_at - benchmark_start).total_seconds(),
        "stall140_threshold_reached": max(actions_per_level, default=0) >= 140,
    }


def analyze_run(run_id: str) -> dict:
    benchmark = json.loads(get_text(run_id, "runs/benchmark.json"))
    benchmark_start = datetime.fromisoformat(benchmark["start_time"])
    rows = [game_row(game, benchmark_start) for game in benchmark["game_runs"]]
    durations = [row["wallclock_seconds"] for row in rows]
    queue = [row for row in rows if row["start_offset_seconds"] > 60.0]
    return {
        "run_id": run_id,
        "suite_seconds": (
            datetime.fromisoformat(benchmark["end_time"]) - benchmark_start
        ).total_seconds(),
        "games": len(rows),
        "full_games_solved": sum(row["score"] >= 99.999 for row in rows),
        "positive_games": sum(row["score"] > 0.0 for row in rows),
        "levels": sum(row["levels"] for row in rows),
        "actions": sum(row["actions"] for row in rows),
        "generated_tokens": sum(row["tokens"] for row in rows),
        "mean_game_wallclock_seconds": statistics.mean(durations),
        "median_game_wallclock_seconds": statistics.median(durations),
        "total_lane_seconds": sum(durations),
        "queued_games": [row["game_id"] for row in queue],
        "queued_start_offsets_seconds": {
            row["game_id"]: row["start_offset_seconds"] for row in queue
        },
        "per_game": {row["game_id"]: row for row in rows},
    }


def sum_fields(rows: list[dict]) -> dict:
    return {
        "games": len(rows),
        "score_sum": sum(row["score"] for row in rows),
        "levels": sum(row["levels"] for row in rows),
        "actions": sum(row["actions"] for row in rows),
        "generated_tokens": sum(row["tokens"] for row in rows),
        "lane_seconds": sum(row["wallclock_seconds"] for row in rows),
    }


def refinement_diagnostics(run_id: str) -> dict:
    lines = get_text(run_id, "runs/artifacts/reasoning-deliberation.jsonl").splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    counts = Counter(row.get("event") for row in rows)
    auxiliary = [row for row in rows if row.get("event") == "refinement_aux_complete"]
    finals = [row for row in rows if row.get("event") == "multipass_final_complete"]
    aux_tokens = sum(
        int((row.get("draft_usage") or {}).get("total_tokens") or 0)
        + int((row.get("critique_usage") or {}).get("total_tokens") or 0)
        for row in auxiliary
    )
    requested = counts["multipass_skipped_capacity"] + len(finals) + counts["refinement_draft_failed"]
    return {
        "events": dict(counts),
        "multipass_requested": requested,
        "multipass_completed": len(finals),
        "multipass_completion_fraction": len(finals) / requested if requested else 0.0,
        "capacity_skip_fraction": counts["multipass_skipped_capacity"] / requested if requested else 0.0,
        "auxiliary_total_tokens": aux_tokens,
        "mean_auxiliary_seconds": statistics.mean(
            float(row.get("elapsed_seconds") or 0.0) for row in auxiliary
        ),
        "mean_final_revision_seconds": statistics.mean(
            float(row.get("elapsed_seconds") or 0.0) for row in finals
        ),
    }


def main() -> None:
    analyses = {name: analyze_run(run_id) for name, run_id in RUNS.items()}
    baseline = analyses["baseline"]["per_game"]
    stall = analyses["stall140"]["per_game"]

    triggered_ids = sorted(
        game_id
        for game_id, row in stall.items()
        if row["stall140_threshold_reached"]
    )
    rest_ids = sorted(set(stall) - set(triggered_ids))
    queued_ids = sorted(set(analyses["stall140"]["queued_games"]) | set(analyses["baseline"]["queued_games"]))

    comparison = {
        "stall_threshold_game_ids": triggered_ids,
        "stall_threshold_games": {
            game_id: {"baseline": baseline[game_id], "stall140": stall[game_id]}
            for game_id in triggered_ids
        },
        "non_threshold_aggregate": {
            "baseline": sum_fields([baseline[game_id] for game_id in rest_ids]),
            "stall140": sum_fields([stall[game_id] for game_id in rest_ids]),
        },
        "queued_game_aggregate": {
            "game_ids": queued_ids,
            "baseline": sum_fields([baseline[game_id] for game_id in queued_ids]),
            "stall140": sum_fields([stall[game_id] for game_id in queued_ids]),
        },
        "all_game_aggregate": {
            "baseline": sum_fields(list(baseline.values())),
            "stall140": sum_fields(list(stall.values())),
        },
    }
    result = {
        "runs": {
            name: {key: value for key, value in data.items() if key != "per_game"}
            for name, data in analyses.items()
        },
        "baseline_vs_stall140": comparison,
        "refinement": refinement_diagnostics(RUNS["refinement"]),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
