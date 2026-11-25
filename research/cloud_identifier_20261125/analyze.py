"""Compute grouped delivery, alarms, costs and adjacent release transitions."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

from design import CANARIES, METHODS, alternative


def main(out):
    def read(name):
        return json.loads((out / (name + ".json")).read_text(encoding="utf-8"))
    tasks = {r["id"]: r for r in read("tasks")}
    backup = {r["task"]: r["correct"] for r in read("direct")}
    obs = read("observations")
    metrics = defaultdict(Counter)
    for method in METHODS:
        for r in read(method):
            project, tag, task = r["project"], r["tag"], tasks[r["task"]]
            alarm = r["verdict"] == "alert"
            correct = r["correct"]
            final = backup[r["task"]] if alarm else correct
            row = dict(n=1, alert_wrong=int(alarm and not correct), alert_correct=int(alarm and correct),
                       unknown=int(r["verdict"] == "unknown"), raw=int(correct), delivered=int(final),
                       backup=int(backup[r["task"]]), improved=int(final and not correct),
                       regressed=int(correct and not final))
            for scope in ("all", project, project + "/" + tag, "group/" + task["group"]):
                metrics[scope + "/" + method].update(row)
    costs, transitions = {}, {}
    raw = {r["raw"] for r in tasks.values()}
    for project, versions in obs.items():
        costs[project] = {m: len(raw | extra) * len(versions) for m, extra in (
            ("examples", {x for x, _ in CANARIES[project]}), ("regex", set()),
            ("dictionary", set()), ("suffix", {x + "Record" for x in raw}),
            ("alias", {alternative(x) for x in raw}))}
        costs[project]["shared_actual"] = sum(map(len, versions.values()))
        changes = []
        tags = list(versions)
        for before, after in zip(tags, tags[1:]):
            different = sorted(x for x in raw if versions[before][x] != versions[after][x])
            if different:
                changes.append(dict(before=before, after=after, changed=different))
        transitions[project] = changes
    (out / "analysis.json").write_text(json.dumps(dict(metrics=metrics, calls=costs, transitions=transitions),
                                                   ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
