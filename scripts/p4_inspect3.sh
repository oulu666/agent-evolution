#!/usr/bin/env bash
.venv/bin/python - <<'PY'
import json,glob
for f in sorted(glob.glob("runs_ext_p4_forget_timing/evaluation/*/lt_probe/results.jsonl")):
    rs=[json.loads(l) for l in open(f)]
    ro=[r for r in rs if "read-only" in json.dumps(r.get("prompt",""))]
    print(f.split("/")[2], "n",len(rs),"joint",sum(r["joint_success"] for r in rs),"final",sum(r["final_correct"] for r in rs),"exec",sum(r["execution_success"] for r in rs), "| readonly n",len(ro),"joint",sum(r["joint_success"] for r in ro))
    bad=[r for r in rs if not r["joint_success"]]
    if bad:
        b=bad[0]; print("   keys", [k for k in b.keys()][:40])
        for k in ("predicted_tool","tool_name","predicted_arguments","pred_tool","failure_reason","error_type","tool_correct","argument_correct","trajectory"):
            if k in b: print("   ",k,str(b[k])[:300])
PY
