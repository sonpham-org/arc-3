#!/bin/bash
# Seed a model snapshot into the GCS bucket the G4 VMs pull from.
# Policy: VMs never download from HuggingFace; this script is the only path
# that talks to HF, and it can run from any machine (workstation, a424, or a
# throwaway cloud shell -- pick one with real uplink: 31GB over home Wi-Fi is
# a day, over GCE it is minutes).
#
# Usage: gcp/upload_model.sh [HF_MODEL_ID] [BUCKET_MODEL_NAME]
#   gcp/upload_model.sh Qwen/Qwen3.6-27B-FP8 Qwen3.6-27B-FP8
#   gcp/upload_model.sh nvidia/Qwen3.6-27B-NVFP4 Qwen3.6-27B-NVFP4
set -euo pipefail

MODEL_ID=${1:-Qwen/Qwen3.6-27B-FP8}
NAME=${2:-$(basename "$MODEL_ID")}
BUCKET=${BUCKET:-gs://cellens-ai-artifacts/arc3-duck}
HF_HOME=${HF_HOME:-$HOME/.cache/huggingface}
export HF_HOME

echo "== downloading $MODEL_ID into $HF_HOME (skips files already cached) =="
python3 - "$MODEL_ID" <<'PYEOF'
import sys
from huggingface_hub import snapshot_download
snapshot_download(
    sys.argv[1],
    allow_patterns=["*.json", "*.jinja", "*.txt", "*.safetensors"],
    max_workers=16,
)
PYEOF

echo "== uploading snapshot to $BUCKET/model/$NAME/hub =="
SLUG="models--${MODEL_ID//\//--}"
gcloud storage rsync -r "$HF_HOME/hub/$SLUG" "$BUCKET/model/$NAME/hub/$SLUG"
echo done | gcloud storage cp - "$BUCKET/model/$NAME/.complete"
echo "== seeded: $BUCKET/model/$NAME (marker written) =="
