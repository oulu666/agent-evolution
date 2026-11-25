#!/usr/bin/env python3
import json, os, subprocess, sys, time
from pathlib import Path
os.environ.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUNBUFFERED="1", TZ="Asia/Shanghai")
ROOT = Path("/mnt/c/Users/Egret/Desktop/oulu/Agent Self-Evolution/fac_tinyagent")
sys.path.insert(0, str(ROOT))
from fac_tinyagent.p11_queue_20261118 import inspect
s = inspect({os.getpid()})
smi = subprocess.check_output(["nvidia-smi", "--query-gpu=enforced.power.limit,power.draw,memory.used,utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"], text=True).strip()
compute = subprocess.check_output(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader"], text=True).strip()
out = {
    "time": time.strftime("%F %T %z"),
    "inspect": s,
    "nvidia_smi_power_mem": smi,
    "compute_apps": compute,
}
path = ROOT / "_p11_fix_tmp" / "precheck_rerun.json"
path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
print(json.dumps(out, indent=2, ensure_ascii=False))
sys.exit(0 if s.get("safe") else 75)
