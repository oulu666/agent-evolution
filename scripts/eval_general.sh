#!/usr/bin/env bash
# [ext-paper 2026-11-10] General-ability eval (lm-eval) with the fac-eval venv.
# Usage (from project root, inside WSL):
#   bash scripts/eval_general.sh --model /home/egret/models/Qwen3-0.6B \
#        [--adapter runs_phase2/A_seed20261108/checkpoints/stage_04_calendar] \
#        --tasks arc_easy,ifeval --limit 100 --output runs_ext_eval/<name> [--chat-template]
# Adapters are only read. Refuses to start if another python process holds the GPU.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${FAC_EVAL_PY:-/home/egret/venvs/fac-eval/bin/python}"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
export TOKENIZERS_PARALLELISM=false
# Only treat actual Python eval/training jobs as GPU holders.
# Matching the filename in an unrelated shell command line (e.g. a launcher
# that mentions scripts/eval_general.py) must not block the real job.
if pgrep -f "[p]ython.*scripts/eval_general[.]py|[p]ython.*-m fac_tinyagent[.]" >/dev/null 2>&1; then
  echo "another fac_tinyagent/eval_general process is running; refusing to share the GPU" >&2
  pgrep -af "[p]ython.*scripts/eval_general[.]py|[p]ython.*-m fac_tinyagent[.]" >&2 || true
  exit 3
fi
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader || true
OUT=""
for ((i=1; i<=$#; i++)); do
  if [ "${!i}" = "--output" ]; then j=$((i+1)); OUT="${!j}"; fi
done
[ -n "$OUT" ] || { echo "--output is required" >&2; exit 2; }
mkdir -p "$OUT"
"$PY" -u scripts/eval_general.py "$@" 2>&1 | tee "$OUT/eval.log"
