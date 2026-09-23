#!/usr/bin/env bash
# Author: Claude Opus 5 (Bubba subagent)
# Date: 21-September-2026
# PURPOSE: Launch the sk48 "act-first" diagnostic arm on the Mac Mini. Four prior sk48 oracle
# runs produced zero game actions: the model measured the board every turn and never committed
# a move. sk48 has nothing worth measuring -- the rod moves a fixed amount per press, the board
# is fully visible, there is no randomness -- so this arm forces experiment-first for the
# opening ten actions and only then restores thinking, to see whether the model can read what
# its own moves did.
#
# This is a DIAGNOSTIC PROBE, not a controlled comparison. It changes three things at once
# (act-first phase, efficiency pressure removed, player framing) on purpose.
#
# The run dir keeps "-oracle-" so distill/extract_sft.py refuses it with exit 2: these
# transcripts carry the sk48 answer key. That fence is intended, not worked around.
#
# SRP/DRY check: Pass -- reuses the oracle injection, run.py CLI and ARCEngine loader from the
# sk48-overfit arm unchanged; only the act-first env knobs and the run name are new.

set -euo pipefail

REPO="$HOME/GitHub/arc-3"
INF="$REPO/ARC3-Inference"
ENVDIR="$HOME/GitHub/arc-explainer/external/ARCEngine/environment_files"
RUNS="$HOME/bubba-workspace/arc3-sft/runs"

# UNCHANGED from the sk48-overfit arm: the Boss's own sk48 write-up, injected every user turn.
export ARC3_ORACLE_RULES_DIR="$REPO/datasets/explainer-games/rulebooks-sk48-overfit"

# UNCHANGED: the already-warm LM Studio endpoint. Do not load a second copy of the model.
export LOCAL_ANALYZER_BASE_URL="http://127.0.0.1:1234/v1"
export LOCAL_ANALYZER_MODEL_ID="qwen/qwen3.8-27b"
export LOCAL_ANALYZER_PROVIDER="vllm"
export LOCAL_ANALYZER_CONTEXT_WINDOW="49152"
export LOCAL_ANALYZER_MAX_OUTPUT="10000"

# Default (post-phase) probe budget. The act-first phase overrides this to 1 probe + 1 retry
# for actions 1-10, then the agent reverts to this so it can study its own moves.
export LOCAL_ANALYZER_TOOL_STEPS="12"

# The act-first phase itself.
export ARC3_ACT_FIRST_ACTIONS="10"
export ARC3_ACT_FIRST_PROBES="1"
export ARC3_ACT_FIRST_MAX_STALL="6"

RUN_NAME="20260921_sk48-act-first-oracle-local-mlx-r4"

cd "$INF"
exec .venv/bin/python -m inference.framework.run \
  --game sk48 \
  --model "qwen/qwen3.8-27b" \
  --environments-dir "$ENVDIR" \
  --experiments-dir "$RUNS" \
  --run-name "$RUN_NAME" \
  --n-passes 1 \
  --concurrent-jobs 1 \
  --max-actions 15 \
  --max-runtime-minutes 110 \
  --timeout 1800 \
  --deployment-target inline \
  --save-request-logs
