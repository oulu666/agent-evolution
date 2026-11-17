#!/usr/bin/env bash
# Start run_calv3_20261111.sh in its own session (survives the calling shell).
# Pilot: CALV3_MODE=pilot bash scripts/launch_calv3_20261111.sh
set -u
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
mkdir -p logs_ext
MODE="${CALV3_MODE:-formal}"
TAG=calv3_20261111; [ "$MODE" = pilot ] && TAG=calv3_pilot_20261111
for t in calv3_20261111 calv3_pilot_20261111; do
  if [ -f logs_ext/$t.pid ] && kill -0 "$(cat logs_ext/$t.pid)" 2>/dev/null; then
    echo "already running ($t) pid $(cat logs_ext/$t.pid)"; exit 1
  fi
done
rm -f logs_ext/calv3_20261111.stop
echo "===== LAUNCH $(date) mode=$MODE =====" >> logs_ext/$TAG.log
CALV3_MODE="$MODE" setsid nohup bash scripts/run_calv3_20261111.sh >> logs_ext/$TAG.log 2>&1 < /dev/null &
sleep 2
echo "RUNNER_PID=$(cat logs_ext/$TAG.pid 2>/dev/null)"
tail -n 5 logs_ext/$TAG.status 2>/dev/null