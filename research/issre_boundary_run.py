"""Freeze reference schedules, then replay public tagged code and held-out pairs."""
from datetime import datetime, timezone
from io import BytesIO
from itertools import combinations, permutations
import json
from pathlib import Path
import random
from statistics import median
import subprocess
import sys
import tempfile
from time import perf_counter_ns
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from issre_boundary_frame import PROJECTS, OUT, git, read, write, digest
from issre_boundary_contracts import extract
from issre_boundary_probes import execute

MODES = ("final","boundary","both")
FILES = ["issre_boundary_frame.py","issre_boundary_contracts.py","issre_boundary_probes.py",
         "issre_boundary_run.py","ISSRE_BOUNDARY_PROTOCOL_20261124_ZH.md","issre_interaction_frame.py"]


def keys(data):
    return {r["id"]+"/"+str(v): (r,bool(v)) for r in data["records"] for v in (0,1)}


def features(rule, varied):
    items = {(rule["observer"],field) for field in rule["fields"]}
    if not varied:
        items.discard((rule["observer"],"undo"))
        items.discard((rule["observer"],"late_registration"))
    return items | {(rule["id"],"end"),(rule["action"],"combined" if varied else "ordinary")}


def plans(data,ref):
    cases = keys(data)
    first = [r["id"] for r in data["records"]][:3]
    basic = [n+"/0" for n in first]
    combined = [n+"/1" for n in first]
    methods = {"ordinary":("final",basic),"combination":("final",combined),"contract":("boundary",combined)}
    cap = round(3*median(v["both"]["ns"] for v in ref.values()))
    best = None
    # Exhaust all admissible subsets. Prefer documented fields covered, then low cost.
    for n in (1,2,3):
        for sequence in combinations(cases,n):
            cost = sum(ref[k]["both"]["ns"] for k in sequence)
            calls = sum(ref[k]["both"]["result"]["public_calls"] for k in sequence)
            if cost>cap or calls>15:
                continue
            gain = len(set().union(*(features(*cases[k]) for k in sequence)))
            score = (gain,-cost)
            if best is None or score>best[0]:
                best = (score,sorted(sequence,key=lambda k:ref[k]["both"]["ns"]))
    methods["budget_contract"] = ("both",best[1] if best else [])
    return {"time_cap_ns":cap,"call_cap":15,"methods":methods,
            "cost":{k:{m:r[m]["result"]["public_calls"] for m in MODES} for k,r in ref.items()}}


def worker(p,root,protocol):
    sys.path.insert(0,str(root/"src"))
    assert Path(__import__(p).__file__).resolve().is_relative_to(root)
    rules = read(OUT/"contracts.json")[p]
    cases = keys(rules)
    rows = {k:{} for k in cases}
    for k,(rule,varied) in cases.items():
        for m in MODES:
            first = execute(p,rule,varied,m)
            elapsed = []
            for _ in range(5):
                start = perf_counter_ns()
                other = execute(p,rule,varied,m)
                elapsed.append(perf_counter_ns()-start)
                if first!=other:
                    raise ValueError(("unstable",k,m))
            rows[k][m] = {"result":first,"ns":median(elapsed)}
    output = {"rows":rows}
    if protocol is not None:
        completed = {n:[] for n in protocol["methods"]}
        names = list(completed)
        rng = random.Random(803)
        for _ in range(5):
            rng.shuffle(names)
            for name in names:
                mode, sequence = protocol["methods"][name]
                clock = perf_counter_ns()
                prefix = []
                used = 0
                for k in sequence:
                    used += protocol["cost"][k][mode]
                    if used>15 or perf_counter_ns()-clock>=protocol["time_cap_ns"]:
                        break
                    rule,v = cases[k]
                    result = execute(p,rule,v,mode)
                    elapsed = perf_counter_ns()-clock
                    if result!=rows[k][mode]["result"]:
                        raise ValueError("unstable plan result")
                    if elapsed>protocol["time_cap_ns"]:
                        break
                    prefix.append(k)
                completed[name].append({"keys":prefix,"elapsed":perf_counter_ns()-clock})
        output["plans"] = completed
    return output


def replay(p,revision,calibration=False):
    source = git(p,"archive","--format=zip",revision,"src/"+p)
    with tempfile.TemporaryDirectory() as tmp:
        with ZipFile(BytesIO(source)) as archive:
            archive.extractall(tmp)
        proc = subprocess.run([sys.executable,"-I",__file__,"worker",p,tmp,
                              "dev" if calibration else "target"],capture_output=True,text=True,
                              encoding="utf8",timeout=120)
        if proc.returncode:
            raise RuntimeError(proc.stderr[-1500:])
        return json.loads(proc.stdout)


def freeze():
    if (OUT/"freeze.json").exists():
        raise ValueError("already frozen")
    data = {}
    for p in PROJECTS:
        t = perf_counter_ns()
        data[p] = extract(p)
        data[p]["extract_with_io_ns"] = perf_counter_ns()-t
    write(OUT/"contracts.json",data)
    reference,schedules = {},{}
    for p,(_,tag,_) in PROJECTS.items():
        reference[p] = replay(p,tag,True)["rows"]
        bad = [(k,m,v["result"]) for k,row in reference[p].items() for m,v in row.items() if not v["result"]["ok"]]
        if bad:
            raise ValueError(("reference",p,bad))
        schedules[p] = plans(data[p],reference[p])
    write(OUT/"reference.json",reference)
    write(OUT/"schedules.json",schedules)
    paths = [HERE/n for n in FILES]+[OUT/n for n in ("sealed.json","contracts.json","reference.json","schedules.json")]
    write(OUT/"freeze.json",{"utc":datetime.now(timezone.utc).isoformat(),"sha256":{path.name:digest(path) for path in paths}})
    print("locked",digest(OUT/"freeze.json"))


def run():
    for name,h in read(OUT/"freeze.json")["sha256"].items():
        assert digest((HERE if name in FILES else OUT)/name)==h
    output = []
    for p,g in read(OUT/"sealed.json").items():
        for row in [{"commit":PROJECTS[p][2]},*g["selected"]]:
            entry = {"project":p,"id":row["commit"]}
            for side in ("parent","commit"):
                if side in row:
                    try:
                        entry[side] = replay(p,row[side])
                    except (RuntimeError,subprocess.SubprocessError) as exc:
                        entry[side] = {"infra_error":str(exc)}
            output.append(entry)
    write(OUT/"paired.json",output)
    print("retained pairs",sum("parent" in e for e in output),"reference tags",len(PROJECTS))
    print("infrastructure errors",[(e["project"],s,v["infra_error"]) for e in output for s,v in e.items()
                                   if isinstance(v,dict) and "infra_error" in v])


if __name__=="__main__":
    if sys.argv[1]=="worker":
        p = sys.argv[2]
        plan = None if sys.argv[4]=="dev" else read(OUT/"schedules.json")[p]
        print(json.dumps(worker(p,Path(sys.argv[3]),plan)))
    elif sys.argv[1]=="freeze":
        freeze()
    elif sys.argv[1]=="run":
        run()

