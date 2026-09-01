"""Build and validate one database-backed ARC3 run submission."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from .model_metadata import ModelMetadataError, validate_model_metadata
except ImportError:  # Docker copies both modules beside each other.
    from model_metadata import ModelMetadataError, validate_model_metadata


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_kind(relative_path: str) -> str:
    name = Path(relative_path).name
    if name == "run-overview.json":
        return "overview"
    if name == "run-timeline.json":
        return "timeline"
    if name == "run-submission.json":
        return "submission"
    if name == "usage.json":
        return "usage"
    if name.endswith("-frames.json"):
        return "frames"
    if "-step-" in name:
        return "step"
    if name.startswith("game-"):
        return "game"
    return "viewer"


def find_catalog_entry(index: dict[str, Any], run_name: str) -> dict[str, Any]:
    matches = [row for row in index.get("runs") or [] if row.get("run") == run_name]
    if len(matches) != 1:
        raise ValueError(f"expected one catalog entry for {run_name}, found {len(matches)}")
    return dict(matches[0])


def validate_catalog_consistency(
    run_name: str,
    entry: dict[str, Any],
    timeline: dict[str, Any],
) -> None:
    if timeline.get("run") != run_name:
        raise ValueError(f"timeline run mismatch: {timeline.get('run')!r} != {run_name!r}")
    curve = timeline.get("scoreCurve") or {}
    points = curve.get("points") or []
    if len(points) < 2:
        raise ValueError("timestamped score curve must contain at least start and end points")
    final_score = float(curve.get("finalMeanScore") or points[-1].get("meanScore") or 0)
    index_score = float(entry.get("avg_score") or 0)
    # The catalog averages per-game scores after rounding each game to three
    # decimals, while the timeline preserves raw game scores. Their final
    # means can therefore straddle a display-rounding boundary by < 0.001.
    if abs(final_score - index_score) >= 0.001:
        raise ValueError(
            f"score mismatch: catalog={index_score:.9f}, score curve={final_score:.9f}"
        )
    if int(curve.get("finalActions") or 0) != int(entry.get("actions") or 0):
        raise ValueError("action total differs between catalog and score curve")
    if int(curve.get("finalGeneratedTokens") or 0) != int(entry.get("tokens") or 0):
        raise ValueError("token total differs between catalog and score curve")
    games = entry.get("per_game") or []
    if len(games) != int(entry.get("games") or 0):
        raise ValueError("per-game score rows do not match catalog game count")
    game_ids = [game.get("id") for game in games]
    if len(game_ids) != len(set(game_ids)):
        raise ValueError("per-game score rows contain duplicate game ids")


def require_catalog_model(entry: dict[str, Any]) -> dict[str, Any]:
    """Require an exact, pinned model identity on every new publication."""

    try:
        return validate_model_metadata(entry.get("model"), require_revision=True)
    except ModelMetadataError as exc:
        raise ValueError(f"invalid model metadata: {exc}") from exc


def prepare_run_submission(
    run_dir: Path,
    index_path: Path,
    source: str,
) -> dict[str, Any]:
    run_name = run_dir.name
    overview_path = run_dir / "run-overview.json"
    timeline_path = run_dir / "run-timeline.json"
    if not overview_path.is_file() or not timeline_path.is_file():
        raise ValueError("run-overview.json and run-timeline.json are both required")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    entry = find_catalog_entry(index, run_name)
    entry["model"] = require_catalog_model(entry)
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    validate_catalog_consistency(run_name, entry, timeline)

    entry["has_execution_trace"] = True
    ignored = {"PUBLISH_RECEIPT.json", "run-submission.json"}
    artifacts = []
    for path in sorted(item for item in run_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(run_dir).as_posix()
        if relative in ignored:
            continue
        artifacts.append(
            {
                "path": relative,
                "kind": artifact_kind(relative),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )

    payload = {
        "schemaVersion": 1,
        "run": run_name,
        "source": source,
        # Publication retries must produce the same artifact manifest. The run's
        # own terminal timestamp is stable; wall-clock publication time belongs
        # in the server-generated receipt instead of this submitted artifact.
        "createdAt": timeline.get("endedAt") or timeline.get("startedAt"),
        "catalogSettings": {
            "schemaVersion": int(index.get("schemaVersion") or 1),
            "baseline": index.get("baseline") or {},
            "biases": index.get("biases") or {},
        },
        "catalogEntry": entry,
        "timeline": {
            "schemaVersion": int(timeline.get("schemaVersion") or 1),
            "startedAt": timeline.get("startedAt"),
            "endedAt": timeline.get("endedAt"),
            "durationSeconds": timeline.get("durationSeconds"),
        },
        "scoreCurve": timeline.get("scoreCurve") or {"points": []},
        "artifacts": artifacts,
    }
    (run_dir / "run-submission.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload
