from datetime import datetime, timezone, date
from pathlib import Path
from tempfile import TemporaryDirectory
import csv
import hashlib
import json
import platform
import statistics
import subprocess
import sys
import time
from urllib.request import urlopen

from fixtures import VERSIONS, execute, menu
from model import EPS, MODES, Transfer, plan, signature, terminal

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OUT=ROOT/"runs_ccet_20261125"
PREV=HERE.parent/"egatv_pilot"
sys.path.insert(0,str(PREV))
from policy import choose as legacy, Evidence
from experiment import development
ARCHIVE=ROOT/"runs_upstream_functional_20261124/paired_releases.json"
PAST=ROOT/"runs_egatv_pilot_20261125/decisions.json"
FILES=[*sorted(HERE.glob("*.py")),HERE/"protocol.md",ARCHIVE,PAST,PREV/"policy.py",PREV/"experiment.py",PREV/"tasks.py",
       HERE.parent/"issre_reviewer_study/reference.json",ROOT/"runs_ext_p11_eaar_v1/branches/A_seed20261108_eaar_v1/checkpoint/adapter_model.safetensors"]
METHODS=("legacy_cache",*MODES,"fallback_first","oracle")


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(file,data):
    (OUT/file).write_text(json.dumps(data,ensure_ascii=False,indent=1),encoding="utf8")


def seal():
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in FILES}


def training():
    archive=read(ARCHIVE)
    old=read(PAST)
    datasets=[]
    for tool in ("week","duration"):
        worlds=[]
        for side in ("before","after"):
            rec=archive[tool][side]
            labels={r["input"]:r["actual"]!=r["expected"] for r in rec["rows"]}
            for r in old:
                if r["tool"]==tool and r["version"]==rec["version"] and r["method"]=="direct":
                    labels[r["value"]]=r["wrong"]
            worlds.append([(signature(tool,x),bool(bad)) for x,bad in labels.items()])
        datasets.append(worlds)
    return Transfer(*datasets)


def baseline(x,features,first,choices,observe,allowed,cost,forced,conf,library):
    # Unchanged EGATV first-round planner with a result memo in observe().
    bad=observe(first)
    prior_check=Evidence(True,True,features[first][0],not bad)
    seen=[]
    def probe(scope):
        j=choices[scope]
        failed=observe(j)
        seen.append(j)
        return Evidence(True,True,scope,not failed)
    action=legacy("generic_risk",x[0],prior_check,probe,library,conf,cost,allowed)
    if forced and not any(j!=first for j in seen):
        extra=next(j for j in reversed(choices) if j!=first)
        observe(extra)
        seen.append(extra)
    weights=[]
    for w in library["worlds"]:
        obs=lambda q:.95 if w[q] else .05
        like=(2+obs(x[0])+obs(1-x[0]))/4
        weight=1-like if bad else like
        for j in seen:
            p=obs(features[j][0])
            weight*=1-p if observe(j) else p
        weights.append(weight)
    risk=EPS+(1-2*EPS)*sum(a*(not w[x[0]]) for a,w in zip(weights,library["worlds"]))/sum(weights)
    if forced:
        action=terminal(risk,cost,allowed,conf)[1]
    return action,risk


def safely(tool,item,altered,alt):
    try:
        return execute(tool,item.args,altered,alt)
    except (TypeError, ValueError, KeyError, IndexError, AttributeError) as e:
        return {"exception":type(e).__name__,"message":str(e)[:150]}


def worker(tool,version,wheel):
    sys.path.insert(0,wheel)
    package=__import__(tool)
    assert package.__version__==version and str(package.__file__).startswith(wheel)
    model=training()
    library=development()
    proposals=[r for r in read(OUT/"routing.json")["rows"] if r["tool"]==tool]
    targets=[v for n in (3,7,11) for v in menu(tool,n)]
    probes=menu(tool,19)
    features=[p.signature for p in probes]
    rows=[]
    for altered in (False,True):
        for i,target in enumerate(targets):
            # Only evaluation and the offline oracle see either counterfactual terminal outcome.
            proposal=proposals[i]
            assert proposal["index"]==i
            route_ok=proposal["picked"]==tool
            primary=safely(tool,target,altered,False)
            alt=safely(tool,target,altered,True)
            bad=not route_ok or primary!=target.expected
            alt_ok=route_ok and alt==target.expected
            choices=(i%2,2+(i+i//6)%4)
            for first in dict.fromkeys((*choices, (choices[1]-1)%4+2)):
                for protocol,allowed,cost in (("equal",True,1),("adaptive",True,1+3*(i//6%2)),("adaptive",False,1+3*(i//6%2))):
                    for m in METHODS:
                        cache={}
                        probe_ns=0
                        def observe(j):
                            nonlocal probe_ns
                            if j not in cache:
                                t=time.perf_counter_ns()
                                result=safely(tool,probes[j],altered,False)
                                cache[j]=dict(id=j,result=result,failed=result!=probes[j].expected)
                                probe_ns+=time.perf_counter_ns()-t
                            return cache[j]["failed"]
                        observe(first)
                        start=time.perf_counter_ns()
                        initial_ns=probe_ns
                        args=(allowed,cost,protocol=="equal",proposal["confidence"])
                        if m in MODES:
                            act,risk=plan(model,m,target.signature,features,first,choices,observe,*args)
                        elif m=="legacy_cache":
                            act,risk=baseline(target.signature,features,first,choices,observe,*args,library)
                        else:
                            if protocol=="equal":
                                observe(next(j for j in choices if j!=first))
                            risk=None
                            if m=="fallback_first": act="fallback" if allowed else "primary"
                            else: act="primary" if not bad else ("fallback" if allowed and alt_ok else "defer")
                        runtime=time.perf_counter_ns()-start-(probe_ns-initial_ns)
                        end=time.perf_counter_ns()
                        value=None if act=="defer" else (safely(tool,target,altered,act=="fallback") if route_ok else {"error":"wrong route"})
                        terminal_ns=time.perf_counter_ns()-end
                        success=act!="defer" and value==target.expected
                        if act!="defer":
                            assert success==(alt_ok if act=="fallback" else not bad)
                        assert len(cache)<=2
                        if protocol=="equal" and m!="oracle": assert len(cache)==2 and act!="defer"
                        rows.append(dict(tool=tool,version=version,altered=altered,target=i,args=target.args,
                            signature=target.signature,gold=target.expected,primary=primary,alternate=alt,bad=bad,
                            protocol=protocol,allowed=allowed,cost=cost,first=first,choices=choices,method=m,
                            checks=list(cache.values()),p=None if risk is None else 1-proposal["confidence"]*(1-risk),
                            action=act,actual=value,success=success,wrong=not success and act!="defer",defer=act=="defer",
                            calls=len(cache)+int(act!="defer"),policy_us=runtime/1000,tool_us=(probe_ns+terminal_ns)/1000))
    print(json.dumps(rows,ensure_ascii=True))


def summarize(rows):
    summary=[]
    for k in ("equal","adaptive"):
        for m in METHODS:
            g=[r for r in rows if r["protocol"]==k and r["method"]==m]
            p=[r for r in g if r["p"] is not None]
            brier=sum((r["bad"]-r["p"])**2 for r in p)/len(p) if p else None
            ece=0.
            for bin_id in range(5):
                bucket=[r for r in p if min(4,int(5*r["p"]))==bin_id]
                ece+=abs(sum(r["bad"]-r["p"] for r in bucket))/max(1,len(p))
            summary.append(dict(protocol=k,method=m,n=len(g),success=sum(r["success"] for r in g),wrong=sum(r["wrong"] for r in g),
                 defer=sum(r["defer"] for r in g),calls=sum(r["calls"] for r in g),fallback=sum(r["action"]=="fallback" for r in g),
                 brier=brier,ece=ece if p else None,decision_us=statistics.median(r["policy_us"] for r in g),
                 tool_us=statistics.median(r["tool_us"] for r in g)))
    return summary


def run():
    lock=read(OUT/"lock.json")
    assert seal()==lock["files"]
    rows=[]
    for name,ref in lock["releases"].items():
        tool,version=name.split()
        with TemporaryDirectory() as tmp:
            path=Path(tmp)/ref["filename"]
            with urlopen(ref["url"],timeout=45) as r: path.write_bytes(r.read())
            assert hashlib.sha256(path.read_bytes()).hexdigest()==ref["sha256"]
            result=subprocess.check_output([sys.executable,str(Path(__file__).resolve()),"worker",tool,version,str(path)],text=True)
            rows.extend(json.loads(result))
    save("decisions.json",rows)
    summary=summarize(rows)
    save("summary.json",summary)
    with (OUT/"scores.csv").open("w",newline="",encoding="utf8") as f:
        w=csv.DictWriter(f,fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)
    for r in summary: print(r["protocol"],r["method"],r["success"],r["wrong"],r["defer"],r["calls"],r["brier"])


def freeze():
    OUT.mkdir(exist_ok=True)
    if (OUT/"lock.json").exists():
        assert read(OUT/"lock.json")["files"]==seal()
        return
    import pip
    import pip._vendor.packaging as vendored
    releases={}
    for tool,versions in VERSIONS.items():
        for version in versions:
            with urlopen(f"https://pypi.org/pypi/{tool}/{version}/json",timeout=30) as resp:
                meta=json.load(resp)
            row=next(f for f in meta["urls"] if f["filename"].endswith("none-any.whl"))
            releases[f"{tool} {version}"]=dict(filename=row["filename"],url=row["url"],sha256=row["digests"]["sha256"])
    model=training()
    save("lock.json",dict(utc=datetime.now(timezone.utc).isoformat(),files=seal(),releases=releases,python=platform.python_version(),
         fallback_pip=pip.__version__,vendored_packaging=vendored.__version__,prior=model.prior_by_scope,alpha=model.alpha,
         ccet=[dict(match=k[1],mid=v[0],transfer=v[1]) for k,v in model.buckets.items() if k[0]=="ccet"]))


if __name__=="__main__":
    if sys.argv[1]=="freeze": freeze()
    elif sys.argv[1]=="worker": worker(*sys.argv[2:])
    else: run()

