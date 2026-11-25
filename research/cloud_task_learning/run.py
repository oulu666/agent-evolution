"""Run concurrent policies, select on development, and then score untouched test tables."""
import argparse
import hashlib
import json
import multiprocessing
import tarfile
import time
import urllib.request
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from shutil import copyfileobj

from benchmark import prepare
from policies import predict

PIN = "cffb423077756d04c1bac5bcd45167c86903fbcb"
CANDIDATES = ("memory", "outcome", "intervention")
METHODS = ("rules", "expert", *CANDIDATES)
TRAIN = []
INPUTS = []


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf8")


def download(target):
    target.mkdir(parents=True, exist_ok=True)
    archive = target / "data.tar.bz2"
    if not archive.exists():
        url = f"https://raw.githubusercontent.com/salesforce/WikiSQL/{PIN}/data.tar.bz2"
        with urllib.request.urlopen(url, timeout=90) as src, archive.open("wb") as dst:
            copyfileobj(src, dst)
    required = {s + suffix for s in ("train", "dev", "test") for suffix in (".db", ".jsonl", ".tables.jsonl")}
    with tarfile.open(archive) as bundle:
        for member in bundle:
            name = Path(member.name).name
            if member.isfile() and name in required:
                with bundle.extractfile(member) as src, (target / name).open("wb") as dst:
                    copyfileobj(src, dst)
                required.remove(name)
    assert not required, required
    return hashlib.sha256(archive.read_bytes()).hexdigest()


def learn(method):
    start = time.process_time()
    choices, cost = predict(method, TRAIN, INPUTS)
    return method, choices, dict(**cost, learner_cpu_seconds=round(time.process_time() - start, 3))


def score(split, choices, out):
    records = []
    for (x, y), index in zip(split, choices, strict=True):
        m = y["matches"]
        records.append(dict(table=x["table"], chosen=x["plans"][index], gold=y["gold"],
                            answer=m["original"][index], exact=y["exact"][index],
                            both=m["original"][index] and m["audit"][index],
                            answer_reachable=any(m["original"]), exact_reachable=any(y["exact"])))
    write(out, records)
    return {k: sum(int(r[k]) for r in records)
            for k in ("answer", "both", "exact", "answer_reachable", "exact_reachable")}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cache", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    args.out.mkdir(exist_ok=True, parents=True)
    archive_hash = download(args.cache)
    splits = prepare(args.cache)
    global TRAIN, INPUTS
    TRAIN = splits["train"]
    dev, test = splits["dev"], splits["test"]
    INPUTS = [x for x, _ in dev + test]
    choices = {}
    costs = {}
    with ProcessPoolExecutor(max_workers=5, mp_context=multiprocessing.get_context("fork")) as pool:
        for name, picks, cost in pool.map(learn, METHODS):
            choices[name], costs[name] = picks, cost
    # Persist every test choice before scoring the first development result.
    write(args.out / "frozen_choices.json", choices)
    dev_scores = {m: score(dev, choices[m][:len(dev)], args.out / (m + "_dev.json")) for m in METHODS}
    winner = max(CANDIDATES, key=lambda m: (dev_scores[m]["answer"], dev_scores[m]["both"]))
    write(args.out / "development_selection.json", dict(winner=winner, scores=dev_scores))
    test_scores = {m: score(test, choices[m][len(dev):], args.out / (m + "_test.json")) for m in METHODS}
    world_counts = {s: sum(len(x["plans"]) + 1 for x, _ in rows) for s, rows in splits.items()}
    summary = dict(data_sha256=archive_hash, data_commit=PIN, winner=winner, costs=costs,
                   query_executions_per_world=world_counts, development=dev_scores, test=test_scores)
    write(args.out / "summary.json", summary)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
