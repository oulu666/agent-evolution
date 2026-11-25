"""Post-reveal scope witness and independent checks of published denominators."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from prepare import HERE,OUT,git,save


def load(name):
    return json.loads((OUT/name).read_text())


def main():
    for name,h in load("lock.json").items():
        path=HERE/name if (HERE/name).is_file() else OUT/name
        assert hashlib.sha256(path.read_bytes()).hexdigest()==h
    raw=load("raw.json")
    labels=load("scorer.json")["labels"]
    assert len(raw)==8 and all(result==labels for result in raw.values())
    for m,v in load("delivery.json").items():
        assert sum(v["quarantine"].values())==192
        if m!="defer":
            assert v["quarantine"]=={"ok":192}
    sample=next(s for s in load("sample.json") if s["rev"].startswith("da55cf1"))
    # The upstream repair concerns a range expression, outside the frozen action.
    code="""import json,sys
sys.path.insert(0,sys.argv[1])
from semantic_version import Version,NpmSpec
s=NpmSpec('>1.2.3-alpha <1.2.3-beta')
print(json.dumps([s.match(Version(v)) for v in json.load(sys.stdin)]))
"""
    versions=["1.2.3-alpha.0","1.2.3-alpha.1","1.2.3","1.2.3-beta.0","1.2.3-bravo"]
    record=dict(inputs=versions,expected=[True,True,False,False,False])
    for arm in ("parent","rev"):
        with tempfile.TemporaryDirectory() as tmp:
            with zipfile.ZipFile(io.BytesIO(git(sample["project"],"archive","--format=zip",sample[arm],"--","semantic_version"))) as z:
                z.extractall(tmp)
            rawout=subprocess.check_output([sys.executable,"-I","-c",code,tmp],cwd=tmp,input=json.dumps(versions).encode())
            record[arm]=json.loads(rawout)
    save("post_reveal_range.json",record)
    print("Verified frozen inputs, 8 snapshots, 192 tasks per policy; post-reveal:",record)


if __name__=="__main__":
    main()
