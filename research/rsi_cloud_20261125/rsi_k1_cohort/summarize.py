"""Collapse synthetic fixture outcomes by release and method; no row-level results."""
from collections import Counter
import json,sys
d=json.load(sys.stdin)
for name,cell in d.items():
    cell["issue_count"]=len(next(iter(cell["result"].values())))
    cell["evidence_class"]="historical_regressions" if name.startswith("pandas-") else "historical_fix_companion"
    cell["result"]={method:dict(Counter(status for outcomes in groups.values() for status in outcomes)) for method,groups in cell["result"].items()}
print(json.dumps(d,indent=2,sort_keys=True))
