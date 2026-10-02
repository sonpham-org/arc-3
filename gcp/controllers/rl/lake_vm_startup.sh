#!/bin/bash
# Trace lake backfill VM (design: docs/plans/2026-10-01-arc3-trace-lake.md §7 A+B). CPU, Debian 12.
# Metadata: rl-code (gs:// code dir). Reuses /opt/rl/venv when the disk already has it (the G0 VM).
# Output: Firestore lake_episodes / lake_levels / lake_harnesses / lake_policies; gs://.../arc3-lake/v1/ episodes+blobs;
#         logs at gs://cellens-ai-artifacts/arc3-lake/v1/_backfill/. Powers off at the end.
set -uo pipefail
exec > >(tee -a /var/log/lake.log) 2>&1
md() { curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
CODE=$(md rl-code)
OUT=gs://cellens-ai-artifacts/arc3-lake/v1/_backfill
echo "start $(date -u +%FT%TZ) code=$CODE"
mkdir -p /opt/rl/out && cd /opt/rl
gcloud storage cp "$CODE/*" /opt/rl/
if [ ! -x venv/bin/python ]; then
  apt-get update -y -q && apt-get install -y -q python3-venv python3-pip >/dev/null
  python3 -m venv venv
fi
. venv/bin/activate
python -c "import transformers" 2>/dev/null || pip install -q --no-cache-dir "transformers==5.18.0"
python test_rl_core.py 2>&1 | tail -2
python test_lake.py 2>&1 | tail -2
python lake_backfill.py index --out /opt/rl/out/lake-index > /opt/rl/out/lake-index.log 2>&1; echo "index exit $?"
gcloud storage cp /opt/rl/out/lake-index.log "$OUT/" ; gcloud storage cp -r /opt/rl/out/lake-index "$OUT/"
python lake_backfill.py episodes \
  --runs daniel-base-a-1001,daniel-base-b-1001,daniel-noborder-c-1001,daniel-noborder-d-1001 \
  --root gs://cellens-ai-artifacts/arc3-duck/daniel-base/runs --harness-label daniel-nb-v1 \
  --policy-json '{"base": "intel-qwen3.8-flash-next-w4a16-autoround", "prune": null, "corrector": null, "draft": "albucino-qwen3-8-flash-next-drafter", "adapter": null, "temperature": "notebook", "top_p": null, "top_k": null}' \
  --stage /opt/rl/lake > /opt/rl/out/lake-episodes.log 2>&1; echo "episodes exit $?"
gcloud storage cp /opt/rl/out/lake-episodes.log /var/log/lake.log "$OUT/"
echo "done $(date -u +%FT%TZ)" | gcloud storage cp - "$OUT/DONE-$(basename $CODE)"
poweroff
