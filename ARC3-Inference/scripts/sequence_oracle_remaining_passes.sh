#!/usr/bin/env bash
# Author: Claude Opus 5 (Bubba subagent, label arc3-oracle-marker-fix-and-relaunch)
# Date: 18-September-2026
# PURPOSE: Sequence the two remaining arm-O passes of the oracle test BEHIND the arm-B pass 2
# that a sibling launched at 18:45:55 (driver pid 963617). The plan forbids concurrent passes --
# lane contention correlates with the treatment if they overlap -- so this waits for that pass
# to exit rather than preempting it, then invokes run_oracle_multipass.sh for P2 and P4.
# Takes a lock and re-checks for any live driver immediately before firing, because two
# concurrent passes is the failure this is meant to prevent and a second sequencer would cause it.
set -u
WORK=$HOME/arc3-oracle-20260918
INF=$HOME/GitHub/arc-3/ARC3-Inference
LEDGER=$WORK/guards/ledger.txt
WAIT_PID=${WAIT_PID:-963617}
PLAN="P2:O:qwen38-27b-oracle-o-p1 P4:O:qwen38-27b-oracle-o-p2"
say(){ echo "$(date -Iseconds) SEQ $*" >> "$LEDGER"; }

mkdir "$WORK/.seq.lock" 2>/dev/null || { say "ABORT another sequencer holds .seq.lock"; exit 1; }
trap 'rmdir "$WORK/.seq.lock" 2>/dev/null' EXIT

say "START pid=$$ waiting_on_driver_pid=$WAIT_PID plan='$PLAN'"
while kill -0 "$WAIT_PID" 2>/dev/null; do sleep 30; done
say "driver pid=$WAIT_PID has exited"
sleep 60   # let the harness' children reap and the run dir settle

# Guard gate. Anything unexpected and nothing launches.
if [ -f "$WORK/ABORTED" ]; then
  say "ABORT $WORK/ABORTED exists after the arm-B pass -- not launching arm O"; exit 1
fi
# `pgrep -x -f` (exact whole-cmdline) and not a loose -f: the sibling's launcher shell and any
# ssh command line mentioning the driver both match loosely, and one of those lingering would
# block this forever. The driver's own cmdline is exactly `bash scripts/run_oracle_multipass.sh`.
LIVE=$(pgrep -x -f "bash scripts/run_oracle_multipass.sh" | tr '\n' ' ')
if [ -n "${LIVE// /}" ]; then
  say "ABORT a driver is still live (pids: $LIVE) -- refusing to run passes concurrently"; exit 1
fi
if [ -f "$WORK/banked/P2" ] || [ -f "$WORK/banked/P4" ]; then
  say "ABORT banked/P2 or banked/P4 appeared -- a sibling took these passes; not launching"; exit 1
fi
if ! curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:1234/health | grep -q 200; then
  say "ABORT vLLM /health is not 200 -- not launching"; exit 1
fi
say "guard gate clear: no live driver, no ABORTED, P2/P4 unbanked, vLLM healthy"

cd "$INF" || { say "ABORT cannot cd $INF"; exit 1; }
unset ARC3_ORACLE_RULES_DIR ARC3_REASONING_STYLE
nohup setsid env PASS_PLAN="$PLAN" bash scripts/run_oracle_multipass.sh \
  < /dev/null >> "$WORK/driver.O.out" 2>&1 &
DPID=$!
say "FIRED driver pid=$DPID plan='$PLAN' log=$WORK/driver.O.out"

# Liveness, ledgered: a launched-and-dead driver reported as running is the failure mode to
# avoid, so assert the O pass is actually producing turns rather than that a pid exists.
sleep 240
DIR=$(ls -1d "$INF"/runs/*_qwen38-27b-oracle-o-p1 2>/dev/null | tail -1)
if [ -z "$DIR" ]; then say "LIVENESS FAIL no -o-p1 run dir after 4m"; exit 1; fi
L1=$(cat "$DIR"/*_requests.jsonl 2>/dev/null | wc -l | tr -d ' ')
sleep 120
L2=$(cat "$DIR"/*_requests.jsonl 2>/dev/null | wc -l | tr -d ' ')
PL=$(ls -1 "$DIR"/prompts/* 2>/dev/null | wc -l | tr -d ' ')
if [ "$L2" -gt "$L1" ] && [ "$PL" -ge 7 ]; then
  say "LIVENESS PASS dir=$DIR prompt_logs=$PL requests ${L1}->${L2} (growing)"
else
  say "LIVENESS FAIL dir=$DIR prompt_logs=$PL requests ${L1}->${L2} (not growing) -- CHECK THE PASS"
fi
say "DONE sequencer exiting; the driver owns P2 and P4 from here"
