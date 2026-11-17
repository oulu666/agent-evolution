#!/bin/bash
set -u
cd "/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
export HF_ENDPOINT="https://hf-mirror.com"
date
echo "=== build cache ==="
/home/egret/venvs/fac-eval/bin/python scripts/build_mmlu_cache.py
echo "CACHE_RC=$?"
export HF_HUB_OFFLINE=1
export HF_DATASETS_OFFLINE=1
echo "=== mmlu base ==="
bash scripts/eval_general.sh --model /home/egret/models/Qwen3-0.6B --tasks mmlu --batch-size 16 --output runs_ext_eval/q06b_base_mmlu_full
echo "RC5=$?"
echo "=== mmlu adapter ==="
bash scripts/eval_general.sh --model /home/egret/models/Qwen3-0.6B --adapter runs_phase2/A_seed20261108/checkpoints/stage_04_calendar --tasks mmlu --batch-size 16 --output runs_ext_eval/q06b_A108_stage04_mmlu_full
echo "RC6=$?"
date