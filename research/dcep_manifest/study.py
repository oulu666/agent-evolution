"""One-probe planning for real Git manifest deliveries. Run with Python 3.11+."""
import csv
import hashlib
import json
import math
import os
import random
import statistics
import subprocess
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from time import perf_counter_ns as clock

HERE = Path(__file__).resolve().parent
OUT = HERE.parents[1] / "runs_dcep_manifest_20261125"
PROJECTS = [
    ("issre-docblind-tqdm.git", "9cf5a12b1f955468a17f0ba3c59092b23e4258ac", "tqdm"),
    ("issre-order-transitions.git", "bd42b38f3627e6bca7274fb4d9af2e105f75da7c", "transitions"),
]
FIELDS = (1, 2, 4)
TASKS = (1, 2, 3, 7)
PROBES = (7, 1, 2, 4)
DEFER = -1
METHODS = ("reuse", "refresh", "no_probe", "fixed", "uncertainty", "risk_cache",
           "native_batch", "voi", "dcep", "voi_cached", "dcep_cached", "feedback_blind")


def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2), encoding="utf8")


def elapsed(start):
    return (clock() - start) / 1e6


class Git:
    def __init__(self, config):
        repo, head, source = config
        self.names = (source, "tests", "examples")
        self.cmd = ["git", "--git-dir", str(Path(os.environ.get("DCEP_GIT_DIR", tempfile.gettempdir())) / repo)]
        self.proc = subprocess.Popen(self.cmd + ["cat-file", "--batch"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        lines = self.git("log", "-80", "--first-parent", "--format=%H %T", head).decode().splitlines()[::-1]
        assert len(lines) == 80 and lines[-1].split()[0] == head
        self.pairs = [(a.split(), b.split()) for a, b in zip(lines[::2], lines[1::2])]

    def git(self, *args):
        return subprocess.check_output(self.cmd + list(args))

    def tree(self, oid):
        self.proc.stdin.write(oid.encode() + b"\n")
        self.proc.stdin.flush()
        returned, kind, size = self.proc.stdout.readline().split()
        assert kind == b"tree" and returned.decode() == oid
        raw = self.proc.stdout.read(int(size))
        assert self.proc.stdout.read(1) == b"\n"
        rows = []
        index = 0
        while index < len(raw):
            end = raw.index(b"\0", index)
            mode, name = raw[index:end].split(b" ", 1)
            rows.append((mode.decode(), name.decode(), raw[end+1:end+21].hex()))
            index = end + 21
        return rows

    def reference(self, rev):
        ans = {f: [] for f in FIELDS}
        for line in self.git("ls-tree", "-r", "-z", rev, "--", *self.names).split(b"\0"):
            if line:
                meta, path = line.decode().split("\t", 1)
                mode, _, oid = meta.split()
                directory, rel = path.split("/", 1)
                ans[FIELDS[self.names.index(directory)]].append([rel, mode, oid])
        return {f: sorted(rows) for f, rows in ans.items()}

    def close(self):
        self.proc.stdin.close()
        assert self.proc.wait() == 0
        self.proc.stdout.close()


class Snapshot:
    def __init__(self, git, root):
        self.git, self.root, self.cache = git, root, {}

    def tree(self, oid):
        if oid not in self.cache:
            self.cache[oid] = self.git.tree(oid)
        return self.cache[oid]

    def ids(self):
        dirs = {name: oid for mode, name, oid in self.tree(self.root) if mode == "40000"}
        return {f: dirs.get(n) for f, n in zip(FIELDS, self.git.names)}

    def observe(self, p, old):
        now = self.ids()
        return sum(f for f in FIELDS if p & f and now[f] != old[f])

    def section(self, oid, prefix=""):
        rows = []
        for mode, name, child in self.tree(oid) if oid else ():
            if mode == "40000":
                rows.extend(self.section(child, prefix + name + "/"))
            else:
                rows.append([prefix + name, mode, child])
        return sorted(rows)

    def deliver(self, task, action, old, dest):
        if action == DEFER:
            return
        ids = self.ids() if action else {}
        rows = {f: self.section(ids[f]) if action & f else old[f] for f in FIELDS if task & f}
        dest.write_bytes(json.dumps(rows, separators=(",", ":")).encode())


def actions(task):
    return [a for a in range(8) if a & task == a] + [DEFER]


def calibrate(git, dest):
    counts, durations = Counter(), defaultdict(list)
    for parent, child in git.pairs:
        ids = Snapshot(git, parent[1]).ids()
        old = git.reference(parent[0])
        for _, root in (parent, child):
            counts[Snapshot(git, root).observe(7, ids)] += 1
            for p in PROBES:
                snap = Snapshot(git, root)
                start = clock()
                snap.observe(p, ids)
                durations["p", p].append(elapsed(start))
            for task in TASKS:
                for a in actions(task):
                    for warm in (False, True):
                        snap = Snapshot(git, root)
                        if warm:
                            snap.observe(7, ids)
                        start = clock()
                        snap.deliver(task, a, old, dest)
                        durations[task, a, warm].append(elapsed(start))
    return [(counts[s] + 1) / (sum(counts.values()) + 8) for s in range(8)], {
        k: statistics.median(v) for k, v in durations.items()}


def make_plan(task, method, prior, costs):
    # The only path from a changed section to loss is through a requested, unrepaired field.
    offers = actions(task)
    def loss(a, s, warm):
        penalty = 5 if a == DEFER else 10 * bool(s & task & ~a)
        return penalty + costs[task, a, warm]

    groups = edges = skipped = 0
    def best(states, warm):
        nonlocal groups, edges
        groups += 1
        edges += len(states) * len(offers)
        return min((sum(prior[s] * loss(a, s, warm) for s in states), a) for a in offers)

    states = list(range(8))
    value, base = best(states, False)
    p0, fallback = 0, {0: base}
    if method == "reuse":
        fallback = {0: 0}
    elif method == "refresh":
        fallback = {0: task}
    elif method == "native_batch":
        return 7, {s: task & s for s in states}, base, (0, 0, 0)
    elif method not in ("no_probe",):
        menu = list(PROBES)
        def buckets(p):
            return {o: [s for s in states if s & p == o] for o in sorted({s & p for s in states})}
        if method == "fixed":
            menu = [1]
        if method == "risk_cache":
            menu = [max((f for f in FIELDS if f & task), key=lambda f: sum(prior[s] for s in states if s & f))]
        if method == "uncertainty":
            def entropy(p):
                probs = [sum(prior[s] for s in group) for group in buckets(p).values()]
                return -sum(w * math.log(w) for w in probs)
            menu = [max(PROBES, key=entropy)]
        forced = method in ("fixed", "risk_cache", "uncertainty")
        for p in menu:
            if method == "dcep" and p != 7 and costs["p", 7] <= costs["p", p]:
                # Batch refines this partition and leaves the same root in the exact cache.
                skipped += 1
                continue
            price = costs["p", p]
            choice = {}
            for o, subset in buckets(p).items():
                if method == "dcep":
                    # Collapse states with identical action-loss vectors within this observation only.
                    weight = Counter()
                    for s in subset:
                        weight[s & task] += prior[s]
                    groups += 1
                    edges += len(weight) * len(offers)
                    subtotal, a = min((sum(w * loss(act, key, True) for key, w in weight.items()), act)
                                      for act in offers)
                else:
                    subtotal, a = best(subset, True)
                price += subtotal
                choice[o] = a
            if forced or price < value - 1e-10:
                p0, fallback, value = p, choice, price
    return p0, fallback, base, (groups, edges, skipped)


def main():
    OUT.mkdir(exist_ok=True)
    lock = {f: hashlib.sha256((HERE / f).read_bytes()).hexdigest() for f in ("protocol.md", "study.py")}
    if (OUT / "lock.json").exists():
        assert json.loads((OUT / "lock.json").read_text()) == lock
    else:
        save("lock.json", lock)
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "manifest.json"
        dev = Git(PROJECTS[0])
        try:
            prior, costs = calibrate(dev, dest)
        finally:
            dev.close()
        save("calibration.json", {"prior": prior, "median_ms": {str(k): v for k,v in costs.items()}})
        git = Git(PROJECTS[1])
        results, memo = [], {}
        rng = random.Random(20261125)
        try:
            for i, (parent, child) in enumerate(git.pairs):
                ids, old = Snapshot(git, parent[1]).ids(), git.reference(parent[0])
                for side, (rev, root) in enumerate((parent, child)):
                    reference = git.reference(rev)
                    truth = sum(f for f in FIELDS if old[f] != reference[f])
                    for task in TASKS:
                        target = {str(f): reference[f] for f in FIELDS if f & task}
                        methods = list(METHODS)
                        rng.shuffle(methods)
                        for method in methods:
                            snap = Snapshot(git, root)
                            start = clock()
                            key = method, task
                            hit = method.endswith("_cached") and key in memo
                            if hit:
                                plan = memo[key]
                            elif method in ("reuse", "refresh", "native_batch"):
                                a = task if method == "refresh" else 0
                                plan = ((7, {s: task & s for s in range(8)}, 0, (0,0,0))
                                        if method == "native_batch" else (0, {0:a}, a, (0,0,0)))
                            else:
                                name = method.removesuffix("_cached")
                                plan = make_plan(task, "dcep" if name == "feedback_blind" else name, prior, costs)
                                if method.endswith("_cached"):
                                    memo[key] = plan
                            p, choices, base, work = plan
                            if method == "feedback_blind" and p:
                                # A warmed root can alter the optimal no-feedback action's execution cost.
                                base = min((sum(prior[s] * (5 if a == DEFER else 10 * bool(s & task & ~a))
                                                for s in range(8)) + costs[task, a, True], a)
                                           for a in actions(task))[1]
                            planning = elapsed(start)
                            obs = snap.observe(p, ids) if p else 0
                            a = base if method == "feedback_blind" else choices[obs]
                            snap.deliver(task, a, old, dest)
                            total = elapsed(start)
                            correct = a != DEFER and json.loads(dest.read_bytes()) == target
                            status = "deferred" if a == DEFER else "ok" if correct else "wrong"
                            assert (a == DEFER or correct == (truth & task & ~a == 0))
                            results.append(dict(pair=i,parent=parent[0],rev=rev,side=side,task=task,method=method,
                                truth=truth,probe=p,observation=obs,action=a,prior_action=base,status=status,
                                changed=int(bool(p) and a!=base),reads=len(snap.cache),plan_ms=planning,total_ms=total,
                                loss_terms=0 if hit else work[1],pruned=0 if hit else work[2]))
        finally:
            git.close()
    with (OUT / "decisions.csv").open("w", newline="", encoding="utf8") as fd:
        w = csv.DictWriter(fd, fieldnames=list(results[0]))
        w.writeheader()
        w.writerows(results)
    summary = {}
    for method in METHODS:
        rows = [r for r in results if r["method"] == method]
        summary[method] = dict(status=dict(Counter(r["status"] for r in rows)), probes=sum(bool(r["probe"]) for r in rows),
                               **{k: round(sum(r[k] for r in rows), 4) for k in
                                  ("changed","reads","plan_ms","total_ms","loss_terms","pruned")})
    save("summary.json", summary)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
