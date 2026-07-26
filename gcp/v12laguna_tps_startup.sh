#!/bin/bash
# Laguna S 2.1 TPS smoke test: boot vLLM 0.25.1 serving one quantization,
# fire concurrent load at it, log measured throughput + peak VRAM, then
# self-teardown. No harness/game loop -- pure serving benchmark, so this stays
# a ~10 minute, cheap boot rather than a multi-hour run.
set -uo pipefail
export HOME="${HOME:-/root}"
exec > >(tee -a /var/log/arc3-startup.log) 2>&1
echo "=== laguna TPS smoke test $(date -u +%FT%TZ) ==="

BUCKET=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-bucket")
RUN_ID=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-run-id")
MIG=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-mig" || echo arc3-g4-laguna-tps)
ZONE=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
# Bare bucket dirname (matches upload_model.sh's BUCKET_MODEL_NAME, e.g. "Laguna-S-2.1-INT4")
# vs. the full HF repo id (e.g. "poolside/Laguna-S-2.1-INT4") -- kept separate because
# upload_model.sh strips the org prefix for the GCS path but vLLM/HF resolution needs it back.
MODEL_BUCKET_NAME=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-model-bucket-name")
MODEL_HF_ID=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-model-hf-id")
TEST_MINUTES=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-test-minutes" || echo 10)
echo "bucket=$BUCKET run=$RUN_ID mig=$MIG model=$MODEL_HF_ID (bucket dir: $MODEL_BUCKET_NAME) test_minutes=$TEST_MINUTES"

mkdir -p /opt/arc3 && cd /opt/arc3
ATTEMPTS=$( (gcloud storage cat "$BUCKET/$RUN_ID/attempts" 2>/dev/null || echo 0) | tr -dc '0-9' ); ATTEMPTS=$(( ${ATTEMPTS:-0} + 1 ))
echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/attempts"; echo "boot attempt #$ATTEMPTS"
if [ "$ATTEMPTS" -gt 5 ]; then echo failed | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"; gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE" || true; exit 1; fi

( while true; do gcloud storage cp /var/log/arc3-startup.log "$BUCKET/$RUN_ID/startup-$(hostname).log" >/dev/null 2>&1; sleep 20; done ) &

apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential ninja-build

# ---- sync model from GCS: flat resolved directory, not the raw HF hub cache -
# (the hub cache's snapshots/ dir is a tree of symlinks into blobs/; `gcloud
# storage rsync` doesn't preserve symlinks, so a synced hub/ cache is missing
# snapshots/ entirely on the far end, and even where it exists,
# snapshot_download(local_files_only=True) demands files upload_model.sh's
# allow_patterns deliberately skipped -- e.g. LICENSE.md -- and refuses to
# resolve as "incomplete" with outgoing traffic disabled. Symlinks were
# resolved to real files once, locally, into model-flat/ -- no HF cache
# machinery needed here at all, just files vLLM can load directly.)
mkdir -p /opt/arc3/model
echo "syncing model from gs://.../model-flat/$MODEL_BUCKET_NAME ..."
gcloud storage rsync -r "$BUCKET/model-flat/$MODEL_BUCKET_NAME" /opt/arc3/model
echo "model sync done: $(du -sh /opt/arc3/model | cut -f1)"

# ---- server: vLLM 0.25.1 (Poolside-validated minimum for Laguna S 2.1) ------
curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"
uv venv --python 3.12.12 /opt/arc3/pysrv
uv pip install --python /opt/arc3/pysrv/bin/python "vllm==0.25.1" || {
  echo "vllm install failed"; echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/serverfail"; exit 1; }

MODEL_PATH=/opt/arc3/model
echo "model path: $MODEL_PATH ($(ls "$MODEL_PATH" | wc -l) files)"

export USE_TF=0 TRANSFORMERS_NO_TF=1 TRANSFORMERS_NO_TORCHVISION=1 VLLM_NO_USAGE_STATS=1
# FlashInfer's prefill workspace buffer is a hardcoded, unconfigurable 256MB
# constant (vllm-project/vllm#25342, closed as not planned) -- too small for
# this model's attention shape and overflows on the profiling ("dummy") run,
# whose tensor sizes scale with --max-num-seqs. It was only ~58MB short
# (471MB needed vs 413MB available), so cap max-num-seqs well below vLLM's
# large default rather than switching attention backends -- confirmed 2026-07-26
# that --attention-backend FLASH_ATTN parses fine but then fails separately
# ("kv_cache_dtype not supported" for this quantized config), so staying on
# FlashInfer (the backend the one working public RTX-6000 benchmark used) and
# just shrinking the profiled batch is the more direct fix.
nohup /opt/arc3/pysrv/bin/python -m vllm.entrypoints.openai.api_server \
  --model "$MODEL_PATH" --served-model-name "$MODEL_HF_ID" \
  --trust-remote-code \
  --host 127.0.0.1 --port 1234 --tensor-parallel-size 1 \
  --enable-auto-tool-choice --tool-call-parser poolside_v1 --reasoning-parser poolside_v1 \
  --default-chat-template-kwargs '{"enable_thinking": true}' \
  --generation-config vllm --enable-prefix-caching \
  --max-num-seqs 16 \
  --max-model-len 65536 \
  > /opt/arc3/vllm.log 2>&1 &
VLLM_PID=$!
for i in $(seq 1 120); do curl -s -m 3 http://127.0.0.1:1234/v1/models >/dev/null && break; sleep 10; done
if ! curl -s -m 5 http://127.0.0.1:1234/v1/models >/dev/null; then
  echo "SERVER FAILED TO START -- aborting attempt $ATTEMPTS"
  gcloud storage cp /opt/arc3/vllm.log "$BUCKET/$RUN_ID/serverlog-$(hostname)-$ATTEMPTS.log" || true
  echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/serverfail"; exit 1
fi
echo "vllm 0.25.1 ready: $MODEL_HF_ID"
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader | tee /opt/arc3/vram-at-ready.txt

# ---- load generator: fire concurrent chat completions for TEST_MINUTES -----
cat > /opt/arc3/load_test.py << 'PYEOF'
import concurrent.futures, json, os, sys, time, urllib.request

DURATION_S = int(os.environ.get("TEST_MINUTES", "10")) * 60
CONCURRENCY = 8
PROMPT = (
    "You are solving a grid puzzle. The board is a 64x64 grid of colored cells, "
    "encoded as ASCII letters (W=white, w=light gray, g=gray, G=dark gray, c=charcoal, "
    "B=black, M=magenta, P=pink, R=red, b=blue, S=sky blue, Y=yellow, O=orange, r=dark red, "
    "N=light green, p=purple). Describe what strategy you would try next, in detail, "
    "reasoning step by step about the objects you can see."
)
URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL = sys.argv[1]

def one_request():
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": 300,
    }).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    dt = time.time() - t0
    usage = data.get("usage", {})
    return usage.get("completion_tokens", 0), dt

def worker(stop_at):
    total_tokens, total_time, n = 0, 0.0, 0
    while time.time() < stop_at:
        try:
            tok, dt = one_request()
            total_tokens += tok
            total_time += dt
            n += 1
        except Exception as e:
            print(f"[worker error] {e}", flush=True)
    return total_tokens, total_time, n

stop_at = time.time() + DURATION_S
t_start = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
    futures = [ex.submit(worker, stop_at) for _ in range(CONCURRENCY)]
    results = [f.result() for f in futures]
wall = time.time() - t_start
total_tokens = sum(r[0] for r in results)
total_reqs = sum(r[2] for r in results)
print(f"RESULT concurrency={CONCURRENCY} wall_s={wall:.1f} total_requests={total_reqs} "
      f"total_completion_tokens={total_tokens} tokens_per_sec={total_tokens/wall:.2f}")
PYEOF
TEST_MINUTES="$TEST_MINUTES" /opt/arc3/pysrv/bin/python /opt/arc3/load_test.py "$MODEL_HF_ID" | tee /opt/arc3/load_test_result.txt
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader | tee /opt/arc3/vram-at-peak.txt

gcloud storage cp /opt/arc3/load_test_result.txt "$BUCKET/$RUN_ID/load_test_result.txt" || true
gcloud storage cp /opt/arc3/vram-at-ready.txt "$BUCKET/$RUN_ID/vram-at-ready.txt" || true
gcloud storage cp /opt/arc3/vram-at-peak.txt "$BUCKET/$RUN_ID/vram-at-peak.txt" || true
gcloud storage cp /opt/arc3/vllm.log "$BUCKET/$RUN_ID/vllm.log" || true

pkill -TERM -f "vllm.entrypoints.openai.api_server" 2>/dev/null; sleep 5
pkill -KILL -f "vllm.entrypoints.openai.api_server" 2>/dev/null || true
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
