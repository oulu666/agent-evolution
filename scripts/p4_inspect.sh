#!/usr/bin/env bash
.venv/bin/python - <<'PY'
import json,glob
for r in open("data_phase2/database/test.jsonl"):
    r=json.loads(r)
    if "db_list_tables_test" in r["episode_id"]: print("TEST", r["episode_id"], r["prompt"])
for f in sorted(glob.glob("runs_ext_p4_forget_timing/evaluation/*/lt_probe/*")):
    print(f)
PY
rg -l "list_tables" runs_ext_e4 runs_ext_p3_count_timing 2>/dev/null | rg -i "prefix|step80|midpoint" | head -20
