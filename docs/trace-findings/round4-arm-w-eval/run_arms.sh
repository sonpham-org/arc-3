#!/usr/bin/env bash
# Author: Claude Opus 5 (Bubba sub-agent, label arc3-round4w-gameplay-eval)
# Date: 20-September-2026
# PURPOSE: Drive the round-4 arm-W held-out gameplay eval on gx10-a424 unattended. Runs one
#   matched 7-game pass at a time against the single already-running vLLM server, varying
#   only MODEL. Order is breadth-first by pass index -- a complete n=1 sweep of all three
#   arms, then n=2, then n=3 -- so that stopping at any point leaves the arms balanced
#   rather than leaving one arm with more passes than another.
# SRP/DRY check: Pass -- this only sequences `make interactive` invocations. Metric
#   extraction is collect_results.py, comparison is compare_arms.py, and the game fence is
#   the seven codes fixed by distill/extract_sft.py's --exclude-games list.
set -u
GAMES="ar25-0c556536,re86-8af5384d,sb26-7fbdac44,su15-1944f8ab,tr87-cd924810,tu93-0768757b,vc33-5430563c"
CFG=/home/son/arc3-round4/eval/a424.qwen38.bf16.json
EVAL=/home/son/arc3-round4/eval
REPO=/home/son/GitHub/arc-3/ARC3-Inference
cd "$REPO" || exit 1

pass () {   # $1 = arm label, $2 = served model id
  local arm="$1" model="$2" name="r4w-a424-$1" rc
  if [ -f "$EVAL/done-$arm" ]; then echo "[$(date -u +%H:%M:%S)] skip $arm (already done)"; return 0; fi
  # Health probe. a424 runs at 109/121 GB with swap active; if vLLM has died, every
  # remaining pass would "complete" in seconds against nothing and be marked done. Abort
  # the whole driver instead of silently burning the queue.
  if ! "$REPO/scripts/server_curl.sh" "$REPO/.cache/arc3_runtime/server-api-key" \
        -fsS "http://127.0.0.1:1234/v1/models" >/dev/null 2>&1; then
    echo "[$(date -u +%H:%M:%S)] ABORT: vLLM server not answering before $arm"
    touch "$EVAL/ABORTED"; exit 1
  fi
  echo "[$(date -u +%H:%M:%S)] START $arm  model=$model"
  make interactive CONFIG_PATH="$CFG" GAME="$GAMES" MODEL="$model" \
       RUN_NAME="$name" CONCURRENT_JOBS=7 N_PASSES=1 > "$EVAL/$arm.log" 2>&1
  rc=$?
  echo "[$(date -u +%H:%M:%S)] END   $arm rc=$rc"
  # Only mark done on success, so a resume re-runs a failed pass instead of skipping it.
  if [ $rc -eq 0 ]; then touch "$EVAL/done-$arm"; else touch "$EVAL/failed-$arm"; fi
}

pass round3-p1  round3
pass round4W-p1 round4W
echo "=== n=1 SWEEP COMPLETE $(date -u +%H:%M:%S) ==="; touch "$EVAL/sweep-n1-complete"

pass base-p2    qwen38-27b-bf16
pass round3-p2  round3
pass round4W-p2 round4W
echo "=== n=2 SWEEP COMPLETE $(date -u +%H:%M:%S) ==="; touch "$EVAL/sweep-n2-complete"

pass base-p3    qwen38-27b-bf16
pass round3-p3  round3
pass round4W-p3 round4W
echo "=== n=3 SWEEP COMPLETE $(date -u +%H:%M:%S) ==="; touch "$EVAL/sweep-n3-complete"
