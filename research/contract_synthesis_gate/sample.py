import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "runs_contract_synthesis_gate_20261125"
PROJECTS = {
    "num2words": ("07814cb114157f582c40a00119c2e9faba8dcee2", "num2words/lang_EN.py"),
    "python-slugify": ("4b6b5b42f050f1ce96899e015247d5e3901cc433", "slugify/slugify.py"),
}


def git(project, *args):
    path = Path(os.environ.get("CGVS_MIRRORS", tempfile.gettempdir())) / f"eswa-contract-{project}.git"
    return subprocess.check_output(["git", "--git-dir", str(path), *args])


def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=True, indent=2), encoding="utf8")


def sample():
    OUT.mkdir(exist_ok=True)
    samples, screened = [], []
    for proj, (head, path) in PROJECTS.items():
        found = 0
        for line in git(proj, "log", "--before=2026-01-01T00:00:00Z", "--no-merges", "--format=%H%x09%s", head, "--", path).decode().splitlines():
            rev, title = line.split("\t", 1)
            accept = bool(re.search(r"\b(fix\w*|bug\w*|incorrect\w*|wrong\w*)\b",title,re.I)) and not re.search(
                r"\b(security|CVE|vulnerab\w*|dependencies|dependency|packaging|CI|docs?|documentation|typos?)\b",title,re.I)
            screened.append(dict(project=proj,rev=rev,eligible=accept))
            if not accept:
                continue
            parent = git(proj,"rev-parse",rev+"^1").decode().strip()
            files = git(proj,"ls-tree","--name-only",parent).decode().splitlines()
            readme = next(n for n in ("README.md","README.rst","README") if n in files)
            raw = git(proj,"show",parent+":"+readme).decode("utf-8-sig")
            lines=[]
            for s in raw.splitlines():
                if re.match(r"^\s*#*\s*(changelog|change log|release notes|changes|history)\s*[:#]*\s*$",s,re.I):
                    break
                lines.append(s)
            key=f"{proj}-{found+1}"
            doc="\n".join(lines)+"\n"
            (OUT / (key+".txt")).write_text(doc, encoding="utf8")
            samples.append(dict(id=key,project=proj,rev=rev,parent=parent,readme=readme,
                                doc_hash=hashlib.sha256((OUT/(key+".txt")).read_bytes()).hexdigest()))
            found+=1
            if found==3:
                break
    save("sample.json",samples)
    save("screening.json",screened)
    print([(s["id"],s["readme"]) for s in samples])


if __name__=="__main__":
    sample()
