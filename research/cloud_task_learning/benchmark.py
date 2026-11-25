"""Generate slates before joining labels. Execute only typed actions on the benchmark tables."""
import hashlib
import json
import random
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

from plans import AGG, OPS, delex, slate, template

SIZES = {"train": 768, "dev": 128, "test": 256}


def digest(text):
    return hashlib.sha256(("tool-agent-global-v1/" + text).encode()).hexdigest()


def sample(path, n):
    by_table = defaultdict(list)
    for line in path.read_text(encoding="utf8").splitlines():
        entry = json.loads(line)
        by_table[entry["table_id"]].append(entry)
    ids = sorted(by_table, key=digest)[:n]
    assert len(ids) == n
    return [min(by_table[t], key=lambda e: digest(e["question"])) for t in ids]


def normalized(value, kind):
    if kind == "real" and isinstance(value, str):
        try:
            return float(value.replace(",", ""))
        except ValueError:
            return float(re.findall(r"[-+]?\d*\.\d+|\d+", value)[0])
    return value.lower() if isinstance(value, str) else value


def execute(conn, plan):
    col, agg, conds = plan
    projection = f"c{col}"
    if agg:
        projection = f"{AGG[agg]}({projection})"
    filters = [f"c{idx} {OPS[op]} ?" for idx, op, _ in conds]
    sql = f"SELECT {projection} FROM t"
    if filters:
        sql += " WHERE " + " AND ".join(filters)
    return tuple(row[0] for row in conn.execute(sql, [v for _, _, v in conds]))


def intervene(rows, seed, mode):
    rng = random.Random(seed)
    if mode == "subset":
        return [row for row in rows if rng.randrange(2) == 0]
    columns = list(map(list, zip(*rows)))
    for column in columns:
        rng.shuffle(column)
    result = list(zip(*columns))
    return result[::2] if mode == "audit" else result


def match_world(rows, types, plans, gold):
    conn = sqlite3.connect(":memory:")
    try:
        schema = ", ".join(f"c{i} {t}" for i, t in enumerate(types))
        conn.execute(f"CREATE TABLE t ({schema})")
        conn.executemany("INSERT INTO t VALUES (" + ",".join("?" for _ in types) + ")", rows)
        target = execute(conn, gold)
        return [execute(conn, p) == target for p in plans]
    finally:
        conn.close()


def record(entry, tab, db, split):
    table_id, question = entry["table_id"], entry["question"]
    types, headers = tab["types"], tab["header"]
    assert re.fullmatch(r"[0-9-]+", table_id) and set(types) <= {"text", "real"}
    internal = "table_" + table_id.replace("-", "_")
    rows = db.execute(f"SELECT * FROM {internal}").fetchall()
    assert rows and len(types) == len(rows[0])
    plans, features = slate(question, headers, types, rows)
    signature = delex(question, headers, {v for _, _, conds in plans for _, _, v in conds})
    # Metadata below is separate from everything the prediction policy can see.
    label = entry["sql"]
    conds = tuple(sorted(((c, op, normalized(v, types[c])) for c, op, v in label["conds"]),
                         key=lambda z: (z[0], z[1], str(z[2]))))
    gold = (label["sel"], label["agg"], conds)
    matches = {"original": match_world(rows, types, plans, gold)}
    for mode in (("subset", "shuffle") if split == "train" else ("audit",)):
        changed = intervene(rows, digest(table_id + "/" + mode), mode)
        matches[mode] = match_world(changed, types, plans, gold)
    return (dict(table=table_id, question=question, signature=signature, plans=plans, features=features),
            dict(matches=matches, exact=[p == gold for p in plans], template=template(gold), gold=gold))


def prepare(directory):
    splits = {}
    seen = set()
    for split, n in SIZES.items():
        entries = sample(directory / (split + ".jsonl"), n)
        selected = {e["table_id"] for e in entries}
        assert not (seen & selected)
        seen.update(selected)
        tables = {}
        with (directory / (split + ".tables.jsonl")).open(encoding="utf8") as handle:
            for line in handle:
                t = json.loads(line)
                if t["id"] in selected:
                    tables[t["id"]] = t
        with sqlite3.connect((directory / (split + ".db")).resolve().as_uri() + "?mode=ro", uri=True) as db:
            splits[split] = [record(e, tables[e["table_id"]], db, split) for e in entries]
        print("Prepared", split, len(entries), flush=True)
    return splits
