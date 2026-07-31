#!/bin/bash
# Launch the ffa7g-hudpixel smoke test (see v12hudpixel_spottest_startup.sh).
# 7-game fast-iteration subset, RedHatAI FP8 on vLLM 0.25.1, concurrency 8.
#
# Usage: RUN_ID=g4run-hudpixel-spottest-$(date -u +%Y%m%d-%H%M) \
#   MIG_NAME=arc3-g4-hudpixel-spottest \
#   gcp/launch_hudpixel_spottest.sh
set -euo pipefail
PROJECT=${PROJECT:-cellensml}
ZONE=${ZONE:-us-central1-b}
BUCKET=${BUCKET:-gs://cellens-ai-artifacts/arc3-duck}
MACHINE=${MACHINE:-g4-standard-48}
IMAGE_FAMILY=${IMAGE_FAMILY:-common-cu129-ubuntu-2404-nvidia-580}
RUN_ID=${RUN_ID:?set RUN_ID}
MIG_NAME=${MIG_NAME:?set MIG_NAME}
MAX_NUM_SEQS=${MAX_NUM_SEQS:-8}
HUD_REFRESH_ACTIONS=${HUD_REFRESH_ACTIONS:-4}

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
  --metadata-from-file=startup-script=gcp/v12hudpixel_spottest_startup.sh,shutdown-script=gcp/shutdown.sh \
  --metadata=arc3-bucket="$BUCKET",arc3-run-id="$RUN_ID",arc3-mig="$MIG_NAME",arc3-max-num-seqs="$MAX_NUM_SEQS",arc3-hud-refresh-actions="$HUD_REFRESH_ACTIONS",install-nvidia-driver=True

echo "== managed instance group (size 1) =="
gcloud compute instance-groups managed describe "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" >/dev/null 2>&1 && \
  gcloud compute instance-groups managed delete "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" --quiet
gcloud compute instance-groups managed create "$MIG_NAME" \
  --project="$PROJECT" --zone="$ZONE" \
  --template="$TEMPLATE" --size=1

echo "== launched hudpixel spottest: RUN_ID=$RUN_ID MIG=$MIG_NAME logs at $BUCKET/$RUN_ID/ =="
