#!/usr/bin/env bash
# Detached start of scripts/run_p3_20261114.sh (survives the calling shell).
#   bash scripts/launch_p3_20261114.sh queue
set -u
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
mkdir -p logs_ext
if [ -f logs_ext/p3_20261114.pid ] && kill -0 "$(cat logs_ext/p3_20261114.pid)" 2>/dev/null; then
  echo "already running pid $(cat logs_ext/p3_20261114.pid)"; exit 1
fi
echo "===== LAUNCH $(date '+%F %T %z') args: $* =====" >> logs_ext/p3_20261114.log
setsid nohup bash scripts/run_p3_20261114.sh "$@" >> logs_ext/p3_20261114.log 2>&1 < /dev/null &
sleep 5
echo "RUNNER_PID=$(cat logs_ext/p3_20261114.pid 2>/dev/null)"
tail -n 3 logs_ext/p3_20261114.status 2>/dev/null
