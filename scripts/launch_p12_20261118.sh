#!/usr/bin/env bash
set -euo pipefail
export TZ=Asia/Shanghai PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false
ROOT="/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
cd "$ROOT"
LOG="$ROOT/runs_ext_p12_eaar_v2/logs"
mkdir -p "$LOG"
if [[ -f "$LOG/host.pid" ]]; then echo "existing host PID evidence; refuse" >&2; exit 1; fi
setsid nohup "$ROOT/.venv/bin/python" -B -m fac_tinyagent.p12_queue_20261118 supervise >>"$LOG/host.stdout.log" 2>>"$LOG/host.stderr.log" </dev/null &
echo $! > "$LOG/host.pid"
echo "started host/supervisor $(<"$LOG/host.pid")"
