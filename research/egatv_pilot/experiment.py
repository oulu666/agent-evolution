import csv
from dataclasses import asdict
from datetime import date, timedelta, datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from policy import METHODS, Evidence, choose
from tasks import HISTORIES, PROBES, VALUES, truth

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT/"runs_egatv_pilot_20261125"
LEGACY = ROOT/"runs_upstream_functional_20261124/paired_releases.json"
DEV = HERE.parent/"issre_reviewer_study/reference.json"
FILES = [*sorted(HERE.glob("*.py")), HERE/"protocol.md", LEGACY, DEV,
         ROOT/"runs_ext_p11_eaar_v1/branches/A_seed20261108_eaar_v1/checkpoint/adapter_model.safetensors"]


def read(p):
    return json.loads(p.read_text(encoding="utf-8-sig"))


def save(name, value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")


def seal():
    return {str(p.relative_to(ROOT).as_posix()): hashlib.sha256(p.read_bytes()).hexdigest() for p in FILES}


def development():
    dev = read(DEV)
    worlds = []
    for v in ["0.2.9","0.2.10"]:
        data = dev["wcwidth "+v]["observations"]
        worlds.append([data["AB"]==2, data["\u2640\ufe0f"]==2])
    # Counting predictions of three deterministic width mutants on AB and female sign + VS16.
    mutants = ((3,3),(2,3),(2,1))
    kills = [[i for i,row in enumerate(mutants) if row[q]!=2] for q in range(2)]
    return dict(worlds=worlds,kills=kills)


def execute(tool, value, alt=False):
    if tool == "week":
        day = date.fromisoformat(value)
        if alt:
            thursday = day + timedelta(days=3-day.weekday())
            week = 1 + (thursday-date(thursday.year,1,1)).days//7
            return f"{thursday.year:04d}-W{week:02d}-{day.weekday()+1}"
        from babel.dates import format_date
        return format_date(day,"YYYY-'W'ww-e",locale="de_DE")
    import xlsxwriter
    data = BytesIO()
    book = xlsxwriter.Workbook(data,{"in_memory":True})
    sheet = book.add_worksheet()
    fmt = book.add_format({"num_format":"[h]:mm"})
    if alt:
        sheet.write_number(0,0,float(value),fmt)
    else:
        sheet.write_datetime(0,0,timedelta(days=value),fmt)
    book.close()
    # Score the emitted cell and its referenced number format, including on the alternate route.
    with ZipFile(data) as z:
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
        styles = ET.fromstring(z.read("xl/styles.xml"))
        c = sheet.find(".//{*}c")
        xf = styles.find("{*}cellXfs")[int(c.get("s"))]
        fmt = next(n.get("formatCode") for n in styles.find("{*}numFmts") if n.get("numFmtId")==xf.get("numFmtId"))
        return [float(c.find("{*}v").text),fmt]


def expected(tool, value):
    result = truth(tool,value)
    return [result,"[h]:mm"] if tool=="duration" else result


def worker(tool,version,folder):
    sys.path.insert(0,folder)
    package=__import__("babel" if tool=="week" else "xlsxwriter")
    assert package.__version__==version and Path(package.__file__).resolve().is_relative_to(folder)
    proposals = {r["value"]:r for r in read(OUT/"routing.json")["rows"] if r["tool"]==tool}
    lib=development()
    rows=[]
    for i,value in enumerate(VALUES[tool]):
        scope=int(i>=4)
        proposal=proposals[value]
        for history_type in HISTORIES:
            for fallback in (False,True):
                severity=1 if i%2==0 else 4
                q=1-scope if history_type=="other_path" else scope
                for method in METHODS:
                    start=time.perf_counter_ns()
                    history_value=execute(tool, PROBES[tool][q])
                    if history_type=="no_assertion":
                        passed=all([])  # suite colour when no checks ran
                    elif history_type=="coarse":
                        passed=isinstance(history_value,str) if tool=="week" else history_value[1]=="[h]:mm"
                    else:
                        passed=history_value==expected(tool,PROBES[tool][q])
                    history=Evidence(history_type!="no_assertion",history_type not in ("no_assertion","coarse"),q,passed)
                    checks=[]
                    probe_ns=0
                    def probe(index):
                        nonlocal probe_ns
                        before=time.perf_counter_ns()
                        actual=execute(tool, PROBES[tool][index])
                        e=Evidence(True,True,index,actual==expected(tool,PROBES[tool][index]))
                        checks.append(dict(scope=index,actual=actual,passed=e.passed))
                        probe_ns+=time.perf_counter_ns()-before
                        return e
                    tick=time.perf_counter_ns()
                    action=choose(method,scope,history,probe,lib,proposal["confidence"],severity,fallback)
                    policy_ns=time.perf_counter_ns()-tick-probe_ns
                    assert len(checks)<=2 and not (action=="fallback" and not fallback)
                    # The caller supplies a typed day count or ISO date. A wrong selected tool rejects the request.
                    mismatch=proposal["picked"]!=tool
                    final=None
                    if action!="defer" and not mismatch:
                        final=execute(tool,value,action=="fallback")
                    ok=action!="defer" and final==expected(tool,value)
                    rows.append(dict(tool=tool,version=version,value=value,scope=scope,history=history_type,
                        starting_evidence=asdict(history),history_value=history_value,severity=severity,fallback_available=fallback,
                        method=method,action=action,tool_mismatch=mismatch,checks=checks,result=final,success=ok,
                        wrong=action!="defer" and not ok,defer=action=="defer",additional=len(checks),
                        calls=1+len(checks)+int(action!="defer"),decision_us=policy_ns/1000,workflow_ms=(time.perf_counter_ns()-start)/1e6))
    print(json.dumps(rows))


def run():
    assert seal()==read(OUT/"lock.json")["files"]
    historical=read(LEGACY)
    routing=read(OUT/"routing.json")
    assert len(routing["rows"])==16
    started=datetime.now(timezone.utc).isoformat()
    rows=[]
    for tool in ("week","duration"):
        for side in ("before","after"):
            ref=historical[tool][side]
            with tempfile.TemporaryDirectory() as tmp:
                with urlopen(ref["url"],timeout=40) as response:
                    payload=response.read()
                assert hashlib.sha256(payload).hexdigest()==ref["sha256"]
                with ZipFile(BytesIO(payload)) as z:
                    z.extractall(tmp)
                child=subprocess.check_output([sys.executable,str(Path(__file__).resolve()),"worker",tool,ref["version"],tmp],text=True)
                rows.extend(json.loads(child))
    summary=[]
    for m in METHODS:
        group=[r for r in rows if r["method"]==m]
        assert len(group)==256 and all(sum(map(int,(r["success"],r["wrong"],r["defer"])))==1 for r in group)
        summary.append(dict(method=m,n=len(group),success=sum(r["success"] for r in group),wrong=sum(r["wrong"] for r in group),
                  defer=sum(r["defer"] for r in group),fallback=sum(r["action"]=="fallback" for r in group),
                  extra=sum(r["additional"] for r in group),calls=sum(r["calls"] for r in group),
                  committed=sum(not r["defer"] for r in group),weighted_error=sum(r["severity"]*r["wrong"] for r in group),
                  median_decision_us=round(statistics.median(r["decision_us"] for r in group),2),
                  median_workflow_ms=round(statistics.median(r["workflow_ms"] for r in group),3)))
    save("decisions.json",rows)
    save("summary.json",dict(started=started,development=development(),summary=summary))
    with (OUT/"scores.csv").open("w",encoding="utf-8",newline="") as file:
        writer=csv.DictWriter(file,fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    print((OUT/"scores.csv").read_text())


if __name__=="__main__":
    if sys.argv[1]=="freeze":
        OUT.mkdir(exist_ok=True)
        if (OUT/"lock.json").exists():
            assert seal()==read(OUT/"lock.json")["files"]
        else:
            save("lock.json",dict(frozen=datetime.now(timezone.utc).isoformat(),files=seal()))
    elif sys.argv[1]=="worker":
        worker(*sys.argv[2:])
    else:
        run()

