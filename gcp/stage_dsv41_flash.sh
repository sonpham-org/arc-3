#!/bin/bash
# Launch the one-off staging VM that lands DeepSeek-V4.1-Flash-NVFP4 in GCS.
# ~492 GiB: budget 30-60 min on an n2 with a 1.2 TB pd-balanced scratch disk.
# The VM deletes itself when $BUCKET/model-flat/$NAME/.complete exists.
#
# Usage: gcp/stage_dsv41_flash.sh
#   MODEL_HF_ID=nvidia/DeepSeek-V4.1-Flash-NVFP4  MODEL_BUCKET_NAME=DeepSeek-V4.1-Flash-NVFP4
#   HF_TOKEN=hf_...  (only if the repo is gated)
set -euo pipefail
PROJECT=${PROJECT:-cellensml}
ZONE=${ZONE:-us-central1-b}
BUCKET=${BUCKET:-gs://cellens-ai-artifacts/arc3-duck}
MODEL_HF_ID=${MODEL_HF_ID:-nvidia/DeepSeek-V4.1-Flash-NVFP4}
MODEL_BUCKET_NAME=${MODEL_BUCKET_NAME:-DeepSeek-V4.1-Flash-NVFP4}
HF_TOKEN=${HF_TOKEN:-}
NAME=arc3-stage-dsv41-$(date -u +%Y%m%d%H%M)
cd "$(dirname "$0")/.."
gcloud compute instances create "$NAME" \
  --project="$PROJECT" --zone="$ZONE" \
  --machine-type=n2-standard-8 \
  --image-family=debian-12 --image-project=debian-cloud \
  --boot-disk-size=1200GB --boot-disk-type=pd-balanced \
  --scopes=cloud-platform \
  --metadata-from-file=startup-script=gcp/stage_dsv41_flash_startup.sh \
  --metadata=arc3-bucket="$BUCKET",arc3-model-hf-id="$MODEL_HF_ID",arc3-model-bucket-name="$MODEL_BUCKET_NAME",arc3-hf-token="$HF_TOKEN"
echo "== staging $MODEL_HF_ID -> $BUCKET/model-flat/$MODEL_BUCKET_NAME on $NAME; watch: gcloud storage ls $BUCKET/model-flat/$MODEL_BUCKET_NAME/.complete =="
