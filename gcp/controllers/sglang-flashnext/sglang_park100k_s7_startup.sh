#!/bin/bash
# SGLang measurement VM: Qwen3.8-Flash-Next NVFP4 (golden image model payload) on the official sglang
# qwen4-main-squashed branch + gabrielolympie/sglang-flashnext-sm120 patches, benchmarked at the ARC
# harness's shape (7 lanes x 50k/100k prompts, cached re-sends, 2k-token decodes). Not a scored run.
set -uo pipefail
exec > >(tee /var/log/arc3-sglang-bench.log) 2>&1
meta() { curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
BUCKET=$(meta arc3-bucket); RUN_ID=$(meta arc3-run-id); SGL_REF=$(meta sgl-ref 2>/dev/null || echo qwen4-main-squashed)
ZONE=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
NAME=$(curl -sf -H "Metadata-Flavor: Google" "http://metadata.google.internal/computeMetadata/v1/instance/name")
OUT=/opt/arc3/sglbench; mkdir -p $OUT
sync_out() { timeout 60 gcloud storage rsync -r $OUT "$BUCKET/$RUN_ID/sglbench" >/dev/null 2>&1 || true
             timeout 20 gcloud storage cp /var/log/arc3-sglang-bench.log "$BUCKET/$RUN_ID/startup.log" >/dev/null 2>&1 || true; }
finish() { local st="$1"; echo "$st $(date -u +%FT%TZ)" | gcloud storage cp - "$BUCKET/$RUN_ID/$st" >/dev/null 2>&1 || true; sync_out
  token=$(curl -sf -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
  proj=$(curl -sf -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/project/project-id)
  curl -sS -X DELETE -H "Authorization: Bearer $token" "https://compute.googleapis.com/compute/v1/projects/$proj/zones/$ZONE/instances/$NAME" >/dev/null || sudo shutdown -h now; }
trap 'finish FAILED' ERR
(while true; do sync_out; sleep 180; done) &
(sleep 13800; echo "hard stop"; finish TIMEOUT) &

echo "=== $(date -u +%FT%TZ) host: $(nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader)"
free -g | head -2; nproc
MODEL_DIR=/opt/arc3/flashnext-model
test -f $MODEL_DIR/config.json && test -f $MODEL_DIR/chat_template.jinja
ls $MODEL_DIR | wc -l
gcloud storage cp "$BUCKET/code/sglang-bench/bench_shape.py" $OUT/bench_shape.py
gcloud storage cp "$BUCKET/code/sglang-bench/bench_slots.py" $OUT/bench_slots.py
mkdir -p /opt/arc3/sgl && cd /opt/arc3/sgl
git clone -q -b "$SGL_REF" https://github.com/sgl-project/sglang sglang-official && (cd sglang-official && git log -1 --format='%H %cd %s' | tee $OUT/sglang_commit.txt)
git clone -q https://github.com/gabrielolympie/sglang-flashnext-sm120 fork && (cd fork && git log -1 --format='%H %cd' | tee $OUT/fork_commit.txt)
cp fork/hot_tokens_64k.pt /opt/arc3/sgl/hot_tokens_64k.pt

# ---- build + serve inside a CUDA 13 dev container (host keeps only driver + docker) ----
docker pull -q nvidia/cuda:13.0.3-devel-ubuntu24.04
cat > /opt/arc3/sgl/inside.sh <<'INSIDE'
#!/bin/bash
set -uo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq python3.12 python3.12-venv python3.12-dev git build-essential gcc-13 g++-13 curl ninja-build cmake pkg-config >/dev/null
curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1
curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal >/dev/null 2>&1
export PATH=/root/.local/bin:/root/.cargo/bin:/usr/local/cuda/bin:$PATH; cargo --version
export CUDA_HOME=/usr/local/cuda CUDACXX=/usr/local/cuda/bin/nvcc CC=gcc-13 CXX=g++-13 CUDAHOSTCXX=g++-13 TORCH_CUDA_ARCH_LIST=12.0
cd /sgl/sglang-official
git config user.email bench@arc3 && git config user.name bench
PATCHED=""
for p in 0002-fp8-qsa-tile-dequant 0003-sm120-fp32-prefill-state 0001b-recoverssm-wy-sm120-PORTED; do
  if git apply --exclude='test/*' ../fork/patches/$p.patch 2>/tmp/p.err; then PATCHED="$PATCHED $p"; else echo "PATCH FAILED $p: $(head -c 300 /tmp/p.err)"; fi
done
for p in 0004-sm120-lowm-triton-gemm 0005-sm120-fp8-weight-only 0006-sm120-fp8-hc-lmhead; do
  if git am ../fork/patches/$p.patch >/tmp/p.err 2>&1; then PATCHED="$PATCHED $p"; else git am --abort 2>/dev/null; echo "PATCH FAILED $p: $(head -c 300 /tmp/p.err)"; fi
done
echo "patches applied:$PATCHED" | tee /out/patches_applied.txt
LINEAR=flashinfer; GDN_MODE=( --gdn-mtp-cache-mode none )
case "$PATCHED" in *0001b*) ;; *) echo "0001b missing: falling back to triton linear-attention backend, no WY verify"; LINEAR=triton; GDN_MODE=(); KVD=auto;; esac
uv venv --python 3.12 /sgl/venv >/dev/null && source /sgl/venv/bin/activate
export MAX_JOBS=16 CMAKE_BUILD_PARALLEL_LEVEL=16 CARGO_BUILD_JOBS=16
echo "=== install start $(date -u +%T)"
uv pip install --prerelease=allow --index-strategy unsafe-best-match --extra-index-url https://docs.sglang.ai/whl/cu130/ -e python > /out/install.log 2>&1; echo "install exit=$?"; tail -n 8 /out/install.log
python -c "import sglang, torch; print('sglang', sglang.__version__, 'torch', torch.__version__, torch.version.cuda)" | tee /out/versions.txt || { echo "INSTALL FAILED"; tail -n 60 /out/install.log; exit 1; }
echo "=== install done $(date -u +%T)"
CACHE=/sgl/cache; mkdir -p $CACHE/{huggingface,torch,torchinductor,triton,flashinfer,sglang/jit}
export HF_HOME=$CACHE/huggingface XDG_CACHE_HOME=$CACHE TORCHINDUCTOR_CACHE_DIR=$CACHE/torchinductor TRITON_CACHE_DIR=$CACHE/triton
export FLASHINFER_WORKSPACE_BASE=$CACHE/flashinfer SGLANG_JIT_CACHE_DIR=$CACHE/sglang/jit
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN=1 OMP_NUM_THREADS=8 TOKENIZERS_PARALLELISM=false
export MAX_JOBS=4 CMAKE_BUILD_PARALLEL_LEVEL=4 FLASHINFER_NINJA_JOBS=4 FLASHINFER_NVCC_THREADS=2 TORCHINDUCTOR_COMPILE_THREADS=4
export SGLANG_SM120_LOWM_FP8_WEIGHT=1 SGLANG_SM120_LM_HEAD_FP8=1

serve() {  # $1 = label, rest = extra args; retries once at mem-fraction 0.95 if the server dies (0.98 OOMed at graph capture)
  local label="$1"; shift
  serve_once "$label" "$@" && return 0
  [ "${MEMFRAC:-0.965}" = "0.95" ] && return 1
  echo "serve[$label] failed at mem-fraction ${MEMFRAC:-0.965}; retrying at 0.95"
  MEMFRAC=0.95 serve_once "${label}_m95" "$@"
}
serve_once() {
  local label="$1"; shift
  pkill -f "sglang.launch_server" 2>/dev/null; sleep 5; pkill -9 -f "sglang" 2>/dev/null
  for i in $(seq 1 60); do used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1); [ "${used:-99999}" -lt 3000 ] && break; sleep 5; done
  echo "gpu memory before serve[$label]: ${used:-?} MiB"
  local args=( -m sglang.launch_server --model-path /model --load-format safetensors --served-model-name pennyroyal
    --host 0.0.0.0 --port 8001 --tp 1 --dtype bfloat16 --quantization modelopt_fp4
    --mem-fraction-static ${MEMFRAC:-0.965} --context-length 131072 --kv-cache-dtype ${KVD:-fp8_e4m3} --page-size 64 --max-running-requests 8 --chunked-prefill-size 4096
    --cuda-graph-max-bs 8 --mamba-ssm-dtype bfloat16 --max-mamba-cache-size 48 --mamba-radix-cache-strategy extra_buffer --mamba-track-interval 64
    --linear-attn-decode-backend $LINEAR --linear-attn-prefill-backend $LINEAR
    --ple-offload-embedding --trust-remote-code --chat-template /model/chat_template.jinja
    --reasoning-parser qwen3 --tool-call-parser qwen3_coder --enable-metrics --watchdog-timeout 1800 "$@" )
  echo "=== serve[$label]: python ${args[*]}" | tee -a /out/serve_cmds.txt
  nohup python "${args[@]}" > /out/server_$label.log 2>&1 &
  for i in $(seq 1 240); do curl -sf http://127.0.0.1:8001/health >/dev/null && return 0; pgrep -f "sglang.launch_server" >/dev/null || { echo "server died"; tail -n 40 /out/server_$label.log; return 1; }; sleep 15; done
  echo "server never became healthy"; tail -n 40 /out/server_$label.log; return 1
}
bench() { python /out/bench_shape.py --base-url http://127.0.0.1:8001/v1 --model pennyroyal --out /out/results_$1.json --label "$1" --shapes 7x50000,7x100000,4x50000,1x50000 --decode-tokens 2000 2>&1 | tee /out/bench_$1.log; }

MTP=( --speculative-algorithm NEXTN --speculative-num-steps 3 --speculative-eagle-topk 1 --speculative-num-draft-tokens 4
      --speculative-draft-model-quantization unquant --speculative-token-map /sgl/hot_tokens_64k.pt "${GDN_MODE[@]}"
      --speculative-accept-threshold-single 1.0 --speculative-accept-threshold-acc 1.0 )
HIC=( --enable-hierarchical-cache --hicache-size 64 --hicache-write-policy write_through --hicache-io-backend kernel --hicache-mem-layout page_first )
slots() { python /out/bench_slots.py --base-url http://127.0.0.1:8001/v1 --model pennyroyal --games $2 --turns 8 --start-tokens $3 --grow 2000 --gen 1500 --sandbox 3 --out /out/slots_$1.json --label "$1" 2>&1 | tee /out/slots_$1.log; }
# 100k sweep, 7 slots: resident reference, then 4 parked extras (hierarchical cache, MTP lossless, mem 0.98)
if serve s7_hic "${MTP[@]}" "${HIC[@]}" --max-running-requests 7 --cuda-graph-max-bs 7 --max-mamba-cache-size 48; then
  slots s7_g7_100k 7 100000; slots s7_g11_100k 11 100000; slots s7_g11_80k 11 80000; slots s7_g9_100k 9 100000
else echo "s7: serve failed"; fi
pkill -f "sglang.launch_server" 2>/dev/null
echo "=== all configs done $(date -u +%T)"
INSIDE
chmod +x /opt/arc3/sgl/inside.sh
docker run --rm --gpus all --ipc=host --network=host --ulimit memlock=-1 \
  -v /opt/arc3/sgl:/sgl -v "$MODEL_DIR:/model:ro" -v $OUT:/out \
  nvidia/cuda:13.0.3-devel-ubuntu24.04 bash /sgl/inside.sh
echo "=== container exited $(date -u +%FT%TZ)"
trap - ERR
finish DONE
