#!/usr/bin/env bash
# Author: Claude Opus 5 (Bubba subagent, label no-score-pressure-wide)
# Date: 21-September-2026
# PURPOSE: Wait for the stripped arm to exit, then launch the matched control arm against the
# same already-running vLLM server with identical lanes, wall and game order. Sequential rather
# than concurrent on purpose: running both arms at once would halve each lane's token rate and
# change the thing being measured.
# SRP/DRY check: Pass -- only sequences two run_nosp_a424.sh invocations.
set -u
ROOT=/home/son/arc3-nosp
while pgrep -f "inference.framework.run" >/dev/null 2>&1; do sleep 60; done
echo "[$(date -u +%H:%M:%S)] stripped arm exited; verifying server before control arm"
if ! curl -s -m 10 http://127.0.0.1:1234/v1/models >/dev/null 2>&1; then
  echo "[$(date -u +%H:%M:%S)] ABORT: vLLM not answering; control arm not launched"
  touch "$ROOT/CONTROL_ABORTED"; exit 1
fi
echo "[$(date -u +%H:%M:%S)] launching control arm"
cd "$ROOT" && ARM=control LANES=25 WALL=150 ./run_nosp_a424.sh > "$ROOT/control-run.log" 2>&1
rc=$?
echo "[$(date -u +%H:%M:%S)] control arm exited rc=$rc"
touch "$ROOT/BOTH_ARMS_DONE"
