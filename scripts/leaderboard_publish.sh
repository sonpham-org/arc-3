#!/bin/bash
# Every-30-minutes job: save the Kaggle leaderboard and push the data to main.
# Runs from its own clone (~/.cache/arc3-leaderboard-bot) so it never touches a working checkout.
set -euo pipefail
export PATH="/Users/macmini/.local/bin:/opt/homebrew/bin:/usr/bin:/bin"
cd "$(dirname "$0")/.."
git pull -q --rebase --autostash origin main
out=$(python3.13 scripts/leaderboard_snapshot.py)
echo "$out"
echo "$out" | grep '^ALERT ' | while read -r _ msg; do
  osascript -e "display notification \"${msg//\"/}\" with title \"ARC-3 leaderboard\"" || true
done || true   # no ALERT lines makes grep exit 1, which set -e/pipefail turned into a silent stop before the commit
git add docs/static/data/leaderboard
if git diff --cached --quiet; then exit 0; fi
git commit -q -m "Leaderboard snapshot $(date -u +%Y-%m-%dT%H:%MZ)"
git pull -q --rebase --autostash origin main
git push -q origin HEAD:main
