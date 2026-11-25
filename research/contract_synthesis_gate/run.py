import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
from sample import HERE, OUT, git, save


def load(name):
    return json.loads((OUT/name).read_text(encoding="utf8"))


def main():
    samples=load("sample.json")
    checks, tasks=load("checks.json"),load("tasks.json")
    inputs=list(HERE.glob("*.py"))+[HERE/"protocol.md"]+list(OUT.glob("*.txt"))+[
        OUT/name for name in ("sample.json","screening.json","checks.json","tasks.json")]
    fingerprints={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    if (OUT/"lock.json").exists():
        assert load("lock.json")==fingerprints
    else:
        save("lock.json",fingerprints)
    if (OUT/"observations.json").exists():
        raise SystemExit("Frozen observations already exist.")
    results={}
    for s in samples:
        proj=s["project"]
        results[s["id"]]={}
        for arm in ("parent","rev"):
            with tempfile.TemporaryDirectory() as tmp:
                package="num2words" if proj=="num2words" else "slugify"
                archive=git(proj,"archive","--format=zip",s[arm],"--",package)
                with zipfile.ZipFile(io.BytesIO(archive)) as stream:
                    for member in stream.namelist():
                        assert (Path(tmp)/member).resolve().is_relative_to(Path(tmp))
                    stream.extractall(tmp)
                payload=dict(project=proj,checks=checks[s["id"]],tasks=[r[:2] for r in tasks[proj]])
                raw=subprocess.run([sys.executable,"-I",str(HERE/"worker.py"),tmp],input=json.dumps(payload),
                    cwd=tmp,text=True,capture_output=True,timeout=60)
                result=json.loads(raw.stdout) if not raw.returncode else {"runtime_error":raw.stderr[-1500:]}
                results[s["id"]][arm]=result
    save("observations.json",results)
    print({k:{side:(v.get("import_error") or v.get("runtime_error") or "ok") for side,v in pair.items()} for k,pair in results.items()})


if __name__=="__main__":
    main()
