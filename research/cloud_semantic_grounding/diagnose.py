"""Paired comparisons and first frozen-order examples after the main evaluation."""
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud_task_learning"))
from benchmark import sample


def main(data, out):
    def read(name):
        return json.loads((out / name).read_text(encoding="utf8"))
    summary = read("summary.json")
    arms = {name: read(name + "_test.json") for name in summary["test"]}
    ids = set(read("ambiguous_columns.json")["tables"])
    primary = summary["winner"]
    matched = "lexical_values" if primary == "with_values" else "lexical"
    comparisons = {}
    for m in arms:
        pairs = list(zip(arms[primary], arms[m], strict=True))
        assert all(a["table"] == b["table"] for a, b in pairs)
        wins = sum(a["original"] and not b["original"] for a, b in pairs)
        losses = sum(b["original"] and not a["original"] for a, b in pairs)
        n = len(pairs)
        draws = np.random.default_rng(173).multinomial(n, [wins/n, losses/n, 1-(wins+losses)/n], size=20000)
        interval = np.percentile(100*(draws[:, 0]-draws[:, 1])/n, [2.5, 97.5]).round(2).tolist()
        comparisons[m] = dict(wins=wins, losses=losses, ties=n-wins-losses, descriptive_paired_interval_pp=interval)
    questions = {x["table_id"]: x["question"] for x in sample(data/"test.jsonl", 1792)[1280:]}
    examples = {}
    for a, b in zip(arms[primary], arms[matched], strict=True):
        if a["table"] not in ids or a["original"] == b["original"]:
            continue
        key = "gain" if a["original"] else "loss"
        if key not in examples:
            examples[key] = dict(table=a["table"], question=questions[a["table"]], selected=a["chosen"],
                                 lexical=b["chosen"], gold=a["gold"])
    with (data/"test.tables.jsonl").open(encoding="utf8") as f:
        for line in f:
            table = json.loads(line)
            for ex in examples.values():
                if table["id"] == ex["table"]:
                    ex["headers"] = table["header"]
    report = dict(primary=primary, matched=matched, comparisons=comparisons, ambiguous_examples=examples)
    (out/"diagnostics.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n",
                                        newline="\n", encoding="utf8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
