#!/usr/bin/env bash
# Author: Claude Opus 5 (Bubba sub-agent, label arc3-lora-round2)
# Date: 18-September-2026
# PURPOSE: Run the round-2 held-out evaluation (base vs round-1 vs round-2 vs the round-2
# checkpoint ladder) on gx10-a424, waiting first for the round-3 TRAINING job to exit.
# It waits rather than killing for the same reason round 3's own launcher waited for round 2:
# GB10 memory is unified, a 27B BF16 load is ~54 GiB of weights, and round 3 is already
# holding 65.87 GiB peak -- two loads do not fit and the kernel OOM killer takes whichever it
# likes. That is not hypothetical here: the first attempt at this eval was launched inside
# round 3's own 120s settle window on 18-Sep and was kernel-OOM-killed during load (pid
# 1023047, "Out of memory: Killed process 1023047 (python)"), with no Python traceback --
# a silent death that looks like a crash and is not one. Round 3 is a 178-step run of a
# different experiment; killing it to reclaim the GPU would destroy ~5 h of another agent's
# work to save this script a wait.
# SRP/DRY check: Pass - distill/eval_lora.py owns the evaluation and is invoked, not
# reimplemented. This is the launch line plus the GPU-exclusion gate, modelled on
# arc3-round3/run_lora_round3.sh so there is one queue pattern on this box, not two.
set -u

WAIT_PID=${WAIT_PID:-1023305}                    # round 3 training
SRC=${SRC:-/home/son/arc3-round1/src/ARC3-Inference}
PY=${PY:-/home/son/arc3-train-venv/bin/python}
CORPUS=${CORPUS:-/home/son/arc3-round1/data/sft_heldout.jsonl}
OUT=${OUT:-/home/son/arc3-round2/eval/eval2.json}
LOG=${LOG:-/home/son/arc3-round2/eval/eval2.log}
LEDGER=${LEDGER:-/home/son/arc3-round2/eval/queue.log}
R3LOG=${R3LOG:-/home/son/arc3-round3/train.log}
SETTLE=${SETTLE:-180}

mkdir -p "$(dirname "$OUT")"
say(){ echo "$(date -Iseconds) $*" >> "$LEDGER"; }

say "QUEUE START pid=$$ waiting_on=$WAIT_PID (round3 training) target=$OUT"
# `wait` is not usable: $WAIT_PID is not this shell's child.
while kill -0 "$WAIT_PID" 2>/dev/null; do sleep 60; done
say "round3 pid $WAIT_PID exited; its last step line: $(grep '^== STEP' "$R3LOG" 2>/dev/null | tail -1)"

# Longer settle than round 3 used (180s vs 120s): the 18-Sep collision happened precisely
# because a second process allocated inside the first one's settle window.
say "settling ${SETTLE}s before allocating (gpu_util=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader 2>/dev/null | tr -d ' '))"
sleep "$SETTLE"

# Refuse to start if ANY other 27B job is holding the GPU -- training or evaluation. Guarding
# only against train_lora.py is what let the 18-Sep collision happen in the first place: both
# jobs correctly checked that TRAINING was clear and neither could see a non-training load.
# The queue pattern is now established on this box and more than one agent uses it, so a second
# queued eval is a live possibility, not a hypothetical.
#
# A collision costs a DELAY, not the run: on a hit, go back to waiting instead of exiting.
# Exiting would turn a 60-second overlap into a lost evaluation.
guard_hit(){ pgrep -f 'distill/(train_lora|eval_lora)\.py' 2>/dev/null | grep -v "^$$\$" | head -1; }
tries=0
while :; do
  hit=$(guard_hit)
  [ -z "$hit" ] && break
  tries=$((tries+1))
  say "HOLD another 27B job is running (pid $hit: $(ps -o cmd= -p "$hit" 2>/dev/null | cut -c1-90)); re-arming, attempt $tries"
  if [ "$tries" -ge 240 ]; then say "ABORT still blocked after $tries checks (~4h); giving up"; exit 1; fi
  sleep 60
done
say "GPU clear; proceeding"

cd "$SRC" || { say "ABORT cannot cd $SRC"; exit 1; }
say "LAUNCH eval2"
"$PY" -u distill/eval_lora.py \
  --corpus "$CORPUS" \
  --adapter round1=/home/son/arc3-round1/ckpt/adapter \
  --adapter round2=/home/son/arc3-round2/ckpt/adapter \
  --adapter round2-step8=/home/son/arc3-round2/ckpt/adapter-step8 \
  --adapter round2-step16=/home/son/arc3-round2/ckpt/adapter-step16 \
  --adapter round2-step32=/home/son/arc3-round2/ckpt/adapter-step32 \
  --adapter round2-step48=/home/son/arc3-round2/ckpt/adapter-step48 \
  --subset-arm round2-step8 --subset-arm round2-step16 \
  --subset-arm round2-step32 --subset-arm round2-step48 --subset-n 12 \
  --out "$OUT" --gen-tokens 96 \
  > "$LOG" 2>&1
say "eval2 END rc=$?"
