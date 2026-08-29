"""Validated, atomic publication of ARC3 run artifacts and catalog rows."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tarfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Callable

try:
    from scripts.run_catalog import artifact_kind, validate_catalog_consistency
except ImportError:  # Docker copies run_catalog.py beside this module.
    from run_catalog import artifact_kind, validate_catalog_consistency


RUN_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MANIFEST_NAME = "MANIFEST.sha256"
IGNORED_ARTIFACTS = {"run-submission.json", "PUBLISH_RECEIPT.json"}


class PublicationProblem(Exception):
    """An expected publication failure that is safe to return to the client."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


@dataclass(frozen=True)
class PublicationPackage:
    run_id: str
    stage_root: Path
    run_dir: Path
    submission: dict[str, Any]
    manifest_sha256: str
    archive_sha256: str
    file_count: int
    byte_count: int
    archive_bytes: int


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_run_id(run_id: str) -> str:
    if not RUN_NAME_RE.fullmatch(run_id):
        raise PublicationProblem(400, "invalid_run", "invalid ARC3 run id")
    return run_id


def validate_sha256(value: str | None, field: str) -> str:
    normalized = (value or "").strip().lower()
    if not SHA256_RE.fullmatch(normalized):
        raise PublicationProblem(400, f"invalid_{field}", f"{field} must be SHA-256")
    return normalized


def receive_body(
    source: BinaryIO,
    destination: Path,
    content_length: int,
    expected_sha256: str,
    max_upload_bytes: int,
) -> str:
    if content_length <= 0:
        raise PublicationProblem(411, "length_required", "Content-Length is required")
    if content_length > max_upload_bytes:
        raise PublicationProblem(413, "upload_too_large", "publication archive is too large")
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    remaining = content_length
    with destination.open("xb") as output:
        while remaining:
            chunk = source.read(min(1024 * 1024, remaining))
            if not chunk:
                raise PublicationProblem(400, "truncated_upload", "publication archive was truncated")
            output.write(chunk)
            digest.update(chunk)
            remaining -= len(chunk)
    actual = digest.hexdigest()
    if actual != expected_sha256:
        destination.unlink(missing_ok=True)
        raise PublicationProblem(400, "archive_hash_mismatch", "archive SHA-256 does not match")
    return actual


def _safe_member_name(raw_name: str, run_id: str) -> str:
    if not raw_name or "\\" in raw_name:
        raise PublicationProblem(400, "unsafe_archive", "archive contains an unsafe path")
    path = PurePosixPath(raw_name)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise PublicationProblem(400, "unsafe_archive", "archive contains an unsafe path")
    normalized = path.as_posix()
    if normalized != MANIFEST_NAME and path.parts[0] != run_id:
        raise PublicationProblem(400, "unsafe_archive", "archive contains files outside the run")
    return normalized


def extract_archive(
    archive_path: Path,
    destination: Path,
    run_id: str,
    max_files: int,
    max_unpacked_bytes: int,
) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    seen: set[str] = set()
    unpacked_bytes = 0
    regular_files = 0
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            for member in archive:
                name = _safe_member_name(member.name, run_id)
                if name in seen:
                    raise PublicationProblem(400, "duplicate_archive_path", f"duplicate path: {name}")
                seen.add(name)
                if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                    raise PublicationProblem(400, "unsafe_archive", "links and special files are forbidden")
                target = destination.joinpath(*PurePosixPath(name).parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if not member.isfile():
                    raise PublicationProblem(400, "unsafe_archive", "unsupported archive member")
                regular_files += 1
                unpacked_bytes += member.size
                if regular_files > max_files or unpacked_bytes > max_unpacked_bytes:
                    raise PublicationProblem(413, "archive_too_large", "unpacked publication exceeds limits")
                target.parent.mkdir(parents=True, exist_ok=True)
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise PublicationProblem(400, "invalid_archive", f"cannot read {name}")
                with extracted, target.open("xb") as output:
                    shutil.copyfileobj(extracted, output, length=1024 * 1024)
                if target.stat().st_size != member.size:
                    raise PublicationProblem(400, "invalid_archive", f"size mismatch for {name}")
    except tarfile.TarError as exc:
        raise PublicationProblem(400, "invalid_archive", "invalid gzip tar archive") from exc


def _read_json(path: Path, label: str, max_bytes: int = 64 * 1024 * 1024) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size <= 0:
        raise PublicationProblem(400, "missing_artifact", f"missing {label}")
    if path.stat().st_size > max_bytes:
        raise PublicationProblem(413, "metadata_too_large", f"{label} is too large")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicationProblem(400, "invalid_json", f"invalid {label}") from exc
    if not isinstance(payload, dict):
        raise PublicationProblem(400, "invalid_json", f"{label} must be an object")
    return payload


def _parse_manifest(payload: bytes, run_id: str) -> dict[str, str]:
    try:
        lines = payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise PublicationProblem(400, "invalid_manifest", "manifest must be UTF-8") from exc
    entries: dict[str, str] = {}
    for line in lines:
        if not line:
            continue
        digest, separator, raw_path = line.partition("  ")
        if not separator or not SHA256_RE.fullmatch(digest):
            raise PublicationProblem(400, "invalid_manifest", "invalid manifest entry")
        name = _safe_member_name(raw_path, run_id)
        if name == MANIFEST_NAME or name in entries:
            raise PublicationProblem(400, "invalid_manifest", "duplicate or recursive manifest entry")
        entries[name] = digest
    if not entries:
        raise PublicationProblem(400, "invalid_manifest", "manifest is empty")
    return entries


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_submission(run_dir: Path, run_id: str) -> dict[str, Any]:
    submission = _read_json(run_dir / "run-submission.json", "run-submission.json")
    overview = _read_json(run_dir / "run-overview.json", "run-overview.json")
    timeline_on_disk = _read_json(run_dir / "run-timeline.json", "run-timeline.json")
    if submission.get("run") != run_id:
        raise PublicationProblem(400, "run_mismatch", "submission run id does not match URL")
    entry = submission.get("catalogEntry")
    curve = submission.get("scoreCurve")
    timeline = submission.get("timeline")
    settings = submission.get("catalogSettings")
    artifacts = submission.get("artifacts")
    if not all(isinstance(value, dict) for value in (entry, curve, timeline, settings)):
        raise PublicationProblem(400, "invalid_submission", "submission metadata is incomplete")
    if not isinstance(artifacts, list) or not isinstance(submission.get("source"), str):
        raise PublicationProblem(400, "invalid_submission", "submission artifacts or source is invalid")
    if entry.get("run") != run_id or not entry.get("has_execution_trace"):
        raise PublicationProblem(400, "invalid_submission", "catalog entry is not a complete trace")
    if timeline_on_disk.get("run") != run_id or timeline_on_disk.get("scoreCurve") != curve:
        raise PublicationProblem(400, "timeline_mismatch", "timeline differs from submitted score curve")
    try:
        validate_catalog_consistency(run_id, entry, timeline_on_disk)
    except (TypeError, ValueError) as exc:
        raise PublicationProblem(400, "catalog_mismatch", str(exc)) from exc
    if overview.get("run") not in (None, run_id):
        raise PublicationProblem(400, "overview_mismatch", "overview run id differs")

    declared: dict[str, tuple[str, int, str]] = {}
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise PublicationProblem(400, "invalid_submission", "invalid artifact record")
        raw_path = artifact.get("path")
        if not isinstance(raw_path, str) or "\\" in raw_path:
            raise PublicationProblem(400, "invalid_submission", "invalid artifact path")
        relative = PurePosixPath(raw_path)
        if relative.is_absolute() or any(part in ("", ".", "..") for part in relative.parts):
            raise PublicationProblem(400, "invalid_submission", "unsafe artifact path")
        normalized = relative.as_posix()
        if normalized in declared or normalized in IGNORED_ARTIFACTS:
            raise PublicationProblem(400, "invalid_submission", "duplicate artifact path")
        digest = validate_sha256(artifact.get("sha256"), "artifact_hash")
        try:
            byte_count = int(artifact.get("bytes"))
        except (TypeError, ValueError) as exc:
            raise PublicationProblem(400, "invalid_submission", "invalid artifact size") from exc
        if byte_count < 0:
            raise PublicationProblem(400, "invalid_submission", "invalid artifact size")
        declared[normalized] = (digest, byte_count, str(artifact.get("kind") or "viewer"))

    actual_paths = {
        path.relative_to(run_dir).as_posix(): path
        for path in run_dir.rglob("*")
        if path.is_file() and path.name not in IGNORED_ARTIFACTS
    }
    if set(declared) != set(actual_paths):
        missing = sorted(set(actual_paths) - set(declared))[:5]
        extra = sorted(set(declared) - set(actual_paths))[:5]
        raise PublicationProblem(
            400,
            "artifact_inventory_mismatch",
            f"artifact inventory mismatch; missing={missing}, extra={extra}",
        )
    for relative, path in actual_paths.items():
        digest, byte_count, kind = declared[relative]
        if path.stat().st_size != byte_count or _hash_file(path) != digest:
            raise PublicationProblem(400, "artifact_hash_mismatch", f"artifact differs: {relative}")
        if kind != artifact_kind(relative):
            raise PublicationProblem(400, "artifact_kind_mismatch", f"artifact kind differs: {relative}")
    return submission


def load_package(
    stage_root: Path,
    archive_path: Path,
    run_id: str,
    archive_sha256: str,
    expected_manifest_sha256: str,
    max_files: int,
    max_unpacked_bytes: int,
) -> PublicationPackage:
    unpack_root = stage_root / "unpacked"
    extract_archive(archive_path, unpack_root, run_id, max_files, max_unpacked_bytes)
    manifest_path = unpack_root / MANIFEST_NAME
    if not manifest_path.is_file() or manifest_path.stat().st_size > 32 * 1024 * 1024:
        raise PublicationProblem(400, "missing_manifest", "missing or oversized manifest")
    manifest_payload = manifest_path.read_bytes()
    manifest_sha256 = hashlib.sha256(manifest_payload).hexdigest()
    if manifest_sha256 != expected_manifest_sha256:
        raise PublicationProblem(400, "manifest_hash_mismatch", "manifest SHA-256 does not match")
    entries = _parse_manifest(manifest_payload, run_id)
    run_dir = unpack_root / run_id
    actual = {
        f"{run_id}/{path.relative_to(run_dir).as_posix()}": path
        for path in run_dir.rglob("*")
        if path.is_file() and path.name != "PUBLISH_RECEIPT.json"
    }
    if set(entries) != set(actual):
        raise PublicationProblem(400, "manifest_inventory_mismatch", "manifest does not cover every file")
    byte_count = 0
    for relative, path in actual.items():
        byte_count += path.stat().st_size
        if _hash_file(path) != entries[relative]:
            raise PublicationProblem(400, "manifest_file_mismatch", f"manifest differs: {relative}")
    submission = _validate_submission(run_dir, run_id)
    return PublicationPackage(
        run_id=run_id,
        stage_root=stage_root,
        run_dir=run_dir,
        submission=submission,
        manifest_sha256=manifest_sha256,
        archive_sha256=archive_sha256,
        file_count=len(entries),
        byte_count=byte_count,
        archive_bytes=archive_path.stat().st_size,
    )


def _insert_score_events(cursor: Any, run_id: str, curve: dict[str, Any], Json: Any) -> None:
    for series, key in (("time", "points"), ("tokens", "tokenPoints")):
        for sequence, point in enumerate(curve.get(key) or []):
            cursor.execute(
                """
                INSERT INTO arc3_score_events (
                    run_id, series, sequence, recorded_at, elapsed_seconds,
                    cumulative_actions, cumulative_generated_tokens, mean_score,
                    kind, game_id, action, level, game_score, timestamp_basis, payload
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    run_id,
                    series,
                    sequence,
                    point.get("at"),
                    point.get("elapsedSeconds") or 0,
                    point.get("cumulativeActions"),
                    point.get("cumulativeGeneratedTokens"),
                    point.get("meanScore") or 0,
                    point.get("kind") or "unknown",
                    point.get("gameId"),
                    point.get("action"),
                    point.get("level"),
                    point.get("gameScore"),
                    point.get("timestampBasis"),
                    Json(point),
                ),
            )


def _replace_catalog_rows(cursor: Any, package: PublicationPackage, Json: Any) -> None:
    submission = package.submission
    run_id = package.run_id
    entry = submission["catalogEntry"]
    timeline = submission["timeline"]
    curve = submission["scoreCurve"]
    settings = submission["catalogSettings"]
    cursor.execute(
        """
        UPDATE arc3_catalog_state
        SET schema_version = GREATEST(schema_version, %s),
            baseline = CASE WHEN baseline = '{}'::jsonb THEN %s ELSE baseline END,
            biases = CASE WHEN biases = '{}'::jsonb THEN %s ELSE biases END
        WHERE singleton = true
        """,
        (
            int(settings.get("schemaVersion") or 1),
            Json(settings.get("baseline") or {}),
            Json(settings.get("biases") or {}),
        ),
    )
    cursor.execute(
        """
        INSERT INTO arc3_runs (
            run_id, schema_version, status, avg_score, game_count, level_count,
            action_count, generated_tokens, duration_seconds, started_at, ended_at,
            catalog_entry, score_curve, artifact_manifest_sha256, source,
            published_at, updated_at
        ) VALUES (%s, %s, 'published', %s, %s, %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s, now(), now())
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
            updated_at = now()
        """,
        (
            run_id,
            int(timeline.get("schemaVersion") or 1),
            float(entry.get("avg_score") or 0),
            int(entry.get("games") or 0),
            int(entry.get("levels") or 0),
            int(entry.get("actions") or 0),
            int(entry.get("tokens") or 0),
            float(timeline.get("durationSeconds") or 0),
            timeline.get("startedAt"),
            timeline.get("endedAt"),
            Json(entry),
            Json(curve),
            package.manifest_sha256,
            submission["source"],
        ),
    )
    for table in ("arc3_game_scores", "arc3_score_events", "arc3_run_artifacts"):
        cursor.execute(f"DELETE FROM {table} WHERE run_id = %s", (run_id,))
    for game in entry.get("per_game") or []:
        cursor.execute(
            """
            INSERT INTO arc3_game_scores (
                run_id, game_id, score, levels_completed, levels_total, actions, payload
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                run_id,
                str(game.get("id") or "unknown"),
                float(game.get("score") or 0),
                int(game.get("levels") or 0),
                int(game.get("levels_total") or 0),
                int(game.get("actions") or 0),
                Json(game),
            ),
        )
    _insert_score_events(cursor, run_id, curve, Json)
    for artifact in submission.get("artifacts") or []:
        cursor.execute(
            """
            INSERT INTO arc3_run_artifacts (
                run_id, relative_path, artifact_kind, sha256, byte_count
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (
                run_id,
                artifact["path"],
                artifact["kind"],
                artifact["sha256"],
                int(artifact["bytes"]),
            ),
        )
    receipt_payload = {
        "apiVersion": 1,
        "run": run_id,
        "source": submission["source"],
        "artifactManifestSha256": package.manifest_sha256,
        "archiveSha256": package.archive_sha256,
        "archiveBytes": package.archive_bytes,
    }
    cursor.execute(
        """
        INSERT INTO arc3_publications (
            publication_id, run_id, source, artifact_manifest_sha256,
            file_count, byte_count, published_at, payload
        ) VALUES (%s, %s, %s, %s, %s, %s, now(), %s)
        ON CONFLICT (publication_id) DO NOTHING
        """,
        (
            f"{run_id}:{package.manifest_sha256}",
            run_id,
            submission["source"],
            package.manifest_sha256,
            package.file_count,
            package.byte_count,
            Json(receipt_payload),
        ),
    )
    cursor.execute("SELECT arc3_refresh_catalog_snapshot()")


def publication_decision(
    current_manifest: str | None,
    incoming_manifest: str,
    replace: bool,
    expected_previous_manifest: str | None,
    final_exists: bool,
) -> str:
    """Return the safe action or reject stale/blind replacement attempts."""

    if current_manifest == incoming_manifest:
        return "already_published" if final_exists else "repair_volume"
    if current_manifest is not None:
        if not replace:
            raise PublicationProblem(
                409,
                "run_exists",
                "run already exists with different artifacts; audited replacement is required",
            )
        if expected_previous_manifest != current_manifest:
            raise PublicationProblem(
                412,
                "stale_replacement",
                "run changed since replacement was prepared",
            )
        return "replace"
    if replace and expected_previous_manifest not in (None, "none"):
        raise PublicationProblem(412, "stale_replacement", "run no longer exists")
    if final_exists and not replace:
        raise PublicationProblem(409, "volume_conflict", "run directory already exists")
    return "replace" if final_exists else "publish"


def publish_package(
    connect: Callable[[], Any],
    data_root: Path,
    package: PublicationPackage,
    replace: bool,
    expected_previous_manifest: str | None,
) -> dict[str, Any]:
    """Install files and catalog rows with rollback and optimistic replacement."""

    from psycopg2.extras import Json

    data_root.mkdir(parents=True, exist_ok=True)
    final = data_root / package.run_id
    rollback_root = data_root / ".rollback"
    failed_root = data_root / ".failed"
    nonce = uuid.uuid4().hex[:12]
    backup = rollback_root / f"{package.run_id}.{nonce}"
    failed = failed_root / f"{package.run_id}.{nonce}"
    connection = connect()
    moved_new = False
    moved_old = False
    try:
        connection.autocommit = False
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended('arc3-catalog', 0))")
            cursor.execute(
                "SELECT artifact_manifest_sha256 FROM arc3_runs WHERE run_id = %s FOR UPDATE",
                (package.run_id,),
            )
            row = cursor.fetchone()
            current_manifest = row[0] if row else None
            decision = publication_decision(
                current_manifest,
                package.manifest_sha256,
                replace,
                expected_previous_manifest,
                final.exists(),
            )
            if decision == "already_published":
                connection.rollback()
                return {
                    "status": "already_published",
                    "run": package.run_id,
                    "artifactManifestSha256": package.manifest_sha256,
                }
            if decision == "repair_volume":
                final.parent.mkdir(parents=True, exist_ok=True)
                os.replace(package.run_dir, final)
                moved_new = True
                connection.rollback()
                return {
                    "status": "repaired_volume_copy",
                    "run": package.run_id,
                    "artifactManifestSha256": package.manifest_sha256,
                }
            receipt = {
                "apiVersion": 1,
                "run": package.run_id,
                "source": package.submission["source"],
                "publishedAt": utc_now(),
                "artifactManifestSha256": package.manifest_sha256,
                "archiveSha256": package.archive_sha256,
                "catalogBackend": "railway-postgres",
            }
            (package.run_dir / "PUBLISH_RECEIPT.json").write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            if final.exists():
                rollback_root.mkdir(parents=True, exist_ok=True)
                os.replace(final, backup)
                moved_old = True
            os.replace(package.run_dir, final)
            moved_new = True
            _replace_catalog_rows(cursor, package, Json)
        connection.commit()
    except Exception:
        connection.rollback()
        if moved_new and final.exists():
            failed_root.mkdir(parents=True, exist_ok=True)
            os.replace(final, failed)
        if moved_old and backup.exists():
            os.replace(backup, final)
        raise
    finally:
        connection.close()
    return {
        "status": "replaced" if moved_old else "published",
        "run": package.run_id,
        "artifactManifestSha256": package.manifest_sha256,
        "archiveSha256": package.archive_sha256,
        "files": package.file_count,
        "bytes": package.byte_count,
    }
