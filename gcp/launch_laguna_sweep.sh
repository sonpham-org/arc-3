#!/bin/bash
# Launch a concurrency sweep against one Laguna S 2.1 quantization: one model
# load, multiple --max-num-seqs levels tested in sequence, stops at the first
# level that fails to start. See gcp/v12laguna_sweep_startup.sh.
#
# Usage: RUN_ID=laguna-sweep-int4-$(date -u +%Y%m%d-%H%M) MIG_NAME=arc3-g4-laguna-sweep \
#   MODEL_BUCKET_NAME=Laguna-S-2.1-INT4 MODEL_HF_ID=poolside/Laguna-S-2.1-INT4 \
#   SWEEP_LEVELS="8 16 20 24 25 28" MINUTES_PER_LEVEL=3 gcp/launch_laguna_sweep.sh
set -euo pipefail
PROJECT=${PROJECT:-cellensml}
ZONE=${ZONE:-us-central1-b}
BUCKET=${BUCKET:-gs://cellens-ai-artifacts/arc3-duck}
MACHINE=${MACHINE:-g4-standard-48}
IMAGE_FAMILY=${IMAGE_FAMILY:-common-cu129-ubuntu-2404-nvidia-580}
RUN_ID=${RUN_ID:?set RUN_ID}
MIG_NAME=${MIG_NAME:?set MIG_NAME}
MODEL_BUCKET_NAME=${MODEL_BUCKET_NAME:?set MODEL_BUCKET_NAME}
MODEL_HF_ID=${MODEL_HF_ID:?set MODEL_HF_ID}
SWEEP_LEVELS=${SWEEP_LEVELS:-"8 16 20 24 25 28"}
MINUTES_PER_LEVEL=${MINUTES_PER_LEVEL:-3}

cd "$(dirname "$0")/.."

echo "== instance template =="
TEMPLATE="$MIG_NAME-$(date -u +%Y%m%d%H%M)"
gcloud compute instance-templates create "$TEMPLATE" \
  --project="$PROJECT" \
  --machine-type="$MACHINE" \
  --image-family="$IMAGE_FAMILY" --image-project=deeplearning-platform-release \
  --boot-disk-size=300GB --boot-disk-type=hyperdisk-balanced \
  --provisioning-model=SPOT \
  --maintenance-policy=TERMINATE \
  --scopes=cloud-platform \
  --metadata-from-file=startup-script=gcp/v12laguna_sweep_startup.sh,shutdown-script=gcp/shutdown.sh \
  --metadata=arc3-bucket="$BUCKET",arc3-run-id="$RUN_ID",arc3-mig="$MIG_NAME",arc3-model-bucket-name="$MODEL_BUCKET_NAME",arc3-model-hf-id="$MODEL_HF_ID",arc3-sweep-levels="$SWEEP_LEVELS",arc3-minutes-per-level="$MINUTES_PER_LEVEL",install-nvidia-driver=True

echo "== managed instance group (size 1) =="
gcloud compute instance-groups managed describe "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" >/dev/null 2>&1 && \
  gcloud compute instance-groups managed delete "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" --quiet
gcloud compute instance-groups managed create "$MIG_NAME" \
  --project="$PROJECT" --zone="$ZONE" \
  --template="$TEMPLATE" --size=1

echo "== launched laguna sweep: RUN_ID=$RUN_ID  MIG=$MIG_NAME  model=$MODEL_HF_ID  levels=[$SWEEP_LEVELS]  logs at $BUCKET/$RUN_ID/ =="
