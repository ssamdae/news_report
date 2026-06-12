#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${NEWS_REPORT_PROJECT_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
PYTHON_BIN="${NEWS_REPORT_PYTHON:-${PROJECT_DIR}/venv/bin/python3}"
LOG_DIR="${PROJECT_DIR}/logs"
RUN_DATE="$(date +%Y-%m-%d)"
LOG_FILE="${LOG_DIR}/daily_report_${RUN_DATE}.log"

mkdir -p "${LOG_DIR}"

log() {
  echo "$@" | tee -a "${LOG_FILE}"
}

on_interrupt() {
  local exit_code=$?
  log "[run_daily_report] interrupted_or_terminated: $(date '+%Y-%m-%d %H:%M:%S') exit_code=${exit_code}"
  exit "${exit_code}"
}

trap on_interrupt INT TERM

log "============================================================"
log "[run_daily_report] start: $(date '+%Y-%m-%d %H:%M:%S')"
log "[run_daily_report] project: ${PROJECT_DIR}"
log "[run_daily_report] python: ${PYTHON_BIN}"
log "[run_daily_report] args: $*"
log "============================================================"

cd "${PROJECT_DIR}"

if [ -f "${PROJECT_DIR}/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "${PROJECT_DIR}/.env"
  set +a
else
  log "[run_daily_report][WARN] .env not found: ${PROJECT_DIR}/.env"
fi

CMD=("${PYTHON_BIN}" -u main.py run-daily-report "$@")

log "[run_daily_report] command: ${CMD[*]}"

set +e
PYTHONUNBUFFERED=1 "${CMD[@]}" 2>&1 | tee -a "${LOG_FILE}"
EXIT_CODE=${PIPESTATUS[0]}
set -e

log "[run_daily_report] exit_code: ${EXIT_CODE}"
log "[run_daily_report] end: $(date '+%Y-%m-%d %H:%M:%S')"
log ""

exit "${EXIT_CODE}"
