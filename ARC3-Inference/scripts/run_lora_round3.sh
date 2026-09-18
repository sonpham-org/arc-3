#!/usr/bin/env bash
# Author: Claude Opus 5 (Bubba sub-agent, label arc3-oracle-driver-and-launch)
# Date: 18-September-2026
# PURPOSE: Launch LoRA round 3 on gx10-a424 against the WINDOWED human-demo corpus
# (PR #52, docs/trace-findings/2026-09-18-human-demos-to-sft.md), waiting first for the
# round-2 job to exit. It waits rather than killing because round 2 trains a DIFFERENT
# corpus -- 40 model-trace records from extract_sft.py, not an older cut of the human demos --
# and its own write-up (2026-09-18-arc3-lora-round2-heldout-eval.md) still has PLACEHOLDER
# results and says in section 7: "Never run training concurrently with another GPU job. GB10
# memory is unified; a second allocation invokes the kernel OOM killer and takes bystander
# processes with it." So the two cannot overlap, and killing a 3/4-finished run of a distinct
# experiment to start this one would destroy the result that doc is waiting for.
#
# Hyperparameters are round 2's, unchanged, so round 3 differs from round 2 in exactly one
# thing: the corpus. Only the checkpoint cadence is rescaled -- 89 records x 4 epochs / 2
# accum = 178 steps, so --save-every 24 / --census-every 12 reproduces round 2's ~7-checkpoint,
# 14-census ladder at the new step count.
# SRP/DRY check: Pass - distill/train_lora.py owns training and is invoked, not reimplemented;
# the round-2 doc's section 7 owns the launch line and this is that line plus the GPU-exclusion
# gate the same section demands. No other script waits on another job's pid.
set -u

WAIT_PID=${WAIT_PID:-935181}                     # round 2
SRC=${SRC:-/home/son/arc3-round1/src/ARC3-Inference}
PY=${PY:-/home/son/arc3-train-venv/bin/python}
CORPUS=${CORPUS:-/home/son/arc3-round3/data/sft_human_windowed.jsonl}
OUT=${OUT:-/home/son/arc3-round3/ckpt}
LOG=${LOG:-/home/son/arc3-round3/train.log}
LEDGER=${LEDGER:-/home/son/arc3-round3/queue.log}
R2LOG=${R2LOG:-/home/son/arc3-round2/train.log}
SETTLE=${SETTLE:-120}

mkdir -p "$OUT" "$(dirname "$LOG")"
say(){ echo "$(date -Iseconds) $*" >> "$LEDGER"; }

say "QUEUE START pid=$$ waiting_on=$WAIT_PID corpus=$CORPUS"
# `wait` is not usable: $WAIT_PID is not this shell's child.
while kill -0 "$WAIT_PID" 2>/dev/null; do sleep 60; done
say "round2 pid $WAIT_PID exited; its last step line: $(grep '^== STEP' "$R2LOG" 2>/dev/null | tail -1)"

# Unified memory: do not allocate the instant the other process disappears. Do NOT gate on
# nvidia-smi memory.used -- it reports [N/A] on this box.
say "settling ${SETTLE}s before allocating (gpu_util=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader 2>/dev/null | tr -d ' '))"
sleep "$SETTLE"

cd "$SRC" || { say "ABORT cannot cd $SRC"; exit 1; }
say "LAUNCH round3"
"$PY" -u distill/train_lora.py \
  --corpus "$CORPUS" \
  --out-dir "$OUT" \
  --epochs 4 --grad-accum 2 --lr 1e-4 --schedule cosine \
  --census-every 12 --save-every 24 --seed 0 --probe \
  > "$LOG" 2>&1
say "round3 END rc=$? last=$(grep '^== STEP' "$LOG" 2>/dev/null | tail -1)"
