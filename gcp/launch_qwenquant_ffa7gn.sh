#!/bin/bash
# Launch one full ffa7gn-harness pass for one Qwen3.6-27B quant candidate
# (see v12qwenquant_ffa7gn_startup.sh). 25 games, concurrency 28, full
# 7920s/132min-per-game budget -- same config as the 2.55/1.30-scoring
# vrfai baseline, just served via vLLM 0.25.1 against a different checkpoint.
#
# Usage: RUN_ID=g4run-qwenquant-ffa7gn-redhatai-p1-$(date -u +%Y%m%d-%H%M) \
#   MIG_NAME=arc3-g4-qwenquant-redhatai-p1 \
#   MODEL_BUCKET_NAME=Qwen3.6-27B-FP8-redhatai MODEL_HF_ID=RedHatAI/Qwen3.6-27B-FP8 \
#   QUANT_LABEL=redhatai-fp8 \
#   gcp/launch_qwenquant_ffa7gn.sh
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
MAX_NUM_SEQS=${MAX_NUM_SEQS:-28}

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
  --metadata-from-file=startup-script=gcp/v12qwenquant_ffa7gn_startup.sh,shutdown-script=gcp/shutdown.sh \
  --metadata=arc3-bucket="$BUCKET",arc3-run-id="$RUN_ID",arc3-mig="$MIG_NAME",arc3-model-bucket-name="$MODEL_BUCKET_NAME",arc3-model-hf-id="$MODEL_HF_ID",arc3-quant-label="$QUANT_LABEL",arc3-max-num-seqs="$MAX_NUM_SEQS",install-nvidia-driver=True

echo "== managed instance group (size 1) =="
gcloud compute instance-groups managed describe "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" >/dev/null 2>&1 && \
  gcloud compute instance-groups managed delete "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" --quiet
gcloud compute instance-groups managed create "$MIG_NAME" \
  --project="$PROJECT" --zone="$ZONE" \
  --template="$TEMPLATE" --size=1

echo "== launched qwenquant ffa7gn: RUN_ID=$RUN_ID MIG=$MIG_NAME model=$MODEL_HF_ID label=$QUANT_LABEL logs at $BUCKET/$RUN_ID/ =="
