#!/usr/bin/env bash
set -euo pipefail
DEST="/home/egret/models/Qwen3-0.6B"
mkdir -p "$DEST"
cd "$DEST"
for file in config.json generation_config.json merges.txt model.safetensors \
            tokenizer.json tokenizer_config.json vocab.json; do
  echo "downloading $file"
  curl -sSL --retry 3 -C - -o "$file" \
    "https://www.modelscope.cn/models/Qwen/Qwen3-0.6B/resolve/master/$file"
done
ls -lh
