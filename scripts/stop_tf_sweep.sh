#!/usr/bin/env bash
# Stop the chain started by scripts/run_tf_sweep_20261111.sh. Finished outputs are kept;
# an interrupted training branch is moved aside (A_seed*_tfXX_partial_*) on the next start.
set -u
ROOT="/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
LOG="$ROOT/logs_ext"
touch "$LOG/tf_sweep_20261111.stop"
echo "stop flag written"
PID="$(tr -d ' \n' < "$LOG/tf_sweep_20261111.pid" 2>/dev/null || true)"
if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
  PGID="$(ps -o pgid= -p "$PID" | tr -d ' ')"
  echo "killing process group $PGID"
  kill -TERM -- "-$PGID" 2>/dev/null || kill -TERM "$PID"
  sleep 3
  kill -KILL -- "-$PGID" 2>/dev/null || true
else
  echo "runner not running"
fi
pkill -f "fac_tinyagent.ext_tf_sweep|fac_tinyagent.monitor_v2_offline" 2>/dev/null || true
echo "$(date '+%F %T') STOP_REQUESTED" >> "$LOG/tf_sweep_20261111.status"
echo "done; to resume: rm $LOG/tf_sweep_20261111.stop && bash scripts/launch_tf_sweep_20261111.sh"
