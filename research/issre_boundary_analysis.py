"""Analyze the lock and separately replay two disclosed functional cases."""
from io import BytesIO
import json
from pathlib import Path
from statistics import median
import subprocess
import sys
import tempfile
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from issre_boundary_frame import OUT,git,read,write


def example(p,root):
    sys.path.insert(0,str(root/"src"))
    assert Path(__import__(p).__file__).resolve().is_relative_to(root)
    rows = []
    if p=="blinker":
        from blinker import Signal
        for fresh in (False,True):
            sent = int("91234567")
            actual = int(str(sent)) if fresh else sent
            trace = []
            def recv(sender):
                trace.append(sender)
                return 9
            sig = Signal()
            sig.connect(recv,sender=sent)
            pairs = sig.send(actual)
            rows.append(dict(same_object=sent is actual,equal=sent==actual,
                             end=[r for _,r in pairs],trace=trace))
    else:
        import pluggy
        for priority,wrapped in ((False,False),(True,False),(False,True),(True,True)):
            pm = pluggy.PluginManager("demo")
            spec,impl = pluggy.HookspecMarker("demo"),pluggy.HookimplMarker("demo")
            trace = []
            class S:
                @spec
                def probe(): pass
            class P:
                @impl(tryfirst=priority)
                def probe(self):
                    trace.append("registered")
                    return 9
            def extra():
                trace.append("extra")
                return 9
            class Wrapper:
                @impl(wrapper=True)
                def probe(self):
                    trace.append('enter')
                    result = yield
                    trace.append('exit')
                    return result
            pm.add_hookspecs(S)
            pm.register(P())
            if wrapped:
                pm.register(Wrapper())
            result = pm.hook.probe.call_extra([extra],{})
            rows.append(dict(tryfirst=priority,wrapped=wrapped,end=result,trace=trace))
    return rows


def paired_example(p,rev):
    with tempfile.TemporaryDirectory() as tmp:
        with ZipFile(BytesIO(git(p,"archive","--format=zip",rev,"src/"+p))) as z:
            z.extractall(tmp)
        return json.loads(subprocess.check_output([sys.executable,"-I",__file__,"example",p,tmp]))


def summarize():
    results = read(OUT/"paired.json")
    schedules = read(OUT/"schedules.json")
    out = {"cases":[],"projects":{}}
    for p,plan in schedules.items():
        rows = [e for e in results if e["project"]==p]
        holdout = next(e for e in rows if "parent" not in e)["commit"]["rows"]
        out["projects"][p] = {"reference_inputs":len(holdout),
            "reference_alerts":[[k,m] for k,r in holdout.items() for m,v in r.items() if not v["result"]["ok"]],
            "costs":{}}
        sides = [e[s] for e in rows if "parent" in e for s in ("parent","commit")]
        for m in plan["methods"]:
            trials = [s["plans"][m] for s in sides]
            out["projects"][p]["costs"][m] = dict(plan_us=median(median(t["elapsed"] for t in ts) for ts in trials)/1000,
                credited_cases=median(median(len(t["keys"]) for t in ts) for ts in trials),
                full_repetitions=sum(len(t["keys"])==len(plan["methods"][m][1]) for ts in trials for t in ts),
                repetitions=sum(map(len,trials)))
        for e in rows:
            if "parent" not in e: continue
            a,b = e["parent"],e["commit"]
            records = {}
            differences,alerts,hits = [],[],[]
            for k in a["rows"]:
                for mode in a["rows"][k]:
                    left,right = [s["rows"][k][mode]["result"] for s in (a,b)]
                    if left!=right: differences.append([k,mode])
                    if not left["ok"] or not right["ok"]: alerts.append([k,mode])
                    if not left["ok"] and right["ok"]: hits.append([k,mode])
            for m,(mode,seq) in plan["methods"].items():
                records[m] = [k for k in seq if [k,mode] in hits and all(
                    sum(k in t["keys"] for t in side["plans"][m])>=3 for side in (a,b))]
            out["cases"].append(dict(project=p,id=e["id"],diff=differences,alerts=alerts,full_hits=hits,credited_hits=records))
    out["diagnostics"] = {}
    sealed = read(OUT/"sealed.json")
    for p,prefix in (("blinker","e27fc051"),("pluggy","443fee6d")):
        row = next(r for r in sealed[p]["selected"] if r["commit"].startswith(prefix))
        out["diagnostics"][p] = {s:paired_example(p,row[s]) for s in ("parent","commit")}
    write(OUT/"findings.json",out)


if __name__=="__main__":
    if len(sys.argv)>1: print(json.dumps(example(sys.argv[2],Path(sys.argv[3]))))
    else: summarize()

