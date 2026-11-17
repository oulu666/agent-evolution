#!/usr/bin/env bash
# [ext-paper 2026-11-10] Download Qwen3 models from ModelScope (Hugging Face CDN was unreliable).
# Generalises setup/download_model.sh (which stays unchanged, 0.6B only).
# Usage: bash setup/download_model_ext.sh Qwen3-1.7B [Qwen3-4B ...]
# Env:   MODELS_ROOT (default /home/egret/models)
# Resumable: existing files with matching size/sha256 are skipped; partial files resume with curl -C -.
set -euo pipefail
ROOT_DIR="${MODELS_ROOT:-/home/egret/models}"
[ "$#" -ge 1 ] || { echo "usage: $0 Qwen3-1.7B [Qwen3-4B ...]"; exit 2; }
for NAME in "$@"; do
  DEST="$ROOT_DIR/$NAME"
  mkdir -p "$DEST"
  echo "== $(date '+%F %T') $NAME -> $DEST"
  LIST_JSON="$DEST/.modelscope_files.json"
  curl -sSL --retry 5 -o "$LIST_JSON" \
    "https://www.modelscope.cn/api/v1/models/Qwen/$NAME/repo/files?Revision=master&Recursive=true"
  python3 - "$LIST_JSON" > "$DEST/.modelscope_files.tsv" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding="utf-8"))
for item in data["Data"]["Files"]:
    if item.get("Type") != "blob":
        continue
    path = item["Path"]
    if path.endswith(".md") or path in (".gitattributes",):
        continue
    print("%s\t%s\t%s" % (path, item.get("Size", 0), item.get("Sha256", "") or ""))
PY
  while IFS=$'\t' read -r FILE SIZE SHA; do
    TARGET="$DEST/$FILE"
    mkdir -p "$(dirname "$TARGET")"
    OK=0
    for ATTEMPT in 1 2 3 4 5 6 7 8 9 10; do
      if [ -f "$TARGET" ] && [ "$(stat -c %s "$TARGET")" = "$SIZE" ]; then
        if [ -z "$SHA" ] || [ "$(sha256sum "$TARGET" | cut -d' ' -f1)" = "$SHA" ]; then
          OK=1; break
        fi
        echo "sha256 mismatch on $FILE, deleting and retrying"; rm -f "$TARGET"
      fi
      # odd attempts: ModelScope; even attempts: hf-mirror.com (identical LFS objects, sha256-checked)
      if [ $((ATTEMPT % 2)) = 1 ]; then
        URL="https://www.modelscope.cn/models/Qwen/$NAME/resolve/master/$FILE"
      else
        URL="https://hf-mirror.com/Qwen/$NAME/resolve/main/$FILE"
      fi
      echo "$(date '+%T') attempt $ATTEMPT $FILE ($SIZE bytes) <- $URL"
      curl -sSL --connect-timeout 30 --speed-limit 10240 --speed-time 60 \
        -C - -o "$TARGET" "$URL" || echo "curl exit $? (will resume)"
      sleep 3
    done
    [ "$OK" = 1 ] || { echo "FAILED $FILE after retries"; exit 1; }
    echo "ok $FILE ($(stat -c %s "$TARGET") bytes${SHA:+, sha256 verified})"
  done < "$DEST/.modelscope_files.tsv"
  ls -lh "$DEST"
  du -sh "$DEST"
  echo "== DONE $NAME"
done
