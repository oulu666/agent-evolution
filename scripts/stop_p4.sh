#!/usr/bin/env bash
# Stop the P4 chain. Finished outputs are kept; an unfinished suite is re-run from scratch on resume.
# Resume: rm -f logs_ext/p4_20261114.stop && bash scripts/launch_p4_20261114.sh queue
set -u
ROOT="/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
touch "$ROOT/logs_ext/p4_20261114.stop"
PID="$(tr -d ' \n' < "$ROOT/logs_ext/p4_20261114.pid" 2>/dev/null || true)"
if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
  PGID="$(ps -o pgid= -p "$PID" | tr -d ' ')"; kill -TERM -- "-$PGID" 2>/dev/null || kill -TERM "$PID"
  sleep 3; kill -KILL -- "-$PGID" 2>/dev/null || true
fi
pkill -f "fac_tinyagent.p4_forget_timing" 2>/dev/null || true
echo "$(date '+%F %T %z') STOP_REQUESTED" >> "$ROOT/logs_ext/p4_20261114.status"
echo stopped
