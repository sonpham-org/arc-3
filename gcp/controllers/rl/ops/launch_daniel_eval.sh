#!/bin/bash
# One evaluation run of Daniel's notebook on his GCP runner, optionally on a LoRA mirror of his inputs (plan 9g).
#   bash launch_daniel_eval.sh <label> <zone> <gs://.../notebook.ipynb> [gs:// input prefix]
# Same VM shape and startup as D:\codex-work\daniel-base-20261001\runner\launch_daniel_run.sh; the only addition is
# the arc3-input-prefix metadata his startup already reads (default: his own inputs). Outputs:
# gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs/daniel-<label>/. The VM powers off at the end.
set -euo pipefail
LABEL=$1 ZONE=$2 NB=$3 IN=${4:-}
STARTUP=/d/codex-work/daniel-base-20261001/runner/daniel-run-vm-startup.sh
export CLOUDSDK_PYTHON='C:\python312\python.exe'
META="arc3-run-id=daniel-$LABEL,arc3-notebook-object=$NB"
[ -n "$IN" ] && META="$META,arc3-input-prefix=$IN"
gcloud compute instances create "arc3-daniel-$LABEL" --zone "$ZONE" --machine-type g4-standard-48 \
  --image arc3-sglang-sm120-recovery-20260926 --image-project cellensml \
  --boot-disk-size 1000GB --boot-disk-type hyperdisk-balanced \
  --boot-disk-provisioned-iops 16000 --boot-disk-provisioned-throughput 1200 \
  --provisioning-model SPOT --instance-termination-action DELETE --max-run-duration 5h \
  --maintenance-policy TERMINATE --scopes cloud-platform --labels purpose=arc3-daniel-base \
  --metadata "$META" --metadata-from-file "startup-script=$STARTUP" < /dev/null
