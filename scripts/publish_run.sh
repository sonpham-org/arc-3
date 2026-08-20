#!/usr/bin/env bash
# Publish a finished GCP run to arc3.sonpham.net.
#
# Usage: scripts/publish_run.sh <gcs-run-id> <log-dir-name>
#   e.g. scripts/publish_run.sh g4run-v12-20260714-1505 20260714_150500_v12-corrected-grafts
#
# Steps: pull logs from GCS -> export scoreboard + viewer JSON -> stream the
# generated run directly into Railway's persistent data volume.
# Requires: a HARNESS entry for <log-dir-name> in scripts/export_runs_index.py,
# plus a Railway-linked checkout (defaults to this repository).
set -euo pipefail

RUN_GCS_ID=$1
RUN_NAME=$2
REPO_DIR=$(cd "$(dirname "$0")/.." && pwd)
BUCKET=gs://cellens-ai-artifacts/arc3-duck
RAILWAY_CWD=${ARC3_SITE_DIR:-$REPO_DIR}

cd "$REPO_DIR"
mkdir -p "logs/$RUN_NAME"
gcloud storage rsync -r "$BUCKET/$RUN_GCS_ID/runs" "logs/$RUN_NAME"

grep -q "\"$RUN_NAME\"" scripts/export_runs_index.py \
  || { echo "ERROR: add a HARNESS entry for $RUN_NAME to scripts/export_runs_index.py first"; exit 1; }
python3 scripts/export_runs_index.py
python3 scripts/export_viewer_data.py "logs/$RUN_NAME"

python3 scripts/publish_railway_data.py "$RUN_NAME" \
  --railway-cwd "$RAILWAY_CWD" \
  --source "$BUCKET/$RUN_GCS_ID"

echo "LIVE: https://arc3.sonpham.net/viewer.html#run=$RUN_NAME"
