"""Verify the frozen CCET comparisons and expose project and intervention strata."""
from pathlib import Path
import csv
import hashlib
import json
import sys
from collections import defaultdict

root=Path(__file__).resolve().parents[1]
out=root/"runs_ccet_20261125"
load=lambda p:json.loads(p.read_text(encoding="utf-8"))
for run in ("runs_egatv_pilot_20261125","runs_ccet_20261125"):
    for f,digest in load(root/run/"lock.json")["files"].items():
        assert hashlib.sha256((root/f).read_bytes()).hexdigest()==digest
rows=load(out/"decisions.json")
groups=defaultdict(dict)
for r in rows:
    key=tuple(r[k] for k in ("tool","version","altered","target","first","allowed","cost","protocol"))
    assert key not in groups[r["method"]]
    groups[r["method"]][key]=r
    assert r["success"]+r["defer"]+r["wrong"]==1
    assert len({p["id"] for p in r["checks"]})==len(r["checks"])
    assert r["calls"]==len(r["checks"])+int(not r["defer"])
    if r["protocol"]=="equal" and r["method"]!="oracle": assert r["calls"]==3
base=groups["legacy_cache"]
results=[]
for m,group in groups.items():
    assert base.keys()==group.keys()
    for regime in ("equal","adaptive"):
        for tool in ("all","packaging","tabulate"):
            for config in ("all","native","altered"):
                g=[(a,base[k]) for k,a in group.items() if a["protocol"]==regime and tool in ("all",a["tool"])
                   and config in ("all","altered" if a["altered"] else "native")]
                wins=sum(a["success"]>b["success"] for a,b in g)
                losses=sum(a["success"]<b["success"] for a,b in g)
                results.append(dict(regime=regime,project=tool,config=config,method=m,n=len(g),
                    wins=wins,losses=losses,ties=len(g)-wins-losses,
                    success=sum(a["success"] for a,b in g),wrong=sum(a["wrong"] for a,b in g),
                    defer=sum(a["defer"] for a,b in g),calls=sum(a["calls"] for a,b in g),
                    brier=sum((a["bad"]-a["p"])**2 for a,b in g)/len(g) if g[0][0]["p"] is not None else None))
with (out/"paired_strata.csv").open("w",newline="",encoding="utf8") as f:
    writer=csv.DictWriter(f,fieldnames=list(results[0]))
    writer.writeheader()
    writer.writerows(results)

# First-probe diagnostic. The label here is the tool's own semantic outcome,
# before any route mistake, fallback decision or selective abstention.
sys.path.insert(0,str(root/"research/ccet_20261125"))
from fixtures import menu
from run import training

model=training()
cells=defaultdict(list)
for r in groups["ccet"].values():
    if r["protocol"]!="equal":
        continue
    x=tuple(r["signature"])
    probe=menu(r["tool"],19)[r["first"]]
    check=r["checks"][0]
    assert check["id"]==r["first"]
    prior=model.prior_by_scope[x[0]]
    after=model.update(prior,model.likelihood("ccet",x,probe.signature),check["failed"])
    cells[x==probe.signature,not check["failed"]].append((r["primary"]!=r["gold"],prior,after))
with (out/"first_probe.csv").open("w",newline="",encoding="utf8") as f:
    w=csv.writer(f)
    w.writerow(("full_signature_match","probe_passed","contexts","semantic_target_errors","mean_prior","mean_after"))
    for cell,values in sorted(cells.items()):
        n=len(values)
        w.writerow((*cell,n,sum(v[0] for v in values),sum(v[1] for v in values)/n,sum(v[2] for v in values)/n))
