"""Run pinned upstream probes and compare reduced oracles on shared observations."""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from issre_independent_replay import version

PREVIOUS = HERE.parents[1] / "runs_independent_20261124" / "replay.json"
METHODS = ("status", "coarse", "relation", "shape", "union", "full")


def shape(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return ["array", [shape(item) for item in value]]
    return ["object", {key: shape(item) for key, item in value.items()}]


def alert(rows, method):
    ordinary, boundary = rows
    if not all(row["actual"]["ok"] for row in rows):
        return True
    if method == "status":
        return False
    if method in ("coarse", "full"):
        fields = ["coarse"] if method == "coarse" else ["coarse", "fine"]
        return any(r["actual"][f] != r["expected"][f] for r in rows for f in fields)
    if method in ("relation", "union"):
        def equal(side):
            return ordinary[side]["fine"] == boundary[side]["fine"]
        if equal("actual") != equal("expected"):
            return True
    return method in ("shape", "union") and any(
        shape(r["actual"]["fine"]) != shape(r["expected"]["fine"]) for r in rows
    )


def comparable(row):
    actual = dict(row["actual"])
    actual.pop("detail", None)
    return (row["input"], row["steps"], row["expected"], actual)


def replay_project(records):
    results = []
    for case in records:
        result = {key: case[key] for key in ("repo", "pr", "parent", "fixed")}
        for side in ("parent", "fixed"):
            try:
                observed = version(case["repo"], case[side], case["pr"])
                reference = case[side + "_rows"]
                result[side + "_rows"] = observed
                result[side + "_matches"] = list(map(comparable, observed)) == list(map(comparable, reference))
            except Exception as exc:
                result[side + "_error"] = str(exc)
        results.append(result)
    return results


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf8")


def score(out, records, method):
    hits, false_alerts, cases, missing = [], [], [], []
    for r in records:
        if "parent_rows" not in r or "fixed_rows" not in r:
            missing.append(r["pr"])
            continue
        old = alert(r["parent_rows"], method)
        fixed = alert(r["fixed_rows"], method)
        cases.append(dict(pr=r["pr"], repo=r["repo"], old_alert=old, fixed_alert=fixed))
        if r["pr"] != 240:
            if old and not fixed:
                hits.append(r["pr"])
            if fixed:
                false_alerts.append(r["pr"])
    summary = dict(hits=sorted(hits), fixed_alerts=sorted(false_alerts), missing=missing)
    write(out / (method + ".json"), dict(**summary, cases=cases))
    return method, summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    original = json.loads(PREVIOUS.read_text(encoding="utf-8-sig"))["outcomes"]
    assert len(original) == 13 and all(c["confirmed"] for c in original)
    projects = {}
    for case in original:
        projects.setdefault(case["repo"], []).append(case)
    with ThreadPoolExecutor(max_workers=4) as pool:
        runs = [r for project in pool.map(replay_project, projects.values()) for r in project]
    write(args.out / "observations.json", runs)
    with ThreadPoolExecutor(max_workers=len(METHODS)) as pool:
        results = dict(pool.map(lambda method: score(args.out, runs, method), METHODS))
    write(args.out / "summary.json", results)
    print(json.dumps(results, indent=2))
    if any(result["missing"] for result in results.values()):
        raise SystemExit("incomplete upstream execution; inspect observations")


if __name__ == "__main__":
    main()
