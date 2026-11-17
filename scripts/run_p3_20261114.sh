#!/usr/bin/env bash
# [ext 2026-11-14] P3「条数 vs 时机」runner（E3B2_PREREG_AMEND_20261114_p3_count_timing_ZH.md）。
# 由 scripts/run_timing_20261113.sh 改写：同样的开跑前检查与 watchdog（tasklist 有 r5apex / tasklist 连续失败 3 次 /
# 功耗上限 <60W 时写停止标志并杀掉任务）。可续跑：已完成的训练与 suite 会跳过，被打断的 suite 从头重评。
#   bash scripts/run_p3_20261114.sh queue      # 训练 + B1 评测（GPU）
#   bash scripts/run_p3_20261114.sh summarize  # CPU
set -u
ROOT="/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
cd "$ROOT"
mkdir -p logs_ext
LOG="$ROOT/logs_ext/p3_20261114.log"
STATUS="$ROOT/logs_ext/p3_20261114.status"
STOP="$ROOT/logs_ext/p3_20261114.stop"
PY="$ROOT/.venv/bin/python"
export PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false HF_HUB_OFFLINE=1
st() { echo "$(date '+%F %T %z') $*" | tee -a "$STATUS" >> "$LOG"; }
game_check() {  # 0 = game running, 1 = clear, 2 = check failed
  local out
  if ! out=$(/mnt/c/Windows/System32/tasklist.exe 2>/dev/null); then return 2; fi
  [ -z "$out" ] && return 2
  if printf '%s\n' "$out" | LC_ALL=C grep -qi r5apex; then return 0; fi
  return 1
}
power_cap() {
  nvidia-smi --query-gpu=enforced.power.limit --format=csv,noheader,nounits 2>/dev/null | head -1 | cut -d. -f1 | tr -dc '0-9'
}
preflight() {
  local s=0
  if [ -f "$STOP" ]; then st "STOP flag present ($STOP); not starting"; exit 3; fi
  game_check || s=$?
  if [ "$s" -eq 0 ]; then st "REFUSE r5apex running"; exit 2; fi
  if [ "$s" -ne 1 ]; then st "REFUSE tasklist check failed"; exit 2; fi
  local cap; cap=$(power_cap)
  if [ -z "$cap" ] || [ "$cap" -lt 60 ]; then st "REFUSE power cap '${cap}'W (<60W or unreadable)"; exit 4; fi
  local apps; apps=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader 2>/dev/null | tr -d ' ')
  if [ -n "$apps" ]; then st "REFUSE other GPU compute process(es): $apps"; exit 5; fi
  st "PREFLIGHT ok game=no power_cap=${cap}W other_gpu_procs=none $(nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader 2>/dev/null)"
}
watchdog() {  # $1 = pid to kill
  local target="$1" fails=0 s
  while kill -0 "$target" 2>/dev/null; do
    sleep 30
    s=0; game_check || s=$?
    if [ "$s" -eq 0 ]; then
      st "WATCHDOG r5apex detected -> stopping GPU job pid $target"; touch "$STOP"
      pkill -TERM -P "$target" 2>/dev/null; kill -TERM "$target" 2>/dev/null; sleep 5; kill -KILL "$target" 2>/dev/null
      return
    elif [ "$s" -ne 1 ]; then
      fails=$((fails+1))
      if [ "$fails" -ge 3 ]; then
        st "WATCHDOG tasklist failed 3x -> stopping GPU job pid $target (fail closed)"; touch "$STOP"
        kill -TERM "$target" 2>/dev/null; sleep 5; kill -KILL "$target" 2>/dev/null
        return
      fi
    else
      fails=0
    fi
    local cap; cap=$(power_cap)
    if [ -n "$cap" ] && [ "$cap" -lt 60 ]; then
      st "WATCHDOG power cap dropped to ${cap}W -> stopping GPU job"; touch "$STOP"
      kill -TERM "$target" 2>/dev/null; sleep 5; kill -KILL "$target" 2>/dev/null
      return
    fi
  done
}
phase="${1:-queue}"; shift || true
case "$phase" in
  summarize)
    st "START summarize (CPU)"
    "$PY" -m fac_tinyagent.p3_count_timing --phase summarize >> "$LOG" 2>&1
    st "END summarize rc=$?"; exit 0 ;;
  queue) MOD=(-m fac_tinyagent.p3_count_timing --phase queue) ;;
  *) echo "unknown phase $phase"; exit 1 ;;
esac
echo "$$" > "$ROOT/logs_ext/p3_20261114.pid"
preflight
st "START $phase"
"$PY" "${MOD[@]}" >> "$LOG" 2>&1 &
PYPID=$!
watchdog "$PYPID" &
WD=$!
wait "$PYPID"; rc=$?
kill "$WD" 2>/dev/null
st "END $phase rc=$rc"
exit $rc
