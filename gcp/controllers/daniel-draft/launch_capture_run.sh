#!/bin/bash
# Launch one Daniel-base run: launch_daniel_run.sh <label> <zone> <gs://.../notebook.ipynb>
# VM arc3-daniel-<label>, run ID daniel-<label>; outputs in gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs/<run id>/.
set -euo pipefail
LABEL=$1 ZONE=$2 NB=$3
HERE=/d/codex-work/daniel-base-20261001/runner
export CLOUDSDK_PYTHON='C:\python312\python.exe'
gcloud compute instances create "arc3-dcap-$LABEL" --zone "$ZONE" --machine-type g4-standard-48 \
  --image arc3-sglang-sm120-recovery-20260926 --image-project cellensml \
  --boot-disk-size 1000GB --boot-disk-type hyperdisk-balanced \
  --boot-disk-provisioned-iops 16000 --boot-disk-provisioned-throughput 1200 \
  --provisioning-model SPOT --instance-termination-action DELETE --max-run-duration 5h \
  --maintenance-policy TERMINATE --scopes cloud-platform --labels purpose=arc3-daniel-draft \
  --metadata "arc3-run-id=daniel-draftcap-$LABEL,arc3-notebook-object=$NB" \
  --metadata-from-file "startup-script=$HERE/daniel-run-vm-startup.sh" < /dev/null
