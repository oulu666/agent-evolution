"""Independent tally over saved observations; no database replay or retuning."""
from collections import Counter
from pathlib import Path
import csv
import json

out = Path(__file__).resolve().parents[1] / "runs_dynamic_snapshot_20261125"
streams = json.loads((out/"streams.json").read_bytes())
with (out/"deployment.csv").open(encoding="utf-8-sig") as f:
    deployment = {(r["project"],r["period"],r["method"]):r for r in csv.DictReader(f)}
checked = []
for project,events in streams.items():
    run = json.loads((out/(project+".json")).read_bytes())
    counts = Counter()
    idx = 0
    for r in run["requests"]:
        cutoff = 1735689600+r["day"]*86400+r["hour"]*3600
        while idx<len(events) and events[idx][0]<=cutoff:
            counts[events[idx][2]]+=1
            idx+=1
        top=sorted(counts.items(),key=lambda x:(-x[1],x[0]))[:3]
        gold={"total":[[idx]],"authors":[[len(counts)]],"top3":[list(x) for x in top]}[r["task"]]
        assert r["probe"]==idx and gold==r["gold"]
        assert all(r["out"][m]==gold for m in ("lazy_gate","summary","publish_memo","live"))
    for period in ("year","H1","H2"):
        d={m:r for (k,h,m),r in deployment.items() if k==project and h==period}
        model=d["lazy_gate"]
        for permission,methods in (("read_only",("primary","backup","newest","live","public_rule")),
                                   ("writer_controlled",("primary","backup","newest","live","public_rule","publish_memo","summary"))):
            base=min((d[m] for m in methods if int(d[m]["wrong"])==int(model["wrong"]) and int(d[m]["success"])==int(model["success"])),
                     key=lambda x:float(x["attributable_ms"]))
            saved=float(base["attributable_ms"])-float(model["attributable_ms"])
            extra=int(model["service_calls"])-int(base["service_calls"])
            checked.append(dict(project=project,period=period,permission=permission,
                zero_probe_baseline=base["method"],saved_ms=saved,relative_saving=saved/float(base["attributable_ms"]),
                extra_calls=extra,break_even_extra_us=saved*1000/extra if saved>0 and extra>0 else None))
with (out/"cost_gate.csv").open("w",newline="",encoding="utf-8-sig") as f:
    w=csv.DictWriter(f,fieldnames=list(checked[0]))
    w.writeheader()
    w.writerows(checked)
