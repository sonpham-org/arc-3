#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFERENCE_DIR="${ROOT_DIR}/ARC3-Inference"
A108_CONFIG="${A108_CONFIG:-configs/a108.qwen36.json}"
A108_HOST="${A108_HOST:-gx10-a108.tail57a229.ts.net}"
A108_SSH_OPTS="${A108_SSH_OPTS:--o BatchMode=yes -o ConnectTimeout=10}"
WARNINGS=0

section() {
  printf '\n== %s ==\n' "$1"
}

warn() {
  WARNINGS=$((WARNINGS + 1))
  printf 'WARN: %s\n' "$*"
}

require_file() {
  local path="$1"
  if [[ -f "${path}" ]]; then
    printf 'ok: %s\n' "${path#${ROOT_DIR}/}"
  else
    printf 'ERROR: missing %s\n' "${path#${ROOT_DIR}/}"
    exit 1
  fi
}

section "Workspace"
printf 'root: %s\n' "${ROOT_DIR}"
require_file "${ROOT_DIR}/Makefile"
require_file "${INFERENCE_DIR}/Makefile"
require_file "${INFERENCE_DIR}/pyproject.toml"
require_file "${ROOT_DIR}/tufa-arc-agi-framework/pyproject.toml"
require_file "${ROOT_DIR}/scripts/check_a108_env.sh"
require_file "${ROOT_DIR}/scripts/a108_bootstrap_report.sh"
require_file "${INFERENCE_DIR}/scripts/smoke_tool_call.py"
require_file "${INFERENCE_DIR}/scripts/download_model.py"

section "Config"
config_path="${INFERENCE_DIR}/${A108_CONFIG}"
require_file "${config_path}"
python3 -m json.tool "${config_path}" >/dev/null
printf 'json: ok\n'
printf 'model: '
python3 "${INFERENCE_DIR}/inference/tools/config_value.py" "${config_path}" shared.model_name
printf 'provider: '
python3 "${INFERENCE_DIR}/inference/tools/config_value.py" "${config_path}" shared.provider
printf 'base_url: '
python3 "${INFERENCE_DIR}/inference/tools/config_value.py" "${config_path}" shared.base_url
printf 'install_target: '
python3 "${INFERENCE_DIR}/inference/tools/config_value.py" "${config_path}" server.install_target
printf 'tool_call_parser: '
python3 "${INFERENCE_DIR}/inference/tools/config_value.py" "${config_path}" server.tool_call_parser
printf 'reasoning_parser: '
python3 "${INFERENCE_DIR}/inference/tools/config_value.py" "${config_path}" server.reasoning_parser

section "Python Syntax"
python3 -m py_compile "${INFERENCE_DIR}/scripts/smoke_tool_call.py"
python3 -m py_compile "${INFERENCE_DIR}/scripts/download_model.py"
printf 'smoke_tool_call.py: ok\n'
printf 'download_model.py: ok\n'
bash -n "${ROOT_DIR}/scripts/check_a108_env.sh"
bash -n "${ROOT_DIR}/scripts/a108_bootstrap_report.sh"
printf 'shell scripts: ok\n'

section "Make Dry Runs"
make -C "${INFERENCE_DIR}" -n CONFIG_PATH="${A108_CONFIG}" server >/tmp/a108_make_server.txt
make -C "${INFERENCE_DIR}" -n CONFIG_PATH="${A108_CONFIG}" download-model >/tmp/a108_make_download_model.txt
make -C "${INFERENCE_DIR}" -n CONFIG_PATH="${A108_CONFIG}" smoke-tool >/tmp/a108_make_smoke_tool.txt
make -C "${ROOT_DIR}" -n A108_CONFIG="${A108_CONFIG}" a108-sync a108-install a108-download-model a108-server a108-smoke-tool a108-smoke-game >/tmp/a108_make_root.txt
printf 'server target: ok\n'
printf 'download-model target: ok\n'
printf 'smoke-tool target: ok\n'
printf 'root a108 targets: ok\n'

section "Local Tools"
if command -v ssh >/dev/null 2>&1; then
  # shellcheck disable=SC2086
  ssh ${A108_SSH_OPTS} -G "${A108_HOST}" >/tmp/a108_ssh_config.txt 2>/tmp/a108_ssh_config.err || warn "ssh -G ${A108_HOST} failed; inspect SSH config or use A108_HOST=user@host"
  if [[ -s /tmp/a108_ssh_config.txt ]]; then
    awk '/^(hostname|user|port) / {print}' /tmp/a108_ssh_config.txt
  fi
else
  warn "ssh not found"
fi
if command -v rsync >/dev/null 2>&1; then
  rsync --version | sed -n '1p'
else
  warn "rsync not found"
fi
if command -v uv >/dev/null 2>&1; then
  uv --version
else
  warn "uv not found locally; this is only required on a108 for install-a108"
fi

section "Done"
printf 'workspace check completed with %d warning(s)\n' "${WARNINGS}"
