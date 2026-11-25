"""Read-only scoring of frozen observations and labelled runtime-recovery results."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sample import HERE, OUT, save


def load(n):
    return json.loads((OUT/n).read_text())


def main():
    for n,h in load("lock.json").items():
        p=HERE/n if (HERE/n).is_file() else OUT/n
        assert hashlib.sha256(p.read_bytes()).hexdigest()==h
    samples, checks, tasks=load("sample.json"),load("checks.json"),load("tasks.json")
    obs=load("observations.json")
    for k,v in load("compatibility_observations.json").items():
        assert all("import_error" in item for item in obs[k].values())
        obs[k]=v
    counts,contracts,actions,paired=Counter(),set(),{},{}
    for s in samples:
        k=s["id"]
        records=checks[k]
        for r in records:
            counts[r["evidence"]]+=1
            contracts.add((s["project"],r["evidence"],r["kind"]))
        paired[k]={}
        for typ in ("literal","extra","property"):
            def flags(arm):
                v=obs[k][arm]
                if typ=="property":
                    return {json.dumps(r["x"]):r["passed"] for r in v["properties"]}
                return {i:r["passed"] for i,r in enumerate(v["assertions"]) if (records[i]["kind"]=="exact")==(typ=="literal")}
            x,y=flags("parent"),flags("rev")
            assert set(x)==set(y)
            paired[k][typ]=dict(Counter(f"{int(ok)}->{int(y[i])}" for i,ok in x.items()))
        for arm,content in obs[k].items():
            for r in content["deliveries"]:
                gold=tasks[s["project"]][r["i"]][2]
                status="defer" if not r["deliver"] else "ok" if r["v"]==["ok",gold] else "wrong"
                assert 1<=r["calls"]<=2
                c=actions.setdefault(r["method"],Counter())
                c[status]+=1
                c["calls"]+=r["calls"]
                c["ns"]+=r["ns"]
    z=dict(evidence=counts,paired=paired,deliveries=actions)
    save("summary.json",z)
    print(json.dumps(z,indent=1))


if __name__=="__main__":
    main()
