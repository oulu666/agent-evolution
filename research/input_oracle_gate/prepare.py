"""Fix projects, blind sample, factorial domain, test menus and offline delivery tasks."""
import csv
import hashlib
import itertools
import json
import os
from pathlib import Path
import random
import re
import subprocess
import tempfile
import urllib.request

HERE=Path(__file__).resolve().parent
OUT=HERE.parents[1]/"runs_input_oracle_gate_20261125"
PROJECTS={"python-semver":"a4b7d337b1eb699ad4bad532a4b3fc68f8ec2408",
          "python-semanticversion":"2cbbee3154d9011cee873ae3a020cd17c669f6df"}
SIZES=(3,3,5,2,2,2)
BUDGET=16


def save(name,data):
    (OUT/name).write_text(json.dumps(data,indent=2),encoding="utf8")


def git(project,*args):
    repo=Path(os.environ.get("COSYN_MIRRORS",tempfile.gettempdir()))/f"eswa-cosyn-{project}.git"
    return subprocess.check_output(["git","--git-dir",str(repo),*args])


def screen():
    sample=[]
    counts={}
    for p,head in PROJECTS.items():
        log=git(p,"log","--no-merges","--since=2014-01-01T00:00:00Z","--before=2026-01-01T00:00:00Z",
                "--format=%H%x09%s",head).decode().splitlines()
        visited=0
        for row in log:
            visited+=1
            rev,title=row.split("\t",1)
            if not re.search(r"fix|bug|incorrect|wrong|correc|repair",title,re.I) or not re.search(
                    r"compar|order|precedence|sort|pre.?release|build.?metadata",title,re.I):
                continue
            if re.search(r"\b(CI|docs?|bump|dependencies|packaging|security|CVE|vulnerab\w*)\b",title,re.I):
                continue
            files=git(p,"diff-tree","--no-commit-id","--name-only","-r",rev).decode().splitlines()
            if not any(re.match(r"^(src/)?(semver(\.py$|/)|semantic_version/)",f) and f.endswith(".py") for f in files):
                continue
            sample.append(dict(project=p,rev=rev,parent=git(p,"rev-parse",rev+"^1").decode().strip()))
            if sum(r["project"]==p for r in sample)==3:
                break
        counts[p]=visited
    save("sample.json",sample)
    save("screening.json",counts)


def materialize(row):
    core,phase,rel,prefix,meta,reverse=row
    left="1.2.3"
    right=("1.2.3","1.2.10","1.1.12")[core]
    x,y=(("a","a"),("2","10"),("2","a"),("rc","rc.1"),("a","b"))[rel]
    pre="rc." if prefix else ""
    if phase==0:
        left+="-"+pre+x
        right+="-"+pre+y
    elif phase==1:
        right+="-"+pre+y
    if meta:
        left+="+z.2"
        right+="+a.10"
    return (right,left) if reverse else (left,right)


def inspect_pair(pair):
    """Semantic obligations transcribed from SemVer 2.0.0 section 11, valid canonical inputs only."""
    def parse(s):
        clean=s.partition("+")[0]
        core,_,tail=clean.partition("-")
        return tuple(map(int,core.split("."))),tail.split(".") if tail else []
    sign=lambda x,y:(x>y)-(x<y)
    l,r=map(parse,pair)
    for field,x,y in zip(("major","minor","patch"),l[0],r[0]):
        if x!=y:
            return field,sign(x,y)
    a,b=l[1],r[1]
    if bool(a)!=bool(b):
        return "release",sign(not a,not b)
    for x,y in zip(a,b):
        if x==y:
            continue
        if x.isdigit() and y.isdigit():
            return "numeric",sign(int(x),int(y))
        if x.isdigit()!=y.isdigit():
            return "mixed",sign(not x.isdigit(),not y.isdigit())
        return "ascii",sign(x,y)
    if len(a)!=len(b):
        return "length",sign(len(a),len(b))
    return "tie",0


def tokens(row,t):
    return {tuple((i,row[i]) for i in ids) for ids in itertools.combinations(range(len(row)),t)}


def acts(t):
    jar=Path(os.environ.get("ACTS_JAR",str(Path(tempfile.gettempdir())/"eswa-acts-basic-1.jar")))
    assert hashlib.sha256(jar.read_bytes()).hexdigest()=="8efe3cdd5847135381b1daba9e8d57d0d013d00b0b2a7c15dd7c4255f0fb1242"
    model=OUT/"acts_model.txt"
    model.write_text("[System]\nName: precedence\n[Parameter]\n"+"\n".join(
        f"P{i} (int) : "+",".join(map(str,range(n))) for i,n in enumerate(SIZES))+"\n",encoding="ascii")
    dest=OUT/f"acts{t}.csv"
    if dest.exists():
        dest.unlink()
    subprocess.run(["java","-Djava.awt.headless=true",f"-Ddoi={t}","-Doutput=csv","-cp",str(jar),
        "edu.uta.cse.fireeye.console.ActsConsoleManager",str(model),str(dest)],check=True,capture_output=True,timeout=45)
    rows=[tuple(map(int,r)) for r in csv.reader(dest.read_text().splitlines()) if r and re.fullmatch(r"\d+",r[0].strip())]
    assert rows
    return rows


def menu():
    text=urllib.request.urlopen("https://raw.githubusercontent.com/semver/semver/v2.0.0/semver.md",timeout=30).read().decode()
    sec=text[text.index("Precedence refers"):].split("Why Use")[0].split("Why use")[0]
    (OUT/"section11.txt").write_text(sec,encoding="utf8")
    pat=r"\d+\.\d+\.\d+(?:-[a-zA-Z0-9]+(?:\.[a-zA-Z0-9]+)*)?"
    pairs=[]
    for chunk in re.findall(pat+r"(?:\s*<\s*"+pat+r")+",sec):
        items=re.findall(pat,chunk)
        pairs.extend(zip(items,items[1:]))
    assert len(pairs)>=8 and all(inspect_pair(x)[1]==-1 for x in pairs)
    unique=lambda seq:list(dict.fromkeys(seq))
    allrows=list(itertools.product(*(range(n) for n in SIZES)))
    domain=unique(map(materialize,allrows))
    methods={"examples":unique(pairs)[:BUDGET]}
    cov={}
    for t in (2,3):
        rows=acts(t)
        total=set().union(*(tokens(r,t) for r in allrows))
        assert set().union(*(tokens(r,t) for r in rows))==total
        chosen=unique(map(materialize,rows))[:BUDGET]
        methods[f"acts{t}"]=chosen
        # Deduplicate physical calls; count only abstract rows actually reached within the cap.
        end=next((i for i,r in enumerate(rows) if materialize(r) not in chosen),len(rows))
        cov[t]=dict(full_rows=len(rows),full_tuples=len(total),prefix_rows=end,
                    prefix_tuples=len(set().union(*(tokens(r,t) for r in rows[:end]))))
    doc=unique(pairs+[(b,a) for a,b in pairs]+[(a,a) for a,b in pairs])
    methods["doc_oracle"]=doc[:BUDGET]
    sampled=random.Random(2711).sample(domain,len(domain))
    methods["separate"]=sampled[:BUDGET]
    # Greedy obligation cover. The result cannot depend on either library's outputs.
    def tags(pair):
        clause,result=inspect_pair(pair)
        return {(clause,result),(clause,"metadata","+" in pair[0]),(clause,"prefix","-rc." in " ".join(pair))}
    seen=set()
    joint=[]
    for _ in range(BUDGET):
        pick=max((p for p in sampled if p not in joint),key=lambda p:len(tags(p)-seen))
        joint.append(pick)
        seen.update(tags(pick))
    methods["joint"]=joint
    used={tuple(sorted(p)) for suite in methods.values() for p in suite}
    candidates=[p for p in domain if tuple(sorted(p)) not in used]
    tasks=random.Random(20261125).sample(candidates,24)
    save("suites.json",methods)
    save("coverage.json",cov)
    save("tasks.json",tasks)
    print("Frozen menus:",{k:len(v) for k,v in methods.items()},cov)


if __name__=="__main__":
    OUT.mkdir(exist_ok=True)
    assert not (OUT/"lock.json").exists()
    screen()
    menu()
