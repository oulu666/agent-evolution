#!/usr/bin/env bash
# Stop the P1 chain. Finished outputs are kept; an unfinished suite is re-run from scratch on resume.
# Resume: rm logs_ext/p1_20261112.stop && bash scripts/launch_p1_20261112.sh queue
set -u
ROOT="/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
touch "$ROOT/logs_ext/p1_20261112.stop"
PID="$(tr -d ' \n' < "$ROOT/logs_ext/p1_20261112.pid" 2>/dev/null || true)"
if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
  PGID="$(ps -o pgid= -p "$PID" | tr -d ' ')"; kill -TERM -- "-$PGID" 2>/dev/null || kill -TERM "$PID"
  sleep 3; kill -KILL -- "-$PGID" 2>/dev/null || true
fi
pkill -f "fac_tinyagent.p1_" 2>/dev/null || true
echo "$(date '+%F %T %z') STOP_REQUESTED" >> "$ROOT/logs_ext/p1_20261112.status"
echo stopped
