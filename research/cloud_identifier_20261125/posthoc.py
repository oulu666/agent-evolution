"""Post-reveal action audit on archived observations. No additional tool executions."""
from collections import Counter
import json
from pathlib import Path
import sys

from design import alternative, standard


def main(out):
    def read(name):
        return json.loads((out / (name + ".json")).read_text(encoding="utf8"))
    tasks = {r["id"]: r for r in read("tasks")}
    obs = read("observations")
    counts = Counter()
    for row in read("alias"):
        task = tasks[row["task"]]
        raw = task["raw"]
        alias = alternative(raw)
        observed = obs[row["project"]][row["tag"]]
        proposal = observed[alias if row["verdict"] == "alert" else raw].get("value")
        direct = standard(alias)
        counts["pairs"] += 1
        counts["use_alias_on_alert_correct"] += proposal == task["target"]
        counts["offline_alias_regex_correct"] += direct == task["target"]
        counts["identical_output"] += proposal == direct
    (out / "posthoc.json").write_text(json.dumps(counts, indent=2) + "\n", encoding="utf8", newline="\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
