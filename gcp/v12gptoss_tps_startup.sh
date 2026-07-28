#!/bin/bash
# gpt-oss-120b smoke test: boot vLLM 0.25.1 serving the model with the
# harmony-format flags (tool-call-parser openai, reasoning-parser
# openai_gptoss -- NOT poolside_v1/qwen3, this is a different model family),
# then fire the SAME prompt at reasoning_effort=low/medium/high/none and
# compare completion token counts -- confirms the field is actually being
# honored by the server before committing to a full harness run. No harness/
# game loop -- pure serving + reasoning_effort validation, ~10-15 min boot.
set -uo pipefail
export HOME="${HOME:-/root}"
exec > >(tee -a /var/log/arc3-startup.log) 2>&1
echo "=== gpt-oss-120b TPS + reasoning_effort smoke test $(date -u +%FT%TZ) ==="

BUCKET=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-bucket")
RUN_ID=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-run-id")
MIG=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-mig" || echo arc3-g4-gptoss-tps)
ZONE=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
MODEL_BUCKET_NAME=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-model-bucket-name")
MODEL_HF_ID=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-model-hf-id")
echo "bucket=$BUCKET run=$RUN_ID mig=$MIG model=$MODEL_HF_ID (bucket dir: $MODEL_BUCKET_NAME)"

mkdir -p /opt/arc3 && cd /opt/arc3
ATTEMPTS=$( (gcloud storage cat "$BUCKET/$RUN_ID/attempts" 2>/dev/null || echo 0) | tr -dc '0-9' ); ATTEMPTS=$(( ${ATTEMPTS:-0} + 1 ))
echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/attempts"; echo "boot attempt #$ATTEMPTS"
if [ "$ATTEMPTS" -gt 5 ]; then echo failed | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"; gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE" || true; exit 1; fi

( while true; do gcloud storage cp /var/log/arc3-startup.log "$BUCKET/$RUN_ID/startup-$(hostname).log" >/dev/null 2>&1; sleep 20; done ) &

apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential ninja-build

# ---- model: flat GCS dir (see laguna-model-swap memory for why flat, not hub/) --
mkdir -p /opt/arc3/model
echo "syncing model from gs://.../model-flat/$MODEL_BUCKET_NAME ..."
gcloud storage rsync -r "$BUCKET/model-flat/$MODEL_BUCKET_NAME" /opt/arc3/model
echo "model sync done: $(du -sh /opt/arc3/model | cut -f1)"

# ---- server: vLLM 0.25.1 (mainline support since 0.10.1, no nightly needed) --
curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"
uv venv --python 3.12.12 /opt/arc3/pysrv
uv pip install --python /opt/arc3/pysrv/bin/python "vllm==0.25.1" || {
  echo "vllm install failed"; echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/serverfail"; exit 1; }

MODEL_PATH=/opt/arc3/model
echo "model path: $MODEL_PATH ($(ls "$MODEL_PATH" | wc -l) files)"

export USE_TF=0 TRANSFORMERS_NO_TF=1 TRANSFORMERS_NO_TORCHVISION=1 VLLM_NO_USAGE_STATS=1
# No --trust-remote-code (native vLLM model class, no custom modeling code).
# No forced --attention-backend: FlashInfer's sink support is TRTLLM-only,
# which rejects SM120 -- let it auto-select TRITON_ATTN (the documented
# default for non-B200 cards). No forced --moe-backend: MXFP4 falls back to
# Marlin on SM120 (compute_cap 12.0, not the 10.0 official Blackwell path) --
# that's the confirmed-working stock path; flashinfer_cutlass is fragile and
# not obviously faster (a vLLM PR trying a formalized SM120 path was
# rejected for benchmarking SLOWER than Marlin). Ship default first.
nohup /opt/arc3/pysrv/bin/python -m vllm.entrypoints.openai.api_server \
  --model "$MODEL_PATH" --served-model-name "$MODEL_HF_ID" \
  --host 127.0.0.1 --port 1234 --tensor-parallel-size 1 \
  --enable-auto-tool-choice --tool-call-parser openai --reasoning-parser openai_gptoss \
  --max-num-seqs 16 \
  --max-model-len 65536 \
  > /opt/arc3/vllm.log 2>&1 &
for i in $(seq 1 120); do curl -s -m 3 http://127.0.0.1:1234/v1/models >/dev/null && break; sleep 10; done
if ! curl -s -m 5 http://127.0.0.1:1234/v1/models >/dev/null; then
  echo "SERVER FAILED TO START -- aborting attempt $ATTEMPTS"
  gcloud storage cp /opt/arc3/vllm.log "$BUCKET/$RUN_ID/serverlog-$(hostname)-$ATTEMPTS.log" || true
  echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/serverfail"; exit 1
fi
echo "vllm 0.25.1 ready: $MODEL_HF_ID"
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader | tee /opt/arc3/vram-at-ready.txt

# ---- reasoning_effort validation: same prompt, 4 effort levels -------------
cat > /opt/arc3/reasoning_effort_check.py << 'PYEOF'
import json, sys, time, urllib.request

URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL = sys.argv[1]
PROMPT = (
    "You are solving a grid puzzle. The board is a 64x64 grid of colored cells, "
    "encoded as ASCII letters (W=white, w=light gray, g=gray, G=dark gray, c=charcoal, "
    "B=black, M=magenta, P=pink, R=red, b=blue, S=sky blue, Y=yellow, O=orange, r=dark red, "
    "N=light green, p=purple). A black object sits at rows 15-23, columns 18-26, with white "
    "dots inside it. What strategy would you try next? Reason step by step."
)

def one_request(effort):
    body = {"model": MODEL, "messages": [{"role": "user", "content": PROMPT}], "max_tokens": 2000}
    if effort is not None:
        body["reasoning_effort"] = effort
    req = urllib.request.Request(
        URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read())
    dt = time.time() - t0
    usage = data.get("usage", {})
    finish_reason = data["choices"][0].get("finish_reason")
    return usage.get("completion_tokens", 0), dt, finish_reason

print("effort,completion_tokens,seconds,finish_reason", flush=True)
for effort in [None, "low", "medium", "high"]:
    try:
        tok, dt, fr = one_request(effort)
        print(f"{effort},{tok},{dt:.1f},{fr}", flush=True)
    except Exception as e:
        print(f"{effort},ERROR,{e!r},", flush=True)
PYEOF
/opt/arc3/pysrv/bin/python /opt/arc3/reasoning_effort_check.py "$MODEL_HF_ID" | tee /opt/arc3/reasoning_effort_result.csv
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader | tee /opt/arc3/vram-at-peak.txt

gcloud storage cp /opt/arc3/reasoning_effort_result.csv "$BUCKET/$RUN_ID/reasoning_effort_result.csv" || true
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
