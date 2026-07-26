#!/bin/bash
# Launch a short (~10 min) RTX PRO 6000 spot boot to measure real tokens/sec
# and peak VRAM for one Laguna S 2.1 quantization. Self-tears-down when the
# load test finishes -- see gcp/v12laguna_tps_startup.sh.
#
# Usage: RUN_ID=laguna-tps-int4-$(date -u +%Y%m%d-%H%M) MIG_NAME=arc3-g4-laguna-tps \
#   MODEL_BUCKET_NAME=Laguna-S-2.1-INT4 MODEL_HF_ID=poolside/Laguna-S-2.1-INT4 \
#   gcp/launch_laguna_tps.sh
set -euo pipefail
PROJECT=${PROJECT:-cellensml}
ZONE=${ZONE:-us-central1-b}
BUCKET=${BUCKET:-gs://cellens-ai-artifacts/arc3-duck}
MACHINE=${MACHINE:-g4-standard-48}
IMAGE_FAMILY=${IMAGE_FAMILY:-common-cu129-ubuntu-2404-nvidia-580}
RUN_ID=${RUN_ID:?set RUN_ID}
MIG_NAME=${MIG_NAME:?set MIG_NAME}
MODEL_BUCKET_NAME=${MODEL_BUCKET_NAME:?set MODEL_BUCKET_NAME, e.g. Laguna-S-2.1-INT4}
MODEL_HF_ID=${MODEL_HF_ID:?set MODEL_HF_ID, e.g. poolside/Laguna-S-2.1-INT4}
TEST_MINUTES=${TEST_MINUTES:-10}

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
  --metadata-from-file=startup-script=gcp/v12laguna_tps_startup.sh,shutdown-script=gcp/shutdown.sh \
  --metadata=arc3-bucket="$BUCKET",arc3-run-id="$RUN_ID",arc3-mig="$MIG_NAME",arc3-model-bucket-name="$MODEL_BUCKET_NAME",arc3-model-hf-id="$MODEL_HF_ID",arc3-test-minutes="$TEST_MINUTES",install-nvidia-driver=True

echo "== managed instance group (size 1) =="
gcloud compute instance-groups managed describe "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" >/dev/null 2>&1 && \
  gcloud compute instance-groups managed delete "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" --quiet
gcloud compute instance-groups managed create "$MIG_NAME" \
  --project="$PROJECT" --zone="$ZONE" \
  --template="$TEMPLATE" --size=1

echo "== launched laguna TPS test: RUN_ID=$RUN_ID  MIG=$MIG_NAME  model=$MODEL_HF_ID  logs at $BUCKET/$RUN_ID/ =="
