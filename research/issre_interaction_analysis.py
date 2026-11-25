"""Summarize the frozen experiment and independently replay one disclosed upstream case."""
import json
from pathlib import Path
from statistics import median
import subprocess
import sys
import tempfile
from zipfile import ZipFile

sys.path.insert(0,str(Path(__file__).resolve().parent))
from issre_interaction_frame import OUT, read, write
from issre_interaction_tasks import menus


def hook_worker(root):
    sys.path.insert(0,str(root/"src"))
    import attrs
    assert Path(attrs.__file__).resolve().is_relative_to(root)
    traces = []
    for explicit in (False,True):
        seen = []
        @attrs.define
        class Item:
            value:int = 100
            def __attrs_pre_init__(self,value):
                seen.append(value)
        item = Item(200) if explicit else Item()
        traces.append(dict(explicit=explicit,final=item.value,callback=seen))
    return traces


def hook(rev):
    archive = Path(tempfile.gettempdir())/f"issre-ix-attrs-{rev}.zip"
    with tempfile.TemporaryDirectory() as tmp, ZipFile(archive) as z:
        root = Path(tmp)
        for member in z.namelist():
            parts = member.split("/")[1:]
            if len(parts)>2 and parts[0]=="src" and parts[1] in ("attrs","attr") and member.endswith(".py"):
                path = root.joinpath(*parts)
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(z.read(member))
        proc = subprocess.run([sys.executable,"-I",__file__,"hook",tmp],capture_output=True,
                              text=True,check=True)
        return json.loads(proc.stdout)


def main():
    versions = read(OUT/"paired.json")
    frames = [read(OUT/f) for f in ("sealed_frame.json","sealed_supplement.json")]
    rows = []
    for frame in frames:
        for p,group in frame.items():
            for r in group["selected"]:
                sides = {v["side"]:v for v in versions if v["project"]==p and v["id"]==r["commit"]}
                if set(sides)!={"parent","commit"} or any("infra_error" in v for v in sides.values()):
                    raise RuntimeError(("incomplete paired run",r["commit"]))
                a,b = sides["parent"]["rows"],sides["commit"]["rows"]
                assert len(a)==24 and set(a)==set(b)
                rows.append(dict(project=p,commit=r["commit"],old_fail=[k for k in a if not a[k]["pass"]],
                    new_fail=[k for k in b if not b[k]["pass"]],diff=[k for k in a if a[k]!=b[k]],
                    hits={m:[k for n,c in cells if not a[k:=n+"/"+c]["pass"] and b[k]["pass"]]
                          for m,cells in menus(p).items()}))
    times = {p:{m:median(median(v["plan_ns"][m]) for v in versions if v["project"]==p)/1e6
             for m in ("single","combined","mirror")} for p in {v["project"] for v in versions}}
    case = next(r for r in frames[0]["attrs"]["selected"] if r["commit"].startswith("937b1e2"))
    write(OUT/"findings.json",dict(pairs=rows,plan_ms=times,posthoc_1428={
        side:hook(case[side]) for side in ("parent","commit")}))


if __name__=="__main__":
    if len(sys.argv)>1:
        print(json.dumps(hook_worker(Path(sys.argv[2]))))
    else:
        main()
