"""Re-score held-out choices on the original SQLite database and describe paired outcomes."""
from pathlib import Path
import json
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cloud_task_learning"))
from audit import original
from benchmark import normalized, sample


def main(out, data):
    def read(file):
        return json.loads((out / file).read_text(encoding="utf8"))
    summary = read("summary.json")
    runs = {m: read(m + "_test.json") for m in summary["test"]}
    primary = runs[summary["winner"]]
    offset = summary.get("test_offset", 256)
    entries = sample(data / "test.jsonl", offset + len(primary))
    old_ids = {e["table_id"] for e in entries[:offset]}
    checks = same = 0
    with sqlite3.connect((data / "test.db").resolve().as_uri() + "?mode=ro", uri=True) as db:
        for i, entry in enumerate(entries[offset:]):
            tid = entry["table_id"]
            assert tid not in old_ids
            name = "table_" + tid.replace("-", "_")
            types = [r[2].lower() for r in db.execute(f"PRAGMA table_info({name})")]
            q = entry["sql"]
            gold = q["sel"], q["agg"], [(c, o, normalized(v, types[c])) for c, o, v in q["conds"]]
            target = original(db, name, gold)
            for rows in runs.values():
                row = rows[i]
                assert row["table"] == tid and row["audit_matching_rows"] >= row["matching_rows"]
                same += (original(db, name, row["chosen"]) == target) == row["original"]
                checks += 1
    paired, subgroups = {}, {}
    for method, rows in runs.items():
        paired[method] = {}
        for key in ("original", "both", "exact"):
            wins = sum(a[key] and not b[key] for a, b in zip(primary, rows))
            losses = sum(b[key] and not a[key] for a, b in zip(primary, rows))
            paired[method][key] = dict(wins=wins, losses=losses, ties=len(rows)-wins-losses)
        nonempty = [r for r in rows if r["matching_rows"] > 0]
        subgroups[method] = dict(original_nonempty=len(nonempty), correct_nonempty=sum(r["original"] for r in nonempty),
                                 both_nonempty=sum(r["both"] for r in nonempty))
    missed = [r for r in primary if not r["original"]]
    result = dict(native_agreements=same, native_checks=checks, previous_test_overlap=0,
                  primary=summary["winner"], paired=paired, subgroups=subgroups,
                  missed_with_correct_answer_available=sum(r["reachable"] for r in missed),
                  missed_without_correct_answer_available=sum(not r["reachable"] for r in missed))
    (out / "recheck.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf8", newline="\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
