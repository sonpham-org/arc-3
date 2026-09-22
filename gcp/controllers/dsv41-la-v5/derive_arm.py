"""Derive the DeepSeek-V4.1-Flash arm from the live LA arm (la_v5_clean_return_a).

Everything harness-side is byte-identical: candidate.tgz, runner, selftests, probes, prompts,
env, lanes (7), cap, compaction, clock. Only the model/server block of startup.sh changes,
plus CONFIG_FLAGS.json's pinned model (and therefore its config_id) so the runtime contract
attests the model actually served.
"""
import hashlib, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = Path(r"D:\codex-work\la-v5-clean-return132-20260921\arms\la_v5_clean_return_a")
ARM = HERE / "arms" / "dsv41_la_v5_clean_return_a"
sys.path.insert(0, str(SRC))
import contract  # noqa: E402  (the arm's own contract.py, byte-identical)

MODEL_ID = "nvidia/DeepSeek-V4.1-Flash-NVFP4"
MODEL_REVISION = "3431dde3247c13b5957f682b1e3c6fcae2566079"   # HF main at 21-Sep-2026 22:00 UTC
MODEL_FLAT = "gs://cellens-ai-artifacts/arc3-duck/model-flat/DeepSeek-V4.1-Flash-NVFP4"
VLLM_IMAGE = "vllm/vllm-openai:nightly"   # recipe: nightly >= 2026-09-10. The model-card tag deepseekv41-flash-0909 lacks the sm_120 sparse-MLA backend (runs #2/#3)

# ---------------------------------------------------------------- CONFIG_FLAGS.json
cfg = json.loads((SRC / "CONFIG_FLAGS.json").read_text(encoding="utf-8-sig"))
cfg["recipe"]["model"] = {
    "id": MODEL_ID,
    "revision": MODEL_REVISION,
    "weights": "FP8 dense + NVFP4 routed experts (modelopt); Engram tables CPU-offloaded",
    "kv_dtype": "fp8_e4m3",
    "ple_dtype": "none",
    "gpu_memory_utilization": 0.965,
}
cfg["run_id"] = "g4run-dsv41flash-la-v5-clean-return-a132-w8x-20260921"
cfg["evidence"]["notes"] = [
    "September21 user: 'maybe try to run it with 8 RTX then. I just want to see how good a strong model is.' "
    "Ceiling measurement: the exact la_v5_clean_return_a candidate (compaction v5 + 14-action clean-return + "
    "Loop A deletion, time-only guidance, 7 lanes, 102985 context, 132 gameplay minutes) with the model swapped "
    "to DeepSeek-V4.1-Flash-NVFP4 (552B MoE, 8B/16B active) served by vLLM TP8 on one g4-standard-384 "
    "(8x RTX PRO 6000 Blackwell). Bundle, runner, selftests, probes, prompts and every ARC3_* value are "
    "byte-identical to the LA arm; only the model, its server block and this model pin differ. "
    "Sampling stays 1.0/0.95/20 as in the LA arm. Thinking on at the model's default effort (50). "
    "Control: the la_v5_clean_return_{a,b} pair. One scored attempt across 25 games; no replacement. Spot only. "
    "No Kaggle action or publication.",
    "Prompt snapshots byte-identical to the LA arm (EXPECTED_PROMPTS.json unchanged).",
] + cfg["evidence"]["notes"][1:]
cfg["config_id"] = contract.config_id(cfg["recipe"])
contract.validate(cfg, for_launch=True)
cfg_bytes = (json.dumps(cfg, indent=2, sort_keys=False) + "\n").encode()
cfg_sha = hashlib.sha256(cfg_bytes).hexdigest()
(ARM / "CONFIG_FLAGS.json").write_bytes(cfg_bytes)
old_cfg_sha = hashlib.sha256((SRC / "CONFIG_FLAGS.json").read_bytes()).hexdigest()
print("config_id", cfg["config_id"])
print("CONFIG_FLAGS sha", cfg_sha, "(was", old_cfg_sha + ")")

# ---------------------------------------------------------------- startup.sh
s = (SRC / "startup.sh").read_text(encoding="utf-8")

def sub1(pattern, repl, text, flags=0):
    new, n = re.subn(pattern, repl, text, count=1, flags=flags)
    assert n == 1, pattern
    return new

s = sub1(r"^# Search/scorer removal \+ 50% swap, W7, 132 minutes, time-only guidance; arm=la_v5_clean_return_a\.\n# Derived from captured baseline; not the exact champion\.",
         "# DeepSeek-V4.1-Flash ceiling run: the la_v5_clean_return_a candidate byte-for-byte, model swapped.\n"
         "# arm=dsv41_la_v5_clean_return_a. Server: vLLM TP8 on 8x RTX PRO 6000 (g4-standard-384),\n"
         "# Engram tables CPU-offloaded, FP8 KV. Harness, lanes (7), clock, cap, compaction unchanged.",
         s, re.M)
s = sub1(r'MODEL_ID="RadixArk/Qwen3\.8-Flash-Next-NVFP4"\nMODEL_REVISION="7b719225242aacd3dbd3f9407468c2ee9a9d2594"',
         f'MODEL_ID="{MODEL_ID}"\nMODEL_REVISION="{MODEL_REVISION}"', s)

# Replace the whole Flash-Next model/server block with the DeepSeek one.
start_marker = "# Flash-Next uses the experimental PLE CPU-offload path packaged in this pinned"
end_marker = "docker exec -i flashnext \"$CONTAINER_PYTHON\" - <<'PYVERS' > /opt/arc3/serving-environment.txt"
a = s.index(start_marker); b = s.index(end_marker)
new_block = r'''# DeepSeek-V4.1-Flash-NVFP4 via the vLLM image named on the NVIDIA model card, TP8.
# Engram tables (~183 GiB) are CPU-offloaded per the vLLM recipe; the g4-standard-384
# has 1440 GB host RAM. No PLE/qsa/scheduler overlays: those were Flash-Next patches.
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker.io
if ! command -v nvidia-ctk >/dev/null 2>&1; then
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nvidia-container-toolkit
fi
nvidia-ctk runtime configure --runtime=docker
systemctl enable --now docker

MODEL_DIR=/opt/arc3/flashnext-model
CONTAINER_IMAGE='__VLLM_IMAGE__'
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
MODEL_GCS_PREFIX='__MODEL_FLAT__'
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
    "model_id": "__MODEL_ID__", "revision": "__MODEL_REVISION__",
    "source": "__MODEL_FLAT__/", "shards": len(shards), "bytes": total,
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
    "requested_server_sequences": 7,
    "context_length": 102985,
}
Path("/opt/arc3/model-info.json").write_text(json.dumps(info, indent=2) + "\n")
PYINFO

start_server() {
  local kv_dtype="$1" blackwell="$2"
  local extra=() envs=()
  if [ "$blackwell" = 1 ]; then
    # vLLM recipe's Blackwell (B200/B300) sparse-MLA path; sm_120 support is unverified,
    # so attempt 2 runs without these if the server does not come up.
    extra=(--indexer-kv-dtype mxfp4 --indexer-sparse-logits true)
    envs=(-e FLASHINFER_MLA_SPARSE_DSV41=1)
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
    "$CONTAINER_IMAGE" \
    --model /model --served-model-name "$SERVED_MODEL_NAME" \
    --host 127.0.0.1 --port 1234 --tensor-parallel-size 8 \
    --distributed-executor-backend mp \
    --engram-config '{"cpu_offload":true}' \
    --gpu-memory-utilization 0.965 \
    --max-model-len 102985 --max-num-seqs 7 --max-num-batched-tokens 16384 \
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
KV_DTYPE_USED=fp8_e4m3
SERVER_MODE=blackwell-flags
start_server "$KV_DTYPE_USED" 1
if ! wait_server; then
  cp /opt/arc3/vllm.log /opt/arc3/vllm-start-attempt1.log
  timeout 15 gcloud storage cp /opt/arc3/vllm-start-attempt1.log "$BUCKET/$RUN_ID/vllm-start-attempt1.log" || true
  sleep 10
  container_gpu_ready
  SERVER_MODE=plain
  start_server "$KV_DTYPE_USED" 0
fi
if ! wait_server; then
  echo "vLLM failed to serve DeepSeek-V4.1-Flash on 8x RTX PRO 6000 (both flag sets)" | gcloud storage cp - "$BUCKET/$RUN_ID/FAILED"
  sync_all
  exit 1
fi
echo "$KV_DTYPE_USED" > /opt/arc3/kv-dtype-used.txt
echo "$SERVER_MODE" | tee /opt/arc3/server-mode.txt | gcloud storage cp - "$BUCKET/$RUN_ID/server-mode"

'''
new_block = (new_block.replace("__VLLM_IMAGE__", VLLM_IMAGE).replace("__MODEL_FLAT__", MODEL_FLAT)
             .replace("__MODEL_ID__", MODEL_ID).replace("__MODEL_REVISION__", MODEL_REVISION))
s = s[:a] + new_block + s[b:]

# Smoke test: model name and chat_template_kwargs (DeepSeek's renderer takes enable_thinking; no preserve_thinking).
s = sub1(r'MODEL = "RadixArk/Qwen3\.8-Flash-Next-NVFP4"', f'MODEL = "{MODEL_ID}"', s)
s = sub1(r'"chat_template_kwargs": \{"enable_thinking": False, "preserve_thinking": True\},',
         '"chat_template_kwargs": {"enable_thinking": False},', s)
# Reflect the serving change in the log preamble
s = sub1(r'# Verify ordinary text, vision, and 7 simultaneous long-prefix requests before',
         '# Verify ordinary text, vision (the harness sends current_grid images), and 7\n# simultaneous long-prefix requests before', s)

# CONFIG_FLAGS.json: point at the re-registered receipt.
s = sub1(r"gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/cap-compact132/" + old_cfg_sha + r"/CONFIG_FLAGS\.json' /opt/arc3/config-audit/CONFIG_FLAGS\.json\n"
         r"echo '" + old_cfg_sha + r"  /opt/arc3/config-audit/CONFIG_FLAGS\.json' \| sha256sum -c -",
         f"gcloud storage cp 'gs://cellens-ai-artifacts/arc3-duck/code/cap-compact132/{cfg_sha}/CONFIG_FLAGS.json' /opt/arc3/config-audit/CONFIG_FLAGS.json\n"
         f"echo '{cfg_sha}  /opt/arc3/config-audit/CONFIG_FLAGS.json' | sha256sum -c -", s)

# Sanity: nothing Flash-Next-specific survives in the server path.
for bad in ("VLLM_PLE_CPU_OFFLOAD", "ple_layer_native_fp8", "qsa.py", "scheduler-overlay", "retention-overlay",
            "golden runtime image", "arc3-model-mirror", "qwen3_xml", "--reasoning-parser qwen3", "preserve_thinking"):
    assert bad not in s, bad
(ARM / "startup.sh").write_text(s, encoding="utf-8", newline="\n")
print("startup.sh", len(s.splitlines()), "lines; sha", hashlib.sha256(s.encode()).hexdigest())
print("uploads needed:", f"code/cap-compact132/{cfg_sha}/CONFIG_FLAGS.json")
