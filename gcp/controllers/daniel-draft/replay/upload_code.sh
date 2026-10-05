#!/bin/bash
# Upload replay code (LF) to gs://.../daniel-draft/replay/code/. Usage: upload_code.sh file...
set -euo pipefail
export CLOUDSDK_PYTHON='C:\python312\python.exe'
RP=gs://cellens-ai-artifacts/arc3-duck/daniel-draft/replay
T=$(mktemp -d)
for f in "$@"; do tr -d '\r' < "$f" > "$T/$(basename "$f")"; done
gcloud storage cp -q "$T"/* $RP/code/
ls "$T"
