#!/bin/bash
# Seed a model snapshot into GCS as a FLAT directory (no HF hub-cache symlinks
# to lose in transit) -- see laguna-model-swap memory: gcloud storage rsync
# does not preserve symlinks, so the hub cache's snapshots/<hash>/ dir (all
# symlinks into blobs/) never survives a plain rsync of the hub tree. This
# script resolves the snapshot locally (cp -rL, dereferencing symlinks into
# real files) before uploading, so the GPU side just needs a flat rsync into
# /opt/arc3/model and can point --model directly at it -- zero HF-cache
# resolution logic needed there at all.
#
# Policy: VMs never download from HuggingFace; this script is the only path
# that talks to HF, and it can run from any machine with real uplink.
#
# Usage: gcp/upload_model_flat.sh <HF_MODEL_ID> <BUCKET_MODEL_NAME>
#   gcp/upload_model_flat.sh RedHatAI/Qwen3.6-27B-FP8 Qwen3.6-27B-FP8-redhatai
set -euo pipefail

MODEL_ID=${1:?set HF_MODEL_ID}
NAME=${2:?set BUCKET_MODEL_NAME}
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
    ignore_patterns=["original/*"],
    max_workers=16,
)
PYEOF

SLUG="models--${MODEL_ID//\//--}"
SNAPSHOT_DIR=$(find "$HF_HOME/hub/$SLUG/snapshots" -mindepth 1 -maxdepth 1 -type d | head -1)
FLAT_DIR=$(mktemp -d)/"$NAME"
echo "== resolving symlinks: $SNAPSHOT_DIR -> $FLAT_DIR =="
mkdir -p "$FLAT_DIR"
cp -rL "$SNAPSHOT_DIR"/. "$FLAT_DIR"/
echo "== flat dir size: $(du -sh "$FLAT_DIR" | cut -f1) =="

echo "== uploading flat dir to $BUCKET/model-flat/$NAME =="
gcloud storage rsync -r "$FLAT_DIR" "$BUCKET/model-flat/$NAME"
echo done | gcloud storage cp - "$BUCKET/model-flat/$NAME/.complete"
rm -rf "$(dirname "$FLAT_DIR")"
echo "== cleaning local HF cache for $MODEL_ID (already in GCS, VMs never read HF) =="
rm -rf "$HF_HOME/hub/$SLUG"
echo "== seeded: $BUCKET/model-flat/$NAME (marker written) =="
