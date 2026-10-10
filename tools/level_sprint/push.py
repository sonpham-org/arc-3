#!/usr/bin/env python3
"""
Author: Claude Opus 5.5 (Bubba)
Date: 10-October-2026
PURPOSE: Ship a sprint dataset build and the sprint notebook to Kaggle in the only safe order. Version 3 of
  sonphamorg/arc3-level-start-sprint (10-Oct-2026 00:13 ET) was pushed four seconds before Kaggle finished processing
  the new dataset version; `kaggle datasets status` already said "ready" (for the previous version), so the run got the
  old sprint.py and the old checkpoints and every lane started with no context. This tool:
    1. creates the dataset (first time) or adds a version, from a folder build_dataset.py wrote;
    2. waits until that build's marker file (level_sprint/build-<ID>.json) can be downloaded from Kaggle, which only
       happens once the new version is live (a status call is not trusted);
    3. pushes the notebook folder (build_notebook.py output, built with --expect-build ID), unless --no-kernel.
  The account is the one whose access token file is given (KAGGLE_API_TOKEN is set for the child processes only).
  Usage: push.py --token-file ~/.kaggle-ronan/access_token --dataset-dir <dir> [--kernel-dir <dir>] [--message <note>]
SRP/DRY check: Pass - no Kaggle client of its own: it calls the kaggle CLI (the same one the doc's manual steps use);
  dataset contents come from build_dataset.py, the notebook from build_notebook.py.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

KAGGLE = os.environ.get("KAGGLE_CLI", "/Users/macmini/.kaggle-venv/bin/kaggle")


def kaggle(args: list[str], env: dict, check: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run([KAGGLE, *args], env=env, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise SystemExit(f"kaggle {' '.join(args[:2])} failed: {(p.stdout + p.stderr)[-800:]}")
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--token-file", type=Path, required=True)
    ap.add_argument("--dataset-dir", type=Path, required=True)
    ap.add_argument("--kernel-dir", type=Path)
    ap.add_argument("--no-kernel", action="store_true")
    ap.add_argument("--message", default="level-start sprint build")
    ap.add_argument("--wait-minutes", type=float, default=30.0)
    args = ap.parse_args()
    env = {**os.environ, "KAGGLE_API_TOKEN": str(args.token_file.expanduser())}
    ref = json.loads((args.dataset_dir / "dataset-metadata.json").read_text())["id"]
    markers = sorted((args.dataset_dir / "level_sprint").glob("build-*.json"))
    if len(markers) != 1:
        raise SystemExit(f"expected one build marker in {args.dataset_dir / 'level_sprint'}, found {len(markers)}")
    build = markers[0].stem[len("build-"):]
    if args.kernel_dir and not args.no_kernel:
        nb = next(args.kernel_dir.glob("*.ipynb")).read_text()
        if f"EXPECT_DATASET_BUILD = '{build}'" not in nb:
            raise SystemExit(f"{args.kernel_dir}: notebook not built with --expect-build {build}")

    exists = kaggle(["datasets", "files", ref, "--page-size", "1"], env, check=False).returncode == 0
    if exists:
        kaggle(["datasets", "version", "-p", str(args.dataset_dir), "-r", "zip", "-m", f"{args.message} ({build})"], env)
    else:
        kaggle(["datasets", "create", "-p", str(args.dataset_dir), "-r", "zip"], env)
    print(f"{ref}: build {build} uploaded ({'new version' if exists else 'created'}); waiting until it is live", flush=True)

    deadline = time.time() + args.wait_minutes * 60
    with tempfile.TemporaryDirectory() as tmp:
        while True:
            p = kaggle(["datasets", "download", ref, "-f", f"level_sprint/build-{build}.json", "-p", tmp, "-o"], env,
                       check=False)
            if p.returncode == 0 and any(Path(tmp).rglob(f"build-{build}.json*")):
                break
            if time.time() > deadline:
                raise SystemExit(f"{ref}: build {build} not downloadable after {args.wait_minutes} min; not pushing")
            time.sleep(20)
    print(f"{ref}: build {build} is live", flush=True)
    time.sleep(30)          # margin: the file route can lead the version the kernel push attaches by a few seconds

    if args.kernel_dir and not args.no_kernel:
        p = kaggle(["kernels", "push", "-p", str(args.kernel_dir)], env)
        print(p.stdout.strip(), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
