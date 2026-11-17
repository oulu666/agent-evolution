#!/usr/bin/env bash
set -u
ROOT="/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
PIDFILE="$ROOT/logs_ext/mmlu_probe_20261110.pid"
STATUS="$ROOT/logs_ext/mmlu_probe_20261110.status"
LOG="$ROOT/logs_ext/mmlu_probe_20261110.log"
# Wait until the runner pid is gone, then print a short summary.
if [ ! -f "$PIDFILE" ]; then
  echo "NO_PIDFILE"
  exit 1
fi
PID="$(tr -d ' \n' < "$PIDFILE")"
echo "waiting for runner pid $PID"
while kill -0 "$PID" 2>/dev/null; do
  sleep 20
done
echo "PROBE_CHAIN_EXITED $(date)"
echo "======= status ======="
cat "$STATUS"
echo "======= log tail ======="
tail -n 30 "$LOG"
