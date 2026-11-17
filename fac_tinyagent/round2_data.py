"""Common replay pool and independent monitor/final sets for round 2.

The pool contains the original old-tool training examples plus targeted natural
wording examples. Monitor and final sets are generated from separate instances;
they are never part of the replay pool.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

from .data.generate import _observation, _schemas, build_system_prompt
from .research_data import _db_candidates, project_answer, task_signature
from .utils import ensure_dir, read_json, read_jsonl, sha256_file, write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data_round2"
FAMILIES = ("file", "database", "python")
DB_PATH = ROOT / "data_phase2" / "fixtures" / "toolbench.db"
CALENDAR_PATH = ROOT / "data_phase2" / "fixtures" / "calendar.json"


def _system(family: str) -> str:
    return build_system_prompt(family, _schemas(family, str(DB_PATH), str(CALENDAR_PATH)))


def _messages(system: str, prompt: str, tool: str, arguments: Dict[str, Any],
              observation: str, answer: Any) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": json.dumps({"tool": tool, "arguments": arguments})},
        {"role": "user", "content": "TOOL RESULT:\n" + observation},
        {"role": "assistant", "content": json.dumps({"answer": answer})},
    ]


def _make_row(family: str, episode_id: str, template: str, split: str,
              prompt: str, tool: str, arguments: Dict[str, Any],
              skill_labels: Sequence[str], environment: Dict[str, Any],
              answer_spec: Dict[str, Any], target_type: str) -> Dict[str, Any]:
    observation = _observation(family, tool, arguments, environment,
                               str(DB_PATH), str(CALENDAR_PATH))
    parsed = json.loads(observation)
    if not parsed.get("ok"):
        raise ValueError("Bad generated task %s: %s" % (episode_id, observation))
    answer = project_answer(parsed["result"], answer_spec)
    system = _system(family)
    row = {
        "episode_id": episode_id, "tool_family": family, "split": split,
        "template_id": template, "target_type": target_type, "target": True,
        "prompt": prompt, "system": system, "environment": environment,
        "expected_tool": tool, "expected_arguments": arguments,
        "skill_labels": list(skill_labels), "answer_spec": answer_spec,
        "expected_observation": observation, "expected_final_answer": answer,
        "evaluation_only": split != "train", "selection_allowed": False,
    }
    row["messages"] = _messages(system, prompt, tool, arguments, observation, answer)
    row["data_signature"] = task_signature(row)
    return row


def _original_rows(family: str) -> List[Dict[str, Any]]:
    return read_jsonl(ROOT / "data_phase2" / family / "train.jsonl")


def _target_python(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    system = _system("python")
    result = []
    for index, row in enumerate(rows):
        if row["template_id"] != "stats_median":
            continue
        values = row["expected_arguments"]["values"]
        prompt = ("The observations are %s. After ordering them from smallest to "
                  "largest, what is the value in the middle position?"
                  % ", ".join(str(v) for v in values))
        result.append(_make_row(
            "python", "python-train-target_median_natural-%03d" % index,
            "target_median_natural", "train", prompt, "stats_median",
            {"values": values}, ["stat_median", "numeric_input"], {},
            {"kind": "identity"}, "median_natural"))
    return result


def _target_file(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    for index, row in enumerate(rows):
        if row["template_id"] != "file_search_first":
            continue
        observation = json.loads(row["expected_observation"])
        matches = observation.get("result", [])
        if not matches:
            continue
        answer = matches[-1]["text"]
        path = row["expected_arguments"]["path"]
        pattern = row["expected_arguments"]["pattern"]
        prompt = ("Return the last line in %s that contains the word '%s'."
                  % (path, pattern))
        result.append(_make_row(
            "file", "file-train-target_file_last_match-%03d" % index,
            "target_file_last_match", "train", prompt, "file_search",
            {"path": path, "pattern": pattern}, ["file_search", "line_index"],
            row.get("environment", {}), {"kind": "identity"}, "file_last_match"))
    return result


def _target_database(n_pool: int, n_monitor: int, n_final: int,
                     used: Set[str]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    candidates = _db_candidates(DB_PATH)["rank"]
    unique = {}
    for candidate in candidates:
        signature = task_signature(candidate)
        if signature not in used:
            unique.setdefault(signature, candidate)
    pool_candidates = list(unique.values())
    random.Random(20261111).shuffle(pool_candidates)
    needed = n_pool + n_monitor + n_final
    if len(pool_candidates) < needed:
        raise ValueError("Not enough independent database filter-top candidates")
    groups = [pool_candidates[:n_pool],
              pool_candidates[n_pool:n_pool + n_monitor],
              pool_candidates[n_pool + n_monitor:needed]]
    result = []
    for group_index, (group, split, offset) in enumerate(zip(
            groups, ("train", "monitor", "final"),
            (0, 0, 0))):
        rows = []
        for index, candidate in enumerate(group):
            target_type = "db_filter_top"
            rows.append(_make_row(
                "database", "database-%s-target_db_filter_top-%03d" % (split, index),
                "target_db_filter_top", split, candidate["prompt"],
                candidate["expected_tool"], candidate["expected_arguments"],
                candidate["skill_labels"], candidate.get("environment", {}),
                candidate["answer_spec"], target_type))
        result.append(rows)
    return result[0], result[1], result[2]


def _file_last_rows(prefix: str, count: int, seed: int,
                    used: Set[str]) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    words = ["juliet", "lima", "hotel", "india", "delta", "charlie", "kilo"]
    rows = []
    for index in range(count):
        path = "%s/file_%03d.txt" % (prefix, index)
        word = rng.choice(words)
        lines = []
        for line_index in range(6):
            lines.append("line %d: %s value %d" % (
                line_index + 1, rng.choice(["alpha", "bravo", "delta", "echo"]),
                rng.randint(10, 99)))
        for position in sorted(rng.sample(range(6), rng.choice([2, 3]))):
            lines[position] = "line %d: %s appears in this line" % (position + 1, word)
        content = "\n".join(lines) + "\n"
        row = _make_row(
            "file", "%s-last-%03d" % (prefix.replace("/", "-"), index),
            "target_file_last_match", "monitor" if "monitor" in prefix else "final",
            "Return the last line in %s that contains the word '%s'." % (path, word),
            "file_search", {"path": path, "pattern": word},
            ["file_search", "line_index"], {"files": {path: content}},
            {"kind": "identity"}, "file_last_match")
        if task_signature(row) in used:
            continue
        rows.append(row)
    return rows


def _python_natural(n_pairs: int, seed: int, split: str) -> List[Dict[str, Any]]:
    from .paired_median_data import generate_paired_median
    roots = [ROOT / "data_phase2", ROOT / "data_replay_study"]
    rows = generate_paired_median(n_pairs=n_pairs, seed=seed,
                                  exclusion_roots=roots)
    excluded = set()
    if split == "final":
        for row in read_jsonl(OUT / "monitor" / "python.jsonl"):
            excluded.add(tuple(sorted(row["expected_arguments"]["values"])))
    natural = []
    for row in rows:
        if row.get("wording") != "natural":
            continue
        if tuple(sorted(row["expected_arguments"]["values"])) in excluded:
            continue
        row = dict(row)
        row["template_id"] = "target_median_natural"
        row["target_type"] = "median_natural"
        row["target"] = True
        row["split"] = split
        row["episode_id"] = row["episode_id"].replace(
            "python-diagnostic-", "python-%s-" % split)
        natural.append(row)
    if len(natural) < n_pairs:
        raise ValueError("Not enough independent natural median tasks for %s" % split)
    return natural[:n_pairs]


def _used_signatures() -> Set[str]:
    used = set()
    for root in (ROOT / "data_phase2", ROOT / "data_replay_study"):
        for path in root.glob("*/*.jsonl"):
            for row in read_jsonl(path):
                used.add(task_signature(row))
    return used


def build_pool() -> Dict[str, Any]:
    used = _used_signatures()
    pool = {}
    target_rows = {}
    for family in FAMILIES:
        original = _original_rows(family)
        targets = (_target_python(original) if family == "python" else
                   _target_file(original) if family == "file" else [])
        pool[family] = original + targets
        target_rows[family] = targets
    # Database target rows are generated from the fixture bank, independent of train.
    db_targets, _, _ = _target_database(11, 0, 0, used)
    pool["database"] += db_targets
    target_rows["database"] = db_targets
    ensure_dir(OUT / "pool")
    for family in FAMILIES:
        write_jsonl(OUT / "pool" / (family + ".jsonl"), pool[family])
    return {"pool": pool, "target_rows": target_rows, "used": used}


def build_monitor_final(pool_info: Dict[str, Any]) -> None:
    used = set(pool_info["used"])
    for family in FAMILIES:
        for row in pool_info["pool"][family]:
            used.add(task_signature(row))
    monitor = {}
    final = {}
    for family in ("file", "python"):
        monitor[family] = (_file_last_rows("round2_monitor", 24, 20261112, used)
                           if family == "file" else
                           _python_natural(24, 20261112, "monitor"))
    db_monitor, = (_target_database(0, 24, 0, used)[1],)
    monitor["database"] = db_monitor
    for family in FAMILIES:
        for row in monitor[family]:
            used.add(task_signature(row))
    for family in ("file", "python"):
        final[family] = (_file_last_rows("round2_final", 30, 20261113, used)
                         if family == "file" else
                         _python_natural(30, 20261113, "final"))
    db_final, = (_target_database(0, 0, 30, used)[2],)
    final["database"] = db_final
    ensure_dir(OUT / "monitor")
    ensure_dir(OUT / "final")
    for family in FAMILIES:
        write_jsonl(OUT / "monitor" / (family + ".jsonl"), monitor[family])
        write_jsonl(OUT / "final" / (family + ".jsonl"), final[family])
    manifest = {
        "pool": {family: {"count": len(pool_info["pool"][family]),
                          "target_count": len(pool_info["target_rows"][family]),
                          "sha256": sha256_file(OUT / "pool" / (family + ".jsonl"))}
                 for family in FAMILIES},
        "monitor": {family: {"count": len(monitor[family]),
                             "sha256": sha256_file(OUT / "monitor" / (family + ".jsonl"))}
                    for family in FAMILIES},
        "final": {family: {"count": len(final[family]),
                           "sha256": sha256_file(OUT / "final" / (family + ".jsonl"))}
                  for family in FAMILIES},
        "target_ids": {family: [row["episode_id"] for row in pool_info["target_rows"][family]]
                       for family in FAMILIES},
        "target_types": {family: sorted({row["target_type"] for row in pool_info["target_rows"][family]})
                         for family in FAMILIES},
    }
    write_json(OUT / "manifest.json", manifest)
    print(json.dumps(manifest, indent=2))


def verify() -> None:
    manifest = read_json(OUT / "manifest.json")
    nonoriginal = set()
    target_seen = set()
    checked = 0
    for family in FAMILIES:
        target_ids = set(manifest["target_ids"][family])
        pool = read_jsonl(OUT / "pool" / (family + ".jsonl"))
        original_sigs = {task_signature(row) for row in pool
                         if row["episode_id"] not in target_ids}
        for row in pool:
            signature = task_signature(row)
            if row["episode_id"] in target_ids:
                if signature in original_sigs or signature in target_seen:
                    raise ValueError("Target duplicates original/other target: %s" % row["episode_id"])
                target_seen.add(signature)
                nonoriginal.add(signature)
            checked += 1
            if row["tool_family"] != family:
                raise ValueError("Wrong family in pool/%s" % family)
        for split in ("monitor", "final"):
            path = OUT / split / (family + ".jsonl")
            seen_here = set()
            for row in read_jsonl(path):
                signature = task_signature(row)
                if signature in original_sigs or signature in nonoriginal or signature in seen_here:
                    raise ValueError("Duplicate task in %s: %s" % (path, row["episode_id"]))
                seen_here.add(signature)
                nonoriginal.add(signature)
                checked += 1
                if row["tool_family"] != family:
                    raise ValueError("Wrong family in %s" % path)
                parsed = json.loads(_observation(
                    family, row["expected_tool"], row["expected_arguments"],
                    row.get("environment", {}), str(DB_PATH), str(CALENDAR_PATH)))
                if not parsed.get("ok"):
                    raise ValueError("Unusable task: %s" % row["episode_id"])
    print("verified", checked, "pool rows;", len(nonoriginal), "unique non-original tasks")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        verify()
        return
    if OUT.exists():
        raise FileExistsError("Refusing to replace existing data_round2")
    info = build_pool()
    build_monitor_final(info)
    verify()


if __name__ == "__main__":
    main()
