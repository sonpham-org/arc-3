#!/bin/bash
# Launch one arm of the Qwen3.6-27B quant-candidate TPS smoke test (see
# v12qwenquant_tps_startup.sh). Pure serving benchmark, hard time cap, no
# harness/game loop.
#
# Usage: RUN_ID=g4run-qwenquant-tps-redhatai-$(date -u +%Y%m%d-%H%M) \
#   MIG_NAME=arc3-g4-qwenquant-tps-redhatai \
#   MODEL_BUCKET_NAME=Qwen3.6-27B-FP8-redhatai MODEL_HF_ID=RedHatAI/Qwen3.6-27B-FP8 \
#   QUANT_LABEL=redhatai-fp8 TIME_CAP_S=1200 \
#   gcp/launch_qwenquant_tps.sh
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
QUANT_LABEL=${QUANT_LABEL:-$MODEL_BUCKET_NAME}
TIME_CAP_S=${TIME_CAP_S:-1200}

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
  --metadata-from-file=startup-script=gcp/v12qwenquant_tps_startup.sh,shutdown-script=gcp/shutdown.sh \
  --metadata=arc3-bucket="$BUCKET",arc3-run-id="$RUN_ID",arc3-mig="$MIG_NAME",arc3-model-bucket-name="$MODEL_BUCKET_NAME",arc3-model-hf-id="$MODEL_HF_ID",arc3-quant-label="$QUANT_LABEL",arc3-time-cap-s="$TIME_CAP_S",install-nvidia-driver=True

echo "== managed instance group (size 1) =="
gcloud compute instance-groups managed describe "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" >/dev/null 2>&1 && \
  gcloud compute instance-groups managed delete "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" --quiet
gcloud compute instance-groups managed create "$MIG_NAME" \
  --project="$PROJECT" --zone="$ZONE" \
  --template="$TEMPLATE" --size=1

echo "== launched qwenquant tps: RUN_ID=$RUN_ID MIG=$MIG_NAME model=$MODEL_HF_ID label=$QUANT_LABEL time_cap_s=$TIME_CAP_S logs at $BUCKET/$RUN_ID/ =="
