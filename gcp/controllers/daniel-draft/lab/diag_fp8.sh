#!/bin/bash
# FP8 fidelity diagnostic on the dlab VM (2-Oct-2026). The PyTorch copy predicts the real next token ~2.5 points better
# than Daniel's served draft and agrees with it 90.8% (99% only below 2,048 tokens). His server keeps the draft's KV in
# fp8 e4m3 (--speculative-draft-kv-cache-dtype fp8_e4m3). If rounding the copy's K/V (or its QSA index keys) through
# fp8 raises agreement with the served proposals, fp8 draft caches are the cause, and a bf16 draft KV is a serving lever.
# Runs after training/packaging; results next to the lab's other outputs.
set -uo pipefail
DD=gs://cellens-ai-artifacts/arc3-duck/daniel-draft
R=$DD/results/daniel-draftcap-a-1002
L=/opt/arc3/dlab; M=$L/mtp
gcloud storage cp -q $DD/code/draft_torch.py $DD/code/verify_draft.py $M/
while pgrep -f "train_draft.py|package_daniel_draft.py" >/dev/null; do sleep 30; done
for v in kv idx kvidx; do
  case $v in kv) X="--fp8-kv";; idx) X="--fp8-idx";; kvidx) X="--fp8-kv --fp8-idx";; esac
  docker run --rm --gpus all --ipc=host -v /opt/arc3:/opt/arc3 arc3-sglang:built bash -lc \
    "source /opt/sglvenv/bin/activate && cd $M && python verify_draft.py --cap $M/cap --ckpt $L/ckpt --mask $L/ckpt/mask.pt --hot $L/hot_tokens_64k.pt --requests 24 --out $M/verify-fp8$v.json $X" \
    > $M/verify-fp8$v.log 2>&1
  echo "$(date -u +%FT%TZ) verify-fp8$v rc=$?" >> $L/phases.txt
  gcloud storage cp -q $M/verify-fp8$v.json $M/verify-fp8$v.log $L/phases.txt $R/ >/dev/null 2>&1
done
