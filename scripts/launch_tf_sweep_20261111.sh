#!/usr/bin/env bash
# Start run_tf_sweep_20261111.sh in its own session (survives the calling shell).
set -u
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
mkdir -p logs_ext
if [ -f logs_ext/tf_sweep_20261111.pid ] && kill -0 "$(cat logs_ext/tf_sweep_20261111.pid)" 2>/dev/null; then
  echo "already running pid $(cat logs_ext/tf_sweep_20261111.pid)"; exit 1
fi
rm -f logs_ext/tf_sweep_20261111.stop
echo "===== LAUNCH $(date) =====" >> logs_ext/tf_sweep_20261111.log
setsid nohup bash scripts/run_tf_sweep_20261111.sh >> logs_ext/tf_sweep_20261111.log 2>&1 < /dev/null &
sleep 2
echo "RUNNER_PID=$(cat logs_ext/tf_sweep_20261111.pid 2>/dev/null)"
tail -n 5 logs_ext/tf_sweep_20261111.status 2>/dev/null
