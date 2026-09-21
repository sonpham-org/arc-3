#!/usr/bin/env bash
# Author: Claude Opus 5 (Bubba)
# Date: 21-September-2026
# PURPOSE: Run the Boss's two chosen games (Skewer Kebabs sk48, Buoyant Pontoons bp35) on the
# Mac Mini against the warm LM Studio endpoint, using the Boss's rewritten system prompt, with
# the board image attached (MULTIMODAL_CONTEXT=current_grid) so the model reads the picture
# instead of measuring ASCII. No rulebook/oracle injection: this is the plain model on the
# plain prompt. Detached via setsid+nohup so an agent session ending cannot kill the run --
# that is exactly how the first attempt died after one turn per game.
# SRP/DRY check: Pass -- reuses inference.framework.run and the act-first launcher's env
# conventions; only the game pair, multimodal flags and run name are new.

set -euo pipefail

REPO="$HOME/GitHub/arc-3"
INF="$REPO/ARC3-Inference"
ENVDIR="$HOME/GitHub/arc-explainer/external/ARCEngine/environment_files"
RUNS="$HOME/bubba-workspace/arc3-sft/runs"

# Plain model, plain prompt: no oracle rulebook, no act-first phase.
unset ARC3_ORACLE_RULES_DIR || true
unset ARC3_ACT_FIRST_ACTIONS || true
unset ARC3_ACT_FIRST_PROBES || true
unset ARC3_ACT_FIRST_MAX_STALL || true

export LOCAL_ANALYZER_BASE_URL="http://127.0.0.1:1234/v1"
export LOCAL_ANALYZER_MODEL_ID="qwen/qwen3.8-27b"
export LOCAL_ANALYZER_PROVIDER="vllm"
export LOCAL_ANALYZER_CONTEXT_WINDOW="49152"
export LOCAL_ANALYZER_MAX_OUTPUT="10000"
export LOCAL_ANALYZER_TOOL_STEPS="12"

# Sampling, pinned by the Boss 21-Sep-2026. Previously we sent temperature/top-p/top-k from the
# harness defaults, sent no min-p at all (so the server's own default applied), and sent no seed,
# which left every Mini arm differing by sampling noise as well as by prompt.
export LOCAL_ANALYZER_TEMPERATURE="0.9"
export LOCAL_ANALYZER_TOP_P="1.0"
export LOCAL_ANALYZER_TOP_K="500"
export LOCAL_ANALYZER_MIN_P="0"
export LOCAL_ANALYZER_SEED="0"

# The board picture goes in the prompt.
export MULTIMODAL_CONTEXT="current_grid"
export MULTIMODAL_UPSCALE="4"

RUN_NAME="${1:-20260921_boss-prompt-two-games-mini-IMAGE-r2}"

cd "$INF"
exec .venv/bin/python -m inference.framework.run \
  --game "sk48,bp35" \
  --model "qwen/qwen3.8-27b" \
  --environments-dir "$ENVDIR" \
  --experiments-dir "$RUNS" \
  --run-name "$RUN_NAME" \
  --n-passes 1 \
  --concurrent-jobs 2 \
  --max-runtime-minutes 60 \
  --timeout 1800 \
  --deployment-target inline \
  --save-request-logs
