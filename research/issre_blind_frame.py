"""Deterministic mechanical screening; emit only counts and a digest before the test freeze."""
from pathlib import Path
import datetime as dt
import hashlib
import json
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runs_blind_pairs_20261124'
PROJECTS={
    'click':('pallets/click','8.0.3',r'^src/click/(core|types|parser|testing|formatting|termui)\.py$'),
    'markdown':('Python-Markdown/markdown','3.3.6',r'^markdown/(core|blockparser|blockprocessors|inlinepatterns|serializers|preprocessors|extensions/(tables|fenced_code|footnotes|toc))\.py$'),
    'tqdm':('tqdm/tqdm','v4.62.3',r'^tqdm/(std|utils)\.py$'),
}
INCLUDE=r'\b(fix(?:es|ed)?|correct(?:ly)?|regression|wrong|incorrect|respect|preserve|restore)\b'
EXCLUDE=r'\b(security|cve|redos|xss|vulnerability|attack|dos|injection|escape sequences|untrusted|malicious|overflow|recursion|infinite|crash|hang|leak|lint|typing|mypy|ruff|typos?|docs?|docstrings?|ci|dependencies|packaging|release|tests? only)\b'


def git(project,*args):
    db=Path(tempfile.gettempdir())/('issre-docblind-'+project+'.git')
    if not db.exists():
        repo=PROJECTS[project][0]
        subprocess.run(['git','clone','--bare','--single-branch','--quiet',
                        f'https://github.com/{repo}.git',str(db)],check=True)
    return subprocess.check_output(['git','--git-dir='+str(db),*args])


def capture(project):
    pattern=PROJECTS[project][2]
    raw=git(project,'log','--first-parent','--since=2022-01-01T00:00:00Z',
            '--until=2024-12-31T23:59:59Z','--format=%H%x1f%P%x1f%ct%x1f%s%x1f%b%x00').decode('utf8','replace')
    eligible=[]
    for record in raw.split('\0'):
        if not record.strip(): continue
        commit,parents,when,title,body=record.strip('\n').split('\x1f',4)
        if title.startswith('Merge pull request') and body.strip():
            title=body.strip().splitlines()[0]
        if not re.search(INCLUDE,title,re.I) or re.search(EXCLUDE,title,re.I): continue
        parent=parents.split()[0]
        paths=git(project,'diff','--name-only',parent,commit).decode().splitlines()
        if not any(re.search(pattern,p) for p in paths): continue
        eligible.append(dict(commit=commit,parent=parent,time=int(when),title=title))
    eligible.sort(key=lambda x:(x['time'],x['commit']),reverse=True)
    return dict(eligible=len(eligible),selected=eligible[:5])


def persist(path,obj):
    path.write_text(json.dumps(obj,indent=1,ensure_ascii=False),encoding='utf8')


if __name__=='__main__':
    from concurrent.futures import ThreadPoolExecutor
    OUT.mkdir(exist_ok=True)
    envelope=OUT/'sealed_frame.json'
    if not envelope.exists():
        with ThreadPoolExecutor(3) as ex:
            result=dict(zip(PROJECTS,ex.map(capture,PROJECTS)))
        persist(envelope,result)
    data=json.loads(envelope.read_text(encoding='utf8'))
    digest=hashlib.sha256(envelope.read_bytes()).hexdigest()
    print({k:len(v['selected']) for k,v in data.items()},digest)
