#!/bin/bash
# Simple VM queue (4-Oct-2026, daniel-draft kernels): run "label notebook" jobs with at most MAX of my VMs at once,
# deleting each VM (by exact name) as soon as its run finishes. Usage: vmq.sh MAX jobfile ["running labels"]
# The job file is re-read every loop: append lines to queue more runs; a label is launched at most once.
# jobfile lines: <label> <gs notebook path>
MAX=$1; JOBS=$2
export CLOUDSDK_PYTHON='C:\python312\python.exe'
B=gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs
ZONES="us-west1-b us-east5-b us-south1-b us-east1-b europe-west4-a"
declare -A ZONE_OF
running=()
declare -A LAUNCHED   # labels launched (or passed as already running): never relaunched; the job file is re-read each loop
finished() { gcloud storage cat "$B/daniel-bench-$1/phases.tsv" 2>/dev/null | grep -q "finish"; }
reap() {
  local keep=()
  for l in "${running[@]}"; do
    if finished "$l"; then
      for z in $ZONES; do
        if gcloud compute instances describe "arc3-dbench-$l" --zone "$z" --format="value(status)" >/dev/null 2>&1; then
          until gcloud compute instances describe "arc3-dbench-$l" --zone "$z" --format="value(status)" 2>/dev/null | grep -q TERMINATED; do sleep 15; done
          gcloud compute instances delete "arc3-dbench-$l" --zone "$z" --quiet >/dev/null 2>&1
          echo "$(date -u +%H:%M) done+deleted $l ($z)"
        fi
      done
    else
      keep+=("$l")
    fi
  done
  running=("${keep[@]}")
}
for l in $3; do running+=("$l"); LAUNCHED[$l]=1; done   # optional: labels already running (space-separated)
next_job() {   # first job-file line whose label was never launched
  local line
  while read -r line; do
    line=${line//$''/}; [ -z "${line// /}" ] && continue
    set -- $line; [ -z "${LAUNCHED[$1]}" ] && { echo "$line"; return; }
  done < "$JOBS"
}
while true; do
  reap
  job=$(next_job)
  [ -z "$job" ] && [ ${#running[@]} -eq 0 ] && break
  while [ ${#running[@]} -lt "$MAX" ] && [ -n "$job" ]; do
    set -- $job
    if out=$(bash /d/codex-work/daniel-draft/launch_bench_run.sh "$1" "$2" $ZONES 2>&1 | tail -1) && echo "$out" | grep -q launched; then
      echo "$(date -u +%H:%M) $out"; running+=("$1"); LAUNCHED[$1]=1
    else
      echo "$(date -u +%H:%M) launch failed $1: $out"; sleep 120; break
    fi
    job=$(next_job)
  done
  sleep 60
done
echo "$(date -u +%H:%M) queue empty"
