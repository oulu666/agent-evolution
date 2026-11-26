"""Compare pointwise, pairwise and boosted ranking students under frozen teacher feedback."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import multiprocessing
from pathlib import Path
import sys
import time

import numpy as np
from lightgbm import LGBMClassifier, LGBMRanker
from scipy import sparse
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud_active_teacher"))
from experiment import download, evaluate, load_split, predict, teach, write

CANDIDATES = ("pair_linear", "tree_class", "tree_rank")
CONTROLS = ("feedback_linear", "expert_linear", "expert_rank")
TRAIN, ITEMS, MASKS = [], [], {}


def contrast(matrix, labels, sizes):
    left, right, weights = [], [], []
    offset = 0
    for size in sizes:
        group = labels[offset:offset+size]
        good = np.flatnonzero(group) + offset
        bad = np.flatnonzero(~group) + offset
        count = len(good) * len(bad)
        left.extend(np.repeat(good, len(bad)))
        right.extend(np.tile(bad, len(good)))
        weights.extend([.5/count] * count)
        offset += size
    delta = matrix[left] - matrix[right]
    model = LogisticRegression(C=4, fit_intercept=False, solver="liblinear", random_state=17, max_iter=250)
    model.fit(sparse.vstack((delta, -delta)), np.repeat([1, 0], len(weights)), sample_weight=weights*2)
    return model, len(weights)


def fit(method):
    t0 = time.process_time()
    masks = MASKS["expert" if method.startswith("expert") else "feedback"]
    train = [(item, {"exact": mask}) for item, mask in zip(TRAIN, masks, strict=True)]
    if method in ("expert_linear", "feedback_linear"):
        picks, stats = predict("expert", train, ITEMS)
    else:
        kept = [(x, y["exact"]) for x, y in train if 0 < sum(y["exact"]) < len(y["exact"])]
        vec = DictVectorizer()
        matrix = vec.fit_transform(f for x, _ in kept for f in x["features"])
        labels = np.asarray([flag for _, mask in kept for flag in mask], dtype=bool)
        sizes = [len(mask) for _, mask in kept]
        score_x = vec.transform(f for x in ITEMS for f in x["features"])
        stats = dict(informative_training_tasks=len(kept), features=matrix.shape[1])
        args = dict(n_estimators=100, num_leaves=15, max_depth=5, learning_rate=.06, min_child_samples=15,
                    n_jobs=1, verbosity=-1, deterministic=True, force_col_wise=True, random_state=17)
        if method == "pair_linear":
            model, stats["training_pairs"] = contrast(matrix, labels, sizes)
            scores = model.decision_function(score_x)
        elif method == "tree_class":
            model = LGBMClassifier(**args)
            weights = np.concatenate([np.where(mask, .5/sum(mask), .5/(len(mask)-sum(mask))) for _, mask in kept])
            model.fit(matrix, labels.astype(int), sample_weight=weights)
            scores = model.predict_proba(score_x)[:, 1]
        else:
            model = LGBMRanker(objective="lambdarank", lambdarank_truncation_level=3, **args)
            model.fit(matrix, labels.astype(int), group=sizes)
            scores = model.predict(score_x)
        offsets = np.cumsum([len(item["plans"]) for item in ITEMS])[:-1]
        picks = [int(np.argmax(group)) for group in np.split(scores, offsets)]
    stats["cpu_seconds"] = round(time.process_time()-t0, 3)
    return method, picks, stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("cache", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    hashed = download(args.cache)
    assert hashed == "755c728ab188e364575705c8641f3fafd86fb089cb8b08e8c03f01832aae0881"
    global TRAIN, ITEMS, MASKS
    TRAIN = load_split(args.cache, "train", 768)
    dev = load_split(args.cache, "dev", 192, offset=320)
    test = load_split(args.cache, "test", 512, offset=768)
    assert len({x["table"] for x in TRAIN + dev + test}) == 1472
    ITEMS = [{k: t[k] for k in ("table", "features", "plans")} for t in dev+test]
    feedback, histories, calls = teach("random", TRAIN, {})
    assert sum(map(sum, feedback)) == 2080 and calls == 110592
    expert = [[p == t["gold"] for p in t["plans"]] for t in TRAIN]
    assert sum(map(sum, expert)) == 611
    MASKS = dict(expert=expert, feedback=feedback)
    methods = CONTROLS + CANDIDATES
    picks, costs = {}, {}
    with ProcessPoolExecutor(max_workers=6, mp_context=multiprocessing.get_context("fork")) as pool:
        for m, choices, stats in pool.map(fit, methods):
            picks[m], costs[m] = choices, stats
    write(args.out / "choices.json", picks)
    d = evaluate(dev, {m: p[:len(dev)] for m, p in picks.items()}, args.out, "dev")
    winner = max(CANDIDATES, key=lambda m: (d[m]["original"], d[m]["both"]))
    write(args.out / "selection.json", dict(winner=winner, development=d))
    scores = evaluate(test, {m: p[len(dev):] for m, p in picks.items()}, args.out, "test")
    strongest = max(CONTROLS, key=lambda m: (scores[m]["original"], scores[m]["both"]))
    passed = (scores[winner]["original"] - scores[strongest]["original"] >= 26
              and scores[winner]["both"] >= scores[strongest]["both"])
    write(args.out / "summary.json", dict(winner=winner, strongest=strongest, passed=passed, test_offset=768,
          development=d, test=scores, costs=costs, teacher_queries=sum(len(h["worlds"]) for h in histories),
          feedback_candidate_queries=calls, archive_sha256=hashed))


if __name__ == "__main__":
    main()
