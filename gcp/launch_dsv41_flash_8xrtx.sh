#!/bin/bash
# DeepSeek-V4.1-Flash (552B MoE, 8B/16B active, NVFP4) on 8x RTX PRO 6000
# Blackwell (g4-standard-384, 768 GB VRAM), driving the frozen 7.36 harness
# against the full official 25 games. Ceiling measurement: same prompt, same
# clock, only the model changes. See docs/plans/2026-09-21-deepseek-v41-flash-ceiling-run.md
# and gcp/v12dsv41_flash_startup.sh.
#
# Prereqs: model staged flat in GCS (gcp/stage_dsv41_flash.sh) and the harness
# bundle object present at $BUCKET/tufa-exact/$BUNDLE.
#
# Usage: RUN_ID=g4run-dsv41flash-8xrtx-$(date -u +%Y%m%d-%H%M) MIG_NAME=arc3-g4-dsv41flash \
#   gcp/launch_dsv41_flash_8xrtx.sh
# Smoke test first (hard seven, 20 min/game):
#   ARC3_GAME_SUBSET="bp35,g50t,lf52,ls20,sk48,tn36,wa30" MAX_RUNTIME_S_PER_GAME=1200 ... same
set -euo pipefail
PROJECT=${PROJECT:-cellensml}
ZONE=${ZONE:-us-central1-b}
BUCKET=${BUCKET:-gs://cellens-ai-artifacts/arc3-duck}
MACHINE=${MACHINE:-g4-standard-384}          # 8x RTX PRO 6000 96GB; -192 = 4x (see plan §3 for why 4x is marginal)
IMAGE_FAMILY=${IMAGE_FAMILY:-common-cu129-ubuntu-2404-nvidia-580}
RUN_ID=${RUN_ID:?set RUN_ID}
MIG_NAME=${MIG_NAME:?set MIG_NAME}
MODEL_BUCKET_NAME=${MODEL_BUCKET_NAME:-DeepSeek-V4.1-Flash-NVFP4}
MODEL_HF_ID=${MODEL_HF_ID:-nvidia/DeepSeek-V4.1-Flash-NVFP4}
BUNDLE=${BUNDLE:-bundle-kaggle-compact-v5-clean-return-20260919.tgz}   # the 7.36 candidate; upload from the Codex checkout
RUNNER=${RUNNER:-v12_run_maxruntime.py}
MAX_NUM_SEQS=${MAX_NUM_SEQS:-7}              # same lane count as the 7.36 baseline: model swap is the only change. KV would allow 25+; that is a separate "throughput mode" arm
MAX_MODEL_LEN=${MAX_MODEL_LEN:-131072}       # 7.36 harness context is 102985; 1M is pointless spend
GAME_SUBSET=${ARC3_GAME_SUBSET:-}
MAX_RUNTIME_S_PER_GAME=${MAX_RUNTIME_S_PER_GAME:-2061}
MAX_RUN_RUNTIME_MINUTES=${MAX_RUN_RUNTIME_MINUTES:-132}
BLACKWELL_FLAGS=${BLACKWELL_FLAGS:-0}        # 1 = add --indexer-kv-dtype/--indexer-sparse-logits: NIGHTLY-ONLY flags. The pinned 0909 image rejects them ("unrecognized arguments", Run #2, 22-Sep 03:00Z). Startup still falls back to plain if 1 fails.
VLLM_IMAGE=${VLLM_IMAGE:-vllm/vllm-openai:deepseekv41-flash-0909}   # tag named on the NVIDIA model card (10-Sep); startup falls back to nightly

cd "$(dirname "$0")/.."
gcloud storage ls "$BUCKET/model-flat/$MODEL_BUCKET_NAME/.complete" >/dev/null || { echo "model not staged: run gcp/stage_dsv41_flash.sh first"; exit 1; }
gcloud storage ls "$BUCKET/tufa-exact/$BUNDLE" >/dev/null || { echo "harness bundle missing: $BUCKET/tufa-exact/$BUNDLE"; exit 1; }

echo "== instance template =="
TEMPLATE="$MIG_NAME-$(date -u +%Y%m%d%H%M)"
gcloud compute instance-templates create "$TEMPLATE" \
  --project="$PROJECT" \
  --machine-type="$MACHINE" \
  --image-family="$IMAGE_FAMILY" --image-project=deeplearning-platform-release \
  --boot-disk-size=1000GB --boot-disk-type=hyperdisk-balanced \
  --provisioning-model=SPOT \
  --maintenance-policy=TERMINATE \
  --scopes=cloud-platform \
  --metadata-from-file=startup-script=gcp/v12dsv41_flash_startup.sh,shutdown-script=gcp/shutdown.sh \
  --metadata=arc3-bucket="$BUCKET",arc3-run-id="$RUN_ID",arc3-mig="$MIG_NAME",arc3-model-bucket-name="$MODEL_BUCKET_NAME",arc3-model-hf-id="$MODEL_HF_ID",arc3-bundle="$BUNDLE",arc3-runner="$RUNNER",arc3-max-num-seqs="$MAX_NUM_SEQS",arc3-max-model-len="$MAX_MODEL_LEN",arc3-game-subset="${GAME_SUBSET//,/+}",arc3-max-runtime-s-per-game="$MAX_RUNTIME_S_PER_GAME",arc3-max-run-runtime-minutes="$MAX_RUN_RUNTIME_MINUTES",arc3-blackwell-flags="$BLACKWELL_FLAGS",arc3-vllm-image="$VLLM_IMAGE",install-nvidia-driver=True

echo "== managed instance group (size 1) =="
gcloud compute instance-groups managed describe "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" >/dev/null 2>&1 && \
  gcloud compute instance-groups managed delete "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" --quiet
gcloud compute instance-groups managed create "$MIG_NAME" \
  --project="$PROJECT" --zone="$ZONE" \
  --template="$TEMPLATE" --size=1

echo "== launched DeepSeek-V4.1-Flash on $MACHINE: RUN_ID=$RUN_ID MIG=$MIG_NAME subset=[${GAME_SUBSET:-full 25}] lanes=$MAX_NUM_SEQS logs at $BUCKET/$RUN_ID/ =="
