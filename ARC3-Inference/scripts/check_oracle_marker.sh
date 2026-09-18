#!/usr/bin/env bash
# Author: Claude Opus 5 (Bubba subagent)
# Date: 18-September-2026
# PURPOSE: Treatment-marker guard for the oracle test (docs/plans/2026-09-18-oracle-test-plan.md
#   section 6 step 2). Counts the games whose prompt log carries the injected rulebook block, the
#   same way run_style_multipass.sh counts `Reasoning style (MANDATORY)` for the compact-reasoning
#   arms. Expect one per game in arm O (7 on the amended slippery-seven run) and 0 in arm B. A
#   missing `export ARC3_ORACLE_RULES_DIR` on one of four launches is the single most likely way
#   this experiment produces a confidently wrong number, so it is checked every pass.
#
#   Counts FILES, not occurrences: tool_agent writes prompts/<game>.log with mode "w", so the file
#   holds the latest turn's full message list and the re-sent block appears once per retained user
#   turn by design. The per-file occurrence figure is reported for eyeballing, not asserted on.
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

echo "oracle_marker: games_with_treatment=$MARK expected=$EXPECT prompt_logs=$LOGS max_occurrences_in_one_log=${MAXOCC:-0}"

if [ "$MARK" != "$EXPECT" ]; then
    echo "oracle_marker: FAIL -- $MARK of $LOGS prompt logs carry the rulebook, expected $EXPECT" >&2
    exit 1
fi
# More than one copy in a log means the block is being retained in history instead of stripped
# on the way in (_persistent_history_messages), which would cost arm O ~1,900 tokens per
# retained turn and leave it holding less real history than arm B -- a second difference
# between the arms. This is the only signal that catches it on pass 1, so it fails, not warns.
if [ "${MAXOCC:-0}" -gt 1 ]; then
    echo "oracle_marker: FAIL -- a prompt log carries the rulebook ${MAXOCC} times; expected at most 1" >&2
    exit 1
fi
echo "oracle_marker: PASS"
