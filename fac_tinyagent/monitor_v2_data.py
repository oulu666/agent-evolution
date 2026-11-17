"""[ext 2026-11-11] Monitor v2 probe set (writes data_ext_monitor_v2/ only).

Per old family 32 probes in labelled subsets:
  database: filter-top canonical wording (12), filter-top paraphrases (12),
            filtered-average natural wording (8)
  file:     last-match on new paths/new files, canonical wording (12),
            last-match paraphrases (12), first-match paraphrases (8);
            gold = the matching *line* (answer_spec match), filler words are
            disjoint from pattern words
  python:   explicit median (8), canonical natural median (8),
            sort-trigger natural paraphrases that previously drew the invalid
            ``stats_sorted`` call (16)
Leakage guards: no task signature, no tool call (tool+arguments) and no median
value-set that appears in data_phase2, data_replay_study or data_round2
(train/val/test/pool/monitor/final); new file roots only.
"""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from .research_data import _db_candidates, call_signature, task_signature
from .round2_data import DB_PATH, _make_row
from .utils import ensure_dir, read_jsonl, sha256_file, write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data_ext_monitor_v2"
FAMILIES = ("file", "database", "python")
SEED = 20261111
SOURCES = [ROOT / "data_phase2", ROOT / "data_replay_study", ROOT / "data_round2"]


def _all_rows():
    for root in SOURCES:
        for path in sorted(root.glob("*/*.jsonl")):
            for row in read_jsonl(path):
                if "prompt" in row and "expected_tool" in row:
                    yield path, row


def used_sets() -> Dict[str, Set]:
    sigs, calls, medians, paths = set(), set(), set(), set()
    for _, row in _all_rows():
        sigs.add(task_signature(row))
        calls.add(call_signature(row))
        if row.get("expected_tool") == "stats_median":
            medians.add(tuple(sorted(float(v) for v in row["expected_arguments"]["values"])))
        for p in (row.get("environment") or {}).get("files", {}) or {}:
            paths.add(p)
    return {"sigs": sigs, "calls": calls, "medians": medians, "paths": paths}


RANK_RE = re.compile(r"SELECT (\w+) FROM (\w+) WHERE (\w+) > ([\d.]+) ORDER BY \w+ DESC, id ASC LIMIT (\d+)")
MEAN_RE = re.compile(r"SELECT AVG\((\w+)\) AS v FROM (\w+) WHERE (\w+) > ([\d.]+)")
DB_PARA = [
    "Among the {t} rows whose {c} exceeds {v}, which {k} {n} values have the highest {c}? "
    "If two rows tie, the smaller id comes first. Answer with a JSON list.",
    "I only care about {t} entries with {c} above {v}. Give me the top {k} of them by {c} "
    "(largest first, ties broken by lower id), returning just their {n} values as a JSON list.",
    "Filter {t} to rows where {c} > {v}, rank what is left by {c} from high to low "
    "(ties: ascending id) and return the first {k} {n} values as a JSON list.",
]
DB_MEAN = [
    "What is the mean {m} of the {t} rows whose {c} is above {v}?",
    "Looking only at {t} records with {c} greater than {v}, what is their average {m}?",
]


def build_database(used, rng) -> List[Dict[str, Any]]:
    banks = _db_candidates(DB_PATH)
    rank = [c for c in banks["rank"] if call_signature(c) not in used["calls"]]
    mean = [c for c in banks["filter_mean"] if call_signature(c) not in used["calls"]
            and MEAN_RE.match(c["expected_arguments"]["sql"])]
    rng.shuffle(rank)
    rng.shuffle(mean)
    if len(rank) < 24 or len(mean) < 8:
        raise ValueError("not enough unused database calls: rank=%d mean=%d" % (len(rank), len(mean)))
    rows = []
    for i, c in enumerate(rank[:12]):
        rows.append(_make_row("database", "mv2-database-filter_top_canon-%03d" % i,
                              "mv2_db_filter_top_canon", "monitor", c["prompt"],
                              c["expected_tool"], c["expected_arguments"], c["skill_labels"],
                              c.get("environment", {}), c["answer_spec"], "db_filter_top"))
    for i, c in enumerate(rank[12:24]):
        n, t, col, v, k = RANK_RE.match(c["expected_arguments"]["sql"]).groups()
        prompt = DB_PARA[i % len(DB_PARA)].format(t=t, c=col, v=v, k=k, n=n)
        rows.append(_make_row("database", "mv2-database-filter_top_para-%03d" % i,
                              "mv2_db_filter_top_para", "monitor", prompt,
                              c["expected_tool"], c["expected_arguments"], c["skill_labels"],
                              c.get("environment", {}), c["answer_spec"], "db_filter_top"))
    for i, c in enumerate(mean[:8]):
        m, t, col, v = MEAN_RE.match(c["expected_arguments"]["sql"]).groups()
        prompt = DB_MEAN[i % len(DB_MEAN)].format(m=m, t=t, c=col, v=v)
        rows.append(_make_row("database", "mv2-database-filter_mean_nat-%03d" % i,
                              "mv2_db_filter_mean_nat", "monitor", prompt,
                              c["expected_tool"], c["expected_arguments"], c["skill_labels"],
                              c.get("environment", {}), c["answer_spec"], "db_filter_mean"))
    return rows


WORDS = ["sierra", "tango", "oscar", "papa", "romeo", "victor", "whiskey", "quebec"]
FILLER = ["amber", "cobalt", "ivory", "maroon", "teal", "umber"]
DIRS = ["ops", "lab", "qa", "finance", "support", "infra"]
NAMES = ["journal", "trace", "memo", "ledger", "digest", "audit"]
FILE_LAST_PARA = [
    "Open {p} and tell me the final line that mentions '{w}'. Return that line exactly.",
    "Which is the bottom-most line of {p} containing the word '{w}'? Reply with that full line.",
    "Search {p} for '{w}' and give back only the last matching line, exactly as written.",
]
FILE_FIRST_PARA = [
    "Find the earliest line in {p} that mentions '{w}' and return it exactly.",
    "In {p}, which line is the first one to contain '{w}'? Return the whole line.",
]


def _file_content(rng, word, style) -> str:
    n_lines = rng.choice([6, 7, 8])
    lines = []
    for i in range(n_lines):
        filler = rng.choice(FILLER)
        if style == 0:
            lines.append("line %d: %s value %d" % (i + 1, filler, rng.randint(10, 99)))
        else:
            lines.append("[%02d] %s reading %d at step %d" % (i + 1, filler, rng.randint(10, 99), rng.randint(1, 50)))
    hits = sorted(rng.sample(range(n_lines), rng.choice([2, 3])))
    for h in hits:
        if style == 0:
            lines[h] = "line %d: %s appears in this line" % (h + 1, word)
        else:
            lines[h] = "[%02d] %s event logged at step %d" % (h + 1, word, rng.randint(1, 50))
    return "\n".join(lines) + "\n"


def build_file(used, rng) -> List[Dict[str, Any]]:
    rows = []
    specs = ([("last_canon", i) for i in range(12)] + [("last_para", i) for i in range(12)]
             + [("first_para", i) for i in range(8)])
    for subset, i in specs:
        path = "mv2_%s/%s/%s_%02d.%s" % (subset, rng.choice(DIRS), rng.choice(NAMES), i,
                                         rng.choice(["txt", "log", "md"]))
        if path in used["paths"]:
            raise ValueError("path collision %s" % path)
        word = rng.choice(WORDS)
        style = 0 if subset == "last_canon" else rng.choice([0, 1])
        content = _file_content(rng, word, style)
        if subset == "last_canon":
            prompt = "Return the last line in %s that contains the word '%s'." % (path, word)
            spec = {"kind": "match", "index": -1}
        elif subset == "last_para":
            prompt = FILE_LAST_PARA[i % len(FILE_LAST_PARA)].format(p=path, w=word)
            spec = {"kind": "match", "index": -1}
        else:
            prompt = FILE_FIRST_PARA[i % len(FILE_FIRST_PARA)].format(p=path, w=word)
            spec = {"kind": "match", "index": 0}
        rows.append(_make_row("file", "mv2-file-%s-%03d" % (subset, i), "mv2_file_" + subset,
                              "monitor", prompt, "file_search", {"path": path, "pattern": word},
                              ["file_search", "line_index"], {"files": {path: content}},
                              spec, "file_" + subset))
    return rows


PY_SORT_PARA = [
    "Sort these readings in ascending order and tell me which one sits exactly in the middle: {v}.",
    "Here are some scores: {v}. If you line them up from lowest to highest, what number lands in the center?",
    "Arrange {v} from smallest to largest. Which value is right in the middle of that ordering?",
    "Given the sample {v}, what value splits it so that half of the numbers are below it and half are above?",
]


def build_python(used, rng) -> List[Dict[str, Any]]:
    rows = []
    seen = set(used["medians"])
    specs = ([("explicit", i) for i in range(8)] + [("natural_canon", i) for i in range(8)]
             + [("sort_para", i) for i in range(16)])
    for subset, i in specs:
        while True:
            values = rng.sample(range(10, 101), 7)
            key = tuple(sorted(float(v) for v in values))
            if key not in seen:
                seen.add(key)
                break
        text = json.dumps(values)
        if subset == "explicit":
            prompt = "The observations are %s. What is their median?" % text
        elif subset == "natural_canon":
            prompt = ("The observations are %s. After ordering them from smallest to largest, "
                      "what is the value in the middle position?" % text)
        else:
            prompt = PY_SORT_PARA[i % len(PY_SORT_PARA)].format(v=text)
        rows.append(_make_row("python", "mv2-python-%s-%03d" % (subset, i), "mv2_py_" + subset,
                              "monitor", prompt, "stats_median", {"values": values},
                              ["stat_median", "numeric_input"], {}, {"kind": "identity"},
                              "median_" + subset))
    return rows


def subset_of(episode_id: str) -> str:
    parts = episode_id.split("-")
    return parts[2] if len(parts) >= 4 and parts[0] == "mv2" else "all"


def verify(rows_by_family, used) -> Dict[str, Any]:
    seen = set()
    for family, rows in rows_by_family.items():
        for row in rows:
            sig, call = task_signature(row), call_signature(row)
            if sig in used["sigs"] or sig in seen:
                raise ValueError("signature leak/duplicate %s" % row["episode_id"])
            if family != "file" and call in used["calls"]:
                raise ValueError("tool-call leak %s" % row["episode_id"])
            seen.add(sig)
            obs = json.loads(row["expected_observation"])
            if not obs.get("ok"):
                raise ValueError("unusable %s" % row["episode_id"])
    return {"checked": len(seen)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    used = used_sets()
    if args.verify_only:
        rows = {f: read_jsonl(OUT / (f + ".jsonl")) for f in FAMILIES}
        print(verify(rows, used))
        return
    if (OUT / "manifest.json").exists():
        print("exists, skip:", OUT)
        return
    rng = random.Random(SEED)
    rows = {"database": build_database(used, rng), "file": build_file(used, rng),
            "python": build_python(used, rng)}
    info = verify(rows, used)
    ensure_dir(OUT)
    for family in FAMILIES:
        write_jsonl(OUT / (family + ".jsonl"), rows[family])
    manifest = {"seed": SEED, "checked": info["checked"],
                "families": {f: {"count": len(rows[f]),
                                 "subsets": {s: sum(subset_of(r["episode_id"]) == s for r in rows[f])
                                             for s in sorted({subset_of(r["episode_id"]) for r in rows[f]})},
                                 "sha256": sha256_file(OUT / (f + ".jsonl"))} for f in FAMILIES},
                "leakage_guards": ["task_signature vs data_phase2/data_replay_study/data_round2",
                                   "tool-call signature (database/python)",
                                   "median value-set (sorted) exclusion", "new file roots mv2_*"]}
    write_json(OUT / "manifest.json", manifest)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
