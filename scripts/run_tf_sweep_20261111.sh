#!/usr/bin/env bash
# [ext 2026-11-11] Monitor-v2 validation + target-fraction sweep chain (A scenario).
# Resumable: every step skips finished outputs. Stop: bash scripts/stop_tf_sweep.sh
# Launch:    bash scripts/launch_tf_sweep_20261111.sh   (setsid, survives the caller)
# Env: TF_SEEDS="20261108 20261109 20261110"  TF_ARMS="tf00 tf25 tf50 tf75"
#      TF_SKIP_NONE=1 (skip the optional no-replay arms)  TF_SKIP_MONITOR=1
#      GATE_MEM_MIB=3000 GATE_UTIL=40 (GPU idle gate checked before every GPU job)
set -u
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
LOG=logs_ext; mkdir -p "$LOG"
STATUS="$LOG/tf_sweep_20261111.status"
STOP="$LOG/tf_sweep_20261111.stop"
echo "$$" > "$LOG/tf_sweep_20261111.pid"
PY=.venv/bin/python
SEEDS="${TF_SEEDS:-20261108 20261109 20261110}"
ARMS="${TF_ARMS:-tf00 tf25 tf50 tf75}"
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

st "CHAIN_START pid=$$ seeds=[$SEEDS] arms=[$ARMS]"
job build_monitor_v2 0 $PY -m fac_tinyagent.monitor_v2_data || { st "ABORT monitor data"; exit 1; }
job monitor_report_cpu 0 $PY -m fac_tinyagent.monitor_v2_offline --phase report
if [ "${TF_SKIP_MONITOR:-0}" != 1 ]; then
  job monitor_v2_gpu 1 $PY -m fac_tinyagent.monitor_v2_offline --phase gpu
fi

SMOKE_SEED=$(echo $SEEDS | awk '{print $1}')
if [ ! -f runs_ext_tf_smoke/SMOKE_OK ]; then
  job smoke_train_tf00 1 $PY -m fac_tinyagent.ext_tf_sweep --phase train --seed "$SMOKE_SEED" --arm tf00 --smoke
  job smoke_eval_tf00 1 $PY -m fac_tinyagent.ext_tf_sweep --phase eval --seed "$SMOKE_SEED" --arm tf00 --smoke
  job smoke_train_tf50 1 $PY -m fac_tinyagent.ext_tf_sweep --phase train --seed "$SMOKE_SEED" --arm tf50 --smoke
  job smoke_eval_tf50 1 $PY -m fac_tinyagent.ext_tf_sweep --phase eval --seed "$SMOKE_SEED" --arm tf50 --smoke
  if job smoke_check 0 $PY -m fac_tinyagent.ext_tf_sweep --phase check-smoke --seed "$SMOKE_SEED" --smoke; then
    date > runs_ext_tf_smoke/SMOKE_OK
  else
    st "ABORT smoke failed; formal sweep not started"; exit 2
  fi
fi

run_arm() {
  local seed="$1" arm="$2"
  job "train_${seed}_${arm}" 1 $PY -m fac_tinyagent.ext_tf_sweep --phase train --seed "$seed" --arm "$arm" \
    && job "eval_${seed}_${arm}" 1 $PY -m fac_tinyagent.ext_tf_sweep --phase eval --seed "$seed" --arm "$arm"
}
for seed in $SEEDS; do
  for arm in $ARMS; do run_arm "$seed" "$arm"; done
  job "report_after_${seed}" 0 $PY -m fac_tinyagent.ext_tf_sweep --phase report
done
if [ "${TF_SKIP_NONE:-0}" != 1 ]; then
  for seed in $SEEDS; do run_arm "$seed" none; done
fi
job final_report 0 $PY -m fac_tinyagent.ext_tf_sweep --phase report
job monitor_report_final 0 $PY -m fac_tinyagent.monitor_v2_offline --phase report
st "ALL_DONE total=$(( $(date +%s) - CHAIN_START ))s"
echo TF_SWEEP_FINISHED
