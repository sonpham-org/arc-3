#!/usr/bin/env bash
# Author: Claude Opus 5 (Bubba subagent, label no-score-pressure-wide)
# Date: 21-September-2026
# PURPOSE: Wait for whatever else is using a424 to finish on its own, then take the box,
# switch the tool-call parser from hermes to qwen3_coder, PROVE the new parser returns a
# native tool call before spending any wall on a timed arm, and only then run the stripped
# arm followed by the matched control arm.
#
# It never kills another operator's run. It waits for the box to be idle. The hermes parser is
# a proven defect on this box (zero native tool_calls; every call recovered from markup; second
# request of each turn times out and the turn retries forever), so nothing is launched until
# the replacement parser is demonstrated working -- the failure this guards against is burning
# five hours on a second wrong parser.
# SRP/DRY check: Pass -- sequences existing scripts (serve_nosp_a424.sh, run_nosp_a424.sh) and
# the existing parser probe. Reimplements none of them.
set -u
ROOT=/home/son/arc3-nosp
DEADLINE=$(date -u -d "2026-09-22 02:00" +%s)

log () { echo "[$(date -u +%H:%M:%S)] $*"; }

log "waiting for the box to go idle (never killing another run)"
while pgrep -f "inference.framework.run" >/dev/null 2>&1; do
  if [ "$(date -u +%s)" -gt "$DEADLINE" ]; then
    log "DEADLINE reached with the box still busy; not waiting further"
    touch "$ROOT/TAKEOVER_ABANDONED"; exit 2
  fi
  sleep 60
done
log "box idle; taking it"

SPID=$(pgrep -f "vllm[ ]serve" | head -1); ENG=$(pgrep -f "VLLM::EngineCore" | head -1)
[ -n "$SPID$ENG" ] && kill $SPID $ENG 2>/dev/null
sleep 10; kill -9 $SPID $ENG 2>/dev/null; sleep 5

sed -i 's/--tool-call-parser hermes/--tool-call-parser qwen3_coder/' "$ROOT/serve_nosp_a424.sh"
log "parser now: $(grep -o 'tool-call-parser [a-z0-9_]*' "$ROOT/serve_nosp_a424.sh")"

cd "$ROOT" && setsid nohup ./serve_nosp_a424.sh > /dev/null 2>&1 < /dev/null &
for i in $(seq 1 90); do
  curl -s -m 3 http://127.0.0.1:1234/v1/models >/dev/null 2>&1 && break
  sleep 10
done
if ! curl -s -m 5 http://127.0.0.1:1234/v1/models >/dev/null 2>&1; then
  log "ABORT: server never came up"; touch "$ROOT/TAKEOVER_FAILED"; exit 1
fi
log "server up; probing the parser"

PROBE=$(/home/son/venv/bin/python3 /tmp/parsertest.py 2>&1)
echo "$PROBE"
NATIVE=$(echo "$PROBE" | sed -n 's/^native tool_calls: //p')
if [ "${NATIVE:-0}" -lt 1 ]; then
  log "ABORT: qwen3_coder returned $NATIVE native tool calls. Not launching a timed arm."
  touch "$ROOT/PARSER_PROBE_FAILED"; exit 1
fi
log "parser verified: $NATIVE native tool call(s). Launching arms."

cd "$ROOT" && ARM=stripped LANES=25 WALL=150 ./run_nosp_a424.sh > "$ROOT/stripped-run.log" 2>&1
log "stripped arm exited rc=$?"
touch "$ROOT/STRIPPED_DONE"

if curl -s -m 10 http://127.0.0.1:1234/v1/models >/dev/null 2>&1; then
  cd "$ROOT" && ARM=control LANES=25 WALL=150 ./run_nosp_a424.sh > "$ROOT/control-run.log" 2>&1
  log "control arm exited rc=$?"
else
  log "ABORT: server died; control arm not run"; touch "$ROOT/CONTROL_ABORTED"
fi
touch "$ROOT/BOTH_ARMS_DONE"
log "done"
