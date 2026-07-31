#!/bin/bash
# Launch gpt-oss-120b on the ffa7gnsg harness against the full official 25
# games (no subset filter) -- direct comparison against the historical Qwen
# 3.6 ffa7gnsg baseline (concurrency 28, full 132-min/7920s per-game budget).
# See gcp/v12gptoss_ffa7gnsg_startup.sh.
#
# Usage: RUN_ID=g4run-v12gptoss-ffa7gnsg-$(date -u +%Y%m%d-%H%M) MIG_NAME=arc3-g4-gptoss-ffa7gnsg \
#   MODEL_BUCKET_NAME=gpt-oss-120b MODEL_HF_ID=openai/gpt-oss-120b \
#   REASONING_EFFORT=low gcp/launch_gptoss_ffa7gnsg.sh
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
REASONING_EFFORT=${REASONING_EFFORT:-low}
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
  --metadata-from-file=startup-script=gcp/v12gptoss_ffa7gnsg_startup.sh,shutdown-script=gcp/shutdown.sh \
  --metadata=arc3-bucket="$BUCKET",arc3-run-id="$RUN_ID",arc3-mig="$MIG_NAME",arc3-model-bucket-name="$MODEL_BUCKET_NAME",arc3-model-hf-id="$MODEL_HF_ID",arc3-max-num-seqs="$MAX_NUM_SEQS",arc3-reasoning-effort="$REASONING_EFFORT",install-nvidia-driver=True

echo "== managed instance group (size 1) =="
gcloud compute instance-groups managed describe "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" >/dev/null 2>&1 && \
  gcloud compute instance-groups managed delete "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" --quiet
gcloud compute instance-groups managed create "$MIG_NAME" \
  --project="$PROJECT" --zone="$ZONE" \
  --template="$TEMPLATE" --size=1

echo "== launched gpt-oss ffa7gnsg (25 games): RUN_ID=$RUN_ID  MIG=$MIG_NAME  model=$MODEL_HF_ID  reasoning_effort=$REASONING_EFFORT  max_num_seqs=$MAX_NUM_SEQS  logs at $BUCKET/$RUN_ID/ =="
