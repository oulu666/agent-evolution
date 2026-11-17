#!/usr/bin/env bash
set -e
sed -i 's/\r$//' scripts/run_p4_20261114.sh scripts/launch_p4_20261114.sh scripts/stop_p4.sh
.venv/bin/python -m fac_tinyagent.p4_forget_timing --phase build 2>&1 | tail -n 8
.venv/bin/python -m fac_tinyagent.p4_forget_timing --phase dry 2>&1 | tail -n 6
ls data_ext_p4_forget_timing data_ext_p4_forget_timing/plans | head -40
wc -l data_ext_p4_forget_timing/probe/list_tables_probe.jsonl
