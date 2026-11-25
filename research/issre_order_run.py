from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha1
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from time import perf_counter_ns
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from issre_order_frame import DOC,PROJECTS,OUT,read,write,git,digest
from issre_order_extract import extract
from issre_order_fixtures import GOLD,transitions_run,statemachine_run


def archive(p,rev):
    cached = Path(tempfile.gettempdir())/f"issre-order-{p}-{rev}.zip"
    if not cached.exists():
        with tempfile.NamedTemporaryFile(delete=False,suffix=".partial") as temp:
            partial = Path(temp.name)
        try:
            subprocess.run(["curl.exe","-fsSL","--max-time","45","--retry","2","--retry-all-errors",
                "https://codeload.github.com/"+PROJECTS[p][0]+"/zip/"+rev,"-o",str(partial)],check=True)
            with ZipFile(partial) as z:
                if z.testzip(): raise ValueError("invalid archive")
            partial.replace(cached)
        finally:
            partial.unlink(missing_ok=True)
    return cached


def contents(p,rev,docs=False):
    lines = git(p,"ls-tree","-r",rev).decode().splitlines()
    hashes = {n:meta.split()[-1] for meta,n in (s.split("\t",1) for s in lines)}
    with ZipFile(archive(p,rev)) as z:
        for name in z.namelist():
            path="/".join(name.split("/")[1:])
            include = bool(DOC.fullmatch(path)) if docs else (
                path.startswith((p+"/","src/"+p+"/")) and path.endswith((".py",".json",".toml",".lark")))
            if not include: continue
            blob = z.read(name)
            if sha1(f"blob {len(blob)}\0".encode()+blob).hexdigest()!=hashes[path]:
                raise ValueError("git object mismatch")
            yield path,blob


def trace(p,rev):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for n,blob in contents(p,rev):
            path=root/n
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(blob)
        proc=subprocess.run([sys.executable,"-I",__file__,"worker",p,tmp],capture_output=True,text=True,
                            encoding="utf8",timeout=30)
        if proc.returncode: return {"infra_error":proc.stderr[-1600:]}
        return json.loads(proc.stdout)


def check_lock():
    for n,h in read(OUT/"extractor_lock.json").items():
        assert digest((OUT if n.endswith(".json") else HERE)/n)==h


def freeze():
    check_lock()
    assert not (OUT/"run_lock.json").exists()
    # Seal the independent reference and runner before emitting any extracted text or predictions.
    write(OUT/"reference_lock.json",{n:digest(HERE/n) for n in ("issre_order_fixtures.py","issre_order_run.py")})
    predictions,refs = {},{}
    for p,(_,tag) in PROJECTS.items():
        predictions[p]={}
        for n,blob in contents(p,tag,True):
            t=perf_counter_ns()
            pred=extract(blob.decode("utf8"))
            predictions[p][n]={**pred,"extract_ns":perf_counter_ns()-t}
        refs[p]=trace(p,tag)
    write(OUT/"predictions.json",predictions)
    write(OUT/"reference_traces.json",refs)
    write(OUT/"run_lock.json",{n:digest(OUT/n) for n in ("extractor_lock.json","reference_lock.json",
                                            "predictions.json","reference_traces.json","sealed.json")})
    print("reference",refs,"locked",digest(OUT/"run_lock.json"))


def compare(p,record,preds):
    if "infra_error" in record:return record
    seq=record["trace"]
    edges={(x["left"],x["right"]) for doc in preds.values() for k in ("direct","derived")
           for x in doc[k] if x["left"] in GOLD[p] and x["right"] in GOLD[p]}
    def complies(s):
        return all(a in s and b in s and s.index(a)<s.index(b) for a,b in edges)
    swaps=[]
    for i in range(len(seq)-1):
        alt=list(seq)
        alt[i:i+2]=reversed(alt[i:i+2])
        swaps.append(not complies(alt) if edges else None)
    return dict(**record,end_ok=record["end"]=="b",members_ok=Counter(seq)==Counter(GOLD[p]),
                auto_order_ok=complies(seq) if edges else None,manual_order_ok=seq==GOLD[p],swaps=swaps)


def run():
    check_lock()
    for folder,lock in ((HERE,"reference_lock.json"),(OUT,"run_lock.json")):
        for n,h in read(OUT/lock).items(): assert digest(folder/n)==h
    preds=read(OUT/"predictions.json")
    work=[(p,entry,side) for p,g in read(OUT/"sealed.json").items() for entry in g["selected"] for side in ("parent","commit")]
    def one(job):
        p,e,s=job
        try: row=trace(p,e[s])
        except (OSError,ValueError,subprocess.SubprocessError) as ex: row={"infra_error":str(ex)}
        return dict(project=p,id=e["commit"],side=s,observation=compare(p,row,preds[p]))
    with ThreadPoolExecutor(3) as pool: result=list(pool.map(one,work))
    write(OUT/"paired.json",result)
    print("completed",len(result),"errors",[(r["project"],r["side"],r["observation"]["infra_error"])
          for r in result if "infra_error" in r["observation"]])


if __name__=="__main__":
    if sys.argv[1]=="worker":
        root=Path(sys.argv[3])
        sys.path[:0]=[str(root/"src"),str(root)]
        p=sys.argv[2]
        assert Path(__import__(p).__file__).resolve().is_relative_to(root)
        print(json.dumps((transitions_run if p=="transitions" else statemachine_run)()))
    elif sys.argv[1]=="freeze":freeze()
    elif sys.argv[1]=="run":run()

