"""Apply frozen gate definitions. Summaries use correct/wrong/defer counts and measured time."""
from collections import Counter,defaultdict
import csv
import json
import statistics
from pathlib import Path
from study import OUT,POLICIES,hashes,load


def csvout(name,rows):
    with (OUT/name).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def valid(r,p):
    return r["out"][p]==r["gold"]


def key(r):
    # UTC day 0 = Wednesday. All features are available without reading the live database.
    return (r["task"],r["hour"],(r["day"]+2)%7>=5,r["public_heads"][0]==r["public_heads"][1])


def fit(dev):
    groups=defaultdict(list)
    for r in dev: groups[key(r)].append(r)
    model={}
    for k,bucket in groups.items():
        opts=("newest","live")
        model[k]=min(opts,key=lambda p:(sum(not valid(r,p) for r in bucket),sum(r["ns"][p] for r in bucket)))
    return model


def run():
    assert hashes()==load("lock.json")["hashes"]
    train=load("pluggy.json")
    model=fit(train["requests"])
    scores=[]
    oracle=[]
    signals=[]
    for project,d in (("pluggy",train),("click",load("click.json"))):
        for half,lo,hi in (("year",0,365),("H1",0,181),("H2",181,365)):
            cases=[r for r in d["requests"] if lo<=r["day"]<hi]
            start=1735689600
            w=[r for r in d["write"] if lo<=int((r["when"]-start)//86400)<hi]
            bootstrap=[r for r in d["refresh"] if lo<=r["day"]<hi or (lo==0 and r["day"]==-1)]
            base_write=sum(r["ns"][0] for r in w)
            indexed_write=sum(r["ns"][1] for r in w)
            bins=Counter((valid(r,"primary"),valid(r,"backup")) for r in cases)
            oracle.append(dict(project=project,period=half,tasks=len(cases),commits=len(w),both=bins[True,True],
                  primary_only=bins[True,False],backup_only=bins[False,True],neither=bins[False,False],
                  cache_oracle_success=len(cases)-bins[False,False],full_oracle_success=len(cases),
                  init_base_ms=d["seed_ns"][0]/1e6,init_summary_ms=d["seed_ns"][1]/1e6))
            for method in (*POLICIES,"public_rule"):
                s=Counter()
                uses=set()
                for r in cases:
                    if method=="public_rule":
                        from time import perf_counter_ns
                        tick=perf_counter_ns()
                        action=model.get(key(r),"live")
                        dispatch=perf_counter_ns()-tick
                    else: action=method;dispatch=0
                    s["time"]+=r["ns"][action]+dispatch
                    s["success"]+=valid(r,action)
                    gate=action in ("head_gate","fused_gate","lazy_gate")
                    only_head=action in ("fused_gate","lazy_gate") and r["task"]=="total"
                    s["probe"]+=gate and not only_head
                    s["calls"]+=1+int(gate and not only_head)
                    if action in ("newest","head_gate","public_rule") or (action=="fused_gate" and not only_head):
                        uses.update((0,1))
                    elif action=="primary":uses.add(0)
                    elif action=="backup":uses.add(1)
                refresh=sum(v["ns"] for v in bootstrap if v["slot"] in uses)
                write=indexed_write if method=="summary" else base_write
                if method=="publish_memo": write+=sum(v["notification_ns"] for v in w)
                scores.append(dict(project=project,period=half,method=method,n=len(cases),success=s["success"],
                     wrong=len(cases)-s["success"],defer=0,service_calls=s["calls"],extra_probes=s["probe"],
                     read_ms=s["time"]/1e6,refresh_ms=refresh/1e6,write_ms=write/1e6,
                     attributable_ms=(s["time"]+refresh+max(0,write-base_write))/1e6,
                     whole_ms=(s["time"]+refresh+write)/1e6))
        for task in ("total","authors","top3"):
            cases=d["paired"]
            # A before/after pair shares both cache heads, logical time, task and probe identity.
            public=sum(max(int(r["before"]["correct"][task])+int(r["after"]["correct"][task]),
                           int(not r["before"]["correct"][task])+int(not r["after"]["correct"][task])) for r in cases)
            feedback=0
            for r in cases:
                bucket=defaultdict(list)
                for moment in ("before","after"):
                    v=r[moment]
                    bucket[v["fresh"]].append(v["correct"][task])
                feedback+=sum(max(sum(z),len(z)-sum(z)) for z in bucket.values())
            signals.append(dict(project=project,task=task,pairs=len(cases),observations=2*len(cases),
                raw_head_changes=sum(r["before"]["response"]!=r["after"]["response"] for r in cases),
                freshness_changes=sum(r["before"]["fresh"]!=r["after"]["fresh"] for r in cases),
                reusable_cache_label_changes=sum(r["before"]["correct"][task]!=r["after"]["correct"][task] for r in cases),
                public_pair_ceiling=public,with_freshness_pair_ceiling=feedback))
    csvout("action_space.csv",oracle)
    csvout("deployment.csv",scores)
    csvout("feedback.csv",signals)
    print("Rows:",len(scores),len(oracle),len(signals))


if __name__=="__main__":run()

