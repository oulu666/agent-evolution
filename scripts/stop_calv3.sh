#!/usr/bin/env bash
# Stop the Calendar v3 chain (formal or pilot). Finished evals are kept; unfinished ones are redone on resume.
# Only kills this chain's own process group / calv3_run processes (never games or other jobs).
set -u
ROOT="/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
LOG="$ROOT/logs_ext"
touch "$LOG/calv3_20261111.stop"
echo "stop flag written"
for t in calv3_20261111 calv3_pilot_20261111; do
  PID="$(tr -d ' \n' < "$LOG/$t.pid" 2>/dev/null || true)"
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    PGID="$(ps -o pgid= -p "$PID" | tr -d ' ')"
    echo "killing process group $PGID ($t)"
    kill -TERM -- "-$PGID" 2>/dev/null || kill -TERM "$PID"
    sleep 3
    kill -KILL -- "-$PGID" 2>/dev/null || true
  fi
done
pkill -f "fac_tinyagent.calv3_run" 2>/dev/null || true
echo "$(date '+%F %T') STOP_REQUESTED" >> "$LOG/calv3_20261111.status"
echo "done; to resume: rm $LOG/calv3_20261111.stop && bash scripts/launch_calv3_20261111.sh"