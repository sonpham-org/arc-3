#!/bin/bash
# V12FFA7: frame-full + ACTION7 fix + compact animation metadata.
# Identical to v12_startup.sh except: bundle = bundle-v12ff3 (baseline ARC3-Inference
# + the 6 frame-mode files, nothing else) and ARC3_FRAME_MODE=full set explicitly.
# Agent code = pristine upstream (commit a2dddac). Env = THEIR exact setup_env
# values. Only the infra scaffolding (GCS sync, guards) is ours.
#
# Server/weights (2026-07-29): RedHatAI/Qwen3.6-27B-FP8 on vLLM 0.25.1 --
# replaces vrfai/Qwen3.6-27B-FP8 on the pinned vLLM 0.19 wheelhouse. A 5-way
# quant-candidate A/B (see qwen-quant-candidates memory) found RedHatAI's FP8
# build scores statistically identically to vrfai's (2-pass mean 1.925 both)
# while avoiding vrfai's pathological kernel path on vLLM 0.25 -- a clean
# drop-in that unblocks the newer vLLM. Same flat-GCS sourcing pattern as
# every other post-vLLM-0.19 model (see laguna-model-swap memory for why flat,
# not the hub/ cache convention).
set -uo pipefail
export HOME="${HOME:-/root}"
exec > >(tee -a /var/log/arc3-startup.log) 2>&1
echo "=== ffa7g startup $(date -u +%FT%TZ) ==="

BUCKET=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-bucket")
RUN_ID=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-run-id")
MIG=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-mig" || echo arc3-g4-v12ffa7gnsg)
ZONE=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
SEED=$BUCKET/tufa-exact
echo "bucket=$BUCKET run=$RUN_ID mig=$MIG"

mkdir -p /opt/arc3 && cd /opt/arc3
# Low-overhead resource sampler (GPU/CPU/RAM every 20s -> GCS resource.log; out-of-band).
gcloud storage cp "$BUCKET/code/resource_sampler.sh" /opt/arc3/resource_sampler.sh 2>/dev/null \
  && bash /opt/arc3/resource_sampler.sh "$BUCKET" "$RUN_ID" || echo "resource sampler skipped"
ATTEMPTS=$( (gcloud storage cat "$BUCKET/$RUN_ID/attempts" 2>/dev/null || echo 0) | tr -dc '0-9' ); ATTEMPTS=$(( ${ATTEMPTS:-0} + 1 ))
echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/attempts"; echo "boot attempt #$ATTEMPTS"
if [ "$ATTEMPTS" -gt 8 ]; then echo failed | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"; gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE" || true; exit 1; fi

( while true; do gcloud storage cp /var/log/arc3-startup.log "$BUCKET/$RUN_ID/startup-$(hostname).log" >/dev/null 2>&1; sleep 60; done ) &

apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential ffmpeg ninja-build

# ---- pristine code + agent bundle -------------------------------------------
gcloud storage cp "$BUCKET/code/arc3-code-tufa0.tgz" /tmp/c.tgz && tar xzf /tmp/c.tgz -C /opt/arc3
BUNDLE_NAME=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-bundle" || echo "bundle-v12ffa7gnsg.tgz")
echo "bundle: $BUNDLE_NAME"
mkdir -p /opt/arc3/bundle && gcloud storage cp "$SEED/$BUNDLE_NAME" /tmp/b.tgz && tar xzf /tmp/b.tgz -C /opt/arc3/bundle
gcloud storage cp "$BUCKET/code/v12_run.py" /opt/arc3/v12_run.py

# ---- model: RedHatAI Qwen3.6-27B FP8, flat GCS dir --------------------------
MODEL_HF_ID="RedHatAI/Qwen3.6-27B-FP8"
mkdir -p /opt/arc3/model
gcloud storage rsync -r "$BUCKET/model-flat/Qwen3.6-27B-FP8-redhatai" /opt/arc3/model
echo "model files: $(ls /opt/arc3/model | wc -l) ($(du -sh /opt/arc3/model | cut -f1))"

# ---- server: vLLM 0.25.1, qwen parser family --------------------------------
curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"
uv venv --python 3.12.12 /opt/arc3/pysrv
uv pip install --python /opt/arc3/pysrv/bin/python "vllm==0.25.1" || {
  echo "vllm install failed"; echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/serverfail"; exit 1; }
export USE_TF=0 TRANSFORMERS_NO_TF=1 TRANSFORMERS_NO_TORCHVISION=1 VLLM_NO_USAGE_STATS=1
nohup /opt/arc3/pysrv/bin/python -m vllm.entrypoints.openai.api_server \
  --model /opt/arc3/model --served-model-name "$MODEL_HF_ID" \
  --host 127.0.0.1 --port 1234 --tensor-parallel-size 1 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3 \
  --default-chat-template-kwargs '{"preserve_thinking":true}' \
  --max-num-seqs 28 --max-model-len 65536 \
  > /opt/arc3/vllm.log 2>&1 &
for i in $(seq 1 120); do curl -s -m 3 http://127.0.0.1:1234/v1/models >/dev/null && break; sleep 10; done
if ! curl -s -m 5 http://127.0.0.1:1234/v1/models >/dev/null; then
  echo "SERVER FAILED TO START -- aborting attempt $ATTEMPTS"
  gcloud storage cp /opt/arc3/vllm.log "$BUCKET/$RUN_ID/serverlog-$(hostname)-$ATTEMPTS.log" || true
  echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/serverfail"; exit 1
fi
echo "vllm 0.25.1 ready: $MODEL_HF_ID"

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
mkdir -p /opt/arc3/work && rm -rf runs && ln -sfn /opt/arc3/work runs
( while true; do gcloud storage rsync -r /opt/arc3/work "$BUCKET/$RUN_ID/runs" >/dev/null 2>&1; sleep 120; done ) &

# Their exact setup_env (setup_commands.json), passed as real env so Make's ?= yields.
export LOCAL_ANALYZER_BASE_URL=http://127.0.0.1:1234/v1 OPENAI_BASE_URL=http://127.0.0.1:1234/v1
export LOCAL_ANALYZER_PROVIDER=vllm OPENAI_PROVIDER=vllm
export LOCAL_ANALYZER_MODEL_ID="$MODEL_HF_ID" INFERENCE_ANALYZER_MODEL="$MODEL_HF_ID"
export ARC3_REEXPLORE_STRICT=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-reexplore-strict" || echo "")
export ARC3_GAME_SUBSET=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-game-subset" || echo "")
export ARC3_STATE_GRAPH=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-state-graph" || echo "")
echo "subset=[$ARC3_GAME_SUBSET] state_graph=[$ARC3_STATE_GRAPH]"
export LOCAL_ANALYZER_APP_NAME="ARC3 Agent Harness"
export LOCAL_ANALYZER_CONTEXT_WINDOW=32768 LOCAL_ANALYZER_MAX_OUTPUT=0
export LOCAL_ANALYZER_TOOL_STEPS=0 LOCAL_ANALYZER_TOOL_TIMEOUT=30 LOCAL_ANALYZER_TOOL_OUTPUT_TOKENS=1024
export LOCAL_ANALYZER_YIELD_SECONDS=60
export LOCAL_ANALYZER_TEMPERATURE=0.6 LOCAL_ANALYZER_TOP_P=0.95 LOCAL_ANALYZER_TOP_K=20
export LOCAL_ANALYZER_ENABLE_THINKING=true
export MULTIMODAL_CONTEXT=current_grid MULTIMODAL_UPSCALE=4

export ARC3_FRAME_MODE=full   # clean full-frame retest (default is full anyway)
./.venv/bin/python /opt/arc3/v12_run.py 2>&1 | tee /opt/arc3/v12.log || echo "runner exited $?"
gcloud storage cp /opt/arc3/v12.log "$BUCKET/$RUN_ID/v12-run.log" || true
# teardown_commands equivalent: SIGTERM the vLLM server, then hard-kill
pkill -TERM -f "vllm.entrypoints.openai.api_server" 2>/dev/null; sleep 10
pkill -KILL -f "vllm.entrypoints.openai.api_server" 2>/dev/null || true
echo "vLLM server stopped (teardown parity)"

gcloud storage rsync -r /opt/arc3/work "$BUCKET/$RUN_ID/runs"
gcloud storage rsync -r -x '^(?!.*benchmark\.json$).*' "$BUCKET/$RUN_ID/runs" /tmp/prior >/dev/null 2>&1 || true
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