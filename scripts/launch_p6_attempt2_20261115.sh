#!/usr/bin/env bash
set -eu
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false HF_HUB_OFFLINE=1
setsid nohup .venv/bin/python -B scripts/run_p6_attempt2_20261115.py --phase queue >> runs_ext_p6_devplan_attempt2/logs/launcher.log 2>&1 < /dev/null &
supervisor=$!
printf 'SUPERVISOR_PID=%s\n' "$supervisor"
.venv/bin/python -B scripts/p6_attempt2_handshake_20261115.py "$supervisor"
