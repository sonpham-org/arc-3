#!/bin/bash
# DeepSeek-V4.1-Flash-NVFP4 on 8x RTX PRO 6000 (g4-standard-384), serving the
# frozen 7.36 harness (compaction v5 + clean-return) unchanged. Only the model,
# the lane count and the server change; every harness knob below is the 7.36
# candidate's own value (docs/plans/2026-09-21-loop-b-arms-on-the-submission-harness.md §1).
#
# Server: vLLM nightly in docker (the recipe path for V4.1; a pip pin does not
# exist yet), TP8, Engram tables CPU-offloaded (~183 GiB host RAM), FP8 KV.
# Server attempt ladder (Run #2 findings, 22-Sep 03:02Z): plain TP8 dies in process_weights_after_loading
# because moe_intermediate_size 2304 / 8 = 288 is not a multiple of 128 and FLASHINFER_CUTLASS cannot pad
# gated w1/w3. So: attempt 1 = --enable-expert-parallel (experts unsliced, no padding), attempt 2 = Marlin
# MoE backend. The recipe's indexer flags exist only in vLLM nightly (pinned 0909 image rejects them);
# arc3-blackwell-flags=1 adds them to every attempt.
set -uo pipefail
export HOME="${HOME:-/root}"
exec > >(tee -a /var/log/arc3-startup.log) 2>&1
echo "=== DeepSeek-V4.1-Flash 8xRTX startup $(date -u +%FT%TZ) ==="

meta() { curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
BUCKET=$(meta arc3-bucket); RUN_ID=$(meta arc3-run-id)
MIG=$(meta arc3-mig || echo arc3-g4-dsv41flash)
ZONE=$(curl -s -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
SEED=$BUCKET/tufa-exact
MODEL_BUCKET_NAME=$(meta arc3-model-bucket-name); MODEL_HF_ID=$(meta arc3-model-hf-id)
BUNDLE=$(meta arc3-bundle); RUNNER=$(meta arc3-runner || echo v12_run_maxruntime.py)
MAX_NUM_SEQS=$(meta arc3-max-num-seqs || echo 25)
MAX_MODEL_LEN=$(meta arc3-max-model-len || echo 131072)
GAME_SUBSET=$(meta arc3-game-subset | tr "+" "," )
MAX_RUNTIME_S_PER_GAME=$(meta arc3-max-runtime-s-per-game || echo 2061)
MAX_RUN_RUNTIME_MINUTES=$(meta arc3-max-run-runtime-minutes || echo 132)
BLACKWELL_FLAGS=$(meta arc3-blackwell-flags || echo 0)   # the indexer flags exist only in nightly; pinned 0909 image rejects them
VLLM_IMAGE=$(meta arc3-vllm-image || echo vllm/vllm-openai:deepseekv41-flash-0909)
MODE=$(meta arc3-mode || echo full)                 # full = harness run; tps = serve, probe throughput, tear down
TPS_LANES=$(meta arc3-tps-lanes || echo 7)
TPS_PROMPT_TOKENS=$(meta arc3-tps-prompt-tokens | tr "+" "," ); TPS_PROMPT_TOKENS=${TPS_PROMPT_TOKENS:-12000,48000,90000}   # "+" carries commas through GCE metadata
echo "bucket=$BUCKET run=$RUN_ID mig=$MIG model=$MODEL_HF_ID bundle=$BUNDLE lanes=$MAX_NUM_SEQS ctx=$MAX_MODEL_LEN subset=[${GAME_SUBSET:-full 25}]"

mkdir -p /opt/arc3 && cd /opt/arc3
gcloud storage cp "$BUCKET/code/resource_sampler.sh" /opt/arc3/resource_sampler.sh 2>/dev/null \
  && bash /opt/arc3/resource_sampler.sh "$BUCKET" "$RUN_ID" || echo "resource sampler skipped"
ATTEMPTS=$( (gcloud storage cat "$BUCKET/$RUN_ID/attempts" 2>/dev/null || echo 0) | tr -dc '0-9' ); ATTEMPTS=$(( ${ATTEMPTS:-0} + 1 ))
echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/attempts"; echo "boot attempt #$ATTEMPTS"
if [ "$ATTEMPTS" -gt 8 ]; then echo failed | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"; gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE" || true; exit 1; fi
( while true; do gcloud storage cp /var/log/arc3-startup.log "$BUCKET/$RUN_ID/startup-$(hostname).log" >/dev/null 2>&1; sleep 60; done ) &

# ---- hardware sanity: 8 GPUs, >= 200 GiB host RAM for the Engram offload ----
nvidia-smi --query-gpu=name,memory.total --format=csv | tee /opt/arc3/gpus.txt
NGPU=$(nvidia-smi -L | wc -l); RAM_GIB=$(awk '/MemTotal/ {printf "%d", $2/1048576}' /proc/meminfo)
echo "gpus=$NGPU host_ram_gib=$RAM_GIB"
if [ "$NGPU" -lt 8 ] || [ "$RAM_GIB" -lt 200 ]; then
  echo "WRONG SHAPE: need 8 GPUs and >=200 GiB RAM"
  echo shape | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"
  gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE"; exit 1
fi

apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential ffmpeg ninja-build

# ---- pristine code + the 7.36 harness bundle -------------------------------
gcloud storage cp "$BUCKET/code/arc3-code-tufa0.tgz" /tmp/c.tgz && tar xzf /tmp/c.tgz -C /opt/arc3
if [ "$MODE" = full ]; then
  mkdir -p /opt/arc3/bundle && gcloud storage cp "$SEED/$BUNDLE" /tmp/b.tgz && tar xzf /tmp/b.tgz -C /opt/arc3/bundle
  gcloud storage cp "$BUCKET/code/$RUNNER" /opt/arc3/v12_run.py
fi

# ---- model: flat GCS dir, ~492 GiB ----------------------------------------
mkdir -p /opt/arc3/model
gcloud storage rsync -r "$BUCKET/model-flat/$MODEL_BUCKET_NAME" /opt/arc3/model
echo "model sync done: $(du -sh /opt/arc3/model | cut -f1), $(ls /opt/arc3/model/*.safetensors | wc -l) shards"

# ---- server: vLLM nightly, docker, TP8 -------------------------------------
docker pull "$VLLM_IMAGE" || { echo "pull of $VLLM_IMAGE failed; falling back to nightly"; VLLM_IMAGE=vllm/vllm-openai:nightly; docker pull "$VLLM_IMAGE"; }
docker inspect --format '{{index .RepoDigests 0}}' "$VLLM_IMAGE" | tee /opt/arc3/vllm-image-digest.txt \
  | gcloud storage cp - "$BUCKET/$RUN_ID/vllm-image-digest.txt"

ENGRAM_CFG='{"cpu_offload":true}'
serve_args_common=(
  --model /model --served-model-name "$MODEL_HF_ID"
  --host 0.0.0.0 --port 1234
  --tensor-parallel-size 8
  --engram-config "$ENGRAM_CFG"
  --language-model-only
  --kv-cache-dtype fp8
  --reasoning-parser deepseek_v41 --tool-call-parser deepseek_v41 --enable-auto-tool-choice
  --max-model-len "$MAX_MODEL_LEN" --max-num-seqs "$MAX_NUM_SEQS"
  --gpu-memory-utilization 0.9
)
start_server() {  # $1 = mode: ep | marlin | plain ; $2 = 1 adds the nightly-only indexer flags
  local mode="$1" extra=() envs=()
  case "$mode" in
    ep)     extra+=(--enable-expert-parallel) ;;                       # experts stay whole (2304 wide): no NVFP4 block-scale padding at TP8
    marlin) extra+=(--kernel-config '{"moe_backend":"marlin"}') ;;    # Marlin handles arbitrary slice sizes; proven on this GPU class, slower
    plain)  ;;                                                         # known to fail on this model at TP8 (22-Sep 03:02Z): FLASHINFER_CUTLASS cannot pad w1/w3
  esac
  if [ "${2:-0}" = 1 ]; then extra+=(--indexer-kv-dtype mxfp4 --indexer-sparse-logits true); envs=(-e FLASHINFER_MLA_SPARSE_DSV41=1); fi
  docker rm -f arc3-vllm >/dev/null 2>&1 || true
  docker run -d --name arc3-vllm --gpus all --ipc=host --shm-size=64g --network host     -v /opt/arc3/model:/model:ro -e VLLM_NO_USAGE_STATS=1 "${envs[@]}"     "$VLLM_IMAGE" vllm serve "${serve_args_common[@]}" "${extra[@]}"
  # 552B across 8 PCIe GPUs: weight load alone is many minutes; allow 40
  for i in $(seq 1 240); do
    curl -s -m 3 http://127.0.0.1:1234/v1/models >/dev/null && return 0
    docker ps -q -f name=arc3-vllm | grep -q . || break   # container died
    sleep 10
  done
  docker logs arc3-vllm > "/opt/arc3/vllm-$mode.log" 2>&1
  gcloud storage cp "/opt/arc3/vllm-$mode.log" "$BUCKET/$RUN_ID/serverlog-$(hostname)-$ATTEMPTS-$mode.log" || true
  return 1
}
SERVER_MODE=""
for mode in ep marlin; do
  if start_server "$mode" "$BLACKWELL_FLAGS"; then SERVER_MODE="$mode"; break; fi
  echo "server mode '$mode' failed; trying next"
done
if [ -z "$SERVER_MODE" ]; then
  echo "SERVER FAILED TO START (ep, marlin) -- aborting attempt $ATTEMPTS"
  echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/serverfail"; exit 1
fi
echo "$SERVER_MODE" | gcloud storage cp - "$BUCKET/$RUN_ID/server-mode"
echo "vllm ready: $MODEL_HF_ID mode=$SERVER_MODE"
( docker logs -f arc3-vllm > /opt/arc3/vllm.log 2>&1 ) &
nvidia-smi --query-gpu=memory.used,memory.total --format=csv | tee -a /opt/arc3/gpus.txt

# ---- tps mode: ARC3-shaped throughput probe at N lanes, then tear down ------
if [ "$MODE" = tps ]; then
  gcloud storage cp "$BUCKET/code/arc3_tps_probe.py" /opt/arc3/arc3_tps_probe.py
  python3 -m pip install -q --break-system-packages aiohttp 2>/dev/null || apt-get install -y -qq python3-aiohttp
  # 1 lane first (the per-request floor), then the requested lane count
  for L in 1 "$TPS_LANES"; do
    python3 /opt/arc3/arc3_tps_probe.py --model "$MODEL_HF_ID" --lanes "$L"       --prompt-tokens "$TPS_PROMPT_TOKENS" --rounds 2 --max-tokens 1500 --out "/opt/arc3/tps/lanes$L"       2>&1 | tee "/opt/arc3/tps-lanes$L.log"
    nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader > "/opt/arc3/tps/lanes$L/vram-at-peak.txt"
  done
  gcloud storage rsync -r /opt/arc3/tps "$BUCKET/$RUN_ID/tps"
  gcloud storage cp /opt/arc3/vllm.log "$BUCKET/$RUN_ID/vllm.log" || true
  gcloud storage cp /opt/arc3/gpus.txt "$BUCKET/$RUN_ID/gpus.txt" || true
  docker stop -t 20 arc3-vllm >/dev/null 2>&1 || true
  echo done | gcloud storage cp - "$BUCKET/$RUN_ID/DONE"
  for _t in 1 2 3; do
    gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE" && { echo "teardown: $MIG resized to 0"; break; }
    [ "$_t" = 3 ] && echo "TEARDOWN FAILED $MIG at $(date -u +%FT%TZ)" | gcloud storage cp - "$BUCKET/$RUN_ID/TEARDOWN_FAILED" || sleep 15
  done
  exit 0
fi

# ---- agent: pristine harness, own venv --------------------------------------
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
export LOCAL_ANALYZER_APP_NAME="ARC3 Agent Harness"
# ---- 7.36 candidate values, byte-for-byte (Loop B spec §1) ------------------
export LOCAL_ANALYZER_CONTEXT_WINDOW=102985 LOCAL_ANALYZER_MAX_OUTPUT=0   # input cap 94281 is derived by the harness from the window
export ARC3_ACTION_CAP=14 ARC3_ACTION_CAP_MODE=return
export ARC3_CONTEXT_COMPACTION=1 ARC3_HALF_CONTEXT_SWAP=1
export ARC3_PROMPT_ABLATE_SEARCH=1
export ARC3_BUDGET_GUIDANCE=time_only
export ARC3_MAX_RUNTIME_S_PER_GAME="$MAX_RUNTIME_S_PER_GAME" ARC3_MAX_RUN_RUNTIME_MINUTES="$MAX_RUN_RUNTIME_MINUTES"
export ARC3_REEXPLORE_STRICT="" ARC3_GAME_SUBSET="$GAME_SUBSET" ARC3_STATE_GRAPH="" ARC3_FRAME_MODE=full
export LOCAL_ANALYZER_TOOL_STEPS=0 LOCAL_ANALYZER_TOOL_TIMEOUT=30 LOCAL_ANALYZER_TOOL_OUTPUT_TOKENS=1024
export LOCAL_ANALYZER_YIELD_SECONDS=60
# Sampling: DeepSeek's recommended defaults rather than Qwen's (0.6/0.95/20);
# this is the one deliberate non-harness difference and it is recorded here.
export LOCAL_ANALYZER_TEMPERATURE=1.0 LOCAL_ANALYZER_TOP_P=0.95 LOCAL_ANALYZER_TOP_K=0
# Thinking stays on (server default; reasoning-parser splits it out). Text-only
# grids: MULTIMODAL_CONTEXT deliberately unset, --language-model-only above.
echo "harness: 7.36 candidate env, lanes=$MAX_NUM_SEQS, per-game=${MAX_RUNTIME_S_PER_GAME}s, run=${MAX_RUN_RUNTIME_MINUTES}min"

./.venv/bin/python /opt/arc3/v12_run.py 2>&1 | tee /opt/arc3/v12.log || echo "runner exited $?"
gcloud storage cp /opt/arc3/v12.log "$BUCKET/$RUN_ID/v12-run.log" || true
gcloud storage cp /opt/arc3/vllm.log "$BUCKET/$RUN_ID/vllm.log" || true
gcloud storage cp /opt/arc3/gpus.txt "$BUCKET/$RUN_ID/gpus.txt" || true
docker stop -t 20 arc3-vllm >/dev/null 2>&1 || true
echo "vLLM server stopped (teardown parity)"

gcloud storage rsync -r /opt/arc3/work "$BUCKET/$RUN_ID/runs"
echo done | gcloud storage cp - "$BUCKET/$RUN_ID/DONE"
for _t in 1 2 3; do
  if gcloud compute instance-groups managed resize "$MIG" --size=0 --zone="$ZONE"; then echo "teardown: $MIG resized to 0"; break; fi
  echo "teardown attempt $_t FAILED for $MIG"
  if [ "$_t" = 3 ]; then
    echo "TEARDOWN FAILED $MIG at $(date -u +%FT%TZ)" | gcloud storage cp - "$BUCKET/$RUN_ID/TEARDOWN_FAILED" || true
  else
    sleep 15
  fi
done
