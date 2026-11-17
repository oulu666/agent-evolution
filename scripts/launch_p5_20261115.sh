#!/usr/bin/env bash
set -eu
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
export PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false HF_HUB_OFFLINE=1
# A sticky STOP flag is never removed by this launcher.
setsid nohup .venv/bin/python -B scripts/run_p5_20261115.py --phase queue >> runs_ext_p5_file_timing/logs/launcher.log 2>&1 < /dev/null &
printf 'SUPERVISOR_PID=%s\n' "$!"
