#!/bin/bash
# Launch one arm of the gpt-oss-120b reasoning_effort sweep (see
# v12gptoss_spottest_startup.sh). 7-game fast-iteration subset, concurrency
# 8 (>= subset size, single wave, full 7920s budget per game).
#
# Usage: RUN_ID=g4run-v12gptoss-spottest-low-$(date -u +%Y%m%d-%H%M) \
#   MIG_NAME=arc3-g4-gptoss-spot-low \
#   MODEL_BUCKET_NAME=gpt-oss-120b MODEL_HF_ID=openai/gpt-oss-120b \
#   REASONING_EFFORT=low \
#   gcp/launch_gptoss_spottest.sh
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
REASONING_EFFORT=${REASONING_EFFORT:-}
MAX_NUM_SEQS=${MAX_NUM_SEQS:-8}

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
  --metadata-from-file=startup-script=gcp/v12gptoss_spottest_startup.sh,shutdown-script=gcp/shutdown.sh \
  --metadata=arc3-bucket="$BUCKET",arc3-run-id="$RUN_ID",arc3-mig="$MIG_NAME",arc3-model-bucket-name="$MODEL_BUCKET_NAME",arc3-model-hf-id="$MODEL_HF_ID",arc3-max-num-seqs="$MAX_NUM_SEQS",arc3-reasoning-effort="$REASONING_EFFORT",install-nvidia-driver=True

echo "== managed instance group (size 1) =="
gcloud compute instance-groups managed describe "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" >/dev/null 2>&1 && \
  gcloud compute instance-groups managed delete "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" --quiet
gcloud compute instance-groups managed create "$MIG_NAME" \
  --project="$PROJECT" --zone="$ZONE" \
  --template="$TEMPLATE" --size=1

echo "== launched gpt-oss spottest: RUN_ID=$RUN_ID MIG=$MIG_NAME reasoning_effort=$REASONING_EFFORT logs at $BUCKET/$RUN_ID/ =="
