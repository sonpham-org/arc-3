#!/bin/bash
# FP8 draft-KV cost in expected tokens per step (2-Oct-2026): the stock and the tuned draft evaluated with fp8-rounded
# K/V (train_draft.py --fp8-kv --steps 0) on the same held-out games and rows as the training run (same seed, split and
# eval settings), next to the run's own bf16 evals (step 0 = stock, step 3500 = tuned).
set -uo pipefail
DD=gs://cellens-ai-artifacts/arc3-duck/daniel-draft
R=$DD/results/daniel-draftcap-a-1002
L=/opt/arc3/dlab; M=$L/mtp
gcloud storage cp -q $DD/code/draft_torch.py $DD/code/train_draft.py $M/
COMMON="--cap $M/cap --ckpt $L/ckpt --mask $L/ckpt/mask.pt --hot $L/hot_tokens_64k.pt --steps 0 --rows 512 --split game --loss kl --eval-rows 12000 --eval-temp 0.7 --eval-top-k 20 --eval-top-p 0.95 --fp8-kv"
for v in stock tuned; do
  X=""; [ $v = tuned ] && X="--init $M/train/draft_ft.pt"
  docker run --rm --gpus all --ipc=host -v /opt/arc3:/opt/arc3 arc3-sglang:built bash -lc \
    "source /opt/sglvenv/bin/activate && cd $M && python train_draft.py $COMMON --out $M/eval-$v-fp8 $X" > $M/eval-$v-fp8.log 2>&1
  echo "$(date -u +%FT%TZ) eval-$v-fp8 rc=$?" >> $L/phases.txt
  gcloud storage cp -q $M/eval-$v-fp8/log.jsonl $R/eval-$v-fp8.log.jsonl >/dev/null 2>&1
  gcloud storage cp -q $M/eval-$v-fp8.log $L/phases.txt $R/ >/dev/null 2>&1
done
