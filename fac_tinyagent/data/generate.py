"""Generate and verify leak-free sequential tool-learning episodes."""
from __future__ import annotations

import json
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from ..tools import (build_calendar_registry, build_db_registry,
                     build_file_registry, build_stats_registry)
from ..tools import (create_calendar_fixture, create_fixture,
                     materialize_sandbox)
from ..tools.file_tools import FileSandbox
from ..utils import (canonical_json, ensure_dir, now_iso, sha256_file,
                     sha256_text, write_json, write_jsonl)
from .templates import DB_CONTEXT, TEMPLATES, Template, stable_rng

FAMILY_CONTEXT = {
    "file": "All paths are relative to a sandbox directory. Use only the listed file tools.",
    "database": DB_CONTEXT,
    "python": "Use exactly one statistical tool; do not compute manually.",
    "calendar": "Calendar data is read-only. Dates are YYYY-MM-DD, times HH:MM, "
                "and the workday is 09:00-17:00.",
}


def _type_name(schema: Dict[str, Any]) -> str:
    if not isinstance(schema, dict):
        return "value"
    if schema.get("type") == "array":
        return "%s[]" % _type_name(schema.get("items", {}))
    return schema.get("type", "value")


def _compact_tools(schemas: List[Dict[str, Any]]) -> str:
    lines = []
    for tool in schemas:
        properties = tool["input_schema"].get("properties", {})
        arguments = ", ".join("%s: %s" % (name, _type_name(schema))
                              for name, schema in properties.items())
        lines.append("- %s(%s): %s" % (tool["name"], arguments, tool["description"]))
    return "\n".join(lines)


def build_system_prompt(family: str, schemas: List[Dict[str, Any]]) -> str:
    return (
        "You are a deterministic tool-using assistant.\n"
        "Tools:\n" + _compact_tools(schemas) + "\n\n"
        + FAMILY_CONTEXT[family] + "\n\n"
        "Output format:\n"
        "1. First assistant turn: exactly one JSON object "
        "{\"tool\": <tool_name>, \"arguments\": <object>}.\n"
        "2. After the user message starting with TOOL RESULT, exactly one JSON object "
        "{\"answer\": <value>}.\n"
        "Do not output markdown, code fences, or any other text.\n"
    )


def _schemas(family: str, db_path: str, calendar_path: str) -> List[Dict[str, Any]]:
    if family == "file":
        with tempfile.TemporaryDirectory() as tmp:
            return build_file_registry(FileSandbox(tmp)).schemas()
    if family == "database":
        return build_db_registry(db_path).schemas()
    if family == "python":
        return build_stats_registry().schemas()
    if family == "calendar":
        return build_calendar_registry(calendar_path).schemas()
    raise ValueError("unknown family: %s" % family)


def _observation(family: str, tool: str, arguments: Dict[str, Any],
                 environment: Dict[str, Any], db_path: str,
                 calendar_path: str) -> str:
    if family == "file":
        with tempfile.TemporaryDirectory() as tmp:
            sandbox = materialize_sandbox(environment.get("files", {}), tmp)
            registry = build_file_registry(sandbox)
            return registry.observation(tool, arguments)
    if family == "database":
        return build_db_registry(db_path).observation(tool, arguments)
    if family == "python":
        return build_stats_registry().observation(tool, arguments)
    if family == "calendar":
        return build_calendar_registry(calendar_path).observation(tool, arguments)
    raise ValueError("unknown family: %s" % family)


def _split_counts(config: Dict[str, Any]) -> Dict[str, int]:
    return {"train": int(config["data"]["train_per_family"]),
            "val": int(config["data"]["val_per_family"]),
            "test": int(config["data"]["test_per_family"])}


def _allocate(templates: List[Template], total: int) -> List[int]:
    base, extra = divmod(total, len(templates))
    return [base + (1 if index < extra else 0) for index in range(len(templates))]


def generate_family(family: str, config: Dict[str, Any], db_path: str,
                    calendar_path: str) -> Dict[str, Any]:
    templates = TEMPLATES[family]
    by_split = defaultdict(list)
    for template in templates:
        by_split[template.split].append(template)
    schemas = _schemas(family, db_path, calendar_path)
    system = build_system_prompt(family, schemas)
    totals = _split_counts(config)
    family_dir = Path(config["data_root"]) / family
    ensure_dir(family_dir)
    manifest = {"templates": {}, "counts": {}, "files": {}, "unique_signatures": {}}
    split_rows = {}
    for split, total in totals.items():
        split_templates = by_split.get(split, [])
        if not split_templates:
            raise ValueError("No %s templates for family %s" % (split, family))
        counts = _allocate(split_templates, total)
        rows = []
        for template, count in zip(split_templates, counts):
            for index in range(count):
                rng = stable_rng(int(config["split_seed"]), family,
                                 template.template_id, split, index)
                entity = template.build(rng, index, split)
                observation = _observation(family, entity["tool"],
                                           entity["arguments"],
                                           entity.get("environment", {}),
                                           db_path, calendar_path)
                result = json.loads(observation)
                if not result.get("ok"):
                    raise RuntimeError("Tool failed for %s/%s/%d: %s"
                                       % (family, template.template_id, index,
                                          observation))
                answer = entity["answer"](result["result"])
                tool_call = {"tool": entity["tool"],
                             "arguments": entity["arguments"]}
                tool_text = json.dumps(tool_call, ensure_ascii=False)
                final_text = json.dumps({"answer": answer}, ensure_ascii=False)
                messages = [
                    {"role": "system", "content": system},
                    {"role": "user", "content": entity["prompt"]},
                    {"role": "assistant", "content": tool_text},
                    {"role": "user", "content": "TOOL RESULT:\n" + observation},
                    {"role": "assistant", "content": final_text},
                ]
                episode = {
                    "episode_id": "%s-%s-%s-%03d" % (family, split,
                                                     template.template_id, index),
                    "tool_family": family,
                    "skill_labels": template.skills,
                    "prompt": entity["prompt"],
                    "expected_tool": entity["tool"],
                    "expected_arguments": entity["arguments"],
                    "expected_observation": observation,
                    "expected_final_answer": answer,
                    "split": split,
                    "template_id": template.template_id,
                    "system": system,
                    "environment": entity.get("environment", {}),
                    "messages": messages,
                    "data_signature": sha256_text(canonical_json({
                        "template": template.template_id,
                        "arguments": entity["arguments"],
                        "prompt": entity["prompt"],
                    })),
                }
                rows.append(episode)
        split_rows[split] = rows
        path = family_dir / ("%s.jsonl" % split)
        write_jsonl(path, rows)
        manifest["templates"][split] = [template.template_id
                                        for template in split_templates]
        manifest["counts"][split] = len(rows)
        manifest["files"][split] = {"path": str(path), "sha256": sha256_file(path)}
        manifest["unique_signatures"][split] = len(
            set(row["data_signature"] for row in rows))
    # Leakage guard: no exact prompt may appear in two splits.
    prompts = {}
    template_splits = {}
    for split, rows in split_rows.items():
        for row in rows:
            key = canonical_json({"prompt": row["prompt"],
                                  "tool": row["expected_tool"],
                                  "arguments": row["expected_arguments"]})
            if key in prompts and prompts[key] != split:
                raise RuntimeError("Duplicate task across splits: %s and %s"
                                   % (prompts[key], split))
            prompts[key] = split
            template = row["template_id"]
            if template in template_splits and template_splits[template] != split:
                raise RuntimeError("Template appears in two splits: %s" % template)
            template_splits[template] = split
    train_skills = set(skill for row in split_rows["train"]
                       for skill in row["skill_labels"])
    test_skills = set(skill for row in split_rows["test"]
                      for skill in row["skill_labels"])
    missing = sorted(test_skills - train_skills)
    if missing:
        raise RuntimeError("Test skills never trained for %s: %s" % (family, missing))
    return manifest


def generate_all(config: Dict[str, Any], verify: bool = True) -> Dict[str, Any]:
    data_root = Path(config["data_root"])
    ensure_dir(data_root)
    fixture_dir = data_root / "fixtures"
    ensure_dir(fixture_dir)
    db_path = fixture_dir / "toolbench.db"
    calendar_path = fixture_dir / "calendar.json"
    create_fixture(str(db_path), force=True)
    create_calendar_fixture(str(calendar_path), force=True)
    manifest = {
        "created": now_iso(),
        "split_seed": config["split_seed"],
        "model_name_or_path": config["model_name_or_path"],
        "families": {},
        "db_fixture": {"path": str(db_path), "sha256": sha256_file(db_path)},
        "calendar_fixture": {"path": str(calendar_path),
                             "sha256": sha256_file(calendar_path)},
    }
    for family in config["data"]["families"]:
        manifest["families"][family] = generate_family(
            family, config, str(db_path), str(calendar_path))
    write_json(data_root / "manifest.json", manifest)
    if verify:
        verify_all(config)
    return manifest


def verify_all(config: Dict[str, Any]) -> Dict[str, Any]:
    data_root = Path(config["data_root"])
    db_path = data_root / "fixtures" / "toolbench.db"
    calendar_path = data_root / "fixtures" / "calendar.json"
    if not db_path.exists():
        raise FileNotFoundError("Missing fixture: %s" % db_path)
    if not calendar_path.exists():
        raise FileNotFoundError("Missing fixture: %s" % calendar_path)
    report = {}
    for family in config["data"]["families"]:
        report[family] = {}
        totals = _split_counts(config)
        seen_ids = set()
        for split, expected_count in totals.items():
            path = data_root / family / ("%s.jsonl" % split)
            rows = []
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        rows.append(json.loads(line))
            if len(rows) != expected_count:
                raise RuntimeError("%s/%s expected %d rows, got %d"
                                   % (family, split, expected_count, len(rows)))
            for row in rows:
                if row["episode_id"] in seen_ids:
                    raise RuntimeError("Duplicate episode id: %s" % row["episode_id"])
                seen_ids.add(row["episode_id"])
                observation = _observation(family, row["expected_tool"],
                                           row["expected_arguments"],
                                           row.get("environment", {}),
                                           str(db_path), str(calendar_path))
                if observation != row["expected_observation"]:
                    raise RuntimeError("Observation mismatch: %s" % row["episode_id"])
                if len(row["messages"]) != 5:
                    raise RuntimeError("Bad message count: %s" % row["episode_id"])
                roles = [message["role"] for message in row["messages"]]
                if roles != ["system", "user", "assistant", "user", "assistant"]:
                    raise RuntimeError("Bad role sequence: %s" % row["episode_id"])
            report[family][split] = {"count": len(rows), "path": str(path)}
    write_json(data_root / "verification.json", {"ok": True, "report": report})
    return report
