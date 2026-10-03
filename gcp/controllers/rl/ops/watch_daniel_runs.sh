#!/bin/bash
# Watch Daniel-runner VMs (plan 9g eval panels) until every run has finished or lost its VM. Prints each phase change
# and the count of per-game viewer files (a 5-game x 5-pass panel shows 25 once all its games have started).
#   bash watch_daniel_runs.sh <label>:<zone> [<label>:<zone> ...]    (VM arc3-daniel-<label>, run id daniel-<label>)
# Dead-VM exit: a VM that is gone (Spot preemption deletes it), TERMINATED or STOPPED ends that run's watch.
# Every gcloud call here runs under `timeout 120`: with an expired login gcloud can hang instead of failing
# (3-Oct 02:57 UTC froze this loop for hours); a timeout reads as a failed check and the loop goes on.
export CLOUDSDK_PYTHON='C:\python312\python.exe'
RUNS=gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs
declare -A LAST NV DONE
warned=0
while :; do
  # an expired gcloud login makes every VM look gone: wait for a working login instead of ending the watches
  if ! timeout 120 gcloud auth print-access-token > /dev/null 2>&1; then
    [ $((warned % 15)) -eq 0 ] && echo "$(date -u +%H:%M) gcloud login expired: run gcloud.cmd auth login (watch waits)"
    warned=$((warned + 1)); sleep 120; continue
  fi
  warned=0
  left=0
  for LZ in "$@"; do
    L=${LZ%%:*} Z=${LZ##*:}
    [ -n "${DONE[$L]}" ] && continue
    P=$(timeout 120 gcloud storage cat "$RUNS/daniel-$L/phases.tsv" 2>/dev/null | tail -n 1 | cut -f1,3)
    [ "$P" != "${LAST[$L]}" ] && { echo "$(date -u +%H:%M) $L: $P"; LAST[$L]=$P; }
    N=$(timeout 120 gcloud storage ls "$RUNS/daniel-$L/working/artifacts/*_viewer_data.json" 2>/dev/null | wc -l)
    [ "$N" != "${NV[$L]:-0}" ] && { echo "$(date -u +%H:%M) $L: $N viewer files"; NV[$L]=$N; }
    ST=$(timeout 120 gcloud compute instances describe "arc3-daniel-$L" --zone "$Z" --format='value(status)' 2>/dev/null)
    if [[ "$P" == *finish* ]] || [ -z "$ST" ] || [ "$ST" = TERMINATED ] || [ "$ST" = STOPPED ]; then
      echo "$(date -u +%H:%M) $L: watch ends (vm ${ST:-gone}), last phase: $P"; DONE[$L]=1; continue
    fi
    left=$((left + 1))
  done
  [ "$left" -eq 0 ] && break
  sleep 120
done
