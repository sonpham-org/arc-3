#!/usr/bin/env python3
"""HTTP API for Railway-backed ARC3 run publication and catalog reads."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import psycopg2
from psycopg2.extras import Json

from publication_store import (
    PublicationProblem,
    load_package,
    publish_package,
    receive_body,
    validate_run_id,
    validate_sha256,
)


RUN_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")


def connect():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    return psycopg2.connect(database_url, connect_timeout=8)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_kind(path: Path) -> str:
    if path.name == "run-overview.json":
        return "overview"
    if path.name == "run-timeline.json":
        return "timeline"
    if path.name == "run-submission.json":
        return "submission"
    return "viewer"


def insert_score_events(cursor, run_id: str, curve: dict) -> None:
    for series, key in (("time", "points"), ("tokens", "tokenPoints")):
        for sequence, point in enumerate(curve.get(key) or []):
            cursor.execute(
                """
                INSERT INTO arc3_score_events (
                    run_id, series, sequence, recorded_at, elapsed_seconds,
                    cumulative_actions, cumulative_generated_tokens, mean_score,
                    kind, game_id, action, level, game_score, timestamp_basis, payload
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (run_id, series, sequence) DO UPDATE SET
                    recorded_at = EXCLUDED.recorded_at,
                    elapsed_seconds = EXCLUDED.elapsed_seconds,
                    cumulative_actions = EXCLUDED.cumulative_actions,
                    cumulative_generated_tokens = EXCLUDED.cumulative_generated_tokens,
                    mean_score = EXCLUDED.mean_score,
                    kind = EXCLUDED.kind,
                    game_id = EXCLUDED.game_id,
                    action = EXCLUDED.action,
                    level = EXCLUDED.level,
                    game_score = EXCLUDED.game_score,
                    timestamp_basis = EXCLUDED.timestamp_basis,
                    payload = EXCLUDED.payload
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


def bootstrap_legacy_catalog(cursor, data_root: Path, index: dict) -> int:
    cursor.execute("SELECT count(*) FROM arc3_runs")
    if cursor.fetchone()[0]:
        return 0

    inserted = 0
    for entry in index.get("runs") or []:
        run_id = entry.get("run")
        if not isinstance(run_id, str) or not RUN_NAME_RE.fullmatch(run_id):
            continue
        run_dir = data_root / run_id
        timeline_path = run_dir / "run-timeline.json"
        timeline = {}
        if timeline_path.is_file():
            try:
                timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                timeline = {}
        curve = timeline.get("scoreCurve") or {"points": []}
        cursor.execute(
            """
            INSERT INTO arc3_runs (
                run_id, schema_version, status, avg_score, game_count,
                level_count, action_count, generated_tokens, duration_seconds,
                started_at, ended_at, catalog_entry, score_curve,
                artifact_manifest_sha256, source, published_at, updated_at
            ) VALUES (
                %s, %s, 'published', %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, NULL, 'legacy-volume-bootstrap', now(), now()
            )
            ON CONFLICT (run_id) DO NOTHING
            """,
            (
                run_id,
                timeline.get("schemaVersion") or 1,
                entry.get("avg_score") or 0,
                entry.get("games") or 0,
                entry.get("levels") or 0,
                entry.get("actions") or 0,
                entry.get("tokens") or 0,
                timeline.get("durationSeconds"),
                timeline.get("startedAt"),
                timeline.get("endedAt"),
                Json(entry),
                Json(curve),
            ),
        )
        for game in entry.get("per_game") or []:
            cursor.execute(
                """
                INSERT INTO arc3_game_scores (
                    run_id, game_id, score, levels_completed,
                    levels_total, actions, payload
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id, game_id) DO NOTHING
                """,
                (
                    run_id,
                    game.get("id") or "unknown",
                    game.get("score") or 0,
                    game.get("levels") or 0,
                    game.get("levels_total") or 0,
                    game.get("actions") or 0,
                    Json(game),
                ),
            )
        insert_score_events(cursor, run_id, curve)

        artifact_count = 0
        artifact_bytes = 0
        for path in (run_dir / "run-overview.json", timeline_path):
            if not path.is_file():
                continue
            artifact_count += 1
            artifact_bytes += path.stat().st_size
            cursor.execute(
                """
                INSERT INTO arc3_run_artifacts (
                    run_id, relative_path, artifact_kind, sha256, byte_count
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (run_id, relative_path) DO NOTHING
                """,
                (
                    run_id,
                    path.name,
                    artifact_kind(path),
                    sha256_file(path),
                    path.stat().st_size,
                ),
            )
        if artifact_count:
            receipt_hash = hashlib.sha256(
                f"legacy-volume-bootstrap:{run_id}".encode()
            ).hexdigest()
            cursor.execute(
                """
                INSERT INTO arc3_publications (
                    publication_id, run_id, source, artifact_manifest_sha256,
                    file_count, byte_count, payload
                ) VALUES (%s, %s, 'legacy-volume-bootstrap', %s, %s, %s, %s)
                ON CONFLICT (publication_id) DO NOTHING
                """,
                (
                    f"legacy-{receipt_hash[:24]}",
                    run_id,
                    receipt_hash,
                    artifact_count,
                    artifact_bytes,
                    Json({"bootstrap": True}),
                ),
            )
        inserted += 1
    return inserted


def migrate_and_bootstrap(schema_path: Path, data_root: Path) -> int:
    schema = schema_path.read_text(encoding="utf-8")
    index_path = data_root / "runs-index.json"
    legacy_index = {"runs": []}
    if index_path.is_file():
        legacy_index = json.loads(index_path.read_text(encoding="utf-8"))

    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(schema)
            cursor.execute(
                """
                UPDATE arc3_catalog_state
                SET baseline = CASE WHEN baseline = '{}'::jsonb THEN %s ELSE baseline END,
                    biases = CASE WHEN biases = '{}'::jsonb THEN %s ELSE biases END
                WHERE singleton = true
                """,
                (Json(legacy_index.get("baseline") or {}), Json(legacy_index.get("biases") or {})),
            )
            inserted = bootstrap_legacy_catalog(cursor, data_root, legacy_index)
            cursor.execute("SELECT arc3_refresh_catalog_snapshot()")
    return inserted


class CatalogHandler(BaseHTTPRequestHandler):
    server_version = "ARC3Catalog/2"
    data_root = Path("/srv/data")
    publish_token = ""
    max_upload_bytes = 4 * 1024 * 1024 * 1024
    max_unpacked_bytes = 12 * 1024 * 1024 * 1024
    max_files = 200_000

    def send_json(self, status: HTTPStatus | int, payload: str | dict) -> None:
        if not isinstance(payload, str):
            payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        body = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()
        self.wfile.write(body)

    def require_publish_auth(self) -> None:
        if not self.publish_token:
            raise PublicationProblem(503, "publisher_disabled", "publication API is not configured")
        authorization = self.headers.get("Authorization", "")
        prefix = "Bearer "
        supplied_token = authorization[len(prefix) :] if authorization.startswith(prefix) else ""
        if not supplied_token or not secrets.compare_digest(supplied_token, self.publish_token):
            raise PublicationProblem(401, "unauthorized", "invalid publication token")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/api/healthz":
                with connect() as connection, connection.cursor() as cursor:
                    cursor.execute("SELECT count(*) FROM arc3_runs WHERE status = 'published'")
                    count = cursor.fetchone()[0]
                self.send_json(
                    HTTPStatus.OK,
                    {"ok": True, "apiVersion": 1, "publishedRuns": count},
                )
                return
            if path in ("/data/runs-index.json", "/api/v1/catalog"):
                with connect() as connection, connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT catalog_json::text FROM arc3_catalog_state WHERE singleton = true"
                    )
                    row = cursor.fetchone()
                if not row:
                    self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, '{"error":"catalog unavailable"}')
                    return
                self.send_json(HTTPStatus.OK, row[0])
                return
            match = re.fullmatch(r"/api/v1/runs/([^/]+)/publication", path)
            if match:
                self.require_publish_auth()
                run_id = validate_run_id(unquote(match.group(1)))
                with connect() as connection, connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT artifact_manifest_sha256, source, published_at
                        FROM arc3_runs
                        WHERE run_id = %s AND status = 'published'
                        """,
                        (run_id,),
                    )
                    row = cursor.fetchone()
                if not row:
                    self.send_json(HTTPStatus.NOT_FOUND, {"error": "run_not_found"})
                    return
                self.send_json(
                    HTTPStatus.OK,
                    {
                        "apiVersion": 1,
                        "run": run_id,
                        "artifactManifestSha256": row[0],
                        "source": row[1],
                        "publishedAt": row[2].isoformat() if row[2] else None,
                    },
                )
                return
            match = re.fullmatch(r"/api/v1/runs/([^/]+)", path)
            if match:
                run_id = unquote(match.group(1))
                validate_run_id(run_id)
                with connect() as connection, connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT jsonb_build_object(
                            'apiVersion', 1,
                            'run', run_id,
                            'status', status,
                            'artifactManifestSha256', artifact_manifest_sha256,
                            'source', source,
                            'publishedAt', published_at,
                            'updatedAt', updated_at,
                            'artifactBaseUrl', '/data/' || run_id || '/'
                        )::text
                        FROM arc3_runs
                        WHERE run_id = %s AND status = 'published'
                        """,
                        (run_id,),
                    )
                    row = cursor.fetchone()
                if not row:
                    self.send_json(HTTPStatus.NOT_FOUND, {"error": "run_not_found"})
                    return
                self.send_json(HTTPStatus.OK, row[0])
                return
            match = re.fullmatch(
                r"/(?:api/runs/([^/]+)/score-curve\.json|api/v1/runs/([^/]+)/score-curve)",
                path,
            )
            if match:
                run_id = unquote(match.group(1) or match.group(2))
                validate_run_id(run_id)
                with connect() as connection, connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT jsonb_build_object(
                            'run', run_id,
                            'durationSeconds', duration_seconds,
                            'scoreCurve', score_curve
                        )::text
                        FROM arc3_runs
                        WHERE run_id = %s AND status = 'published'
                        """,
                        (run_id,),
                    )
                    row = cursor.fetchone()
                if not row:
                    self.send_json(HTTPStatus.NOT_FOUND, '{"error":"run not found"}')
                    return
                self.send_json(HTTPStatus.OK, row[0])
                return
            self.send_json(HTTPStatus.NOT_FOUND, '{"error":"not found"}')
        except PublicationProblem as exc:
            self.send_json(exc.status, {"error": exc.code, "message": exc.message})
        except Exception as exc:  # Keep the public failure small; full detail goes to Railway logs.
            print(f"catalog request failed for {path}: {exc}", flush=True)
            self.send_json(HTTPStatus.SERVICE_UNAVAILABLE, '{"error":"catalog unavailable"}')

    def do_PUT(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        match = re.fullmatch(r"/api/v1/runs/([^/]+)/publication", parsed.path)
        if not match:
            self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        request_id = uuid.uuid4().hex
        stage_root: Path | None = None
        try:
            self.require_publish_auth()
            run_id = validate_run_id(unquote(match.group(1)))
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip() not in (
                "application/gzip",
                "application/x-gzip",
            ):
                raise PublicationProblem(415, "unsupported_media_type", "expected application/gzip")
            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise PublicationProblem(400, "invalid_content_length", "invalid Content-Length") from exc
            archive_sha256 = validate_sha256(
                self.headers.get("X-ARC3-Archive-SHA256"), "archive_hash"
            )
            manifest_sha256 = validate_sha256(
                self.headers.get("X-ARC3-Manifest-SHA256"), "manifest_hash"
            )
            query = parse_qs(parsed.query)
            replace = query.get("replace") == ["1"]
            expected_previous = self.headers.get("X-ARC3-Expected-Manifest-SHA256")
            if replace and expected_previous is None:
                raise PublicationProblem(
                    428,
                    "precondition_required",
                    "replacement requires the currently published manifest SHA-256",
                )
            if expected_previous not in (None, "none"):
                expected_previous = validate_sha256(expected_previous, "expected_manifest_hash")

            stage_root = self.data_root / ".incoming" / f"{run_id}.{request_id}"
            stage_root.mkdir(parents=True, exist_ok=False)
            archive_path = stage_root / "publication.tgz"
            receive_body(
                self.rfile,
                archive_path,
                content_length,
                archive_sha256,
                self.max_upload_bytes,
            )
            package = load_package(
                stage_root,
                archive_path,
                run_id,
                archive_sha256,
                manifest_sha256,
                self.max_files,
                self.max_unpacked_bytes,
            )
            result = publish_package(
                connect,
                self.data_root,
                package,
                replace,
                expected_previous,
            )
            result["apiVersion"] = 1
            result["requestId"] = request_id
            status = HTTPStatus.CREATED if result["status"] in ("published", "replaced") else HTTPStatus.OK
            self.send_json(status, result)
            print(
                f"publication {result['status']} run={run_id} "
                f"manifest={manifest_sha256} request={request_id}",
                flush=True,
            )
        except PublicationProblem as exc:
            self.send_json(
                exc.status,
                {"error": exc.code, "message": exc.message, "requestId": request_id},
            )
        except Exception as exc:
            print(f"publication failed request={request_id}: {exc}", flush=True)
            self.send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "publication_failed", "requestId": request_id},
            )
        finally:
            if stage_root is not None:
                shutil.rmtree(stage_root, ignore_errors=True)

    def log_message(self, format_string: str, *args) -> None:
        print(f"catalog: {format_string % args}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8082)
    parser.add_argument("--schema", type=Path, default=Path("/catalog_schema.sql"))
    parser.add_argument("--bootstrap-root", type=Path, default=Path("/srv/data"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    inserted = migrate_and_bootstrap(args.schema, args.bootstrap_root)
    CatalogHandler.data_root = args.bootstrap_root
    CatalogHandler.publish_token = os.environ.get("ARC3_PUBLISH_TOKEN", "")
    CatalogHandler.max_upload_bytes = int(
        os.environ.get("ARC3_MAX_UPLOAD_BYTES", str(4 * 1024 * 1024 * 1024))
    )
    CatalogHandler.max_unpacked_bytes = int(
        os.environ.get("ARC3_MAX_UNPACKED_BYTES", str(12 * 1024 * 1024 * 1024))
    )
    CatalogHandler.max_files = int(os.environ.get("ARC3_MAX_PUBLICATION_FILES", "200000"))
    print(
        f"catalog database ready; api=v1 legacy runs inserted={inserted} "
        f"publisher={'enabled' if CatalogHandler.publish_token else 'disabled'}",
        flush=True,
    )
    server = ThreadingHTTPServer((args.host, args.port), CatalogHandler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
