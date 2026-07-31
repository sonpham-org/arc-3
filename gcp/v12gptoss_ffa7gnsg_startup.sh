#!/bin/bash
# gpt-oss-120b on the ffa7gnsg harness, full official 25-game suite, no subset
# filter -- fair comparison against the historical Qwen 3.6 ffa7gnsg baseline
# (proper 132-min/7920s per-game budget, concurrency 28 -- matches that
# baseline exactly, not the 7-game spot-test's concurrency-8 scaling).
#
# Parameterizes the one lever the spot-test sweep validated:
#   arc3-reasoning-effort   "" (omit field, server default) | low | medium | high
set -uo pipefail
export HOME="${HOME:-/root}"
exec > >(tee -a /var/log/arc3-startup.log) 2>&1
echo "=== gpt-oss ffa7gnsg startup $(date -u +%FT%TZ) ==="

BUCKET=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-bucket")
RUN_ID=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-run-id")
MIG=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-mig" || echo arc3-g4-gptoss-ffa7gnsg)
ZONE=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
SEED=$BUCKET/tufa-exact
MODEL_BUCKET_NAME=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-model-bucket-name")
MODEL_HF_ID=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-model-hf-id")
MAX_NUM_SEQS=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-max-num-seqs" || echo 28)
REASONING_EFFORT=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-reasoning-effort" || echo "")
echo "bucket=$BUCKET run=$RUN_ID mig=$MIG model=$MODEL_HF_ID max_num_seqs=$MAX_NUM_SEQS reasoning_effort=$REASONING_EFFORT"

mkdir -p /opt/arc3 && cd /opt/arc3
gcloud storage cp "$BUCKET/code/resource_sampler.sh" /opt/arc3/resource_sampler.sh 2>/dev/null \
  && bash /opt/arc3/resource_sampler.sh "$BUCKET" "$RUN_ID" || echo "resource sampler skipped"
ATTEMPTS=$( (gcloud storage cat "$BUCKET/$RUN_ID/attempts" 2>/dev/null || echo 0) | tr -dc '0-9' ); ATTEMPTS=$(( ${ATTEMPTS:-0} + 1 ))
echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/attempts"; echo "boot attempt #$ATTEMPTS"
if [ "$ATTEMPTS" -gt 8 ]; then echo failed | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"; gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE" || true; exit 1; fi

( while true; do gcloud storage cp /var/log/arc3-startup.log "$BUCKET/$RUN_ID/startup-$(hostname).log" >/dev/null 2>&1; sleep 60; done ) &

apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential ffmpeg ninja-build

# ---- pristine code (official 25 environment_files + ARC3-Inference) --------
gcloud storage cp "$BUCKET/code/arc3-code-tufa0.tgz" /tmp/c.tgz && tar xzf /tmp/c.tgz -C /opt/arc3
# ---- bundle: textgrid + reasoning_effort passthrough patch -----------------
mkdir -p /opt/arc3/bundle && gcloud storage cp "$SEED/bundle-v12ffa7gnsg-textgrid-reasoning.tgz" /tmp/b.tgz && tar xzf /tmp/b.tgz -C /opt/arc3/bundle
gcloud storage cp "$BUCKET/code/v12_run_maxruntime.py" /opt/arc3/v12_run.py

# ---- model: gpt-oss-120b, flat GCS dir (see laguna-model-swap memory) ------
mkdir -p /opt/arc3/model
gcloud storage rsync -r "$BUCKET/model-flat/$MODEL_BUCKET_NAME" /opt/arc3/model
echo "model sync done: $(du -sh /opt/arc3/model | cut -f1)"

# ---- server: vLLM 0.25.1 (mainline gpt-oss support since 0.10.1) -----------
curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"
uv venv --python 3.12.12 /opt/arc3/pysrv
uv pip install --python /opt/arc3/pysrv/bin/python "vllm==0.25.1" || {
  echo "vllm install failed"; echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/serverfail"; exit 1; }
export USE_TF=0 TRANSFORMERS_NO_TF=1 TRANSFORMERS_NO_TORCHVISION=1 VLLM_NO_USAGE_STATS=1
# No --trust-remote-code, no forced attention/moe backend -- see
# v12gptoss_tps_startup.sh's comments (SM120 auto-selects TRITON_ATTN +
# Marlin MXFP4, the confirmed-working stock path for this GPU class). VRAM
# stays flat regardless of --max-num-seqs (vLLM pre-allocates the whole
# KV-cache pool once at startup from gpu_memory_utilization) -- confirmed
# 89.6/97.9GB at max-num-seqs=16 in the TPS smoke test; 28 should be the same.
nohup /opt/arc3/pysrv/bin/python -m vllm.entrypoints.openai.api_server \
  --model /opt/arc3/model --served-model-name "$MODEL_HF_ID" \
  --host 127.0.0.1 --port 1234 --tensor-parallel-size 1 \
  --enable-auto-tool-choice --tool-call-parser openai --reasoning-parser openai_gptoss \
  --max-num-seqs "$MAX_NUM_SEQS" \
  --max-model-len 65536 \
  > /opt/arc3/vllm.log 2>&1 &
for i in $(seq 1 120); do curl -s -m 3 http://127.0.0.1:1234/v1/models >/dev/null && break; sleep 10; done
if ! curl -s -m 5 http://127.0.0.1:1234/v1/models >/dev/null; then
  echo "SERVER FAILED TO START -- aborting attempt $ATTEMPTS"
  gcloud storage cp /opt/arc3/vllm.log "$BUCKET/$RUN_ID/serverlog-$(hostname)-$ATTEMPTS.log" || true
  echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/serverfail"; exit 1
fi
echo "vllm 0.25.1 ready: $MODEL_HF_ID (reasoning_effort=$REASONING_EFFORT)"

# ---- agent: pristine harness (own venv, independent of the server's) -------
cd /opt/arc3/ARC3-Inference
export CONFIG_PATH=configs/tufa0.json
export TAAF_PERIODIC_SAVE_INTERVAL_S=120
make install-a108
mkdir -p /opt/arc3/engwheels && gcloud storage rsync -r "$SEED/engine-wheels" /opt/arc3/engwheels
export PATH="$HOME/.local/bin:$PATH"
uv pip install --python ./.venv/bin/python --no-deps /opt/arc3/engwheels/arc_agi-0.9.8-py3-none-any.whl /opt/arc3/engwheels/arcengine-0.9.3-py3-none-any.whl
./.venv/bin/python -c "import arc_agi, arcengine, importlib.metadata as m; print('engine:', m.version('arc-agi'), m.version('arcengine'))"
mkdir -p /opt/arc3/work && rm -rf runs && ln -sfn /opt/arc3/work runs
( while true; do gcloud storage rsync -r /opt/arc3/work "$BUCKET/$RUN_ID/runs" >/dev/null 2>&1; sleep 120; done ) &

export LOCAL_ANALYZER_BASE_URL=http://127.0.0.1:1234/v1 OPENAI_BASE_URL=http://127.0.0.1:1234/v1
export LOCAL_ANALYZER_PROVIDER=vllm OPENAI_PROVIDER=vllm
export LOCAL_ANALYZER_MODEL_ID="$MODEL_HF_ID" INFERENCE_ANALYZER_MODEL="$MODEL_HF_ID"
export ARC3_REEXPLORE_STRICT="" ARC3_GAME_SUBSET="" ARC3_STATE_GRAPH=""
echo "subset=[unset -> full 25] state_graph=[off]"
export LOCAL_ANALYZER_APP_NAME="ARC3 Agent Harness"
export LOCAL_ANALYZER_CONTEXT_WINDOW=32768 LOCAL_ANALYZER_MAX_OUTPUT=0
export LOCAL_ANALYZER_TOOL_STEPS=0 LOCAL_ANALYZER_TOOL_TIMEOUT=30 LOCAL_ANALYZER_TOOL_OUTPUT_TOKENS=1024
export LOCAL_ANALYZER_YIELD_SECONDS=60
export LOCAL_ANALYZER_TEMPERATURE=0.6 LOCAL_ANALYZER_TOP_P=0.95 LOCAL_ANALYZER_TOP_K=20
# NOTE: LOCAL_ANALYZER_ENABLE_THINKING is irrelevant for gpt-oss (harmony
# format bypasses chat_template_kwargs entirely) -- reasoning_effort below is
# this model's real lever, wired via harnesses/ffa7g-textgrid-reasoning-effort/.
export LOCAL_ANALYZER_REASONING_EFFORT="$REASONING_EFFORT"
# NOTE: MULTIMODAL_CONTEXT deliberately left UNSET -- gpt-oss-120b is
# text-only, same textgrid-inlining patch as Laguna.
export ARC3_FRAME_MODE=full
# No ARC3_MAX_RUNTIME_S_PER_GAME override: default 7920s/132min (matches the
# historical Qwen ffa7gnsg baseline exactly) applies since MAX_NUM_SEQS=28
# >= 25 games (single wave, no queueing starvation -- see laguna-model-swap
# memory for why that matters).

./.venv/bin/python /opt/arc3/v12_run.py 2>&1 | tee /opt/arc3/v12.log || echo "runner exited $?"
gcloud storage cp /opt/arc3/v12.log "$BUCKET/$RUN_ID/v12-run.log" || true
pkill -TERM -f "vllm.entrypoints.openai.api_server" 2>/dev/null; sleep 10
pkill -KILL -f "vllm.entrypoints.openai.api_server" 2>/dev/null || true
echo "vLLM server stopped (teardown parity)"

gcloud storage rsync -r /opt/arc3/work "$BUCKET/$RUN_ID/runs"
echo done | gcloud storage cp - "$BUCKET/$RUN_ID/DONE"
for _t in 1 2 3; do
  if gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE"; then
    echo "teardown: $MIG resized to 0"; break
  fi
  echo "teardown attempt $_t FAILED for $MIG"
  if [ "$_t" = 3 ]; then
    echo "TEARDOWN FAILED $MIG at $(date -u +%FT%TZ)" | gcloud storage cp - "$BUCKET/$RUN_ID/TEARDOWN_FAILED" || true
  else
    sleep 15
  fi
done
