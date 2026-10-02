#!/bin/bash
# Upload gcp/controllers/rl (+ the shared Firestore/observer helpers + frontier.json) to
# gs://cellens-ai-artifacts/arc3-rl/code/<sha>/ and print the sha (the trainer VM's jobs copy code from there).
#   RL_WORK=D:/codex-work/rl-20261001 bash ops/push_code.sh
set -e
export CLOUDSDK_PYTHON='C:\python312\python.exe'
RL=$(cd "$(dirname "$0")/.." && pwd)
WORK=${RL_WORK:-/d/codex-work/rl-20261001}
STAGE=$(mktemp -d)
cp "$RL"/*.py "$STAGE"/ && cp "$RL"/../../arc3_firestore_scores.py "$RL"/../../arc3_minute_score_observer.py "$STAGE"/
cp "$WORK"/frontier.json "$STAGE"/
SHA=$(cat "$STAGE"/*.py | sha256sum | cut -c1-12)
gcloud storage cp "$(cygpath -w "$STAGE")\*" "gs://cellens-ai-artifacts/arc3-rl/code/$SHA/" > /dev/null 2>&1
echo "$SHA" > "$WORK"/code-sha.txt
rm -rf "$STAGE"
echo "$SHA"
