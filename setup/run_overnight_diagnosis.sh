#!/usr/bin/env bash
set -euo pipefail
diagnosis_log=$1
shift
exec .venv/bin/python -u -m fac_tinyagent.overnight_diagnosis "$@" > "$diagnosis_log" 2>&1
