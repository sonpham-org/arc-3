#!/bin/bash
# 3-Oct-2026: score the deployed 2-Oct tuned drafter (daniel-draftcap-a-1002/draft_ft.pt) on the 4-bit-KV capture's
# held-out games, same eval as the new drafter's training log (train_draft.py --init ... --steps 0), on the lab VM
# arc3-dlab-1003kv4b that already holds the capture and checkpoint. Run: sudo nohup bash eval_old_on_kv4cap.sh &
R=gs://cellens-ai-artifacts/arc3-duck/daniel-draft/results/daniel-bench-kv4cap-1003
L=/opt/arc3/dlab; M=$L/mtp
gcloud storage cp -q gs://cellens-ai-artifacts/arc3-duck/daniel-draft/results/daniel-draftcap-a-1002/draft_ft.pt $L/old_ft.pt
docker run --rm --gpus all --ipc=host -v /opt/arc3:/opt/arc3 arc3-sglang:built bash -lc "source /opt/sglvenv/bin/activate && cd $M && \
python train_draft.py --cap $M/cap --ckpt $L/ckpt --mask $L/ckpt/mask.pt --hot $L/hot_tokens_64k.pt --out $M/evalold \
--init $L/old_ft.pt --steps 0 --lr 2e-5 --rows 512 --split game --loss kl --eval-every 500 --eval-rows 12000 \
--eval-temp 0.7 --eval-top-k 20 --eval-top-p 0.95" > $L/evalold.log 2>&1
echo "rc=$?" >> $L/evalold.log
gcloud storage cp -q $M/evalold/log.jsonl $R/eval_old_tuned.log.jsonl
gcloud storage cp -q $L/evalold.log $R/eval_old_tuned.log
