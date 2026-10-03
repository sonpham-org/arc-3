#!/bin/bash
# Trainer watchdog. Spot can stop the trainer VM at any moment. The work survives (lora_train --ckpt-every keeps a
# checkpoint every optimizer step, and the trainer service reruns the unfinished job, which resumes from it), but
# nothing starts the VM again. This loop does: every 3 minutes, if the VM is stopped while the given job has no EXIT
# yet, start it, retrying through stockouts. It ends when that job has an EXIT.
#   bash ops/trainer_watchdog.sh 029-r0-merge          (stop it before stopping the VM on purpose)
export CLOUDSDK_PYTHON='C:\python312\python.exe'
LAST=${1:?last job id to watch}
VM=${VM:-arc3-rl-train4-20261002} ZONE=${ZONE:-us-south1-b}
OUT=gs://cellens-ai-artifacts/arc3-rl/trainer/train4-1002/out
say() { echo "$(date -u +%H:%M) $*"; }
say "watching $VM until $LAST has an EXIT"
while true; do
  if gcloud storage ls "$OUT/$LAST/EXIT" > /dev/null 2>&1; then
    say "$LAST finished (exit $(gcloud storage cat "$OUT/$LAST/EXIT" | tr -d '\r\n ')); watchdog ends"; exit 0
  fi
  st=$(gcloud compute instances describe "$VM" --zone "$ZONE" --format='value(status)' 2>/dev/null | tr -d '\r')
  case "$st" in
    TERMINATED|STOPPED|SUSPENDED)
      out=$(gcloud compute instances start "$VM" --zone "$ZONE" 2>&1 | tr '\n' ' ')
      if echo "$out" | grep -qiE "STOCKOUT|exhausted|not enough resources|unavailable"; then
        say "$VM was $st; start failed: no capacity, retrying"
      else
        say "$VM was $st; started ($(echo "$out" | cut -c1-120)) - the job resumes from its last checkpoint"
      fi ;;
    "") say "could not read $VM's status (gcloud login?)" ;;
  esac
  sleep 180
done
