#!/bin/bash
# Launch an ffa7g (frame-full + ACTION7 + animation metadata + goal-guidance prompt)
# spot G4 run as a size-1 managed instance group. The startup (v12ffa7g_startup.sh)
# is self-contained: it pulls the pre-existing GCS deps (arc3-code-tufa0.tgz, model,
# wheelhouse, engine-wheels, v12_run.py, resource_sampler.sh) plus bundle-v12ffa7g.tgz,
# so there is nothing to pack here. The MIG recreates the VM after each spot preemption
# and scales itself to 0 when all 25 games are terminal.
#
# Usage: RUN_ID=g4run-v12ffa7g-$(date -u +%Y%m%d-%H%M) MIG_NAME=arc3-g4-v12ffa7g gcp/launch_ffa7g.sh
set -euo pipefail
PROJECT=${PROJECT:-cellensml}
ZONE=${ZONE:-us-central1-b}
BUCKET=${BUCKET:-gs://cellens-ai-artifacts/arc3-duck}
MACHINE=${MACHINE:-g4-standard-48}
IMAGE_FAMILY=${IMAGE_FAMILY:-common-cu129-ubuntu-2404-nvidia-580}
RUN_ID=${RUN_ID:?set RUN_ID, e.g. RUN_ID=g4run-v12ffa7g-$(date -u +%Y%m%d-%H%M)}
MIG_NAME=${MIG_NAME:?set MIG_NAME, e.g. MIG_NAME=arc3-g4-v12ffa7g}

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
  --metadata-from-file=startup-script=gcp/v12ffa7g_startup.sh,shutdown-script=gcp/shutdown.sh \
  --metadata=arc3-bucket="$BUCKET",arc3-run-id="$RUN_ID",arc3-mig="$MIG_NAME",install-nvidia-driver=True

echo "== managed instance group (size 1) =="
gcloud compute instance-groups managed describe "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" >/dev/null 2>&1 && \
  gcloud compute instance-groups managed delete "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" --quiet
gcloud compute instance-groups managed create "$MIG_NAME" \
  --project="$PROJECT" --zone="$ZONE" \
  --template="$TEMPLATE" --size=1

echo "== launched ffa7g: RUN_ID=$RUN_ID  MIG=$MIG_NAME  logs at $BUCKET/$RUN_ID/ =="
