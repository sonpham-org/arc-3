#!/bin/bash
# DeepSeek-V4.1-Flash ceiling run: the la_v5_clean_return_a candidate byte-for-byte, model swapped.
# arm=dsv41_la_v5_long (25 lanes, 5 h/game, 330 min suite, 8 h VM). Server: vLLM TP8+EP on 8x RTX PRO 6000 (g4-standard-384),
# Engram tables CPU-offloaded, FP8 KV. Harness, lanes (7), clock, cap, compaction unchanged.
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
MODEL_ID="nvidia/DeepSeek-V4.1-Flash-NVFP4"
MODEL_REVISION="3431dde3247c13b5957f682b1e3c6fcae2566079"
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
  for telemetry in time-guidance-selftest.log feature-selftest.log half-swap-live-gate.json half-swap-live-gate.log half-swap-tests.log live-canary-attempts.json prompt-selftest.log reminder-selftest.log reminder-runtime-identity.json native-context-prefix-reset.json native-context-prefix-reset.log native-context-capacity-gate.json native-context-capacity-gate.log full-context-selftest.json full-context-selftest.log gameplay-metrics-start.txt gameplay-metrics-end.txt model-download.log ple-conversion.log gpu-after-load.csv ram-after-load.txt kv-dtype-used.txt vllm.log vllm-fp8-failed.log vllm-start-attempt1.log verified-queue-selftest.log hypothesis-lab-selftest.log replay-selftest.log pre-harness-warmup.json pre-harness-warmup.log execution-selftest.json execution-selftest.log execution-release-manifest.json retention-runtime-identity.json; do
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
      "https://compute.googleapis.com/compute/v1/projects/$project_id/zones/$ZONE/instances/$OWNED_VM_NAME?requestId=dc68a275-36d5-4078-87e3-d6587a75da1b" || true)
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

# Hard cost guard: 28800 seconds from VM startup, including setup.
(
  sleep 28800
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
echo 'dacbf9b9867cd4a1e618c6c1b688c39e0dcf8ff41d2a9eb3b084cfbcdd3ecc5d  /tmp/bundle.tgz' | sha256sum -c -
tar xzf /tmp/bundle.tgz -C /opt/arc3/bundle
# Activate only the immutable gameplay package carried by the audited bundle.
# Keep the pinned deployment project's Makefile, lockfile, and deployment-only
# config (including configs/tufa0.json), which are not part of the Kaggle bundle.
cp -a /opt/arc3/bundle/src/ARC3-Inference/inference/. /opt/arc3/ARC3-Inference/inference/
find /opt/arc3/ARC3-Inference/inference -type f -name '*.pyc' -delete
gcloud storage cp "$RUNNER_OBJECT" /opt/arc3/v12_run.py
echo '0200ccfb786f330e97cc3e07aa3a8ab0c372e557c772faae0547264b0ee52942  /opt/arc3/v12_run.py' | sha256sum -c -
gcloud storage cp "$SCORE_OBSERVER_OBJECT" /opt/arc3/arc3_minute_score_observer.py
python3 - <<'PYRUNLIMIT'
from pathlib import Path

path = Path('/opt/arc3/v12_run.py')
text = path.read_text(encoding='utf-8')
old = 'soft_end = datetime.now() + timedelta(hours=11, minutes=20)'
new = 'soft_end = datetime.now() + timedelta(minutes=330)'
if text.count(old) != 1:
    raise RuntimeError('runner soft-deadline anchor drift')
path.write_text(text.replace(old, new), encoding='utf-8')
PYRUNLIMIT
grep -F 'soft_end = datetime.now() + timedelta(minutes=330)' /opt/arc3/v12_run.py
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
echo '6878db943e954f5c3e68e77e0e2101bf8b9ade543ae94a03e0446efe105d96a5  /tmp/execution-selftest.tgz' | sha256sum -c -
tar xzf /tmp/execution-selftest.tgz -C /opt/arc3/execution-selftest
gcloud storage cp "$(meta arc3-release-manifest-object)" /opt/arc3/execution-release-manifest.json
echo '6723b454d56026e15be5366aa4028e24cc9f984cf5817b30bc741983300a0a61  /opt/arc3/execution-release-manifest.json' | sha256sum -c -
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

# DeepSeek-V4.1-Flash-NVFP4 via the vLLM image named on the NVIDIA model card, TP8.
# Engram tables (~183 GiB) are CPU-offloaded per the vLLM recipe; the g4-standard-384
# has 1440 GB host RAM. No PLE/qsa/scheduler overlays: those were Flash-Next patches.
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker.io
if ! command -v nvidia-ctk >/dev/null 2>&1; then
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nvidia-container-toolkit
fi
nvidia-ctk runtime configure --runtime=docker
systemctl enable --now docker

MODEL_DIR=/opt/arc3/flashnext-model
CONTAINER_IMAGE='vllm/vllm-openai:nightly'
mkdir -p "$MODEL_DIR" /opt/arc3/vllm-cache
nvidia-smi --query-gpu=name,memory.total --format=csv
NGPU=$(nvidia-smi -L | wc -l); RAM_GIB=$(awk '/MemTotal/ {printf "%d", $2/1048576}' /proc/meminfo)
echo "gpus=$NGPU host_ram_gib=$RAM_GIB"
test "$NGPU" = 8
test "$RAM_GIB" -ge 400

docker pull "$CONTAINER_IMAGE"
docker inspect --format '{{index .RepoDigests 0}}' "$CONTAINER_IMAGE" | tee /opt/arc3/vllm-image-digest.txt \
  | gcloud storage cp - "$BUCKET/$RUN_ID/vllm-image-digest.txt"
docker run --rm --gpus all --entrypoint nvidia-smi "$CONTAINER_IMAGE"
CONTAINER_PYTHON=$(docker run --rm --entrypoint /bin/sh "$CONTAINER_IMAGE" -lc '
  entry=$(command -v vllm)
  first=$(head -n 1 "$entry")
  case "$first" in
    "#!"*)
      candidate=${first#\#!}
      set -- $candidate
      if [ "$1" = /usr/bin/env ] && [ -n "${2:-}" ]; then
        command -v "$2" && exit 0
      fi
      [ -x "$1" ] && { printf "%s\n" "$1"; exit 0; }
      ;;
  esac
  for candidate in /opt/venv/bin/python /opt/venv/bin/python3 /opt/uv/python/*/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
    [ -x "$candidate" ] && { printf "%s\n" "$candidate"; exit 0; }
  done
  exit 1
')
case "$CONTAINER_PYTHON" in
  /*) ;;
  *) echo "Could not resolve container Python: $CONTAINER_PYTHON"; exit 1 ;;
esac
echo "container python: $CONTAINER_PYTHON"

# Model: the flat GCS staging of the exact HF revision (gcp/stage_dsv41_flash.sh).
MODEL_GCS_PREFIX='gs://cellens-ai-artifacts/arc3-duck/model-flat/DeepSeek-V4.1-Flash-NVFP4'
gcloud storage ls "$MODEL_GCS_PREFIX/.complete" >/dev/null
# gcloud storage rsync (snap 493) can crash in its final report and leave worker
# processes hung, so each pass is time-boxed, its exit status ignored, and the
# shard set is what decides (verify below). Existing files are skipped by size.
verify_model() {
  /opt/arc3/pysrv/bin/python - <<'PYCHECK'
import json, sys
from pathlib import Path
root = Path("/opt/arc3/flashnext-model")
idx = root / "model.safetensors.index.json"
if not idx.is_file(): sys.exit(1)
shards = sorted(set(json.loads(idx.read_text())["weight_map"].values()))
sys.exit(0 if all((root / s).is_file() and (root / s).stat().st_size > 0 for s in shards) else 1)
PYCHECK
}
for pass_no in 1 2 3; do
  echo "model copy pass $pass_no $(date -u +%FT%TZ)"
  ( time timeout -k 30 1500 gcloud storage rsync -r --exclude='^(stage\.log|\.complete)$' "$MODEL_GCS_PREFIX" "$MODEL_DIR" ) > /opt/arc3/model-download-pass$pass_no.log 2>&1 || true
  pkill -f "gcloud.py storage rsync" 2>/dev/null || true
  grep -E "Average throughput|real|crashed|failed" /opt/arc3/model-download-pass$pass_no.log | tail -4 | tee -a /opt/arc3/model-download.log
  if verify_model; then echo "model shards complete after pass $pass_no" | tee -a /opt/arc3/model-download.log; break; fi
  [ "$pass_no" = 3 ] && { echo "model copy incomplete after 3 passes" | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"; exit 1; }
done
/opt/arc3/pysrv/bin/python - <<'PYVERIFY'
import json
from pathlib import Path
root = Path("/opt/arc3/flashnext-model")
index = json.loads((root / "model.safetensors.index.json").read_text())
shards = sorted(set(index["weight_map"].values()))
missing = [s for s in shards if not (root / s).is_file()]
assert not missing, f"missing shards: {missing[:5]} (+{max(0,len(missing)-5)})"
total = sum((root / s).stat().st_size for s in shards)
print(f"shards={len(shards)} bytes={total} ({total/2**30:.1f} GiB)", flush=True)
assert total > 450 * 2**30, "checkpoint smaller than expected"
(root / "download-info.json").write_text(json.dumps({
    "model_id": "nvidia/DeepSeek-V4.1-Flash-NVFP4", "revision": "3431dde3247c13b5957f682b1e3c6fcae2566079",
    "source": "gs://cellens-ai-artifacts/arc3-duck/model-flat/DeepSeek-V4.1-Flash-NVFP4/", "shards": len(shards), "bytes": total,
    "verified": "shard presence and size against model.safetensors.index.json",
}, indent=2))
PYVERIFY
/opt/arc3/pysrv/bin/python - <<'PYINFO'
import json
from pathlib import Path
root = Path("/opt/arc3/flashnext-model")
download = json.loads((root / "download-info.json").read_text())
info = {
    **download,
    "quantization": "modelopt MIXED_PRECISION: FP8 dense, NVFP4 routed experts (group 16); Engram tables CPU-offloaded",
    "tensor_parallel": 8,
    "mtp_enabled": False,
    "requested_server_sequences": 25,
    "context_length": 102985,
}
Path("/opt/arc3/model-info.json").write_text(json.dumps(info, indent=2) + "\n")
PYINFO

INDEXER_PATH=/usr/local/lib/python3.12/dist-packages/vllm/v1/attention/backends/mla/indexer.py
mkdir -p /opt/arc3/indexer-overlay
docker run --rm --entrypoint cat "$CONTAINER_IMAGE" "$INDEXER_PATH" > /opt/arc3/indexer-overlay/indexer.py
sha256sum /opt/arc3/indexer-overlay/indexer.py | tee /opt/arc3/indexer-base-sha.txt
python3 - <<'PYPATCH'
from pathlib import Path
p = Path('/opt/arc3/indexer-overlay/indexer.py'); s = p.read_text()
old = "return [64 if current_platform.is_device_capability_family(90) else 128]"
new = "return [128 if current_platform.is_device_capability_family(100) else 64]  # arc3 sm_120 overlay"
assert s.count(old) == 1, s.count(old)
p.write_text(s.replace(old, new)); print("indexer overlay applied")
PYPATCH
python3 -c "import ast; ast.parse(open('/opt/arc3/indexer-overlay/indexer.py').read())"
gcloud storage cp /opt/arc3/indexer-overlay/indexer.py "$BUCKET/$RUN_ID/indexer-overlay.py" >/dev/null 2>&1 || true

start_server() {
  local kv_dtype="$1" mode="$2"
  local extra=(--enable-expert-parallel) envs=()
  # Run #2 (TP8, no EP) failed: "Intermediate size padding for w1 and w3 ... NvFp4 backend
  # FLASHINFER_CUTLASS not supported". Expert parallelism keeps whole experts per GPU.
  # Attempt 2 keeps EP and swaps the V4.1 sparse-attention kernel family.
  if [ "$mode" = flashmla ]; then
    extra+=(--attention-backend FLASHMLA_SPARSE_DSV41)
  fi
  docker rm -f flashnext >/dev/null 2>&1 || true
  pkill -f "docker logs -f flashnext" >/dev/null 2>&1 || true
  : > /opt/arc3/vllm.log
  # Gloo needs a null-terminated hostname. GCE FQDNs can be exactly 64 bytes,
  # which makes ProcessGroupGloo fail with ENAMETOOLONG before model loading.
  docker run -d --name flashnext --hostname arc3-vllm --gpus all --ipc=host --network=host \
    --ulimit memlock=-1 --cap-add=SYS_PTRACE --shm-size=64g \
    -e TORCH_CUDA_ARCH_LIST=12.0f \
    -e PYTORCH_ALLOC_CONF=expandable_segments:True \
    -e HF_HUB_OFFLINE=1 \
    -e VLLM_NO_USAGE_STATS=1 \
    -e VLLM_SERVER_DEV_MODE=1 \
    "${envs[@]}" \
    -v "$MODEL_DIR:/model:ro" \
    -v /opt/arc3/vllm-cache:/root/.cache \
    -v "/opt/arc3/indexer-overlay/indexer.py:$INDEXER_PATH:ro" \
    "$CONTAINER_IMAGE" \
    --model /model --served-model-name "$SERVED_MODEL_NAME" \
    --host 127.0.0.1 --port 1234 --tensor-parallel-size 8 \
    --distributed-executor-backend mp \
    --engram-config '{"cpu_offload":true}' \
    --gpu-memory-utilization 0.965 \
    --max-model-len 102985 --max-num-seqs 25 --max-num-batched-tokens 16384 \
    --kv-cache-dtype "$kv_dtype" --scheduling-policy fcfs --enable-chunked-prefill \
    --enable-prefix-caching --enable-prompt-tokens-details \
    --enable-auto-tool-choice --tool-call-parser deepseek_v41 \
    --reasoning-parser deepseek_v41 \
    --generation-config vllm \
    "${extra[@]}"
  nohup docker logs -f flashnext > /opt/arc3/vllm.log 2>&1 &
}

wait_server() {
  # 552B over 8 PCIe GPUs from hyperdisk: weight load alone can take 15+ minutes.
  for _ in $(seq 1 240); do
    curl -s -m 3 http://127.0.0.1:1234/v1/models >/dev/null && return 0
    docker inspect -f '{{.State.Running}}' flashnext 2>/dev/null | grep -qx true || return 1
    sleep 10
  done
  return 1
}

container_gpu_ready() {
  docker run --rm --gpus all --entrypoint "$CONTAINER_PYTHON" \
    "$CONTAINER_IMAGE" - <<'PYCUDACHECK'
import torch
assert torch.cuda.is_available(), "CUDA unavailable in serving container"
assert torch.cuda.device_count() == 8, torch.cuda.device_count()
print(torch.cuda.get_device_name(0), torch.cuda.device_count())
PYCUDACHECK
}

if ! container_gpu_ready; then
  sleep 10
  container_gpu_ready
fi
KV_DTYPE_USED=fp8
SERVER_MODE=tp8-ep8-flashinfer
start_server "$KV_DTYPE_USED" flashinfer
if ! wait_server; then
  cp /opt/arc3/vllm.log /opt/arc3/vllm-start-attempt1.log
  timeout 15 gcloud storage cp /opt/arc3/vllm-start-attempt1.log "$BUCKET/$RUN_ID/vllm-start-attempt1.log" || true
  sleep 10
  container_gpu_ready
  SERVER_MODE=tp8-ep8-flashmla
  start_server "$KV_DTYPE_USED" flashmla
fi
if ! wait_server; then
  echo "vLLM failed to serve DeepSeek-V4.1-Flash on 8x RTX PRO 6000 (both flag sets)" | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"
  sync_all
  exit 1
fi
echo "$KV_DTYPE_USED" > /opt/arc3/kv-dtype-used.txt
echo "$SERVER_MODE" | tee /opt/arc3/server-mode.txt | gcloud storage cp - "$BUCKET/$RUN_ID/server-mode"

docker exec -i flashnext "$CONTAINER_PYTHON" - <<'PYVERS' > /opt/arc3/serving-environment.txt
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
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu \
  --format=csv,noheader > /opt/arc3/gpu-after-load.csv
free -h > /opt/arc3/ram-after-load.txt

# Verify ordinary text, vision (the harness sends current_grid images), and 25
# simultaneous long-prefix requests before
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
MODEL = "nvidia/DeepSeek-V4.1-Flash-NVFP4"

def call(messages, max_tokens=64, timeout=900):
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
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
with concurrent.futures.ThreadPoolExecutor(max_workers=25) as pool:
    capacity = list(pool.map(capacity_call, range(25)))
capacity_seconds = time.monotonic() - capacity_started

summary = {
    "model": MODEL,
    "kv_dtype": os.environ["KV_DTYPE_USED"],
    "mtp_enabled": False,
    "max_num_seqs": 25,
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
docker exec -i flashnext "$CONTAINER_PYTHON" - <<'PYVERS' > /opt/arc3/serving-environment.txt
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
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu \
  --format=csv,noheader > /opt/arc3/gpu-after-load.csv
free -h > /opt/arc3/ram-after-load.txt
sync_all

# Native 25x102985 acceptance runs on this GPU and must finish before gameplay.
gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/astra-execution/context-matrix-r1/0dbd08c9aeec9c5681c232fec2f42fd8e5aa6d9bd3b2a97bdb4bfa0ccef3c186/context-matrix-capacity-r1.tgz' /tmp/astra-native-context-capacity.tgz
echo '0dbd08c9aeec9c5681c232fec2f42fd8e5aa6d9bd3b2a97bdb4bfa0ccef3c186  /tmp/astra-native-context-capacity.tgz' | sha256sum -c -
tar xzf /tmp/astra-native-context-capacity.tgz -C /opt/arc3
timeout --kill-after=10 330 /opt/arc3/pysrv/bin/python -B /opt/arc3/context-matrix-capacity-r1/capacity_gate.py \
  --base-url http://127.0.0.1:1234/v1 --model "$SERVED_MODEL_NAME" \
  --context 102985 --concurrency 25 --append-rounds 2 \
  --total-seconds 300 --request-timeout 300 --run-key c102985-w7-matrix-r1 \
  --output /opt/arc3/native-context-capacity-gate.json --ack-idle-pregame-server \
  2>&1 | tee /opt/arc3/native-context-capacity-gate.log
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
export LOCAL_ANALYZER_CONTEXT_WINDOW=102985 LOCAL_ANALYZER_MAX_OUTPUT=0
export LOCAL_ANALYZER_TOOL_STEPS=0 LOCAL_ANALYZER_TOOL_TIMEOUT=30 LOCAL_ANALYZER_TOOL_OUTPUT_TOKENS=1024
export LOCAL_ANALYZER_YIELD_SECONDS=60 LOCAL_ANALYZER_TEMPERATURE=1.0 LOCAL_ANALYZER_TOP_P=0.95 LOCAL_ANALYZER_TOP_K=20
export ARC3_ANIMATION_CHECKPOINT_ENABLED=1 ARC3_ANIMATION_CHECKPOINT_MIN_CHANGED=2 ARC3_ANIMATION_EXPOSED_KEYFRAMES=12 ARC3_ANIMATION_BASELINE_MIN_SAMPLES=5 ARC3_ANIMATION_FAMILY_MIN_SAMPLES=5 ARC3_ANIMATION_HUD_BORDER=0 ARC3_ANIMATION_MIN_SPATIAL_FRAMES=4 ARC3_ANIMATION_MIN_SPATIAL_UNIQUE_CELLS=8 ARC3_ANIMATION_MIN_SPATIAL_CHANGE_SUM=32 ARC3_ANIMATION_STORYBOARD_MAX_TOKENS=2000 ARC3_ANIMATION_CHECKPOINT_MAX_PER_LEVEL=3 ARC3_ANIMATION_CHECKPOINT_COOLDOWN_ACTIONS=5
export LOCAL_ANALYZER_ENABLE_THINKING=true MULTIMODAL_CONTEXT=current_grid MULTIMODAL_UPSCALE=4
export ARC3_PROMPT_ABLATE_VIEW=0
export ARC3_PROMPT_ABLATE_LOOP=1
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
export LOCAL_ANALYZER_CONTEXT_WINDOW=102985
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
export ARC3_BENCHMARK_CONCURRENCY=25
export ARC3_MAX_RUNTIME_S_PER_GAME=18000
export ARC3_MAX_RUN_RUNTIME_MINUTES=330
export ARC3_REEXPLORE_STRICT="" ARC3_GAME_SUBSET="" ARC3_STATE_GRAPH="" ARC3_FRAME_MODE=full

export ARC3_HISTORY_MODE=full_context
# Exact arm CPU regressions and one bounded model-authored probe; no game actions.
echo '9819c16bb12a0480647f2aab593596d20140d813a43600ea187a3230b4d00b83  /opt/arc3/execution-selftest/linux_selftest_matrix.py' | sha256sum -c -
PYTHONPATH=/opt/arc3/execution-selftest/candidate/src/ARC3-Inference \
  ./.venv/bin/python -B /opt/arc3/execution-selftest/linux_selftest_matrix.py \
  --live --arm baseline --model "$SERVED_MODEL_NAME" --context 102985 \
  --output /opt/arc3/execution-selftest.json \
  2>&1 | tee /opt/arc3/execution-selftest.log

gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/astra-execution/feature-ablation-132-v1/11db93bca6d982d4c129680df7d241a715df5a8eca5f4a2cbef950e73014570d/full_context_live_matrix.py' /opt/arc3/full_context_live_matrix.py
echo '11db93bca6d982d4c129680df7d241a715df5a8eca5f4a2cbef950e73014570d  /opt/arc3/full_context_live_matrix.py' | sha256sum -c -
timeout --kill-after=10 600 ./.venv/bin/python -B /opt/arc3/full_context_live_matrix.py \
  --packet /opt/arc3/execution-selftest --output /opt/arc3/full-context-selftest.json \
  --live --context 102985 --base-url http://127.0.0.1:1234/v1 --model "$SERVED_MODEL_NAME" \
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
assert os.environ["ARC3_PROMPT_ABLATE_LOOP"] == "1"
assert os.environ['ARC3_PERSISTENT_GAME_MODEL'] == '0'
assert os.environ['ARC3_EXECUTION_MODE'] == '0'
assert os.environ['ARC3_SYMBOLIC_SEARCH'] == '0'
assert os.environ['ARC3_PROGRAMMATIC_WORKSPACE'] == '0'
assert os.environ['ARC3_EXECUTION_CONFIRMATIONS'] == '2'
assert os.environ['ARC3_EXECUTION_LEASE_ACTIONS'] == '3'
assert os.environ['ARC3_HISTORY_MODE'] == 'full_context'
assert os.environ['LOCAL_ANALYZER_CONTEXT_WINDOW'] == '102985'
assert os.environ['ARC3_BENCHMARK_CONCURRENCY'] == '25'
assert os.environ['ARC3_MAX_RUNTIME_S_PER_GAME'] == '18000'
assert os.environ['ARC3_MAX_RUN_RUNTIME_MINUTES'] == '330'
assert os.environ["ARC3_POST_LEVEL_UNCAPPED_TURNS"] == "0"
assert tool_agent._PERSISTENT_HISTORY_ASSISTANT_TURNS == 30
agent = tool_agent.ToolAgent()
assert (agent._execution_mode is not None) == False
assert agent._full_context_tokens is not None
assert agent._context_budget_tokens == 94281
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
print("verified feature arm baseline; no curator; 330-minute suite, 25 lanes")
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
    http://127.0.0.1:1234/metrics \
    | grep -E '^vllm:(prefix_cache_|external_prefix_cache_|num_preemptions_|kv_cache_usage_|num_requests_)' \
    > "/opt/arc3/gameplay-metrics-${phase}.txt" || true
}

# Runtime capacity evidence must exist even if a caller bypasses the insertion placeholder.
/opt/arc3/pysrv/bin/python - <<'PYCAPACITYFINAL'
import json
from pathlib import Path
report = json.loads(Path('/opt/arc3/native-context-capacity-gate.json').read_text())
assert report['status'] == 'passed', report.get('status')
assert report['configuration']['context'] == 102985
assert report['configuration']['concurrency'] == 25
assert report['gates']['native_capacity_and_reuse_pass'] is True
assert report['gates']['zero_preemptions_verified'] is True
assert report['gates']['server_concurrency_observed'] is True
assert report['script_sha256'] == '13fe2cd4a9cf545cfffaa6e3932250433389b541221b745327c87b7e1b33da39'
renderer = json.loads(Path('/opt/arc3/full-context-selftest.json').read_text())
assert renderer['status'] == 'passed'
assert renderer['context'] == 102985
assert renderer['input_budget'] == 94281
assert renderer['near_budget_multimodal_renderer_pass'] is True
assert renderer['production_mode_renderer_count_matches'] is True
PYCAPACITYFINAL
# New swap tests run with inherited fixture flags OFF, then production ON.
ARC3_HALF_CONTEXT_SWAP=0 ./.venv/bin/python -B /opt/arc3/execution-selftest/test_half_swap.py > /opt/arc3/half-swap-tests.log 2>&1
ARC3_HALF_CONTEXT_SWAP=0 ./.venv/bin/python -B /opt/arc3/execution-selftest/test_half_swap_integration.py >> /opt/arc3/half-swap-tests.log 2>&1
export ARC3_ROLLING_HALF_CHECKPOINT=0
export ARC3_HALF_CONTEXT_SWAP=1
timeout --kill-after=10 300 ./.venv/bin/python -B /opt/arc3/execution-selftest/live_half_swap_gate.py 2>&1 | tee /opt/arc3/half-swap-live-gate.log
# Clear synthetic fixtures only after all live gates and warmup have settled.
timeout --kill-after=5 30 /opt/arc3/pysrv/bin/python -B /opt/arc3/context-matrix-capacity-r1/reset_idle_cache.py \
  --base-url http://127.0.0.1:1234/v1 --output /opt/arc3/native-context-prefix-reset.json \
  --ack-idle-pregame-server 2>&1 | tee /opt/arc3/native-context-prefix-reset.log
gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/astra-execution/full128/ad50b27a77af132f134fa1849d93a6c4adf1359c466acadd4c5fd7086d3040a1/vllm_metrics_sampler.py' /opt/arc3/vllm_metrics_sampler.py
echo 'ad50b27a77af132f134fa1849d93a6c4adf1359c466acadd4c5fd7086d3040a1  /opt/arc3/vllm_metrics_sampler.py' | sha256sum -c -
/opt/arc3/pysrv/bin/python -B /opt/arc3/vllm_metrics_sampler.py sample \
  --url http://127.0.0.1:1234/metrics --output /opt/arc3/work/vllm-metrics.jsonl \
  --interval-seconds 30 --max-seconds 28800 > /opt/arc3/work/vllm-metrics-sampler.log 2>&1 &
METRICS_SAMPLER_PID=$!
/opt/arc3/pysrv/bin/python - <<'PYMETRICSREADY'
import json, time
from pathlib import Path
path = Path('/opt/arc3/work/vllm-metrics.jsonl')
for attempt in range(20):
    if path.exists() and path.stat().st_size:
        line = path.read_text().splitlines()[0]
        row = json.loads(line)
        assert row['ok'] is True, row.get('error_type')
        assert any(x['name'] == 'vllm:num_requests_running' for x in row['metrics'])
        break
    time.sleep(.5)
else:
    raise RuntimeError('Gameplay telemetry did not become ready')
PYMETRICSREADY
kill -0 "$METRICS_SAMPLER_PID"
# Keep enough of the fixed four-hour VM lifetime for the full suite and teardown.
test "$(cut -d. -f1 /proc/uptime)" -lt 12000
mkdir -p /opt/arc3/config-audit
gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/cap-compact132/3d0b0464d91ec3e2b5b8b0eb28cdce3bd601777db686eab8d35284c7cb44c696/CONFIG_FLAGS.json' /opt/arc3/config-audit/CONFIG_FLAGS.json
echo '3d0b0464d91ec3e2b5b8b0eb28cdce3bd601777db686eab8d35284c7cb44c696  /opt/arc3/config-audit/CONFIG_FLAGS.json' | sha256sum -c -
gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/cap-compact132/604b256d70d72c1ec55f786da3ef13207b1d045db10e55a83d5f98fc0274f7b7/ADAPTER.json' /opt/arc3/config-audit/ADAPTER.json
echo '604b256d70d72c1ec55f786da3ef13207b1d045db10e55a83d5f98fc0274f7b7  /opt/arc3/config-audit/ADAPTER.json' | sha256sum -c -
gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/cap-compact132/64d537c9b113fa23f8092aecc167e6dce443349825d64fc6c1c6a328a369fad3/contract.py' /opt/arc3/config-audit/contract.py
echo '64d537c9b113fa23f8092aecc167e6dce443349825d64fc6c1c6a328a369fad3  /opt/arc3/config-audit/contract.py' | sha256sum -c -
gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/cap-compact132/85df8159dacd2a7bd94196f880b3e8b2ed2b7e9c07c43eacad63b71992b7d359/runtime_probe.py' /opt/arc3/config-audit/runtime_probe.py
echo '85df8159dacd2a7bd94196f880b3e8b2ed2b7e9c07c43eacad63b71992b7d359  /opt/arc3/config-audit/runtime_probe.py' | sha256sum -c -
gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/cap-compact132/9bfa3fd1430725629b684665c0c9b381780810e005220e459da281845ab74528/prompt_probe.py' /opt/arc3/config-audit/prompt_probe.py
echo '9bfa3fd1430725629b684665c0c9b381780810e005220e459da281845ab74528  /opt/arc3/config-audit/prompt_probe.py' | sha256sum -c -
gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/cap-compact132/2f6227eee2569a4e0e383818d8cf0ab7f8b3c60a1464371658f64dd607b4545a/EXPECTED_PROMPTS.json' /opt/arc3/config-audit/EXPECTED_PROMPTS.json
echo '2f6227eee2569a4e0e383818d8cf0ab7f8b3c60a1464371658f64dd607b4545a  /opt/arc3/config-audit/EXPECTED_PROMPTS.json' | sha256sum -c -
ARC3_HALF_CONTEXT_SWAP=0 ./.venv/bin/python -B /opt/arc3/execution-selftest/test_action_cap_modes.py > /opt/arc3/action-cap-selftest.log 2>&1
./.venv/bin/python -B /opt/arc3/execution-selftest/test_compaction_mode.py > /opt/arc3/feature-selftest.log 2>&1
gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/cap-compact132/3796093bc39f0a0ec5436ae312a150d87c6262ea06a8bdaf5d25e5a7ed7c69b4/time_guidance_probe.py' /opt/arc3/config-audit/time_guidance_probe.py
echo '3796093bc39f0a0ec5436ae312a150d87c6262ea06a8bdaf5d25e5a7ed7c69b4  /opt/arc3/config-audit/time_guidance_probe.py' | sha256sum -c -
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

