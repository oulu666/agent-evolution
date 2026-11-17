#!/usr/bin/env python3
"""Read-only classification of train / replay / exam items into operation patterns.

Does not write into frozen data_* or runs_* directories. Default output is stdout.
Optional --json-out writes a JSON summary to a path you choose.

Usage (from the project root, with PYTHONPATH=.):

  .venv/bin/python scripts/classify_operation_patterns.py
  .venv/bin/python scripts/classify_operation_patterns.py --json-out /tmp/coverage_inventory.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fac_tinyagent.coverage_patterns import (  # noqa: E402
    OFFICIAL_PATTERNS,
    PATTERN_DESC,
    PATTERN_FAMILY,
    TEMPLATE_TO_PATTERN,
    classify_item,
    classify_sql_query,
    experience_diversity,
    experience_identity,
    pattern_coverage,
)

SOURCES = [
    ("phase2_train_database", "data_phase2/database/train.jsonl", "train"),
    ("phase2_train_file", "data_phase2/file/train.jsonl", "train"),
    ("phase2_train_python", "data_phase2/python/train.jsonl", "train"),
    ("phase2_train_calendar", "data_phase2/calendar/train.jsonl", "train"),
    ("phase2_test_database", "data_phase2/database/test.jsonl", "exam"),
    ("phase2_test_file", "data_phase2/file/test.jsonl", "exam"),
    ("phase2_test_python", "data_phase2/python/test.jsonl", "exam"),
    ("phase2_test_calendar", "data_phase2/calendar/test.jsonl", "exam"),
    ("e4_pool_database", "data_ext_e4/pool/database.jsonl", "replay_pool"),
    ("e4_pool_file", "data_ext_e4/pool/file.jsonl", "replay_pool"),
    ("e4_pool_python", "data_ext_e4/pool/python.jsonl", "replay_pool"),
    ("natv2_database", "data_ext_e4/final_v2/database.jsonl", "exam"),
    ("natv2_file", "data_ext_e4/final_v2/file.jsonl", "exam"),
    ("natv2_python", "data_ext_e4/final_v2/python.jsonl", "exam"),
    ("natv2_calendar", "data_ext_e4/final_v2/calendar.jsonl", "exam"),
    ("calendar_v3", "data_ext_cal_v3/final_v3/calendar_v3.jsonl", "exam"),
    ("p0_db_nontarget", "data_ext_p0_db_nontarget/final/database_nontarget.jsonl", "exam"),
    ("p0_cal_v3fix", "data_ext_p0_cal_titlecount/final/title_count_v3fix.jsonl", "exam"),
]


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--json-out", type=Path, default=None)
    args = ap.parse_args()
    root: Path = args.root

    inventory: Dict[str, Dict[str, Any]] = {}
    disagreements = []
    unmapped = []
    by_pattern_sources: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_pattern_unique: Dict[str, Dict[str, set]] = defaultdict(lambda: defaultdict(set))

    for name, rel, kind in SOURCES:
        path = root / rel
        if not path.exists():
            print("MISSING %s" % path, file=sys.stderr)
            continue
        rows = read_jsonl(path)
        counts: Counter = Counter()
        for row in rows:
            c = classify_item(row)
            counts[c.pattern] += 1
            ident = experience_identity(row)
            by_pattern_sources[c.pattern][name] += 1
            by_pattern_unique[c.pattern][name].add(ident)
            if c.source != "template_id":
                unmapped.append({
                    "source": name,
                    "episode_id": row.get("episode_id"),
                    "template_id": row.get("template_id"),
                    "classification": c.to_dict(),
                })
            # If both template_id and SQL exist, record structural agreement.
            if row.get("template_id") in TEMPLATE_TO_PATTERN and row.get("expected_tool") == "db_query":
                sql = (row.get("expected_arguments") or {}).get("sql")
                if sql:
                    structural = classify_sql_query(sql)
                    official = TEMPLATE_TO_PATTERN[row["template_id"]]
                    if structural and structural != official:
                        disagreements.append({
                            "source": name,
                            "episode_id": row.get("episode_id"),
                            "template_id": row.get("template_id"),
                            "template_pattern": official,
                            "structural_pattern": structural,
                            "sql": sql,
                        })
        cov = pattern_coverage(rows)
        div = experience_diversity(rows)
        inventory[name] = {
            "path": rel,
            "kind": kind,
            "n": len(rows),
            "pattern_counts": dict(counts),
            "coverage": cov.to_dict(),
            "diversity": div.to_dict(),
        }

    print("# Operation-pattern inventory (read-only)")
    print()
    print("| pattern | family | train_phase2 unique/slots | e4_pool unique/slots | exams (n) | official |")
    print("|---|---|---|---|---|---|")
    exam_names = [n for n, _, k in SOURCES if k == "exam"]
    train_names = [n for n, _, k in SOURCES if k == "train"]
    pool_names = [n for n, _, k in SOURCES if k == "replay_pool"]
    all_pats = list(OFFICIAL_PATTERNS) + sorted(
        p for p in by_pattern_sources if p not in OFFICIAL_PATTERNS
    )
    for pat in all_pats:
        def fmt(names):
            slots = sum(by_pattern_sources[pat].get(n, 0) for n in names)
            uniq = len(set().union(*[by_pattern_unique[pat][n] for n in names if n in by_pattern_unique[pat]]))
            if slots == 0:
                return "—"
            return "%d/%d" % (uniq, slots)

        exam_bits = []
        for n in exam_names:
            c = by_pattern_sources[pat].get(n, 0)
            if c:
                exam_bits.append("%s:%d" % (n, c))
        official = "yes" if pat in OFFICIAL_PATTERNS else "no"
        print("| `%s` | %s | %s | %s | %s | %s |" % (
            pat,
            PATTERN_FAMILY.get(pat, "?"),
            fmt(train_names),
            fmt(pool_names),
            "; ".join(exam_bits) or "—",
            official,
        ))

    print()
    print("Official catalog size: %d. Descriptions:" % len(OFFICIAL_PATTERNS))
    for pat in OFFICIAL_PATTERNS:
        print("- `%s`: %s" % (pat, PATTERN_DESC[pat]))

    print()
    print("Template_id vs structural SQL disagreements: %d" % len(disagreements))
    for item in disagreements[:20]:
        print("  - %s %s template=%s structural=%s sql=%s" % (
            item["source"], item["episode_id"], item["template_pattern"],
            item["structural_pattern"], item["sql"]))
    print("Items not classified via template_id: %d" % len(unmapped))
    for item in unmapped[:20]:
        print("  - %s %s tid=%s -> %s" % (
            item["source"], item["episode_id"], item["template_id"],
            item["classification"]["pattern"]))

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "inventory": inventory,
            "disagreements": disagreements,
            "unmapped_via_template": unmapped,
        }
        args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print("wrote %s" % args.json_out)


if __name__ == "__main__":
    main()
