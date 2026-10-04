#!/bin/bash
# Every-30-minutes job: save the Kaggle leaderboard and push the data to main.
# Runs from its own clone (~/.cache/arc3-leaderboard-bot) so it never touches a working checkout.
set -euo pipefail
export PATH="/Users/macmini/.local/bin:/opt/homebrew/bin:/usr/bin:/bin"
cd "$(dirname "$0")/.."
git pull -q --rebase origin main
python3.13 scripts/leaderboard_snapshot.py
git add docs/static/data/leaderboard
if git diff --cached --quiet; then exit 0; fi
git commit -q -m "Leaderboard snapshot $(date -u +%Y-%m-%dT%H:%MZ)"
git pull -q --rebase origin main
git push -q origin HEAD:main
