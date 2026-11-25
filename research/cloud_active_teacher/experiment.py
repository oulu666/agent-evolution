"""Parallel, budget-matched task-environment teachers for the frozen WikiSQL student."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing
from pathlib import Path
import re
import sqlite3
import sys
import time

BASE = Path(__file__).resolve().parents[1] / "cloud_task_learning"
sys.path.insert(0, str(BASE))
from benchmark import SIZES, normalized, sample
from plans import slate
from policies import predict
from run import download, write
from teach import run_table, teach, world

CANDIDATES = ("construct", "adaptive", "pooled")
BASELINES = ("expert", "legacy", "random")
METHODS = BASELINES + CANDIDATES
TRAIN = []
INPUTS = []


def load_split(directory, split, n):
    offset = 0 if split == "train" else SIZES[split]
    entries = sample(directory / (split + ".jsonl"), offset + n)
    exclude = {e["table_id"] for e in entries[:offset]}
    entries = entries[offset:]
    desired = {e["table_id"] for e in entries}
    assert len(desired) == n and not desired & exclude
    tables = {}
    with (directory / (split + ".tables.jsonl")).open(encoding="utf8") as handle:
        for line in handle:
            tab = json.loads(line)
            if tab["id"] in desired:
                tables[tab["id"]] = tab
    tasks = []
    with sqlite3.connect((directory / (split + ".db")).resolve().as_uri() + "?mode=ro", uri=True) as db:
        for e in entries:
            tid = e["table_id"]
            assert re.fullmatch(r"[0-9-]+", tid)
            rows = db.execute("SELECT * FROM table_" + tid.replace("-", "_")).fetchall()
            tab = tables[tid]
            plans, features = slate(e["question"], tab["header"], tab["types"], rows)
            sql = e["sql"]
            cond = tuple(sorted(((c, op, normalized(v, tab["types"][c])) for c, op, v in sql["conds"]),
                                key=lambda z: (z[0], z[1], str(z[2]))))
            tasks.append(dict(table=tid, rows=rows, types=tab["types"], plans=plans, features=features,
                              gold=(sql["sel"], sql["agg"], cond)))
    return tasks


def train_method(method):
    start = time.process_time()
    if method == "expert":
        masks = [[p == t["gold"] for p in t["plans"]] for t in TRAIN]
        histories, calls = [], 0
    else:
        masks, histories, calls = teach(method, TRAIN, {})
    train = [(t, {"exact": mask}) for t, mask in zip(TRAIN, masks, strict=True)]
    choices, stats = predict("expert", train, INPUTS)
    spent = sum(len(h["worlds"]) for h in histories)
    assert method == "expert" or spent == 3 * len(TRAIN)
    return method, choices, histories, dict(**stats, teacher_queries=spent, candidate_queries=calls,
                                           expert_plans=len(TRAIN) if method == "expert" else 0,
                                           extra_query_histogram=dict(Counter(len(h["worlds"]) - 1 for h in histories)),
                                           cpu_seconds=round(time.process_time() - start, 3))


def evaluate(tasks, picks, out, split):
    reports = {m: [] for m in METHODS}
    for i, t in enumerate(tasks):
        gold = t["gold"]
        plans = [gold, (gold[0], 0, gold[2])] + [t["plans"][picks[m][i]] for m in METHODS]
        main, audit = [run_table(world(t["rows"], t["plans"], t["table"], name), t["types"], plans)
                       for name in ("original", "audit")]
        feasible = run_table(t["rows"], t["types"], t["plans"])
        for j, method in enumerate(METHODS, 2):
            reports[method].append(dict(table=t["table"], gold=gold, chosen=plans[j], original=main[j] == main[0],
                                        both=main[j] == main[0] and audit[j] == audit[0],
                                        exact=gold == plans[j], matching_rows=len(main[1]),
                                        audit_matching_rows=len(audit[1]), reachable=main[0] in feasible))
    for m, rows in reports.items():
        write(out / (m + "_" + split + ".json"), rows)
    return {m: {k: sum(r[k] for r in rows) for k in ("original", "both", "exact", "reachable")}
            for m, rows in reports.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cache", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    data_hash = download(args.cache)
    assert data_hash == "755c728ab188e364575705c8641f3fafd86fb089cb8b08e8c03f01832aae0881"
    global TRAIN, INPUTS
    TRAIN, dev, test = [load_split(args.cache, s, n) for s, n in (("train", 768), ("dev", 192), ("test", 512))]
    assert len({t["table"] for t in TRAIN + dev + test}) == 1472
    INPUTS = [{k: t[k] for k in ("table", "features", "plans")} for t in dev + test]
    costs, picks = {}, {}
    with ProcessPoolExecutor(max_workers=len(METHODS), mp_context=multiprocessing.get_context("fork")) as pool:
        for m, choices, histories, stats in pool.map(train_method, METHODS):
            costs[m], picks[m] = stats, choices
            if histories:
                write(args.out / (m + "_teacher.json"), histories)
            print(m, stats, flush=True)
    write(args.out / "choices.json", picks)
    d = evaluate(dev, {m: p[:len(dev)] for m, p in picks.items()}, args.out, "dev")
    winner = max(CANDIDATES, key=lambda m: (d[m]["original"], d[m]["both"]))
    write(args.out / "selection.json", dict(development=d, winner=winner))
    t = evaluate(test, {m: p[len(dev):] for m, p in picks.items()}, args.out, "test")
    strongest = max(BASELINES, key=lambda m: (t[m]["original"], t[m]["both"]))
    passes = t[winner]["original"] - t[strongest]["original"] >= 26 and t[winner]["both"] >= t[strongest]["both"]
    write(args.out / "summary.json", dict(development=d, test=t, winner=winner, strongest=strongest,
                                          passed=passes, costs=costs, archive_sha256=data_hash))


if __name__ == "__main__":
    main()
