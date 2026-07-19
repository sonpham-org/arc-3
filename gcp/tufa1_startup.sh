#!/bin/bash
# RUNG 1: Tufa-exact agent + OUR serving stack (vllm 0.25, ngram spec decode).
# Agent code = pristine upstream (commit a2dddac). Server = THEIR pinned stack
# (vllm 0.19 wheelhouse) launched with THEIR exact flags. Env = THEIR exact
# setup_env values. Only the infra scaffolding (GCS sync, guards) is ours.
set -uo pipefail
export HOME="${HOME:-/root}"
exec > >(tee -a /var/log/arc3-startup.log) 2>&1
echo "=== tufa0 startup $(date -u +%FT%TZ) ==="

BUCKET=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-bucket")
RUN_ID=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-run-id")
MIG=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-mig" || echo arc3-g4-tufa1)
ZONE=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
SEED=$BUCKET/tufa-exact
echo "bucket=$BUCKET run=$RUN_ID mig=$MIG"

mkdir -p /opt/arc3 && cd /opt/arc3
ATTEMPTS=$( (gcloud storage cat "$BUCKET/$RUN_ID/attempts" 2>/dev/null || echo 0) | tr -dc '0-9' ); ATTEMPTS=$(( ${ATTEMPTS:-0} + 1 ))
echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/attempts"; echo "boot attempt #$ATTEMPTS"
if [ "$ATTEMPTS" -gt 8 ]; then echo failed | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"; gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE" || true; exit 1; fi

( while true; do gcloud storage cp /var/log/arc3-startup.log "$BUCKET/$RUN_ID/startup-$(hostname).log" >/dev/null 2>&1; sleep 60; done ) &

apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential ffmpeg ninja-build

# ---- pristine code + their model + their wheelhouse -------------------------
gcloud storage cp "$BUCKET/code/arc3-code-tufa0.tgz" /tmp/c.tgz && tar xzf /tmp/c.tgz -C /opt/arc3
gcloud storage rsync -r "$SEED/model" /opt/arc3/vrfai-model
gcloud storage rsync -r "$SEED/wheelhouse" /opt/arc3/wheelhouse
echo "model files: $(ls /opt/arc3/vrfai-model | wc -l), wheelhouse wheels: $(ls /opt/arc3/wheelhouse/*.whl 2>/dev/null | wc -l)"

# ---- server: THEIR stack, THEIR flags (mirrors setup_commands.json PYSETUP) --
curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"
uv venv --python 3.12.12 /opt/arc3/pysrv
uv pip install --python /opt/arc3/pysrv/bin/python vllm==0.25.0 || {
  echo "vllm 0.25 install failed"; echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/serverfail"; exit 1; }
export USE_TF=0 TRANSFORMERS_NO_TF=1 TRANSFORMERS_NO_TORCHVISION=1 VLLM_NO_USAGE_STATS=1
nohup /opt/arc3/pysrv/bin/python -m vllm.entrypoints.openai.api_server \
  --model /opt/arc3/vrfai-model --served-model-name vrfai/Qwen3.6-27B-FP8 \
  --host 127.0.0.1 --port 1234 --tensor-parallel-size 1 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder \
  --generation-config vllm --enable-prefix-caching \
  --default-chat-template-kwargs '{"preserve_thinking": true}' \
  --reasoning-parser qwen3 --max-model-len 65536 --max-num-seqs 128 \
  --speculative-config '{"method":"ngram","num_speculative_tokens":5,"prompt_lookup_max":5,"prompt_lookup_min":2}' \
  > /opt/arc3/vllm.log 2>&1 &
for i in $(seq 1 120); do curl -s -m 3 http://127.0.0.1:1234/v1/models >/dev/null && break; sleep 10; done
if ! curl -s -m 5 http://127.0.0.1:1234/v1/models >/dev/null; then
  echo "SERVER FAILED TO START -- aborting attempt $ATTEMPTS"
  gcloud storage cp /opt/arc3/vllm.log "$BUCKET/$RUN_ID/serverlog-$(hostname)-$ATTEMPTS.log" || true
  echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/serverfail"; exit 1
fi
echo "vllm 0.25 spec-decode server ready"

# ---- agent: pristine harness, THEIR env values -------------------------------
cd /opt/arc3/ARC3-Inference
export CONFIG_PATH=configs/tufa0.json
export TAAF_PERIODIC_SAVE_INTERVAL_S=120
make install-a108
mkdir -p runs
( while true; do gcloud storage rsync -r runs "$BUCKET/$RUN_ID/runs" >/dev/null 2>&1; sleep 120; done ) &

# Their exact setup_env (setup_commands.json), passed as real env so Make's ?= yields.
export LOCAL_ANALYZER_BASE_URL=http://127.0.0.1:1234/v1 OPENAI_BASE_URL=http://127.0.0.1:1234/v1
export LOCAL_ANALYZER_PROVIDER=vllm OPENAI_PROVIDER=vllm
export LOCAL_ANALYZER_MODEL_ID=vrfai/Qwen3.6-27B-FP8 INFERENCE_ANALYZER_MODEL=vrfai/Qwen3.6-27B-FP8
export LOCAL_ANALYZER_APP_NAME="ARC3 Agent Harness"
export LOCAL_ANALYZER_CONTEXT_WINDOW=32768 LOCAL_ANALYZER_MAX_OUTPUT=0
export LOCAL_ANALYZER_TOOL_STEPS=0 LOCAL_ANALYZER_TOOL_TIMEOUT=30 LOCAL_ANALYZER_TOOL_OUTPUT_TOKENS=1024
export LOCAL_ANALYZER_YIELD_SECONDS=60
export LOCAL_ANALYZER_TEMPERATURE=0.6 LOCAL_ANALYZER_TOP_P=0.95 LOCAL_ANALYZER_TOP_K=20
export LOCAL_ANALYZER_ENABLE_THINKING=true
export MULTIMODAL_CONTEXT=current_grid MULTIMODAL_UPSCALE=4

mkdir -p /tmp/prior
gcloud storage rsync -r -x '^(?!.*benchmark\.json$).*' "$BUCKET/$RUN_ID/runs" /tmp/prior >/dev/null 2>&1 || true
REMAINING=$(./.venv/bin/python /opt/arc3/gcp/remaining_games.py /tmp/prior) || REMAINING="ERROR"
[ -z "$REMAINING" ] && REMAINING="ERROR"
echo "remaining games: $REMAINING"
if [ "$REMAINING" = "ERROR" ]; then
  echo failed | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"; gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE" || true; exit 1
elif [ "$REMAINING" != "NONE" ]; then
  make interactive GAME="$REMAINING" N_PASSES=1 CONCURRENT_JOBS=28 MAX_RUNTIME_MINUTES=132 ANALYZER_TIMEOUT=900 RUN_NAME="$RUN_ID-$(date -u +%H%M%S)" || echo "run exited $?"
fi

gcloud storage rsync -r runs "$BUCKET/$RUN_ID/runs"
gcloud storage rsync -r -x '^(?!.*benchmark\.json$).*' "$BUCKET/$RUN_ID/runs" /tmp/prior >/dev/null 2>&1 || true
FINAL=$(./.venv/bin/python /opt/arc3/gcp/remaining_games.py /tmp/prior) || FINAL="ERROR"
if [ "$FINAL" = "NONE" ]; then
  echo done | gcloud storage cp - "$BUCKET/$RUN_ID/DONE"
  # Self-teardown: scale this MIG to 0 so a finished run stops burning GPU. Requires
  # compute.instanceGroupManagers.update on the instance service account. If it 403s the VM idles
  # FOREVER (MIG targetSize stays 1 and even recreates it), so never mask the error: retry, then
  # leave a loud TEARDOWN_FAILED marker in GCS so it gets reaped instead of silently costing money.
  for _t in 1 2 3; do
    if gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE"; then
      echo "teardown: $MIG resized to 0"; break
    fi
    echo "teardown attempt $_t FAILED for $MIG"
    if [ "$_t" = 3 ]; then
      echo "TEARDOWN FAILED $MIG at $(date -u +%FT%TZ)" | gcloud storage cp - "$BUCKET/$RUN_ID/TEARDOWN_FAILED" || true
      echo "!!! TEARDOWN FAILED: $MIG still at targetSize>0 -- VM will idle until reaped !!!"
    else
      sleep 15
    fi
  done
else
  echo "still remaining: $FINAL -- leaving MIG up"
fi
