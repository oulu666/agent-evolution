"""Audit saved decisions and paired work; no re-execution or refitting of policies."""
import csv
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

here = Path(__file__).resolve().parent
out = here.parents[1] / "runs_complementary_release_20261125"
locked = json.loads((out/"lock.json").read_text())
assert all(hashlib.sha256((here/n).read_bytes()).hexdigest() == h for n,h in locked.items())
with (out/"decisions.csv").open(newline="") as f:
    rows = list(csv.DictReader(f))
with (out/"summary.csv").open(newline="") as f:
    totals = list(csv.DictReader(f))
dev = json.loads((out/"development.json").read_text())
arms = defaultdict(dict)
for r in rows:
    k = tuple(int(r[n]) for n in ("group","advance","lag"))
    arm = arms[r["mode"],r["method"]]
    assert k not in arm
    arm[k] = r
    h, g = int(r["html_ok"]), int(r["gzip_ok"])
    expected = bool(h and g) if r["action"]=="reuse" else bool(h) if r["action"]=="zip" else True
    assert expected == bool(int(r["ok"]))
    options = ["build"] + (["zip"] if h else []) + (["reuse"] if h and g else [])
    assert r["oracle"] == min(options, key=dev["cost_ms"].get)
    assert abs(float(r["ms"]) - statistics.median(map(float,r["rounds_ms"].split()))) < 1e-5
assert len(rows)==720 and len(arms)==15 and all(len(v)==48 for v in arms.values())
for t in totals:
    arm = list(arms[t["mode"],t["method"]].values())
    assert int(t["correct"])==sum(int(r["ok"]) for r in arm)
    assert int(t["checks"])==sum(len(r["trace"].split()) for r in arm)
    assert abs(float(t["ms"])-sum(float(r["ms"]) for r in arm)) < .00051
for mode, baseline in (("artifacts","A_first"),("receipts","receipts")):
    voi, fixed = arms[mode,"VOI"], arms[mode,baseline]
    assert all((r["action"],r["trace"])==(fixed[k]["action"],fixed[k]["trace"]) for k,r in voi.items())
    print(mode, "oracle differences", [(k,r["action"],r["oracle"]) for k,r in voi.items() if r["action"]!=r["oracle"]])
    print(mode, Counter((r["trace"],r["action"]) for r in voi.values()))
for mode,lft,rgt in (("artifacts","A_first","B_first"),("artifacts","A_first","VOI"),("receipts","receipts","VOI")):
    left,right=arms[mode,lft],arms[mode,rgt]
    diff=[sum(float(right[k]["ms"])-float(left[k]["ms"]) for k in left if k[0]==g) for g in range(12)]
    print(mode, lft, "vs", rgt, "groups faster",sum(d>0 for d in diff),"median ms saved",round(statistics.median(diff),3))
print("Verified",len(rows),"condition-policy rows,",3*len(rows),"deliveries")
