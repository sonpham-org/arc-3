#!/usr/bin/env bash
# Author: Claude Opus 5 (Bubba subagent, label no-score-pressure-wide)
# Date: 21-September-2026
# PURPOSE: Serve the stock BF16 Qwen3.8-27B on gx10-a424 for the no-score-pressure wide arm.
# Derives from arc3-sk48-overfit/serve_a424.sh: same single-instance guard intent, same seed 0,
# same qwen3 reasoning parser, same hermes tool-call parser (the pairing verified working against
# the current-HEAD harness on this box earlier today). Serving flags are raised toward the
# round-4W baseline protocol (gpu-util 0.85, prefix caching ON) because the sk48 settings
# (0.62 util, caching OFF, 4 seqs) were the reason that arm decoded at ~2 tok/s and could not
# finish. Prefix caching matters here: the harness resends a long system prompt every turn.
# SRP/DRY check: Pass -- this only pins serving flags. Harness behaviour is untouched upstream code.
set -euo pipefail
MODEL_DIR=${MODEL_DIR:-/home/son/models/Qwen3.8-27B-BF16}
PORT=${PORT:-1234}
LOG=${LOG:-/home/son/arc3-nosp/vllm-nosp.log}

# Single-instance guard: refuse to start a second server on this port.
if ss -ltn | grep -q ":${PORT} "; then
  echo "ABORT: port ${PORT} already in use; a server is already running." >&2
  exit 1
fi
if pgrep -f "vllm[ ]serve" >/dev/null 2>&1; then
  echo "ABORT: a vllm serve process already exists." >&2
  exit 1
fi

exec /home/son/venv/bin/vllm serve "$MODEL_DIR" \
  --served-model-name qwen/qwen3.8-27b \
  --host 127.0.0.1 --port "$PORT" \
  --max-model-len 49152 \
  --gpu-memory-utilization 0.85 \
  --max-num-seqs 32 \
  --seed 0 \
  --enable-prefix-caching \
  --reasoning-parser qwen3 \
  --enable-auto-tool-choice --tool-call-parser hermes \
  > "$LOG" 2>&1
