#!/usr/bin/env bash
# [ext 2026-11-11] E3 chain: budget sweep (5%/20% x tf00/tf25/tf50) + Database dose (10%, k=0/1/2/3/4/6)
# + compute-matched Calendar-only control (10%).  10% tf00/tf25/tf50 and none are REUSED from E4.
# Order: E3-A (budget x tf + Calendar-only controls) seed 08 -> 09 -> 10, THEN E3-B (Database dose) 08 -> 09 -> 10;
#        within a seed see data_ext_e3/manifest.json.  E3_WITH_DRAW2=1 appends the optional second nested draw (E3-B2).
# Resumable: finished trainings (train_summary.json) and evals (EVAL_DONE) are skipped in the shell,
# an interrupted branch is moved aside (*_partial_<ts>) and retrained.  Stop: bash scripts/stop_e3.sh
# Launch: bash scripts/launch_e3_20261111.sh  (setsid, survives the caller)
# Env: E3_SEEDS="20261108 20261109 20261110"  E3_GROUPS="A B"  E3_ARMS_A / E3_ARMS_B / E3_WITH_DRAW2=1
#      GATE_MEM_MIB=3000 GATE_UTIL=40 (GPU idle gate: 3 consecutive checks 20 s apart before every GPU job,
#      and no other fac_tinyagent python process may be running)
set -u
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
LOG=logs_ext; mkdir -p "$LOG"
STATUS="$LOG/e3_20261111.status"
STOP="$LOG/e3_20261111.stop"
echo "$$" > "$LOG/e3_20261111.pid"
PY=.venv/bin/python
SEEDS="${E3_SEEDS:-20261108 20261109 20261110}"
RUN_GROUPS="${E3_GROUPS:-A B}"
ARMS_A="${E3_ARMS_A:-b05_tf25 b20_tf25 b05_tf50 b20_tf50 ctrl_cal10 ctrl_cal05 ctrl_cal20 b05_tf00 b20_tf00}"
ARMS_B="${E3_ARMS_B:-dose_db0 dose_db6 dose_db2 dose_db4 dose_db1 dose_db3}"
[ "${E3_WITH_DRAW2:-0}" = 1 ] && ARMS_B="$ARMS_B dose2_db6 dose2_db2 dose2_db4 dose2_db1 dose2_db3"
GATE_MEM="${GATE_MEM_MIB:-3000}"
GATE_UTIL="${GATE_UTIL:-40}"
export TOKENIZERS_PARALLELISM=false HF_HUB_OFFLINE=1 PYTHONUNBUFFERED=1
CHAIN_START=$(date +%s)
FAILS=0

st() { echo "$(date '+%F %T') $*" | tee -a "$STATUS"; }
stopped() { if [ -f "$STOP" ]; then st "STOPPED (stop flag)"; exit 0; fi; }
other_py() { pgrep -af "python.*fac_tinyagent" | grep -v "^$$ " | grep -v pgrep | head -1; }
gpu_idle_once() {
  local line used util
  [ -n "$(other_py)" ] && return 1
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
        st "WAIT_GPU busy: $(nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader 2>/dev/null) other_py=[$(other_py)] waited=${waited}s"
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
    stopped; st "RETRY $name rc=$rc"; sleep 30; stopped; wait_gpu; "$@"; rc=$?
  fi
  st "$([ "$rc" = 0 ] && echo DONE || echo FAIL) $name rc=$rc wall=$(( $(date +%s) - t0 ))s"
  return "$rc"
}

st "CHAIN_START pid=$$ seeds=[$SEEDS] groups=[$RUN_GROUPS] A=[$ARMS_A] B=[$ARMS_B]"
if [ ! -f data_ext_e3/manifest.json ]; then
  job build_e3_data 0 $PY -m fac_tinyagent.e3_data || { st "ABORT e3 data build"; exit 1; }
fi
job check_e3_data 0 $PY scripts/test_e3_data.py || { st "ABORT e3 data checks failed"; exit 1; }
job prep_prefixes 0 $PY -m fac_tinyagent.e3_run --phase prep || { st "ABORT prefix copy/verify failed"; exit 1; }

SMOKE_SEED=$(echo $SEEDS | awk '{print $1}')
export E3_SMOKE_DIR="${E3_SMOKE_DIR:-runs_ext_e3_smoke_v2}"   # v2 = smoke of the revised (post-review) plan code
if [ ! -f "$E3_SMOKE_DIR/SMOKE_OK" ]; then
  for arm in dose_db2 ctrl_cal10; do
    job "smoke_train_$arm" 1 $PY -m fac_tinyagent.e3_run --phase train --seed "$SMOKE_SEED" --arm "$arm" --smoke
    job "smoke_eval_$arm" 1 $PY -m fac_tinyagent.e3_run --phase eval --seed "$SMOKE_SEED" --arm "$arm" --smoke
  done
  if job smoke_check 0 $PY -m fac_tinyagent.e3_run --phase check-smoke --seed "$SMOKE_SEED" --smoke; then
    date > "$E3_SMOKE_DIR/SMOKE_OK"
  else
    st "ABORT smoke failed; formal E3 not started"; exit 2
  fi
fi

run_arm() {
  local seed="$1" arm="$2" b="runs_ext_e3/branches/A_seed${1}_${2}" e="runs_ext_e3/evaluation/A_seed${1}_${2}"
  if [ -f "$b/checkpoint/train_summary.json" ]; then st "SKIP train_${seed}_${arm} (done)";
  else job "train_${seed}_${arm}" 1 $PY -m fac_tinyagent.e3_run --phase train --seed "$seed" --arm "$arm" || return 1; fi
  if [ -f "$e/EVAL_DONE" ]; then st "SKIP eval_${seed}_${arm} (done)";
  else job "eval_${seed}_${arm}" 1 $PY -m fac_tinyagent.e3_run --phase eval --seed "$seed" --arm "$arm" || return 1; fi
}
for g in $RUN_GROUPS; do
  if [ "$g" = A ]; then ARMS="$ARMS_A"; else ARMS="$ARMS_B"; fi
  st "GROUP_START E3-$g"
  for seed in $SEEDS; do
    for arm in $ARMS; do run_arm "$seed" "$arm" || FAILS=$((FAILS+1)); done
    job "report_after_E3${g}_${seed}" 0 $PY -m fac_tinyagent.e3_run --phase report
  done
  st "GROUP_DONE E3-$g fails_so_far=$FAILS"
done
job final_report 0 $PY -m fac_tinyagent.e3_run --phase report
st "ALL_DONE fails=$FAILS total=$(( $(date +%s) - CHAIN_START ))s"
echo E3_FINISHED
