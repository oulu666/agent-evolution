#!/usr/bin/env bash
# Run inside WSL2 Ubuntu from the fac_tinyagent project root:
#   bash setup/setup_wsl.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== FAC-TinyAgent WSL setup =="
echo "project: $(pwd)"
python3 --version
nvidia-smi --query-gpu=name,memory.total,memory.used,memory.free,driver_version --format=csv,noheader || true
export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Run setup/bootstrap_wsl.sh first."
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  uv venv --python 3.12 .venv
fi
source .venv/bin/activate
uv pip install --upgrade pip
uv pip install torch transformers peft bitsandbytes accelerate sentencepiece
uv pip freeze > requirements.lock.txt
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"

python -m fac_tinyagent.run env --output environment_report.txt

cat <<'EOF'

Setup complete.
Activate the environment with:
  source .venv/bin/activate

Then:
  python -m fac_tinyagent.run gen-data
  python -m fac_tinyagent.run smoke
  python -m fac_tinyagent.run sequential

The first model load downloads Qwen/Qwen3-0.6B from Hugging Face.
If Hugging Face is unavailable, run:
  bash setup/download_model.sh
and use configs/local_full.json (model path /home/egret/models/Qwen3-0.6B).
EOF
