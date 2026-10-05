#!/bin/bash
# Delete each bench VM (by exact name) once its run has finished (4-Oct-2026, daniel-draft kernels).
# Usage: reap.sh label:zone [label:zone ...]
export CLOUDSDK_PYTHON='C:\python312\python.exe'
B=gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs
pending=("$@")
while [ ${#pending[@]} -gt 0 ]; do
  keep=()
  for lz in "${pending[@]}"; do
    l=${lz%%:*}; z=${lz##*:}
    if gcloud storage cat "$B/daniel-bench-$l/phases.tsv" 2>/dev/null | grep "finish" >/dev/null; then
      for i in $(seq 1 40); do
        s=$(gcloud compute instances describe "arc3-dbench-$l" --zone "$z" --format="value(status)" 2>/dev/null)
        [ -z "$s" ] && break
        [ "$s" = "TERMINATED" ] && break
        sleep 15
      done
      gcloud compute instances delete "arc3-dbench-$l" --zone "$z" --quiet >/dev/null 2>&1
      echo "$(date -u +%H:%M) done+deleted $l ($z)"
    else
      keep+=("$lz")
    fi
  done
  pending=("${keep[@]}")
  [ ${#pending[@]} -gt 0 ] && sleep 60
done
echo "$(date -u +%H:%M) all reaped"
