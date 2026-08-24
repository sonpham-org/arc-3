#!/bin/bash
# Three-arm cross-game influence study on the compact-English checkpoint-8
# general-thinking champion with pinned Unsloth NVFP4. Gameplay remains 28-way;
# the GPU curator arms add one asynchronous persistent request stream.
set -euo pipefail
export HOME="${HOME:-/root}"
exec > >(tee -a /var/log/arc3-qwen38-startup.log) 2>&1

meta() {
  curl -sf -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"
}

BUCKET=$(meta arc3-bucket)
RUN_ID=$(meta arc3-run-id)
MIG=$(meta arc3-mig)
BUNDLE_NAME=$(meta arc3-bundle)
INFLUENCE_MODE=$(meta arc3-influence-mode)
RUNNER_OBJECT=$(meta arc3-runner-object)
CURATOR_OBJECT=$(meta arc3-curator-object)
CPU_BOOTSTRAP_OBJECT=$(meta arc3-cpu-bootstrap-object)
SEED_OBJECT=$(meta arc3-seed-object)
ZONE=$(curl -sf -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
SEED="$BUCKET/tufa-exact"
MODEL_ID="unsloth/Qwen3.8-27B-NVFP4"
MODEL_REVISION="7d6f8d4d72f56b92b3cdbf22f156b90e1bab0108"
SERVED_MODEL_NAME="$MODEL_ID"
TEARDOWN_STARTED=0

sync_all() {
  if [ -d /opt/arc3/work ]; then
    timeout 45 gcloud storage rsync -r /opt/arc3/work \
      "$BUCKET/$RUN_ID/runs" >/dev/null 2>&1 || true
  fi
  [ -f /opt/arc3/v12.log ] && timeout 15 gcloud storage cp \
    /opt/arc3/v12.log "$BUCKET/$RUN_ID/v12-run.log" >/dev/null 2>&1 || true
  [ -f /opt/arc3/vllm.log ] && timeout 15 gcloud storage cp \
    /opt/arc3/vllm.log "$BUCKET/$RUN_ID/vllm.log" >/dev/null 2>&1 || true
  [ -f /opt/arc3/model-smoke.json ] && timeout 10 gcloud storage cp \
    /opt/arc3/model-smoke.json "$BUCKET/$RUN_ID/model-smoke.json" >/dev/null 2>&1 || true
  [ -f /opt/arc3/model-info.json ] && timeout 10 gcloud storage cp \
    /opt/arc3/model-info.json "$BUCKET/$RUN_ID/model-info.json" >/dev/null 2>&1 || true
  [ -f /opt/arc3/serving-environment.txt ] && timeout 10 gcloud storage cp \
    /opt/arc3/serving-environment.txt "$BUCKET/$RUN_ID/serving-environment.txt" >/dev/null 2>&1 || true
  if [ -d /opt/arc3/curator ]; then
    timeout 45 gcloud storage rsync -r /opt/arc3/curator \
      "$BUCKET/$RUN_ID/curator" >/dev/null 2>&1 || true
  fi
  if [ -d /opt/arc3/reviewed-themes ]; then
    timeout 90 gcloud storage rsync -r /opt/arc3/reviewed-themes \
      "$BUCKET/$RUN_ID/reviewed-themes" >/dev/null 2>&1 || true
  fi
  timeout 15 gcloud storage cp /var/log/arc3-qwen38-startup.log \
    "$BUCKET/$RUN_ID/startup-$(hostname).log" >/dev/null 2>&1 || true
}

teardown() {
  [ "$TEARDOWN_STARTED" = 1 ] && return
  TEARDOWN_STARTED=1
  trap - EXIT TERM INT
  sync_all
  pkill -TERM -f "nvfp4_cross_game_curator.py" 2>/dev/null || true
  pkill -TERM -f "cross_game_theme_influence_sidecar.py" 2>/dev/null || true
  pkill -TERM -f "llama-server" 2>/dev/null || true
  pkill -TERM -f "vllm.entrypoints.openai.api_server" 2>/dev/null || true
  for attempt in 1 2 3; do
    if gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE"; then
      echo "teardown verified request: $MIG -> 0"
      return
    fi
    sleep 10
  done
  echo "TEARDOWN FAILED $MIG $(date -u +%FT%TZ)" | gcloud storage cp - \
    "$BUCKET/$RUN_ID/TEARDOWN_FAILED" || true
}
trap teardown EXIT TERM INT

case "$INFLUENCE_MODE" in
  cpu_reviewed_themes|gpu_theme_curator|gpu_world_model_curator) ;;
  *) echo "invalid influence mode: $INFLUENCE_MODE" | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"; exit 1 ;;
esac
echo "=== Qwen3.8 NVFP4 cross-game study $(date -u +%FT%TZ) run=$RUN_ID mig=$MIG mode=$INFLUENCE_MODE ==="

# Hard cost guard: 3h15m from VM startup, including package/model download.
(
  sleep 11700
  echo "hard lifetime reached $(date -u +%FT%TZ)" | gcloud storage cp - \
    "$BUCKET/$RUN_ID/HARD_TIMEOUT" || true
  pkill -TERM -f v12_run.py 2>/dev/null || true
  sleep 20
  pkill -KILL -f v12_run.py 2>/dev/null || true
  sync_all
  gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE" || true
) &

# A Spot recreation would restart the whole benchmark and contaminate the run.
# Refuse every boot after the first and immediately scale the owned MIG to zero.
ATTEMPTS=$( (gcloud storage cat "$BUCKET/$RUN_ID/attempts" 2>/dev/null || echo 0) | tr -dc '0-9')
ATTEMPTS=$(( ${ATTEMPTS:-0} + 1 ))
echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/attempts"
if [ "$ATTEMPTS" -gt 1 ]; then
  echo "preemption/recreation detected; duplicate gameplay forbidden" | gcloud storage cp - \
    "$BUCKET/$RUN_ID/FAILED"
  exit 1
fi

mkdir -p /opt/arc3/work /opt/arc3/bundle /opt/arc3/qwen38-model
(while true; do sync_all; sleep 120; done) &

gcloud storage cp "$BUCKET/code/resource_sampler.sh" /opt/arc3/resource_sampler.sh 2>/dev/null \
  && bash /opt/arc3/resource_sampler.sh "$BUCKET" "$RUN_ID" \
  || echo "resource sampler skipped"

apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential ffmpeg ninja-build
cd /opt/arc3
gcloud storage cp "$BUCKET/code/arc3-code-tufa0.tgz" /tmp/code.tgz
tar xzf /tmp/code.tgz -C /opt/arc3
gcloud storage cp "$SEED/$BUNDLE_NAME" /tmp/bundle.tgz
tar xzf /tmp/bundle.tgz -C /opt/arc3/bundle
gcloud storage cp "$RUNNER_OBJECT" /opt/arc3/v12_run.py
gcloud storage cp "$CURATOR_OBJECT" /opt/arc3/nvfp4_cross_game_curator.py
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv venv --python 3.12.12 /opt/arc3/pysrv
export UV_HTTP_TIMEOUT=600 UV_HTTP_RETRIES=10
INSTALL_STATUS=1
for install_attempt in 1 2 3; do
  if uv pip install --python /opt/arc3/pysrv/bin/python "vllm==0.27.1" huggingface_hub; then
    INSTALL_STATUS=0
    break
  else
    INSTALL_STATUS=$?
    echo "vLLM install attempt $install_attempt failed status=$INSTALL_STATUS"
    sleep 10
  fi
done
if [ "$INSTALL_STATUS" -ne 0 ]; then
  echo "vLLM install failed after guarded retries status=$INSTALL_STATUS" | \
    gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"
  exit "$INSTALL_STATUS"
fi
export PATH="/opt/arc3/pysrv/bin:$PATH"

/opt/arc3/pysrv/bin/python - <<'PYVERS' > /opt/arc3/serving-environment.txt
import platform
import torch
import transformers
import vllm
print("python", platform.python_version())
print("vllm", vllm.__version__)
print("torch", torch.__version__)
print("transformers", transformers.__version__)
print("cuda", torch.version.cuda)
PYVERS

# Download only the immutable Unsloth NVFP4 snapshot. MTP files may exist in the
# repository, but vLLM is launched without speculative_config, so MTP is off.
/opt/arc3/pysrv/bin/python - <<'PYMODEL'
import json
from huggingface_hub import HfApi, snapshot_download

model_id = "unsloth/Qwen3.8-27B-NVFP4"
revision = "7d6f8d4d72f56b92b3cdbf22f156b90e1bab0108"
info = HfApi().model_info(model_id, revision=revision)
if info.sha != revision:
    raise RuntimeError(f"Resolved model revision drift: {info.sha} != {revision}")
snapshot_download(
    repo_id=model_id,
    revision=revision,
    local_dir="/opt/arc3/qwen38-model",
    max_workers=8,
)
with open("/opt/arc3/model-info.json", "w", encoding="utf-8") as fh:
    json.dump(
        {
            "model_id": model_id,
            "revision": info.sha,
            "last_modified": str(info.last_modified),
            "library_name": info.library_name,
            "pipeline_tag": info.pipeline_tag,
            "quantization": "NVFP4 compressed-tensors",
            "mtp_enabled": False,
        },
        fh,
        indent=2,
    )
print(f"resolved model: {model_id}@{info.sha}", flush=True)
PYMODEL

export USE_TF=0 TRANSFORMERS_NO_TF=1 TRANSFORMERS_NO_TORCHVISION=1 VLLM_NO_USAGE_STATS=1
nohup /opt/arc3/pysrv/bin/python -m vllm.entrypoints.openai.api_server \
  --model /opt/arc3/qwen38-model --served-model-name "$SERVED_MODEL_NAME" \
  --host 127.0.0.1 --port 1234 --tensor-parallel-size 1 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder \
  --generation-config vllm --enable-prefix-caching \
  --default-chat-template-kwargs '{"preserve_thinking": true}' \
  --reasoning-parser qwen3 --max-model-len 65536 \
  > /opt/arc3/vllm.log 2>&1 &

for _ in $(seq 1 120); do
  curl -s -m 3 http://127.0.0.1:1234/v1/models >/dev/null && break
  sleep 10
done
if ! curl -s -m 5 http://127.0.0.1:1234/v1/models >/dev/null; then
  echo "vLLM failed" | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"
  sync_all
  exit 1
fi

# Serving smoke test before any paid gameplay. This exercises the model's new
# reasoning template and confirms that the OpenAI-compatible response parses.
/opt/arc3/pysrv/bin/python - <<'PYSMOKE'
import json
import urllib.request

payload = {
    "model": "unsloth/Qwen3.8-27B-NVFP4",
    "messages": [{"role": "user", "content": "Return exactly the word READY."}],
    "temperature": 0.0,
    "max_tokens": 128,
    "chat_template_kwargs": {"enable_thinking": False, "preserve_thinking": True},
}
request = urllib.request.Request(
    "http://127.0.0.1:1234/v1/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(request, timeout=180) as response:
    result = json.loads(response.read().decode("utf-8"))
assert result.get("choices"), result
with open("/opt/arc3/model-smoke.json", "w", encoding="utf-8") as fh:
    json.dump(result, fh, indent=2)
print("Qwen3.8 Unsloth NVFP4 serving smoke passed", flush=True)
PYSMOKE
sync_all

# Install the exact environment and run the unmodified champion on all official
# 25 games with the same analyzer settings used for Qwen3.6.
cd /opt/arc3/ARC3-Inference
export CONFIG_PATH=configs/tufa0.json TAAF_PERIODIC_SAVE_INTERVAL_S=120
make install-a108
mkdir -p /opt/arc3/engwheels
gcloud storage rsync -r "$SEED/engine-wheels" /opt/arc3/engwheels
uv pip install --python ./.venv/bin/python --no-deps \
  /opt/arc3/engwheels/arc_agi-0.9.8-py3-none-any.whl \
  /opt/arc3/engwheels/arcengine-0.9.3-py3-none-any.whl
rm -rf runs && ln -sfn /opt/arc3/work runs
mkdir -p /opt/arc3/work/artifacts

export LOCAL_ANALYZER_BASE_URL=http://127.0.0.1:1234/v1 OPENAI_BASE_URL=http://127.0.0.1:1234/v1
export LOCAL_ANALYZER_PROVIDER=vllm OPENAI_PROVIDER=vllm
export LOCAL_ANALYZER_MODEL_ID="$SERVED_MODEL_NAME" INFERENCE_ANALYZER_MODEL="$SERVED_MODEL_NAME"
export LOCAL_ANALYZER_APP_NAME="ARC3 Agent Harness"
export LOCAL_ANALYZER_CONTEXT_WINDOW=32768 LOCAL_ANALYZER_MAX_OUTPUT=0
export LOCAL_ANALYZER_TOOL_STEPS=0 LOCAL_ANALYZER_TOOL_TIMEOUT=30 LOCAL_ANALYZER_TOOL_OUTPUT_TOKENS=1024
export LOCAL_ANALYZER_YIELD_SECONDS=60 LOCAL_ANALYZER_TEMPERATURE=1.0 LOCAL_ANALYZER_TOP_P=0.95 LOCAL_ANALYZER_TOP_K=20
export LOCAL_ANALYZER_ENABLE_THINKING=true MULTIMODAL_CONTEXT=current_grid MULTIMODAL_UPSCALE=4
export ARC3_REEXPLORE_STRICT="" ARC3_GAME_SUBSET="" ARC3_STATE_GRAPH="" ARC3_FRAME_MODE=full

if [ "$INFLUENCE_MODE" = cpu_reviewed_themes ]; then
  export BUCKET RUN_ID
  export ARC3_COMMON_THEMES_PATH=/opt/arc3/reviewed-themes/themes-reviewed.json
  export ARC3_COMMON_THEMES_INJECTION_LOG=/opt/arc3/reviewed-themes/gameplay-theme-injections.jsonl
  export ARC3_COMMON_THEMES_MAX=12 ARC3_COMMON_THEMES_MAX_CHARS=6500
  export COLLECTOR_SHA256_EXPECTED=09be80484392480ad59a2ea69377b8150bbc22e6d4794d50b6e7287fa9d73159
  export BASE_SHA256_EXPECTED=ce879c58fc996d73ecc932fcf4254140fcb17389fe0c885e03bfd839b819bf1a
  export SHARDED_SHA256_EXPECTED=959555926ad0355e83d5191b5190c8821241ff68a8ddbf89b887ca8125ab7e17
  export SEED_OBJECT
  gcloud storage cp "$CPU_BOOTSTRAP_OBJECT" /opt/arc3/cpu-reviewed-bootstrap.sh
  bash /opt/arc3/cpu-reviewed-bootstrap.sh
  test -s "$ARC3_COMMON_THEMES_PATH"
  test -s /opt/arc3/reviewed-themes/collector.pid
else
  mkdir -p /opt/arc3/curator
  export ARC3_COMMON_THEMES_PATH=/opt/arc3/curator/ledger.json
  export ARC3_COMMON_THEMES_INJECTION_LOG=/opt/arc3/curator/gameplay-injections.jsonl
  export ARC3_COMMON_THEMES_MAX=12 ARC3_COMMON_THEMES_MAX_CHARS=6000
  CURATOR_MODE=themes
  CURATOR_EVENTS_DIR=/opt/arc3/work/artifacts
  if [ "$INFLUENCE_MODE" = gpu_world_model_curator ]; then
    CURATOR_MODE=world_models
    CURATOR_EVENTS_DIR=/opt/arc3/work
  fi
  nohup /opt/arc3/pysrv/bin/python /opt/arc3/nvfp4_cross_game_curator.py \
    --mode "$CURATOR_MODE" --events-dir "$CURATOR_EVENTS_DIR" \
    --output-dir /opt/arc3/curator --base-url http://127.0.0.1:1234/v1 \
    --model "$SERVED_MODEL_NAME" --max-evidence 10 --min-games 3 \
    --max-entries 6 --poll-seconds 15 --request-timeout 900 --max-tokens 3600 \
    --temperature 0.6 --top-p 0.95 --top-k 20 \
    > /opt/arc3/curator/curator.log 2>&1 &
  CURATOR_PID=$!
  echo "$CURATOR_PID" > /opt/arc3/curator/curator.pid
  for _ in $(seq 1 30); do
    [ -s /opt/arc3/curator/ledger.json ] && [ -s /opt/arc3/curator/health.json ] && break
    sleep 1
  done
  kill -0 "$CURATOR_PID"
  test -s "$ARC3_COMMON_THEMES_PATH"
fi
sync_all

set +e
./.venv/bin/python /opt/arc3/v12_run.py 2>&1 | tee /opt/arc3/v12.log
RUN_STATUS=${PIPESTATUS[0]}
set -e
sync_all
if [ "$RUN_STATUS" -ne 0 ]; then
  echo "runner failed with status $RUN_STATUS" | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"
  exit "$RUN_STATUS"
fi

echo done | gcloud storage cp - "$BUCKET/$RUN_ID/DONE"
exit 0

