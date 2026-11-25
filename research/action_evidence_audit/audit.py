"""Optimistic information bounds and policies fixed before observation of the new releases."""
from collections import Counter,defaultdict
from pathlib import Path
import csv
import json
import statistics
import time

from measure import OUT,SPEC,fingerprints,load
from workloads import corpus,nearest

ROUTES=("P","B")


def csvfile(name,rows):
    with (OUT/name).open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def select(rows):
    # Primary objective correct deliveries; then fewer wrong deliveries, then lower measured service time.
    if not rows: return "P"
    return max(("P","B","D"),key=lambda a: (
        sum(r[a] for r in rows) if a!="D" else 0,
        -sum(not r[a] for r in rows) if a!="D" else 0,
        -sum(r["t"+a] for r in rows) if a!="D" else 0))


def groupkey(r,view):
    key=(r["project"],r["family"])
    if "id" in view: key+=(r["probe"],)
    if "bits" in view: key+=(r["probeP"],r["probeB"])
    return key


def main():
    assert fingerprints()==load(OUT/"lock.json")["files"]
    cases=corpus(load(SPEC))
    bank=[r for r in cases if r["role"]=="probe"]
    ds={}
    for ver in ("old","new"):
        readings=load(OUT/(ver+".json"))["records"]
        records=[]
        for r in cases:
            if r["role"]=="probe": continue
            q=nearest(r,bank)
            rr=readings[r["id"]]
            p=readings[q]
            obj=dict(project=r["project"],family=r["family"],id=r["id"],role=r["role"],probe=q)
            for a in ROUTES:
                obj[a]=rr["actual"][a][0]
                obj["t"+a]=statistics.median(rr["time"][a])
                obj["probe"+a]=p["actual"][a][0]
                obj["q"+a]=statistics.median([u+v for u,v in zip(p["time"][a],p["judge"][a])])
            records.append(obj)
        ds[ver]=records
    dev=[r for r in ds["old"] if r["role"]=="development"]
    test=[r for r in ds["new"] if r["role"]=="test"]
    assert {r["id"] for r in dev}.isdisjoint(r["id"] for r in test)
    policies={}
    for view in ("family","id","bits","id_bits"):
        groups=defaultdict(list)
        for r in dev: groups[groupkey(r,view)].append(r)
        policies[view]={k:select(v) for k,v in groups.items()}
    outcomes=[]
    bounds=[]
    held=[]
    for project in ("Markdown","YAML"):
        sample=[r for r in test if r["project"]==project]
        c=Counter((r["P"],r["B"]) for r in sample)
        bounds.append(dict(project=project,n=len(sample),both=c[True,True],primary_only=c[True,False],
                    backup_only=c[False,True],neither=c[False,False],oracle_success=len(sample)-c[False,False],
                    primary_us=sum(r["tP"] for r in sample),backup_us=sum(r["tB"] for r in sample),
                    fastest_correct_or_defer_us=sum(min((r["t"+a] for a in ROUTES if r[a]),default=0) for r in sample)))
        for view in ("family","id","bits","id_bits"):
            groups=defaultdict(list)
            for r in sample: groups[groupkey(r,view)].append(r)
            rights=sum(max(sum(r["P"] for r in g),sum(r["B"] for r in g)) for g in groups.values())
            safe=sum(len(g) for g in groups.values() if any(all(r[a] for r in g) for a in ROUTES))
            held.append(dict(project=project,visible=view,buckets=len(groups),success_ceiling=rights,
                             zero_wrong_commit_ceiling=safe))
        for method in ("primary","backup","family","id","P_probe","B_probe","bits","id_bits"):
            cache=set()
            counter=Counter()
            trace=[]
            for r in sample:
                t=time.perf_counter_ns()
                probes=("P","B") if "bits" in method else (("P",) if method=="P_probe" else (("B",) if method=="B_probe" else ()))
                # Include the cost of online neighbour selection whenever this method needs a probe identity.
                if probes or "id" in method:
                    target=case_lookup[r["id"]]
                    q=nearest(target,bank)
                    assert q==r["probe"]
                if method=="primary": a="P"
                elif method=="backup": a="B"
                elif method=="P_probe": a="P" if r["probeP"] else "B"
                elif method=="B_probe": a="B" if r["probeB"] else "P"
                else: a=policies[method].get(groupkey(r,method),policies["family"].get(groupkey(r,"family"),"P"))
                control=(time.perf_counter_ns()-t)/1000
                counter["control_us"]+=control
                for j in probes:
                    counter["cold_probe_us"]+=r["q"+j]
                    counter["probes"]+=1
                    item=(r["probe"],j)
                    if item not in cache:
                        cache.add(item)
                        counter["shared_probe_us"]+=r["q"+j]
                counter["delivery_us"]+=r["t"+a] if a!="D" else 0
                counter["correct"]+=int(a!="D" and r[a])
                counter["wrong"]+=int(a!="D" and not r[a])
                counter["defer"]+=int(a=="D")
                trace.append(dict(id=r["id"],project=project,method=method,action=a,
                                  success=a!="D" and r[a],probe=r["probe"] if probes else None))
            n=len(sample)
            outcomes.append(dict(project=project,method=method,n=n,correct=counter["correct"],wrong=counter["wrong"],
                defer=counter["defer"],cold_probes=counter["probes"],cached_probes=len(cache),
                cold_calls=n-counter["defer"]+counter["probes"],cached_calls=n-counter["defer"]+len(cache),
                control_us=counter["control_us"],delivery_us=counter["delivery_us"],
                cold_total_us=counter["control_us"]+counter["delivery_us"]+counter["cold_probe_us"],
                cached_total_us=counter["control_us"]+counter["delivery_us"]+counter["shared_probe_us"]))
            trajectories.extend(trace)
    csvfile("action_space.csv",bounds)
    csvfile("evidence_ceiling.csv",held)
    csvfile("deployment.csv",outcomes)
    csvfile("heldout_inputs.csv",test)
    csvfile("decisions.csv",trajectories)
    print("dev",len(dev),"test",len(test),"bank",len(bank),bounds,held)


if __name__=="__main__":
    trajectories=[]
    case_lookup={r["id"]:r for r in corpus(load(SPEC))}
    main()

