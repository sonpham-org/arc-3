#!/bin/bash
# RL box startup (4-Oct-2026, plan C; rl/box/README.md). Every boot of the g4-standard-384 (8x RTX PRO 6000) booted
# from a snapshot of the RL trainer's disk (weights, venv, /opt/m/work):
#   1. docker + the NVIDIA container toolkit (installed once if the trainer image lacks them)
#   2. the Kaggle GPU image the notebooks run in (pulled once, its name in /var/lib/box/image)
#   3. box_agent.sh (unit box-agent): one persistent hot-swap rollout server per play card (box_pslot.sh), sessions
#   4. box_panel.sh (unit rl-panel) on the test card: the held-out full test, newest model after newest model
#   5. the trainer service on the training cards (CUDA_VISIBLE_DEVICES), same job queue as the trainer VM it replaces
# Metadata: rl-code, rl-service, box-code (default gs://cellens-ai-artifacts/arc3-rl/box/code), slot-gpus ("0 1 2"),
# slot-notebook (the hot-swap rollout notebook), slot-input (cold-start inputs), panel-gpu ("3"; "none" = no panel),
# panel-notebook (the held-out panel notebook), panel-first (a merge job to test first), trainer-gpus ("4,5,6,7").
set -uo pipefail
mkdir -p /var/log/box /var/lib/box
exec > >(tee -a /var/log/box/startup.log) 2>&1
md() { curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/$1"; }
CODE=$(md attributes/rl-code); SERVICE=$(md attributes/rl-service); BOX=$(md name)
BOXCODE=$(md attributes/box-code); case "$BOXCODE" in gs://*) ;; *) BOXCODE=gs://cellens-ai-artifacts/arc3-rl/box/code;; esac
BOXQ=gs://cellens-ai-artifacts/arc3-rl/box/$BOX
SLOT_GPUS=$(md attributes/slot-gpus); [ -n "$SLOT_GPUS" ] || SLOT_GPUS="0 1 2"
SLOT_NB=$(md attributes/slot-notebook); SLOT_IN=$(md attributes/slot-input)
PANEL_GPU=$(md attributes/panel-gpu); [ -n "$PANEL_GPU" ] || PANEL_GPU=3
PANEL_NB=$(md attributes/panel-notebook); PANEL_FIRST=$(md attributes/panel-first)
TRAINER_GPUS=$(md attributes/trainer-gpus); [ -n "$TRAINER_GPUS" ] || TRAINER_GPUS=4,5,6,7
IMAGE_GPU=gcr.io/kaggle-gpu-images/python@sha256:37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461
phase() { echo "$(date -u +%FT%TZ) $*" | tee -a /var/log/box/phases.log; gcloud storage cp /var/log/box/phases.log "$BOXQ/phases.log" >/dev/null 2>&1; }
phase "boot $BOX code=$CODE service=$SERVICE"
nvidia-smi --query-gpu=index,name,memory.total --format=csv || { phase "no GPU"; exit 1; }
phase "cards $(nvidia-smi -L | wc -l); disk $(df -h / | awk 'NR==2 {print $4 " free of " $2}'); RAM $(free -g | awk '/Mem:/ {print $2}') GB"
growpart /dev/nvme0n1 1 > /dev/null 2>&1; resize2fs /dev/nvme0n1p1 > /dev/null 2>&1   # a restore onto a bigger disk

apt_get() { DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=900 -y -q "$@"; }
if ! command -v docker > /dev/null; then
  apt_get update > /dev/null && apt_get install docker.io > /dev/null && phase "docker installed" || phase "docker install FAILED"
fi
if ! command -v nvidia-ctk > /dev/null; then
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --batch --yes --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    > /etc/apt/sources.list.d/nvidia-container-toolkit.list
  apt_get update > /dev/null && apt_get install nvidia-container-toolkit > /dev/null && phase "container toolkit installed" \
    || phase "container toolkit install FAILED"
fi
nvidia-ctk runtime configure --runtime=docker > /dev/null 2>&1 && systemctl restart docker
gcloud auth configure-docker gcr.io --quiet > /dev/null 2>&1
if ! docker image inspect "$IMAGE_GPU" > /dev/null 2>&1; then
  ( for i in 1 2 3; do timeout 2400 docker pull "$IMAGE_GPU" > /var/log/box/image-pull.log 2>&1 && break; sleep 30; done
    docker image inspect "$IMAGE_GPU" > /dev/null 2>&1 && echo "$IMAGE_GPU" > /var/lib/box/image && phase "image pulled" \
      || phase "image pull FAILED" ) &
else
  echo "$IMAGE_GPU" > /var/lib/box/image
fi

mkdir -p /opt/box
gcloud storage cp "$BOXCODE/box_agent.sh" "$BOXCODE/box_pslot.sh" "$BOXCODE/box_panel.sh" /opt/box/ && chmod +x /opt/box/*.sh   || phase "box code download FAILED"
gcloud storage cp "$BOXCODE/extract_delta.py" /opt/rl/extract_delta.py > /dev/null 2>&1
mkdir -p /kaggle-delta /kaggle-in
systemctl stop box-agent > /dev/null 2>&1; systemctl reset-failed box-agent > /dev/null 2>&1
if [ -n "$SLOT_NB" ] && [ "$SLOT_GPUS" != none ]; then
  systemd-run --unit box-agent --setenv=SLOTS="$SLOT_GPUS" --setenv=NB_OBJ="$SLOT_NB" ${SLOT_IN:+--setenv=IN="$SLOT_IN"}     /bin/bash /opt/box/box_agent.sh "$BOX" "$BOXCODE" && phase "agent started: play cards $SLOT_GPUS"
fi
systemctl stop rl-panel > /dev/null 2>&1; systemctl reset-failed rl-panel > /dev/null 2>&1
if [ -n "$PANEL_NB" ] && [ "$PANEL_GPU" != none ]; then
  systemd-run --unit rl-panel --setenv=CARD="$PANEL_GPU" --setenv=NB_OBJ="$PANEL_NB" ${PANEL_FIRST:+--setenv=FIRST="$PANEL_FIRST"}     /bin/bash /opt/box/box_panel.sh && phase "panel loop started: card $PANEL_GPU"
fi

# the trainer (trainer_vm_startup.sh after its one-time setup, which this disk already has); trainer-gpus=none = a
# test-only boot (run_c.py's last held-out test on a 1-card box)
[ "$TRAINER_GPUS" = none ] && { phase "no trainer (trainer-gpus=none)"; exit 0; }
[ -f /opt/rl/.env_ok ] && [ -f /opt/m/bf16/.done ] || { phase "trainer disk without venv or weights: no trainer"; exit 1; }
. /opt/rl/venv/bin/activate
gcloud storage cp "$CODE/*" /opt/rl/
cd /opt/rl
NT=$(echo "$TRAINER_GPUS" | tr ',' ' ' | wc -w)
phase "trainer service start: cards $TRAINER_GPUS"
CUDA_VISIBLE_DEVICES=$TRAINER_GPUS python trainer_service.py --service "$SERVICE" --model /opt/m/bf16 --hf /opt/m/bf16   --work /opt/m/work --gpus "$NT" --gpu-gib 70
phase "trainer service exited $?"
