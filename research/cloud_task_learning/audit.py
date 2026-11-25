"""Post-run native database recheck and attribution of robustness changes."""
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from benchmark import digest, execute, intervene, normalized, sample
from plans import AGG, OPS


def original(db, table, plan):
    col, agg, conds = plan
    field = f"col{col}"
    if agg:
        field = f"{AGG[agg]}({field})"
    where = " AND ".join(f"col{c} {OPS[o]} :v{c}" for c, o, _ in conds)
    sql = f"SELECT {field} FROM {table}" + (" WHERE " + where if where else "")
    return tuple(r[0] for r in db.execute(sql, {f"v{c}": v for c, _, v in conds}))


def paired(rows, other, metric):
    flags = [(r[metric], s[metric]) for r, s in zip(rows, other, strict=True)]
    return dict(wins=flags.count((True, False)), losses=flags.count((False, True)),
                ties=sum(a == b for a, b in flags))


def main(data, results):
    methods = ("rules", "expert", "memory", "outcome", "intervention")
    runs = {m: json.loads((results / (m + "_test.json")).read_text(encoding="utf8")) for m in methods}
    entries = sample(data / "test.jsonl", 256)
    direct_checks = same = empty_vs_null = 0
    kinds = Counter()
    examples = {}
    with sqlite3.connect((data / "test.db").resolve().as_uri() + "?mode=ro", uri=True) as db:
        for i, entry in enumerate(entries):
            tid = entry["table_id"]
            name = "table_" + tid.replace("-", "_")
            types = [r[2].lower() for r in db.execute(f"PRAGMA table_info({name})")]
            q = entry["sql"]
            gold = (q["sel"], q["agg"], [(c, o, normalized(v, types[c])) for c, o, v in q["conds"]])
            truth = original(db, name, gold)
            for rows in runs.values():
                r = rows[i]
                assert r["table"] == tid
                same += (original(db, name, r["chosen"]) == truth) == r["answer"]
                direct_checks += 1
            a, b = runs["intervention"][i], runs["outcome"][i]
            if a["both"] == b["both"]:
                continue
            raw = db.execute("SELECT * FROM " + name).fetchall()
            changed = intervene(raw, digest(tid + "/audit"), "audit")
            with sqlite3.connect(":memory:") as local:
                local.execute("CREATE TABLE t (" + ",".join(f"c{c} {t}" for c, t in enumerate(types)) + ")")
                local.executemany("INSERT INTO t VALUES (" + ",".join("?" for _ in types) + ")", changed)
                answers = [execute(local, plan) for plan in (gold, a["chosen"], b["chosen"])]
            direction = "gain" if a["both"] else "loss"
            if direction == "gain" and b["answer"] and answers[0] == () and answers[2] == (None,):
                empty_vs_null += 1
            kind = "empty" if not answers[0] else "null" if answers[0] == (None,) else "nonempty"
            key = direction + "_" + kind
            kinds[key] += 1
            if key not in examples:
                examples[key] = dict(table=tid, question=entry["question"], original_gold=truth,
                                     audit_gold=answers[0], audit_intervention=answers[1], audit_outcome=answers[2])
    audit = dict(native_checks=direct_checks, native_agreements=same, robustness_discordances=kinds,
                 gain_explained_by_empty_vs_null=empty_vs_null,
                 examples=examples, pairs={m: {k: paired(runs["intervention"], runs[m], k)
                 for k in ("answer", "both", "exact")} for m in methods if m != "intervention"},
                 any_policy_correct=sum(any(r["answer"] for r in rows) for rows in zip(*runs.values())))
    (results / "posthoc_audit.json").write_text(json.dumps(audit, indent=1, ensure_ascii=False) + "\n",
                                               encoding="utf8", newline="\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
