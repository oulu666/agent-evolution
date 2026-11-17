#!/usr/bin/env bash
# [ext-paper 2026-11-10] GPU smoke for a larger model on the original pipeline.
# Usage: bash scripts/run_smoke_ext.sh configs/ext/qwen3_1p7b_phase2_smoke.json runs_smoke_1p7b [order] [seed] [test_limit]
# Records whole-GPU memory (nvidia-smi, includes ~1.6GB Windows baseline) every 2s and wall time.
set -uo pipefail
cd "$(dirname "$0")/.."
CONFIG="$1"; OUT="$2"; ORDER="${3:-A}"; SEED="${4:-20261108}"; LIMIT="${5:-3}"
BUDGET="${SMOKE_BUDGET_SECONDS:-2400}"
mkdir -p "$OUT"
if pgrep -f "[f]ac_tinyagent\.|[e]val_general\.py" >/dev/null; then
  echo "GPU job already running, abort"; pgrep -af "[f]ac_tinyagent\.|[e]val_general\.py"; exit 3
fi
FREE_GB=$(df -BG --output=avail /mnt/c | tail -n 1 | tr -dc 0-9)
echo "C: free ${FREE_GB}GB"; [ "$FREE_GB" -ge 20 ] || { echo "disk < 20GB, abort"; exit 4; }
nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader | tee "$OUT/gpu_baseline.txt"
( while true; do nvidia-smi --query-gpu=timestamp,memory.used --format=csv,noheader >> "$OUT/gpu_mem_trace.csv"; sleep 2; done ) &
SAMPLER=$!
START=$(date +%s)
timeout "$BUDGET" .venv/bin/python -u -m fac_tinyagent.ext_sweep --config "$CONFIG" \
  --output-root "$OUT" --orders "$ORDER" --seeds "$SEED" --test-limit "$LIMIT"
RC=$?
END=$(date +%s)
if [ "$RC" = 124 ]; then
  echo "FULL SMOKE EXCEEDED ${BUDGET}s -> rerunning first training stage only"
  timeout "$BUDGET" .venv/bin/python -u -m fac_tinyagent.ext_sweep --config "$CONFIG" \
    --output-root "$OUT" --orders "$ORDER" --seeds "$SEED" --test-limit "$LIMIT" \
    --max-stages 1 --run-id-prefix stage1only_
  RC=$?; END=$(date +%s)
fi
kill "$SAMPLER" 2>/dev/null
PEAK=$(cut -d, -f2 "$OUT/gpu_mem_trace.csv" | tr -dc '0-9\n' | sort -n | tail -n 1)
echo "SMOKE_RC=$RC WALL_SECONDS=$((END-START)) GPU_MEM_PEAK_MIB(whole GPU)=$PEAK BASELINE=$(cat "$OUT/gpu_baseline.txt")" | tee "$OUT/smoke_summary.txt"
