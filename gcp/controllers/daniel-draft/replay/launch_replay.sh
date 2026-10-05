#!/bin/bash
# Launch one replay VM (4-Oct-2026): launch_replay.sh <label> <gs://.../notebook.ipynb> <run1[,run2...]> <zone> [<zone>...]
# VM arc3-drep-<label>, outputs gs://.../daniel-draft/replay/runs/replay-<label>/, capture
# gs://.../daniel-draft/replay/captures/replay-<label>/ (synced while it runs; _DONE written at the end).
# DISK=<GB> env sets the boot disk (default 1500; inputs ~200 GB + image ~50 GB + the capture).
# Tries the zones in order until one has G4 Spot capacity. Delete the VM by exact name when it is TERMINATED.
set -uo pipefail
LABEL=$1 NB=$2 RUNS=$3; shift 3
HERE=/d/codex-work/daniel-draft/replay
IN=gs://cellens-ai-artifacts/arc3-duck/daniel-base/kaggle-input
export CLOUDSDK_PYTHON='C:\python312\python.exe'
tr -d '\r' < "$HERE/replay_vm_startup.sh" > "/tmp/replay_vm_startup.lf.sh"
for ZONE in "$@"; do
  case "$ZONE" in us-central1-*) echo "$ZONE: skipped (us-central1 is reserved for the RL loop, Son 4-Oct)"; continue;; esac
  if gcloud compute instances create "arc3-drep-$LABEL" --zone "$ZONE" --machine-type g4-standard-48 \
      --image arc3-sglang-sm120-recovery-20260926 --image-project cellensml \
      --boot-disk-size ${DISK:-1500}GB --boot-disk-type hyperdisk-balanced \
      --boot-disk-provisioned-iops 16000 --boot-disk-provisioned-throughput 1200 \
      --provisioning-model SPOT --instance-termination-action DELETE --max-run-duration 6h \
      --maintenance-policy TERMINATE --scopes cloud-platform --labels purpose=arc3-daniel-draft,owner-task=claude-replay \
      --metadata "arc3-run-id=replay-$LABEL,arc3-notebook-object=$NB,arc3-input-prefix=$IN,arc3-replay-runs=$RUNS" \
      --metadata-from-file "startup-script=/tmp/replay_vm_startup.lf.sh" < /dev/null > "/tmp/launch-drep-$LABEL.log" 2>&1; then
    echo "launched arc3-drep-$LABEL in $ZONE (replay of $RUNS)"; exit 0
  fi
  echo "$ZONE: $(grep -o -m1 'STOCKOUT\|QUOTA[A-Z_]*\|already exists\|ZONE_RESOURCE_POOL_EXHAUSTED\|does not have enough resources' "/tmp/launch-drep-$LABEL.log")"
done
exit 1
