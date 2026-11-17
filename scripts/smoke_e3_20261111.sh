#!/usr/bin/env bash
# [ext 2026-11-11] One-off E3 GPU smoke test (runs_ext_e3_smoke/ only; does NOT start the formal chain).
# dose_db2 + ctrl_cal10 on seed 20261108: 16 Calendar rows, 1 epoch, probes 1/8, replay 30%, eval 3 items/suite + 1/v3 type.
set -u
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
PY=.venv/bin/python
export E3_SMOKE_DIR="${E3_SMOKE_DIR:-runs_ext_e3_smoke}"
export TOKENIZERS_PARALLELISM=false HF_HUB_OFFLINE=1 PYTHONUNBUFFERED=1
S=20261108
t0=$(date +%s)
step() { echo "$(date '+%F %T') START $*"; local a=$(date +%s); "$@"; local rc=$?; echo "$(date '+%F %T') END rc=$rc wall=$(( $(date +%s)-a ))s :: $*"; return $rc; }
[ "${E3_SKIP_PREP:-0}" = 1 ] || step $PY -m fac_tinyagent.e3_run --phase prep || exit 1
for arm in dose_db2 ctrl_cal10; do
  step $PY -m fac_tinyagent.e3_run --phase train --seed $S --arm $arm --smoke || exit 1
  step $PY -m fac_tinyagent.e3_run --phase eval --seed $S --arm $arm --smoke || exit 1
done
if step $PY -m fac_tinyagent.e3_run --phase check-smoke --seed $S --smoke; then date > "$E3_SMOKE_DIR/SMOKE_OK"; echo SMOKE_PASSED; else echo SMOKE_FAILED; fi
echo "TOTAL $(( $(date +%s)-t0 ))s"
