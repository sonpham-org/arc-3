#!/bin/bash
# cv5-CR on SGLang, 7 x 67584 context, 2061 s/game: Search/scorer removal + 50% swap, W7, 132 minutes, time-only guidance; arm=compaction_v5_clean_return_a.
# Derived from captured baseline; not the exact champion.
set -euo pipefail
exec > >(tee /var/log/arc3-qwen38-startup.log) 2>&1

meta() {
  curl -sf -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"
}

BUCKET=$(meta arc3-bucket)
RUN_ID=$(meta arc3-run-id)
OWNED_VM_NAME=$(meta arc3-mig)
BUNDLE_NAME=$(meta arc3-bundle)
INFLUENCE_MODE=$(meta arc3-influence-mode)
RUNNER_OBJECT=$(meta arc3-runner-object)
CURATOR_OBJECT=$(meta arc3-curator-object)
SCORE_OBSERVER_OBJECT=$(meta arc3-score-observer-object)
GOLDEN_RUNTIME_IMAGE=$(meta arc3-golden-runtime-image 2>/dev/null || true)
CPU_BOOTSTRAP_OBJECT=$(meta arc3-cpu-bootstrap-object)
SEED_OBJECT=$(meta arc3-seed-object)
ZONE=$(curl -sf -H "Metadata-Flavor: Google" \
  "http://metadata.google.internal/computeMetadata/v1/instance/zone" | awk -F/ '{print $NF}')
SEED="$BUCKET/tufa-exact"
MODEL_ID="RadixArk/Qwen3.8-Flash-Next-NVFP4"
MODEL_REVISION="7b719225242aacd3dbd3f9407468c2ee9a9d2594"
SERVED_MODEL_NAME="$MODEL_ID"
TEARDOWN_STARTED=0

sync_all() {
  if [ -d /opt/arc3/config-audit ]; then
    timeout 15 gcloud storage rsync -r /opt/arc3/config-audit "$BUCKET/$RUN_ID/config-audit" >/dev/null 2>&1 || true
  fi
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
  for telemetry in time-guidance-selftest.log feature-selftest.log half-swap-live-gate.json half-swap-live-gate.log half-swap-tests.log live-canary-attempts.json prompt-selftest.log reminder-selftest.log reminder-runtime-identity.json native-context-prefix-reset.log sglang-serving-gate.json sglang-serving-gate.log sglang-versions.txt sgl-proxy.log full-context-selftest.json full-context-selftest.log gameplay-metrics-start.txt gameplay-metrics-end.txt model-download.log ple-conversion.log gpu-after-load.csv ram-after-load.txt kv-dtype-used.txt vllm.log vllm-fp8-failed.log vllm-start-attempt1.log verified-queue-selftest.log hypothesis-lab-selftest.log replay-selftest.log pre-harness-warmup.json pre-harness-warmup.log execution-selftest.json execution-selftest.log execution-release-manifest.json retention-runtime-identity.json; do
    [ -f "/opt/arc3/$telemetry" ] && timeout 20 gcloud storage cp \
      "/opt/arc3/$telemetry" "$BUCKET/$RUN_ID/$telemetry" >/dev/null 2>&1 || true
  done
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

delete_self_or_shutdown() {
  local project_id token http
  project_id=$(curl -sf -H "Metadata-Flavor: Google" \
    http://metadata.google.internal/computeMetadata/v1/project/project-id || true)
  token=$(curl -sf -H "Metadata-Flavor: Google" \
    http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])' 2>/dev/null || true)
  if [ -n "$project_id" ] && [ -n "$token" ]; then
    http=$(curl -sS --max-time 30 -o /tmp/arc3-self-delete.json -w '%{http_code}' \
      -X DELETE -H "Authorization: Bearer $token" \
      "https://compute.googleapis.com/compute/v1/projects/$project_id/zones/$ZONE/instances/$OWNED_VM_NAME?requestId=77fb5cd6-3a62-4c96-937d-a7dc933c8b9f" || true)
    if [ "$http" = 200 ] || [ "$http" = 201 ] || [ "$http" = 404 ]; then
      timeout 10 gcloud storage cp /tmp/arc3-self-delete.json \
        "$BUCKET/$RUN_ID/SELF_DELETE_ACCEPTED.json" >/dev/null 2>&1 || true
      sleep 120
    fi
  fi
  echo "self-delete fallback shutdown $OWNED_VM_NAME $(date -u +%FT%TZ)" | \
    gcloud storage cp - "$BUCKET/$RUN_ID/SELF_DELETE_FALLBACK" >/dev/null 2>&1 || true
  /sbin/shutdown -h now || true
}

teardown() {
  [ "$TEARDOWN_STARTED" = 1 ] && return
  TEARDOWN_STARTED=1
  trap - EXIT TERM INT
  if [ -n "${METRICS_SAMPLER_PID:-}" ]; then
    kill -TERM "$METRICS_SAMPLER_PID" 2>/dev/null || true
    wait "$METRICS_SAMPLER_PID" 2>/dev/null || true
  fi
  pkill -TERM -f arc3_minute_score_observer.py 2>/dev/null || true
  sleep 1
  sync_all
  pkill -TERM -f "nvfp4_cross_game_curator.py" 2>/dev/null || true
  pkill -TERM -f "cross_game_theme_influence_sidecar.py" 2>/dev/null || true
  pkill -TERM -f "llama-server" 2>/dev/null || true
  [ -n "${WATCHDOG_PID:-}" ] && kill -TERM "$WATCHDOG_PID" 2>/dev/null || true
  docker stop -t 20 flashnext 2>/dev/null || true
  pkill -TERM -f "vllm.entrypoints.openai.api_server" 2>/dev/null || true
  delete_self_or_shutdown
  return
}
on_exit() {
  status=$?
  if [ "$status" -ne 0 ]; then
    echo "startup or runner failed: $status" | timeout 15 gcloud storage cp - "$BUCKET/$RUN_ID/FAILED" || true
  fi
  teardown
}
trap on_exit EXIT
trap teardown TERM INT

case "$INFLUENCE_MODE" in
  none) ;;
  *) echo "invalid influence mode: $INFLUENCE_MODE" | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"; exit 1 ;;
esac
echo "=== Experimental execution-memory study $(date -u +%FT%TZ) run=$RUN_ID instance=$OWNED_VM_NAME mode=$INFLUENCE_MODE ==="

# Hard cost guard: 14400 seconds from VM startup, including setup.
(
  sleep 14400
  echo "hard lifetime reached $(date -u +%FT%TZ)" | gcloud storage cp - \
    "$BUCKET/$RUN_ID/HARD_TIMEOUT" || true
  pkill -TERM -f v12_run.py 2>/dev/null || true
  sleep 20
  pkill -KILL -f v12_run.py 2>/dev/null || true
  sync_all
  delete_self_or_shutdown
) &

test "$(meta arc3-experiment-serving-approved)" = 0
test "$(meta arc3-runtime-capacity-gate)" = context-matrix-capacity-r1
test "$(meta arc3-symbolic-search)" = 0
test "$(meta arc3-programmatic-workspace)" = 0
test "$(meta arc3-experiment-profile-id)" = '9f32a9dd86f46fa9b09060f9b08cb3b92043d68bcbe9c6ad8d7450415fa6c97f'
test "$(meta arc3-exact-kaggle-champion)" = 0
test "$(meta arc3-execution-mode)" = 0

# A Spot recreation would restart the whole benchmark and contaminate the run.
# Refuse every boot after the first and shut down this direct instance.
ATTEMPTS=$( (gcloud storage cat "$BUCKET/$RUN_ID/attempts" 2>/dev/null || echo 0) | tr -dc '0-9')
ATTEMPTS=$(( ${ATTEMPTS:-0} + 1 ))
echo "$ATTEMPTS" | gcloud storage cp - "$BUCKET/$RUN_ID/attempts"
if [ "$ATTEMPTS" -gt 1 ]; then
  echo "preemption/recreation detected; duplicate gameplay forbidden" | gcloud storage cp - \
    "$BUCKET/$RUN_ID/FAILED"
  exit 1
fi

if [ -n "$GOLDEN_RUNTIME_IMAGE" ]; then
  # The image deliberately retains only reusable model, package, container, and
  # compilation caches. Never inherit gameplay or arm-specific telemetry.
  rm -rf /opt/arc3/work /opt/arc3/bundle /opt/arc3/curator \
    /opt/arc3/reviewed-themes /opt/arc3/engwheels
  rm -f /opt/arc3/v12.log /opt/arc3/model-smoke.json /opt/arc3/model-info.json \
    /opt/arc3/serving-environment.txt /opt/arc3/gpu-after-load.csv \
    /opt/arc3/ram-after-load.txt /opt/arc3/kv-dtype-used.txt \
    /opt/arc3/replay-selftest.log /opt/arc3/pre-harness-warmup.json \
    /opt/arc3/pre-harness-warmup.log /opt/arc3/model-download.log \
    /opt/arc3/vllm.log /opt/arc3/vllm-fp8-failed.log \
    /opt/arc3/vllm-start-attempt1.log
  rm -f /opt/arc3/execution-selftest.json /opt/arc3/execution-selftest.log /opt/arc3/execution-release-manifest.json
  rm -f /opt/arc3/retention-runtime-identity.json
  echo "golden runtime: cleared prior run state while preserving immutable caches"
fi
mkdir -p /opt/arc3/work /opt/arc3/bundle /opt/arc3/flashnext-model
(while true; do sync_all; sleep 120; done) &

gcloud storage cp "$BUCKET/code/resource_sampler.sh" /opt/arc3/resource_sampler.sh 2>/dev/null \
  && bash /opt/arc3/resource_sampler.sh "$BUCKET" "$RUN_ID" \
  || echo "resource sampler skipped"

if [ -z "$GOLDEN_RUNTIME_IMAGE" ]; then
  apt-get update -qq
else
  echo "golden runtime: skipping apt index refresh"
fi
# Prefer the reusable GCS bootstrap cache before apt computes its download queue.
# gcloud validates object checksums and apt independently validates each package
# against the signed Ubuntu package metadata before installation.
BOOTSTRAP_APT_PREFIX="$BUCKET/bootstrap-cache/ubuntu2404-ab4"
if [ -n "$GOLDEN_RUNTIME_IMAGE" ]; then
  command -v ffmpeg >/dev/null
  command -v ninja >/dev/null
  command -v gcc >/dev/null
  echo "golden runtime: reusing OS build and media packages"
else
  mkdir -p /var/cache/apt/archives
  if gcloud storage ls "$BOOTSTRAP_APT_PREFIX/*.deb" >/dev/null 2>&1; then
    gcloud storage cp "$BOOTSTRAP_APT_PREFIX/*.deb" /var/cache/apt/archives/
  fi
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq build-essential ffmpeg ninja-build
fi
cd /opt/arc3
gcloud storage cp "$BUCKET/code/arc3-code-tufa0.tgz" /tmp/code.tgz
tar xzf /tmp/code.tgz -C /opt/arc3
gcloud storage cp "$(meta arc3-bundle-object)" /tmp/bundle.tgz
echo '9f3197598e5e8d0181a084bbf55fa86d9d13dadb5acbeba0b76a7145a1df9c5d  /tmp/bundle.tgz' | sha256sum -c -
tar xzf /tmp/bundle.tgz -C /opt/arc3/bundle
# Activate only the immutable gameplay package carried by the audited bundle.
# Keep the pinned deployment project's Makefile, lockfile, and deployment-only
# config (including configs/tufa0.json), which are not part of the Kaggle bundle.
cp -a /opt/arc3/bundle/src/ARC3-Inference/inference/. /opt/arc3/ARC3-Inference/inference/
find /opt/arc3/ARC3-Inference/inference -type f -name '*.pyc' -delete
gcloud storage cp "$RUNNER_OBJECT" /opt/arc3/v12_run.py
echo '5979692269253e6b5873a0674977f4913cacf284b547908d27282e87031cc523  /opt/arc3/v12_run.py' | sha256sum -c -
gcloud storage cp "$SCORE_OBSERVER_OBJECT" /opt/arc3/arc3_minute_score_observer.py
python3 - <<'PYRUNLIMIT'
from pathlib import Path

path = Path('/opt/arc3/v12_run.py')
text = path.read_text(encoding='utf-8')
old = 'soft_end = datetime.now() + timedelta(hours=11, minutes=20)'
new = 'soft_end = datetime.now() + timedelta(minutes=132)'
if text.count(old) != 1:
    raise RuntimeError('runner soft-deadline anchor drift')
path.write_text(text.replace(old, new), encoding='utf-8')
PYRUNLIMIT
grep -F 'soft_end = datetime.now() + timedelta(minutes=132)' /opt/arc3/v12_run.py
export PATH="${HOME:-/root}/.local/bin:$PATH"
if [ -n "$GOLDEN_RUNTIME_IMAGE" ]; then
  test -x /root/.local/bin/uv
  test -x /opt/arc3/pysrv/bin/python
  echo "golden runtime: reusing uv and curator/server client environment"
else
  curl -LsSf https://astral.sh/uv/install.sh | sh
  uv venv --python 3.12.12 /opt/arc3/pysrv
fi

# Immutable experiment payloads. Full hashes are embedded in this startup.
rm -rf /opt/arc3/execution-assets /opt/arc3/execution-selftest
mkdir -p /opt/arc3/execution-assets /opt/arc3/execution-selftest
gcloud storage cp "$(meta arc3-runtime-assets-object)" /tmp/execution-assets.tgz
echo 'cacb4c3540c05272ea84c64f1979eaba16b313f70c0e2013ab69e350a7ff78aa  /tmp/execution-assets.tgz' | sha256sum -c -
tar xzf /tmp/execution-assets.tgz -C /opt/arc3/execution-assets
gcloud storage cp "$(meta arc3-selftest-object)" /tmp/execution-selftest.tgz
echo '12fee2e1261d21a490ec932097e1c1bfb489d799ab1276daad867b15e8707442  /tmp/execution-selftest.tgz' | sha256sum -c -
tar xzf /tmp/execution-selftest.tgz -C /opt/arc3/execution-selftest
gcloud storage cp "$(meta arc3-release-manifest-object)" /opt/arc3/execution-release-manifest.json
echo 'c56a2f6394df66530ddb7a30f4dd94dc81ec3dd891f466318bd0e3c50b0874ba  /opt/arc3/execution-release-manifest.json' | sha256sum -c -
cmp -s /opt/arc3/execution-selftest/release-manifest.json /opt/arc3/execution-release-manifest.json
/opt/arc3/pysrv/bin/python - <<'PYPACKAGEEARLY'
import hashlib, json
from pathlib import Path
manifest = json.loads(Path('/opt/arc3/execution-release-manifest.json').read_text())
for name, expected in manifest['candidate_files'].items():
    assert hashlib.sha256((Path('/opt/arc3/bundle') / name).read_bytes()).hexdigest() == expected, name
for name, expected in manifest['implementation']['candidate_source_sha256'].items():
    relative = name.removeprefix('src/ARC3-Inference/')
    assert hashlib.sha256((Path('/opt/arc3/ARC3-Inference') / relative).read_bytes()).hexdigest() == expected, name
print('PACKAGE_SOURCE_HASHES_VERIFIED before GPU model startup', flush=True)
PYPACKAGEEARLY
/opt/arc3/pysrv/bin/python - <<'PYASSETS'
import hashlib, json
from pathlib import Path
root = Path('/opt/arc3/execution-assets')
for name, expected in json.loads((root / 'asset-hashes.json').read_text()).items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
report = json.loads((root / 'gpu-numeric-r3.json').read_text())
assert report['status'] == 'completed' and report['all_gates_passed'] is True
assert report['script_sha256'] == 'abc09adedb35e1cb2976f6f71d4c40566cd4c8d2498424e019b91a51dc6512aa' and len(report['cases']) == 16
assert report['patch_manifest_sha256'] == 'a4f83b4020bbbb1086527b16670a2c2ca20a5a44bf7dd66d36255bb03646a2d5'
PYASSETS

# Flash-Next uses the experimental PLE CPU-offload path packaged in this pinned
# vLLM image.  The PLE table is the only model component placed in host RAM.
if [ -n "$GOLDEN_RUNTIME_IMAGE" ]; then
  command -v docker >/dev/null
  command -v nvidia-ctk >/dev/null
  echo "golden runtime: reusing Docker and NVIDIA container toolkit"
else
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker.io
  if ! command -v nvidia-ctk >/dev/null 2>&1; then
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nvidia-container-toolkit
  fi
  nvidia-ctk runtime configure --runtime=docker
fi
systemctl enable --now docker

MODEL_DIR=/opt/arc3/flashnext-model
# ---- SGLang serving stack: official sglang qwen4-main-squashed + gabrielolympie/sglang-flashnext-sm120 patches ----
# Built once inside a CUDA 13 dev container and committed as arc3-sglang:built; the serve container reuses that image.
SGL_IMAGE_BASE='nvidia/cuda:13.0.3-devel-ubuntu24.04'
SGL_IMAGE='arc3-sglang:built'
mkdir -p /opt/arc3/sgl/cache
cd /opt/arc3/sgl
git clone -q -b qwen4-main-squashed https://github.com/sgl-project/sglang sglang-official
git clone -q https://github.com/gabrielolympie/sglang-flashnext-sm120 fork
(cd sglang-official && git log -1 --format='%H %cd %s') | tee /opt/arc3/sgl/sglang_commit.txt
(cd fork && git log -1 --format='%H %cd') | tee /opt/arc3/sgl/fork_commit.txt
cp fork/hot_tokens_64k.pt /opt/arc3/sgl/hot_tokens_64k.pt
cd /opt/arc3
cat > /opt/arc3/sgl/build.sh <<'SGLBUILD'
#!/bin/bash
set -euo pipefail
nvidia-smi -L
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq python3.12 python3.12-venv python3.12-dev git build-essential gcc-13 g++-13 curl ninja-build cmake pkg-config >/dev/null
curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1
curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal >/dev/null 2>&1
export PATH=/root/.local/bin:/root/.cargo/bin:/usr/local/cuda/bin:$PATH
export CUDA_HOME=/usr/local/cuda CUDACXX=/usr/local/cuda/bin/nvcc CC=gcc-13 CXX=g++-13 CUDAHOSTCXX=g++-13 TORCH_CUDA_ARCH_LIST=12.0
cd /sgl/sglang-official
git config user.email arc3@arc3 && git config user.name arc3
applied=0
for p in 0002-fp8-qsa-tile-dequant 0003-sm120-fp32-prefill-state 0001b-recoverssm-wy-sm120-PORTED; do
  git apply --exclude='test/*' ../fork/patches/$p.patch && applied=$((applied+1))
done
for p in 0004-sm120-lowm-triton-gemm 0005-sm120-fp8-weight-only 0006-sm120-fp8-hc-lmhead; do
  git am ../fork/patches/$p.patch && applied=$((applied+1))
done
test "$applied" = 6
git log -1 --format='%H' > /sgl/patched_commit.txt
uv venv --python 3.12 /opt/sglvenv >/dev/null && source /opt/sglvenv/bin/activate
export MAX_JOBS=16 CMAKE_BUILD_PARALLEL_LEVEL=16 CARGO_BUILD_JOBS=16
uv pip install --prerelease=allow --index-strategy unsafe-best-match --extra-index-url https://docs.sglang.ai/whl/cu130/ -e python > /sgl/install.log 2>&1
python -c "import sglang, torch; print('sglang', sglang.__version__, 'torch', torch.__version__, torch.version.cuda)" | tee /sgl/versions.txt
SGLBUILD
cat > /opt/arc3/sgl/serve.sh <<'SGLSERVE'
#!/bin/bash
# argv keeps the vLLM flag names the runtime probe reads back from `docker inspect flashnext` (Config.Cmd).
set -uo pipefail
MEMFRAC=""; KVD=""; CTX=""; LANES=""
while [ $# -gt 0 ]; do
  case "$1" in
    --gpu-memory-utilization) MEMFRAC=$2; shift 2;;
    --kv-cache-dtype) KVD=$2; shift 2;;
    --max-model-len) CTX=$2; shift 2;;
    --max-num-seqs) LANES=$2; shift 2;;
    *) echo "serve.sh: unknown argument $1"; exit 2;;
  esac
done
test -n "$MEMFRAC" && test -n "$KVD" && test -n "$CTX" && test -n "$LANES"
source /opt/sglvenv/bin/activate
export PATH=/root/.local/bin:/root/.cargo/bin:/usr/local/cuda/bin:$PATH
export CUDA_HOME=/usr/local/cuda CUDACXX=/usr/local/cuda/bin/nvcc CC=gcc-13 CXX=g++-13 CUDAHOSTCXX=g++-13 TORCH_CUDA_ARCH_LIST=12.0
CACHE=/sgl/cache; mkdir -p $CACHE/huggingface $CACHE/torchinductor $CACHE/triton $CACHE/flashinfer $CACHE/sglang/jit
export HF_HOME=$CACHE/huggingface XDG_CACHE_HOME=$CACHE TORCHINDUCTOR_CACHE_DIR=$CACHE/torchinductor TRITON_CACHE_DIR=$CACHE/triton
export FLASHINFER_WORKSPACE_BASE=$CACHE/flashinfer SGLANG_JIT_CACHE_DIR=$CACHE/sglang/jit
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True SGLANG_ALLOW_OVERWRITE_LONGER_CONTEXT_LEN=1 OMP_NUM_THREADS=8 TOKENIZERS_PARALLELISM=false
export MAX_JOBS=4 CMAKE_BUILD_PARALLEL_LEVEL=4 FLASHINFER_NINJA_JOBS=4 FLASHINFER_NVCC_THREADS=2 TORCHINDUCTOR_COMPILE_THREADS=4
export SGLANG_SM120_LOWM_FP8_WEIGHT=1 SGLANG_SM120_LM_HEAD_FP8=1 HF_HUB_OFFLINE=1
exec python -m sglang.launch_server --model-path /model --load-format safetensors --served-model-name "$SERVED_MODEL_NAME" \
  --host 127.0.0.1 --port 1235 --tp 1 --dtype bfloat16 --quantization modelopt_fp4 \
  --mem-fraction-static "$MEMFRAC" --context-length "$CTX" --kv-cache-dtype "$KVD" --page-size 64 \
  --max-running-requests "$LANES" --cuda-graph-max-bs "$LANES" --chunked-prefill-size 4096 \
  --mamba-ssm-dtype bfloat16 --max-mamba-cache-size 48 --mamba-radix-cache-strategy extra_buffer --mamba-track-interval 64 \
  --linear-attn-decode-backend flashinfer --linear-attn-prefill-backend flashinfer \
  --ple-offload-embedding --trust-remote-code --chat-template /model/chat_template.jinja \
  --reasoning-parser qwen3 --tool-call-parser qwen3_coder --enable-metrics --watchdog-timeout 1800 \
  --speculative-algorithm NEXTN --speculative-num-steps 3 --speculative-eagle-topk 1 --speculative-num-draft-tokens 4 \
  --speculative-draft-model-quantization unquant --speculative-token-map /sgl/hot_tokens_64k.pt --gdn-mtp-cache-mode none \
  --speculative-accept-threshold-single 1.0 --speculative-accept-threshold-acc 1.0 \
  --enable-hierarchical-cache --hicache-size 64 --hicache-write-policy write_through --hicache-io-backend kernel --hicache-mem-layout page_first
SGLSERVE
docker pull -q "$SGL_IMAGE_BASE"
docker run --rm --gpus all "$SGL_IMAGE_BASE" nvidia-smi -L
docker rm -f sglbuild >/dev/null 2>&1 || true
docker run --name sglbuild --gpus all --network=host -v /opt/arc3/sgl:/sgl "$SGL_IMAGE_BASE" bash /sgl/build.sh
docker commit sglbuild "$SGL_IMAGE" >/dev/null
docker rm sglbuild >/dev/null
cp /opt/arc3/sgl/versions.txt /opt/arc3/sglang-versions.txt

# Immutable, checksummed GCS mirror attestation (unchanged model payload; golden image carries it).
MODEL_GCS_PREFIX='gs://cellens-ai-artifacts/arc3-duck/models/qwen3.8-flash-next-nvfp4-radixark/7b719225242aacd3dbd3f9407468c2ee9a9d2594'
gcloud storage cp "$MODEL_GCS_PREFIX/_mirror/DONE" /opt/arc3/model-mirror-done.json
gcloud storage cp "$MODEL_GCS_PREFIX/_mirror/MANIFEST.json" /opt/arc3/model-mirror-manifest.json
if [ -n "$GOLDEN_RUNTIME_IMAGE" ]; then
  printf 'golden runtime image %s: immutable model payload reused\n' "$GOLDEN_RUNTIME_IMAGE" | \
    tee /opt/arc3/model-download.log
else
  gcloud storage rsync --recursive "$MODEL_GCS_PREFIX" "$MODEL_DIR" \
    2>&1 | tee /opt/arc3/model-download.log
fi
ARC3_GOLDEN_RUNTIME_IMAGE="$GOLDEN_RUNTIME_IMAGE" /opt/arc3/pysrv/bin/python - <<'PYVERIFY'
import hashlib
import json
import os
from pathlib import Path

model_id = "RadixArk/Qwen3.8-Flash-Next-NVFP4"
revision = "7b719225242aacd3dbd3f9407468c2ee9a9d2594"
manifest = json.loads(Path("/opt/arc3/model-mirror-manifest.json").read_text(encoding="utf-8"))
assert manifest["model_id"] == model_id
assert manifest["revision"] == revision
assert manifest["resolved_revision"] == revision
assert manifest["file_count"] == len(manifest["files"])
assert manifest["total_bytes"] == sum(row["size"] for row in manifest["files"])
for row in manifest["files"]:
    path = Path("/opt/arc3/flashnext-model") / row["path"]
    assert path.is_file(), f"missing mirrored model file: {row['path']}"
    assert path.stat().st_size == row["size"], f"size drift: {row['path']}"
    if not os.environ.get("ARC3_GOLDEN_RUNTIME_IMAGE"):
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(16 * 1024 * 1024), b""):
                digest.update(block)
        assert digest.hexdigest() == row["sha256"], f"sha256 drift: {row['path']}"
print(
    "golden image size-manifest attestation passed"
    if os.environ.get("ARC3_GOLDEN_RUNTIME_IMAGE")
    else "full model SHA-256 verification passed",
    flush=True,
)
PYVERIFY
/opt/arc3/pysrv/bin/python - <<'PYINFO'
import json
with open("/opt/arc3/flashnext-model/download-info.json", "w", encoding="utf-8") as fh:
    json.dump({
        "model_id": "RadixArk/Qwen3.8-Flash-Next-NVFP4",
        "revision": "7b719225242aacd3dbd3f9407468c2ee9a9d2594",
        "source": "gs://cellens-ai-artifacts/arc3-duck/models/qwen3.8-flash-next-nvfp4-radixark/7b719225242aacd3dbd3f9407468c2ee9a9d2594/",
        "verified_from_manifest": True,
    }, fh, indent=2)
PYINFO
/opt/arc3/pysrv/bin/python - <<'PYINFO'
import json
from pathlib import Path

root = Path("/opt/arc3/flashnext-model")
download = json.loads((root / "download-info.json").read_text())
info = {
    **download,
    "quantization": "RadixArk NVFP4 routed experts; served by SGLang (sglang-flashnext-sm120 patches: fp8 KV, fp8 weight copies, fp8 QSA tile dequant)",
    "serving": "sglang",
    "sglang_commit": Path("/opt/arc3/sgl/sglang_commit.txt").read_text().strip(),
    "sglang_fork_commit": Path("/opt/arc3/sgl/fork_commit.txt").read_text().strip(),
    "sglang_patched_commit": Path("/opt/arc3/sgl/patched_commit.txt").read_text().strip(),
    "mtp_enabled": True,
    "speculative": "NEXTN k=3, 4 draft tokens, lossless acceptance, FR-Spec 64k token map",
    "hierarchical_host_cache_gb": 64,
    "requested_server_sequences": 7,
    "games_in_flight": 7,
    "context_length": 67584,
}
Path("/opt/arc3/model-info.json").write_text(json.dumps(info, indent=2) + "\n")
PYINFO

# vLLM-compat shim in front of SGLang: the harness needs /tokenize (messages+tools+images -> {count, max_model_len}),
# max_model_len on /v1/models, and preserve_thinking as a default chat-template kwarg (vLLM had it server-side).
cat > /opt/arc3/sgl_proxy.py <<'PYPROXY'
import json, sys, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
LISTEN, UPSTREAM, MAX_MODEL_LEN = int(sys.argv[1]), sys.argv[2], int(sys.argv[3])
HOP = {"connection", "keep-alive", "transfer-encoding", "content-length", "host", "accept-encoding"}
DEFAULT_MODEL = [None]

def with_defaults(payload):
    kw = dict(payload.get("chat_template_kwargs") or {})
    kw.setdefault("preserve_thinking", True)
    payload["chat_template_kwargs"] = kw
    return payload

class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""
    def _send(self, code, payload, ctype="application/json"):
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload)
    def _upstream(self, method, path, body, headers, timeout=3600):
        req = urllib.request.Request(UPSTREAM + path, data=body if body else None, method=method)
        for k, v in headers.items():
            if k.lower() not in HOP: req.add_header(k, v)
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            return e
    def _stream(self, r):
        self.send_response(r.code if hasattr(r, "code") else r.status)
        for k, v in r.headers.items():
            if k.lower() not in HOP: self.send_header(k, v)
        self.send_header("Transfer-Encoding", "chunked"); self.end_headers()
        while True:
            chunk = r.read(65536)
            if not chunk: break
            self.wfile.write(b"%x\r\n" % len(chunk) + chunk + b"\r\n"); self.wfile.flush()
        self.wfile.write(b"0\r\n\r\n")
    def _passthrough(self, method):
        body = self._body()
        self._stream(self._upstream(method, self.path, body, dict(self.headers)))
    def _model(self):
        if DEFAULT_MODEL[0] is None:
            data = json.loads(self._upstream("GET", "/v1/models", None, {}).read())
            DEFAULT_MODEL[0] = data["data"][0]["id"]
        return DEFAULT_MODEL[0]
    def do_GET(self):
        if self.path.split("?")[0] in ("/v1/models", "/models"):
            r = self._upstream("GET", "/v1/models", None, {})
            data = json.loads(r.read())
            for row in data.get("data", []): row["max_model_len"] = MAX_MODEL_LEN
            return self._send(200, json.dumps(data).encode())
        return self._passthrough("GET")
    def do_POST(self):
        route = self.path.split("?")[0]
        if route == "/tokenize":
            payload = json.loads(self._body() or b"{}")
            model = payload.get("model") or self._model()
            if "messages" in payload:
                msgs = []
                for m in payload["messages"]:   # the harness counts with the vLLM alias `reasoning`; render it as the completion will
                    m = dict(m)
                    if m.get("reasoning") is not None and m.get("reasoning_content") is None:
                        m["reasoning_content"] = m.pop("reasoning")
                    msgs.append(m)
                fwd = {"model": model, "messages": msgs, "max_tokens": 1, "temperature": 0.0, "stream": False}
                if payload.get("tools"): fwd["tools"] = payload["tools"]
                if payload.get("chat_template_kwargs") is not None: fwd["chat_template_kwargs"] = payload["chat_template_kwargs"]
                fwd = with_defaults(fwd)
                r = self._upstream("POST", "/v1/chat/completions", json.dumps(fwd).encode(), {"Content-Type": "application/json"}, timeout=900)
            else:
                fwd = {"model": model, "prompt": payload.get("prompt", ""), "max_tokens": 1, "temperature": 0.0, "stream": False}
                r = self._upstream("POST", "/v1/completions", json.dumps(fwd).encode(), {"Content-Type": "application/json"}, timeout=900)
            raw = r.read()
            if (r.code if hasattr(r, "code") else r.status) != 200:
                return self._send(502, raw)
            n = json.loads(raw)["usage"]["prompt_tokens"]
            return self._send(200, json.dumps({"count": int(n), "max_model_len": MAX_MODEL_LEN, "tokens": []}).encode())
        if route in ("/v1/chat/completions", "/chat/completions"):
            body = self._body()
            try:
                payload = json.loads(body or b"{}")
            except ValueError:
                payload = None
            if isinstance(payload, dict):
                body = json.dumps(with_defaults(payload)).encode()
            r = self._upstream("POST", self.path, body, {k: v for k, v in self.headers.items() if k.lower() != "content-length"})
            return self._stream(r)
        return self._passthrough("POST")

ThreadingHTTPServer.daemon_threads = True
ThreadingHTTPServer(("127.0.0.1", LISTEN), H).serve_forever()
PYPROXY

start_server() {
  local kv_dtype="$1"
  docker rm -f flashnext >/dev/null 2>&1 || true
  pkill -f "docker logs -f flashnext" >/dev/null 2>&1 || true
  pkill -f sgl_proxy.py >/dev/null 2>&1 || true
  : > /opt/arc3/vllm.log
  # --privileged: Spot hosts have revoked the container's GPU cgroup rule mid-run ("Failed to initialize NVML: Unknown Error").
  docker run -d --name flashnext --hostname arc3-vllm --privileged --gpus all --ipc=host --network=host \
    --ulimit memlock=-1 \
    -e SERVED_MODEL_NAME="$SERVED_MODEL_NAME" \
    -v /opt/arc3/sgl:/sgl \
    -v "$MODEL_DIR:/model:ro" \
    "$SGL_IMAGE" bash /sgl/serve.sh \
    --gpu-memory-utilization 0.95 --kv-cache-dtype "$kv_dtype" \
    --max-model-len 67584 --max-num-seqs 7
  nohup docker logs -f flashnext > /opt/arc3/vllm.log 2>&1 &
  nohup /opt/arc3/pysrv/bin/python /opt/arc3/sgl_proxy.py 1234 http://127.0.0.1:1235 67584 > /opt/arc3/sgl-proxy.log 2>&1 &
}

wait_server() {
  # weights ~7 min + MTP CUDA graph capture ~13 min on this card
  for _ in $(seq 1 240); do
    if curl -sf -m 3 http://127.0.0.1:1235/health >/dev/null && curl -sf -m 3 http://127.0.0.1:1234/v1/models | grep -q max_model_len; then return 0; fi
    docker inspect -f '{{.State.Running}}' flashnext 2>/dev/null | grep -qx true || return 1
    sleep 10
  done
  return 1
}

# Experimental KV choice is explicit. No fallback to a different profile.
container_gpu_ready() {
  docker run --rm --gpus all "$SGL_IMAGE_BASE" nvidia-smi -L
}

if ! container_gpu_ready; then
  sleep 10
  container_gpu_ready
fi
KV_DTYPE_USED=fp8_e4m3
start_server "$KV_DTYPE_USED"
if ! wait_server; then
  cp /opt/arc3/vllm.log /opt/arc3/vllm-start-attempt1.log
  sleep 10
  container_gpu_ready
  start_server "$KV_DTYPE_USED"
fi
if ! wait_server; then
  echo "SGLang failed to serve the requested profile" | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"
  sync_all
  exit 1
fi
echo "$KV_DTYPE_USED" > /opt/arc3/kv-dtype-used.txt

docker exec -i flashnext /opt/sglvenv/bin/python - <<'PYVERS' > /opt/arc3/serving-environment.txt
import platform
import torch
import transformers
import sglang
print("python", platform.python_version())
print("sglang", sglang.__version__)
print("torch", torch.__version__)
print("transformers", transformers.__version__)
print("cuda", torch.version.cuda)
PYVERS
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu \
  --format=csv,noheader > /opt/arc3/gpu-after-load.csv
free -h > /opt/arc3/ram-after-load.txt

# Verify ordinary text, vision, and 7 simultaneous long-prefix requests before
# starting gameplay.  Thinking is disabled only for this capacity smoke test.
export KV_DTYPE_USED
run_smoke() {
/opt/arc3/pysrv/bin/python - <<'PYSMOKE'
import base64
import concurrent.futures
import json
import os
import time
import urllib.request

URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL = "RadixArk/Qwen3.8-Flash-Next-NVFP4"

def call(messages, max_tokens=64, timeout=900):
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False, "preserve_thinking": True},
    }
    request = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("choices"):
        raise RuntimeError(result)
    choice = result["choices"][0]
    message = choice.get("message") or {}
    material = " ".join([
        str(choice.get("text") or ""),
        str(message.get("content") or ""),
        str(message.get("reasoning_content") or ""),
    ])
    if not material.strip() or "nan" in material.lower():
        raise RuntimeError({"invalid_generated_material": material, "response": result})
    return {"seconds": time.monotonic() - started, "response": result}

text = call([{"role": "user", "content": "Return exactly READY."}], max_tokens=32)

png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
vision = call([{"role": "user", "content": [
    {"type": "text", "text": "Describe this one-pixel image in one word."},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64," + png}},
]}], max_tokens=32)

filler = "x " * 9000
def capacity_call(index):
    return call([{"role": "user", "content": (
        "This is capacity probe %d. Ignore the filler and return only OK. " % index
    ) + filler}], max_tokens=16)

capacity_started = time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=7) as pool:
    capacity = list(pool.map(capacity_call, range(7)))
capacity_seconds = time.monotonic() - capacity_started

summary = {
    "model": MODEL,
    "kv_dtype": os.environ["KV_DTYPE_USED"],
    "mtp_enabled": True,
    "max_num_seqs": 7,
    "text": text,
    "vision": vision,
    "capacity": {
        "requests": len(capacity),
        "wall_seconds": capacity_seconds,
        "min_seconds": min(x["seconds"] for x in capacity),
        "max_seconds": max(x["seconds"] for x in capacity),
        "mean_seconds": sum(x["seconds"] for x in capacity) / len(capacity),
        "all_returned": all(x["response"].get("choices") for x in capacity),
    },
}
with open("/opt/arc3/model-smoke.json", "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=2)
print(json.dumps(summary["capacity"], indent=2), flush=True)
PYSMOKE
}

if ! run_smoke; then
  echo "Experimental capacity smoke failed; no KV fallback" | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"
  sync_all
  exit 1
fi

# Capture the final serving process for this exact experimental profile.
docker exec -i flashnext /opt/sglvenv/bin/python - <<'PYVERS' > /opt/arc3/serving-environment.txt
import platform
import torch
import transformers
import sglang
print("python", platform.python_version())
print("sglang", sglang.__version__)
print("torch", torch.__version__)
print("transformers", transformers.__version__)
print("cuda", torch.version.cuda)
PYVERS
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu \
  --format=csv,noheader > /opt/arc3/gpu-after-load.csv
free -h > /opt/arc3/ram-after-load.txt
sync_all

# SGLang serving gate. Replaces the vLLM native-context capacity gate (it reads vllm:* prefix-cache metrics that do
# not exist here). Tests what actually risks this arm: LANES concurrent long-prefix completions, a vision request, a
# tool call that comes back parsed, and /tokenize == usage.prompt_tokens on text+tools, an image, and the selftest
# fixture (4 x 1024px images + reasoning history rendered through the `reasoning` alias).
/opt/arc3/pysrv/bin/python - <<'PYSGLGATE' 2>&1 | tee /opt/arc3/sglang-serving-gate.log
import base64, json, struct, time, urllib.request, zlib
from concurrent.futures import ThreadPoolExecutor
URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL = "RadixArk/Qwen3.8-Flash-Next-NVFP4"
LANES = 7

def post(payload, timeout=900):
    req = urllib.request.Request(URL, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    started = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as fh:
        body = json.load(fh)
    return body, time.monotonic() - started

filler = "The board is a grid. " * 3000
def long_call(index):
    body, seconds = post({"model": MODEL, "max_tokens": 32, "temperature": 0.7, "top_p": 0.95,
                          "chat_template_kwargs": {"enable_thinking": False},
                          "messages": [{"role": "user", "content": f"Probe {index}. {filler} Reply OK."}]})
    return {"index": index, "seconds": seconds, "ok": bool(body.get("choices"))}

started = time.monotonic()
with ThreadPoolExecutor(max_workers=LANES) as pool:
    concurrent = list(pool.map(long_call, range(LANES)))
concurrent_seconds = time.monotonic() - started

# the 1x1 PNG the startup smoke test already sends successfully (the 2x2 hex blob from the llama.cpp arm is not a valid PNG: SGLang 400s it)
png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
base64.b64decode(png)
vision, vision_seconds = post({"model": MODEL, "max_tokens": 24, "temperature": 0.7, "chat_template_kwargs": {"enable_thinking": False}, "messages": [
    {"role": "user", "content": [{"type": "text", "text": "Name one colour in this image."},
                                 {"type": "image_url", "image_url": {"url": "data:image/png;base64," + png}}]}]})

tools = [{"type": "function", "function": {
    "name": "python", "description": "Run a Python snippet against the current game.",
    "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}}}]
tool_body, tool_seconds = post({"model": MODEL, "max_tokens": 512, "temperature": 0.7, "tools": tools,
                                "chat_template_kwargs": {"enable_thinking": False}, "messages": [
    {"role": "user", "content": "Call the python tool with code that sets result to 2+2. Do not answer in text."}]})
message = tool_body["choices"][0]["message"]
tool_calls = message.get("tool_calls") or []

def count_tokens(messages, tools=None):
    body = {"model": MODEL, "messages": messages, "add_generation_prompt": True, "chat_template_kwargs": {"enable_thinking": False}}
    if tools: body["tools"] = tools
    req = urllib.request.Request(URL.replace("/v1/chat/completions", "/tokenize"), data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as fh:
        data = json.load(fh)
    assert data["max_model_len"] == 67584, data
    return data["count"]
def usage_tokens(messages, tools=None):
    body = {"model": MODEL, "messages": messages, "max_tokens": 1, "temperature": 0.0, "chat_template_kwargs": {"enable_thinking": False}}
    if tools: body["tools"] = tools
    return post(body)[0]["usage"]["prompt_tokens"]
text_msgs = [{"role": "system", "content": "You play a grid game."}, {"role": "user", "content": "Probe. " + filler[:4000] + " Reply OK."}]
img_msgs = [{"role": "user", "content": [{"type": "text", "text": "Name one colour in this image."},
                                          {"type": "image_url", "image_url": {"url": "data:image/png;base64," + png}}]}]
tok_text, use_text = count_tokens(text_msgs, tools), usage_tokens(text_msgs, tools)
tok_img, use_img = count_tokens(img_msgs), usage_tokens(img_msgs)
def png_rgb(w, h, rgb=(0, 0, 0)):
    raw = b''.join(bytes([0]) + bytes(rgb) * w for _ in range(h))
    def chunk(t, d): return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    sig = bytes([137, 80, 78, 71, 13, 10, 26, 10])
    return sig + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b'')
big = base64.b64encode(png_rgb(1024, 1024)).decode()
fixture = [{'role': 'system', 'content': 'You play a grid game.'}]
for i in range(4):
    fixture += [{'role': 'user', 'content': [{'type': 'text', 'text': 'Synthetic frame ' + str(i)}, {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + big}}]},
                {'role': 'assistant', 'content': 'Observed.', 'reasoning_content': 'The red square stayed in place.'}]
fixture.append({'role': 'user', 'content': 'Validation only. Reply OK.'})
aliased = [({**m, 'reasoning': m['reasoning_content']} if 'reasoning_content' in m else m) for m in fixture]
for m in aliased: m.pop('reasoning_content', None)
tok_fix, use_fix = count_tokens(aliased, tools), usage_tokens(fixture, tools)
report = {
    "tokenize_text_tools": [tok_text, use_text], "tokenize_image": [tok_img, use_img], "tokenize_selftest_fixture": [tok_fix, use_fix],
    "concurrent_requests": len(concurrent), "concurrent_wall_seconds": round(concurrent_seconds, 1),
    "all_concurrent_returned": all(x["ok"] for x in concurrent),
    "slowest_concurrent_seconds": round(max(x["seconds"] for x in concurrent), 1),
    "vision_seconds": round(vision_seconds, 1),
    "vision_returned": bool(vision.get("choices")),
    "tool_seconds": round(tool_seconds, 1),
    "tool_calls_parsed": len(tool_calls),
    "tool_call_name": (tool_calls[0]["function"]["name"] if tool_calls else None),
    "tool_call_markup_in_content": "<tool_call>" in str(message.get("content") or ""),
    "serving": "sglang", "lanes": LANES, "context": 67584,
}
print(json.dumps(report, indent=2), flush=True)
with open("/opt/arc3/sglang-serving-gate.json", "w", encoding="utf-8") as fh:
    json.dump(report, fh, indent=2)
assert report["all_concurrent_returned"], "concurrent long-prefix completions failed"
assert report["vision_returned"], "vision request failed; the harness sends current_grid images"
assert report["tool_calls_parsed"] >= 1, "no parsed tool call came back; the harness cannot act"
assert tok_text == use_text, ("/tokenize count differs from usage.prompt_tokens (text+tools)", tok_text, use_text)
assert tok_img == use_img, ("/tokenize count differs from usage.prompt_tokens (image)", tok_img, use_img)
assert tok_fix == use_fix, ("/tokenize count differs from usage.prompt_tokens (selftest fixture: 4 x 1024px image + reasoning)", tok_fix, use_fix)
PYSGLGATE
timeout 15 gcloud storage cp /opt/arc3/sglang-serving-gate.json "$BUCKET/$RUN_ID/sglang-serving-gate.json" || true
sync_all

# Install the pinned environment and run the experimental candidate on all 25 games.
cd /opt/arc3/ARC3-Inference
export CONFIG_PATH=configs/tufa0.json TAAF_PERIODIC_SAVE_INTERVAL_S=120
if [ -n "$GOLDEN_RUNTIME_IMAGE" ]; then
  test -x ./.venv/bin/python
  ./.venv/bin/python -c 'import numpy, openai, PIL; print("golden runtime: harness environment import check passed")'
else
  make install-a108
fi
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
export LOCAL_ANALYZER_CONTEXT_WINDOW=67584 LOCAL_ANALYZER_MAX_OUTPUT=0
export LOCAL_ANALYZER_TOOL_STEPS=0 LOCAL_ANALYZER_TOOL_TIMEOUT=30 LOCAL_ANALYZER_TOOL_OUTPUT_TOKENS=1024
export LOCAL_ANALYZER_YIELD_SECONDS=60 LOCAL_ANALYZER_TEMPERATURE=1.0 LOCAL_ANALYZER_TOP_P=0.95 LOCAL_ANALYZER_TOP_K=20
export ARC3_ANIMATION_CHECKPOINT_ENABLED=1 ARC3_ANIMATION_CHECKPOINT_MIN_CHANGED=2 ARC3_ANIMATION_EXPOSED_KEYFRAMES=12 ARC3_ANIMATION_BASELINE_MIN_SAMPLES=5 ARC3_ANIMATION_FAMILY_MIN_SAMPLES=5 ARC3_ANIMATION_HUD_BORDER=0 ARC3_ANIMATION_MIN_SPATIAL_FRAMES=4 ARC3_ANIMATION_MIN_SPATIAL_UNIQUE_CELLS=8 ARC3_ANIMATION_MIN_SPATIAL_CHANGE_SUM=32 ARC3_ANIMATION_STORYBOARD_MAX_TOKENS=2000 ARC3_ANIMATION_CHECKPOINT_MAX_PER_LEVEL=3 ARC3_ANIMATION_CHECKPOINT_COOLDOWN_ACTIONS=5
export LOCAL_ANALYZER_ENABLE_THINKING=true MULTIMODAL_CONTEXT=current_grid MULTIMODAL_UPSCALE=4
export ARC3_PROMPT_ABLATE_VIEW=0
export ARC3_PROMPT_ABLATE_LOOP=0
export ARC3_SERVING_SPECULATIVE=sglang-nextn3-c67584-w7
export ARC3_PROMPT_ABLATE_SEARCH=1
export ARC3_PROMPT_ABLATE_COORDS=0
export ARC3_PROMPT_ABLATE_PRIORS=0
export ARC3_PROMPT_ABLATE_TRANSITION=0
export ARC3_ACTION_CAP=14
export ARC3_ACTION_CAP_MODE=return
export ARC3_CONTEXT_COMPACTION=1
export ARC3_POST_LEVEL_UNCAPPED_TURNS=0
unset ARC3_REPLAY_ENABLED ARC3_REPLAY_ARM ARC3_REPLAY_TRIGGER_REMINDER
unset ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED
unset ARC3_SAME_CONTEXT_LEVEL_REFLECTION_VERSION
unset ARC3_CONTEXT_COMPACTION_ENABLED ARC3_CONTEXT_COMPACTION_TRIGGER_FRACTION
unset ARC3_CONTEXT_COMPACTION_KEEP_ASSISTANT_TURNS ARC3_CONTEXT_COMPACTION_MAX_TOKENS
unset ARC3_CONTEXT_TRIM_TARGET ARC3_CONTEXT_TRIM_TARGET_FRACTION ARC3_CONTEXT_HISTORY_MAX_ASSISTANT_TURNS
export LOCAL_ANALYZER_CONTEXT_WINDOW=67584
export ARC3_PERSISTENT_HISTORY_ASSISTANT_TURNS=30
unset ARC3_VISUAL_TRANSITION_MODE
export ARC3_BUDGET_REMINDER_ENABLED=1
export ARC3_BUDGET_GUIDANCE=time_only
unset ARC3_REASONING_POLICY
unset ARC3_COMMON_THEMES_PATH ARC3_COMMON_THEMES_INJECTION_LOG
export ARC3_EXECUTION_MODE=0
export ARC3_PERSISTENT_GAME_MODEL=0
export ARC3_EXECUTION_CONFIRMATIONS=2
export ARC3_EXECUTION_LEASE_ACTIONS=3
export ARC3_SYMBOLIC_SEARCH=0
export ARC3_PROGRAMMATIC_WORKSPACE=0
export ARC3_BENCHMARK_CONCURRENCY=7
export ARC3_MAX_RUNTIME_S_PER_GAME=2061
export ARC3_MAX_RUN_RUNTIME_MINUTES=132
export ARC3_REEXPLORE_STRICT="" ARC3_GAME_SUBSET="" ARC3_STATE_GRAPH="" ARC3_FRAME_MODE=full

export ARC3_HISTORY_MODE=full_context
# Exact arm CPU regressions and one bounded model-authored probe; no game actions.
echo '9819c16bb12a0480647f2aab593596d20140d813a43600ea187a3230b4d00b83  /opt/arc3/execution-selftest/linux_selftest_matrix.py' | sha256sum -c -
PYTHONPATH=/opt/arc3/execution-selftest/candidate/src/ARC3-Inference \
  ./.venv/bin/python -B /opt/arc3/execution-selftest/linux_selftest_matrix.py \
  --live --arm baseline --model "$SERVED_MODEL_NAME" --context 67584 \
  --output /opt/arc3/execution-selftest.json \
  2>&1 | tee /opt/arc3/execution-selftest.log

gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/astra-execution/feature-ablation-132-v1/11db93bca6d982d4c129680df7d241a715df5a8eca5f4a2cbef950e73014570d/full_context_live_matrix.py' /opt/arc3/full_context_live_matrix.py
echo '11db93bca6d982d4c129680df7d241a715df5a8eca5f4a2cbef950e73014570d  /opt/arc3/full_context_live_matrix.py' | sha256sum -c -
timeout --kill-after=10 600 ./.venv/bin/python -B /opt/arc3/full_context_live_matrix.py \
  --packet /opt/arc3/execution-selftest --output /opt/arc3/full-context-selftest.json \
  --live --context 67584 --base-url http://127.0.0.1:1234/v1 --model "$SERVED_MODEL_NAME" \
  2>&1 | tee /opt/arc3/full-context-selftest.log
export ARC3_HISTORY_MODE=full_context

test "$INFLUENCE_MODE" = none
echo "cross-game curator disabled in every feature arm"

sync_all

./.venv/bin/python -B /opt/arc3/execution-selftest/test_canary_retry.py
TEST_FULL_CONTEXT=1 ./.venv/bin/python -B /opt/arc3/execution-selftest/test_prompt_ablation.py > /opt/arc3/prompt-selftest.log 2>&1
# Verify reminder ON/OFF request assembly and full-context persistence on installed source.
TEST_FULL_CONTEXT=1 ./.venv/bin/python -B /opt/arc3/execution-selftest/test_reminder_requests.py \
  > /opt/arc3/reminder-selftest.log 2>&1
TEST_FULL_CONTEXT=1 ./.venv/bin/python -B /opt/arc3/execution-selftest/test_time_guidance.py > /opt/arc3/time-guidance-selftest.log 2>&1
./.venv/bin/python - <<'PYREMINDER'
import hashlib, json, os
from pathlib import Path
from inference.agent.tool_agent import ToolAgent
agent = ToolAgent()
enabled = os.environ['ARC3_BUDGET_REMINDER_ENABLED'] == '1'
assert (agent._budget_reminder is not None) == enabled
assert agent._full_context_tokens is not None
assert agent._budget_reminder.mode == 'time_only' and agent._budget_reminder.target_tokens is None
report = {'status':'passed', 'enabled':enabled, 'target_tokens':agent._budget_reminder.target_tokens, 'guidance_mode':agent._budget_reminder.mode,
          'source':'cumulative backend completion tokens', 'hard_token_limit':None,
          'full_context':True, 'input_budget':agent._context_budget_tokens,
          'agent_sha256':hashlib.sha256(Path(__import__('inference.agent.tool_agent',fromlist=['']).__file__).read_bytes()).hexdigest()}
Path('/opt/arc3/reminder-runtime-identity.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
PYREMINDER

./.venv/bin/python /opt/arc3/bundle/pre_harness_warmup.py \
  --model "$SERVED_MODEL_NAME" \
  --output /opt/arc3/pre-harness-warmup.json \
  2>&1 | tee /opt/arc3/pre-harness-warmup.log
./.venv/bin/python - <<'PYCHAMPION' 2>&1 | tee /opt/arc3/replay-selftest.log
import os
from pathlib import Path

from inference.agent import tool_agent

assert "ARC3_REPLAY_ENABLED" not in os.environ
assert "ARC3_REPLAY_ARM" not in os.environ
assert "ARC3_REPLAY_TRIGGER_REMINDER" not in os.environ
assert "ARC3_SAME_CONTEXT_LEVEL_REFLECTION_ENABLED" not in os.environ
assert os.environ["ARC3_ACTION_CAP"] == "14"
assert os.environ["ARC3_ACTION_CAP_MODE"] == "return"
assert os.environ["ARC3_CONTEXT_COMPACTION"] == "1"
assert os.environ['ARC3_PERSISTENT_GAME_MODEL'] == '0'
assert os.environ['ARC3_EXECUTION_MODE'] == '0'
assert os.environ['ARC3_SYMBOLIC_SEARCH'] == '0'
assert os.environ['ARC3_PROGRAMMATIC_WORKSPACE'] == '0'
assert os.environ['ARC3_EXECUTION_CONFIRMATIONS'] == '2'
assert os.environ['ARC3_EXECUTION_LEASE_ACTIONS'] == '3'
assert os.environ['ARC3_HISTORY_MODE'] == 'full_context'
assert os.environ['LOCAL_ANALYZER_CONTEXT_WINDOW'] == '67584'
assert os.environ['ARC3_BENCHMARK_CONCURRENCY'] == '7'
assert os.environ['ARC3_MAX_RUNTIME_S_PER_GAME'] == '2061'
assert os.environ['ARC3_MAX_RUN_RUNTIME_MINUTES'] == '132'
assert os.environ["ARC3_POST_LEVEL_UNCAPPED_TURNS"] == "0"
assert tool_agent._PERSISTENT_HISTORY_ASSISTANT_TURNS == 30
agent = tool_agent.ToolAgent()
assert (agent._execution_mode is not None) == False
assert agent._full_context_tokens is not None
assert agent._context_budget_tokens == 58880
assert "Lossless replay memory:" not in agent._system_prompt
assert "replay.repeated_states()" not in tool_agent._PYTHON_TOOL_DESCRIPTION
assert "Winning world model:" not in agent._system_prompt
import hashlib, json
manifest = json.loads(Path('/opt/arc3/execution-release-manifest.json').read_text())
for name, expected in manifest['candidate_files'].items():
    assert hashlib.sha256((Path('/opt/arc3/bundle') / name).read_bytes()).hexdigest() == expected, name
for name, expected in manifest['implementation']['candidate_source_sha256'].items():
    relative = name.removeprefix('src/ARC3-Inference/')
    assert hashlib.sha256((Path('/opt/arc3/ARC3-Inference') / relative).read_bytes()).hexdigest() == expected, name
runtime_tool_agent = Path(tool_agent.__file__).resolve()
bundle_tool_agent = Path("/opt/arc3/bundle/src/ARC3-Inference/inference/agent/tool_agent.py")
assert runtime_tool_agent == Path("/opt/arc3/ARC3-Inference/inference/agent/tool_agent.py").resolve()
assert runtime_tool_agent.read_bytes() == bundle_tool_agent.read_bytes()
from inference.agent.symbolic_search import search_symbolic_model
assert callable(search_symbolic_model)
agent = tool_agent.ToolAgent()
assert agent._symbolic_search_enabled is False
assert agent._programmatic_workspace_enabled is False
import sys, tempfile
sys.path.insert(0, "/opt/arc3/execution-selftest")
from feature_contract import assert_contract
with tempfile.TemporaryDirectory() as tmp:
    assert_contract(agent, Path(tmp) / "state.json", 'baseline')
print("verified feature arm baseline; no curator; 132-minute suite")
PYCHAMPION
mkdir -p /opt/arc3/work/score-observer
nice -n 19 ionice -c3 /opt/arc3/pysrv/bin/python /opt/arc3/arc3_minute_score_observer.py \
  --artifacts-dir /opt/arc3/work/artifacts \
  --output-dir /opt/arc3/work/score-observer \
  --interval-seconds 60 \
  > /opt/arc3/work/score-observer/observer.log 2>&1 &
SCORE_OBSERVER_PID=$!
echo "$SCORE_OBSERVER_PID" > /opt/arc3/work/score-observer/observer.pid

capture_gameplay_metrics() {
  local phase="$1"
  curl --fail --silent --show-error --max-time 10 --max-filesize 8388608 \
    http://127.0.0.1:1235/metrics \
    | grep -E '^sglang:' \
    > "/opt/arc3/gameplay-metrics-${phase}.txt" || true
}

# Runtime capacity evidence must exist even if a caller bypasses the insertion placeholder.
/opt/arc3/pysrv/bin/python - <<'PYCAPACITYFINAL'
import json
from pathlib import Path
report = json.loads(Path('/opt/arc3/sglang-serving-gate.json').read_text())   # SGLang arm: the serving gate is the capacity evidence
assert report['serving'] == 'sglang' and report['lanes'] == 7 and report['context'] == 67584
assert report['concurrent_requests'] == 7 and report['all_concurrent_returned'] is True
assert report['vision_returned'] is True and report['tool_calls_parsed'] >= 1
assert report['tokenize_text_tools'][0] == report['tokenize_text_tools'][1]
assert report['tokenize_image'][0] == report['tokenize_image'][1]
assert report['tokenize_selftest_fixture'][0] == report['tokenize_selftest_fixture'][1]
renderer = json.loads(Path('/opt/arc3/full-context-selftest.json').read_text())
assert renderer['status'] == 'passed'
assert renderer['context'] == 67584
assert renderer['input_budget'] == 58880
assert renderer['near_budget_multimodal_renderer_pass'] is True
assert renderer['production_mode_renderer_count_matches'] is True
PYCAPACITYFINAL
# New swap tests run with inherited fixture flags OFF, then production ON.
ARC3_HALF_CONTEXT_SWAP=0 ./.venv/bin/python -B /opt/arc3/execution-selftest/test_half_swap.py > /opt/arc3/half-swap-tests.log 2>&1
ARC3_HALF_CONTEXT_SWAP=0 ./.venv/bin/python -B /opt/arc3/execution-selftest/test_half_swap_integration.py >> /opt/arc3/half-swap-tests.log 2>&1
export ARC3_ROLLING_HALF_CHECKPOINT=0
export ARC3_HALF_CONTEXT_SWAP=1
timeout --kill-after=10 300 ./.venv/bin/python -B /opt/arc3/execution-selftest/live_half_swap_gate.py 2>&1 | tee /opt/arc3/half-swap-live-gate.log
# Clear synthetic fixtures only after all live gates and warmup have settled (SGLang: /flush_cache drops the radix tree).
curl -sf -m 30 -X POST http://127.0.0.1:1235/flush_cache > /opt/arc3/native-context-prefix-reset.log 2>&1 || true
# SGLang exposes Prometheus counters at /metrics under sglang:* names; sample them every 30 s like the vLLM sampler did.
( while true; do
    printf '{"utc":"%s","body":%s}\n' "$(date -u +%FT%TZ)" \
      "$(curl -s -m 5 http://127.0.0.1:1235/metrics | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))' 2>/dev/null || echo '""')" \
      >> /opt/arc3/work/sglang-metrics.jsonl
    sleep 30
  done ) > /opt/arc3/work/sglang-metrics-sampler.log 2>&1 &
METRICS_SAMPLER_PID=$!
sleep 2
test -s /opt/arc3/work/sglang-metrics.jsonl
kill -0 "$METRICS_SAMPLER_PID"
# Keep enough of the fixed four-hour VM lifetime for the full suite and teardown.
test "$(cut -d. -f1 /proc/uptime)" -lt 6360
mkdir -p /opt/arc3/config-audit
gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/sglang-cv5cr-v1/fd627169239463d1cfb46bc60fe60d4aca3574d7d994f2e6a13852184069997f/CONFIG_FLAGS.json' /opt/arc3/config-audit/CONFIG_FLAGS.json
echo 'fd627169239463d1cfb46bc60fe60d4aca3574d7d994f2e6a13852184069997f  /opt/arc3/config-audit/CONFIG_FLAGS.json' | sha256sum -c -
gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/sglang-cv5cr-v1/685c4f6d42c46353337f2013e67eb5e9dbce9b4baa0648ae30a0c5268c079496/ADAPTER.json' /opt/arc3/config-audit/ADAPTER.json
echo '685c4f6d42c46353337f2013e67eb5e9dbce9b4baa0648ae30a0c5268c079496  /opt/arc3/config-audit/ADAPTER.json' | sha256sum -c -
gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/cap-compact132/64d537c9b113fa23f8092aecc167e6dce443349825d64fc6c1c6a328a369fad3/contract.py' /opt/arc3/config-audit/contract.py
echo '64d537c9b113fa23f8092aecc167e6dce443349825d64fc6c1c6a328a369fad3  /opt/arc3/config-audit/contract.py' | sha256sum -c -
gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/sglang-cv5cr-v1/3a67b0392d54107ed14e89bef346d1122f9f91d6b60e1d4103179b1bfc81e513/runtime_probe.py' /opt/arc3/config-audit/runtime_probe.py
echo '3a67b0392d54107ed14e89bef346d1122f9f91d6b60e1d4103179b1bfc81e513  /opt/arc3/config-audit/runtime_probe.py' | sha256sum -c -
gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/cap-compact132/d24188eab47927ba495247a78f2d0126a1036c976091e8e9fea70812dcabd631/prompt_probe.py' /opt/arc3/config-audit/prompt_probe.py
echo 'd24188eab47927ba495247a78f2d0126a1036c976091e8e9fea70812dcabd631  /opt/arc3/config-audit/prompt_probe.py' | sha256sum -c -
gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/cap-compact132/45369cb0c5bb34f228ef8564f19b40338c095238075fccd54a8ba23e3513d1ca/EXPECTED_PROMPTS.json' /opt/arc3/config-audit/EXPECTED_PROMPTS.json
echo '45369cb0c5bb34f228ef8564f19b40338c095238075fccd54a8ba23e3513d1ca  /opt/arc3/config-audit/EXPECTED_PROMPTS.json' | sha256sum -c -
ARC3_HALF_CONTEXT_SWAP=0 ./.venv/bin/python -B /opt/arc3/execution-selftest/test_action_cap_modes.py > /opt/arc3/action-cap-selftest.log 2>&1
./.venv/bin/python -B /opt/arc3/execution-selftest/test_compaction_mode.py > /opt/arc3/feature-selftest.log 2>&1
gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/cap-compact132/3796093bc39f0a0ec5436ae312a150d87c6262ea06a8bdaf5d25e5a7ed7c69b4/time_guidance_probe.py' /opt/arc3/config-audit/time_guidance_probe.py
echo '3796093bc39f0a0ec5436ae312a150d87c6262ea06a8bdaf5d25e5a7ed7c69b4  /opt/arc3/config-audit/time_guidance_probe.py' | sha256sum -c -
# vLLM watchdog: the 264-class hard-seven run lost its engine at minute 31 and spun for hours.
# Probe every 60 s; on 3 consecutive misses snapshot the log, restart with the same start_server/wait_server.
(
  fails=0; restarts=0
  while true; do
    sleep 60
    if curl -s -m 8 http://127.0.0.1:1234/v1/models >/dev/null 2>&1; then fails=0; continue; fi
    fails=$((fails+1))
    if [ "$fails" -lt 3 ]; then continue; fi
    restarts=$((restarts+1))
    echo "watchdog: server unreachable x$fails at $(date -u +%FT%TZ); restart #$restarts"
    cp /opt/arc3/vllm.log "/opt/arc3/vllm-crash-$restarts.log" 2>/dev/null || true
    timeout 30 gcloud storage cp "/opt/arc3/vllm-crash-$restarts.log" "$BUCKET/$RUN_ID/vllm-crash-$restarts.log" >/dev/null 2>&1 || true
    start_server "$KV_DTYPE_USED" || true
    if wait_server; then
      echo "watchdog: server back at $(date -u +%FT%TZ)"
      fails=0
    else
      echo "watchdog: restart #$restarts did not come up"
    fi
    echo "$restarts $(date -u +%FT%TZ)" | timeout 15 gcloud storage cp - "$BUCKET/$RUN_ID/SERVER_RESTARTS" >/dev/null 2>&1 || true
    if [ "$restarts" -ge 5 ]; then echo "watchdog: giving up after 5 restarts"; break; fi
  done
) &
WATCHDOG_PID=$!
capture_gameplay_metrics start
set +e
./.venv/bin/python /opt/arc3/config-audit/runtime_probe.py 2>&1 | tee /opt/arc3/v12.log
RUN_STATUS=${PIPESTATUS[0]}
set -e
kill -TERM "$METRICS_SAMPLER_PID" 2>/dev/null || true
wait "$METRICS_SAMPLER_PID" 2>/dev/null || true
capture_gameplay_metrics end
kill -TERM "$SCORE_OBSERVER_PID" 2>/dev/null || true
wait "$SCORE_OBSERVER_PID" 2>/dev/null || true
sync_all
if [ "$RUN_STATUS" -ne 0 ]; then
  echo "runner failed with status $RUN_STATUS" | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"
  exit "$RUN_STATUS"
fi

echo done | gcloud storage cp - "$BUCKET/$RUN_ID/DONE"
exit 0

