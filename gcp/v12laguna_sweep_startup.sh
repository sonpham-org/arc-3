#!/bin/bash
# Laguna S 2.1 concurrency sweep: boot vLLM ONCE (model load is the expensive
# part), then restart the server at each --max-num-seqs level in SWEEP_LEVELS,
# load-test it at matching concurrency with a realistic-sized prompt, and
# record tokens/sec + peak VRAM per level. Stops climbing at the first level
# that fails to start (VRAM pressure is monotonic in max-num-seqs, so a
# failure means every higher level would fail too) -- reports the max
# concurrency that actually survived alongside its own throughput number.
set -uo pipefail
export HOME="${HOME:-/root}"
exec > >(tee -a /var/log/arc3-startup.log) 2>&1
echo "=== laguna concurrency sweep $(date -u +%FT%TZ) ==="

BUCKET=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-bucket")
RUN_ID=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-run-id")
MIG=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-mig" || echo arc3-g4-laguna-sweep)
ZONE=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
MODEL_BUCKET_NAME=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-model-bucket-name")
MODEL_HF_ID=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-model-hf-id")
SWEEP_LEVELS=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-sweep-levels" || echo "8 16 20 24 25 28")
MINUTES_PER_LEVEL=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/arc3-minutes-per-level" || echo 3)
echo "bucket=$BUCKET run=$RUN_ID mig=$MIG model=$MODEL_HF_ID sweep=[$SWEEP_LEVELS] minutes_per_level=$MINUTES_PER_LEVEL"

mkdir -p /opt/arc3 && cd /opt/arc3
ATTEMPTS=$( (gcloud storage cat "$BUCKET/$RUN_ID/attempts" 2>/dev/null || echo 0) | tr -dc '0-9' ); ATTEMPTS=$(( ${ATTEMPTS:-0} + 1 ))
echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/attempts"; echo "boot attempt #$ATTEMPTS"
if [ "$ATTEMPTS" -gt 5 ]; then echo failed | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"; gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE" || true; exit 1; fi

( while true; do gcloud storage cp /var/log/arc3-startup.log "$BUCKET/$RUN_ID/startup-$(hostname).log" >/dev/null 2>&1; sleep 20; done ) &

apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential ninja-build

# ---- sync model (flat resolved dir -- see v12laguna_tps_startup.sh for why) --
mkdir -p /opt/arc3/model
gcloud storage rsync -r "$BUCKET/model-flat/$MODEL_BUCKET_NAME" /opt/arc3/model
echo "model sync done: $(du -sh /opt/arc3/model | cut -f1)"

curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH="$HOME/.local/bin:$PATH"
uv venv --python 3.12.12 /opt/arc3/pysrv
uv pip install --python /opt/arc3/pysrv/bin/python "vllm==0.25.1" || {
  echo "vllm install failed"; echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/serverfail"; exit 1; }

# ---- realistic-size load-test prompt (approximates one real harness turn: --
# system-prompt-scale boilerplate + a full 64x64 ascii grid) so KV-cache
# pressure per sequence isn't understated by a toy-short benchmark prompt.
cat > /opt/arc3/build_prompt.py << 'PYEOF'
import random
random.seed(7)
CHARS = "WwgGcBMPRbSYOrNp"
grid_lines = ["".join(random.choice(CHARS) for _ in range(64)) for _ in range(64)]
grid = "\n".join(grid_lines)
boilerplate = (
    "You are a coding agent solving a grid-based puzzle game. "
    "You are called repeatedly over the course of a run. Treat each turn as one "
    "observe-plan-act cycle: re-understand the current state from the newest frame, "
    "update your working world model in Python, choose the next best action or short "
    "sequence against the goal as currently understood, execute it, and expect to "
    "re-evaluate on the next turn from the updated state. Your job is to solve the "
    "entire game by clearing every level, not just the current screen. Levels often "
    "build on earlier mechanics, but layouts and interactions can still change between "
    "levels, and new mechanics might be introduced. Optimize for as few in-game actions "
    "as possible while still reliably clearing every level. Treat each board as a scene "
    "with objects, blockers, targets, adjacency, containment, motion, and symmetry. "
) * 6
with open("/opt/arc3/prompt.txt", "w") as f:
    f.write(boilerplate + "\n\nCurrent grid (ASCII):\n" + grid)
print(f"prompt chars: {len(boilerplate) + len(grid)}")
PYEOF
/opt/arc3/pysrv/bin/python /opt/arc3/build_prompt.py

cat > /opt/arc3/load_test.py << 'PYEOF'
import concurrent.futures, json, os, sys, time, urllib.request

DURATION_S = int(os.environ["LEVEL_MINUTES"]) * 60
CONCURRENCY = int(os.environ["LEVEL_CONCURRENCY"])
PROMPT = open("/opt/arc3/prompt.txt").read()
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
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read())
    dt = time.time() - t0
    usage = data.get("usage", {})
    return usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), dt

def worker(stop_at):
    total_tokens, n, errors = 0, 0, 0
    prompt_tokens = 0
    while time.time() < stop_at:
        try:
            ptok, ctok, dt = one_request()
            total_tokens += ctok
            prompt_tokens = ptok
            n += 1
        except Exception as e:
            errors += 1
            print(f"[worker error] {e}", flush=True)
    return total_tokens, n, errors, prompt_tokens

stop_at = time.time() + DURATION_S
t_start = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
    futures = [ex.submit(worker, stop_at) for _ in range(CONCURRENCY)]
    results = [f.result() for f in futures]
wall = time.time() - t_start
total_tokens = sum(r[0] for r in results)
total_reqs = sum(r[1] for r in results)
total_errors = sum(r[2] for r in results)
prompt_tokens = max((r[3] for r in results), default=0)
print(f"RESULT concurrency={CONCURRENCY} prompt_tokens={prompt_tokens} wall_s={wall:.1f} "
      f"total_requests={total_reqs} total_errors={total_errors} "
      f"total_completion_tokens={total_tokens} tokens_per_sec={total_tokens/wall:.2f}")
PYEOF

export USE_TF=0 TRANSFORMERS_NO_TF=1 TRANSFORMERS_NO_TORCHVISION=1 VLLM_NO_USAGE_STATS=1
RESULTS_FILE=/opt/arc3/sweep_results.txt
: > "$RESULTS_FILE"

for LEVEL in $SWEEP_LEVELS; do
  echo "=== sweep level: max-num-seqs=$LEVEL ==="
  rm -f /opt/arc3/vllm.log
  nohup /opt/arc3/pysrv/bin/python -m vllm.entrypoints.openai.api_server \
    --model /opt/arc3/model --served-model-name "$MODEL_HF_ID" \
    --trust-remote-code \
    --host 127.0.0.1 --port 1234 --tensor-parallel-size 1 \
    --enable-auto-tool-choice --tool-call-parser poolside_v1 --reasoning-parser poolside_v1 \
    --default-chat-template-kwargs '{"enable_thinking": true}' \
    --generation-config vllm --enable-prefix-caching \
    --max-num-seqs "$LEVEL" \
    --max-model-len 65536 \
    > /opt/arc3/vllm.log 2>&1 &
  VLLM_PID=$!

  READY=0
  for i in $(seq 1 60); do
    if curl -s -m 3 http://127.0.0.1:1234/v1/models >/dev/null; then READY=1; break; fi
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then break; fi
    sleep 5
  done

  if [ "$READY" != "1" ]; then
    echo "LEVEL $LEVEL: FAILED TO START -- stopping sweep here (higher levels would fail too)" | tee -a "$RESULTS_FILE"
    gcloud storage cp /opt/arc3/vllm.log "$BUCKET/$RUN_ID/vllm-fail-level$LEVEL.log" || true
    pkill -KILL -f "vllm.entrypoints.openai.api_server" 2>/dev/null || true
    sleep 5
    break
  fi

  VRAM_READY=$(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader)
  echo "LEVEL $LEVEL: ready, vram_at_ready=[$VRAM_READY]" | tee -a "$RESULTS_FILE"

  LEVEL_MINUTES="$MINUTES_PER_LEVEL" LEVEL_CONCURRENCY="$LEVEL" \
    /opt/arc3/pysrv/bin/python /opt/arc3/load_test.py "$MODEL_HF_ID" | tee -a "$RESULTS_FILE"

  VRAM_PEAK=$(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader)
  echo "LEVEL $LEVEL: vram_at_peak=[$VRAM_PEAK]" | tee -a "$RESULTS_FILE"

  pkill -TERM -f "vllm.entrypoints.openai.api_server" 2>/dev/null; sleep 8
  pkill -KILL -f "vllm.entrypoints.openai.api_server" 2>/dev/null || true
  sleep 5
  gcloud storage cp "$RESULTS_FILE" "$BUCKET/$RUN_ID/sweep_results.txt" || true
done

echo "=== sweep complete ===" | tee -a "$RESULTS_FILE"
gcloud storage cp "$RESULTS_FILE" "$BUCKET/$RUN_ID/sweep_results.txt" || true

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
