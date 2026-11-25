"""Screen locally and reveal only counts until tests and schedules have been frozen."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "runs_interaction_blind_20261124"
PROJECTS = {
    "attrs": ("python-attrs/attrs", "21.4.0", r"^src/attr/(_make|_funcs|validators|converters|_next_gen)\.py$"),
    "dateutil": ("dateutil/dateutil", "2.8.2", r"(^|/)dateutil/(relativedelta|rrule|utils|parser/_parser)\.py$"),
}
KEEP = r"\b(fix(?:es|ed)?|correct(?:ly)?|regression|wrong|incorrect|respect|preserve|restore|bug)\b"
DROP = r"\b(security|cve|redos|xss|vulnerability|attack|dos|injection|untrusted|malicious|overflow|recursion|infinite|crash|hang|leak|typing|annotations?|lint|mypy|ruff|typos?|docs?|docstrings?|ci|dependencies|packaging|release|tests? only)\b"


def git(p, *args):
    db = Path(tempfile.gettempdir()) / ("issre-interaction-" + p + ".git")
    if not db.exists():
        subprocess.run(["git","-c","http.version=HTTP/1.1","clone","--quiet","--filter=blob:none","--bare","--single-branch",
                        "https://github.com/" + PROJECTS[p][0] + ".git",str(db)],check=True)
    return subprocess.check_output(["git","--git-dir=" + str(db),*args])


def write(path, obj):
    path.write_text(json.dumps(obj,indent=1,ensure_ascii=False),encoding="utf8")


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def collect(p, supplemental=False):
    ancestry = "--no-merges" if supplemental else "--first-parent"
    logs = git(p,"log",ancestry,"--since=2022-01-01T00:00:00Z","--until=2025-12-31T23:59:59Z",
               "--format=%H%x1f%P%x1f%ct%x1f%s%x1f%b%x00").decode("utf8","replace")
    rows = []
    for record in logs.split("\0"):
        if not record.strip():
            continue
        commit, parents, when, title, body = record.strip("\n").split("\x1f",4)
        if title.startswith("Merge pull request") and body.strip():
            title = body.strip().splitlines()[0]
        if not re.search(KEEP,title,re.I) or re.search(DROP,title,re.I):
            continue
        parent = parents.split()[0]
        paths = git(p,"diff","--no-renames","--name-only",parent,commit).decode().splitlines()
        if any(re.search(PROJECTS[p][2],path) for path in paths):
            rows.append(dict(commit=commit,parent=parent,title=title,time=int(when)))
    rows.sort(key=lambda row:(row["time"],row["commit"]),reverse=True)
    return {"eligible":len(rows),"selected":rows[:6]}


if __name__ == "__main__":
    from concurrent.futures import ThreadPoolExecutor
    OUT.mkdir(exist_ok=True)
    path = OUT / "sealed_frame.json"
    if not path.exists():
        with ThreadPoolExecutor(2) as executor:
            write(path,dict(zip(PROJECTS,executor.map(collect,PROJECTS))))
    print({p:len(g["selected"]) for p,g in read(path).items()},digest(path))
    extra = OUT / "sealed_supplement.json"
    if not extra.exists():
        write(extra,{p:collect(p,True) for p,g in read(path).items() if not g["selected"]})
    print("supplement",{p:len(g["selected"]) for p,g in read(extra).items()},digest(extra))
