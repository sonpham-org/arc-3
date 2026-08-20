#!/usr/bin/env python3
"""Publish one generated ARC3 viewer run directly to Railway's data volume.

Git is deliberately not involved. The uploader streams a tar archive over
``railway ssh`` into a unique staging directory, verifies every file, installs
the run directory, and atomically replaces ``runs-index.json``.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import secrets
import subprocess
import sys
import tarfile
import time
from pathlib import Path


RUN_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
DEFAULT_DATA_ROOT = "/srv/data"


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
    files = sorted(path for path in run_dir.rglob("*") if path.is_file())
    if not files:
        raise ValueError(f"viewer export is empty: {run_dir}")
    for path in files:
        if path.is_symlink():
            raise ValueError(f"viewer exports may not contain symlinks: {path}")
    return files


def build_manifest(run_dir: Path, run_name: str, index_path: Path) -> tuple[str, int]:
    lines: list[str] = []
    total_bytes = 0
    for path in run_files(run_dir):
        relative = path.relative_to(run_dir).as_posix()
        lines.append(f"{sha256_file(path)}  {run_name}/{relative}")
        total_bytes += path.stat().st_size
    lines.append(f"{sha256_file(index_path)}  runs-index.json")
    total_bytes += index_path.stat().st_size
    return "\n".join(lines) + "\n", total_bytes


def add_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name=name)
    info.size = len(payload)
    info.mode = 0o644
    info.mtime = int(time.time())
    archive.addfile(info, io.BytesIO(payload))


def railway_base(args: argparse.Namespace) -> list[str]:
    return [
        args.railway_bin,
        "ssh",
        "--service",
        args.service,
        "--environment",
        args.environment,
    ]


def railway_run(
    args: argparse.Namespace,
    command: list[str],
    *,
    input_bytes: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        railway_base(args) + command,
        cwd=args.railway_cwd,
        input=input_bytes,
        check=True,
    )


def stream_archive(
    args: argparse.Namespace,
    run_dir: Path,
    index_path: Path,
    manifest: str,
    stage: str,
    source: str,
) -> None:
    command = railway_base(args) + ["tar", "-xzf", "-", "-C", stage]
    process = subprocess.Popen(command, cwd=args.railway_cwd, stdin=subprocess.PIPE)
    if process.stdin is None:
        raise RuntimeError("failed to open Railway upload stream")

    receipt = json.dumps(
        {
            "run": args.run_name,
            "source": source,
            "published_at_unix": int(time.time()),
            "manifest_sha256": hashlib.sha256(manifest.encode()).hexdigest(),
        },
        indent=2,
        sort_keys=True,
    ).encode() + b"\n"

    try:
        with tarfile.open(fileobj=process.stdin, mode="w|gz") as archive:
            archive.add(run_dir, arcname=args.run_name, recursive=True)
            archive.add(index_path, arcname="runs-index.json", recursive=False)
            add_bytes(archive, "MANIFEST.sha256", manifest.encode())
            add_bytes(archive, f"{args.run_name}/PUBLISH_RECEIPT.json", receipt)
    finally:
        process.stdin.close()

    return_code = process.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, command)


def finalize_script(args: argparse.Namespace, stage: str, nonce: str) -> bytes:
    replace = "1" if args.replace else "0"
    data_root = DEFAULT_DATA_ROOT
    run_name = args.run_name
    script = f"""set -eu
stage='{stage}'
run='{run_name}'
data_root='{data_root}'
final="$data_root/$run"
backup="$data_root/.rollback/$run.{nonce}"
cd "$stage"
sha256sum -cs MANIFEST.sha256
test -s "$run/run-overview.json"
grep -Fq "\\\"$run\\\"" runs-index.json
lock="$data_root/.publish-lock"
if ! mkdir "$lock"; then
  echo "REFUSED: another Railway data publication is active" >&2
  exit 45
fi
trap 'rmdir "$lock" 2>/dev/null || true' EXIT
if [ -e "$final" ]; then
  if [ '{replace}' != '1' ]; then
    echo "REFUSED: $final already exists; pass --replace for an audited replacement" >&2
    exit 42
  fi
  mkdir -p "$data_root/.rollback"
  mv "$final" "$backup"
fi
if ! mv "$stage/$run" "$final"; then
  if [ -e "$backup" ]; then mv "$backup" "$final"; fi
  exit 43
fi
cp "$stage/runs-index.json" "$data_root/.runs-index.{nonce}"
if ! mv "$data_root/.runs-index.{nonce}" "$data_root/runs-index.json"; then
  mv "$final" "$stage/$run"
  if [ -e "$backup" ]; then mv "$backup" "$final"; fi
  exit 44
fi
rm -f "$stage/MANIFEST.sha256" "$stage/runs-index.json"
rmdir "$stage"
wget -q -O /dev/null "http://127.0.0.1:8081/data/$run/run-overview.json"
echo "PUBLISHED_RUN=$run"
if [ -e "$backup" ]; then echo "ROLLBACK_COPY=$backup"; fi
"""
    return script.encode()


def validate_upload_script(args: argparse.Namespace, stage: str) -> bytes:
    run_name = args.run_name
    script = f"""set -eu
stage='{stage}'
run='{run_name}'
cd "$stage"
sha256sum -cs MANIFEST.sha256
test -s "$run/run-overview.json"
grep -Fq "\\\"$run\\\"" runs-index.json
cd /
rm -rf "$stage"
echo "UPLOAD_VALIDATED=$run"
"""
    return script.encode()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_name", type=validate_run_name)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--railway-cwd", type=Path)
    parser.add_argument("--railway-bin", default=os.environ.get("RAILWAY_BIN", "railway"))
    parser.add_argument("--service", default="arc3-viewer")
    parser.add_argument("--environment", default="production")
    parser.add_argument("--source", default="local-export")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--validate-upload-only",
        action="store_true",
        help="verify the Railway stream and remove staging without publishing",
    )
    args = parser.parse_args(argv)
    args.repo_root = args.repo_root.resolve()
    args.railway_cwd = (args.railway_cwd or args.repo_root).resolve()
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = args.repo_root / "docs" / "data" / args.run_name
    index_path = args.repo_root / "docs" / "data" / "runs-index.json"
    if not (run_dir / "run-overview.json").is_file():
        raise SystemExit(f"missing viewer export: {run_dir / 'run-overview.json'}")
    if not index_path.is_file():
        raise SystemExit(f"missing run index: {index_path}")
    if args.run_name not in index_path.read_text(encoding="utf-8"):
        raise SystemExit(f"run is absent from {index_path}")

    manifest, total_bytes = build_manifest(run_dir, args.run_name, index_path)
    summary = {
        "run": args.run_name,
        "files": len(manifest.splitlines()),
        "bytes": total_bytes,
        "manifest_sha256": hashlib.sha256(manifest.encode()).hexdigest(),
        "source": args.source,
    }
    print(json.dumps(summary, sort_keys=True))
    if args.dry_run:
        return 0

    nonce = f"{int(time.time())}-{secrets.token_hex(4)}"
    stage = f"{DEFAULT_DATA_ROOT}/.incoming/{args.run_name}.{nonce}"
    railway_run(args, ["mkdir", "-p", stage])
    stream_archive(args, run_dir, index_path, manifest, stage, args.source)
    if args.validate_upload_only:
        railway_run(args, ["sh", "-s"], input_bytes=validate_upload_script(args, stage))
        return 0
    railway_run(args, ["sh", "-s"], input_bytes=finalize_script(args, stage, nonce))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Railway command failed with status {exc.returncode}", file=sys.stderr)
        raise SystemExit(exc.returncode) from exc
