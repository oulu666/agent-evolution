#!/usr/bin/env bash
.venv/bin/python - <<'PY'
import json,glob,os
for f in sorted(glob.glob("runs_ext_p4_forget_timing/evaluation/*/lt_probe/results.jsonl")):
    rs=[json.loads(l) for l in open(f)]
    ro=[r for r in rs if "readonly" in str(r.get("template_id",""))+str(r.get("episode_id",""))]
    keys=[k for k in rs[0] if "success" in k or "joint" in k.lower() or k in ("final_correct","correct")]
    print(f, len(rs), keys[:6])
    if rs: print("  sample", {k:rs[-1].get(k) for k in keys[:6]}, str(rs[-1].get("prediction", rs[-1].get("generated","")))[:200])
hits=[]
for pat in ["runs_ext_*/**/*prefix*","runs_ext_*/**/*step80*","runs_ext_*/**/*midpoint*"]:
    hits+=glob.glob(pat, recursive=True)
print("PREFIX-LIKE", sorted(set(h for h in hits if os.path.isdir(h)))[:30])
PY
