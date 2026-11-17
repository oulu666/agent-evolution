#!/usr/bin/env bash
# P0 GPU / CPU launcher. Never writes into existing runs_*/data_* except new data_ext_p0_* / runs_ext_p0_*.
set -euo pipefail
ROOT="/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
cd "$ROOT"
export PYTHONUNBUFFERED=1
PY="$ROOT/.venv/bin/python"
LOG="$ROOT/logs_ext/p0_20261112.log"
mkdir -p "$ROOT/logs_ext"

# 0 = game running, 1 = clear, 2+ = check failed (fail closed).
game_running() {
  local out rc
  if ! out=$(/mnt/c/Windows/System32/tasklist.exe 2>&1); then
    rc=$?
    echo "tasklist failed rc=${rc}; refusing to start GPU work" | tee -a "$LOG"
    return 2
  fi
  if printf '%s\n' "$out" | grep -qi r5apex; then
    return 0
  fi
  return 1
}

status=0
game_running || status=$?
if [[ "$status" -eq 0 ]]; then
  echo "r5apex is running; refusing to start GPU work" | tee -a "$LOG"
  exit 2
elif [[ "$status" -ne 1 ]]; then
  exit 2
fi

phase="${1:-all-gpu}"
{
  echo "===== $(date '+%Y-%m-%d %H:%M:%S %z') phase=$phase ====="
  nvidia-smi --query-gpu=utilization.gpu,memory.used,power.draw,power.limit,temperature.gpu --format=csv,noheader || true
  "$PY" -m fac_tinyagent.p0_run --phase "$phase" "${@:2}"
  echo "===== $(date '+%Y-%m-%d %H:%M:%S %z') phase=$phase DONE ====="
} 2>&1 | tee -a "$LOG"
