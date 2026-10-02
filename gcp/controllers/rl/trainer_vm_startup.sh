#!/bin/bash
# RL trainer VM (plan: docs/plans/2026-10-01-rl-on-burst-games.md §0b step 1). g4-standard-192 (4x RTX PRO 6000),
# image family common-cu129-ubuntu-2404-nvidia-580, 2 TB hyperdisk-balanced, Spot with STOP on preemption.
# Metadata: rl-code (gs:// code dir), rl-service (job folder name under gs://.../arc3-rl/trainer/).
# Idempotent: a restart after a Spot stop skips the steps already done, then resumes the job service.
set -uo pipefail
exec > >(tee -a /var/log/rl-trainer.log) 2>&1
md() { curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
CODE=$(md rl-code); SERVICE=$(md rl-service)
OUT=gs://cellens-ai-artifacts/arc3-rl/trainer/$SERVICE
phase() { echo "$(date -u +%FT%TZ) $*" | tee -a /var/log/rl-trainer-phases.log; gcloud storage cp /var/log/rl-trainer-phases.log "$OUT/phases.log" >/dev/null 2>&1; }
phase "boot code=$CODE"
nvidia-smi --query-gpu=index,name,memory.total --format=csv || { phase "no GPU"; exit 1; }
mkdir -p /opt/m /opt/rl
if [ ! -f /opt/rl/.env_ok ]; then
  apt-get update -y -q && apt-get install -y -q python3-venv python3-pip python3-dev build-essential git >/dev/null
  python3 -m venv /opt/rl/venv
  . /opt/rl/venv/bin/activate
  pip install -q --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cu129
  pip install -q --no-cache-dir "transformers==5.18.0" "peft==0.21.2" accelerate safetensors pillow jinja2 \
      huggingface_hub hf_transfer
  pip install -q --no-cache-dir flash-linear-attention || phase "flash-linear-attention install failed (reference kernels)"
  python -c "import torch; assert torch.cuda.is_available(); print(torch.__version__, torch.cuda.get_device_capability(0), torch.cuda.device_count())" \
    && touch /opt/rl/.env_ok
fi
. /opt/rl/venv/bin/activate
phase "env $(python -c 'import torch, transformers, peft; print(torch.__version__, transformers.__version__, peft.__version__)' 2>&1 | tail -1)"
if [ ! -f /opt/m/bf16/.done ]; then
  export HF_HUB_ENABLE_HF_TRANSFER=1
  (hf download Qwen/Qwen3.8-Flash-Next --local-dir /opt/m/bf16 || huggingface-cli download Qwen/Qwen3.8-Flash-Next --local-dir /opt/m/bf16) \
    > /var/log/hf-download.log 2>&1 && touch /opt/m/bf16/.done
fi
phase "weights $(du -sh /opt/m/bf16 | cut -f1) done=$(test -f /opt/m/bf16/.done && echo yes || echo NO)"
gcloud storage cp "$CODE/*" /opt/rl/
cd /opt/rl
python test_rl_core.py 2>&1 | tail -2
phase "service start"
python trainer_service.py --service "$SERVICE" --model /opt/m/bf16 --hf /opt/m/bf16 --work /opt/m/work --gpus 4 --gpu-gib 70
phase "service exited $?"
