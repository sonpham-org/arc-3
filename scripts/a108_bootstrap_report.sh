#!/usr/bin/env bash
set -uo pipefail

A108_HOST="${A108_HOST:-gx10-a108.tail57a229.ts.net}"
A108_SSH_OPTS="${A108_SSH_OPTS:--o BatchMode=yes -o ConnectTimeout=10}"
A108_ROOT="${A108_ROOT:-\$HOME/GitHub/arc-3}"
A108_CONFIG="${A108_CONFIG:-configs/a108.qwen36.json}"
A108_SMOKE_GAME="${A108_SMOKE_GAME:-ft09}"
A108_SMOKE_RUN="${A108_SMOKE_RUN:-a108-smoke-ft09}"
A108_SERVER_START_TIMEOUT="${A108_SERVER_START_TIMEOUT:-3600}"
A108_SERVER_TAIL_ON_WAIT="${A108_SERVER_TAIL_ON_WAIT:-true}"
REPORT_ROOT="${REPORT_ROOT:-reports/a108}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_DIR="${REPORT_ROOT}/${TIMESTAMP}"
OVERALL_STATUS=0

mkdir -p "${REPORT_DIR}"

run_step() {
  local name="$1"
  shift
  local log_path="${REPORT_DIR}/${name}.log"
  printf '\n== %s ==\n' "${name}" | tee -a "${REPORT_DIR}/summary.log"
  printf 'command:' | tee -a "${REPORT_DIR}/summary.log"
  printf ' %q' "$@" | tee -a "${REPORT_DIR}/summary.log"
  printf '\n' | tee -a "${REPORT_DIR}/summary.log"
  "$@" 2>&1 | tee "${log_path}"
  local status="${PIPESTATUS[0]}"
  printf 'status: %s\n' "${status}" | tee -a "${REPORT_DIR}/summary.log"
  if [[ "${status}" -ne 0 ]]; then
    OVERALL_STATUS="${status}"
    printf 'bootstrap stopped at step %s\n' "${name}" | tee -a "${REPORT_DIR}/summary.log"
    return "${status}"
  fi
  return 0
}

remote() {
  # shellcheck disable=SC2086
  ssh ${A108_SSH_OPTS} "${A108_HOST}" "$@"
}

printf 'a108 bootstrap report\n' >"${REPORT_DIR}/summary.log"
printf 'timestamp: %s\n' "${TIMESTAMP}" >>"${REPORT_DIR}/summary.log"
printf 'host: %s\n' "${A108_HOST}" >>"${REPORT_DIR}/summary.log"
printf 'ssh_opts: %s\n' "${A108_SSH_OPTS}" >>"${REPORT_DIR}/summary.log"
printf 'root: %s\n' "${A108_ROOT}" >>"${REPORT_DIR}/summary.log"
printf 'config: %s\n' "${A108_CONFIG}" >>"${REPORT_DIR}/summary.log"
printf 'server_start_timeout: %s\n' "${A108_SERVER_START_TIMEOUT}" >>"${REPORT_DIR}/summary.log"
printf 'server_tail_on_wait: %s\n' "${A108_SERVER_TAIL_ON_WAIT}" >>"${REPORT_DIR}/summary.log"

run_step local_workspace_check env A108_HOST="${A108_HOST}" A108_SSH_OPTS="${A108_SSH_OPTS}" A108_CONFIG="${A108_CONFIG}" bash scripts/check_workspace.sh || exit "${OVERALL_STATUS}"
# shellcheck disable=SC2086
run_step check_ssh ssh ${A108_SSH_OPTS} "${A108_HOST}" 'hostname && uname -a' || exit "${OVERALL_STATUS}"
# shellcheck disable=SC2086
run_step make_remote_root ssh ${A108_SSH_OPTS} "${A108_HOST}" "mkdir -p \"${A108_ROOT}\"" || exit "${OVERALL_STATUS}"
run_step sync rsync -az --delete \
  -e "ssh ${A108_SSH_OPTS}" \
  --exclude .git \
  --exclude .venv \
  --exclude .cache \
  --exclude runs \
  --exclude reports \
  --exclude __pycache__ \
  --exclude '*.pyc' \
  --exclude example-run \
  ./ "${A108_HOST}:${A108_ROOT}/" || exit "${OVERALL_STATUS}"
run_step check_env remote "cd \"${A108_ROOT}\" && A108_CONFIG=\"${A108_ROOT}/ARC3-Inference/${A108_CONFIG}\" bash scripts/check_a108_env.sh" || exit "${OVERALL_STATUS}"
run_step install remote "cd \"${A108_ROOT}/ARC3-Inference\" && CONFIG_PATH=\"${A108_CONFIG}\" make install-a108" || exit "${OVERALL_STATUS}"
run_step check_env_after_install remote "cd \"${A108_ROOT}\" && A108_CONFIG=\"${A108_ROOT}/ARC3-Inference/${A108_CONFIG}\" bash scripts/check_a108_env.sh" || exit "${OVERALL_STATUS}"
run_step server remote "cd \"${A108_ROOT}/ARC3-Inference\" && CONFIG_PATH=\"${A108_CONFIG}\" SERVER_START_TIMEOUT=\"${A108_SERVER_START_TIMEOUT}\" SERVER_TAIL_ON_WAIT=\"${A108_SERVER_TAIL_ON_WAIT}\" make server" || exit "${OVERALL_STATUS}"
run_step smoke_chat remote "cd \"${A108_ROOT}/ARC3-Inference\" && CONFIG_PATH=\"${A108_CONFIG}\" make chat PROMPT='Answer in one sentence: what is 2+2?'" || exit "${OVERALL_STATUS}"
run_step smoke_tool remote "cd \"${A108_ROOT}/ARC3-Inference\" && CONFIG_PATH=\"${A108_CONFIG}\" make smoke-tool" || exit "${OVERALL_STATUS}"
run_step smoke_game remote "cd \"${A108_ROOT}/ARC3-Inference\" && CONFIG_PATH=\"${A108_CONFIG}\" make interactive GAME=\"${A108_SMOKE_GAME}\" N_PASSES=1 CONCURRENT_JOBS=1 MAX_RUNTIME_MINUTES=10 RUN_NAME=\"${A108_SMOKE_RUN}\"" || exit "${OVERALL_STATUS}"
run_step score_smoke remote "cd \"${A108_ROOT}/ARC3-Inference\" && latest=\"\$(ls -dt runs/*/ 2>/dev/null | head -n 1)\" && if [ -z \"\$latest\" ]; then echo 'No run directories under runs/'; exit 1; fi; echo \"Scoring \$latest\"; CONFIG_PATH=\"${A108_CONFIG}\" make score_run SCORE_RUN_DIR=\"\$latest\"" || exit "${OVERALL_STATUS}"

printf '\nbootstrap completed successfully\n' | tee -a "${REPORT_DIR}/summary.log"
printf 'report directory: %s\n' "${REPORT_DIR}"
