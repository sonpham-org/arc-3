#!/bin/bash
# Every-30-minutes job: save the Kaggle leaderboard and send it to ARC Explainer's public page
# (https://arc.markbarney.net/kaggle-leaderboard). Runs from its own clone (~/.cache/arc3-leaderboard-bot);
# the pull only picks up script changes. Since 05-Oct-2026 the data stays out of git, in
# $LEADERBOARD_DATA_DIR, so the job no longer commits a snapshot to arc-3 every half hour.
set -euo pipefail
export PATH="/Users/macmini/.local/bin:/opt/homebrew/bin:/usr/bin:/bin"
export LEADERBOARD_DATA_DIR="${LEADERBOARD_DATA_DIR:-$HOME/.cache/arc3-leaderboard-data}"
cd "$(dirname "$0")/.."
git pull -q --rebase --autostash origin main || echo "git pull failed; running the scripts already here"
out=$(python3.13 scripts/leaderboard_snapshot.py)
echo "$out"
echo "$out" | grep '^ALERT ' | while read -r _ msg; do
  osascript -e "display notification \"${msg//\"/}\" with title \"ARC-3 leaderboard\"" || true
done || true   # no ALERT lines makes grep exit 1, which set -e/pipefail would turn into a silent stop
python3.13 scripts/leaderboard_push_explainer.py || true   # never blocks the save
