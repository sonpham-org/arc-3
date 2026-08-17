#!/bin/bash
# One-off, clean model swap: native TAAF checkpoint-8 champion with the
# official Qwen/Qwen3.8-27B-FP8 checkpoint. All harness and sampling settings
# remain identical to the Qwen3.6 full-25 baseline.
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
REASONING_EFFORT=$(meta arc3-reasoning-effort)
ARC3_VARIANT=$(meta arc3-variant 2>/dev/null || printf '%s' checkpoint8)
ZONE=$(curl -sf -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
SEED="$BUCKET/tufa-exact"
MODEL_ID="Qwen/Qwen3.8-27B-FP8"
MODEL_REVISION="017b9c7af6b5689d5dd426a76e0bc077eb5ca20a"
SERVED_MODEL_NAME="$MODEL_ID"
TEARDOWN_STARTED=0

case "$ARC3_VARIANT" in
  checkpoint8)
    EXPECTED_BUNDLE_NAME="bundle-taaf-plain-checkpoint8-20260812.tgz"
    EXPECTED_BUNDLE_SHA256="f9e12ec74f869c200210c9b44cb030361af2a62718e6ca1feb1e434ffd146ee6"
    MULTIMODAL_UPSCALE_VALUE=8
    ;;
  kaggle-203-nocap-control)
    # One-variable control derived from Kaggle submission 55551321 / script
    # version 342637750: pristine author TAAF removes only the 19 checkpoint
    # lines, while the scored notebook's 4x current-grid transport is retained.
    EXPECTED_BUNDLE_NAME="bundle-taaf-plain-author-20260812-132401.tgz"
    EXPECTED_BUNDLE_SHA256="7d030b62d95eed54899e3a8d0abf49281230d9f1ae7dcb72831a1cff86b18ce3"
    MULTIMODAL_UPSCALE_VALUE=4
    ;;
  *)
    echo "unsupported ARC3 variant: $ARC3_VARIANT" >&2
    exit 2
    ;;
esac

if [ "$BUNDLE_NAME" != "$EXPECTED_BUNDLE_NAME" ]; then
  echo "refusing non-champion bundle: got $BUNDLE_NAME, expected $EXPECTED_BUNDLE_NAME" >&2
  exit 2
fi

case "$REASONING_EFFORT" in
  xhigh|medium|low) ;;
  *)
    echo "unsupported Qwen3.8 reasoning effort: $REASONING_EFFORT" >&2
    exit 2
    ;;
esac

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
  [ -f /opt/arc3/reasoning-config.json ] && timeout 10 gcloud storage cp \
    /opt/arc3/reasoning-config.json "$BUCKET/$RUN_ID/reasoning-config.json" >/dev/null 2>&1 || true
  timeout 15 gcloud storage cp /var/log/arc3-qwen38-startup.log \
    "$BUCKET/$RUN_ID/startup-$(hostname).log" >/dev/null 2>&1 || true
}

teardown() {
  [ "$TEARDOWN_STARTED" = 1 ] && return
  TEARDOWN_STARTED=1
  trap - EXIT TERM INT
  sync_all
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

echo "=== Qwen3.8 model swap $(date -u +%FT%TZ) run=$RUN_ID mig=$MIG variant=$ARC3_VARIANT reasoning_effort=$REASONING_EFFORT upscale=$MULTIMODAL_UPSCALE_VALUE ==="

mkdir -p /opt/arc3
python3 - "$REASONING_EFFORT" "$ARC3_VARIANT" "$MULTIMODAL_UPSCALE_VALUE" <<'PYCONFIG' > /opt/arc3/reasoning-config.json
import json
import sys

effort = sys.argv[1]
variant = sys.argv[2]
upscale = int(sys.argv[3])
json.dump(
    {
        "enable_thinking": True,
        "preserve_thinking": True,
        "reasoning_effort": effort,
        "variant": variant,
        "multimodal_upscale": upscale,
        "control_surface": "vLLM default_chat_template_kwargs",
    },
    sys.stdout,
    indent=2,
)
print()
PYCONFIG

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
echo "$EXPECTED_BUNDLE_SHA256  /tmp/bundle.tgz" | sha256sum -c -
tar xzf /tmp/bundle.tgz -C /opt/arc3/bundle
gcloud storage cp "$BUCKET/code/v12_run.py" /opt/arc3/v12_run.py
gcloud storage rsync -r "$SEED/wheelhouse" /opt/arc3/wheelhouse

curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv venv --python 3.12.12 /opt/arc3/pysrv
uv pip install --python /opt/arc3/pysrv/bin/python --no-index \
  --find-links /opt/arc3/wheelhouse -r /opt/arc3/wheelhouse/requirements.lock \
  --only-binary :all: --no-build-isolation
export PATH="/opt/arc3/pysrv/bin:$PATH"

# Download only the immutable official FP8 snapshot. Record the resolved commit
# so the experiment stays reproducible even if the Hugging Face branch moves.
/opt/arc3/pysrv/bin/python - "$MODEL_REVISION" <<'PYMODEL'
import json
import sys
from huggingface_hub import HfApi, snapshot_download

model_id = "Qwen/Qwen3.8-27B-FP8"
revision = sys.argv[1]
info = HfApi().model_info(model_id, revision=revision)
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
            "requested_revision": revision,
            "revision": info.sha,
            "last_modified": str(info.last_modified),
            "library_name": info.library_name,
            "pipeline_tag": info.pipeline_tag,
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
  --default-chat-template-kwargs "{\"preserve_thinking\":true,\"reasoning_effort\":\"$REASONING_EFFORT\"}" \
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
    "model": "Qwen/Qwen3.8-27B-FP8",
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
print("Qwen3.8 serving smoke passed", flush=True)
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

export LOCAL_ANALYZER_BASE_URL=http://127.0.0.1:1234/v1 OPENAI_BASE_URL=http://127.0.0.1:1234/v1
export LOCAL_ANALYZER_PROVIDER=vllm OPENAI_PROVIDER=vllm
export LOCAL_ANALYZER_MODEL_ID="$SERVED_MODEL_NAME" INFERENCE_ANALYZER_MODEL="$SERVED_MODEL_NAME"
export LOCAL_ANALYZER_APP_NAME="ARC3 Agent Harness"
export LOCAL_ANALYZER_CONTEXT_WINDOW=32768 LOCAL_ANALYZER_MAX_OUTPUT=0
export LOCAL_ANALYZER_TOOL_STEPS=0 LOCAL_ANALYZER_TOOL_TIMEOUT=30 LOCAL_ANALYZER_TOOL_OUTPUT_TOKENS=1024
export LOCAL_ANALYZER_YIELD_SECONDS=60 LOCAL_ANALYZER_TEMPERATURE=0.6 LOCAL_ANALYZER_TOP_P=0.95 LOCAL_ANALYZER_TOP_K=20
export LOCAL_ANALYZER_ENABLE_THINKING=true MULTIMODAL_CONTEXT=current_grid MULTIMODAL_UPSCALE="$MULTIMODAL_UPSCALE_VALUE"
export ARC3_REEXPLORE_STRICT="" ARC3_GAME_SUBSET="" ARC3_STATE_GRAPH="" ARC3_FRAME_MODE=full

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
