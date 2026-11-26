"""Post-reveal check for task/plan distinctions lost by the shared feature map."""
from pathlib import Path
from collections import Counter
import json
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud_task_learning"))
from audit import original
from benchmark import sample
from plans import slate


def main(data, out):
    def read(name):
        return json.loads((out / name).read_text(encoding="utf8"))
    method = read("summary.json")["winner"]
    result = read(method + "_test.json")
    choices = read("choices.json")[method][-len(result):]
    entries = sample(data / "test.jsonl", 1280)[768:]
    wanted = {r["table"] for r in result if not r["original"] and r["reachable"]}
    tables = {}
    with (data / "test.tables.jsonl").open(encoding="utf8") as f:
        for line in f:
            tab = json.loads(line)
            if tab["id"] in wanted:
                tables[tab["id"]] = tab
    counts, examples = Counter(), {}
    with sqlite3.connect((data / "test.db").resolve().as_uri() + "?mode=ro", uri=True) as db:
        for entry, r, i in zip(entries, result, choices, strict=True):
            tid = r["table"]
            assert entry["table_id"] == tid
            if tid not in wanted:
                continue
            tab = tables[tid]
            name = "table_" + tid.replace("-", "_")
            plans, features = slate(entry["question"], tab["header"], tab["types"],
                                    db.execute("SELECT * FROM " + name).fetchall())
            assert json.loads(json.dumps(plans[i])) == r["chosen"]
            target = original(db, name, r["gold"])
            correct = [j for j, p in enumerate(plans) if original(db, name, p) == target]
            counts["wrong_with_correct_answer_available"] += 1
            for key, ignored in (("rank_only", {"rank"}), ("rank_and_prior", {"rank", "prior"})):
                def signature(j):
                    return {k: v for k, v in features[j].items() if k not in ignored}
                other = next((j for j in correct if signature(j) == signature(i)), None)
                if other is not None:
                    counts[key] += 1
                    if key not in examples:
                        examples[key] = dict(table=tid, question=entry["question"], headers=tab["header"],
                                             chosen=plans[i], alternative=plans[other], gold=r["gold"])
    (out / "feature_audit.json").write_text(json.dumps(dict(counts=counts, examples=examples),
                                            indent=1, ensure_ascii=False) + "\n", encoding="utf8", newline="\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
