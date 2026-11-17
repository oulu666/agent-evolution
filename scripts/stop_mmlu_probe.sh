#!/usr/bin/env bash
# Stop the MMLU probe chain started by scripts/run_mmlu_probe_20261110.sh.
# Already-written results.json / samples.json are kept. An in-flight job may be
# incomplete and will be retried if the chain is started again (skip-if-complete).
set -u
ROOT="/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
LOGDIR="$ROOT/logs_ext"
STOPFILE="$LOGDIR/mmlu_probe_20261110.stop"
PIDFILE="$LOGDIR/mmlu_probe_20261110.pid"
mkdir -p "$LOGDIR"
touch "$STOPFILE"
echo "wrote stop flag $STOPFILE"
if [ -f "$PIDFILE" ]; then
  PID="$(tr -d ' \n' < "$PIDFILE")"
  echo "pidfile pid=$PID"
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    PGID="$(ps -o pgid= -p "$PID" | tr -d ' ')"
    echo "killing process group $PGID (leader $PID)"
    if [ -n "$PGID" ]; then
      kill -TERM -- "-$PGID" 2>/dev/null || kill -TERM "$PID" 2>/dev/null || true
      sleep 2
      kill -KILL -- "-$PGID" 2>/dev/null || kill -KILL "$PID" 2>/dev/null || true
    else
      kill -TERM "$PID" 2>/dev/null || true
      sleep 2
      kill -KILL "$PID" 2>/dev/null || true
    fi
  else
    echo "runner pid not running"
  fi
else
  echo "no pidfile"
fi
echo "matching processes after signal:"
pgrep -af "scripts/eval_general.py|scripts/run_mmlu_probe_20261110.sh" || true
for p in $(pgrep -f "scripts/eval_general.py" || true); do
  echo "killing eval_general pid $p"
  kill -TERM "$p" 2>/dev/null || true
done
sleep 1
echo "stop requested at $(date). Completed results were not deleted."
