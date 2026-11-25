#!/usr/bin/env bash
set -euo pipefail
export TZ=Asia/Shanghai
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
export HF_HUB_OFFLINE=1
export TOKENIZERS_PARALLELISM=false
ROOT="/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
cd "$ROOT"
LOG="$ROOT/runs_ext_p11_eaar_v1/logs"
mkdir -p "$LOG"
if [[ -f "$LOG/host.pid" ]] && kill -0 "$(cat "$LOG/host.pid")" 2>/dev/null; then
  echo "host already running pid=$(cat "$LOG/host.pid")" >&2
  exit 1
fi
# setsid+nohup so the supervisor survives this shell
setsid nohup "$ROOT/.venv/bin/python" -B -m fac_tinyagent.p11_queue_20261118 supervise   >>"$LOG/host.stdout.log" 2>>"$LOG/host.stderr.log" </dev/null &
echo $! > "$LOG/host.pid"
echo "started host_pid=$(cat "$LOG/host.pid")"
