"""Freeze inputs and comparators, execute revisions, then score each policy independently."""
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
from prepare import HERE,OUT,git,inspect_pair,save


def load(name):
    return json.loads((OUT/name).read_text())


def key(pair):
    return "|".join(pair)


def doc_oracle(pair,examples):
    # Partial oracle constructed from the externally documented example ordering,
    # numeric core, stable-vs-prerelease, and build metadata clauses.
    a,b=(s.partition("+")[0] for s in pair)
    if a==b:
        return 0
    ca,cb=[tuple(map(int,x.partition("-")[0].split("."))) for x in (a,b)]
    if ca!=cb:
        return (ca>cb)-(ca<cb)
    if ("-" in a)!=("-" in b):
        return -1 if "-" in a else 1
    if (a,b) in examples:
        return -1
    if (b,a) in examples:
        return 1
    return None


def external(pairs):
    js="""const fs=require('fs'),path=require('path');const dir=path.join(path.dirname(process.execPath),'node_modules/npm/node_modules/semver');const s=require(dir);const cases=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify({version:require(path.join(dir,'package.json')).version,labels:cases.map(([a,b])=>Math.sign(s.compare(a,b)))}));"""
    return json.loads(subprocess.check_output(["node","-e",js],input=json.dumps(pairs).encode()))


def execute(project,rev,pairs):
    files=git(project,"ls-tree","--name-only",rev).decode().splitlines()
    paths=[x for x in files if x in ("src","semver.py","semver","semantic_version")]
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(io.BytesIO(git(project,"archive","--format=zip",rev,"--",*paths))) as z:
            for n in z.namelist():
                assert (Path(tmp)/n).resolve().is_relative_to(Path(tmp))
            z.extractall(tmp)
        run=subprocess.run([sys.executable,"-I",str(HERE/"worker.py"),tmp,project],input=json.dumps(pairs),
                           text=True,capture_output=True,cwd=tmp,timeout=60)
        if run.returncode:
            return {"unavailable":run.stderr[-1800:]}
        values=json.loads(run.stdout)
        assert len(values)==len(pairs)
        return dict(zip(map(key,pairs),values))


def main():
    inputs=list(HERE.glob("*.py"))+[HERE/"protocol.md"]+[OUT/n for n in
        ("sample.json","suites.json","coverage.json","tasks.json","section11.txt","acts_model.txt","acts2.csv","acts3.csv","screening.json")]
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    if (OUT/"lock.json").exists():
        assert load("lock.json")==hashes
    else:
        save("lock.json",hashes)
    assert not (OUT/"raw.json").exists()
    samples=load("sample.json")
    suites={k:list(map(tuple,v)) for k,v in load("suites.json").items()}
    tasks=list(map(tuple,load("tasks.json")))
    assert not {tuple(sorted(p)) for p in tasks} & {tuple(sorted(p)) for v in suites.values() for p in v}
    pairs=list(dict.fromkeys([p for v in suites.values() for p in v]+tasks))
    other=external(pairs)
    gold=dict(zip(map(key,pairs),other["labels"]))
    assert all(inspect_pair(p)[1]==gold[key(p)] for p in pairs)
    save("scorer.json",{"node_semver":other["version"],"labels":gold})
    raw={}
    for s in samples:
        for rev in (s["parent"],s["rev"]):
            raw[rev]=execute(s["project"],rev,pairs)
    save("raw.json",raw)
    report(raw,samples,suites,tasks,gold)


def report(raw,samples,suites,tasks,gold):
    examples=set(suites["examples"])
    for t in (2,3):
        suites[f"acts{t}_doc"]=suites[f"acts{t}"]
    suites["separate_doc"]=suites["separate"]
    suites["joint_doc"]=suites["joint"]
    details={}
    deliveries={}
    for method in ["always","defer","direct_norm",*suites]:
        total=Counter()
        route_fallback=Counter()
        audits={}
        for rev,results in raw.items():
            if "unavailable" in results:
                continue
            flags=[]
            unknown=[]
            for pair in suites.get(method,[]):
                oracle=doc_oracle(pair,examples) if method.endswith("_doc") else inspect_pair(pair)[1]
                if oracle is None:
                    unknown.append(pair)
                elif results[key(pair)]!=oracle:
                    flags.append(pair)
            audits[rev]=dict(flags=flags,unknown=unknown,checks=len(suites.get(method,[])))
            for pair in tasks:
                k=key(pair)
                value=results[k]
                oracle=inspect_pair(pair)[1]
                should_choose_second=gold[k]<0
                def outcome(v):
                    return "defer" if type(v) is not int else "ok" if (v<0)==should_choose_second else "wrong"
                plain="defer" if flags or method=="defer" else outcome(oracle if method=="direct_norm" else value)
                total[plain]+=1
                route_fallback[outcome(oracle if flags else value)]+=1
        paired=[]
        for s in samples:
            if s["parent"] not in audits or s["rev"] not in audits:
                continue
            p={tuple(x) for x in audits[s["parent"]]["flags"]}
            r={tuple(x) for x in audits[s["rev"]]["flags"]}
            paired.append(dict(project=s["project"],rev=s["rev"],old_only=sorted(p-r),
                               both=sorted(p&r),fixed_only=sorted(r-p),old_suite=bool(p),fixed_suite=bool(r)))
        details[method]=dict(pairs=paired,audit=audits)
        deliveries[method]=dict(quarantine=dict(total),fallback=dict(route_fallback) if method in suites else {},
              audit_calls=sum(v["checks"] for v in audits.values()))
    save("audit.json",details)
    save("delivery.json",deliveries)
    print("Unavailable", {k:v for k,v in raw.items() if "unavailable" in v})
    for m,r in details.items():
        print(m, [(x["rev"][:7], len(x["old_only"]),len(x["both"]),len(x["fixed_only"])) for x in r["pairs"]],
              deliveries[m]["quarantine"])


if __name__=="__main__":
    main()
