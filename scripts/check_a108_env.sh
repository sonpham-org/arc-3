#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFERENCE_DIR="${ROOT_DIR}/ARC3-Inference"
VENV_PYTHON="${INFERENCE_DIR}/.venv/bin/python"
A108_CONFIG="${A108_CONFIG:-${INFERENCE_DIR}/configs/a108.qwen36.json}"
SERVER_API_KEY_FILE="${SERVER_API_KEY_FILE:-${INFERENCE_DIR}/.cache/arc3_runtime/server-api-key}"
SERVER_HEALTH_URL="${SERVER_HEALTH_URL:-http://127.0.0.1:1234/v1/models}"

WARNINGS=0

section() {
  printf '\n== %s ==\n' "$1"
}

warn() {
  WARNINGS=$((WARNINGS + 1))
  printf 'WARN: %s\n' "$*"
}

section "Host"
hostname
uname -a
ARCH="$(uname -m)"
printf 'arch: %s\n' "${ARCH}"
case "${ARCH}" in
  aarch64|arm64)
    printf 'arch_check: looks compatible with DGX Spark Arm CPU\n'
    ;;
  *)
    warn "expected DGX Spark Arm architecture aarch64/arm64, got ${ARCH}"
    ;;
esac

section "NVIDIA"
if command -v nvidia-smi >/dev/null 2>&1; then
  GPU_QUERY="$(nvidia-smi --query-gpu=name,driver_version,memory.total,memory.free --format=csv,noheader,nounits 2>/dev/null || true)"
  if [[ -n "${GPU_QUERY}" ]]; then
    printf '%s\n' "${GPU_QUERY}"
    GPU_NAME="$(printf '%s\n' "${GPU_QUERY}" | head -n 1 | cut -d, -f1 | xargs || true)"
    case "${GPU_NAME}" in
      *GB10*|*Blackwell*|*DGX*)
        printf 'gpu_check: looks like Spark/Blackwell-class GPU: %s\n' "${GPU_NAME}"
        ;;
      *)
        warn "expected GB10/DGX/Blackwell GPU name, got ${GPU_NAME:-unknown}"
        ;;
    esac
  else
    warn "nvidia-smi query returned no GPU rows"
  fi
  nvidia-smi || true
else
  warn "nvidia-smi not found"
fi

section "Python And uv"
if command -v python3 >/dev/null 2>&1; then
  python3 --version
else
  warn "python3 not found"
fi
UV_BIN="$(command -v uv 2>/dev/null || true)"
if [[ -z "${UV_BIN}" && -x "${HOME}/.local/bin/uv" ]]; then
  UV_BIN="${HOME}/.local/bin/uv"
fi
if [[ -n "${UV_BIN}" ]]; then
  "${UV_BIN}" --version
  if "${UV_BIN}" pip install --help 2>/dev/null | grep -q -- '--torch-backend'; then
    printf 'uv_check: --torch-backend is supported\n'
  else
    warn "uv pip install does not advertise --torch-backend; install-a108 may need adjustment"
  fi
else
  warn "uv not found; install-a108 will try python3 -m pip install --user -U uv"
fi

section "Network"
if command -v curl >/dev/null 2>&1; then
  if curl -I -L --max-time 10 -sS https://huggingface.co >/tmp/a108_hf_headers.txt 2>/tmp/a108_hf.err; then
    printf 'huggingface.co: reachable\n'
    sed -n '1p' /tmp/a108_hf_headers.txt
  else
    warn "could not reach https://huggingface.co with curl"
    if [[ -s /tmp/a108_hf.err ]]; then
      sed -n '1,3p' /tmp/a108_hf.err
    fi
  fi
else
  python3 - <<'PY' || true
from urllib.request import Request, urlopen
try:
    with urlopen(Request("https://huggingface.co", method="HEAD"), timeout=10) as response:
        print(f"huggingface.co: reachable status={response.status}")
except Exception as exc:
    print(f"WARN: could not reach https://huggingface.co: {type(exc).__name__}: {exc}")
PY
fi

section "Workspace"
printf 'root: %s\n' "${ROOT_DIR}"
if [[ -d "${INFERENCE_DIR}" ]]; then
  printf 'ARC3-Inference: present\n'
else
  warn "ARC3-Inference directory missing"
fi
if [[ -f "${A108_CONFIG}" ]]; then
  printf 'a108 config: %s\n' "${A108_CONFIG}"
else
  warn "a108 config missing at ${A108_CONFIG}"
fi

section "Project venv"
if [[ -x "${VENV_PYTHON}" ]]; then
  "${VENV_PYTHON}" --version
  "${VENV_PYTHON}" - <<'PY'
import importlib.util
for name in ["arcengine", "taaf", "vllm", "torch", "requests"]:
    spec = importlib.util.find_spec(name)
    print(f"{name}: {'ok' if spec else 'missing'}")
PY
  if [[ -x "${INFERENCE_DIR}/.venv/bin/vllm" ]]; then
    "${INFERENCE_DIR}/.venv/bin/vllm" --version || true
  else
    warn "vLLM CLI missing from project venv"
  fi
else
  warn "project venv not found at ${VENV_PYTHON}"
fi

section "Torch CUDA"
if [[ -x "${VENV_PYTHON}" ]]; then
  "${VENV_PYTHON}" - <<'PY'
try:
    import torch
except Exception as exc:
    print(f"torch import failed: {type(exc).__name__}: {exc}")
else:
    print(f"torch: {torch.__version__}")
    print(f"cuda_available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"cuda_device_count: {torch.cuda.device_count()}")
        for idx in range(torch.cuda.device_count()):
            print(f"device_{idx}: {torch.cuda.get_device_name(idx)}")
PY
else
  printf 'SKIP: no project venv yet\n'
fi

section "Config resolution"
if [[ -f "${INFERENCE_DIR}/inference/tools/config_value.py" ]]; then
  printf 'model: '
  python3 "${INFERENCE_DIR}/inference/tools/config_value.py" "${A108_CONFIG}" shared.model_name
  printf 'provider: '
  python3 "${INFERENCE_DIR}/inference/tools/config_value.py" "${A108_CONFIG}" shared.provider
  printf 'base_url: '
  python3 "${INFERENCE_DIR}/inference/tools/config_value.py" "${A108_CONFIG}" shared.base_url
  printf 'install_target: '
  python3 "${INFERENCE_DIR}/inference/tools/config_value.py" "${A108_CONFIG}" server.install_target
  printf 'concurrent_jobs: '
  python3 "${INFERENCE_DIR}/inference/tools/config_value.py" "${A108_CONFIG}" environment.concurrent_jobs
  printf 'context_window: '
  python3 "${INFERENCE_DIR}/inference/tools/config_value.py" "${A108_CONFIG}" shared.context_window
  printf 'server_max_model_len: '
  python3 "${INFERENCE_DIR}/inference/tools/config_value.py" "${A108_CONFIG}" server.max_model_len
  printf 'server_gpu_memory_utilization: '
  python3 "${INFERENCE_DIR}/inference/tools/config_value.py" "${A108_CONFIG}" server.gpu_memory_utilization
  printf 'tool_call_parser: '
  python3 "${INFERENCE_DIR}/inference/tools/config_value.py" "${A108_CONFIG}" server.tool_call_parser
  printf 'reasoning_parser: '
  python3 "${INFERENCE_DIR}/inference/tools/config_value.py" "${A108_CONFIG}" server.reasoning_parser
else
  warn "config_value.py missing"
fi

section "vLLM Serve Capabilities"
if [[ -x "${INFERENCE_DIR}/.venv/bin/vllm" ]]; then
  if "${INFERENCE_DIR}/.venv/bin/vllm" serve --help=all >/tmp/a108_vllm_serve_help.txt 2>/tmp/a108_vllm_serve_help.err; then
    for needle in "--enable-auto-tool-choice" "--tool-call-parser" "--reasoning-parser" "--default-chat-template-kwargs" "--enable-prefix-caching"; do
      if grep -q -- "${needle}" /tmp/a108_vllm_serve_help.txt; then
        printf 'vllm_flag: %s ok\n' "${needle}"
      else
        warn "vLLM serve help does not list ${needle}"
      fi
    done
    if grep -q -- "qwen3_coder" /tmp/a108_vllm_serve_help.txt; then
      printf 'vllm_parser: qwen3_coder listed\n'
    else
      warn "vLLM serve help does not list qwen3_coder; tool parsing may still work if parser names are not enumerated"
    fi
  else
    warn "could not run vllm serve --help"
    if [[ -s /tmp/a108_vllm_serve_help.err ]]; then
      sed -n '1,5p' /tmp/a108_vllm_serve_help.err
    fi
  fi
else
  printf 'SKIP: vLLM CLI missing until install-a108 completes\n'
fi

section "Server health"
if [[ -f "${INFERENCE_DIR}/scripts/server_curl.sh" ]]; then
  if "${INFERENCE_DIR}/scripts/server_curl.sh" "${SERVER_API_KEY_FILE}" -fsS "${SERVER_HEALTH_URL}" >/tmp/a108_server_models.json 2>/tmp/a108_server_health.err; then
    printf 'server_health: reachable at %s\n' "${SERVER_HEALTH_URL}"
    head -c 1000 /tmp/a108_server_models.json
    printf '\n'
  else
    printf 'server_health: not reachable at %s\n' "${SERVER_HEALTH_URL}"
    if [[ -s /tmp/a108_server_health.err ]]; then
      sed -n '1,5p' /tmp/a108_server_health.err
    fi
  fi
else
  warn "server_curl.sh missing"
fi

section "Done"
printf 'a108 environment check completed with %d warning(s)\n' "${WARNINGS}"
