#!/usr/bin/env bash
# Publish a finished GCP run to arc3.sonpham.net.
#
# Usage: scripts/publish_run.sh <gcs-run-id> <log-dir-name>
#   e.g. scripts/publish_run.sh g4run-v12-20260714-1505 20260714_150500_v12-corrected-grafts
#
# Steps: pull logs from GCS -> export every website artifact -> upload one
# verified archive through the API -> commit the complete Railway catalog.
# This command does not modify Git or start a Railway deployment.
set -euo pipefail

RUN_GCS_ID=$1
RUN_NAME=$2
REPO_DIR=$(cd "$(dirname "$0")/.." && pwd)
BUCKET=gs://cellens-ai-artifacts/arc3-duck
RAILWAY_CWD=${ARC3_SITE_DIR:-$REPO_DIR}

cd "$REPO_DIR"
mkdir -p "logs/$RUN_NAME"
gcloud storage rsync -r \
  -x '(^|/)movies/|.*\.mp4$|.*\.html$|.*\.pkl$|^vllm\.log$|^startup-.*\.log$' \
  "$BUCKET/$RUN_GCS_ID" "logs/$RUN_NAME"

python3 scripts/publish_complete_run.py "$RUN_NAME" \
  --log-dir "logs/$RUN_NAME" \
  --railway-cwd "$RAILWAY_CWD" \
  --source "$BUCKET/$RUN_GCS_ID"

echo "LIVE: https://arc3.sonpham.net/internal.html"
echo "TRACE: https://arc3.sonpham.net/trace.html#run=$RUN_NAME"
echo "SCORE: https://arc3.sonpham.net/score-time.html#run=$RUN_NAME"
