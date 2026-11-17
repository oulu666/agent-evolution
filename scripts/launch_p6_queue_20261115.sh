#!/usr/bin/env bash
set -eu
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false HF_HUB_OFFLINE=1
# Stage 2 only: requires 9 plans frozen after calibration; guarded serial production queue.
setsid nohup .venv/bin/python -B scripts/run_p6_queue_20261115.py --phase queue >> runs_ext_p6_devplan/logs/launcher.log 2>&1 < /dev/null &
supervisor=$!
printf 'SUPERVISOR_PID=%s\n' "$supervisor"
# Handshake keeps the WSL caller alive until the supervisor initializes or visibly fails.
.venv/bin/python -B scripts/p6_launch_handshake_20261115.py "$supervisor"
