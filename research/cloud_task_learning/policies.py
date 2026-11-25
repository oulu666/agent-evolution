"""Independent offline learners with the same deployment action space."""
import numpy as np
from sklearn.feature_extraction import DictVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from plans import template


def predict(method, train, items):
    if method == "rules":
        return [0] * len(items), {}
    if method == "memory":
        corpus = [x["signature"] for x, _ in train]
        vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        matrix = vec.fit_transform(corpus)
        near = (vec.transform([x["signature"] for x in items]) @ matrix.T).toarray()
        picks = []
        for row, item in zip(near, items):
            target = train[int(row.argmax())][1]["template"]
            pick = next((i for i, plan in enumerate(item["plans"]) if template(plan) == target), 0)
            picks.append(pick)
        return picks, {"examples_in_memory": len(train)}
    features, targets, weights = [], [], []
    used = positives = candidates = 0
    for x, gold in train:
        if method == "expert":
            mask = gold["exact"]
        elif method == "outcome":
            mask = gold["matches"]["original"]
        elif method == "intervention":
            mask = [all(flags) for flags in zip(*gold["matches"].values())]
        else:
            raise ValueError(method)
        hits = sum(mask)
        positives += hits
        candidates += len(mask)
        if hits == 0 or hits == len(mask):
            continue
        used += 1
        features.extend(x["features"])
        targets.extend(mask)
        weights.extend([.5 / hits if good else .5 / (len(mask) - hits) for good in mask])
    vectorizer = DictVectorizer()
    matrix = vectorizer.fit_transform(features)
    classifier = LogisticRegression(solver="liblinear", C=4, max_iter=250, random_state=17)
    classifier.fit(matrix, targets, sample_weight=weights)
    picks = [int(np.argmax(classifier.decision_function(vectorizer.transform(x["features"])))) for x in items]
    return picks, dict(informative_training_tasks=used, positive_programs=positives,
                       candidate_programs=candidates, coefficients=len(classifier.coef_[0]))
