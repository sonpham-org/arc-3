#!/usr/bin/env python3
"""
Author: Claude Opus 5.5 (Bubba)
Date: 09-October-2026
PURPOSE: Assemble the Kaggle dataset the level-start sprint notebook reads (internet is off on Kaggle, so everything a
  lane needs besides the model and Son's bundle ships here):
    spark_runner/   the runner's Python code (sample.py plays a lane; checkpoints.py, replays.py pick its start)
    level_sprint/   sprint.py, lanes.json, variants/
    home/solutions, home/replays   winning lines and their verified level-start replays (no-context starts)
    home/checkpoints               exact level-start checkpoints (carried-context starts), from the Spark runner
    home/environment_files         the game files the replays were verified on
  The runner-home parts come from a local copy of Jethro's ~/arc3-runner (rsync it first; see the doc). Then
  `kaggle datasets create -p <out>` (first time) or `kaggle datasets version -p <out> -m <note>`.
  Usage: build_dataset.py --runner-home <copy of ~/arc3-runner> --owner sonphamorg --slug arc3-level-sprint --out <dir>
SRP/DRY check: Pass - copies files only; nothing is generated or edited.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.tmp")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runner-home", type=Path, required=True)
    ap.add_argument("--owner", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)
    shutil.copytree(HERE.parent / "spark_runner", args.out / "spark_runner", ignore=IGNORE)
    shutil.copytree(HERE, args.out / "level_sprint", ignore=IGNORE)
    for name in ("solutions", "replays", "checkpoints", "environment_files"):
        src = args.runner_home / name
        if not src.is_dir():
            raise SystemExit(f"missing {src}")
        shutil.copytree(src, args.out / "home" / name, ignore=IGNORE)
    (args.out / "dataset-metadata.json").write_text(json.dumps({
        "title": "ARC3 Level Sprint", "id": f"{args.owner}/{args.slug}", "licenses": [{"name": "other"}],
        "subtitle": "Runner code, replays and level-start checkpoints for the sprint"},
        indent=2))
    n = sum(1 for p in args.out.rglob("*") if p.is_file())
    print(f"dataset at {args.out}: {n} files")


if __name__ == "__main__":
    main()
