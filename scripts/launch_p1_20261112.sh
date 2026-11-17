#!/usr/bin/env bash
# Detached start of scripts/run_p1_20261112.sh (survives the calling shell). Args are passed through.
set -u
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
mkdir -p logs_ext
if [ -f logs_ext/p1_20261112.pid ] && kill -0 "$(cat logs_ext/p1_20261112.pid)" 2>/dev/null; then
  echo "already running pid $(cat logs_ext/p1_20261112.pid)"; exit 1
fi
echo "===== LAUNCH $(date '+%F %T %z') args: $* =====" >> logs_ext/p1_20261112.log
setsid nohup bash scripts/run_p1_20261112.sh "$@" >> logs_ext/p1_20261112.log 2>&1 < /dev/null &
sleep 3
echo "RUNNER_PID=$(cat logs_ext/p1_20261112.pid 2>/dev/null)"
tail -n 3 logs_ext/p1_20261112.status 2>/dev/null
