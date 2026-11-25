"""Paired real executions. Use isolated package directories obtained from the protocol."""
from pathlib import Path
import hashlib
import importlib.metadata as metadata
import json
import platform
import random
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

from workloads import corpus,normalized_html

HERE=Path(__file__).resolve().parent
OUT=HERE.parents[1]/"runs_action_evidence_20261125"
SPEC=OUT/"commonmark-0.31.2.json"
ENV=Path(tempfile.gettempdir())/"eswa-action-audit-20261125"
RELEASES={
    "old":{"mistune":"3.0.2","markdown-it-py":"3.0.0","PyYAML":"6.0.2","ruamel.yaml":"0.17.40"},
    "new":{"mistune":"3.1.3","markdown-it-py":"4.2.0","PyYAML":"6.0.3","ruamel.yaml":"0.18.16"},
}
FILES=["measure.py","workloads.py","audit.py","protocol.md"]


def load(p):
    return json.loads(p.read_text(encoding="utf8"))


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fingerprints():
    return {f:digest(HERE/f) for f in FILES}|{SPEC.name:digest(SPEC)}


def worker(which):
    env=ENV/which
    sys.path.insert(0,str(env))
    import mistune
    from markdown_it import MarkdownIt
    import yaml
    from ruamel.yaml import YAML
    for name,version in (RELEASES[which]|{"mdurl":"0.1.2","ruamel.yaml.clib":"0.2.14"}).items():
        dist=metadata.distribution(name)
        assert dist.version==version and Path(dist.locate_file("")).resolve()==env.resolve(),name
    md_primary=mistune.create_markdown(escape=False,plugins=[])
    md_backup=MarkdownIt("commonmark")
    configs={}
    for v in ("1.1","1.2"):
        reader=YAML(typ="safe",pure=True)
        reader.version=tuple(map(int,v.split(".")))
        configs[v]=reader
    loader=getattr(yaml,"CSafeLoader",yaml.SafeLoader)
    def call(row,route):
        if row["project"]=="Markdown":
            return (md_primary if route=="P" else md_backup.render)(row["text"])
        if route=="P":
            return yaml.load(row["text"],Loader=loader)
        return configs[row["family"][:3]].load(row["text"])

    cases=corpus(load(SPEC))
    rows={r["id"]:{"actual":{},"time":{},"judge":{}} for r in cases}
    rng=random.Random(11252026)
    for repetition in range(6):
        jobs=[(r,a) for r in cases for a in ("P","B")]
        rng.shuffle(jobs)
        for r,a in jobs:
            t=time.perf_counter_ns()
            try:
                value=call(r,a)
                end=time.perf_counter_ns()
                actual=normalized_html(value) if r["project"]=="Markdown" else json.dumps(value,sort_keys=True)
            except Exception as e:
                end=time.perf_counter_ns()
                actual="ERROR "+type(e).__name__+" "+str(e)
            ok=actual==r["gold"]
            finished=time.perf_counter_ns()
            result=rows[r["id"]]
            if repetition==0:
                result["actual"][a]=[ok,actual]
                result["time"][a]=[]
                result["judge"][a]=[]
            else:
                assert result["actual"][a]==[ok,actual],(r["id"],a)
                result["time"][a].append((end-t)/1000)
                result["judge"][a].append((finished-end)/1000)
    return {"yaml_primary_loader":loader.__name__,"records":rows}


if __name__=="__main__":
    if sys.argv[1]=="worker":
        (OUT/(sys.argv[2]+".json")).write_text(json.dumps(worker(sys.argv[2]),ensure_ascii=True),encoding="utf8")
    elif sys.argv[1]=="freeze":
        assert digest(SPEC)=="d431b29d97b6f73e69d547109cf5081578fac931e72afe95639ebe766c1b2a20"
        from workloads import nearest
        cases=corpus(load(SPEC))
        assert len(cases)==len({r["id"] for r in cases})
        for r in cases:
            if r["role"]!="probe":
                nearest(r,[p for p in cases if p["role"]=="probe"])
        lock=OUT/"lock.json"
        if lock.exists(): assert load(lock)["files"]==fingerprints()
        else:
            lock.write_text(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),files=fingerprints(),
                    versions=RELEASES,system=platform.platform(),python=platform.python_version()),indent=2),encoding="utf8")
    else:
        assert load(OUT/"lock.json")["files"]==fingerprints()
        for which in RELEASES:
            subprocess.run([sys.executable,"-I", "-c",
                "import runpy,sys;sys.path.insert(0,sys.argv.pop(1));sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name='__main__')",
                str(HERE),str(HERE/"measure.py"),"worker",which],check=True)

