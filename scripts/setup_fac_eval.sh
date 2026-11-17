#!/usr/bin/env bash
# [ext-paper 2026-11-10] Build the general-ability evaluation venv on the WSL native disk.
# Does NOT touch the project .venv. Pins torch/transformers/peft/bitsandbytes/accelerate to .venv versions.
# Usage: bash scripts/setup_fac_eval.sh
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
VENV="${FAC_EVAL_VENV:-/home/egret/venvs/fac-eval}"
PY="$VENV/bin/python"
export UV_DEFAULT_INDEX="${UV_DEFAULT_INDEX:-https://pypi.tuna.tsinghua.edu.cn/simple}"
export UV_HTTP_TIMEOUT=600
mkdir -p "$(dirname "$VENV")"
[ -x "$PY" ] || uv venv --python 3.12 "$VENV" || exit 1
CONS="$VENV/constraints-core.txt"
cat > "$CONS" <<'C'
torch==2.15.0
transformers==5.22.2
peft==0.21.2
bitsandbytes==0.50.2
accelerate==1.15.0
C
echo "== step1 core $(date '+%T')"
uv pip install --python "$PY" -c "$CONS" torch transformers peft bitsandbytes accelerate sentencepiece || { echo "STEP1 FAILED"; exit 1; }
echo "== step2 lm-eval[ifeval] $(date '+%T')"
if ! uv pip install --python "$PY" -c "$CONS" "lm-eval[ifeval]"; then
  echo "STEP2 extras failed; trying lm-eval + ifeval deps explicitly"
  uv pip install --python "$PY" -c "$CONS" lm-eval langdetect immutabledict nltk || echo "STEP2 FAILED"
fi
echo "== step3 bfcl-eval (separate venv) $(date '+%T')"
# bfcl-eval 2026.3.23 pins numpy==1.26.4, which breaks pyarrow/datasets needed by lm-eval,
# so BFCL lives in its own venv (torch pinned to the same version to reuse the uv cache).
BFCL_VENV="${BFCL_VENV:-/home/egret/venvs/bfcl-eval}"
[ -x "$BFCL_VENV/bin/python" ] || uv venv --python 3.12 "$BFCL_VENV"
printf 'torch==2.15.0\n' > "$BFCL_VENV/constraints.txt"
# soundfile: needed by qwen_agent (imported by the bfcl CLI) but not declared by bfcl-eval
uv pip install --python "$BFCL_VENV/bin/python" -c "$BFCL_VENV/constraints.txt" bfcl-eval soundfile || echo "STEP3 FAILED"
uv pip freeze --python "$BFCL_VENV/bin/python" > "$BFCL_VENV/requirements.freeze.txt"
echo "== step4 nltk punkt for ifeval $(date '+%T')"
# nltk.download('punkt_tab') fails here with "Security Violation"; unpack the official zip manually.
if ! "$PY" -c "import nltk; nltk.data.find('tokenizers/punkt_tab/english/')" 2>/dev/null; then
  mkdir -p "$HOME/nltk_data/tokenizers"
  curl -sSL --retry 3 -o /tmp/punkt_tab.zip \
    https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/tokenizers/punkt_tab.zip
  (cd "$HOME/nltk_data/tokenizers" && python3 -m zipfile -e /tmp/punkt_tab.zip .)
fi
"$PY" -c "import nltk; print(nltk.data.find('tokenizers/punkt_tab/english/'))" || echo "punkt_tab missing: ifeval scoring will fail"
uv pip freeze --python "$PY" > "$VENV/requirements.freeze.txt"
"$PY" - <<'P'
import importlib
for name in ("torch", "transformers", "peft", "bitsandbytes", "accelerate", "numpy", "lm_eval", "datasets"):
    try:
        mod = importlib.import_module(name)
        print(name, getattr(mod, "__version__", "?"))
    except Exception as exc:
        print(name, "IMPORT FAILED", type(exc).__name__, exc)
import torch
print("cuda", torch.cuda.is_available(), torch.version.cuda)
P
echo "== SETUP DONE $(date '+%T')"
