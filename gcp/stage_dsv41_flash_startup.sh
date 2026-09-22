#!/bin/bash
# One-off staging VM: pull nvidia/DeepSeek-V4.1-Flash-NVFP4 (~492 GiB, 48 shards)
# from HuggingFace and land it FLAT in GCS at $BUCKET/model-flat/$NAME, then
# self-destruct. This is the ONLY step that talks to HF (policy: GPU VMs never
# download from HF, see gcp/upload_model_flat.sh). Run it on a cheap non-GPU VM
# with a 1.2 TB disk -- a laptop uplink is the wrong tool for half a terabyte.
#
# Metadata: arc3-bucket, arc3-model-hf-id, arc3-model-bucket-name, arc3-hf-token (optional)
set -uo pipefail
exec > >(tee -a /var/log/arc3-stage.log) 2>&1
meta() { curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
BUCKET=$(meta arc3-bucket); MODEL_ID=$(meta arc3-model-hf-id); NAME=$(meta arc3-model-bucket-name)
HF_TOKEN=$(meta arc3-hf-token || true)
ZONE=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
SELF=$(hostname)
echo "=== stage $MODEL_ID -> $BUCKET/model-flat/$NAME  $(date -u +%FT%TZ) ==="

if gcloud storage ls "$BUCKET/model-flat/$NAME/.complete" >/dev/null 2>&1; then
  echo "already staged, nothing to do"; gcloud compute instances delete "$SELF" --zone="$ZONE" --quiet; exit 0
fi

apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-pip
pip3 install -q --break-system-packages "huggingface_hub[hf_transfer]"
export HF_HUB_ENABLE_HF_TRANSFER=1 HF_TOKEN
mkdir -p /mnt/stage && cd /mnt/stage
# local_dir download = already flat, no hub-cache symlinks to lose in rsync
python3 - "$MODEL_ID" "/mnt/stage/$NAME" <<'PYEOF'
import sys
from huggingface_hub import snapshot_download
snapshot_download(sys.argv[1], local_dir=sys.argv[2],
    allow_patterns=["*.json", "*.jinja", "*.txt", "*.py", "*.safetensors", "*.md"],
    max_workers=16)
PYEOF
echo "downloaded: $(du -sh /mnt/stage/$NAME | cut -f1)"
ls /mnt/stage/$NAME/*.safetensors | wc -l | xargs echo "shards:"

gcloud storage rsync -r "/mnt/stage/$NAME" "$BUCKET/model-flat/$NAME"
echo done | gcloud storage cp - "$BUCKET/model-flat/$NAME/.complete"
gcloud storage cp /var/log/arc3-stage.log "$BUCKET/model-flat/$NAME/stage.log" || true
echo "staged; deleting self"
gcloud compute instances delete "$SELF" --zone="$ZONE" --quiet
