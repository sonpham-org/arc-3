"""vLLM watchdog for the cv5-CR clock family startups.

Added 24-Sep after g4run-cv5cr-hard7-264-…-d85c029903: at minute 31 the engine died ("RPC call to
sample_tokens timed out" -> EngineDeadError) and the harness spun for hours against a dead server with
the score frozen. The startup already has start_server/wait_server; this loop probes /v1/models every
60 s and, after three consecutive misses, snapshots the log to the bucket and restarts the container
the same way the startup did. Runs in a subshell so the outer flow is untouched; teardown kills it.
"""
import re

SNIPPET = r'''# vLLM watchdog: the 264-class hard-seven run lost its engine at minute 31 and spun for hours.
# Probe every 60 s; on 3 consecutive misses snapshot the log, restart with the same start_server/wait_server.
(
  fails=0; restarts=0
  while true; do
    sleep 60
    if curl -s -m 8 http://127.0.0.1:1234/v1/models >/dev/null 2>&1; then fails=0; continue; fi
    fails=$((fails+1))
    if [ "$fails" -lt 3 ]; then continue; fi
    restarts=$((restarts+1))
    echo "watchdog: server unreachable x$fails at $(date -u +%FT%TZ); restart #$restarts"
    cp /opt/arc3/vllm.log "/opt/arc3/vllm-crash-$restarts.log" 2>/dev/null || true
    timeout 30 gcloud storage cp "/opt/arc3/vllm-crash-$restarts.log" "$BUCKET/$RUN_ID/vllm-crash-$restarts.log" >/dev/null 2>&1 || true
    start_server "$KV_DTYPE_USED" || true
    if wait_server; then
      echo "watchdog: server back at $(date -u +%FT%TZ)"
      fails=0
    else
      echo "watchdog: restart #$restarts did not come up"
    fi
    echo "$restarts $(date -u +%FT%TZ)" | timeout 15 gcloud storage cp - "$BUCKET/$RUN_ID/SERVER_RESTARTS" >/dev/null 2>&1 || true
    if [ "$restarts" -ge 5 ]; then echo "watchdog: giving up after 5 restarts"; break; fi
  done
) &
WATCHDOG_PID=$!
'''

def add_watchdog(s: str) -> str:
    assert "WATCHDOG_PID" not in s
    s, n = re.subn(r"^capture_gameplay_metrics start$", SNIPPET + "capture_gameplay_metrics start", s, count=1, flags=re.M)
    assert n == 1, "capture_gameplay_metrics anchor"
    s, n = re.subn(r"^  docker stop -t 20 flashnext 2>/dev/null \|\| true$",
                   '  [ -n "${WATCHDOG_PID:-}" ] && kill -TERM "$WATCHDOG_PID" 2>/dev/null || true\n'
                   "  docker stop -t 20 flashnext 2>/dev/null || true", s, count=1, flags=re.M)
    assert n == 1, "teardown anchor"
    return s
