from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
import subprocess
import tempfile
from issre_interaction_frame import KEEP,DROP,read,write,digest

HERE = Path(__file__).resolve().parent
OUT = HERE.parent/"runs_order_contract_20261124"
PROJECTS = {"transitions":("pytransitions/transitions","0.9.0"),"statemachine":("fgmacedo/python-statemachine","v2.3.0")}
DOC = re.compile(r"^(?:readme\.(?:md|rst)|docs?/(?:.*/)?(?:actions?|callbacks?|lifecycle|processing(?:_model)?|execution(?:_order)?)\.(?:md|rst))$",re.I)


def git(p,*args):
    db = Path(tempfile.gettempdir())/f"issre-order-{p}.git"
    if not db.exists():
        subprocess.run(["git","clone","--bare","--quiet","--filter=blob:none","--single-branch",
                        "https://github.com/"+PROJECTS[p][0]+".git",str(db)],check=True)
    return subprocess.check_output(["git","--git-dir="+str(db),*args])


def collect(p):
    history = git(p,"log","--no-merges","--since=2024-08-01T00:00:00Z","--until=2025-12-31T23:59:59Z",
                  "--format=%H%x1f%P%x1f%ct%x1f%s").decode()
    rows=[]
    for line in history.splitlines():
        rev,parent,when,title=line.split("\x1f",3)
        if not re.search(KEEP,title,re.I) or re.search(DROP,title,re.I): continue
        files = git(p,"diff","--name-only","--no-renames",parent,rev).decode().splitlines()
        if any(n.startswith((p+"/","src/"+p+"/")) and n.endswith(".py") for n in files):
            rows.append(dict(commit=rev,parent=parent,title=title,time=int(when)))
    rows.sort(key=lambda r:(r["time"],r["commit"]),reverse=True)
    return dict(eligible=len(rows),selected=rows[:3])


if __name__=="__main__":
    OUT.mkdir(exist_ok=True)
    if not (OUT/"extractor_lock.json").exists():
        with ThreadPoolExecutor(2) as pool:
            write(OUT/"sealed.json",dict(zip(PROJECTS,pool.map(collect,PROJECTS))))
        files=[HERE/n for n in ("issre_order_frame.py","issre_order_extract.py","ISSRE_ORDER_PROTOCOL_20261124_ZH.md","issre_interaction_frame.py")]+[OUT/"sealed.json"]
        write(OUT/"extractor_lock.json",{f.name:digest(f) for f in files})
    print("locked",digest(OUT/"extractor_lock.json"),{p:len(s["selected"]) for p,s in read(OUT/"sealed.json").items()})

