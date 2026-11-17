#!/usr/bin/env bash
# Detached start of scripts/run_timing_20261113.sh (survives the calling shell).
set -u
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
mkdir -p logs_ext
if [ -f logs_ext/timing_20261113.pid ] && kill -0 "$(cat logs_ext/timing_20261113.pid)" 2>/dev/null; then
  echo "already running pid $(cat logs_ext/timing_20261113.pid)"; exit 1
fi
echo "===== LAUNCH $(date '+%F %T %z') args: $* =====" >> logs_ext/timing_20261113.log
setsid nohup bash scripts/run_timing_20261113.sh "$@" >> logs_ext/timing_20261113.log 2>&1 < /dev/null &
sleep 5
echo "RUNNER_PID=$(cat logs_ext/timing_20261113.pid 2>/dev/null)"
tail -n 3 logs_ext/timing_20261113.status 2>/dev/null
