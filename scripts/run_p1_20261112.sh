#!/usr/bin/env bash
# [ext 2026-11-12 P1] E3-B2 queue runner (batch diag -> B1 bridge/T0/v3fix -> experiment A seed 08).
# Usage (normally via scripts/launch_p1_20261112.sh, which detaches with setsid):
#   bash scripts/run_p1_20261112.sh diag            # step 1 batch-path diagnostics
#   bash scripts/run_p1_20261112.sh queue [args]    # steps 2-5 (python -m fac_tinyagent.p1_run --phase queue)
#   bash scripts/run_p1_20261112.sh summarize       # CPU only
# Safety: refuses to start if r5apex is running OR tasklist fails (fail closed), or if the GPU power
# cap reads < 60 W (quiet mode ~33 W).  A watchdog polls tasklist every 30 s while GPU work runs and
# kills this runner's python (writes logs_ext/p1_20261112.stop) as soon as r5apex appears, or after
# 3 consecutive tasklist failures.  Every step is resumable (finished outputs are skipped).
set -u
ROOT="/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
cd "$ROOT"
mkdir -p logs_ext
LOG="$ROOT/logs_ext/p1_20261112.log"
STATUS="$ROOT/logs_ext/p1_20261112.status"
STOP="$ROOT/logs_ext/p1_20261112.stop"
PY="$ROOT/.venv/bin/python"
export PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false HF_HUB_OFFLINE=1
echo "$$" > "$ROOT/logs_ext/p1_20261112.pid"
st() { echo "$(date '+%F %T %z') $*" | tee -a "$STATUS" >> "$LOG"; }

# 0 = game running, 1 = clear, 2 = check failed
game_check() {
  local out
  if ! out=$(/mnt/c/Windows/System32/tasklist.exe 2>/dev/null); then return 2; fi
  [ -z "$out" ] && return 2
  if printf '%s\n' "$out" | LC_ALL=C grep -qi r5apex; then return 0; fi
  return 1
}
power_cap() {
  nvidia-smi 2>/dev/null | LC_ALL=C grep -oE '/ +[0-9]+W' | head -1 | tr -dc '0-9'
}
preflight() {
  local s=0
  if [ -f "$STOP" ]; then st "STOP flag present ($STOP); not starting"; exit 3; fi
  game_check || s=$?
  if [ "$s" -eq 0 ]; then st "REFUSE r5apex running"; exit 2; fi
  if [ "$s" -ne 1 ]; then st "REFUSE tasklist check failed"; exit 2; fi
  local cap; cap=$(power_cap)
  if [ -n "$cap" ] && [ "$cap" -lt 60 ]; then st "REFUSE power cap ${cap}W (<60W, quiet mode?)"; exit 4; fi
  st "PREFLIGHT ok game=no power_cap=${cap:-unknown}W $(nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader 2>/dev/null)"
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
    "$PY" -m fac_tinyagent.p1_run --phase summarize "$@" >> "$LOG" 2>&1
    st "END summarize rc=$?"; exit 0 ;;
  diag) MOD=(-m fac_tinyagent.p1_batchdiag) ;;
  queue) MOD=(-m fac_tinyagent.p1_run --phase queue) ;;
  *) echo "unknown phase $phase"; exit 1 ;;
esac
preflight
st "START $phase $*"
"$PY" "${MOD[@]}" "$@" >> "$LOG" 2>&1 &
PYPID=$!
watchdog "$PYPID" &
WD=$!
wait "$PYPID"; rc=$?
kill "$WD" 2>/dev/null
st "END $phase rc=$rc"
if [ "$phase" = "queue" ] && [ "$rc" -eq 0 ]; then
  "$PY" -m fac_tinyagent.p1_run --phase summarize >> "$LOG" 2>&1 && st "summary refreshed"
fi
exit $rc
