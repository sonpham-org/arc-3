#!/bin/bash
# Self-contained: serve Qwen3.6-27B (vLLM :1234, CHAT endpoint -- no codex, no
# proxy, none of the Responses dialect problems) and run our NATIVE world-model
# CEGIS core against it. Answers: does OUR model synthesize + exact-replay-verify
# a transition model like gpt-oss did? Syncs native_results.json to GCS + scales to 0.
set -uo pipefail
export HOME=/home/son
export PATH="$HOME/.local/bin:$PATH"
exec > >(tee -a /var/log/arc3-qwennative.log) 2>&1
echo "=== qwen36_native startup $(date -u +%FT%TZ) ==="

BUCKET=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-bucket")
RUN_ID=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-run-id")
MIG=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-mig" || echo arc3-g4-qwennative)
ZONE=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
SEED=$BUCKET/tufa-exact

done_stop(){ gcloud storage cp /var/log/arc3-qwennative.log "$BUCKET/$RUN_ID/qwennative.log" 2>/dev/null; \
  echo "$1" | gcloud storage cp - "$BUCKET/$RUN_ID/$2" 2>/dev/null; \
  gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE" 2>/dev/null; }
( sleep 7200; done_stop timeout SERVE_TIMEOUT ) &
( while true; do gcloud storage cp /var/log/arc3-qwennative.log "$BUCKET/$RUN_ID/qwennative.log" >/dev/null 2>&1; sleep 30; done ) &

apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential ninja-build ffmpeg

# ---- serve Qwen3.6 (vLLM :1234) ----
mkdir -p /opt/arc3 && cd /opt/arc3
gcloud storage rsync -r "$SEED/model" /opt/arc3/vrfai-model
gcloud storage rsync -r "$SEED/wheelhouse" /opt/arc3/wheelhouse
curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"
uv venv --python 3.12.12 /opt/arc3/pysrv
uv pip install --python /opt/arc3/pysrv/bin/python --no-index --find-links /opt/arc3/wheelhouse \
  -r /opt/arc3/wheelhouse/requirements.lock --only-binary :all: --no-build-isolation || { done_stop vllm-deps SERVE_FAILED; exit 1; }
export USE_TF=0 TRANSFORMERS_NO_TF=1 TRANSFORMERS_NO_TORCHVISION=1 VLLM_NO_USAGE_STATS=1
nohup /opt/arc3/pysrv/bin/python -m vllm.entrypoints.openai.api_server \
  --model /opt/arc3/vrfai-model --served-model-name vrfai/Qwen3.6-27B-FP8 \
  --host 127.0.0.1 --port 1234 --tensor-parallel-size 1 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder \
  --generation-config vllm --enable-prefix-caching \
  --default-chat-template-kwargs '{"preserve_thinking": true}' \
  --reasoning-parser qwen3 --max-model-len 65536 > /opt/arc3/vllm.log 2>&1 &
for i in $(seq 1 150); do curl -s -m 3 http://127.0.0.1:1234/v1/models >/dev/null && break; sleep 10; done
curl -s -m 5 http://127.0.0.1:1234/v1/models >/dev/null || { gcloud storage cp /opt/arc3/vllm.log "$BUCKET/$RUN_ID/serve-vllm.log"; done_stop vllm-start SERVE_FAILED; exit 1; }
echo "vLLM chat endpoint ready"

# ---- native harness venv: arcengine + numpy (no torch/vllm needed) ----
mkdir -p /opt/native && gcloud storage cp "$BUCKET/code/native_pkg.tgz" /tmp/n.tgz && tar xzf /tmp/n.tgz -C /opt/native
mkdir -p /opt/native/engwheels && gcloud storage rsync -r "$SEED/engine-wheels" /opt/native/engwheels
uv venv --python 3.12.12 /opt/native/.venv
uv pip install --python /opt/native/.venv/bin/python numpy pillow opencv-python-headless >/dev/null 2>&1
uv pip install --python /opt/native/.venv/bin/python --no-deps \
  /opt/native/engwheels/arc_agi-0.9.8-py3-none-any.whl /opt/native/engwheels/arcengine-0.9.3-py3-none-any.whl
/opt/native/.venv/bin/python -c "import arcengine, numpy; print('arcengine ok')" || { done_stop arcengine RUN_FAILED; exit 1; }

# ---- run the native CEGIS core with Qwen3.6 (chat) ----
cd /opt/native
echo "=== running native CEGIS on ls20+ft09 with Qwen3.6-27B @ $(date -u +%FT%TZ) ==="
WM_LLM_BASE_URL=http://127.0.0.1:1234/v1 WM_LLM_MODEL=vrfai/Qwen3.6-27B-FP8 WM_GAMES="ls20 ft09" \
  /opt/native/.venv/bin/python /opt/native/run_native.py 2>&1 | tail -n +1
echo "=== native run exited $? @ $(date -u +%FT%TZ) ==="
gcloud storage cp /opt/native/native_results.json "$BUCKET/$RUN_ID/native_results.json" 2>/dev/null
done_stop done DONE
echo "=== done ==="
