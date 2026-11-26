"""Public attrs development gate, with online probe budgets and offline planning."""
from fractions import Fraction
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter_ns

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from freeze_guards import ExtraCalls, OUTCOME_LOSS, disposition

MENU = ("default", "explicit")
STATES = ("forward_argument", "forward_default")
METHODS = ("direct", "metamorphic", "eliminate", "adaptive", "preplanned")
SOURCE = Path(sys.argv[1]).resolve() if __name__ == "__main__" else None


def expected(q):
    return 100 if q == "default" else 200


def prediction(h, q):
    return expected(q) if h == "forward_argument" else 100


def invoke(q):
    import attrs
    seen = []

    @attrs.define
    class Item:
        value: int = 100

        def __attrs_pre_init__(self, value):
            seen.append(value)

    item = Item() if q == "default" else Item(200)
    return {"final": item.value, "callback": seen}


def narrow(states, q, obs):
    if obs["final"] != expected(q):
        return ()
    return tuple(h for h in states if "callback" not in obs or obs["callback"] == [prediction(h, q)])


def verdict(states, task):
    claims = {prediction(h, task) == expected(task) for h in states}
    return "satisfied" if claims == {True} else "violated" if claims == {False} else "undetermined"


def terminal(states, task):
    if verdict(states, task) == "violated":
        return Fraction(OUTCOME_LOSS["deferred"]), Fraction(0)
    wrong = sum(prediction(h, task) != expected(task) for h in states)
    return Fraction(wrong * OUTCOME_LOSS["wrong"], len(states)), Fraction(0)


def groups(states, q):
    return [tuple(h for h in states if prediction(h, q) == v)
            for v in sorted({prediction(h, q) for h in states})]


def evaluate_next(states, q, continuation):
    loss, calls = Fraction(0), Fraction(1)
    for group in groups(states, q):
        weight = Fraction(len(group), len(states))
        branch_loss, branch_calls = continuation(group)
        loss += weight * branch_loss
        calls += weight * branch_calls
    return loss, calls


def static_value(states, task, seq):
    stop = terminal(states, task)
    if not seq or verdict(states, task) != "undetermined":
        return stop
    return min(stop, evaluate_next(states, seq[0], lambda g: static_value(g, task, seq[1:])))


def adaptive(states, task, depth):
    best = terminal(states, task)
    query = None
    if depth and verdict(states, task) == "undetermined":
        for q in MENU:
            value = evaluate_next(states, q, lambda g: adaptive(g, task, depth-1)[0])
            if value < best:
                best, query = value, q
    return best, query


def conflicts(states, task):
    yes = sum(prediction(h, task) == expected(task) for h in states)
    return yes * (len(states) - yes)


def evaluate(name, task, obs):
    start = perf_counter_ns()
    states = narrow(STATES, task, obs)
    if not states:
        raise ValueError("first return outside registered model")
    initial = verdict(states, task)
    trace = []
    meter = ExtraCalls(invoke)
    seq = ()
    relation = None
    if name == "preplanned":
        seq = min((s for n in range(4) for s in product(MENU, repeat=n)),
                  key=lambda s: (static_value(states, task, s), len(s), s))
    for step in range(3):
        if verdict(states, task) != "undetermined" or name == "direct":
            break
        if name == "metamorphic":
            q = MENU[step]
        elif name == "eliminate":
            q = min(MENU, key=lambda x: sum(conflicts(g, task) for g in groups(states, x)))
            if sum(conflicts(g, task) for g in groups(states, q)) >= conflicts(states, task):
                break
        elif name == "adaptive":
            _, q = adaptive(states, task, 3-step)
            if q is None:
                break
        else:
            suffix = seq[step:]
            if not suffix or static_value(states, task, suffix) >= terminal(states, task):
                break
            q = suffix[0]
        actual = meter.call("probe", q)
        following = narrow(states, q, actual)
        trace.append({"q": q, "response": actual, "before": states, "after": following})
        if not following:
            raise ValueError("probe return outside registered model")
        states = following
        if name == "metamorphic" and step == 1:
            delta = actual["callback"][0] - trace[0]["response"]["callback"][0]
            relation = {"observed_difference": delta, "expected_difference": 100}
            assert (delta == 100) == (verdict(states, task) == "satisfied")
    v = verdict(states, task)
    return {"initial_verdict": initial, "verdict": v, "sequence_commitment": seq,
            "trace": trace, "charges": meter.events, "relation": relation,
            "action": disposition(v, verified_replacement=False), "elapsed_ns": perf_counter_ns()-start}


def main():
    rev = subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", "HEAD"], text=True).strip()
    if rev != sys.argv[2]:
        raise ValueError("source revision mismatch")
    sys.path.insert(0, str(SOURCE / "src"))
    import attrs
    assert Path(attrs.__file__).resolve().is_relative_to(SOURCE / "src")
    prior = json.loads(Path("runs_interaction_blind_20261124/findings.json").read_text())["posthoc_1428"][sys.argv[3]]
    rows = []
    for task, ref in zip(MENU, prior, strict=True):
        started = perf_counter_ns()
        actual = invoke(task)
        elapsed = perf_counter_ns() - started
        assert ref["explicit"] == (task == "explicit") and actual == {k: ref[k] for k in actual}
        correct = actual["final"] == expected(task) and actual["callback"] == [expected(task)]
        for access in ("returned_object", "first_hook"):
            obs = dict(actual) if access == "first_hook" else {"final": actual["final"]}
            results = {method: evaluate(method, task, obs) for method in METHODS}
            for result in results.values():
                result["outcome"] = ("deferred" if result["action"] == "defer" else
                                     "correct" if correct else "wrong")
            rows.append({"task": task, "access": access, "view": obs, "scorer": actual,
                         "callback_already_wrong": not correct, "first_ns": elapsed, "methods": results})
    data = {"revision": rev, "side": sys.argv[3], "rows": rows,
            "runner_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}
    Path(f"attrs-{sys.argv[3]}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
