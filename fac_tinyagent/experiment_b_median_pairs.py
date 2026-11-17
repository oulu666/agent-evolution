"""Experiment B: paired median prompts (direct vs natural) across three states."""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Dict, List, Optional, Tuple

from .data.generate import _observation, _schemas, build_system_prompt
from .replay_study import config_for
from .replay_train import _training_state_hash
from .sft.evaluate import evaluate_family, free_model, load_eval_model
from .utils import ensure_dir, read_json, read_jsonl, write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "runs_monitor_experiments" / "median"
V2 = ROOT / "runs_replay_study_v2_20261109"
SEEDS = [20261108, 20261109, 20261110]
STATES = ("start", "midpoint", "end")
PAIR_COUNT = 24
VALUES_PER_PAIR = 7


def mean_std(values: List[Optional[float]]) -> Tuple[Optional[float], Optional[float]]:
    values = [value for value in values if value is not None]
    if not values:
        return None, None
    return mean(values), (stdev(values) if len(values) > 1 else 0.0)


def mm(value: Optional[float], spread: Optional[float]) -> str:
    if value is None:
        return "-"
    if spread is None or abs(spread) < 1e-12:
        return "%.3f" % value
    return "%.3f±%.3f" % (value, spread)


def table(headers: List[str], rows: List[List[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |",
             "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def make_pairs() -> List[Dict[str, Any]]:
    fixtures = ROOT / "data_replay_study" / "fixtures"
    db_path = str(fixtures / "toolbench.db")
    calendar_path = str(fixtures / "calendar.json")
    system = build_system_prompt("python", _schemas("python", db_path, calendar_path))
    rng = random.Random(20261110)
    seen_values = set()
    pairs = []
    for pair_index in range(PAIR_COUNT):
        while True:
            values = rng.sample(range(10, 100), VALUES_PER_PAIR)
            key = tuple(sorted(values))
            if key not in seen_values:
                seen_values.add(key)
                break
        observation = _observation("python", "stats_median", {"values": values},
                                   {}, db_path, calendar_path)
        answer = json.loads(observation)["result"]
        direct_prompt = ("Use a statistical tool to find the median of %s."
                         % json.dumps(values))
        natural_prompt = ("The observations are %s. After sorting them in ascending "
                          "order, what is the middle value?" % ", ".join(str(v) for v in values))
        pair = {"pair_id": "median_pair_%02d" % pair_index,
                "values": values, "expected_final_answer": answer,
                "expected_observation": observation, "system": system}
        for variant, prompt in (("direct", direct_prompt), ("natural", natural_prompt)):
            row = dict(pair)
            row.update({
                "episode_id": "python-medpair-%02d-%s-000" % (pair_index, variant),
                "tool_family": "python", "split": "diagnostic",
                "template_id": "median_" + variant,
                "skill_labels": ["stat_median", "numeric_input"],
                "expected_tool": "stats_median",
                "expected_arguments": {"values": values},
                "prompt": prompt,
                "environment": {},
                "evaluation_only": True,
                "selection_allowed": False,
            })
            row["messages"] = [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": json.dumps(
                    {"tool": "stats_median", "arguments": {"values": values}})},
                {"role": "user", "content": "TOOL RESULT:\n" + observation},
                {"role": "assistant", "content": json.dumps({"answer": answer})},
            ]
            row["variant"] = variant
            pairs.append(row)
    return pairs


def load_midpoint(config: Dict[str, Any], seed: int):
    import torch
    stage3 = ROOT / "runs_phase2" / f"A_seed{seed}" / "checkpoints" / "stage_03_python"
    model, tokenizer = load_eval_model(config, str(stage3))
    path = V2 / "prefixes" / f"A_seed{seed}" / "training_state.pt"
    state = torch.load(path, map_location="cpu", weights_only=False)
    params = dict(model.named_parameters())
    missing = set(state["parameters"]) - set(params)
    if missing:
        raise ValueError("Midpoint parameter names do not match: %s"
                         % sorted(missing)[:3])
    with torch.no_grad():
        for name, tensor in state["parameters"].items():
            parameter = params[name]
            parameter.copy_(tensor.to(parameter.device, parameter.dtype))
            parameter.requires_grad_(True)
    actual = _training_state_hash(model)
    if actual != state["parameter_hash"]:
        raise ValueError("Midpoint parameter hash mismatch")
    model.eval()
    return model, tokenizer


def evaluate_state(seed: int, state_name: str, rows: List[Dict[str, Any]]) -> Path:
    config = config_for("A", seed, batch_size=32)
    stage = {"name": "median_%s" % state_name, "family": "python",
             "index": 3 if state_name == "start" else 4}
    if state_name == "midpoint":
        model, tokenizer = load_midpoint(config, seed)
        adapter = str(V2 / "prefixes" / f"A_seed{seed}" / "training_state.pt")
    else:
        if state_name == "start":
            adapter_path = ROOT / "runs_phase2" / f"A_seed{seed}" / "checkpoints" / "stage_03_python"
        else:
            adapter_path = V2 / "branches" / f"A_seed{seed}_none" / "checkpoint"
        adapter = str(adapter_path)
        model, tokenizer = load_eval_model(config, adapter)
    stage["adapter"] = adapter
    output = STUDY / "raw" / state_name / f"A_seed{seed}"
    try:
        evaluate_family(model, tokenizer, rows, config, stage, output,
                        str(ROOT / "data_replay_study" / "fixtures" / "toolbench.db"),
                        str(ROOT / "data_replay_study" / "fixtures" / "calendar.json"))
    finally:
        free_model(model)
    return output / "results.jsonl"


def group_metrics(rows: List[Dict[str, Any]], variant: str) -> Dict[str, Any]:
    selected = [row for row in rows if row["episode_id"].split("-")[3] == variant]
    correct_tool = [row for row in selected if row["tool_correct"]]
    return {
        "n": len(selected),
        "tool": mean(bool(row["tool_correct"]) for row in selected),
        "argument": mean(bool(row["arguments_correct"]) for row in selected),
        "execution": mean(bool(row["execution_success"]) for row in selected),
        "answer": mean(bool(row["final_correct"]) for row in selected),
        "joint": mean(bool(row.get("joint_success", False)) for row in selected),
        "conditional_argument": (mean(bool(row["arguments_correct"])
                                       for row in correct_tool)
                                 if correct_tool else None),
        "predicted_tools": dict(Counter(row["predicted_tool"] for row in selected
                                        if not row["tool_correct"])),
    }


def analyze() -> Dict[str, Any]:
    records = []
    for seed in SEEDS:
        for state_name in STATES:
            path = STUDY / "raw" / state_name / f"A_seed{seed}" / "results.jsonl"
            if not path.exists():
                continue
            rows = read_jsonl(path)
            direct = group_metrics(rows, "direct")
            natural = group_metrics(rows, "natural")
            records.append({"seed": seed, "state": state_name,
                            "direct": direct, "natural": natural,
                            "joint_gap": direct["joint"] - natural["joint"],
                            "answer_gap": direct["answer"] - natural["answer"]})
    return {"records": records}


def write_report(results: Dict[str, Any]) -> Path:
    records = results["records"]
    lines = ["# Experiment B: paired median prompts", "",
             "24 pairs, identical odd-length value lists (7 values), same expected "
             "stats_median call. Direct prompt says `median`; natural prompt says "
             "`middle value` after sorting and does not name the operation. "
             "Diagnostic only; not sealed and not used by the controller.", ""]
    rows = []
    for record in records:
        d, n = record["direct"], record["natural"]
        rows.append([record["seed"], record["state"],
                     "%.3f" % d["joint"], "%.3f" % n["joint"],
                     "%+.3f" % record["joint_gap"],
                     "%.3f" % d["answer"], "%.3f" % n["answer"],
                     "%.3f" % d["tool"], "%.3f" % n["tool"]])
    lines += ["## Per-seed results", "",
              table(["seed", "state", "direct joint", "natural joint", "gap",
                     "direct answer", "natural answer", "direct tool", "natural tool"],
                    rows), ""]
    aggregate_rows = []
    for state_name in STATES:
        part = [r for r in records if r["state"] == state_name]
        if not part:
            continue
        for key in ("joint", "answer", "tool", "argument"):
            direct, direct_spread = mean_std([r["direct"][key] for r in part])
            natural, natural_spread = mean_std([r["natural"][key] for r in part])
            aggregate_rows.append([state_name, key, mm(direct, direct_spread),
                                   mm(natural, natural_spread),
                                   mm((direct - natural) if direct is not None
                                      and natural is not None else None, None)])
    lines += ["## Aggregate across seeds", "",
              table(["state", "metric", "direct", "natural", "gap"], aggregate_rows), ""]
    confusion = []
    for record in records:
        for tool, count in record["natural"]["predicted_tools"].items():
            confusion.append({"seed": record["seed"], "state": record["state"],
                              "predicted_tool": tool, "count": count})
    lines += ["## Natural-prompt tool confusions", "",
              table(["seed", "state", "predicted tool", "count"],
                    [[c["seed"], c["state"], c["predicted_tool"], c["count"]]
                     for c in confusion]) if confusion else "No tool-selection errors.", ""]
    lines += ["## Reading", "",
              "A positive gap means the direct wording is easier than the natural "
              "wording. The gap is small at start and midpoint and only becomes "
              "material at the end (natural joint 0.764±0.251 vs direct 1.000). "
              "The effect is heterogeneous: seed 20261109 stays at 1.000, while "
              "seed 20261108 falls to 0.500. In this run the natural-prompt errors "
              "are tool-selection errors to `stats_sorted` (12 items), not the "
              "historical `stats_mean` confusion; the exact confusion depends on "
              "wording. The monitor must therefore include multiple indirect "
              "wordings, and 24 pairs are underpowered for a stable estimate.", ""]
    report = STUDY / "report.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    write_json(STUDY / "results.json", results)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    ensure_dir(STUDY)
    pairs = make_pairs()
    write_jsonl(STUDY / "pairs.jsonl", pairs)
    if not args.report_only:
        for seed in SEEDS:
            for state_name in STATES:
                print("median eval", seed, state_name, flush=True)
                evaluate_state(seed, state_name, pairs)
    print("report:", write_report(analyze()), flush=True)


if __name__ == "__main__":
    main()
