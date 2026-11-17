"""Independent monitoring probes and sealed final tests for the replay study.

This is an instance/wording holdout under the existing family-specific tool
schemas, not a claim of structural OOD generalization. No model is loaded here.
The sealed_test split must not select methods, thresholds, or checkpoints.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import PROJECT_ROOT
from .data.generate import _observation, _schemas, build_system_prompt
from .data.templates import DB_COLUMNS, DB_GROUPS, DB_NAMES, DB_NUMERIC, stable_rng
from .metrics import answers_equal, observations_equal
from .tools import build_db_registry
from .utils import (canonical_json, now_iso, read_json, read_jsonl, sha256_file,
                    sha256_text, write_json, write_jsonl)

FAMILIES = ("file", "database", "python", "calendar")
SPLITS = ("probe", "sealed_test")
QUOTAS = {
    "file": {name: (4, 10) for name in
             ("line_count", "word_count", "first_match", "last_match", "list", "write")},
    "python": {name: (4, 10) for name in
               ("mean", "median", "std", "percentile", "correlation", "regression")},
    "database": {"filter_count": (4, 12), "filter_mean": (4, 12),
                 "group_count": (4, 10), "rank": (6, 16),
                 "schema": (4, 8), "tables": (2, 2)},
    "calendar": {"list": (4, 10), "search": (4, 10), "month": (1, 2),
                 "attendees": (7, 18), "free": (8, 20)},
}


def task_signature(row: Dict[str, Any]) -> str:
    """Exact task identity deliberately excludes split and template labels."""
    return sha256_text(canonical_json({
        "prompt": row["prompt"], "tool": row["expected_tool"],
        "arguments": row["expected_arguments"],
    }))


def call_signature(row: Dict[str, Any]) -> str:
    return sha256_text(canonical_json({"tool": row["expected_tool"],
                                       "arguments": row["expected_arguments"]}))


def _candidate(prompt, tool, arguments, skills, answer_spec=None, files=None):
    return {"prompt": prompt, "expected_tool": tool,
            "expected_arguments": arguments, "skill_labels": skills,
            "answer_spec": answer_spec or {"kind": "identity"},
            "environment": {"files": files} if files is not None else {}}


def project_answer(result: Any, spec: Dict[str, Any]) -> Any:
    """Recompute the expected answer from an actual successful observation."""
    kind = spec["kind"]
    if kind == "identity":
        return result
    if kind == "length":
        return len(result)
    if kind == "line_count":
        return len(result.splitlines())
    if kind == "word_count":
        return len(result.split())
    if kind == "match":
        return result[spec["index"]]["text"] if result else ""
    if kind == "field":
        return result[spec["field"]]
    if kind == "scalar":
        return result["rows"][0][0]
    if kind == "rows_first":
        return [row[0] for row in result["rows"]]
    if kind == "rows_mapping":
        return {row[0]: row[1] for row in result["rows"]}
    if kind == "column_type":
        return next(column["type"] for column in result
                    if column["name"] == spec["column"])
    if kind == "sorted":
        return sorted(result)
    if kind == "item":
        return result[spec["index"]] if result else None
    if kind == "pluck":
        values = [item[spec["field"]] for item in result]
        if spec.get("unique"):
            values = list(set(values))
        return sorted(values)
    raise ValueError("Unknown answer projection: %s" % kind)


def _file_candidates(seed):
    banks = {key: [] for key in QUOTAS["file"]}
    rng = stable_rng(seed, "file", "new_entities", "study", 0)
    for index in range(100):
        directory = "replay_study_%d/case_%03d" % (seed, index)
        path = directory + "/notes.txt"
        word = rng.choice(["amber", "birch", "cedar", "dune", "elm", "fern"])
        lines = ["record %d has value %d" % (j, rng.randint(10, 99))
                 for j in range(rng.randint(5, 10))]
        for position in rng.sample(range(len(lines)), 2):
            lines[position] += " " + word
        files = {path: "\n".join(lines) + "\n"}
        for category, prompt, spec in (
            ("line_count", "Read %s and give the number of lines." % path,
             {"kind": "line_count"}),
            ("word_count", "Count the whitespace-separated words in %s." % path,
             {"kind": "word_count"}),
        ):
            banks[category].append(_candidate(prompt, "file_read", {"path": path},
                                              ["file_read", "counting"], spec, files))
        for category, position in (("first_match", 0), ("last_match", -1)):
            prompt = "Search %s for '%s'; return the %s matching line verbatim." % (
                path, word, "earliest" if position == 0 else "latest")
            banks[category].append(_candidate(
                prompt, "file_search", {"path": path, "pattern": word},
                ["file_search", "line_index"], {"kind": "match", "index": position}, files))
        listed_files = {directory + "/item_%02d.txt" % j: "value %d\n" % j
                        for j in range(rng.randint(2, 6))}
        listed_files[directory + "/nested/summary.md"] = "summary\n"
        banks["list"].append(_candidate(
            "Return a sorted JSON list of all file paths beneath %s." % directory,
            "file_list", {"directory": directory}, ["file_list", "final_formatting"],
            {"kind": "sorted"}, listed_files))
        content = "entry %d: %s measurement %d" % (index, word, rng.randint(100, 999))
        target = directory + "/saved.txt"
        banks["write"].append(_candidate(
            "Store '%s' at %s. Return the number of characters saved." % (content, target),
            "file_write", {"path": target, "content": content},
            ["file_write", "character_count"], {"kind": "field", "field": "characters"}, {}))
    return banks


def _stats_candidates(seed):
    banks = {key: [] for key in QUOTAS["python"]}
    rng = stable_rng(seed, "python", "new_values", "study", 0)
    for index in range(100):
        values = rng.sample(range(10, 101), 7)
        ys = [2 * value + rng.randint(-5, 5) for value in values]
        for kind, operation in (("mean", "arithmetic mean"), ("median", "median"),
                                ("std", "population standard deviation")):
            banks[kind].append(_candidate(
                "Use a statistical tool to find the %s of %s." % (operation, json.dumps(values)),
                "stats_" + kind, {"values": values}, ["stat_" + kind, "numeric_input"]))
        percentile = rng.choice([10, 25, 50, 75, 90])
        banks["percentile"].append(_candidate(
            "Find percentile %d for these values: %s." % (percentile, json.dumps(values)),
            "stats_percentile", {"values": values, "percentile": percentile},
            ["stat_percentile", "numeric_input"]))
        for kind, tool, request in (
            ("correlation", "stats_correlation", "Pearson correlation"),
            ("regression", "stats_linear_regression", "regression slope and intercept for y on x"),
        ):
            banks[kind].append(_candidate(
                "Return the %s for x=%s and y=%s." % (request, json.dumps(values), json.dumps(ys)),
                tool, {"xs": values, "ys": ys}, ["stat_" + kind, "numeric_input"]))
    return banks


def _db_candidates(db_path):
    banks = {key: [] for key in QUOTAS["database"]}
    registry = build_db_registry(str(db_path))
    for table, columns in DB_NUMERIC.items():
        for column in columns:
            result = registry.execute("db_query", {
                "sql": "SELECT DISTINCT %s FROM %s ORDER BY %s" % (column, table, column)})
            if not result.get("ok"):
                raise ValueError("Cannot inspect fixture: %s" % result)
            values = [row[0] for row in result["result"]["rows"]]
            thresholds = values[:-1]  # Every filter keeps at least one row.
            for threshold in thresholds:
                literal = str(threshold)
                condition = "%s > %s" % (column, literal)
                common = "in %s where %s is greater than %s" % (table, column, literal)
                banks["filter_count"].append(_candidate(
                    "Count the rows %s." % common, "db_query",
                    {"sql": "SELECT COUNT(*) AS n FROM %s WHERE %s" % (table, condition)},
                    ["sql_filter", "sql_count"], {"kind": "scalar"}))
                for measured in columns:
                    banks["filter_mean"].append(_candidate(
                        "Give the average %s among rows %s." % (measured, common), "db_query",
                        {"sql": "SELECT AVG(%s) AS v FROM %s WHERE %s" % (measured, table, condition)},
                        ["sql_filter", "sql_aggregation"], {"kind": "scalar"}))
                group = DB_GROUPS[table]
                banks["group_count"].append(_candidate(
                    "For rows %s, return a JSON object mapping each %s to its row count."
                    % (common, group), "db_query",
                    {"sql": "SELECT %s, COUNT(*) AS n FROM %s WHERE %s GROUP BY %s ORDER BY %s"
                     % (group, table, condition, group, group)},
                    ["sql_filter", "sql_group", "sql_count"], {"kind": "rows_mapping"}))
                for limit in (2, 3, 4):
                    name = DB_NAMES[table]
                    banks["rank"].append(_candidate(
                        "For rows %s, list up to %d %s values by decreasing %s; break ties by "
                        "increasing id. Return a JSON list." % (common, limit, name, column),
                        "db_query", {"sql": "SELECT %s FROM %s WHERE %s ORDER BY %s DESC, id ASC LIMIT %d"
                                     % (name, table, condition, column, limit)},
                        ["sql_filter", "sql_order", "sql_select"], {"kind": "rows_first"}))
        for column in DB_COLUMNS[table]:
            banks["schema"].append(_candidate(
                "Inspect the schema of %s and return the declared SQL type of column %s."
                % (table, column), "db_schema", {"table": table},
                ["schema_reading"], {"kind": "column_type", "column": column}))
    for prompt, projection in (
        ("Return the available database table names in alphabetical order.", {"kind": "sorted"}),
        ("Use the table-listing tool and return how many tables are available.", {"kind": "length"}),
        ("Use the table-listing tool and return the alphabetically first table name.", {"kind": "item", "index": 0}),
        ("Use the table-listing tool and return the alphabetically last table name.", {"kind": "item", "index": -1}),
    ):
        banks["tables"].append(_candidate(prompt, "db_list_tables", {},
                                          ["tool_selection", "schema_reading"], projection))
    return banks


def _calendar_candidates(calendar_path):
    events = read_json(calendar_path)["events"]
    banks = {key: [] for key in QUOTAS["calendar"]}
    for date in sorted({event["date"] for event in events}):
        for field in ("id", "title", "location"):
            banks["list"].append(_candidate(
                "List the distinct event %s values on %s in alphabetical order." % (field, date),
                "calendar_list", {"date": date}, ["calendar_list", "calendar_date"],
                {"kind": "pluck", "field": field, "unique": True}))
        for duration in range(15, 61, 5):
            for position, label in ((0, "earliest"), (-1, "latest")):
                banks["free"].append(_candidate(
                    "On %s, return the %s free workday interval of at least %d minutes, "
                    "as an object with start and end." % (date, label, duration),
                    "calendar_free_slots", {"date": date, "duration_minutes": duration},
                    ["calendar_time", "calendar_free"], {"kind": "item", "index": position}))
    fragments = sorted({event["title"] for event in events} |
                       {word for event in events for word in event["title"].split()})
    for fragment in fragments:
        for field in ("id", "date"):
            banks["search"].append(_candidate(
                "Search event titles for '%s' and return their %s values as a sorted list."
                % (fragment, field), "calendar_search", {"title": fragment},
                ["calendar_search", "calendar_date"], {"kind": "pluck", "field": field}))
    for month in sorted({event["date"][:7] for event in events}):
        banks["month"].append(_candidate(
            "Use the monthly counting tool to obtain the number of entries for %s." % month,
            "calendar_count", {"month": month}, ["calendar_month", "calendar_count"]))
    for event in events:
        for operation, spec in (("a sorted list of attendees", {"kind": "sorted"}),
                                ("the attendee count", {"kind": "length"})):
            banks["attendees"].append(_candidate(
                "For calendar event %s, return %s." % (event["id"], operation),
                "calendar_attendees", {"event_id": event["id"]},
                ["calendar_attendees", "calendar_event"], spec))
    return banks


def _legacy_rows(roots):
    rows, files = [], []
    for root in roots:
        root = Path(root).resolve()
        if not root.is_dir():
            raise FileNotFoundError("Missing exclusion root: %s" % root)
        for family in FAMILIES:
            for split in ("train", "val", "test"):
                path = root / family / (split + ".jsonl")
                if path.exists():
                    rows.extend(read_jsonl(path))
                    files.append({"path": str(path), "sha256": sha256_file(path)})
    if not files:
        raise ValueError("No legacy data files found for exclusion checking")
    return rows, files


def _relative_path(path, root):
    """Keep commitments usable from both Windows and the WSL checkout."""
    try:
        return os.path.relpath(str(path), str(root)).replace("\\", "/")
    except ValueError:  # Different Windows drives cannot be made relative.
        return Path(path).as_posix()


def _make_episode(candidate, family, category, split, index, system, fixtures):
    row = dict(candidate)
    observation = _observation(family, row["expected_tool"], row["expected_arguments"],
                               row["environment"], str(fixtures / "toolbench.db"),
                               str(fixtures / "calendar.json"))
    parsed = json.loads(observation)
    if not parsed.get("ok"):
        raise ValueError("Invalid generated task: %s" % observation)
    answer = project_answer(parsed["result"], row["answer_spec"])
    row.update({"episode_id": "%s-%s-%s-%03d" % (family, split, category, index),
                "tool_family": family, "split": split, "template_id": "study_" + category,
                "system": system, "expected_observation": observation,
                "expected_final_answer": answer, "data_signature": task_signature(row),
                "evaluation_only": True, "selection_allowed": split == "probe"})
    row["messages"] = [
        {"role": "system", "content": system}, {"role": "user", "content": row["prompt"]},
        {"role": "assistant", "content": json.dumps({"tool": row["expected_tool"],
                                                      "arguments": row["expected_arguments"]})},
        {"role": "user", "content": "TOOL RESULT:\n" + observation},
        {"role": "assistant", "content": json.dumps({"answer": answer})},
    ]
    return row


def generate_study(source_root: Path, output_root: Path, seed: int = 20261109,
                   exclusion_roots: Optional[List[Path]] = None) -> Dict[str, Any]:
    source_root, output_root = Path(source_root).resolve(), Path(output_root).resolve()
    roots = list(exclusion_roots) if exclusion_roots is not None else [source_root]
    if source_root not in [Path(root).resolve() for root in roots]:
        roots.append(source_root)
    legacy, legacy_files = _legacy_rows(roots)
    if output_root.exists():
        raise FileExistsError("Refusing to replace an existing study dataset: %s" % output_root)
    fixtures = output_root / "fixtures"
    fixtures.mkdir(parents=True)
    for name in ("toolbench.db", "calendar.json"):
        shutil.copyfile(str(source_root / "fixtures" / name), str(fixtures / name))
    banks = {"file": _file_candidates(seed), "python": _stats_candidates(seed),
             "database": _db_candidates(fixtures / "toolbench.db"),
             "calendar": _calendar_candidates(fixtures / "calendar.json")}
    old_signatures = {task_signature(row) for row in legacy}
    used = set(old_signatures)
    manifest = {
        "version": 1, "created": now_iso(), "seed": seed,
        "path_base": "manifest directory",
        "source_root": _relative_path(source_root, output_root),
        "exclusion_roots": [_relative_path(Path(root).resolve(), output_root) for root in roots],
        "legacy_files": [{"path": _relative_path(record["path"], output_root),
                          "sha256": record["sha256"]} for record in legacy_files],
        "legacy_rows": len(legacy),
        "task_identity": "sha256(canonical JSON of prompt, tool, arguments)",
        "purpose": {"probe": "Monitoring and controller selection only; never replay as training data.",
                    "sealed_test": "Final evaluation after choices are frozen; never used for selection or tuning."},
        "limitations": ["Instance/wording holdout, not structural OOD.",
                        "The existing fixed database and calendar fixtures are reused.",
                        "Unique tasks can share a tool call or answer; counts are not independent environments.",
                        "Family-specific tool menus are retained; no cross-family routing.",
                        "Sealing is an experiment protocol and hash commitment, not access control."],
        "fixtures": {name: sha256_file(fixtures / name) for name in ("toolbench.db", "calendar.json")},
        "families": {},
    }
    for family in FAMILIES:
        schema = _schemas(family, str(fixtures / "toolbench.db"), str(fixtures / "calendar.json"))
        system = build_system_prompt(family, schema)
        split_rows = {split: [] for split in SPLITS}
        for category, quotas in QUOTAS[family].items():
            candidates = list(banks[family][category])
            stable_rng(seed, family, category, "selection", 0).shuffle(candidates)
            available = []
            seen_category = set()
            for candidate in candidates:
                signature = task_signature(candidate)
                if signature not in used and signature not in seen_category:
                    available.append(candidate)
                    seen_category.add(signature)
            if len(available) < sum(quotas):
                raise ValueError("Not enough distinct tasks for %s/%s" % (family, category))
            offset = 0
            for split, quota in zip(SPLITS, quotas):
                for index, candidate in enumerate(available[offset:offset + quota]):
                    row = _make_episode(candidate, family, category, split, index, system, fixtures)
                    used.add(task_signature(row))
                    split_rows[split].append(row)
                offset += quota
        manifest["families"][family] = {}
        for split, rows in split_rows.items():
            path = output_root / family / (split + ".jsonl")
            write_jsonl(path, rows)
            manifest["families"][family][split] = {
                "path": path.relative_to(output_root).as_posix(), "count": len(rows),
                "sha256": sha256_file(path), "unique_tasks": len({task_signature(r) for r in rows}),
                "unique_calls": len({call_signature(r) for r in rows}),
                "tools": dict(sorted(Counter(r["expected_tool"] for r in rows).items())),
                "categories": dict(sorted(Counter(r["template_id"] for r in rows).items())),
                "skills": dict(sorted(Counter(s for r in rows for s in r["skill_labels"]).items())),
            }
        probe_calls = {call_signature(row) for row in split_rows["probe"]}
        test_calls = {call_signature(row) for row in split_rows["sealed_test"]}
        manifest["families"][family]["call_overlap_probe_sealed"] = len(probe_calls & test_calls)
    write_json(output_root / "manifest.json", manifest)
    verification = verify_study(output_root)
    write_json(output_root / "verification.json", verification)
    return manifest


def verify_study(output_root: Path) -> Dict[str, Any]:
    """Read-only verification of commitments, exact isolation, and executed gold."""
    output_root = Path(output_root).resolve()
    manifest = read_json(output_root / "manifest.json")
    for record in manifest["legacy_files"]:
        if sha256_file(output_root / record["path"]) != record["sha256"]:
            raise ValueError("Legacy source changed: %s" % record["path"])
    legacy, _ = _legacy_rows([output_root / root for root in manifest["exclusion_roots"]])
    old = {task_signature(row) for row in legacy}
    fixtures = output_root / "fixtures"
    for name, digest in manifest["fixtures"].items():
        if sha256_file(fixtures / name) != digest:
            raise ValueError("Fixture hash mismatch: %s" % name)
    seen, ids, report = set(), set(), {}
    for family in FAMILIES:
        report[family] = {}
        expected_system = build_system_prompt(family, _schemas(
            family, str(fixtures / "toolbench.db"), str(fixtures / "calendar.json")))
        for split, expected_n in (("probe", 24), ("sealed_test", 60)):
            record = manifest["families"][family][split]
            path = output_root / record["path"]
            if sha256_file(path) != record["sha256"]:
                raise ValueError("Data hash mismatch: %s" % path)
            rows = read_jsonl(path)
            if len(rows) != expected_n:
                raise ValueError("Wrong count for %s/%s" % (family, split))
            for row in rows:
                signature = task_signature(row)
                if signature in seen or signature in old or row["episode_id"] in ids:
                    raise ValueError("Duplicate or leaking task: %s" % row["episode_id"])
                seen.add(signature)
                ids.add(row["episode_id"])
                if row["split"] != split or row["tool_family"] != family:
                    raise ValueError("Incorrect split/family metadata")
                if row["selection_allowed"] != (split == "probe") or not row["evaluation_only"]:
                    raise ValueError("Incorrect evaluation-use restriction")
                if row["system"] != expected_system or row["messages"][0]["content"] != expected_system:
                    raise ValueError("Incorrect family-specific tool menu")
                observation = _observation(family, row["expected_tool"], row["expected_arguments"],
                                           row["environment"], str(fixtures / "toolbench.db"),
                                           str(fixtures / "calendar.json"))
                parsed = json.loads(observation)
                if not parsed.get("ok") or not observations_equal(observation, row["expected_observation"]):
                    raise ValueError("Execution/gold mismatch: %s" % row["episode_id"])
                answer = project_answer(parsed["result"], row["answer_spec"])
                if not answers_equal(answer, row["expected_final_answer"]):
                    raise ValueError("Answer/gold mismatch: %s" % row["episode_id"])
                if [m["role"] for m in row["messages"]] != ["system", "user", "assistant", "user", "assistant"]:
                    raise ValueError("Malformed message sequence")
                if row["messages"][1]["content"] != row["prompt"] or json.loads(row["messages"][2]["content"]) != {
                        "tool": row["expected_tool"], "arguments": row["expected_arguments"]}:
                    raise ValueError("Message/task mismatch")
                if row["messages"][3]["content"] != "TOOL RESULT:\n" + row["expected_observation"]:
                    raise ValueError("Message/observation mismatch")
                if not answers_equal(json.loads(row["messages"][4]["content"])["answer"], answer):
                    raise ValueError("Message/answer mismatch")
            report[family][split] = {"count": len(rows), "executed_and_verified": len(rows),
                                    "unique_tasks": len(rows)}
    return {"ok": True, "total_verified": len(seen), "legacy_task_overlap": 0,
            "probe_sealed_task_overlap": 0, "report": report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=PROJECT_ROOT / "data_phase2")
    parser.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "data_replay_study")
    parser.add_argument("--seed", type=int, default=20261109)
    parser.add_argument("--exclude-roots", type=Path, nargs="+")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        print(json.dumps(verify_study(args.output_root), indent=2))
    else:
        roots = args.exclude_roots
        if roots is None:
            roots = [PROJECT_ROOT / name for name in
                     ("data", "data_smoke", "data_phase2", "data_phase2_smoke")
                     if (PROJECT_ROOT / name).is_dir()]
        manifest = generate_study(args.source_root, args.output_root, args.seed, roots)
        print(json.dumps({"output_root": str(args.output_root), "seed": manifest["seed"],
                          "counts_per_family": {"probe": 24, "sealed_test": 60},
                          "total_verified": 336}, indent=2))


if __name__ == "__main__":
    main()
