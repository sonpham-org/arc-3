#!/bin/bash
# G1 trainer box (plan: docs/plans/2026-10-01-rl-on-burst-games.md §9, G1). NOT launched without Son's go.
# Machine: g4-standard-384 (8x RTX PRO 6000, 96 GB each), Spot; image family common-cu129-ubuntu-2404-nvidia-580
# (drivers, no docker, no pip); 2 TB hyperdisk/pd-ssd at /mnt/m.
# Metadata: rl-code (gs:// code dir), rl-campaign, rl-records (gs:// glob of round-0 records).
# Steps (each writes to gs://cellens-ai-artifacts/arc3-rl/<campaign>/g1/):
#   1. env: torch (cu129, sm_120), transformers 5.18, peft 0.21.2, accelerate, fla + causal-conv1d kernels
#   2. weights: Qwen/Qwen3.8-Flash-Next BF16 from HF (~360 GB); Intel W4A16 from GCS (Daniel's served model)
#   3. lora_train.py check on the largest record (~118k tokens): memory, forward/step time, loss falls
#   4. lora_train.py train on 16 records (mini round): adapter
#   5. merge_lora.py: zero check on W4A16 (byte-identical), real merge into W4A16 (kept share per tensor)
# Serving the merged checkpoint (Daniel's SGLang) and served = trained come next (G1b).
set -uo pipefail
exec > >(tee -a /var/log/rl-g1.log) 2>&1
md() { curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
CODE=$(md rl-code); CAMPAIGN=$(md rl-campaign); RECORDS=$(md rl-records)
OUT=gs://cellens-ai-artifacts/arc3-rl/$CAMPAIGN/g1
step() { echo "$(date -u +%FT%TZ) $*" | tee -a /var/log/rl-g1-phases.log; gcloud storage cp /var/log/rl-g1-phases.log "$OUT/phases.log" >/dev/null 2>&1; }
step start
nvidia-smi --query-gpu=index,name,memory.total --format=csv || { step "no GPU"; exit 1; }
DISK=$(lsblk -dn -o NAME,SIZE | awk '$2 ~ /T$/ {print $1}' | head -1)
mkdir -p /mnt/m && { mount /dev/$DISK /mnt/m 2>/dev/null || { mkfs.ext4 -q -F /dev/$DISK && mount /dev/$DISK /mnt/m; }; }
df -h /mnt/m
mkdir -p /opt/rl/hf /mnt/m/rl && cd /opt/rl
gcloud storage cp "$CODE/*" /opt/rl/
apt-get update -y -q && apt-get install -y -q python3-venv python3-pip python3-dev build-essential >/dev/null
python3 -m venv venv && . venv/bin/activate
pip install -q --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cu129
pip install -q --no-cache-dir "transformers==5.18.0" "peft==0.21.2" accelerate safetensors pillow jinja2 \
    huggingface_hub hf_transfer
pip install -q --no-cache-dir flash-linear-attention || step "fla install failed (reference kernels)"
pip install -q --no-cache-dir causal-conv1d --no-build-isolation || step "causal-conv1d install failed (reference)"
python -c "import torch; print(torch.__version__, torch.cuda.get_device_capability(0), torch.cuda.device_count())"
step env_ready
export HF_HUB_ENABLE_HF_TRANSFER=1
huggingface-cli download Qwen/Qwen3.8-Flash-Next --local-dir /mnt/m/bf16 --max-workers 32 >/dev/null 2>&1 \
    || hf download Qwen/Qwen3.8-Flash-Next --local-dir /mnt/m/bf16 >/dev/null 2>&1
cp /mnt/m/bf16/{chat_template.jinja,tokenizer.json,tokenizer_config.json,vocab.json,merges.txt,preprocessor_config.json,video_preprocessor_config.json,config.json} /opt/rl/hf/
step bf16_ready "$(du -sh /mnt/m/bf16 | cut -f1)"
gcloud storage cp -r "gs://cellens-ai-artifacts/arc3-duck/daniel-base/kaggle-input/models/dfranzen/intel-qwen3.8-flash-next-w4a16-autoround/transformers/default/1" /mnt/m/w4a16-src >/dev/null 2>&1
step w4a16_ready "$(du -sh /mnt/m/w4a16-src | cut -f1)"
mkdir -p /mnt/m/rl/records && gcloud storage cp "$RECORDS" /mnt/m/rl/records/ >/dev/null 2>&1
BIG=$(ls -S /mnt/m/rl/records/*.jsonl.gz | head -1)
python lora_train.py check --model /mnt/m/bf16 --hf /opt/rl/hf --records "$BIG" --steps 3 --out /mnt/m/rl/check \
    > /mnt/m/rl/check.log 2>&1; step "check exit $?"
gcloud storage cp /mnt/m/rl/check.log /mnt/m/rl/check/CHECK.json "$OUT/" >/dev/null 2>&1
python lora_train.py train --model /mnt/m/bf16 --hf /opt/rl/hf --records "/mnt/m/rl/records/*.jsonl.gz" --epochs 1 \
    --limit 16 --accum 4 --out /mnt/m/rl/adapter-mini > /mnt/m/rl/train.log 2>&1; step "mini train exit $?"
gcloud storage cp -r /mnt/m/rl/train.log /mnt/m/rl/adapter-mini "$OUT/" >/dev/null 2>&1
python merge_lora.py --adapter /mnt/m/rl/check/adapter --checkpoint /mnt/m/w4a16-src --out /mnt/m/w4a16-zero \
    --mult 0 --expect-identical > /mnt/m/rl/merge_zero.log 2>&1; step "zero merge exit $?"
python merge_lora.py --adapter /mnt/m/rl/adapter-mini --checkpoint /mnt/m/w4a16-src --out /mnt/m/w4a16-mini \
    > /mnt/m/rl/merge.log 2>&1; step "merge exit $?"
gcloud storage cp /mnt/m/rl/merge_zero.log /mnt/m/rl/merge.log /mnt/m/w4a16-mini/MERGE_REPORT.json "$OUT/" >/dev/null 2>&1
gcloud storage cp /var/log/rl-g1.log "$OUT/vm.log"
step done
