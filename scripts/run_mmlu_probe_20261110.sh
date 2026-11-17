#!/usr/bin/env bash
# [ext-paper 2026-11-10] MMLU probe chain: stage trajectory, format controls, other seeds.
# Resumable: skips a job if $OUT/results.json already has the expected aggregate acc.
# Stop: bash scripts/stop_mmlu_probe.sh (touch stop flag + kill process group).
# Usage: from project root, in Ubuntu WSL:
#   nohup bash scripts/run_mmlu_probe_20261110.sh > logs_ext/mmlu_probe_20261110.log 2>&1 &
set -u
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
ROOT="$(pwd)"
LOGDIR="$ROOT/logs_ext"
OUTROOT="$ROOT/runs_ext_eval"
MODEL="/home/egret/models/Qwen3-0.6B"
PHASE2="$ROOT/runs_phase2"
STOPFILE="$LOGDIR/mmlu_probe_20261110.stop"
STATUS="$LOGDIR/mmlu_probe_20261110.status"
PIDFILE="$LOGDIR/mmlu_probe_20261110.pid"
mkdir -p "$LOGDIR" "$OUTROOT"
echo "$$" > "$PIDFILE"
date
echo "PROBE_PID=$$"
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu,power.draw,temperature.gpu --format=csv,noheader || true

START_TS=$(date +%s)
BUDGET_SECS="${PROBE_BUDGET_SECS:-14400}"
EST_FULL_LL=600

export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export TOKENIZERS_PARALLELISM=false
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export HF_DATASETS_OFFLINE="${HF_DATASETS_OFFLINE:-1}"
PREFETCHED=0

have_results() {
  local out="$1"
  local key="${2:-}"
  /home/egret/venvs/fac-eval/bin/python - "$out" "$key" <<'PY'
import json, sys
from pathlib import Path
out = Path(sys.argv[1]); key = sys.argv[2]
p = out / "results.json"
if not p.is_file() or p.stat().st_size < 50:
    sys.exit(1)
try:
    d = json.load(p.open(encoding="utf-8"))
except Exception:
    sys.exit(1)
res = d.get("results") or {}
if not res:
    sys.exit(1)
if key:
    if key in res and isinstance(res[key], dict):
        if any(("acc" in k or "exact_match" in k) and "stderr" not in k for k in res[key]):
            sys.exit(0)
    sys.exit(1)
for v in res.values():
    if isinstance(v, dict) and any(("acc" in k or "exact_match" in k) and "stderr" not in k for k in v):
        sys.exit(0)
sys.exit(1)
PY
}

remaining() {
  echo $(( BUDGET_SECS - ($(date +%s) - START_TS) ))
}

should_stop() {
  if [ -f "$STOPFILE" ]; then
    echo "STOP FLAG present; exiting between jobs. Completed results.json kept."
    echo "STOPPED $(date)" | tee -a "$STATUS"
    return 0
  fi
  return 1
}

log_status() {
  echo "$(date '+%F %T') $*" | tee -a "$STATUS"
}

run_job() {
  local name="$1"
  local key="$2"
  local estimate="$3"
  shift 3
  local out="$OUTROOT/$name"
  if should_stop; then
    return 99
  fi
  local rem
  rem=$(remaining)
  if [ "$rem" -lt "$estimate" ]; then
    log_status "SKIP_BUDGET $name rem=${rem}s estimate=${estimate}s"
    return 10
  fi
  if have_results "$out" "$key"; then
    log_status "SKIP_EXISTS $name"
    return 0
  fi
  mkdir -p "$out"
  log_status "START $name rem=${rem}s est=${estimate}s"
  local job_start job_end rc dur
  job_start=$(date +%s)
  bash scripts/eval_general.sh --model "$MODEL" --batch-size 16 --log-samples --output "$out" "$@"
  rc=$?
  if [ "$rc" = 3 ]; then
    log_status "RETRY $name after rc=3 (GPU busy guard)"
    sleep 5
    bash scripts/eval_general.sh --model "$MODEL" --batch-size 16 --log-samples --output "$out" "$@"
    rc=$?
  fi
  job_end=$(date +%s)
  dur=$((job_end - job_start))
  if have_results "$out" "$key"; then
    log_status "DONE $name rc=$rc wall=${dur}s"
    if [ "$estimate" -ge 300 ] && [ "$dur" -gt 60 ]; then
      EST_FULL_LL="$dur"
    fi
    return 0
  fi
  log_status "FAIL $name rc=$rc wall=${dur}s"
  return "$rc"
}

prefetch_mmlu_if_needed() {
  if [ "$PREFETCHED" = 1 ]; then
    return 0
  fi
  log_status "PREFETCH cais/mmlu (temporary online)"
  env -u HF_HUB_OFFLINE -u HF_DATASETS_OFFLINE HF_ENDPOINT="https://hf-mirror.com" \
    /home/egret/venvs/fac-eval/bin/python scripts/prefetch_eval_data.py cais/mmlu
  local rc=$?
  PREFETCHED=1
  log_status "PREFETCH_RC=$rc"
  return 0
}


log_status "PHASE 1 trajectory A_seed20261108 stage_01-03 default mmlu"
run_job q06b_A108_stage01_mmlu_full mmlu "$EST_FULL_LL" \
  --adapter "$PHASE2/A_seed20261108/checkpoints/stage_01_file" --tasks mmlu
rc=$?; [ "$rc" = 99 ] && exit 0

run_job q06b_A108_stage02_mmlu_full mmlu "$EST_FULL_LL" \
  --adapter "$PHASE2/A_seed20261108/checkpoints/stage_02_database" --tasks mmlu
rc=$?; [ "$rc" = 99 ] && exit 0

run_job q06b_A108_stage03_mmlu_full mmlu "$EST_FULL_LL" \
  --adapter "$PHASE2/A_seed20261108/checkpoints/stage_03_python" --tasks mmlu
rc=$?; [ "$rc" = 99 ] && exit 0

log_status "PHASE 3a chat-template default mmlu (base + stage_04)"
run_job q06b_base_mmlu_full_chat mmlu "$EST_FULL_LL" \
  --tasks mmlu --chat-template
rc=$?; [ "$rc" = 99 ] && exit 0
if [ "$rc" != 0 ] && [ "$rc" != 10 ]; then
  prefetch_mmlu_if_needed
  run_job q06b_base_mmlu_full_chat mmlu "$EST_FULL_LL" --tasks mmlu --chat-template
  rc=$?; [ "$rc" = 99 ] && exit 0
fi

run_job q06b_A108_stage04_mmlu_full_chat mmlu "$EST_FULL_LL" \
  --adapter "$PHASE2/A_seed20261108/checkpoints/stage_04_calendar" --tasks mmlu --chat-template
rc=$?; [ "$rc" = 99 ] && exit 0

log_status "PHASE 3b mmlu_continuation (choice-text loglikelihood, base + stage_04)"
run_job q06b_base_mmlu_continuation_full mmlu_continuation "$EST_FULL_LL" \
  --tasks mmlu_continuation
rc=$?; [ "$rc" = 99 ] && exit 0
if [ "$rc" != 0 ] && [ "$rc" != 10 ]; then
  prefetch_mmlu_if_needed
  run_job q06b_base_mmlu_continuation_full mmlu_continuation "$EST_FULL_LL" --tasks mmlu_continuation
  rc=$?; [ "$rc" = 99 ] && exit 0
fi

run_job q06b_A108_stage04_mmlu_continuation_full mmlu_continuation "$EST_FULL_LL" \
  --adapter "$PHASE2/A_seed20261108/checkpoints/stage_04_calendar" --tasks mmlu_continuation
rc=$?; [ "$rc" = 99 ] && exit 0


log_status "PHASE 3c mmlu_generative (same limit for base and adapter)"
GEN_LIMIT="${PROBE_GEN_LIMIT:-}"
TIME_L1=0
if [ -z "$GEN_LIMIT" ]; then
  rem=$(remaining)
  if [ "$rem" -gt 600 ]; then
    run_job q06b_base_mmlu_generative_l1 mmlu_generative 600 \
      --tasks mmlu_generative --max-gen-toks 32 --limit 1
    rc=$?; [ "$rc" = 99 ] && exit 0
    if [ "$rc" != 0 ] && [ "$rc" != 10 ]; then
      prefetch_mmlu_if_needed
      run_job q06b_base_mmlu_generative_l1 mmlu_generative 600 \
        --tasks mmlu_generative --max-gen-toks 32 --limit 1
      rc=$?; [ "$rc" = 99 ] && exit 0
    fi
  fi
  if have_results "$OUTROOT/q06b_base_mmlu_generative_l1" mmlu_generative; then
    TIME_L1=$(/home/egret/venvs/fac-eval/bin/python - <<'PY'
import json
from pathlib import Path
p=Path("/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent/runs_ext_eval/q06b_base_mmlu_generative_l1/results.json")
d=json.load(p.open(encoding="utf-8"))
print(int(round(float(d.get("wall_seconds") or 0))))
PY
)
  fi
  rem=$(remaining)
  reserve=$(( EST_FULL_LL * 3 ))
  if [ "$reserve" -gt $(( rem / 3 )) ]; then
    reserve=$(( rem / 3 ))
  fi
  usable=$(( rem - reserve ))
  if [ "$usable" -lt 0 ]; then usable=0; fi
  if [ "$TIME_L1" -gt 30 ]; then
    max_l=$(( usable / (2 * TIME_L1) ))
    if [ "$max_l" -gt 20 ]; then max_l=20; fi
    if [ "$max_l" -lt 5 ]; then max_l=5; fi
    GEN_LIMIT="$max_l"
  else
    if [ "$rem" -gt 7200 ]; then GEN_LIMIT=15
    elif [ "$rem" -gt 3600 ]; then GEN_LIMIT=8
    else GEN_LIMIT=5
    fi
  fi
  log_status "GEN_LIMIT=$GEN_LIMIT TIME_L1=${TIME_L1}s rem=${rem}s reserve=${reserve}s"
fi

if [ "$TIME_L1" -gt 30 ]; then
  EST_GEN=$(( TIME_L1 * GEN_LIMIT + 60 ))
else
  EST_GEN=$(( GEN_LIMIT * 90 + 120 ))
fi

run_job "q06b_base_mmlu_generative_l${GEN_LIMIT}" mmlu_generative "$EST_GEN" \
  --tasks mmlu_generative --max-gen-toks 32 --limit "$GEN_LIMIT"
rc=$?; [ "$rc" = 99 ] && exit 0

run_job "q06b_A108_stage04_mmlu_generative_l${GEN_LIMIT}" mmlu_generative "$EST_GEN" \
  --adapter "$PHASE2/A_seed20261108/checkpoints/stage_04_calendar" \
  --tasks mmlu_generative --max-gen-toks 32 --limit "$GEN_LIMIT"
rc=$?; [ "$rc" = 99 ] && exit 0

log_status "PHASE 2 other seeds/orders final adapters"
run_job q06b_A109_stage04_mmlu_full mmlu "$EST_FULL_LL" \
  --adapter "$PHASE2/A_seed20261109/checkpoints/stage_04_calendar" --tasks mmlu
rc=$?; [ "$rc" = 99 ] && exit 0

run_job q06b_B108_stage04_mmlu_full mmlu "$EST_FULL_LL" \
  --adapter "$PHASE2/B_seed20261108/checkpoints/stage_04_file" --tasks mmlu
rc=$?; [ "$rc" = 99 ] && exit 0

run_job q06b_A110_stage04_mmlu_full mmlu "$EST_FULL_LL" \
  --adapter "$PHASE2/A_seed20261110/checkpoints/stage_04_calendar" --tasks mmlu
rc=$?; [ "$rc" = 99 ] && exit 0

log_status "ALL_DONE rem=$(remaining)s est_full_ll=${EST_FULL_LL}s"
date
echo "PROBE_FINISHED"
exit 0
