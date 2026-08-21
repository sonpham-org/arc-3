#!/usr/bin/env python3
"""Export and publish one ARC3 run as a complete dashboard transaction.

The public contract is stricter than merely uploading viewer files: a run is
published only after its overview, execution timeline, and shared run index
all exist.  The final uploader atomically installs the run plus that index on
Railway's persistent volume, keeping the scoreboard and Score Over Time in
sync.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run(command: list[str], cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_name")
    parser.add_argument("--source", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--railway-cwd", type=Path)
    parser.add_argument("--railway-bin", default="railway")
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.repo_root.resolve()
    log_dir = root / "logs" / args.run_name
    export_dir = root / "docs" / "data" / args.run_name
    index_path = root / "docs" / "data" / "runs-index.json"
    if not log_dir.is_dir():
        raise SystemExit(f"missing run logs: {log_dir}")

    run([sys.executable, "scripts/export_viewer_data.py", str(log_dir)], root)
    run([sys.executable, "scripts/export_execution_trace.py", str(log_dir)], root)
    run([sys.executable, "scripts/export_runs_index.py"], root)

    required = [export_dir / "run-overview.json", export_dir / "run-timeline.json", index_path]
    missing = [str(path) for path in required if not path.is_file() or not path.stat().st_size]
    if missing:
        raise SystemExit(f"refusing incomplete publication; missing: {', '.join(missing)}")

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    entry = next((row for row in payload.get("runs", []) if row.get("run") == args.run_name), None)
    if not entry or not entry.get("has_execution_trace"):
        raise SystemExit("refusing publication: run index lacks the execution-trace flag")

    command = [
        sys.executable,
        "scripts/publish_railway_data.py",
        args.run_name,
        "--repo-root",
        str(root),
        "--railway-cwd",
        str((args.railway_cwd or root).resolve()),
        "--railway-bin",
        args.railway_bin,
        "--source",
        args.source,
    ]
    if args.replace:
        command.append("--replace")
    if args.dry_run:
        command.append("--dry-run")
    run(command, root)
    print(f"COMPLETE_DASHBOARD_PUBLICATION={args.run_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
