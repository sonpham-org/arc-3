#!/usr/bin/env python3
"""
Author: Claude Opus 5.5 (Bubba)
Date: 10-October-2026
PURPOSE: Offline check of a sprint dataset build before spending Kaggle hours: copies the dataset folder, unpacks its
  .gz files the way Kaggle does on upload, runs the notebook's setup steps (writable runner home, gzip request.json and
  state.pkl back), then runs that build's own sprint.py plan with the given arguments, so it prints exactly the start
  each lane would get on Kaggle. --no-regzip skips the setup cell's gzip step (shows the unreadable-checkpoint stop).
  Usage: offline_check.py <dataset dir or Kaggle download> <scratch dir> [--no-regzip] -- --start auto --expect-build <ID>
SRP/DRY check: Pass - no planning logic here; it only stages files and calls the dataset's sprint.py.
"""
import gzip, os, shutil, subprocess, sys
from pathlib import Path
data, work = Path(sys.argv[1]), Path(sys.argv[2]); rest = sys.argv[3:]
regzip = "--no-regzip" not in rest; rest = [a for a in rest if a not in ("--no-regzip", "--")]
shutil.rmtree(work, ignore_errors=True)
kag = work / "input"; shutil.copytree(data, kag)
for f in list(kag.rglob("*.gz")):            # what Kaggle does on upload
    with gzip.open(f, "rb") as a, open(str(f)[:-3], "wb") as b:
        shutil.copyfileobj(a, b)
    f.unlink()
home = work / "home"; home.mkdir()
for n in ("solutions", "replays", "checkpoints"):
    shutil.copytree(kag / "home" / n, home / n)
if regzip:                                    # the notebook's setup cell
    for f in list((home / "checkpoints").rglob("*")):
        if f.is_file() and f.name in ("request.json", "state.pkl"):
            with open(f, "rb") as a, gzip.open(f"{f}.gz", "wb") as b:
                shutil.copyfileobj(a, b)
            f.unlink()
env = dict(os.environ, ARC3_RUNNER_HOME=str(home), ARC3_RUNNER_ENVIRONMENTS=str(kag / "home" / "environment_files"),
           ARC3_SPRINT_RUNNER_CODE=str(kag / "spark_runner"))
sys.exit(subprocess.run([sys.executable, str(kag / "level_sprint" / "sprint.py"), "plan", *rest], env=env).returncode)
