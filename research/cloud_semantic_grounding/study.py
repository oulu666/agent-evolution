"""Blind evaluation of three semantic grounding architectures on fresh WikiSQL tables."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud_student_ranking"))
import students
from students import download, evaluate, load_split, teach, write
from represent import Encoder, block, get_model

CANDIDATES = ("whole", "factorized", "with_values")
CONTROLS = ("feedback_base", "expert_base", "lexical", "lexical_values", "expert_lexical", "raw_encoder")
BLOCKS = {
    "feedback_base": (), "expert_base": (), "lexical": ("lex",), "expert_lexical": ("lex",),
    "lexical_values": ("lex", "lexsamples"), "whole": ("lex", "joint"), "factorized": ("lex", "roles"),
    "with_values": ("lex", "lexsamples", "roles", "samples"),
}
ALL = []
FEATURES = {}
MASKS = {}
LENGTHS = (768, 192, 512)
MODEL = None


def build(mode):
    encoder = None if mode.startswith("lex") else Encoder(MODEL)
    arrays, costs = [], {}
    offset = 0
    for split, size in zip(("train", "dev", "test"), LENGTHS):
        start = time.process_time()
        cost = np.zeros(3, dtype="int64")
        for t in ALL[offset:offset+size]:
            features, count = block(mode, t, encoder)
            arrays.append(np.array(features, dtype=np.float32))
            cost += count
        costs[split] = dict(zip(("pairs", "tokens", "preview_cells"), map(int, cost)))
        costs[split]["cpu_seconds"] = round(time.process_time()-start, 3)
        offset += size
    return mode, arrays, costs


def fit(name):
    if name == "raw_encoder":
        return name, [int(np.argmax(a[:, 0])) for a in FEATURES["joint"][LENGTHS[0]:]], {}
    ranked = []
    for i, t in enumerate(ALL):
        features = [dict(row) for row in t["features"]]
        for mode in BLOCKS[name]:
            arr = FEATURES[mode][i]
            for j in range(arr.shape[1]):
                key = mode + str(j)
                for row, value in zip(features, arr[:, j], strict=True):
                    row[key] = float(value)
        ranked.append(dict(features=features, plans=t["plans"]))
    students.TRAIN, students.ITEMS = ranked[:LENGTHS[0]], ranked[LENGTHS[0]:]
    students.MASKS = MASKS
    _, picks, stats = students.fit("expert_rank" if name.startswith("expert") else "tree_rank")
    return name, picks, stats


def subgroup(tasks, picks):
    # Build a method-independent, post-prediction diagnostic denominator.
    idx = []
    for i, t in enumerate(tasks):
        gold = t["gold"]
        if gold not in t["plans"]:
            continue
        def signature(j):
            return {k: v for k, v in t["features"][j].items() if k not in ("rank", "prior")}
        ref = signature(t["plans"].index(gold))
        if any(p[0] != gold[0] and p[1:] == gold[1:] and signature(j) == ref
               for j, p in enumerate(t["plans"])):
            idx.append(i)
    return dict(n=len(idx), tables=[tasks[i]["table"] for i in idx],
                output_column={m: sum(tasks[i]["plans"][choices[i]][0] == tasks[i]["gold"][0] for i in idx)
                               for m, choices in picks.items()})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cache", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    data_hash = download(args.cache)
    assert data_hash == "755c728ab188e364575705c8641f3fafd86fb089cb8b08e8c03f01832aae0881"
    global ALL, MODEL, FEATURES, MASKS
    MODEL = args.cache / "tinybert"
    get_model(MODEL)
    train = load_split(args.cache, "train", LENGTHS[0])
    dev = load_split(args.cache, "dev", LENGTHS[1], offset=512)
    test = load_split(args.cache, "test", LENGTHS[2], offset=1280)
    ALL = train + dev + test
    assert len({t["table"] for t in ALL}) == sum(LENGTHS)
    feedback, histories, sims = teach("random", train, {})
    assert sum(map(sum, feedback)) == 2080 and sims == 110592
    MASKS = dict(feedback=feedback, expert=[[p == t["gold"] for p in t["plans"]] for t in train])
    performance = {}
    with ProcessPoolExecutor(max_workers=5, mp_context=mp.get_context("fork")) as pool:
        for mode, arrays, time_used in pool.map(build, ("lex", "lexsamples", "roles", "samples", "joint")):
            FEATURES[mode] = arrays
            performance[mode] = time_used
            print("representation completed", mode, time_used, flush=True)
    picks, costs = {}, {}
    with ProcessPoolExecutor(max_workers=4, mp_context=mp.get_context("fork")) as pool:
        for name, decisions, stats in pool.map(fit, CONTROLS + CANDIDATES):
            picks[name], costs[name] = decisions, stats
    write(args.out / "choices.json", picks)
    d = evaluate(dev, {m: p[:len(dev)] for m, p in picks.items()}, args.out, "dev")
    winner = max(CANDIDATES, key=lambda m: (d[m]["original"], d[m]["both"]))
    write(args.out / "selection.json", dict(winner=winner, development=d))
    test_picks = {m: p[len(dev):] for m, p in picks.items()}
    t = evaluate(test, test_picks, args.out, "test")
    strongest = max(CONTROLS, key=lambda m: (t[m]["original"], t[m]["both"]))
    passed = t[winner]["original"]-t[strongest]["original"] >= 26 and t[winner]["both"] >= t[strongest]["both"]
    write(args.out / "ambiguous_columns.json", subgroup(test, test_picks))
    write(args.out / "summary.json", dict(winner=winner, strongest=strongest, passed=passed, development=d,
          test=t, test_offset=1280, costs=costs, representations=performance, archive_sha256=data_hash,
          teacher_queries=sum(len(h["worlds"]) for h in histories), candidate_queries=sims))


if __name__ == "__main__":
    main()
