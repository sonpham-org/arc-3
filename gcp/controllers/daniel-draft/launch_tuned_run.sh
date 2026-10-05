#!/bin/bash
# Launch one tuned-draft run of Daniel Franzen's notebook (2-Oct-2026): launch_tuned_run.sh <label> <zone> <gs://.../notebook.ipynb>
# VM arc3-dtune-<label>, run ID daniel-drafttune-<label>; inputs from the daniel-draft mirror (stage_tuned_input.sh);
# outputs in gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs/<run id>/ (same runner as every Daniel-base run).
set -euo pipefail
LABEL=$1 ZONE=$2 NB=$3
HERE=/d/codex-work/daniel-base-20261001/runner
IN=gs://cellens-ai-artifacts/arc3-duck/daniel-draft/kaggle-input
export CLOUDSDK_PYTHON='C:\python312\python.exe'
gcloud compute instances create "arc3-dtune-$LABEL" --zone "$ZONE" --machine-type g4-standard-48 \
  --image arc3-sglang-sm120-recovery-20260926 --image-project cellensml \
  --boot-disk-size 1000GB --boot-disk-type hyperdisk-balanced \
  --boot-disk-provisioned-iops 16000 --boot-disk-provisioned-throughput 1200 \
  --provisioning-model SPOT --instance-termination-action DELETE --max-run-duration 5h \
  --maintenance-policy TERMINATE --scopes cloud-platform --labels purpose=arc3-daniel-draft \
  --metadata "arc3-run-id=daniel-drafttune-$LABEL,arc3-notebook-object=$NB,arc3-input-prefix=$IN" \
  --metadata-from-file "startup-script=$HERE/daniel-run-vm-startup.sh" < /dev/null
