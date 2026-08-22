"""Build and validate one database-backed ARC3 run submission."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
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


def sql_json(value: Any) -> str:
    body = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    tag = f"arc3_{hashlib.sha256(body.encode()).hexdigest()[:12]}"
    marker = f"${tag}$"
    if marker in body:
        raise ValueError("unexpected SQL dollar-quote collision")
    return f"{marker}{body}{marker}::jsonb"


def sql_text(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + value.replace("'", "''") + "'"


def sql_timestamp(value: str | None) -> str:
    return "NULL" if not value else f"{sql_text(value)}::timestamptz"


def build_catalog_sql(
    schema_sql: str,
    submission: dict[str, Any],
    artifact_manifest_sha256: str,
    file_count: int,
    byte_count: int,
) -> bytes:
    if len(artifact_manifest_sha256) != 64:
        raise ValueError("artifact manifest SHA256 must be 64 hexadecimal characters")
    run_name = submission["run"]
    source = submission["source"]
    entry = submission["catalogEntry"]
    timeline = submission["timeline"]
    curve = submission["scoreCurve"]
    settings = submission["catalogSettings"]
    publication_id = f"{run_name}:{artifact_manifest_sha256[:24]}"
    statements = [schema_sql.rstrip(), "BEGIN;", "SELECT pg_advisory_xact_lock(hashtextextended('arc3-catalog', 0));"]
    statements.append(
        """
UPDATE arc3_catalog_state
SET schema_version = CASE WHEN schema_version = 1 THEN {schema_version} ELSE schema_version END,
    baseline = CASE WHEN baseline = '{{}}'::jsonb THEN {baseline} ELSE baseline END,
    biases = CASE WHEN biases = '{{}}'::jsonb THEN {biases} ELSE biases END
WHERE singleton = true;
        """.format(
            schema_version=int(settings.get("schemaVersion") or 1),
            baseline=sql_json(settings.get("baseline") or {}),
            biases=sql_json(settings.get("biases") or {}),
        ).strip()
    )
    statements.append(
        f"""
INSERT INTO arc3_runs (
    run_id, schema_version, status, avg_score, game_count, level_count,
    action_count, generated_tokens, duration_seconds, started_at, ended_at,
    catalog_entry, score_curve, artifact_manifest_sha256, source,
    published_at, updated_at
) VALUES (
    {sql_text(run_name)}, {int(timeline.get('schemaVersion') or 1)}, 'published',
    {float(entry.get('avg_score') or 0)}, {int(entry.get('games') or 0)},
    {int(entry.get('levels') or 0)}, {int(entry.get('actions') or 0)},
    {int(entry.get('tokens') or 0)}, {float(timeline.get('durationSeconds') or 0)},
    {sql_timestamp(timeline.get('startedAt'))}, {sql_timestamp(timeline.get('endedAt'))},
    {sql_json(entry)}, {sql_json(curve)}, {sql_text(artifact_manifest_sha256)},
    {sql_text(source)}, now(), now()
)
ON CONFLICT (run_id) DO UPDATE SET
    schema_version = EXCLUDED.schema_version,
    status = 'published',
    avg_score = EXCLUDED.avg_score,
    game_count = EXCLUDED.game_count,
    level_count = EXCLUDED.level_count,
    action_count = EXCLUDED.action_count,
    generated_tokens = EXCLUDED.generated_tokens,
    duration_seconds = EXCLUDED.duration_seconds,
    started_at = EXCLUDED.started_at,
    ended_at = EXCLUDED.ended_at,
    catalog_entry = EXCLUDED.catalog_entry,
    score_curve = EXCLUDED.score_curve,
    artifact_manifest_sha256 = EXCLUDED.artifact_manifest_sha256,
    source = EXCLUDED.source,
    published_at = now(),
    updated_at = now();
        """.strip()
    )
    statements.extend(
        [
            f"DELETE FROM arc3_game_scores WHERE run_id = {sql_text(run_name)};",
            f"DELETE FROM arc3_score_events WHERE run_id = {sql_text(run_name)};",
            f"DELETE FROM arc3_run_artifacts WHERE run_id = {sql_text(run_name)};",
        ]
    )
    for game in entry.get("per_game") or []:
        statements.append(
            f"""
INSERT INTO arc3_game_scores (
    run_id, game_id, score, levels_completed, levels_total, actions, payload
) VALUES (
    {sql_text(run_name)}, {sql_text(str(game.get('id') or 'unknown'))},
    {float(game.get('score') or 0)}, {int(game.get('levels') or 0)},
    {int(game.get('levels_total') or 0)}, {int(game.get('actions') or 0)},
    {sql_json(game)}
);
            """.strip()
        )
    for series, key in (("time", "points"), ("tokens", "tokenPoints")):
        for sequence, point in enumerate(curve.get(key) or []):
            statements.append(
                f"""
INSERT INTO arc3_score_events (
    run_id, series, sequence, recorded_at, elapsed_seconds,
    cumulative_actions, cumulative_generated_tokens, mean_score, kind,
    game_id, action, level, game_score, timestamp_basis, payload
) VALUES (
    {sql_text(run_name)}, {sql_text(series)}, {sequence},
    {sql_timestamp(point.get('at'))}, {float(point.get('elapsedSeconds') or 0)},
    {int(point['cumulativeActions']) if point.get('cumulativeActions') is not None else 'NULL'},
    {int(point['cumulativeGeneratedTokens']) if point.get('cumulativeGeneratedTokens') is not None else 'NULL'},
    {float(point.get('meanScore') or 0)}, {sql_text(str(point.get('kind') or 'unknown'))},
    {sql_text(point.get('gameId'))},
    {int(point['action']) if point.get('action') is not None else 'NULL'},
    {int(point['level']) if point.get('level') is not None else 'NULL'},
    {float(point['gameScore']) if point.get('gameScore') is not None else 'NULL'},
    {sql_text(point.get('timestampBasis'))}, {sql_json(point)}
);
                """.strip()
            )
    for artifact in submission.get("artifacts") or []:
        statements.append(
            f"""
INSERT INTO arc3_run_artifacts (
    run_id, relative_path, artifact_kind, sha256, byte_count
) VALUES (
    {sql_text(run_name)}, {sql_text(artifact['path'])}, {sql_text(artifact['kind'])},
    {sql_text(artifact['sha256'])}, {int(artifact['bytes'])}
);
            """.strip()
        )
    receipt_payload = {
        "run": run_name,
        "source": source,
        "artifactManifestSha256": artifact_manifest_sha256,
        "catalogSchemaVersion": 1,
    }
    statements.append(
        f"""
INSERT INTO arc3_publications (
    publication_id, run_id, source, artifact_manifest_sha256,
    file_count, byte_count, published_at, payload
) VALUES (
    {sql_text(publication_id)}, {sql_text(run_name)}, {sql_text(source)},
    {sql_text(artifact_manifest_sha256)}, {int(file_count)}, {int(byte_count)},
    now(), {sql_json(receipt_payload)}
)
ON CONFLICT (publication_id) DO NOTHING;
        """.strip()
    )
    statements.extend(
        [
            "SELECT arc3_refresh_catalog_snapshot();",
            "COMMIT;",
            f"SELECT 'CATALOG_COMMITTED={run_name}';",
        ]
    )
    return ("\n\n".join(statements) + "\n").encode("utf-8")
