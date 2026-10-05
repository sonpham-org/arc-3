#!/bin/bash
# Launch one throughput-bench run (60-min gameplay budget, not scored) of Daniel Franzen's notebook (2-Oct-2026): launch_hicache_run.sh <label> <gs://.../notebook.ipynb> <zone> [<zone> ...]
# VM arc3-dbench-<label>, run ID daniel-bench-<label>; inputs from the daniel-draft mirror (tuned drafter included);
# outputs in gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs/<run id>/ (same runner as every Daniel-base run).
# Tries the zones in order until one has G4 Spot capacity.
set -uo pipefail
LABEL=$1 NB=$2; shift 2
HERE=/d/codex-work/daniel-base-20261001/runner
IN=gs://cellens-ai-artifacts/arc3-duck/daniel-draft/kaggle-input
export CLOUDSDK_PYTHON='C:\python312\python.exe'
for ZONE in "$@"; do
  if gcloud compute instances create "arc3-dbench-$LABEL" --zone "$ZONE" --machine-type g4-standard-48 \
      --image arc3-sglang-sm120-recovery-20260926 --image-project cellensml \
      --boot-disk-size 1000GB --boot-disk-type hyperdisk-balanced \
      --boot-disk-provisioned-iops 16000 --boot-disk-provisioned-throughput 1200 \
      --provisioning-model SPOT --instance-termination-action DELETE --max-run-duration 3h \
      --maintenance-policy TERMINATE --scopes cloud-platform --labels purpose=arc3-daniel-draft \
      --metadata "arc3-run-id=daniel-bench-$LABEL,arc3-notebook-object=$NB,arc3-input-prefix=$IN" \
      --metadata-from-file "startup-script=$HERE/daniel-run-vm-startup.sh" < /dev/null > "/tmp/launch-dbench-$LABEL.log" 2>&1; then
    echo "launched arc3-dbench-$LABEL in $ZONE (run daniel-bench-$LABEL)"; exit 0
  fi
  echo "$ZONE: $(grep -o -m1 'STOCKOUT\|QUOTA[A-Z_]*\|already exists\|ZONE_RESOURCE_POOL_EXHAUSTED\|does not have enough resources' "/tmp/launch-dbench-$LABEL.log")"
done
exit 1
