#!/bin/bash
# SERVE-ONLY: stand up Qwen3.6-27B-FP8 as a vLLM OpenAI server on :1234 for a
# REMOTE client (local OPINE/codex over an IAP tunnel) to drive. No harness run.
# Binds 0.0.0.0 so `gcloud compute start-iap-tunnel <inst> 1234:localhost:1234`
# can reach it (IAP is auth'd over Google's control plane -- no open firewall).
# Writes SERVE_READY / SERVE_FAILED markers, probes /v1/responses (codex needs
# it), and self-scales the MIG to 0 after 3h as a cost backstop.
set -uo pipefail
export HOME="${HOME:-/root}"
exec > >(tee -a /var/log/arc3-serve.log) 2>&1
echo "=== qwen36 serve startup $(date -u +%FT%TZ) ==="

BUCKET=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-bucket")
RUN_ID=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-run-id")
MIG=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-mig" || echo arc3-g4-qwenserve)
ZONE=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
SEED=$BUCKET/tufa-exact
echo "bucket=$BUCKET run=$RUN_ID mig=$MIG zone=$ZONE"

# Cost backstop: force the MIG to 0 after 3h no matter what.
( sleep 10800; echo timeout | gcloud storage cp - "$BUCKET/$RUN_ID/SERVE_TIMEOUT" 2>/dev/null; \
  gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE" 2>/dev/null ) &

( while true; do gcloud storage cp /var/log/arc3-serve.log "$BUCKET/$RUN_ID/serve-$(hostname).log" >/dev/null 2>&1; sleep 60; done ) &

# ninja-build is REQUIRED: vLLM/flashinfer JIT-compiles the SM120 (Blackwell) GEMM
# kernel at startup via ninja; without it the engine core dies on first forward.
apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential ninja-build ffmpeg

mkdir -p /opt/arc3 && cd /opt/arc3
gcloud storage rsync -r "$SEED/model" /opt/arc3/vrfai-model
gcloud storage rsync -r "$SEED/wheelhouse" /opt/arc3/wheelhouse
echo "model files: $(ls /opt/arc3/vrfai-model | wc -l), wheels: $(ls /opt/arc3/wheelhouse/*.whl 2>/dev/null | wc -l)"

curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"
uv venv --python 3.12.12 /opt/arc3/pysrv
uv pip install --python /opt/arc3/pysrv/bin/python --no-index --find-links /opt/arc3/wheelhouse \
  -r /opt/arc3/wheelhouse/requirements.lock --only-binary :all: --no-build-isolation || {
  echo "wheelhouse install failed"; echo fail | gcloud storage cp - "$BUCKET/$RUN_ID/SERVE_FAILED"; exit 1; }

export USE_TF=0 TRANSFORMERS_NO_TF=1 TRANSFORMERS_NO_TORCHVISION=1 VLLM_NO_USAGE_STATS=1
# Same proven flags as the harness runs, except --host 0.0.0.0 for the tunnel.
nohup /opt/arc3/pysrv/bin/python -m vllm.entrypoints.openai.api_server \
  --model /opt/arc3/vrfai-model --served-model-name vrfai/Qwen3.6-27B-FP8 \
  --host 0.0.0.0 --port 1234 --tensor-parallel-size 1 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder \
  --generation-config vllm --enable-prefix-caching \
  --default-chat-template-kwargs '{"preserve_thinking": true}' \
  --reasoning-parser qwen3 --max-model-len 65536 \
  > /opt/arc3/vllm.log 2>&1 &

for i in $(seq 1 150); do curl -s -m 3 http://127.0.0.1:1234/v1/models >/dev/null && break; sleep 10; done
if ! curl -s -m 5 http://127.0.0.1:1234/v1/models >/dev/null; then
  echo "SERVER FAILED"; gcloud storage cp /opt/arc3/vllm.log "$BUCKET/$RUN_ID/serve-vllm.log" || true
  echo fail | gcloud storage cp - "$BUCKET/$RUN_ID/SERVE_FAILED"; exit 1
fi
echo "vLLM up on :1234"

# Does this vLLM serve the Responses API codex needs? Probe and record it.
RESP=$(curl -s -m 20 -o /tmp/resp.json -w "%{http_code}" -X POST http://127.0.0.1:1234/v1/responses \
  -H 'Content-Type: application/json' \
  -d '{"model":"vrfai/Qwen3.6-27B-FP8","input":"say hi"}' 2>/dev/null || echo "000")
echo "responses-probe HTTP $RESP"; head -c 300 /tmp/resp.json 2>/dev/null
{ echo "responses_http=$RESP"; echo "host=$(hostname)"; } | gcloud storage cp - "$BUCKET/$RUN_ID/SERVE_READY"
gcloud storage cp /tmp/resp.json "$BUCKET/$RUN_ID/serve-responses-probe.json" 2>/dev/null || true
gcloud storage cp /opt/arc3/vllm.log "$BUCKET/$RUN_ID/serve-vllm.log" 2>/dev/null || true
echo "READY marker written (responses_http=$RESP). Serving until tunnel client done or 3h backstop."

# Stay up (serve). Keep re-uploading the log; the 3h backstop or a manual resize stops it.
while true; do gcloud storage cp /opt/arc3/vllm.log "$BUCKET/$RUN_ID/serve-vllm.log" >/dev/null 2>&1; sleep 120; done
