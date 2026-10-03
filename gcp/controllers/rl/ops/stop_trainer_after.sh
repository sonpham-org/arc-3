#!/bin/bash
# Stop the trainer VM once a job is done AND its outputs are in GCS (idle GPUs cost; Son 3-Oct). The service writes
# a job's EXIT before (old code) or after (new code) uploading its outputs; either way its heartbeat leaves
# "running <job>" only after the upload, so wait for both. Stop the trainer watchdog's restarts first: they end at EXIT.
#   bash ops/stop_trainer_after.sh 029-r0-merge
export CLOUDSDK_PYTHON='C:\python312\python.exe'
JOB=${1:?job id}
VM=${VM:-arc3-rl-train4-20261002} ZONE=${ZONE:-us-south1-b}
T=gs://cellens-ai-artifacts/arc3-rl/trainer/train4-1002
say() { echo "$(date -u +%H:%M) $*"; }
until timeout 120 gcloud storage ls "$T/out/$JOB/EXIT" > /dev/null 2>&1; do sleep 120; done
say "$JOB EXIT $(timeout 120 gcloud storage cat "$T/out/$JOB/EXIT" | tr -d '\r\n ')"
while :; do
  hb=$(timeout 120 gcloud storage cat "$T/status.json" 2>/dev/null)
  if [ -n "$hb" ] && ! { echo "$hb" | grep -q '"state": "running"' && echo "$hb" | grep -q "\"job\": \"$JOB\""; }; then break; fi
  sleep 60
done
say "service heartbeat: $(echo "$hb" | cut -c1-100)"
timeout 300 gcloud compute instances stop "$VM" --zone "$ZONE" > /dev/null 2>&1 && say "trainer VM stopped" || say "stop failed"
