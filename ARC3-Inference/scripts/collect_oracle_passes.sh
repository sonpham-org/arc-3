#!/usr/bin/env bash
# Author: Claude Opus 5 (Bubba sub-agent, label arc3-oracle-driver-and-launch)
# Date: 18-September-2026
# PURPOSE: Read-side companion to run_oracle_multipass.sh. Prints the driver's guard ledger and,
# per banked pass, the per-game level clears and final score from benchmark.json, in the shape
# docs/plans/2026-09-18-oracle-test-plan.md section 4 requires: paired per game, level clears
# first and score second, and NO arm totals. Section 4 forbids arm totals and calls a single
# pass not a result, so this script refuses to sum across games or across passes -- the
# aggregation, when there is enough of it to aggregate, is scripts/multipass_compare.py's job.
# SRP/DRY check: Pass - multipass_compare.py does the paired statistics for a finished
# experiment; this is the in-flight "what has landed so far" reader and computes no statistic.
set -u
WORK=${WORK:-$HOME/arc3-oracle-20260918}
INF=${INF:-$HOME/GitHub/arc-3/ARC3-Inference}

echo "=== guard ledger: $WORK/guards/ledger.txt ==="
cat "$WORK/guards/ledger.txt" 2>/dev/null || echo "(no ledger yet)"

echo
echo "=== per-game results, per banked pass (no totals, by design) ==="
for B in "$WORK"/banked/*; do
  [ -f "$B" ] || continue
  LBL=$(basename "$B"); DIR=$(cat "$B")
  echo "--- $LBL  $DIR"
  python3 - "$DIR" <<'PY'
import json,sys
from pathlib import Path
f=Path(sys.argv[1])/"benchmark.json"
if not f.exists():
    print("  (no benchmark.json yet)"); raise SystemExit
b=json.loads(f.read_text())
for r in b.get("game_runs") or []:
    code=str(r.get("game_id","?")).split("-")[0]
    lv=r.get("levels_completed"); nl=r.get("number_of_levels")
    print("  %-6s levels_cleared=%s/%s  score=%s  state=%s  wall=%s" % (
        code, lv, nl, r.get("final_score"), r.get("state"),
        r.get("final_wallclock_seconds")))
PY
done

echo
echo "=== live check: is a pass running now? ==="
pgrep -af "inference-taaf-run" | head -5 || echo "(no harness process)"
echo "vllm 765547: $(ps -o etime= -p 765547 2>/dev/null | tr -d ' ' || echo DEAD) health=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:1234/health)"
