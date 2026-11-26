"""Public-case development comparison. Sealed files are never used."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from itertools import permutations, product
import json
from pathlib import Path
import random
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter_ns
from zipfile import ZipFile
from io import BytesIO
from hashlib import sha256

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parents[1]
sys.path.extend([str(HERE.parent), str(RESEARCH), str(RESEARCH / "egatv_pilot")])
import upstream_functional_witnesses as archive
from experiment import execute, expected
from freeze_guards import ExtraCalls, OUTCOME_LOSS

PROBES = {
    "week": ["2014-07-16", "2011-01-01", "2010-01-01", "2019-12-30"],
    "duration": [2.25, 57.5, 61.25, 92],
    "column": [["text"] * 4, ["width", "width", "text", "text"],
               ["width", "text", "fit", "fit"], ["text", "fit", "width", "fit"]]}
ARMS = ("raw", "regression", "static_info", "active_info", "static_task", "active_task",
        "random", "native")


def inputs(case):
    if case == "column":
        return [list(seq) for size in range(4) for seq in product(("width", "text", "fit"), repeat=size)]
    if case == "duration":
        return [1, 30, 59, 59.5, 60, 75]
    return [f"{year}-{day}" for year in (2003, 2004, 2005, 2008)
            for day in ("06-15", "01-01", "12-28", "12-29", "12-31")]


def call(case, value, alternate=False):
    if case == "column":
        return archive.workbook_result(value)
    return execute(case, value, alt=alternate)


def oracle(case, value):
    if case == "column":
        return {"visible": True, "cell_text": "hello world" if "text" in value else ""}
    return expected(case, value)


def schema(case, result):
    if case == "column":
        return isinstance(result, dict) and type(result.get("visible")) is bool and isinstance(result.get("cell_text"), str)
    if case == "duration":
        return isinstance(result, list) and len(result) == 2 and isinstance(result[0], float) and isinstance(result[1], str)
    return isinstance(result, str)


def capture(case):
    def measure(value):
        start = perf_counter_ns()
        observed = call(case, value)
        return {"value": value, "observed": observed, "elapsed_ns": perf_counter_ns() - start}
    return {"initial": [measure(v) for v in inputs(case)], "bank": [measure(v) for v in PROBES[case]]}


def survivors(bank, states, q, output):
    return tuple(s for s in states if bank[s][q] == output)


def information_choice(bank, states, unused):
    def score(q):
        return sum(len(survivors(bank, states, q, bank[s][q])) for s in states)
    best = min(unused, key=lambda q: (score(q), q))
    return best if score(best) < len(states) ** 2 else None


def best_static(bank):
    def score(seq):
        residual = calls = 0
        for state in range(len(bank)):
            candidates = tuple(range(len(bank)))
            for q in seq:
                if len(candidates) == 1:
                    break
                candidates = survivors(bank, candidates, q, bank[state][q])
                calls += 1
            residual += len(candidates)
        return residual, calls, seq
    return min((seq for size in range(4) for seq in permutations(range(4), size)), key=score)


def task_probe_values(bank, current_loss):
    """Evaluate each probe+stop against immediate stop once the full verdict is known."""
    states = tuple(range(len(bank)))
    values = []
    for q in range(len(bank[0])):
        partitions = {survivors(bank, states, q, bank[s][q]) for s in states}
        expected_after = sum(len(group) * current_loss for group in partitions) / len(states)
        values.append(current_loss - expected_after)
    return values


def evaluate(case, initial, bank, arm):
    rows = []
    static = best_static(bank) if arm == "static_info" else ()
    for first in initial:
        value, actual = first["value"], first["observed"]
        check_start = perf_counter_ns()
        required = oracle(case, value)
        schema_ok = schema(case, actual)
        violated = not schema_ok or actual != required
        check_ns = perf_counter_ns() - check_start
        events = []
        gains = None

        def dispatch(request):
            if request["kind"] == "recovery":
                return call(case, value, alternate=True)
            return call(case, PROBES[case][request["q"]])

        meter = ExtraCalls(dispatch)
        delivered = actual
        target_alarm = False
        start = perf_counter_ns()
        if arm == "raw":
            pass
        elif (arm == "native" and case != "column") or violated:
            target_alarm = violated
            if case == "column":
                delivered = None
            elif case == "week":
                delivered = call(case, value, alternate=True)
            else:
                delivered = meter.call("recovery", {"kind": "recovery"})
            if delivered != required:
                delivered = None
        elif arm == "active_task":
            gains = task_probe_values(bank, OUTCOME_LOSS["correct"])
            assert max(gains) == 0  # Ties favor immediate delivery.
        elif arm in {"regression", "static_info", "active_info", "random"}:
            candidates = tuple(range(len(bank)))
            unused = list(range(4))
            plan = list(static) if arm == "static_info" else [0, 1, 2]
            if arm == "random":
                plan = random.Random(20261126).sample(unused, 3)
            for step in range(3):
                if len(candidates) <= 1:
                    break
                if arm == "active_info":
                    q = information_choice(bank, candidates, unused)
                    if q is None:
                        break
                elif step < len(plan):
                    q = plan[step]
                else:
                    break
                output = meter.call("probe", {"kind": "probe", "q": q})
                following = survivors(bank, candidates, q, output)
                events.append({"q": q, "input": PROBES[case][q], "output": output,
                               "before": candidates, "after": following, "old_diff": output != bank[0][q]})
                unused.remove(q)
                candidates = following
        # With a complete target check, expected improvement of any pure identification probe is zero.
        elapsed = perf_counter_ns() - start
        outcome = "deferred" if delivered is None else "correct" if delivered == required else "wrong"
        rows.append({"value": value, "initial": actual, "required": required, "schema_ok": schema_ok,
                     "initial_wrong": violated, "target_alarm": target_alarm, "delivered": delivered,
                     "outcome": outcome, "loss": OUTCOME_LOSS[outcome], "probes": events,
                     "charges": meter.events, "probe_loss_reductions": gains,
                     "check_ns": check_ns, "post_check_ns": elapsed})
    return {"arm": arm, "preplanned": static, "rows": rows}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def launch(case, output):
    package, old, new, source = archive.CASES[case]
    registered = json.loads((RESEARCH.parent / "runs_upstream_functional_20261124" / "paired_releases.json").read_text())[case]
    with TemporaryDirectory() as tmp:
        base = Path(tmp)
        folders = []
        captures = []
        def worker(i, mode):
            args = [sys.executable, "-I", str(Path(__file__).resolve()), case, "--worker", mode,
                    "--folder", str(folders[i]), "--version", (old, new)[i], "--output", str(base)]
            subprocess.run(args, check=True)
            return json.loads((base / f"{(old,new)[i]}-{mode}.json").read_text())
        for i, side in enumerate(("before", "after")):
            spec = registered[side]
            assert spec["version"] == (old, new)[i]
            data = archive.fetch(spec["url"])
            assert sha256(data).hexdigest() == spec["sha256"]
            dest = base / spec["version"]
            with ZipFile(BytesIO(data)) as z:
                z.extractall(dest)
            folders.append(dest)
            captures.append(worker(i, "capture"))
        bank = [[p["observed"] for p in c["bank"]] for c in captures]
        save(base / "bank.json", bank)
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {(i, arm): pool.submit(worker, i, arm) for i in range(2) for arm in ARMS}
            results = {v: {a: futures[i, a].result() for a in ARMS} for i, v in enumerate((old, new))}
        output.mkdir(parents=True, exist_ok=True)
        save(output / f"{case}.json", {"case": case, "source": source, "versions": [old, new],
             "wheels": [registered[s]["sha256"] for s in ("before", "after")],
             "captures": captures, "results": results})


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("case", choices=PROBES)
    p.add_argument("--worker")
    p.add_argument("--folder", type=Path)
    p.add_argument("--version")
    p.add_argument("--output", type=Path, default=Path("dev-results"))
    a = p.parse_args()
    if a.worker:
        sys.path.insert(0, str(a.folder))
        pkg = __import__(archive.CASES[a.case][0].lower())
        assert pkg.__version__ == a.version and Path(pkg.__file__).resolve().is_relative_to(a.folder)
        if a.worker == "capture":
            result = capture(a.case)
        else:
            initial = json.loads((a.output / f"{a.version}-capture.json").read_text())["initial"]
            result = evaluate(a.case, initial, json.loads((a.output / "bank.json").read_text()), a.worker)
        save(a.output / f"{a.version}-{a.worker}.json", result)
    else:
        launch(a.case, a.output)
