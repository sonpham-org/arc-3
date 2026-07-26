#!/bin/bash
# Same as launch_ffa7gnsg.sh (best-known config: no-impact ON, state-graph OFF),
# but boots via v12ffa7gnsg_customgames_startup.sh, which merges the 17 in-house
# custom games (gcp/environment-extra-customgames17.tgz) into environment_files/
# alongside the official 25, and defaults ARC3_GAME_SUBSET to just those 17 so
# this run plays only the custom games, not the official suite.
#
# Usage: RUN_ID=g4run-v12ffa7gnsg-customgames17-$(date -u +%Y%m%d-%H%M) MIG_NAME=arc3-g4-v12ffa7gnsg-customgames gcp/launch_ffa7gnsg_customgames.sh
set -euo pipefail
PROJECT=${PROJECT:-cellensml}
ZONE=${ZONE:-us-central1-b}
BUCKET=${BUCKET:-gs://cellens-ai-artifacts/arc3-duck}
MACHINE=${MACHINE:-g4-standard-48}
IMAGE_FAMILY=${IMAGE_FAMILY:-common-cu129-ubuntu-2404-nvidia-580}
RUN_ID=${RUN_ID:?set RUN_ID, e.g. RUN_ID=g4run-v12ffa7gnsg-customgames17-$(date -u +%Y%m%d-%H%M)}
MIG_NAME=${MIG_NAME:?set MIG_NAME, e.g. MIG_NAME=arc3-g4-v12ffa7gnsg-customgames}
GAME_SUBSET=${GAME_SUBSET:-"ac02 ar02 cr01 fr01 gh14 lb03 pc01 pi01 ps01 pt01 px02 sh01 sn02 td05 ts01 ws03-v1 ws04-v1"}

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
  --metadata-from-file=startup-script=gcp/v12ffa7gnsg_customgames_startup.sh,shutdown-script=gcp/shutdown.sh \
  --metadata=arc3-bucket="$BUCKET",arc3-run-id="$RUN_ID",arc3-mig="$MIG_NAME",arc3-reexplore-strict="${REEXPLORE_STRICT:-}",arc3-game-subset="$GAME_SUBSET",arc3-state-graph="${STATE_GRAPH:-}",arc3-bundle="${BUNDLE_NAME:-bundle-v12ffa7gnsg.tgz}",install-nvidia-driver=True

echo "== managed instance group (size 1) =="
gcloud compute instance-groups managed describe "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" >/dev/null 2>&1 && \
  gcloud compute instance-groups managed delete "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" --quiet
gcloud compute instance-groups managed create "$MIG_NAME" \
  --project="$PROJECT" --zone="$ZONE" \
  --template="$TEMPLATE" --size=1

echo "== launched ffa7gnsg+customgames17: RUN_ID=$RUN_ID  MIG=$MIG_NAME  logs at $BUCKET/$RUN_ID/ =="
