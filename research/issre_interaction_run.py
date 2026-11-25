"""Run fixed tasks on pre-screening documentation tags, then sealed commit pairs."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha1
import json
from pathlib import Path, PurePosixPath
import random
import subprocess
import sys
import tempfile
from threading import Lock
from time import perf_counter_ns
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from issre_interaction_frame import PROJECTS, OUT, git, digest, read, write
from issre_interaction_tasks import execute, menus, FACTORS

FILES = ["issre_interaction_frame.py","issre_interaction_tasks.py","issre_interaction_run.py",
         "ISSRE_INTERACTION_PROTOCOL_20261124_ZH.md"]
BENCH_LOCK = Lock()


def worker(p, root):
    sys.path[:0] = [str(root/"src"),str(root)]
    mod = __import__("attr" if p=="attrs" else "dateutil")
    assert Path(mod.__file__).resolve().is_relative_to(root)
    schedules = menus(p)
    measured = {method:[] for method in ("single","combined","mirror")}
    values = {n+"/"+c:execute(p,n,c) for n,c in schedules["all"]}
    rng = random.Random(122)
    order = list(measured)
    for trial in range(6):
        rng.shuffle(order)
        for m in order:
            start = perf_counter_ns()
            results = [execute(p,n,c) for n,c in schedules[m]]
            duration = perf_counter_ns()-start
            assert results == [values[n+"/"+c] for n,c in schedules[m]]
            if trial:
                measured[m].append(duration)
    return dict(rows=values,plan_ns=measured)


def replay(p,rev):
    cache = Path(tempfile.gettempdir())/f"issre-ix-{p}-{rev}.zip"
    if not cache.exists():
        with tempfile.NamedTemporaryFile(delete=False,suffix=".partial") as f:
            partial = Path(f.name)
        try:
            subprocess.run(["curl.exe","--silent","--show-error","--fail","--location","--max-time","35",
                "--retry","3","--retry-all-errors","--output",str(partial),
                "https://codeload.github.com/"+PROJECTS[p][0]+"/zip/"+rev],check=True)
            with ZipFile(partial) as archive:
                if archive.testzip():
                    raise ValueError("invalid source archive")
            partial.replace(cache)
        finally:
            partial.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        fingerprints = {}
        with ZipFile(cache) as archive:
            for item in archive.infolist():
                parts = PurePosixPath(item.filename).parts[1:]
                if len(parts)<2 or ".." in parts or not parts[-1].endswith(".py"):
                    continue
                pkg = parts[1] if parts[0]=="src" else parts[0]
                if pkg not in ({"attr","attrs"} if p=="attrs" else {"dateutil"}):
                    continue
                content = archive.read(item)
                path = root.joinpath(*parts)
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(content)
                fingerprints["/".join(parts)] = sha1(f"blob {len(content)}\0".encode()+content).hexdigest()
        if not fingerprints:
            raise ValueError("source files missing")
        tree = git(p,"ls-tree","-r",rev).decode("utf8").splitlines()
        objects = {path:meta.split()[-1] for meta,path in (line.split("\t",1) for line in tree)}
        if any(objects.get(path)!=h for path,h in fingerprints.items()):
            raise ValueError("source archive mismatch")
        with BENCH_LOCK:
            proc = subprocess.run([sys.executable,"-I",__file__,"worker",p,tmp],capture_output=True,
                                  text=True,encoding="utf8",check=True,timeout=80)
        return json.loads(proc.stdout)


def freeze():
    assert not (OUT/"freeze.json").exists()
    dev = {}
    for p,(_,rev,_) in PROJECTS.items():
        dev[p] = replay(p,rev)
        failed = {k:v for k,v in dev[p]["rows"].items() if not v["pass"]}
        if failed:
            raise ValueError((p,failed))
    write(OUT/"reference.json",dev)
    write(OUT/"plans.json",{"factors":FACTORS,"menus":{p:menus(p) for p in PROJECTS}})
    paths = [HERE/f for f in FILES]+[OUT/f for f in ("reference.json","plans.json","sealed_frame.json","sealed_supplement.json")]
    write(OUT/"freeze.json",{"time_utc":datetime.now(timezone.utc).isoformat(),
            "sha256":{path.name:digest(path) for path in paths}})
    print("freeze",digest(OUT/"freeze.json"))


def run():
    for name,h in read(OUT/"freeze.json")["sha256"].items():
        assert digest((HERE if name in FILES else OUT)/name)==h
    results = []
    slots = [(p,r,side,stratum) for stratum,file in (("primary","sealed_frame.json"),("supplement","sealed_supplement.json"))
             for p,data in read(OUT/file).items() for r in data["selected"] for side in ("parent","commit")]
    def one(slot):
        p,r,side,stratum = slot
        result = dict(project=p,id=r["commit"],side=side,revision=r[side],stratum=stratum)
        try:
            result.update(replay(p,r[side]))
        except Exception as e:
            result["infra_error"] = str(e)
        return result
    # Downloads may overlap, but at most one timing worker measures plans at once.
    with ThreadPoolExecutor(2) as executor:
        results.extend(executor.map(one,slots))
    write(OUT/"paired.json",results)
    print("completed",len(results),"version sides; unavailable",sum("infra_error" in r for r in results))


if __name__=="__main__":
    if sys.argv[1]=="worker":
        print(json.dumps(worker(sys.argv[2],Path(sys.argv[3]))))
    elif sys.argv[1]=="freeze":
        freeze()
    elif sys.argv[1]=="run":
        run()
