#!/bin/bash
# Wait until a trainer job is in the service's done list (max N minutes), then print its log tail (filtered).
#   bash wait_job.sh <job_id> [max_minutes]
export CLOUDSDK_PYTHON='C:\python312\python.exe'
J=$1; MAX=${2:-60}; T0=$(date +%s)
until gcloud storage ls "gs://cellens-ai-artifacts/arc3-rl/trainer/train4-1002/out/$J/EXIT" >/dev/null 2>&1; do
  [ $(( $(date +%s) - T0 )) -gt $(( MAX * 60 )) ] && { echo "timeout waiting for $J"; exit 1; }
  sleep 30
done
gcloud storage cat "gs://cellens-ai-artifacts/arc3-rl/trainer/train4-1002/out/$J/job.log" 2>/dev/null \
  | grep -vE '^\s*\^|File "/opt/rl/venv|return |forward_call|^Copying|warn|Loading weights|^\s*$|^\.+$|Average throughput' | tail -60
