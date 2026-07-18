#!/bin/bash
# Launch a spot RTX PRO 6000 run that plays ONE game N times (default 25) offline,
# to get a ROBUST per-game score (mean +/- variance) instead of the +/-1.0 lottery
# a single all-25 pass gives. No ARC API -- offline bundled env files.
#
# Usage:
#   GAME=ft09 gcp/launch_single_game.sh
#   GAME=ls20 N_PASSES=25 BUNDLE=bundle-v12a7.tgz gcp/launch_single_game.sh
#
# When DONE, the per-pass scores are in the run's benchmark.json; get mean/std with
# the ANALYSIS command printed at the end. The startup tries to self-scale the MIG
# to 0; if it lingers, run the SCALE-DOWN command printed at the end.
set -euo pipefail

GAME=${GAME:?set GAME, e.g. GAME=ft09}
N_PASSES=${N_PASSES:-25}
BUNDLE=${BUNDLE:-bundle-v12a7.tgz}
PROJECT=${PROJECT:-cellensml}
ZONE=${ZONE:-us-central1-b}
BUCKET=${BUCKET:-gs://cellens-ai-artifacts/arc3-duck}
MACHINE=${MACHINE:-g4-standard-48}
IMAGE_FAMILY=${IMAGE_FAMILY:-common-cu129-ubuntu-2404-nvidia-580}

SAFE=$(echo "$GAME" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9')
MIG_NAME=arc3-g4-sg-$SAFE
RUN_ID=g4run-sg-$SAFE-$(date -u +%Y%m%d-%H%M)
TEMPLATE="$MIG_NAME-$(date -u +%Y%m%d%H%M)"

cd "$(dirname "$0")/.."

echo "== single-game run: $GAME x $N_PASSES passes | bundle=$BUNDLE | RUN_ID=$RUN_ID =="

# The startup pulls the runner from GCS -- keep it current.
gcloud storage cp gcp/v12_run_single.py "$BUCKET/code/v12_run_single.py" --project="$PROJECT"

gcloud compute instance-templates create "$TEMPLATE" \
  --project="$PROJECT" --machine-type="$MACHINE" \
  --image-family="$IMAGE_FAMILY" --image-project=deeplearning-platform-release \
  --boot-disk-size=300GB --boot-disk-type=hyperdisk-balanced \
  --provisioning-model=SPOT --maintenance-policy=TERMINATE --scopes=cloud-platform \
  --metadata-from-file=startup-script=gcp/single_game_startup.sh,shutdown-script=gcp/shutdown.sh \
  --metadata=arc3-bucket="$BUCKET",arc3-run-id="$RUN_ID",arc3-mig="$MIG_NAME",arc3-single-game="$GAME",arc3-n-passes="$N_PASSES",arc3-bundle-file="$BUNDLE",install-nvidia-driver=True

gcloud compute instance-groups managed describe "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" >/dev/null 2>&1 && \
  gcloud compute instance-groups managed delete "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" --quiet
gcloud compute instance-groups managed create "$MIG_NAME" \
  --project="$PROJECT" --zone="$ZONE" --template="$TEMPLATE" --size=1

echo ""
echo "== LAUNCHED $RUN_ID =="
echo "logs:       $BUCKET/$RUN_ID/"
echo "ANALYSIS (mean/std of the $N_PASSES passes, when DONE):"
echo "  gcloud storage cat $BUCKET/$RUN_ID/runs/benchmark.json | python3 -c \"import sys,json,statistics as st; d=json.load(sys.stdin); s=[g.get('final_score',g.get('score')) for g in d['game_runs']]; s=[x for x in s if x is not None]; print('passes:',len(s),'mean:',round(st.mean(s),3),'std:',round(st.pstdev(s),3),'min:',min(s),'max:',max(s))\""
echo "SCALE-DOWN (if the MIG lingers after DONE):"
echo "  gcloud compute instance-groups managed resize $MIG_NAME --size=0 --zone=$ZONE --project=$PROJECT"
