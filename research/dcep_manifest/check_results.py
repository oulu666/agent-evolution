"""Verify the frozen run against Git diffs independently of the manifest generator."""
import csv
import hashlib
import json
import os
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

here = Path(__file__).resolve().parent
out = here.parents[1] / "runs_dcep_manifest_20261125"
lock = json.loads((out / "lock.json").read_text())
assert all(hashlib.sha256((here / k).read_bytes()).hexdigest() == v for k, v in lock.items())
with (out / "decisions.csv").open(newline="") as stream:
    rows = list(csv.DictReader(stream))
arms = {}
for row in rows:
    key = tuple(int(row[k]) for k in ("pair", "side", "task"))
    arm = arms.setdefault(row["method"], {})
    assert key not in arm
    arm[key] = row
assert len(arms) == 12 and all(len(v) == 320 for v in arms.values())
path = Path(os.environ.get("DCEP_GIT_DIR", tempfile.gettempdir())) / "issre-order-transitions.git"
folders = {"transitions": 1, "tests": 2, "examples": 4}
flip_tasks = flip_pairs = 0
for i in range(40):
    facts = arms["dcep"][i, 1, 7]
    command = ["git", "--git-dir", str(path)]
    assert subprocess.check_output(command + ["rev-parse", facts["rev"]+"^1"]).decode().strip() == facts["parent"]
    files = subprocess.check_output(command + ["diff", "--no-renames", "--name-only", "-z", facts["parent"], facts["rev"]])
    dirs = {s.decode().partition("/")[0] for s in files.split(b"\0") if s}
    changed = sum(f for name, f in folders.items() if name in dirs)
    flips = 0
    for task in (1, 2, 3, 7):
        before, after = (arms["dcep"][i, side, task] for side in (0, 1))
        assert before["probe"] == after["probe"]
        flips += before["action"] != after["action"]
        for side in (0, 1):
            key = i, side, task
            mask = changed if side else 0
            for arm in arms.values():
                row = arm[key]
                a, p = int(row["action"]), int(row["probe"])
                assert int(row["truth"]) == mask and int(row["observation"]) == mask & p
                status = "deferred" if a == -1 else "wrong" if mask & task & ~a else "ok"
                assert row["status"] == status
            ds = arms["dcep"][key]
            for method in ("voi", "voi_cached", "dcep_cached"):
                assert all(ds[k] == arms[method][key][k] for k in ("probe", "action", "status", "reads"))
            assert ds["action"] == arms["native_batch"][key]["action"]
    flip_tasks += flips
    flip_pairs += bool(flips)
summary = json.loads((out / "summary.json").read_text())
for method, entries in arms.items():
    values = list(entries.values())
    assert Counter(r["status"] for r in values) == summary[method]["status"]
    for k in ("reads", "loss_terms", "pruned", "changed"):
        assert sum(int(r[k]) for r in values) == summary[method][k]
    for k in ("plan_ms", "total_ms"):
        assert abs(sum(float(r[k]) for r in values) - summary[method][k]) < 0.0001
print(f"{len(rows)} verified policy rows, {flip_tasks}/160 paired task changes across {flip_pairs}/40 transitions")
