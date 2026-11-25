#!/usr/bin/env bash
set -euo pipefail
export TZ=Asia/Shanghai
ROOT="/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent"
cd "$ROOT"
SRC="runs_ext_p11_eaar_v1"
DST="runs_ext_p11_eaar_v1_failed_20261118_025333"
if [[ ! -d "$SRC" ]]; then
  echo "missing $SRC" >&2
  exit 1
fi
if [[ -d "$DST" ]]; then
  echo "archive dest already exists: $DST" >&2
  exit 1
fi
if [[ -f "$SRC/runtime_manifest.json" && -f "$SRC/ERROR.json" ]]; then
  mv "$SRC" "$DST"
else
  echo "refuse archive: expected failed-run markers missing" >&2
  exit 1
fi
echo "archived $SRC -> $DST"
ls -la "$DST"
test ! -e "$SRC"
test -f "$DST/ERROR.json"
python3 - <<'PY2'
import hashlib, pathlib
p=pathlib.Path("/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent/runs_ext_e4/prefixes/A_seed20261108/training_state.pt")
h=hashlib.sha256(p.read_bytes()).hexdigest()
print("prefix_state_sha256", h)
assert h=="5702cc7ef0e9b9dec5c4025b1b593d0a497088cb17dbdfa840b4353f7efa86d9", h
PY2
