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

# Sampling, pinned by the Boss 21-Sep-2026. Previously we sent temperature/top-p/top-k from the
# harness defaults, sent no min-p at all (so the server's own default applied), and sent no seed,
# which left every Mini arm differing by sampling noise as well as by prompt.
export LOCAL_ANALYZER_TEMPERATURE="0.9"
export LOCAL_ANALYZER_TOP_P="1.0"
export LOCAL_ANALYZER_TOP_K="500"
export LOCAL_ANALYZER_MIN_P="0"
export LOCAL_ANALYZER_SEED="0"

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
