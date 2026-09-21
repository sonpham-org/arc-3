#!/usr/bin/env bash
# Author: Claude Opus 5 (Bubba)
# Date: 21-September-2026
# PURPOSE: Streamer-persona arm. Same two games (sk48, bp35), same box, same warm LM Studio
# endpoint, same board image attached, same decoding and budgets as run_two_games_image_local.sh.
# The ONLY difference is ARC3_PERSONA=streamer, which swaps the opening sentences of the system
# prompt for the Boss's Gen Z Twitch streamer framing. Control arm is the unset default, which
# renders byte-identical to the committed prompt.
# SRP/DRY check: Pass -- delegates every shared setting to the same launcher by sourcing its
# env conventions; only the persona flag and run name differ.

set -euo pipefail

REPO="$HOME/GitHub/arc-3"
INF="$REPO/ARC3-Inference"
ENVDIR="$HOME/GitHub/arc-explainer/external/ARCEngine/environment_files"
RUNS="$HOME/bubba-workspace/arc3-sft/runs"

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

export MULTIMODAL_CONTEXT="current_grid"
export MULTIMODAL_UPSCALE="4"

# The whole arm.
export ARC3_PERSONA="streamer"

RUN_NAME="${1:-20260921_boss-prompt-two-games-mini-STREAMER}"

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
