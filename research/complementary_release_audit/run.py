"""Frozen admission audit. Python 3.11, markdown-it-py 4.2.0, local bare mirrors."""
import csv
import gzip
import hashlib
import itertools
import json
import math
import os
import platform
import random
import statistics
import subprocess
import sys
import tempfile
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from time import perf_counter_ns as now

import markdown_it
from markdown_it import MarkdownIt

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "runs_complementary_release_20261125"
PROJECTS = [
    ("issre-docblind-markdown.git", "5609061bd3359e882b745de184ebfe5ef1c08011", 18),
    ("issre20261124-rich.git", "3a109ccdffe5b2d0e30684a304fbd388e99ce57b", 36),
]
engine = MarkdownIt("commonmark")
STATES = tuple(itertools.product((False, True), repeat=2))
ACTIONS = ("reuse", "zip", "build")


def digest(data):
    return hashlib.sha256(data).digest()


def render(src):
    return engine.render(src.decode("utf-8-sig")).encode()


def pack(html):
    return gzip.compress(html, compresslevel=6, mtime=0)


def timed(fn, *args):
    start = now()
    value = fn(*args)
    return value, (now() - start) / 1e6


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2), encoding="utf8")


def csv_save(name, rows):
    with (OUT / name).open("w", encoding="utf8", newline="") as fd:
        writer = csv.DictWriter(fd, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


@dataclass
class Artifact:
    rev: str
    src: bytes
    html: bytes
    gz: bytes
    source_key: bytes
    html_key: bytes
    gzip_input_key: bytes
    reference: bytes


def prepare(config):
    repo, head, count = config
    root = Path(os.environ.get("DCEP_GIT_DIR", tempfile.gettempdir())) / repo
    cmd = ["git", "--git-dir", str(root)]
    revs = subprocess.check_output(cmd + ["log", "--first-parent", "--format=%H", f"-{count}", head,
                                          "--", "README.md"]).decode().splitlines()[::-1]
    assert len(revs) == len(set(revs)) == count
    artifacts, metadata_ms = [], 0
    for rev in revs:
        src = subprocess.check_output(cmd + ["show", rev + ":README.md"])
        html = render(src)
        gz = pack(html)
        # The two producers independently fingerprint the bytes each stage wrote or consumed.
        h, dt1 = timed(digest, html)
        z, dt2 = timed(digest, html)
        metadata_ms += dt1 + dt2
        reference = subprocess.check_output([sys.executable, "-c",
            "import sys;from markdown_it import MarkdownIt;"
            "sys.stdout.buffer.write(MarkdownIt('commonmark').render(sys.stdin.buffer.read().decode('utf-8-sig')).encode())"],
            input=src)
        assert html == reference and zlib.decompress(gz, 31) == reference
        artifacts.append(Artifact(rev, src, html, gz, digest(src), h, z, reference))
    cases = []
    for i in range(0, count, 3):
        older, base, nxt = artifacts[i:i + 3]
        for advance, lag in itertools.product((0,1), repeat=2):
            cases.append((i//3, advance, lag, nxt if advance else base, base, older if lag else base))
    return cases, metadata_ms, revs


class Job:
    def __init__(self, src, page, side):
        self.src, self.page, self.side = src, page, side
        self.fresh = None

    def check(self, q):
        if q in ("A", "J") and self.fresh is None:
            self.fresh = digest(self.src.src) == self.page.source_key
        if q == "A":
            return int(self.fresh)
        if q == "B":
            return int(gzip.decompress(self.side.gz) == self.page.html)
        assert q == "J"
        return 2 * int(self.fresh) + int(self.page.html_key == self.side.gzip_input_key)

    def finish(self, act):
        if act == "reuse":
            return self.page.html, self.side.gz
        html = render(self.src.src) if act == "build" else self.page.html
        return html, pack(html)


def observe(state, q):
    a, b = map(int, state)
    return {"A":a, "B":b, "J":2*a+b}[q]


def certified(state, act):
    a, b = state
    return act == "build" or a and (act == "zip" or b)


def calibrate(cases):
    costs = defaultdict(list)
    freq = Counter({s:1 for s in STATES})
    for _, _, _, src, page, side in cases:
        job = Job(src, page, side)
        freq[bool(job.check("A")),bool(job.check("B"))] += 1
        for q in ("A","B","J"):
            for warm in (False,True):
                job = Job(src,page,side)
                if warm:
                    job.check("A")
                _, dt = timed(job.check, q)
                costs[q, warm].append(dt)
        for act in ACTIONS:
            _, dt = timed(job.finish, act)
            costs[act].append(dt)
    return {k:statistics.median(v) for k,v in costs.items()}, freq


def exact(menu, costs, freq):
    @lru_cache(None)
    def solve(states, used):
        options = [(costs[act], act, {}) for act in ACTIONS if all(certified(s,act) for s in states)]
        if len(used) < 2:
            for q in menu:
                if q in used:
                    continue
                groups = defaultdict(list)
                for s in states:
                    groups[observe(s,q)].append(s)
                if len(groups) == 1:
                    continue
                expected = costs[q, "A" in used or "J" in used]
                branches = {}
                for obs, subset in groups.items():
                    value, node = solve(tuple(subset), used+(q,))
                    expected += value * sum(freq[s] for s in subset)/sum(freq[s] for s in states)
                    branches[obs] = node
                options.append((expected,q,branches))
        value, label, children = min(options, key=lambda option:option[0])
        return value, (label, children)
    return solve(STATES, ())


def operate(job, method, tree, dest, oracle_act):
    history = []
    def ask(q):
        v = job.check(q)
        history.append((q,v))
        return v
    if method == "VOI":
        label, branches = tree
        while branches:
            label, branches = branches[ask(label)]
        act = label
    elif method == "A_first":
        act = "build" if not ask("A") else "reuse" if ask("B") else "zip"
    elif method in ("B_first","both"):
        if method == "B_first":
            b, a = ask("B"), ask("A")
        else:
            a, b = ask("A"), ask("B")
        act = "build" if not a else "reuse" if b else "zip"
    elif method == "receipts":
        act = ("build","build","zip","reuse")[ask("J")]
    elif method == "oracle":
        act = oracle_act
    else:
        act = method
    html, gz = job.finish(act)
    (dest / "page.html").write_bytes(html)
    (dest / "page.html.gz").write_bytes(gz)
    return history, act


def main():
    assert markdown_it.__version__ == "4.2.0"
    OUT.mkdir(exist_ok=True)
    if (OUT/"lock.json").exists():
        raise SystemExit("Run already frozen. Copy into a new run root to replicate.")
    save("lock.json",{name:digest((HERE/name).read_bytes()).hex() for name in ("protocol.md","run.py")})
    dev, dm, dr = prepare(PROJECTS[0])
    costs, weights = calibrate(dev)
    modes = {"artifacts":"AB", "receipts":"ABJ"}
    plans = {mode:exact(menu,costs,weights) for mode,menu in modes.items()}
    save("development.json", dict(cost_ms={str(k):v for k,v in costs.items()}, weights={str(k):v for k,v in weights.items()},
         plans=plans, revisions=dr, metadata_ms=dm, python=platform.python_version(), markdown_it=markdown_it.__version__))
    test, tm, tr = prepare(PROJECTS[1])
    save("holdout.json",dict(revisions=tr, metadata_ms=tm))
    rng, rows = random.Random(25112026), []
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp)
        for group, advance, lag, src, page, side in test:
            gold = src.reference
            html_good = page.html == gold
            gz_good = zlib.decompress(side.gz, 31) == gold
            feasible = ["build"] + (["zip"] if html_good else []) + (["reuse"] if html_good and gz_good else [])
            oracle = min(feasible,key=costs.get)
            for mode in modes:
                methods = ["reuse","build","A_first","B_first","both","VOI","oracle"]
                if mode == "receipts":
                    methods.append("receipts")
                records = defaultdict(list)
                for rnd in range(3):
                    rng.shuffle(methods)
                    for method in methods:
                        job = Job(src,page,side)
                        (trace,act),ms = timed(operate,job,method,plans[mode][1],dest,oracle)
                        ok = ((dest/"page.html").read_bytes() == gold and
                              zlib.decompress((dest/"page.html.gz").read_bytes(),31) == gold)
                        if method != "reuse":
                            assert ok
                        records[method].append((trace,act,ok,ms))
                for method, reps in records.items():
                    trace, act, ok, _ = reps[0]
                    assert all(r[:3]==reps[0][:3] for r in reps)
                    online_model = costs[act]
                    warm = False
                    for q,_ in trace:
                        online_model += costs[q,warm]
                        warm |= q in "AJ"
                    rows.append(dict(group=group,advance=advance,lag=lag,revision=src.rev,page=page.rev,gzip=side.rev,
                        mode=mode,method=method,html_ok=int(html_good),gzip_ok=int(gz_good),
                        trace=" ".join(f"{q}{o}" for q,o in trace),checks=len(trace),action=act,ok=int(ok),
                        oracle=oracle,model_ms=online_model,ms=statistics.median(r[3] for r in reps),
                        rounds_ms=" ".join(f"{r[3]:.6f}" for r in reps)))
    csv_save("decisions.csv", rows)
    summary=[]
    for mode, method in sorted({(r["mode"],r["method"]) for r in rows}):
        rr=[r for r in rows if (r["mode"],r["method"])==(mode,method)]
        summary.append(dict(mode=mode,method=method,n=len(rr),correct=sum(r["ok"] for r in rr),
             checks=sum(r["checks"] for r in rr),render=sum(r["action"]=="build" for r in rr),
             compress=sum(r["action"]!="reuse" for r in rr),oracle_actions=sum(r["action"]==r["oracle"] for r in rr),
             ms=round(sum(r["ms"] for r in rr),3),model_ms=round(sum(r["model_ms"] for r in rr),3)))
    csv_save("summary.csv",summary)
    print((OUT/"summary.csv").read_text())


if __name__ == "__main__":
    main()
