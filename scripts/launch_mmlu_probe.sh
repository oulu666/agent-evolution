#!/usr/bin/env bash
# Start the MMLU probe chain in its own session and exit.
set -u
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
mkdir -p logs_ext
rm -f logs_ext/mmlu_probe_20261110.stop
# keep previous log; start a fresh dated appendix
echo "===== LAUNCH $(date) =====" >> logs_ext/mmlu_probe_20261110.log
echo "===== LAUNCH $(date) =====" >> logs_ext/mmlu_probe_20261110.status
setsid bash scripts/run_mmlu_probe_20261110.sh >> logs_ext/mmlu_probe_20261110.log 2>&1 < /dev/null &
LPID=$!
echo "$LPID" > logs_ext/mmlu_probe_20261110.launch.pid
sleep 1
echo "LAUNCH_PID=$LPID"
if [ -f logs_ext/mmlu_probe_20261110.pid ]; then
  echo "RUNNER_PID=$(cat logs_ext/mmlu_probe_20261110.pid)"
fi
ps -p "$LPID" -o pid,pgid,cmd || true
tail -n 15 logs_ext/mmlu_probe_20261110.log || true
