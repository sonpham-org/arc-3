#!/usr/bin/env python3
"""
Author: Claude Opus 5.5 (Bubba)
Date: 09-October-2026 (10-October-2026: build marker, --add-checkpoints)
PURPOSE: Assemble the Kaggle dataset the level-start sprint notebook reads (internet is off on Kaggle, so everything a
  lane needs besides the model and Son's bundle ships here):
    spark_runner/   the runner's Python code (sample.py plays a lane; checkpoints.py, replays.py pick its start)
    level_sprint/   sprint.py, lanes.json, variants/
    home/solutions, home/replays   winning lines and their verified level-start replays (no-context starts)
    home/checkpoints               exact level-start checkpoints (carried-context starts), from the Spark runner
    home/environment_files         the game files the replays were verified on
    level_sprint/build-<ID>.json   the build marker: build id, time, owner/slug and every saved level start. The
                   notebook refuses to run when the attached dataset is not the build it expects, and push.py waits for
                   this file to be downloadable before pushing the notebook (Kaggle can attach the previous version).
  --add-checkpoints <dir> (repeatable): level-start checkpoints a sprint run saved (its sprint/home/checkpoints), merged
  into the runner-home copy first (new checkpoint folders only, index.json skipped, request.json / state.pkl gzipped
  back if they come unpacked), so the next dataset version ships them.
  The runner-home parts come from a local copy of Jethro's ~/arc3-runner (rsync it first; see the doc). Then
  `kaggle datasets create -p <out>` (first time) or `kaggle datasets version -p <out> -m <note>`.
  Usage: build_dataset.py --runner-home <copy of ~/arc3-runner> --owner sonphamorg --slug arc3-level-sprint --out <dir>
SRP/DRY check: Pass - copies files only; nothing is generated or edited.
"""
from __future__ import annotations

import argparse
import gzip
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.tmp")


def add_checkpoints(src: Path, home: Path) -> list[str]:
    """Copy checkpoint folders <game>/<level>/<id>/ from a sprint output into the runner home; returns the new ones."""
    added = []
    for meta in sorted(src.glob("*/*/*/meta.json")):
        d = meta.parent
        dest = home / "checkpoints" / d.relative_to(src)
        if dest.exists():
            continue
        shutil.copytree(d, dest, ignore=IGNORE)
        for name in ("request.json", "state.pkl"):
            raw = dest / name
            if raw.is_file():
                with open(raw, "rb") as a, gzip.open(f"{raw}.gz", "wb") as b:
                    shutil.copyfileobj(a, b)
                raw.unlink()
        if not (dest / "state.pkl.gz").is_file() or not (dest / "request.json.gz").is_file():
            shutil.rmtree(dest)
            raise SystemExit(f"{d}: no state.pkl / request.json, not a complete checkpoint")
        added.append(str(d.relative_to(src)))
    return added


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runner-home", type=Path, required=True)
    ap.add_argument("--owner", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--add-checkpoints", type=Path, action="append", default=[])
    args = ap.parse_args()
    for src in args.add_checkpoints:
        new = add_checkpoints(src, args.runner_home)
        print(f"added {len(new)} checkpoint(s) from {src}: {', '.join(new) or 'none new'}")
    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)
    shutil.copytree(HERE.parent / "spark_runner", args.out / "spark_runner", ignore=IGNORE)
    shutil.copytree(HERE, args.out / "level_sprint",       # one build marker per dataset: never an old one
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.tmp", "build-*.json"))
    for name in ("solutions", "replays", "checkpoints", "environment_files"):
        src = args.runner_home / name
        if not src.is_dir():
            raise SystemExit(f"missing {src}")
        shutil.copytree(src, args.out / "home" / name, ignore=IGNORE)
    (args.out / "dataset-metadata.json").write_text(json.dumps({
        "title": "ARC3 Level Sprint", "id": f"{args.owner}/{args.slug}", "licenses": [{"name": "other"}],
        "subtitle": "Runner code, replays and level-start checkpoints for the sprint"},
        indent=2))
    build = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    starts = sorted({f"{m.parent.parent.parent.name}/{m.parent.parent.name}"
                     for m in (args.out / "home" / "checkpoints").glob("*/*/*/meta.json")})
    (args.out / "level_sprint" / f"build-{build}.json").write_text(json.dumps(
        {"build": build, "dataset": f"{args.owner}/{args.slug}", "level_starts_with_checkpoints": starts}, indent=1))
    n = sum(1 for p in args.out.rglob("*") if p.is_file())
    print(f"build {build}: {len(starts)} level starts with checkpoints")
    print(f"dataset at {args.out}: {n} files")


if __name__ == "__main__":
    main()
