#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${NEWS_REPORT_PROJECT_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
PYTHON_BIN="${NEWS_REPORT_PYTHON:-${PROJECT_DIR}/venv/bin/python3}"
LOG_DIR="${PROJECT_DIR}/logs"
RUN_DATE="$(date +%Y-%m-%d)"
LOG_FILE="${LOG_DIR}/daily_report_${RUN_DATE}.log"

mkdir -p "${LOG_DIR}"

{
  echo "============================================================"
  echo "[run_daily_report] start: $(date '+%Y-%m-%d %H:%M:%S')"
  echo "[run_daily_report] project: ${PROJECT_DIR}"
  echo "[run_daily_report] python: ${PYTHON_BIN}"
  echo "[run_daily_report] args: $*"
  echo "============================================================"
} >> "${LOG_FILE}"

cd "${PROJECT_DIR}"

if [ -f "${PROJECT_DIR}/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "${PROJECT_DIR}/.env"
  set +a
else
  echo "[run_daily_report][WARN] .env not found: ${PROJECT_DIR}/.env" >> "${LOG_FILE}"
fi

CMD=("${PYTHON_BIN}" main.py run-daily-report "$@")

{
  echo "[run_daily_report] command: ${CMD[*]}"
} >> "${LOG_FILE}"

set +e
"${CMD[@]}" >> "${LOG_FILE}" 2>&1
EXIT_CODE=$?
set -e

{
  echo "[run_daily_report] exit_code: ${EXIT_CODE}"
  echo "[run_daily_report] end: $(date '+%Y-%m-%d %H:%M:%S')"
  echo
} >> "${LOG_FILE}"

exit "${EXIT_CODE}"
