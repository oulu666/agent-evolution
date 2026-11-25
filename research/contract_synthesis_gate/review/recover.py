"""Run the unchanged blind policies through a Python 2 JSON bridge on the two unavailable pairs."""
from contextlib import contextmanager
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sample import OUT,git,save
from worker import run

runtime=Path(sys.executable).resolve().parents[1]
exe=runtime/"pypy2.7-v8.0.1-win64/pypy.exe"
bridge="""
import sys,json
sys.path[:0]=sys.argv[1:3]
n=sys.argv[3]
f=getattr(__import__(n),n)
for line in sys.stdin:
    x,kw=json.loads(line)
    try:
        r=f(x,**dict((k.encode('ascii'),v) for k,v in kw.items()))
        if isinstance(r,str): r=r.decode('utf8')
        reply=['ok',r]
    except Exception as e:
        reply=['err',type(e).__name__]
    print json.dumps(reply)
    sys.stdout.flush()
"""


@contextmanager
def historical(s,arm):
    pkg="num2words" if s["project"]=="num2words" else "slugify"
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(io.BytesIO(git(s["project"],"archive","--format=zip",s[arm],"--",pkg))) as z:
            z.extractall(tmp)
        pr=subprocess.Popen([str(exe),"-S","-c",bridge,tmp,str(runtime/"py2deps"),pkg],stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=tmp,text=True)
        def f(x,**kw):
            pr.stdin.write(json.dumps([x,kw])+"\n")
            pr.stdin.flush()
            text=pr.stdout.readline()
            if not text:
                raise RuntimeError(pr.stderr.read())
            status,v=json.loads(text)
            if status=="err":
                raise type(v,(Exception,),{})()
            return v
        try:
            yield f
        finally:
            pr.stdin.close()
            if pr.wait()!=0:
                raise RuntimeError(pr.stderr.read())


def load(n):
    return json.loads((OUT/n).read_text())


if __name__=="__main__":
    obs=load("observations.json")
    results,diagnostic={},{}
    for s in load("sample.json"):
        if "assertions" in obs[s["id"]]["parent"]:
            continue
        key=s["id"]
        results[key]={}
        diagnostic[key]={}
        for arm in ("parent","rev"):
            with historical(s,arm) as fn:
                results[key][arm]=run(fn,s["project"],load("checks.json")[key],[t[:2] for t in load("tasks.json")[s["project"]]])
                if s["project"]=="num2words":
                    diagnostic[key][arm]=fn(199)
                else:
                    diagnostic[key][arm]=[fn("jaja---lol-méméméoo--a",max_length=n,word_boundary=True) for n in (17,18,19)]
    save("compatibility_observations.json",results)
    save("revealed_witnesses.json",diagnostic)
