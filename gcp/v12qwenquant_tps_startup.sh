#!/bin/bash
# Qwen3.6-27B quant-candidate smoke test: boot vLLM 0.25.1 serving-only (qwen
# parser family, same as v12model_startup.sh's default "qwen" flavor -- these
# are all still Qwen3.6-27B derivatives, just a different quantization job),
# fire a handful of concurrent chat-completion requests at a fixed harness-
# shaped prompt, measure tok/s + VRAM, then self-teardown. No harness/game
# loop -- pure serving benchmark, same funnel as v12gptoss_tps_startup.sh /
# v12laguna_tps_startup.sh.
#
# HARD TIME CAP: a background watchdog forces teardown at arc3-time-cap-s
# regardless of what the main script is doing (protects GPU spend if a boot
# hangs -- e.g. a quant format vLLM can't auto-detect and sits retrying).
set -uo pipefail
export HOME="${HOME:-/root}"
exec > >(tee -a /var/log/arc3-startup.log) 2>&1
echo "=== Qwen quant-candidate TPS smoke test $(date -u +%FT%TZ) ==="

BUCKET=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-bucket")
RUN_ID=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-run-id")
MIG=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-mig" || echo arc3-g4-qwenquant-tps)
ZONE=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
MODEL_BUCKET_NAME=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-model-bucket-name")
MODEL_HF_ID=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-model-hf-id")
QUANT_LABEL=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-quant-label" || echo "$MODEL_BUCKET_NAME")
TIME_CAP_S=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-time-cap-s" || echo 1200)
echo "bucket=$BUCKET run=$RUN_ID mig=$MIG model=$MODEL_HF_ID label=$QUANT_LABEL time_cap_s=$TIME_CAP_S"

mkdir -p /opt/arc3 && cd /opt/arc3
ATTEMPTS=$( (gcloud storage cat "$BUCKET/$RUN_ID/attempts" 2>/dev/null || echo 0) | tr -dc '0-9' ); ATTEMPTS=$(( ${ATTEMPTS:-0} + 1 ))
echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/attempts"; echo "boot attempt #$ATTEMPTS"
if [ "$ATTEMPTS" -gt 3 ]; then echo failed | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"; gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE" || true; exit 1; fi

( while true; do gcloud storage cp /var/log/arc3-startup.log "$BUCKET/$RUN_ID/startup-$(hostname).log" >/dev/null 2>&1; sleep 20; done ) &

# ---- hard time cap watchdog: forces teardown no matter what's hung --------
( sleep "$TIME_CAP_S"
  echo "TIME CAP ($TIME_CAP_S s) HIT -- forcing teardown at $(date -u +%FT%TZ)" | gcloud storage cp - "$BUCKET/$RUN_ID/TIMECAP" || true
  gcloud storage cp /opt/arc3/vllm.log "$BUCKET/$RUN_ID/vllm-at-timecap.log" 2>/dev/null || true
  for _t in 1 2 3; do
    gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE" && break
    sleep 10
  done
) &
WATCHDOG_PID=$!

apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential ninja-build

# ---- model: flat GCS dir (see laguna-model-swap memory for why flat, not hub/) --
mkdir -p /opt/arc3/model
echo "syncing model from gs://.../model-flat/$MODEL_BUCKET_NAME ..."
gcloud storage rsync -r "$BUCKET/model-flat/$MODEL_BUCKET_NAME" /opt/arc3/model
echo "model sync done: $(du -sh /opt/arc3/model | cut -f1)"

# ---- server: vLLM 0.25.1, qwen parser family (default flavor in v12model_startup.sh) --
curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"
uv venv --python 3.12.12 /opt/arc3/pysrv
uv pip install --python /opt/arc3/pysrv/bin/python "vllm==0.25.1" || {
  echo "vllm install failed"; echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/serverfail"; exit 1; }

MODEL_PATH=/opt/arc3/model
echo "model path: $MODEL_PATH ($(ls "$MODEL_PATH" | wc -l) files)"

export USE_TF=0 TRANSFORMERS_NO_TF=1 TRANSFORMERS_NO_TORCHVISION=1 VLLM_NO_USAGE_STATS=1
# No forced --attention-backend / --quantization: let vLLM auto-detect from
# each checkpoint's own config.json / hf_quant_config.json (same "ship
# default first" policy as gpt-oss/Laguna -- only add an override if boot
# actually fails with a concrete error naming the missing piece).
nohup /opt/arc3/pysrv/bin/python -m vllm.entrypoints.openai.api_server \
  --model "$MODEL_PATH" --served-model-name "$MODEL_HF_ID" \
  --host 127.0.0.1 --port 1234 --tensor-parallel-size 1 \
  --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3 \
  --default-chat-template-kwargs '{"preserve_thinking":true}' \
  --max-num-seqs 16 \
  --max-model-len 65536 \
  > /opt/arc3/vllm.log 2>&1 &
for i in $(seq 1 120); do curl -s -m 3 http://127.0.0.1:1234/v1/models >/dev/null && break; sleep 10; done
if ! curl -s -m 5 http://127.0.0.1:1234/v1/models >/dev/null; then
  echo "SERVER FAILED TO START ($QUANT_LABEL) -- aborting attempt $ATTEMPTS"
  gcloud storage cp /opt/arc3/vllm.log "$BUCKET/$RUN_ID/serverlog-$(hostname)-$ATTEMPTS.log" || true
  echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/serverfail"
  kill "$WATCHDOG_PID" 2>/dev/null || true
  for _t in 1 2 3; do gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE" && break; sleep 10; done
  exit 1
fi
echo "vllm 0.25.1 ready: $MODEL_HF_ID ($QUANT_LABEL)"
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader | tee /opt/arc3/vram-at-ready.txt

# ---- TPS check: N concurrent harness-shaped completions -------------------
cat > /opt/arc3/tps_check.py << 'PYEOF'
import json, sys, time, threading, urllib.request

URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL = sys.argv[1]
LABEL = sys.argv[2]
CONCURRENCY = int(sys.argv[3]) if len(sys.argv) > 3 else 8
PROMPT = (
    "You are solving a grid puzzle. The board is a 64x64 grid of colored cells, "
    "encoded as ASCII letters (W=white, w=light gray, g=gray, G=dark gray, c=charcoal, "
    "B=black, M=magenta, P=pink, R=red, b=blue, S=sky blue, Y=yellow, O=orange, r=dark red, "
    "N=light green, p=purple). A black object sits at rows 15-23, columns 18-26, with white "
    "dots inside it. What strategy would you try next? Reason step by step, then propose "
    "one concrete action."
)

results = []
lock = threading.Lock()

def one_request(i):
    body = {"model": MODEL, "messages": [{"role": "user", "content": PROMPT}], "max_tokens": 1024}
    req = urllib.request.Request(
        URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
        dt = time.time() - t0
        usage = data.get("usage", {})
        with lock:
            results.append((i, usage.get("completion_tokens", 0), dt,
                             data["choices"][0].get("finish_reason")))
    except Exception as e:
        with lock:
            results.append((i, "ERROR", repr(e), None))

t_start = time.time()
threads = [threading.Thread(target=one_request, args=(i,)) for i in range(CONCURRENCY)]
for t in threads: t.start()
for t in threads: t.join()
wall = time.time() - t_start

print(f"label,concurrency,wall_s")
print(f"{LABEL},{CONCURRENCY},{wall:.1f}")
print("i,completion_tokens,seconds,finish_reason")
total_tok = 0
for i, tok, dt, fr in sorted(results):
    print(f"{i},{tok},{dt},{fr}")
    if isinstance(tok, int):
        total_tok += tok
print(f"AGGREGATE: total_completion_tokens={total_tok} wall_s={wall:.1f} tok_per_s={total_tok/wall:.1f}")
PYEOF
/opt/arc3/pysrv/bin/python /opt/arc3/tps_check.py "$MODEL_HF_ID" "$QUANT_LABEL" 8 | tee /opt/arc3/tps_result.csv
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader | tee /opt/arc3/vram-at-peak.txt

gcloud storage cp /opt/arc3/tps_result.csv "$BUCKET/$RUN_ID/tps_result.csv" || true
gcloud storage cp /opt/arc3/vram-at-ready.txt "$BUCKET/$RUN_ID/vram-at-ready.txt" || true
gcloud storage cp /opt/arc3/vram-at-peak.txt "$BUCKET/$RUN_ID/vram-at-peak.txt" || true
gcloud storage cp /opt/arc3/vllm.log "$BUCKET/$RUN_ID/vllm.log" || true

kill "$WATCHDOG_PID" 2>/dev/null || true
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
