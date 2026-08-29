#!/usr/bin/env python3
"""Publish one complete ARC3 run through the Railway publication API.

This command never changes Git and never starts a Railway deployment. It builds
one verified gzip archive locally, then sends it to the versioned API. The API
atomically installs the trace files and updates every catalog/score table.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit

try:
    from .run_catalog import prepare_run_submission
except ImportError:  # Direct script execution adds scripts/ to sys.path.
    from run_catalog import prepare_run_submission


RUN_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
DEFAULT_API_URL = "https://arc3.sonpham.net"


class ApiError(RuntimeError):
    def __init__(self, status: int, payload: dict | str):
        message = (
            payload.get("message") or payload.get("error")
            if isinstance(payload, dict)
            else payload
        )
        super().__init__(f"publication API returned HTTP {status}: {message}")
        self.status = status
        self.payload = payload


def validate_run_name(value: str) -> str:
    if not RUN_NAME_RE.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "run name must contain only letters, digits, dot, underscore, or dash"
        )
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_files(run_dir: Path) -> list[Path]:
    files = sorted(
        path
        for path in run_dir.rglob("*")
        if path.is_file() and path.name != "PUBLISH_RECEIPT.json"
    )
    if not files:
        raise ValueError(f"viewer export is empty: {run_dir}")
    for path in files:
        if path.is_symlink():
            raise ValueError(f"viewer exports may not contain symlinks: {path}")
    return files


def build_manifest(
    run_dir: Path,
    run_name: str,
    extra_files: dict[str, bytes] | None = None,
) -> tuple[str, int]:
    """Build the complete, stable file manifest.

    extra_files is retained for callers of the old helper, but API publications
    use only the run directory and never upload generated SQL.
    """

    lines: list[str] = []
    total_bytes = 0
    for path in run_files(run_dir):
        relative = path.relative_to(run_dir).as_posix()
        lines.append(f"{sha256_file(path)}  {run_name}/{relative}")
        total_bytes += path.stat().st_size
    for relative, payload in sorted((extra_files or {}).items()):
        lines.append(f"{hashlib.sha256(payload).hexdigest()}  {relative}")
        total_bytes += len(payload)
    return "\n".join(lines) + "\n", total_bytes


def add_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name=name)
    info.size = len(payload)
    info.mode = 0o644
    info.mtime = int(time.time())
    archive.addfile(info, io.BytesIO(payload))


def build_archive(run_dir: Path, run_name: str, manifest: str, destination: Path) -> None:
    with tarfile.open(destination, mode="w:gz", compresslevel=6) as archive:
        archive.add(run_dir, arcname=run_name, recursive=True)
        add_bytes(archive, "MANIFEST.sha256", manifest.encode("utf-8"))


def railway_variables(args: argparse.Namespace) -> dict[str, str]:
    completed = subprocess.run(
        [
            args.railway_bin,
            "variable",
            "list",
            "--service",
            args.service,
            "--environment",
            args.environment,
            "--json",
        ],
        cwd=args.railway_cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("Railway variable response was not an object")
    return {str(key): str(value) for key, value in payload.items()}


def resolve_publish_token(args: argparse.Namespace) -> str:
    token = os.environ.get("ARC3_PUBLISH_TOKEN")
    if token:
        return token
    try:
        token = railway_variables(args).get("ARC3_PUBLISH_TOKEN")
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "ARC3_PUBLISH_TOKEN is unset and could not be read from the linked Railway service"
        ) from exc
    if not token:
        raise RuntimeError(
            "ARC3_PUBLISH_TOKEN is not configured; set it on arc3-viewer before publishing"
        )
    return token


def api_connection(api_url: str, timeout: int) -> tuple[http.client.HTTPConnection, str]:
    parsed = urlsplit(api_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("--api-url must be an absolute HTTP(S) URL")
    port = parsed.port
    if parsed.scheme == "https":
        connection: http.client.HTTPConnection = http.client.HTTPSConnection(
            parsed.hostname, port or 443, timeout=timeout
        )
    else:
        connection = http.client.HTTPConnection(parsed.hostname, port or 80, timeout=timeout)
    prefix = parsed.path.rstrip("/")
    return connection, prefix


def decode_response(response: http.client.HTTPResponse) -> dict | str:
    body = response.read(2 * 1024 * 1024)
    try:
        return json.loads(body.decode("utf-8")) if body else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return body.decode("utf-8", errors="replace")


def fetch_current_manifest(args: argparse.Namespace, run_name: str, token: str) -> str:
    connection, prefix = api_connection(args.api_url, args.timeout)
    path = f"{prefix}/api/v1/runs/{quote(run_name, safe='')}/publication"
    try:
        connection.request("GET", path, headers={"Authorization": f"Bearer {token}"})
        response = connection.getresponse()
        payload = decode_response(response)
    finally:
        connection.close()
    if response.status == 404:
        return "none"
    if response.status != 200 or not isinstance(payload, dict):
        raise ApiError(response.status, payload)
    value = str(payload.get("artifactManifestSha256") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", value):
        raise RuntimeError("publication API returned an invalid current manifest")
    return value


def upload_once(
    args: argparse.Namespace,
    archive_path: Path,
    run_name: str,
    token: str,
    archive_sha256: str,
    manifest_sha256: str,
    expected_previous: str | None,
) -> dict:
    connection, prefix = api_connection(args.api_url, args.timeout)
    query = urlencode({"replace": "1"}) if args.replace else ""
    path = f"{prefix}/api/v1/runs/{quote(run_name, safe='')}/publication"
    if query:
        path += f"?{query}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/gzip",
        "Content-Length": str(archive_path.stat().st_size),
        "X-ARC3-Archive-SHA256": archive_sha256,
        "X-ARC3-Manifest-SHA256": manifest_sha256,
        "User-Agent": "arc3-publisher/1",
    }
    if expected_previous is not None:
        headers["X-ARC3-Expected-Manifest-SHA256"] = expected_previous
    try:
        with archive_path.open("rb") as body:
            connection.request("PUT", path, body=body, headers=headers)
            response = connection.getresponse()
            payload = decode_response(response)
    finally:
        connection.close()
    if response.status not in (200, 201) or not isinstance(payload, dict):
        raise ApiError(response.status, payload)
    return payload


def upload_with_retries(
    args: argparse.Namespace,
    archive_path: Path,
    run_name: str,
    token: str,
    archive_sha256: str,
    manifest_sha256: str,
    expected_previous: str | None,
) -> dict:
    retryable_statuses = {502, 503, 504}
    for attempt in range(1, args.attempts + 1):
        try:
            return upload_once(
                args,
                archive_path,
                run_name,
                token,
                archive_sha256,
                manifest_sha256,
                expected_previous,
            )
        except ApiError as exc:
            if exc.status not in retryable_statuses or attempt == args.attempts:
                raise
        except (OSError, http.client.HTTPException):
            if attempt == args.attempts:
                raise
        time.sleep(min(2 ** (attempt - 1), 8))
    raise AssertionError("unreachable")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_name", type=validate_run_name)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--railway-cwd", type=Path)
    parser.add_argument("--railway-bin", default=os.environ.get("RAILWAY_BIN", "railway"))
    parser.add_argument("--service", default="arc3-viewer")
    parser.add_argument("--environment", default="production")
    parser.add_argument("--source", default="local-export")
    parser.add_argument("--api-url", default=os.environ.get("ARC3_API_URL", DEFAULT_API_URL))
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--expected-manifest")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--validate-upload-only",
        action="store_true",
        help="build and validate the API archive without sending it",
    )
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args(argv)
    args.repo_root = args.repo_root.resolve()
    args.railway_cwd = (args.railway_cwd or args.repo_root).resolve()
    if args.expected_manifest and not args.replace:
        parser.error("--expected-manifest requires --replace")
    if args.expected_manifest and args.expected_manifest != "none" and not re.fullmatch(
        r"[0-9a-f]{64}", args.expected_manifest
    ):
        parser.error("--expected-manifest must be a SHA-256 or 'none'")
    if args.attempts < 1:
        parser.error("--attempts must be at least 1")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = args.repo_root / "docs" / "data" / args.run_name
    index_path = args.repo_root / "docs" / "data" / "runs-index.json"
    if not index_path.is_file():
        raise SystemExit(f"missing local catalog export: {index_path}")

    prepare_run_submission(run_dir, index_path, args.source)
    manifest, artifact_bytes = build_manifest(run_dir, args.run_name)
    manifest_sha256 = hashlib.sha256(manifest.encode("utf-8")).hexdigest()
    with tempfile.TemporaryDirectory(prefix="arc3-publication-") as temp:
        archive_path = Path(temp) / f"{args.run_name}.tgz"
        build_archive(run_dir, args.run_name, manifest, archive_path)
        archive_sha256 = sha256_file(archive_path)
        summary = {
            "run": args.run_name,
            "files": len(manifest.splitlines()),
            "artifactBytes": artifact_bytes,
            "archiveBytes": archive_path.stat().st_size,
            "archiveSha256": archive_sha256,
            "artifactManifestSha256": manifest_sha256,
            "source": args.source,
            "catalogBackend": "railway-postgres",
            "transport": "publication-api-v1",
            "deploymentRequired": False,
        }
        print(json.dumps(summary, sort_keys=True))
        if args.dry_run or args.validate_upload_only:
            return 0

        token = resolve_publish_token(args)
        expected_previous = args.expected_manifest
        if args.replace and expected_previous is None:
            expected_previous = fetch_current_manifest(args, args.run_name, token)
        result = upload_with_retries(
            args,
            archive_path,
            args.run_name,
            token,
            archive_sha256,
            manifest_sha256,
            expected_previous,
        )
        print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ApiError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
