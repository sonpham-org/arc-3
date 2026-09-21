#!/usr/bin/env bash
# Author: Claude Opus 5 (Bubba subagent)
# Date: 21-September-2026
# PURPOSE: Launch the deliberately-overfit sk48 arm entirely on the Mac Mini (M4 Pro, 64GB):
# stock Qwen3.8-27B-MLX-4bit served by LM Studio's OpenAI-compatible endpoint, the local
# ARCEngine environment_files build of sk48 played in-process by ARC3-Inference's solver, and
# the Boss's own sk48 write-up injected into every user turn through the existing oracle-rules
# mechanism (inference/agent/oracle_rules.py, ARC3_ORACLE_RULES_DIR).
#
# This is NOT a benchmark arm. It is demonstration/RL-trace generation: the model is told the
# game's name and its full mechanics up front, which is exactly the variable a benchmark holds
# out. Its score is not comparable to the a108 baseline arms.
#
# The run dir carries "-oracle-" on purpose: distill/extract_sft.py refuses such a dir with
# exit 2 and no override (ARC3-Inference/distill/README.md), because these transcripts contain
# the answer key. That fence is intended, not worked around.
#
# SRP/DRY check: Pass -- reuses the in-tree oracle injection, the in-tree run.py CLI and the
# in-tree ARCEngine environment loader. Nothing here reimplements harness behaviour; it only
# pins the endpoint, the budget and the paths for this one local arm.

set -euo pipefail

REPO="$HOME/GitHub/arc-3"
INF="$REPO/ARC3-Inference"
ENVDIR="$HOME/GitHub/arc-explainer/external/ARCEngine/environment_files"
RUNS="$HOME/bubba-workspace/arc3-sft/runs"

# The overfit treatment. Gitignored (datasets/explainer-games/ is a cache of arc-explainer),
# so the writeup quotes it verbatim for reproducibility.
export ARC3_ORACLE_RULES_DIR="$REPO/datasets/explainer-games/rulebooks-sk48-overfit"

# LM Studio, OpenAI-compatible. Tool calling verified with scripts/smoke_tool_call.py.
export LOCAL_ANALYZER_BASE_URL="http://127.0.0.1:1234/v1"
export LOCAL_ANALYZER_MODEL_ID="qwen/qwen3.8-27b"
export LOCAL_ANALYZER_PROVIDER="vllm"

# LM Studio serves this model at 208,384 context. 49,152 leaves room for the ~3.2K-token
# injected block plus the upscaled frame image on every turn while keeping prefill cheap on
# an M4 Pro, where generation measured ~12 tok/s.
export LOCAL_ANALYZER_CONTEXT_WINDOW="49152"

# Bound the per-action analysis loop. The default is 12 tool steps with unbounded output, which
# on this box spent 23 minutes and 4 requests on action 1 without ever calling action(...) --
# measured in run 20260921_162713_*, kept as the untuned-pace evidence. 3 steps at 3,000 output
# tokens is the difference between a reachable level-1 clear and a pre-determined null.
# Capping thinking is also aligned with the overfit hypothesis rather than a compromise of it:
# a model handed the mechanics should not need 16,000 characters re-deriving them.
export LOCAL_ANALYZER_TOOL_STEPS="3"
export LOCAL_ANALYZER_MAX_OUTPUT="7000"

RUN_NAME="20260921_sk48-overfit-oracle-local-mlx-bounded2"

cd "$INF"
exec .venv/bin/python -m inference.framework.run \
  --game sk48 \
  --model "qwen/qwen3.8-27b" \
  --environments-dir "$ENVDIR" \
  --experiments-dir "$RUNS" \
  --run-name "$RUN_NAME" \
  --n-passes 1 \
  --concurrent-jobs 1 \
  --max-runtime-minutes 240 \
  --timeout 1800 \
  --deployment-target inline \
  --save-request-logs
