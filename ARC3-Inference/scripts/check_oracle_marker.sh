#!/usr/bin/env bash
# Author: Claude Opus 5 (Bubba subagent)
# Date: 18-September-2026
# PURPOSE: Treatment-marker guard for the oracle test (docs/plans/2026-09-18-oracle-test-plan.md
#   section 6 step 2). Two separate questions, measured on two separate artifacts:
#
#   1. TREATMENT (the export check). Did this pass actually run the arm it claims? Counts the
#      prompt-log FILES carrying the injected rulebook: expect one per game in arm O (7 on the
#      amended slippery-seven run) and 0 in arm B. A missing `export ARC3_ORACLE_RULES_DIR` on
#      one of four launches is the single most likely way this experiment produces a confidently
#      wrong number, so it is checked every pass, in flight and at the end.
#
#   2. RETENTION (the confound check). Is the block being left in the retained history instead of
#      stripped on the way in (_persistent_history_messages)? That would cost arm O ~1,900 tokens
#      per retained turn and leave it holding less real history than arm B -- a SECOND difference
#      between the arms, which would make a null result uninterpretable. Measured per REQUEST over
#      <run>/*_requests.jsonl, which is the actual wire message list sent to vLLM, one JSON line
#      per request. More than one copy in one request's message list is that bug, and fails.
#
#   WHY NOT grep -c OVER THE PROMPT LOG. The prompt log is not a rendered prompt. tool_agent's
#   _write_prompt_log_snapshot writes `[MODEL INPUT]` (the message list) AND `[TURN TRANSCRIPT SO
#   FAR]`, which re-prints the same turn's `[USER PROMPT]` once per analysis step of the current
#   turn. So an arm-O log holds `1 + analysis_steps` copies -- a FLOOR of 2, always, with a correct
#   single-copy injection. The 18-Sep abort (P2 of the first launch, run 20260918_174825) was
#   exactly this: all seven logs read 2, while every one of the seven `*_requests.jsonl` first
#   requests read `message_count: 2` and exactly one copy, in the user message. The occurrence
#   figure is still printed below, for eyeballing, and is NOT asserted on.
#
# Usage: check_oracle_marker.sh <run-dir> <expected-games>   # e.g. ... /path/run-oracle-p0 7
# SRP/DRY check: Pass -- the compact-reasoning marker guard is inline in run_style_multipass.sh and
#   hardcodes its own marker; this is the oracle marker and is a separate arm's guard.
set -euo pipefail

DIR="${1:?usage: check_oracle_marker.sh <run-dir> <expected-games>}"
EXPECT="${2:?usage: check_oracle_marker.sh <run-dir> <expected-games>}"
MARKER="Rules of this game, from a verified source."

if [ ! -d "$DIR/prompts" ]; then
    echo "oracle_marker: NO prompts/ directory under $DIR" >&2
    exit 1
fi

# `grep` exits 1 when nothing matches, which is the EXPECTED result for arm B. Under
# `set -euo pipefail` that would abort the guard on its passing case, so each count
# tolerates the no-match exit explicitly.
LOGS=$(ls -1 "$DIR"/prompts/* 2>/dev/null | wc -l | tr -d ' ')
MARK=$( { grep -l "$MARKER" "$DIR"/prompts/* 2>/dev/null || true; } | wc -l | tr -d ' ')
MAXOCC=$( { grep -c "$MARKER" "$DIR"/prompts/* 2>/dev/null || true; } | cut -d: -f2 | sort -n | tail -1)

echo "oracle_marker: games_with_treatment=$MARK expected=$EXPECT prompt_logs=$LOGS log_occurrences_max=${MAXOCC:-0} (log_occurrences is 1+analysis_steps by construction; not asserted)"

# Retention, on the wire message lists. Reported before the treatment verdict so a failing pass
# shows both numbers in the ledger rather than only the first one to trip.
RETENTION=$(python3 - "$DIR" "$MARKER" <<'PY'
import glob, json, os, sys

run_dir, marker = sys.argv[1], sys.argv[2]
paths = sorted(glob.glob(os.path.join(run_dir, "*_requests.jsonl")))
if not paths:
    print("requests_files=0 SKIPPED -- no *_requests.jsonl yet; retention unmeasured")
    raise SystemExit(0)

worst = 0            # most copies in any single request's message list
worst_where = ""
zero_requests = 0    # requests carrying no copy at all (arm B: all of them)
total = 0
for path in paths:
    with open(path, encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                # A request being written as the guard reads it. The final check re-reads.
                continue
            total += 1
            copies = 0
            for message in record.get("messages") or []:
                content = message.get("content")
                if not isinstance(content, str):
                    content = json.dumps(content, ensure_ascii=True)
                copies += content.count(marker)
            if copies == 0:
                zero_requests += 1
            if copies > worst:
                worst, worst_where = copies, f"{os.path.basename(path)}:{line_no}"

print(
    f"requests_files={len(paths)} requests={total} "
    f"max_copies_in_one_request={worst} requests_with_zero_copies={zero_requests}"
    + (f" worst_at={worst_where}" if worst > 1 else "")
)
if worst > 1:
    raise SystemExit(3)
PY
) || RC=$?
RC=${RC:-0}
echo "oracle_marker: $RETENTION"

if [ "$RC" -eq 3 ]; then
    echo "oracle_marker: FAIL -- a single request's message list carries the rulebook more than once;" >&2
    echo "oracle_marker:         the block is being retained in history instead of stripped." >&2
    exit 1
fi
if [ "$RC" -ne 0 ]; then
    echo "oracle_marker: FAIL -- retention check errored (rc=$RC)" >&2
    exit 1
fi

if [ "$MARK" != "$EXPECT" ]; then
    echo "oracle_marker: FAIL -- $MARK of $LOGS prompt logs carry the rulebook, expected $EXPECT" >&2
    exit 1
fi
echo "oracle_marker: PASS"
