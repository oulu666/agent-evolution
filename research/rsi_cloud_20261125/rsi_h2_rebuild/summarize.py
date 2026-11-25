"""Compact JSON run output; keep only workload-level totals/medians."""
import json, sys
d=json.load(sys.stdin)
d["python"]=d["python"].split()[0]
for cell in d["result"].values():
    cell.pop("seeds",None)
print(json.dumps(d,ensure_ascii=False,indent=2,sort_keys=True))
