#!/bin/bash
# RL v1 rounds back to back on the RL box (4-Oct-2026; rl/box/README.md): round N runs run_round_box.sh; as soon as it
# has queued its training, round N+1 starts and waits for N's merge (its step 0), so no time is lost between rounds.
# The loop ends after LAST, when a round ends before queueing its training (loop gate, failed job, no box), or when
# $WORK/STOP_BOX_LOOP exists (checked before each new round).
#   BOX=arc3-rl-box1 BOX_ZONE=us-central1-b SHA=<code> NB=<gs://.../notebook.ipynb> \
#       bash ops/box_loop.sh <first round> <last round>      (round 1's env: PREV_MERGE=105k-n0-merge EXTRA_TRIES=...)
# Each round logs to $WORK/run_box_n<N>.log. TAG (b) names the jobs: round N = (103+3N)<TAG>-nN-records, +1 train,
# +2 merge, so round N+1 plays (105+3N)<TAG>-nN-merge.
set -uo pipefail
OPS=$(cd "$(dirname "$0")" && pwd)
WORK=/d/codex-work/rl-20261001
FIRST=${1:?first round} LAST=${2:?last round}
T=${TAG:-b}
say() { echo "$(date -u +%H:%M) $*"; }
for N in $(seq "$FIRST" "$LAST"); do
  [ -f "$WORK/STOP_BOX_LOOP" ] && { say "STOP_BOX_LOOP found: round $N not started"; exit 0; }
  LOG=$WORK/run_box_n$N.log
  if [ "$N" -gt "$FIRST" ]; then
    PM=$(printf '%03d%s-n%d-merge' $((105 + 3 * (N - 1))) "$T" $((N - 1)))
    ( unset EXTRA_TRIES; PREV_MERGE=$PM bash "$OPS/run_round_box.sh" "$N" >> "$LOG" 2>&1 ) &
  else
    bash "$OPS/run_round_box.sh" "$N" >> "$LOG" 2>&1 &
  fi
  PID=$!
  say "round $N started (log $LOG)"
  until grep -q "queued [0-9]*$T-n$N-train" "$LOG" 2>/dev/null; do
    kill -0 "$PID" 2>/dev/null || { say "round $N ended before queueing its training: loop stops ($(tail -n 1 "$LOG"))"; exit 1; }
    sleep 60
  done
  say "round $N queued its training"
done
wait
say "rounds $FIRST-$LAST done"
