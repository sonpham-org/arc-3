#!/bin/bash
# Launch (or relaunch) the spot G4 duck-harness run as a size-1 managed instance
# group. The MIG recreates the VM after every spot preemption; startup.sh makes
# each incarnation resume where the last one stopped, and scales the MIG to zero
# when all 25 games are terminal.
set -euo pipefail

PROJECT=${PROJECT:-cellensml}
ZONE=${ZONE:-us-central1-b}
BUCKET=${BUCKET:-gs://cellens-ai-artifacts/arc3-duck}
RUN_ID=${RUN_ID:?set RUN_ID, e.g. RUN_ID=g4run-$(date -u +%Y%m%d-%H%M)}
MACHINE=${MACHINE:-g4-standard-48}
IMAGE_FAMILY=${IMAGE_FAMILY:-common-cu129-ubuntu-2404-nvidia-580}

cd "$(dirname "$0")/.."

echo "== packing code tarball (repo + environment files) =="
TARDIR=$(mktemp -d)
tar czf "$TARDIR/arc3-code.tgz" \
  --exclude='.git' --exclude='.venv' --exclude='.cache' --exclude='runs' \
  --exclude='reports' --exclude='__pycache__' --exclude='*.pyc' \
  ARC3-Inference tufa-arc-agi-framework gcp environment_files
gcloud storage cp "$TARDIR/arc3-code.tgz" "$BUCKET/code/arc3-code.tgz" --project="$PROJECT"

echo "== instance template =="
TEMPLATE="arc3-g4-duck-$(date -u +%Y%m%d%H%M)"
gcloud compute instance-templates create "$TEMPLATE" \
  --project="$PROJECT" \
  --machine-type="$MACHINE" \
  --image-family="$IMAGE_FAMILY" --image-project=deeplearning-platform-release \
  --boot-disk-size=300GB --boot-disk-type=pd-ssd \
  --provisioning-model=SPOT \
  --maintenance-policy=TERMINATE \
  --scopes=cloud-platform \
  --metadata-from-file=startup-script=gcp/startup.sh,shutdown-script=gcp/shutdown.sh \
  --metadata=arc3-bucket="$BUCKET",arc3-run-id="$RUN_ID",install-nvidia-driver=True

echo "== managed instance group (size 1) =="
gcloud compute instance-groups managed describe arc3-g4-duck --zone="$ZONE" --project="$PROJECT" >/dev/null 2>&1 && \
  gcloud compute instance-groups managed delete arc3-g4-duck --zone="$ZONE" --project="$PROJECT" --quiet
gcloud compute instance-groups managed create arc3-g4-duck \
  --project="$PROJECT" --zone="$ZONE" \
  --template="$TEMPLATE" --size=1

echo "== launched: RUN_ID=$RUN_ID  logs at $BUCKET/$RUN_ID/ =="
