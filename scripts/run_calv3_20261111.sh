#!/usr/bin/env bash
# [ext 2026-11-11] Calendar v3 read-only re-eval chain (E4 12 + E2 15 + REF start/p2cal 6 checkpoints).
# Resumable: each eval skips finished outputs.  Stop: bash scripts/stop_calv3.sh
# Launch:    bash scripts/launch_calv3_20261111.sh   (setsid, survives the caller)
# Env: CALV3_MODE=formal|pilot  (pilot = candidate items on REF:start + E4:tf50 of seed 20261108, before freezing)
#      GATE_MEM_MIB=3000 GATE_UTIL=40 (GPU idle gate, 3 consecutive checks 20 s apart, before every GPU job)
set -u
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
LOG=logs_ext; mkdir -p "$LOG"
MODE="${CALV3_MODE:-formal}"
TAG=calv3_20261111; [ "$MODE" = pilot ] && TAG=calv3_pilot_20261111
STATUS="$LOG/$TAG.status"
STOP="$LOG/calv3_20261111.stop"
echo "$$" > "$LOG/$TAG.pid"
PY=.venv/bin/python
GATE_MEM="${GATE_MEM_MIB:-3000}"
GATE_UTIL="${GATE_UTIL:-40}"
export TOKENIZERS_PARALLELISM=false HF_HUB_OFFLINE=1 PYTHONUNBUFFERED=1
CHAIN_START=$(date +%s)

st() { echo "$(date '+%F %T') $*" | tee -a "$STATUS"; }
stopped() { if [ -f "$STOP" ]; then st "STOPPED (stop flag)"; exit 0; fi; }
gpu_idle_once() {
  local line used util
  line=$(nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
  used=${line%%,*}; util=${line##*,}
  [ -n "$used" ] && [ "$used" -lt "$GATE_MEM" ] && [ "$util" -lt "$GATE_UTIL" ]
}
wait_gpu() {
  local ok=0 waited=0 noted=0
  while [ "$ok" -lt 3 ]; do
    stopped
    if gpu_idle_once; then ok=$((ok+1)); else ok=0; fi
    if [ "$ok" -lt 3 ]; then
      if [ "$noted" = 0 ] || [ $((waited % 600)) -eq 0 ]; then
        st "WAIT_GPU busy: $(nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader 2>/dev/null) waited=${waited}s"
        noted=1
      fi
      sleep 20; waited=$((waited+20))
    fi
  done
  [ "$waited" -gt 0 ] && st "GPU_IDLE after ${waited}s"
  return 0
}
job() {  # job <name> <gpu:0|1> <cmd...>
  local name="$1" gpu="$2"; shift 2
  stopped
  [ "$gpu" = 1 ] && wait_gpu
  st "START $name"
  local t0=$(date +%s) rc
  "$@"; rc=$?
  if [ "$rc" != 0 ] && [ "$gpu" = 1 ]; then
    st "RETRY $name rc=$rc"; sleep 30; stopped; wait_gpu; "$@"; rc=$?
  fi
  st "$([ "$rc" = 0 ] && echo DONE || echo FAIL) $name rc=$rc wall=$(( $(date +%s) - t0 ))s"
  return "$rc"
}

st "CHAIN_START mode=$MODE pid=$$"
if [ "$MODE" = pilot ]; then
  job pilot_start_20261108 1 $PY -m fac_tinyagent.calv3_run --phase pilot --round REF --seed 20261108 --arm start
  job pilot_e4tf50_20261108 1 $PY -m fac_tinyagent.calv3_run --phase pilot --round E4 --seed 20261108 --arm tf50
  job pilot_report 0 $PY -m fac_tinyagent.calv3_run --phase report --pilot-report
  st "ALL_DONE total=$(( $(date +%s) - CHAIN_START ))s"; echo CALV3_PILOT_FINISHED; exit 0
fi
if [ ! -f data_ext_cal_v3/final_v3/FROZEN.json ]; then st "ABORT calendar v3 not frozen"; exit 1; fi
FAILS=0
$PY -m fac_tinyagent.calv3_run --phase list > "$LOG/$TAG.targets"
cur=""
while read -r rnd seed arm; do
  if [ -n "$cur" ] && [ "$seed" != "$cur" ]; then job "report_after_${cur}" 0 $PY -m fac_tinyagent.calv3_run --phase report; fi
  cur="$seed"
  job "eval_${rnd}_${seed}_${arm}" 1 $PY -m fac_tinyagent.calv3_run --phase eval --round "$rnd" --seed "$seed" --arm "$arm" || FAILS=$((FAILS+1))
done < "$LOG/$TAG.targets"
job final_report 0 $PY -m fac_tinyagent.calv3_run --phase report
st "ALL_DONE fails=$FAILS total=$(( $(date +%s) - CHAIN_START ))s"
echo CALV3_FINISHED