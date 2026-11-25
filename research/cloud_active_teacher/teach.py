"""Training environment and budget controllers. Only ask() returns teacher labels."""
from collections import Counter
import heapq
import random
import sqlite3

from benchmark import digest, execute, intervene

MENU = ("double", "even", "odd", "sample", "edit0", "edit1", "edit2", "edit3")
OLD = ("subset", "shuffle")


def world(rows, plans, tid, name):
    if name == "original":
        return rows
    if name in OLD:
        return intervene(rows, digest(tid + "/" + name), name)
    rng = random.Random(digest(tid + "/teacher/" + name))
    if name == "double":
        return rows + rows
    if name in ("even", "odd", "sample"):
        extra = rows[::2] if name == "even" else rows[1::2]
        if name == "sample":
            extra = [r for r in rows if rng.random() < .35]
        return rows + extra
    columns = list(dict.fromkeys(p[0] for p in plans))
    if name == "audit":
        # A separate environment retaining every original row.
        cols = rng.sample(range(len(rows[0])), min(2, len(rows[0])))
        source = list(reversed(rows[::2]))
    else:
        idx = int(name[-1])
        cols = [columns[idx % len(columns)]]
        source = rows if idx < 2 else rows[::2]
    extra = []
    for row in source:
        donor = rng.choice(rows)
        copy = list(row)
        for col in cols:
            copy[col] = donor[col]
        extra.append(tuple(copy))
    return rows + extra


def run_table(rows, types, plans):
    db = sqlite3.connect(":memory:")
    try:
        db.execute("CREATE TABLE t (" + ",".join(f"c{i} {t}" for i, t in enumerate(types)) + ")")
        db.executemany("INSERT INTO t VALUES (" + ",".join("?" for _ in types) + ")", rows)
        return [execute(db, plan) for plan in plans]
    finally:
        db.close()


class Classroom:
    def __init__(self, task, shared):
        self.task = task
        self.shared = shared
        self.live = list(range(len(task["plans"])))
        self.history = []
        self.local_queries = 0
        self.inspected = set()
        self.ask("original")

    def predictions(self, name):
        t = self.task
        key = (t["table"], name)
        if name not in self.inspected:
            self.inspected.add(name)
            self.local_queries += len(t["plans"])
        if key not in self.shared:
            rows = world(t["rows"], t["plans"], t["table"], name)
            answers = run_table(rows, t["types"], t["plans"])
            ids = {}
            parts = [ids.setdefault(ans, len(ids)) for ans in answers]
            self.shared[key] = (parts, ids)
        return self.shared[key][0]

    def ask(self, name):
        assert name not in self.history
        t = self.task
        parts = self.predictions(name)
        rows = world(t["rows"], t["plans"], t["table"], name)
        answer, = run_table(rows, t["types"], [t["gold"]])
        label = self.shared[t["table"], name][1].get(answer, -1)
        self.live = [i for i in self.live if parts[i] == label]
        self.history.append(name)

    def best(self):
        options = [name for name in MENU if name not in self.history]
        if len(self.live) < 2:
            return 0., options[0]
        def gain(name):
            parts = self.predictions(name)
            counts = Counter(parts[i] for i in self.live)
            return len(self.live) - sum(n*n for n in counts.values()) / len(self.live)
        scores = [(gain(name), name) for name in options]
        return max(scores, key=lambda item: item[0])


def teach(method, tasks, shared):
    rooms = [Classroom(t, shared) for t in tasks]
    if method == "pooled":
        queue = []
        def enqueue(i):
            room = rooms[i]
            score, name = room.best()
            heapq.heappush(queue, (-score, len(room.history), i, name))
        for i in range(len(rooms)):
            enqueue(i)
        for _ in range(2 * len(rooms)):
            _, _, i, name = heapq.heappop(queue)
            rooms[i].ask(name)
            if len(rooms[i].history) < 5:
                enqueue(i)
    else:
        for room in rooms:
            if method == "adaptive":
                for _ in range(2):
                    room.ask(room.best()[1])
                continue
            if method == "legacy":
                names = OLD
            elif method == "construct":
                names = ("double", "edit0")
            elif method == "random":
                rng = random.Random(digest(room.task["table"] + "/random-pair"))
                names = rng.sample(MENU, 2)
            else:
                raise ValueError(method)
            for name in names:
                room.ask(name)
    masks = [[i in r.live for i in range(len(r.task["plans"]))] for r in rooms]
    histories = [dict(table=r.task["table"], worlds=r.history, survivors=len(r.live)) for r in rooms]
    return masks, histories, sum(r.local_queries for r in rooms)
