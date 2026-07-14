#!/usr/bin/env bash
# Publish a finished GCP run to arc3.sonpham.net.
#
# Usage: scripts/publish_run.sh <gcs-run-id> <log-dir-name>
#   e.g. scripts/publish_run.sh g4run-v12-20260714-1505 20260714_150500_v12-corrected-grafts
#
# Steps: pull logs from GCS -> export scoreboard + viewer JSON -> commit/push
# arc-3 (public) -> pull the new data from GitHub into the Railway volume.
# Requires: a HARNESS entry for <log-dir-name> in scripts/export_runs_index.py,
# and the arc3-site checkout (railway-linked) at $ARC3_SITE_DIR.
set -euo pipefail

RUN_GCS_ID=$1
RUN_NAME=$2
REPO_DIR=$(cd "$(dirname "$0")/.." && pwd)
BUCKET=gs://cellens-ai-artifacts/arc3-duck
: "${ARC3_SITE_DIR:?set ARC3_SITE_DIR to the railway-linked arc3-site checkout}"

cd "$REPO_DIR"
mkdir -p "logs/$RUN_NAME"
gcloud storage rsync -r "$BUCKET/$RUN_GCS_ID/runs" "logs/$RUN_NAME"

grep -q "\"$RUN_NAME\"" scripts/export_runs_index.py \
  || { echo "ERROR: add a HARNESS entry for $RUN_NAME to scripts/export_runs_index.py first"; exit 1; }
python3 scripts/export_runs_index.py
python3 scripts/export_viewer_data.py "logs/$RUN_NAME"

git add "logs/$RUN_NAME" "docs/data/$RUN_NAME" docs/data/runs-index.json scripts/export_runs_index.py
git commit -m "Publish run $RUN_NAME"
git push origin main
SHA=$(git rev-parse --short HEAD)

# Pull the new run dir + refreshed index from the public repo into the volume.
cd "$ARC3_SITE_DIR"
railway ssh "sh -c \"wget -q -O- https://codeload.github.com/sonpham-org/arc-3/tar.gz/$SHA | tar -xz --strip-components=3 -C /srv/data arc-3-$SHA/docs/data/$RUN_NAME arc-3-$SHA/docs/data/runs-index.json && echo VOLUME-UPDATED\""

curl -sf "https://arc3.sonpham.net/data/$RUN_NAME/run-overview.json" -o /dev/null \
  && echo "LIVE: https://arc3.sonpham.net (run $RUN_NAME)" \
  || { echo "ERROR: run not served after volume update"; exit 1; }
