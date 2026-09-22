#!/bin/bash
# Throughput probe only: bring up DeepSeek-V4.1-Flash-NVFP4 at TP8 on 8x RTX PRO 6000,
# fire ARC3-shaped prompts (12K / 48K / 90K tokens, 1500-token replies) at 1 lane and
# then N lanes, record TTFT + decode tok/s per lane + aggregate, tear down. No harness,
# no games, no bundle needed. Own MIG name so it cannot collide with the ceiling run.
# Results: $BUCKET/$RUN_ID/tps/lanes{1,N}/summary.json
#
# Usage: gcp/launch_dsv41_flash_tps.sh            (7 lanes, the 27B's lane count)
#        TPS_LANES=25 gcp/launch_dsv41_flash_tps.sh
set -euo pipefail
PROJECT=${PROJECT:-cellensml}
ZONE=${ZONE:-us-central1-b}
BUCKET=${BUCKET:-gs://cellens-ai-artifacts/arc3-duck}
MACHINE=${MACHINE:-g4-standard-384}
IMAGE_FAMILY=${IMAGE_FAMILY:-common-cu129-ubuntu-2404-nvidia-580}
RUN_ID=${RUN_ID:-g4run-dsv41flash-tps-$(date -u +%Y%m%d-%H%M)}
MIG_NAME=${MIG_NAME:-arc3-g4-dsv41flash-tps}
MODEL_BUCKET_NAME=${MODEL_BUCKET_NAME:-DeepSeek-V4.1-Flash-NVFP4}
MODEL_HF_ID=${MODEL_HF_ID:-nvidia/DeepSeek-V4.1-Flash-NVFP4}
TPS_LANES=${TPS_LANES:-7}
TPS_PROMPT_TOKENS=${TPS_PROMPT_TOKENS:-12000,48000,90000}
MAX_MODEL_LEN=${MAX_MODEL_LEN:-131072}
BLACKWELL_FLAGS=${BLACKWELL_FLAGS:-0}
VLLM_IMAGE=${VLLM_IMAGE:-vllm/vllm-openai:deepseekv41-flash-0909}   # tag named on the NVIDIA model card (10-Sep); startup falls back to nightly

cd "$(dirname "$0")/.."
gcloud storage ls "$BUCKET/model-flat/$MODEL_BUCKET_NAME/.complete" >/dev/null || { echo "model not staged: run gcp/stage_dsv41_flash.sh first"; exit 1; }
gcloud storage cp gcp/arc3_tps_probe.py "$BUCKET/code/arc3_tps_probe.py"

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
  --metadata=arc3-mode=tps,arc3-bucket="$BUCKET",arc3-run-id="$RUN_ID",arc3-mig="$MIG_NAME",arc3-model-bucket-name="$MODEL_BUCKET_NAME",arc3-model-hf-id="$MODEL_HF_ID",arc3-tps-lanes="$TPS_LANES",arc3-tps-prompt-tokens="${TPS_PROMPT_TOKENS//,/+}",arc3-max-num-seqs="$TPS_LANES",arc3-max-model-len="$MAX_MODEL_LEN",arc3-blackwell-flags="$BLACKWELL_FLAGS",arc3-vllm-image="$VLLM_IMAGE",install-nvidia-driver=True

gcloud compute instance-groups managed describe "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" >/dev/null 2>&1 && \
  gcloud compute instance-groups managed delete "$MIG_NAME" --zone="$ZONE" --project="$PROJECT" --quiet
gcloud compute instance-groups managed create "$MIG_NAME" --project="$PROJECT" --zone="$ZONE" --template="$TEMPLATE" --size=1
echo "== TPS probe launched: RUN_ID=$RUN_ID lanes=1,$TPS_LANES prompts=$TPS_PROMPT_TOKENS  results at $BUCKET/$RUN_ID/tps/ =="
