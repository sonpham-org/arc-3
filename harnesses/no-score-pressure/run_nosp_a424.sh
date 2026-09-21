#!/usr/bin/env bash
# Author: Claude Opus 5 (Bubba subagent, label no-score-pressure-wide)
# Date: 21-September-2026
# PURPOSE: Run one arm of the no-score-pressure wide experiment on gx10-a424 across all 25
# public duck games against the BF16 Qwen3.8-27B served by serve_nosp_a424.sh.
#   ARM=stripped -> system prompt with the four scoring/HUD bullets removed and the opening
#                   line reframed as a player playing a video game.
#   ARM=control  -> clean repo-HEAD system prompt, unmodified.
# The prompt is the ONLY variable between the two arms: same tree, same server, same seed,
# same explicit game list in the same order, same lane count, same wall.
#
# The explicit --game list (rather than letting the harness enumerate) is deliberate: if an arm
# is truncated, the completed games still line up pairwise with the other arm.
#
# ARC3_ORACLE_RULES_DIR is explicitly unset. This tree was copied from the sk48 overfit arm,
# whose oracle injection activates off that variable; a leaked export would hand BOTH arms the
# sk48 answer key. Run dirs deliberately do NOT carry "-oracle-": this arm is not an oracle arm
# and must stay eligible for SFT extraction.
# SRP/DRY check: Pass -- reuses the in-tree run CLI and the established serve script. Nothing
# here reimplements harness behaviour.
set -euo pipefail

ROOT=/home/son/arc3-nosp
INF="$ROOT/ARC3-Inference"
ENVDIR=/home/son/GitHub/arc-3/environment_files
RUNS="$ROOT/runs"
ARM=${ARM:?set ARM=stripped or ARM=control}
LANES=${LANES:-16}
WALL=${WALL:-90}

GAMES="ar25-0c556536,bp35-0a0ad940,cd82-fb555c5d,cn04-2fe56bfb,dc22-fdcac232,ft09-0d8bbf25,g50t-5849a774,ka59-38d34dbb,lf52-271a04aa,lp85-305b61c3,ls20-9607627b,m0r0-492f87ba,r11l-495a7899,re86-8af5384d,s5i5-18d95033,sb26-7fbdac44,sc25-635fd71a,sk48-d8078629,sp80-589a99af,su15-1944f8ab,tn36-ef4dde99,tr87-cd924810,tu93-0768757b,vc33-5430563c,wa30-ee6fef47"

# Install the prompt variant for this arm and record exactly what went in.
cp "$ROOT/variants/prompts.$ARM.py"    "$INF/inference/agent/prompts.py"
cp "$ROOT/variants/tool_agent.$ARM.py" "$INF/inference/agent/tool_agent.py"
echo "ARM=$ARM installed:"
md5sum "$INF/inference/agent/prompts.py" "$INF/inference/agent/tool_agent.py"
grep -n "You are" "$INF/inference/agent/tool_agent.py" | grep -i "puzzle game\|video game"

unset ARC3_ORACLE_RULES_DIR
export LOCAL_ANALYZER_BASE_URL="http://127.0.0.1:1234/v1"
export LOCAL_ANALYZER_MODEL_ID="qwen/qwen3.8-27b"
export LOCAL_ANALYZER_PROVIDER="vllm"
export LOCAL_ANALYZER_API_KEY="${LOCAL_ANALYZER_API_KEY:-EMPTY}"
export LOCAL_ANALYZER_CONTEXT_WINDOW="49152"

RUN_NAME="20260921_nosp-a424-bf16-${ARM}"
mkdir -p "$RUNS"
cd "$INF"
exec .venv/bin/python -m inference.framework.run \
  --game "$GAMES" \
  --model "qwen/qwen3.8-27b" \
  --environments-dir "$ENVDIR" \
  --experiments-dir "$RUNS" \
  --run-name "$RUN_NAME" \
  --n-passes 1 \
  --concurrent-jobs "$LANES" \
  --max-runtime-minutes "$WALL" \
  --timeout 900 \
  --deployment-target inline \
  --save-request-logs
