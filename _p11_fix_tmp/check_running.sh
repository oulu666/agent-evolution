#!/usr/bin/env bash
set -euo pipefail
export TZ=Asia/Shanghai
ROOT="/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
cd "$ROOT"
LOG="$ROOT/runs_ext_p11_eaar_v1/logs"
echo "======= pids ======="
echo -n "host="; cat "$LOG/host.pid"; echo
echo -n "supervisor="; cat "$LOG/supervisor.pid"; echo
echo -n "worker="; cat "$LOG/worker.pid"; echo
echo "======= ps ======="
HOST=$(tr -d '[:space:]' < "$LOG/host.pid")
SUP=$(tr -d '[:space:]' < "$LOG/supervisor.pid")
WK=$(tr -d '[:space:]' < "$LOG/worker.pid")
ps -p "$HOST,$SUP,$WK" -o pid,ppid,sid,etime,cmd || true
echo "======= still alive? ======="
for n in host supervisor worker; do
  pid=$(tr -d '[:space:]' < "$LOG/${n}.pid")
  if kill -0 "$pid" 2>/dev/null; then echo "$n $pid ALIVE"; else echo "$n $pid DEAD"; fi
done
echo "======= host.stdout ======="
cat "$LOG/host.stdout.log"
echo "======= host.stderr ======="
cat "$LOG/host.stderr.log"
echo "======= worker.log last lines ======="
tail -n 20 "$LOG/worker.log"
echo "======= ERROR ======="
if [[ -f "$ROOT/runs_ext_p11_eaar_v1/ERROR.json" ]]; then cat "$ROOT/runs_ext_p11_eaar_v1/ERROR.json"; else echo no_ERROR; fi
echo "======= supervisor_end ======="
if [[ -f "$ROOT/runs_ext_p11_eaar_v1/supervisor_end.json" ]]; then cat "$ROOT/runs_ext_p11_eaar_v1/supervisor_end.json"; else echo none; fi
echo "======= probes ======="
ls -la "$ROOT/runs_ext_p11_eaar_v1/probes" 2>/dev/null || true
find "$ROOT/runs_ext_p11_eaar_v1/probes" -type f 2>/dev/null | head
echo "======= nvidia compute ======="
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
