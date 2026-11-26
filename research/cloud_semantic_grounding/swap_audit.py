"""Post-hoc, in-slate column substitution with frozen plan predictions; no refitting."""
from collections import Counter
from pathlib import Path
import json
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud_task_learning"))
from audit import original
from benchmark import sample
from plans import slate


def main(data, out):
    def read(name):
        return json.loads((out / (name + "_test.json")).read_text(encoding="utf8"))
    donor = read("raw_encoder")
    bases = {m: read(m) for m in ("lexical", "whole")}
    entries = sample(data / "test.jsonl", 1792)[1280:]
    wanted = {e["table_id"] for e in entries}
    tables = {}
    with (data / "test.tables.jsonl").open(encoding="utf8") as f:
        for line in f:
            tab = json.loads(line)
            if tab["id"] in wanted:
                tables[tab["id"]] = tab
    counts = {m: Counter() for m in bases}
    with sqlite3.connect((data / "test.db").resolve().as_uri() + "?mode=ro", uri=True) as db:
        for i, e in enumerate(entries):
            tid = e["table_id"]
            table = "table_" + tid.replace("-", "_")
            tab = tables[tid]
            plans, _ = slate(e["question"], tab["header"], tab["types"], db.execute("SELECT * FROM " + table).fetchall())
            assert donor[i]["table"] == tid
            for m, rows in bases.items():
                row = rows[i]
                assert row["table"] == tid
                before = row["chosen"]
                alt = donor[i]["chosen"][0], before[1], tuple(tuple(c) for c in before[2])
                change = before[0] != alt[0] and alt in plans
                chosen = alt if change else before
                correct = original(db, table, chosen) == original(db, table, row["gold"])
                counts[m].update(n=1, disagree=int(before[0] != alt[0]), changed=int(change), correct=int(correct),
                                 gains=int(correct and not row["original"]), losses=int(row["original"] and not correct))
    (out / "posthoc_column_swap.json").write_text(json.dumps(counts, indent=1) + "\n", encoding="utf8", newline="\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
