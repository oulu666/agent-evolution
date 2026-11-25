"""Freeze a new cohort. Only emit project counts before the study lock."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
import subprocess
import tempfile
from issre_interaction_frame import KEEP, DROP, read, write, digest

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "runs_contract_boundary_20261124"
PROJECTS = {
    "blinker": ("pallets-eco/blinker", "1.6.2", "1.6.1"),
    "pluggy": ("pytest-dev/pluggy", "1.3.0", "1.2.0"),
}


def git(p, *args):
    db = Path(tempfile.gettempdir())/f"issre-boundary-{p}.git"
    if not db.exists():
        subprocess.run(["git","clone","--quiet","--bare","--single-branch",
                        f"https://github.com/{PROJECTS[p][0]}.git",str(db)],check=True)
    return subprocess.check_output(["git","--git-dir="+str(db),*args])


def collect(p):
    history = git(p,"log","--no-merges","--since=2023-10-01T00:00:00Z",
                  "--until=2025-12-31T23:59:59Z","--format=%H%x1f%P%x1f%ct%x1f%s").decode()
    matches = []
    for line in history.splitlines():
        rev,parent,when,title = line.split("\x1f",3)
        if not re.search(KEEP,title,re.I) or re.search(DROP,title,re.I):
            continue
        names = git(p,"diff","--name-only","--no-renames",parent,rev).decode().splitlines()
        if any(n.startswith(f"src/{p}/") and n.endswith(".py") for n in names):
            matches.append(dict(commit=rev,parent=parent,time=int(when),title=title))
    matches.sort(key=lambda r:(r["time"],r["commit"]),reverse=True)
    return {"eligible":len(matches),"selected":matches[:6]}


if __name__=="__main__":
    OUT.mkdir(exist_ok=True)
    path = OUT/"sealed.json"
    if not path.exists():
        with ThreadPoolExecutor(2) as pool:
            write(path,dict(zip(PROJECTS,pool.map(collect,PROJECTS))))
    print({p:(v["eligible"],len(v["selected"])) for p,v in read(path).items()},digest(path))
