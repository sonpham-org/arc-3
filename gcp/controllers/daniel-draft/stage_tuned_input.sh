#!/bin/bash
# Stage the Kaggle-input mirror for tuned-draft runs (2-Oct-2026): stage_tuned_input.sh <gs://.../drafter-tuned>
# = Daniel's mirror (daniel-base/kaggle-input, copied server-side) + the tuned drafter at
# models/cellens/daniel-drafter-tuned/transformers/default/1/ (tuned_cell.py points DRAFT_MODEL_DIR there).
# _STAGED_OK is written last: the runner waits for it before copying the inputs. Extra files beside his manifest are
# fine (the runner's input check only requires every manifest file at its size).
set -euo pipefail
TUNED=${1%/}
SRC=gs://cellens-ai-artifacts/arc3-duck/daniel-base/kaggle-input
DST=gs://cellens-ai-artifacts/arc3-duck/daniel-draft/kaggle-input
export CLOUDSDK_PYTHON='C:\python312\python.exe'
gcloud storage rm -q "$DST/_STAGED_OK" 2>/dev/null || true
gcloud storage rsync -r -q -x '^_STAGED_OK$' "$SRC" "$DST"
gcloud storage rsync -r -q --delete-unmatched-destination-objects "$TUNED" "$DST/models/cellens/daniel-drafter-tuned/transformers/default/1"
gcloud storage cat "$DST/models/cellens/daniel-drafter-tuned/transformers/default/1/TUNED.json" | head -c 400; echo
gcloud storage cp -q "$SRC/_STAGED_OK" "$DST/_STAGED_OK"
echo "staged $DST"
