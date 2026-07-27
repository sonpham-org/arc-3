#!/bin/bash
# Launch one arm of the Laguna token-efficiency A/B/C/D spot-test sweep (see
# v12laguna_spottest_startup.sh). 7-game fast-iteration subset, concurrency 8
# (>= subset size, single wave, full 7920s budget per game).
#
# Usage: RUN_ID=g4run-v12laguna-spottest-promptfix-$(date -u +%Y%m%d-%H%M) \
#   MIG_NAME=arc3-g4-laguna-spottest-promptfix \
#   MODEL_BUCKET_NAME=Laguna-S-2.1-INT4 MODEL_HF_ID=poolside/Laguna-S-2.1-INT4 \
#   BUNDLE_NAME=bundle-v12ffa7gnsg-textgrid-concise ENABLE_THINKING=true MAX_OUTPUT_TOKENS=0 \
#   gcp/launch_laguna_spottest.sh
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
BUNDLE_NAME=${BUNDLE_NAME:?set BUNDLE_NAME}
ENABLE_THINKING=${ENABLE_THINKING:?set ENABLE_THINKING (true|false)}
MAX_OUTPUT_TOKENS=${MAX_OUTPUT_TOKENS:-0}
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
  --metadata-from-file=startup-script=gcp/v12laguna_spottest_startup.sh,shutdown-script=gcp/shutdown.sh \
  --metadata=arc3-bucket="$BUCKET",arc3-run-id="$RUN_ID",arc3-mig="$MIG_NAME",arc3-model-bucket-name="$MODEL_BUCKET_NAME",arc3-model-hf-id="$MODEL_HF_ID",arc3-max-num-seqs="$MAX_NUM_SEQS",arc3-bundle-name="$BUNDLE_NAME",arc3-enable-thinking="$ENABLE_THINKING",arc3-max-output-tokens="$MAX_OUTPUT_TOKENS",install-nvidia-driver=True

echo "== managed instance group (size 1) =="
gcloud compute instance-groups managed describe "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" >/dev/null 2>&1 && \
  gcloud compute instance-groups managed delete "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" --quiet
gcloud compute instance-groups managed create "$MIG_NAME" \
  --project="$PROJECT" --zone="$ZONE" \
  --template="$TEMPLATE" --size=1

echo "== launched laguna spottest: RUN_ID=$RUN_ID MIG=$MIG_NAME bundle=$BUNDLE_NAME thinking=$ENABLE_THINKING max_output=$MAX_OUTPUT_TOKENS logs at $BUCKET/$RUN_ID/ =="
