#!/bin/bash
# V12_[MODEL]: v12 grafts + pickles + tempo env, serving an alternate model on vllm 0.25.
# Agent code = pristine upstream (commit a2dddac). Server = THEIR pinned stack
# (vllm 0.19 wheelhouse) launched with THEIR exact flags. Env = THEIR exact
# setup_env values. Only the infra scaffolding (GCS sync, guards) is ours.
set -uo pipefail
export HOME="${HOME:-/root}"
exec > >(tee -a /var/log/arc3-startup.log) 2>&1
echo "=== tufa0 startup $(date -u +%FT%TZ) ==="

BUCKET=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-bucket")
RUN_ID=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-run-id")
MIG=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-mig" || echo arc3-g4-v12m)
MODEL_GCS=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-model-gcs")
MODEL_NAME=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-model-name")
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
mkdir -p /opt/arc3/bundle && gcloud storage cp "$SEED/bundle-v12.tgz" /tmp/b.tgz && tar xzf /tmp/b.tgz -C /opt/arc3/bundle
gcloud storage cp "$BUCKET/code/v12_run.py" /opt/arc3/v12_run.py
gcloud storage rsync -r "$MODEL_GCS" /opt/arc3/model
echo "model files: $(ls /opt/arc3/model | wc -l) ($MODEL_NAME)"

# ---- server: THEIR stack, THEIR flags (mirrors setup_commands.json PYSETUP) --
curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"
uv venv --python 3.12.12 /opt/arc3/pysrv
uv pip install --python /opt/arc3/pysrv/bin/python vllm==0.25.0 || {
  echo "vllm install failed"; echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/serverfail"; exit 1; }
export USE_TF=0 TRANSFORMERS_NO_TF=1 TRANSFORMERS_NO_TORCHVISION=1 VLLM_NO_USAGE_STATS=1
nohup /opt/arc3/pysrv/bin/python -m vllm.entrypoints.openai.api_server \
  --model /opt/arc3/model --served-model-name "$MODEL_NAME" \
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
echo "vllm 0.25 model server ready: $MODEL_NAME"

# ---- agent: pristine harness, THEIR env values -------------------------------
cd /opt/arc3/ARC3-Inference
export CONFIG_PATH=configs/tufa0.json
export TAAF_PERIODIC_SAVE_INTERVAL_S=120
make install-a108
# Competition-exact engine: Kaggle reruns use arc_agi 0.9.8 / arcengine 0.9.3
# (the competition wheelhouse); Tufa's lock resolves the newer 0.9.9.
mkdir -p /opt/arc3/engwheels && gcloud storage rsync -r "$SEED/engine-wheels" /opt/arc3/engwheels
export PATH="$HOME/.local/bin:$PATH"
uv pip install --python ./.venv/bin/python --no-deps /opt/arc3/engwheels/arc_agi-0.9.8-py3-none-any.whl /opt/arc3/engwheels/arcengine-0.9.3-py3-none-any.whl
./.venv/bin/python -c "import arc_agi, arcengine, importlib.metadata as m; print('engine:', m.version('arc-agi'), m.version('arcengine'))"
mkdir -p runs
( while true; do gcloud storage rsync -r runs "$BUCKET/$RUN_ID/runs" >/dev/null 2>&1; sleep 120; done ) &

# Their exact setup_env (setup_commands.json), passed as real env so Make's ?= yields.
export LOCAL_ANALYZER_BASE_URL=http://127.0.0.1:1234/v1 OPENAI_BASE_URL=http://127.0.0.1:1234/v1
export LOCAL_ANALYZER_PROVIDER=vllm OPENAI_PROVIDER=vllm
export LOCAL_ANALYZER_MODEL_ID="$MODEL_NAME" INFERENCE_ANALYZER_MODEL="$MODEL_NAME"
export LOCAL_ANALYZER_APP_NAME="ARC3 Agent Harness"
export LOCAL_ANALYZER_CONTEXT_WINDOW=32768 LOCAL_ANALYZER_MAX_OUTPUT=0
export LOCAL_ANALYZER_TOOL_STEPS=0 LOCAL_ANALYZER_TOOL_TIMEOUT=30 LOCAL_ANALYZER_TOOL_OUTPUT_TOKENS=1024
export LOCAL_ANALYZER_YIELD_SECONDS=60
export LOCAL_ANALYZER_TEMPERATURE=0.6 LOCAL_ANALYZER_TOP_P=0.95 LOCAL_ANALYZER_TOP_K=20
export LOCAL_ANALYZER_ENABLE_THINKING=true
export MULTIMODAL_CONTEXT=current_grid MULTIMODAL_UPSCALE=4

RUNS_LINK=/opt/arc3/work
mkdir -p "$RUNS_LINK" && ln -sfn "$RUNS_LINK" runs
./.venv/bin/python /opt/arc3/v12_run.py 2>&1 | tee /opt/arc3/v12.log || echo "runner exited $?"
gcloud storage cp /opt/arc3/v12.log "$BUCKET/$RUN_ID/v12-run.log" || true
# teardown_commands equivalent: SIGTERM the vLLM server, then hard-kill
pkill -TERM -f "vllm.entrypoints.openai.api_server" 2>/dev/null; sleep 10
pkill -KILL -f "vllm.entrypoints.openai.api_server" 2>/dev/null || true
echo "vLLM server stopped (teardown parity)"

gcloud storage rsync -r runs "$BUCKET/$RUN_ID/runs"
gcloud storage rsync -r -x '^(?!.*benchmark\.json$).*' "$BUCKET/$RUN_ID/runs" /tmp/prior >/dev/null 2>&1 || true
echo done | gcloud storage cp - "$BUCKET/$RUN_ID/DONE"
gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE" || true