#!/bin/bash
# Self-contained: on ONE PRO 6000, serve Qwen3.6-27B (vLLM :1234), run a
# developer->system role-rewrite proxy (:1235), then run OPINE's synthesis loop
# on ls20 driven by codex -> proxy -> Qwen. Everything local; no tunnel, no SSH
# needed to drive it. Streams log + results to GCS and scales the MIG to 0 at end.
set -uo pipefail
export HOME=/home/son
export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:/usr/local/bin:$PATH"
exec > >(tee -a /var/log/arc3-qwenopine.log) 2>&1
echo "=== qwen36_opine startup $(date -u +%FT%TZ) ==="

BUCKET=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-bucket")
RUN_ID=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-run-id")
MIG=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-mig" || echo arc3-g4-qwenopine)
ZONE=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
SEED=$BUCKET/tufa-exact
echo "bucket=$BUCKET run=$RUN_ID mig=$MIG"

done_and_stop(){ gcloud storage cp /var/log/arc3-qwenopine.log "$BUCKET/$RUN_ID/qwenopine.log" 2>/dev/null; \
  echo "$1" | gcloud storage cp - "$BUCKET/$RUN_ID/$2" 2>/dev/null; \
  gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE" 2>/dev/null; }
# hard cost backstop
( sleep 12600; done_and_stop timeout SERVE_TIMEOUT ) &
( while true; do gcloud storage cp /var/log/arc3-qwenopine.log "$BUCKET/$RUN_ID/qwenopine.log" >/dev/null 2>&1; sleep 30; done ) &

apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential ninja-build ffmpeg

# ---- serve Qwen3.6 (vLLM :1234, 127.0.0.1) ----
mkdir -p /opt/arc3 && cd /opt/arc3
gcloud storage rsync -r "$SEED/model" /opt/arc3/vrfai-model
gcloud storage rsync -r "$SEED/wheelhouse" /opt/arc3/wheelhouse
curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"
uv venv --python 3.12.12 /opt/arc3/pysrv
uv pip install --python /opt/arc3/pysrv/bin/python --no-index --find-links /opt/arc3/wheelhouse \
  -r /opt/arc3/wheelhouse/requirements.lock --only-binary :all: --no-build-isolation || { done_and_stop vllm-deps SERVE_FAILED; exit 1; }
export USE_TF=0 TRANSFORMERS_NO_TF=1 TRANSFORMERS_NO_TORCHVISION=1 VLLM_NO_USAGE_STATS=1
nohup /opt/arc3/pysrv/bin/python -m vllm.entrypoints.openai.api_server \
  --model /opt/arc3/vrfai-model --served-model-name vrfai/Qwen3.6-27B-FP8 \
  --host 127.0.0.1 --port 1234 --tensor-parallel-size 1 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder \
  --generation-config vllm --enable-prefix-caching \
  --default-chat-template-kwargs '{"preserve_thinking": true}' \
  --reasoning-parser qwen3 --max-model-len 65536 > /opt/arc3/vllm.log 2>&1 &
for i in $(seq 1 150); do curl -s -m 3 http://127.0.0.1:1234/v1/models >/dev/null && break; sleep 10; done
curl -s -m 5 http://127.0.0.1:1234/v1/models >/dev/null || { gcloud storage cp /opt/arc3/vllm.log "$BUCKET/$RUN_ID/serve-vllm.log"; done_and_stop vllm-start SERVE_FAILED; exit 1; }
echo "vLLM ready"

# ---- role-rewrite proxy :1235 (stdlib python, developer->system) ----
gcloud storage cp "$BUCKET/code/opine_proxy.py" /opt/arc3/opine_proxy.py
nohup env PROXY_UPSTREAM=http://127.0.0.1:1234 PROXY_PORT=1235 python3 /opt/arc3/opine_proxy.py > /opt/arc3/proxy.log 2>&1 &
sleep 3; curl -s -m 5 http://127.0.0.1:1235/v1/models >/dev/null && echo "proxy up" || echo "proxy WARN"

# ---- codex + uv + OPINE ----
command -v uv >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash - >/dev/null 2>&1
  apt-get install -y -qq nodejs >/dev/null 2>&1
fi
mkdir -p "$HOME/.npm-global"; npm config set prefix "$HOME/.npm-global" >/dev/null 2>&1
export PATH="$HOME/.npm-global/bin:$PATH"
npm i -g @openai/codex@0.142.5 >/dev/null 2>&1
codex --version || { done_and_stop codex-install RUN_FAILED; exit 1; }

mkdir -p /opt/opine && gcloud storage cp "$BUCKET/code/opine_pkg.tgz" /tmp/o.tgz && tar xzf /tmp/o.tgz -C /opt/opine
cd /opt/opine/opine-world || { done_and_stop opine-extract RUN_FAILED; exit 1; }
uv sync >/dev/null 2>&1 || { done_and_stop uv-sync RUN_FAILED; exit 1; }

# ---- sanity: codex -> proxy -> Qwen writes a file ----
WS=/opt/opine/captest; rm -rf "$WS"; mkdir -p "$WS"; cd "$WS"
OPENAI_API_KEY="" timeout 180 codex -m vrfai/Qwen3.6-27B-FP8 -c model_reasoning_effort=high \
  -c 'model_provider="local_srv"' -c 'model_providers.local_srv.name="Local"' \
  -c 'model_providers.local_srv.base_url="http://127.0.0.1:1235/v1"' \
  -c 'model_providers.local_srv.wire_api="responses"' \
  -c 'model_providers.local_srv.requires_openai_auth=false' -c 'web_search="disabled"' \
  --disable plugins exec --sandbox workspace-write --skip-git-repo-check --ignore-user-config \
  --ignore-rules --cd "$WS" --json "Create a file cap.txt with the word QWENOK. Then stop." > /opt/arc3/captest.json 2>&1
tail -4 /opt/arc3/captest.json
echo "CAPTEST: $( [ -f "$WS/cap.txt" ] && cat "$WS/cap.txt" || echo MISSING )"
gcloud storage cp /opt/arc3/captest.json "$BUCKET/$RUN_ID/captest.json" 2>/dev/null
gcloud storage cp /opt/arc3/proxy.log "$BUCKET/$RUN_ID/proxy.log" 2>/dev/null

# ---- the run: OPINE ls20 with Qwen3.6 ----
cd /opt/opine/opine-world
OUT=/opt/opine/obs_out; rm -rf "$OUT"; mkdir -p "$OUT"
echo "=== launching OPINE ls20 with Qwen3.6-27B @ $(date -u +%FT%TZ) ==="
OPINE_CODEX_LOCAL=1 OPINE_CODEX_BASE_URL=http://127.0.0.1:1235/v1 OPENAI_API_KEY="" \
PYTHONPATH=src uv run python play.py \
  --game ls20 --max-actions 16 \
  --backend codex --codex-model vrfai/Qwen3.6-27B-FP8 --codex-effort high \
  --synthesis-interval 8 --output-dir "$OUT" \
  --synthesis-defer-min-moves-after-divergence 5 --synthesis-defer-max-errors 3 \
  --planner-after-levels-completed 1 2>&1 | tail -n +1
echo "=== OPINE exited $? @ $(date -u +%FT%TZ) ==="
gcloud storage rsync -r "$OUT" "$BUCKET/$RUN_ID/obs/" >/dev/null 2>&1
gcloud storage cp /opt/arc3/proxy.log "$BUCKET/$RUN_ID/proxy.log" 2>/dev/null
done_and_stop done DONE
echo "=== all done ==="
