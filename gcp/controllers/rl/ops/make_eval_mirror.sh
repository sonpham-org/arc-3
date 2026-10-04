#!/bin/bash
# A copy of Daniel's Kaggle inputs with merged LoRA shards swapped into his model (plan 9g), for his GCP runner.
#   bash make_eval_mirror.sh <tag> <gs:// prefix holding the merged *.safetensors and MERGE_REPORT.json>
# -> gs://cellens-ai-artifacts/arc3-duck/daniel-base/kaggle-input-<tag>/ (copied inside GCS, nothing downloaded).
# merge_lora.py --only-changed rewrites target bytes in place, so every swapped shard keeps its size and the runner's
# manifest check (names + sizes) still passes. _STAGED_OK is written last: the runner waits for it.
# MIRROR_BASE=daniel-draft (4-Oct): start from the tuned-drafter inputs instead, for the rollout server's kv4s13 build
# (it reads models/cellens/daniel-drafter-tuned); the copy is then daniel-draft/kaggle-input-<tag>.
set -euo pipefail
TAG=$1 MERGED=${2%/}
export CLOUDSDK_PYTHON='C:\python312\python.exe'
ROOT=gs://cellens-ai-artifacts/arc3-duck/${MIRROR_BASE:-daniel-base}
BASE=$ROOT/kaggle-input
DST=$ROOT/kaggle-input-$TAG
MODEL=models/dfranzen/intel-qwen3.8-flash-next-w4a16-autoround/transformers/default/1
gcloud storage ls "$MERGED/MERGE_REPORT.json" > /dev/null
gcloud storage rsync -r -x '_STAGED_OK$' "$BASE" "$DST"
for f in $(gcloud storage ls "$MERGED/" | grep -E '\.safetensors$'); do
  gcloud storage cp "$f" "$DST/$MODEL/"
done
gcloud storage cp "$MERGED/MERGE_REPORT.json" "$DST/MERGE_REPORT.json"
echo "lora mirror $TAG from $MERGED $(date -u +%FT%TZ)" | gcloud storage cp - "$DST/_STAGED_OK"
echo "$DST"
