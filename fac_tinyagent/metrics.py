"""Accuracy, skill-level metrics and the forgetting matrix."""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .utils import ensure_dir, read_jsonl, write_json

METRIC_KEYS = [
    "tool_selection_accuracy",
    "argument_accuracy",
    "execution_success_rate",
    "final_task_success_rate",
]

# Keep the legacy list stable: old capability/forgetting reports do not contain
# the derived metrics, and conditional accuracy can legitimately be undefined.
DERIVED_METRIC_KEYS = ["joint_success_rate", "conditional_argument_accuracy"]
REPORT_METRIC_KEYS = METRIC_KEYS + DERIVED_METRIC_KEYS


def joint_success(row: Dict[str, Any]) -> bool:
    """Strict end-to-end success, also derivable from archived result rows."""
    return all(bool(row[key]) for key in (
        "tool_correct", "arguments_correct", "execution_success", "final_correct"))


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def answers_equal(expected: Any, predicted: Any) -> bool:
    if _is_number(expected) and _is_number(predicted):
        return math.isclose(float(expected), float(predicted),
                            rel_tol=1e-4, abs_tol=1e-4)
    if isinstance(expected, str) or isinstance(predicted, str):
        return expected == predicted
    if isinstance(expected, list) and isinstance(predicted, list):
        return (len(expected) == len(predicted) and
                all(answers_equal(a, b) for a, b in zip(expected, predicted)))
    if isinstance(expected, dict) and isinstance(predicted, dict):
        return (set(expected) == set(predicted) and
                all(answers_equal(expected[key], predicted[key]) for key in expected))
    return expected == predicted


def observations_equal(expected: str, predicted: str) -> bool:
    try:
        left = json.loads(expected) if isinstance(expected, str) else expected
        right = json.loads(predicted) if isinstance(predicted, str) else predicted
    except (TypeError, ValueError):
        return expected == predicted
    return answers_equal(left, right)


def ratio(values: Iterable[bool]) -> float:
    values = list(values)
    if not values:
        return 0.0
    return round(sum(1 for value in values if value) / len(values), 6)


def summarize_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    correct_tool = [row for row in results if row["tool_correct"]]
    return {
        "n": len(results),
        "tool_selection_accuracy": ratio(row["tool_correct"] for row in results),
        "argument_accuracy": ratio(row["arguments_correct"] for row in results),
        "execution_success_rate": ratio(row["execution_success"] for row in results),
        "final_task_success_rate": ratio(row["final_correct"] for row in results),
        "joint_success_rate": ratio(joint_success(row) for row in results),
        "conditional_argument_accuracy": (
            ratio(row["arguments_correct"] for row in correct_tool)
            if correct_tool else None),
        "conditional_argument_numerator": sum(
            bool(row["arguments_correct"]) for row in correct_tool),
        "conditional_argument_denominator": len(correct_tool),
    }


def summarize_usage(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Sum recorded costs without representing unrecorded legacy costs as zero.

    ``inference_calls`` counts logical requests (two per completed episode),
    while ``generation_batches`` counts actual model.generate invocations.
    Batch generation time is apportioned across its episodes by the evaluator.
    Legacy calls can be inferred from the two saved raw generations; token
    counts and generation time cannot be recovered exactly from decoded text.
    """
    fields = ("inference_calls", "input_tokens", "output_tokens", "total_tokens",
              "generation_seconds")
    values = {field: [] for field in fields}
    inferred_calls = 0
    batches = set()
    batch_coverage = 0
    for row in results:
        for field in fields:
            value = row.get(field)
            if (field == "inference_calls" and value is None
                    and "tool_call_raw" in row and "answer_raw" in row):
                value = 2
                inferred_calls += 1
            if value is not None:
                values[field].append(value)
        usage = row.get("generation_usage", {})
        if all(usage.get(role, {}).get("batch_id") is not None
               for role in ("tool", "answer")):
            batch_coverage += 1
            for role in ("tool", "answer"):
                batches.add((role, usage[role]["batch_id"]))
    coverage = {field: len(items) for field, items in values.items()}
    recorded = {field: (sum(items) if items or not results else None)
                for field, items in values.items()}
    if recorded["generation_seconds"] is not None:
        recorded["generation_seconds"] = round(recorded["generation_seconds"], 6)
    summary = {field: (recorded[field] if coverage[field] == len(results) else None)
               for field in fields}
    summary.update({
        "n": len(results),
        "generation_batches": len(batches) if batch_coverage == len(results) else None,
        "usage_coverage": coverage,
        "recorded_totals": recorded,
        "inferred_inference_call_episodes": inferred_calls,
        "inference_calls_definition": "logical generation requests; two per episode",
        "generation_seconds_definition": "generation wall time; batch time apportioned equally",
    })
    return summary


def summarize_result_file(path: Path) -> Dict[str, Any]:
    """Read archived results and derive metrics without inference or file writes."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    results = read_jsonl(path)
    families = sorted({row["tool_family"] for row in results})
    return {
        "source_results": str(path.resolve()),
        "families": families,
        "metrics": summarize_results(results),
        "skill_metrics": summarize_skills(results),
        "inference_usage": summarize_usage(results),
        "by_family": {
            family: {
                "metrics": summarize_results(
                    [row for row in results if row["tool_family"] == family]),
                "inference_usage": summarize_usage(
                    [row for row in results if row["tool_family"] == family]),
            }
            for family in families
        },
    }


def summarize_skills(results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    by_skill = defaultdict(list)
    for row in results:
        for skill in row.get("skill_labels", []):
            by_skill[skill].append(row)
    return {skill: summarize_results(rows) for skill, rows in sorted(by_skill.items())}


def evaluate_stage_family(results: List[Dict[str, Any]], stage: Dict[str, Any],
                          family: str, output_dir: Path) -> Dict[str, Any]:
    ensure_dir(output_dir)
    metrics = summarize_results(results)
    skills = summarize_skills(results)
    report = {"stage_index": stage["index"], "stage_name": stage["name"],
              "family": family, "metrics": metrics, "skill_metrics": skills,
              "inference_usage": summarize_usage(results)}
    write_json(output_dir / "metrics.json", report)
    with (output_dir / "metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        for key in REPORT_METRIC_KEYS:
            writer.writerow([key, metrics[key]])
    with (output_dir / "skill_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["skill", "n"] + REPORT_METRIC_KEYS)
        for skill, values in skills.items():
            writer.writerow([skill, values["n"]] + [values[key] for key in REPORT_METRIC_KEYS])
    return report


def forgetting_rows(evaluations: List[Dict[str, Any]],
                    learned_stage: Dict[str, int]) -> Tuple[List[Dict[str, Any]],
                                                           List[Dict[str, Any]]]:
    """F(i,t) = max(0, max_{k<t} A(i,k) - A(i,t)), after family i is learned.

    The first post-learning evaluation is the baseline and does not produce a
    forgetting row.  `peak` is the maximum BEFORE the current stage, never the
    updated maximum; `n` is the number of test episodes behind the value.
    """
    by_family = defaultdict(list)
    for evaluation in evaluations:
        by_family[evaluation["family"]].append(evaluation)
    family_rows = []
    skill_rows = []
    for family, items in by_family.items():
        start = learned_stage.get(family)
        if start is None:
            continue
        items = sorted([item for item in items if item["stage_index"] >= start],
                       key=lambda item: item["stage_index"])
        if len(items) < 2:
            continue
        for metric in METRIC_KEYS:
            peak = None
            for item in items:
                value = item["metrics"][metric]
                if peak is None:
                    peak = value
                    continue
                family_rows.append({
                    "family": family, "skill": "", "metric": metric,
                    "stage_index": item["stage_index"],
                    "stage_name": item["stage_name"],
                    "value": value, "peak": peak,
                    "forgetting": round(max(0.0, peak - value), 6),
                    "n": item["metrics"]["n"],
                })
                peak = max(peak, value)
        skills = set()
        for item in items:
            skills.update(item.get("skill_metrics", {}).keys())
        for skill in sorted(skills):
            for metric in METRIC_KEYS:
                peak = None
                for item in items:
                    values = item.get("skill_metrics", {}).get(skill)
                    if not values or metric not in values:
                        continue
                    value = values[metric]
                    if peak is None:
                        peak = value
                        continue
                    skill_rows.append({
                        "family": family, "skill": skill, "metric": metric,
                        "stage_index": item["stage_index"],
                        "stage_name": item["stage_name"],
                        "value": value, "peak": peak,
                        "forgetting": round(max(0.0, peak - value), 6),
                        "n": values.get("n", 0),
                    })
                    peak = max(peak, value)
    return family_rows, skill_rows


def average_forgetting(rows: List[Dict[str, Any]], weighted: bool = False) -> Dict[str, Any]:
    by_stage_metric = defaultdict(list)
    for row in rows:
        by_stage_metric[(row["stage_index"], row["metric"])].append(row)
    result = defaultdict(dict)
    for (stage_index, metric), items in sorted(by_stage_metric.items()):
        if weighted:
            total = sum(item.get("n", 0) for item in items)
            value = (sum(item["forgetting"] * item.get("n", 0) for item in items) / total
                     if total else 0.0)
        else:
            value = mean(item["forgetting"] for item in items)
        result[str(stage_index)][metric] = round(value, 6)
    return dict(result)


def write_forgetting_reports(output_dir: Path, evaluations: List[Dict[str, Any]],
                             learned_stage: Dict[str, int]) -> Dict[str, Any]:
    ensure_dir(output_dir)
    family_rows, skill_rows = forgetting_rows(evaluations, learned_stage)
    rows = family_rows + skill_rows
    fields = ["family", "skill", "metric", "stage_index", "stage_name",
              "value", "peak", "forgetting", "n"]
    with (output_dir / "forgetting.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "family_average": average_forgetting(family_rows),
        "family_average_weighted": average_forgetting(family_rows, weighted=True),
        "skill_average": average_forgetting(skill_rows),
        "skill_average_weighted": average_forgetting(skill_rows, weighted=True),
        "family_rows": family_rows,
        "skill_rows": skill_rows,
    }
    write_json(output_dir / "forgetting.json", report)
    return report


def write_capability_matrix(output_dir: Path,
                            evaluations: List[Dict[str, Any]]) -> Dict[str, Any]:
    ensure_dir(output_dir)
    fields = ["stage_index", "stage_name", "family", "n"] + METRIC_KEYS
    with (output_dir / "capability_matrix.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for evaluation in sorted(evaluations,
                                 key=lambda item: (item["stage_index"], item["family"])):
            writer.writerow({
                "stage_index": evaluation["stage_index"],
                "stage_name": evaluation["stage_name"],
                "family": evaluation["family"],
                "n": evaluation["metrics"]["n"],
                **{key: evaluation["metrics"][key] for key in METRIC_KEYS},
            })
    stages = sorted({(item["stage_index"], item["stage_name"]) for item in evaluations})
    families = sorted({item["family"] for item in evaluations})
    pivot = []
    for stage_index, stage_name in stages:
        row = {"stage_index": stage_index, "stage_name": stage_name}
        for family in families:
            match = [item for item in evaluations
                     if item["stage_index"] == stage_index and item["family"] == family]
            row[family] = match[0]["metrics"]["final_task_success_rate"] if match else None
        pivot.append(row)
    with (output_dir / "capability_matrix_final.csv").open("w", newline="",
                                                           encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["stage_index", "stage_name"] + families)
        writer.writeheader()
        writer.writerows(pivot)
    result = {"families": families, "pivot": pivot}
    write_json(output_dir / "capability_matrix.json", result)
    return result
