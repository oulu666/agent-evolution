"""Round-2 A-scenario: none / uniform / targeted / adaptive replay."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Dict, List, Optional, Tuple

from .replay_study import config_for
from .replay_train import train_replay_stage
from .sft.evaluate import evaluate_family, free_model, load_eval_model
from .utils import ensure_dir, read_json, read_jsonl, write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data_round2"
OUT = ROOT / "runs_round2"
SEEDS = [20261108, 20261109, 20261110]
MODES = ("none", "uniform", "targeted", "adaptive")
OLD = ["file", "database", "python"]
FAMILIES = OLD + ["calendar"]
DB_PATH = ROOT / "data_phase2" / "fixtures" / "toolbench.db"
CALENDAR_PATH = ROOT / "data_replay_study" / "fixtures" / "calendar.json"


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


def manifest() -> Dict[str, Any]:
    return read_json(DATA / "manifest.json")


def branch_dir(seed: int, mode: str) -> Path:
    return OUT / "branches" / f"A_seed{seed}_{mode}"


def train_all(seeds: List[int], modes: List[str]) -> None:
    target_ids = manifest()["target_ids"]
    for seed in seeds:
        config = config_for("A", seed, batch_size=32)
        stage = dict(config["stages"][4], index=4)
        old_train = {family: str(DATA / "pool" / (family + ".jsonl"))
                     for family in OLD}
        probes = {family: str(DATA / "monitor" / (family + ".jsonl"))
                  for family in OLD}
        prefix = OUT / "prefixes" / f"A_seed{seed}"
        previous = str(ROOT / "runs_phase2" / f"A_seed{seed}" /
                       "checkpoints" / "stage_03_python")
        for mode in MODES:
            if mode not in modes:
                continue
            run = branch_dir(seed, mode)
            checkpoint = run / "checkpoint"
            if (checkpoint / "train_summary.json").exists():
                print("skip", run.name, flush=True)
                continue
            if run.exists():
                raise FileExistsError("Refusing to overwrite partial branch: %s" % run)
            print("train", run.name, flush=True)
            train_replay_stage(
                config=config, stage=stage,
                train_path=str(ROOT / "data_phase2" / "calendar" / "train.jsonl"),
                old_train_paths=old_train, probe_paths=probes,
                previous_adapter=previous, output_dir=str(checkpoint),
                db_path=str(DB_PATH), calendar_path=str(CALENDAR_PATH),
                mode=mode, replay_ratio=0.1, uniform_floor=0.2,
                prefix_dir=str(prefix), target_ids=target_ids,
                target_fraction=0.5,
                target_family_weights=({family: 1.0 / len(OLD) for family in OLD}
                                       if mode == "targeted" else None))


def suites() -> List[Tuple[str, Dict[str, Any]]]:
    return [
        ("historical", {"root": ROOT / "data_phase2", "split": "test",
                        "families": FAMILIES, "fixtures": ROOT / "data_phase2" }),
        ("natural_final", {"root": DATA / "final", "split": "",
                           "families": OLD, "fixtures": ROOT / "data_replay_study"}),
    ]


def evaluate_state(seed: int, mode: str, adapter: Path, stage_index: int) -> None:
    config = config_for("A", seed, batch_size=32)
    stage = {"name": f"A_seed{seed}_{mode}_eval", "index": stage_index,
             "adapter": str(adapter)}
    model, tokenizer = load_eval_model(config, str(adapter))
    try:
        for suite_name, spec in suites():
            for family in spec["families"]:
                if suite_name == "historical":
                    path = spec["root"] / family / "test.jsonl"
                else:
                    path = spec["root"] / (family + ".jsonl")
                episodes = read_jsonl(path)
                out = OUT / "evaluation" / f"A_seed{seed}_{mode}" / suite_name / family
                if (out / "stage_report.json").exists():
                    continue
                fixtures = spec["fixtures"] / "fixtures"
                evaluate_family(
                    model, tokenizer, episodes, config, stage, out,
                    str(fixtures / "toolbench.db"),
                    str(fixtures / "calendar.json"))
    finally:
        free_model(model)


def evaluate_all(seeds: List[int], modes: List[str]) -> None:
    for seed in seeds:
        start_adapter = ROOT / "runs_phase2" / f"A_seed{seed}" / "checkpoints" / "stage_03_python"
        evaluate_state(seed, "start", start_adapter, 3)
        for mode in modes:
            checkpoint = branch_dir(seed, mode) / "checkpoint"
            if (checkpoint / "train_summary.json").exists():
                evaluate_state(seed, mode, checkpoint, 4)


def stage_report(seed: int, mode: str, suite: str, family: str) -> Optional[Dict[str, Any]]:
    path = OUT / "evaluation" / f"A_seed{seed}_{mode}" / suite / family / "stage_report.json"
    return read_json(path) if path.exists() else None


def aggregate(seeds: List[int], modes: List[str]) -> Dict[str, Any]:
    rows = []
    for seed in seeds:
        for mode in ("start",) + tuple(modes):
            for suite in ("historical", "natural_final"):
                old_values = [stage_report(seed, mode, suite, family) for family in OLD]
                old_values = [item["metrics"]["joint_success_rate"] for item in old_values if item]
                old_answer = [item["metrics"]["final_task_success_rate"]
                              for item in (stage_report(seed, mode, suite, family)
                                           for family in OLD) if item]
                new = stage_report(seed, mode, suite, "calendar") if suite == "historical" else None
                if old_values:
                    rows.append({
                        "seed": seed, "mode": mode, "suite": suite,
                        "old_joint": mean(old_values),
                        "old_answer": mean(old_answer) if old_answer else None,
                        "new_joint": new["metrics"]["joint_success_rate"] if new else None,
                        "new_answer": new["metrics"]["final_task_success_rate"] if new else None,
                    })
    aggregates = {}
    for suite in ("historical", "natural_final"):
        aggregates[suite] = []
        for mode in ("start",) + tuple(modes):
            part = [row for row in rows
                    if row["mode"] == mode and row["suite"] == suite]
            if not part:
                continue
            entry = {"mode": mode, "n_seeds": len(part)}
            for key in ("old_joint", "old_answer", "new_joint", "new_answer"):
                values = [row[key] for row in part if row[key] is not None]
                value, spread = mean_std(values)
                entry[key] = {"mean": value, "std": spread}
            aggregates[suite].append(entry)
    comparisons = []
    for seed in seeds:
        by_mode = {row["mode"]: row for row in rows
                   if row["seed"] == seed and row["suite"] == "historical"}
        natural = {row["mode"]: row for row in rows
                   if row["seed"] == seed and row["suite"] == "natural_final"}
        if all(mode in by_mode for mode in ("none", "uniform", "targeted", "adaptive")):
            comparisons.append({
                "seed": seed,
                "uniform_minus_none_old_joint": by_mode["uniform"]["old_joint"] - by_mode["none"]["old_joint"],
                "targeted_minus_uniform_old_joint": by_mode["targeted"]["old_joint"] - by_mode["uniform"]["old_joint"],
                "adaptive_minus_uniform_old_joint": by_mode["adaptive"]["old_joint"] - by_mode["uniform"]["old_joint"],
                "targeted_minus_none_old_joint": by_mode["targeted"]["old_joint"] - by_mode["none"]["old_joint"],
                "adaptive_minus_none_old_joint": by_mode["adaptive"]["old_joint"] - by_mode["none"]["old_joint"],
                "targeted_minus_uniform_natural": natural["targeted"]["old_joint"] - natural["uniform"]["old_joint"],
                "adaptive_minus_uniform_natural": natural["adaptive"]["old_joint"] - natural["uniform"]["old_joint"],
            })
    costs = []
    for seed in seeds:
        for mode in modes:
            path = branch_dir(seed, mode) / "checkpoint" / "train_summary.json"
            if path.exists():
                summary = read_json(path)
                costs.append({"seed": seed, "mode": mode,
                              "new_input_tokens": summary["new_input_tokens"],
                              "replay_input_tokens": summary["replay_input_tokens"],
                              "replay_supervised_tokens": summary["replay_supervised_tokens"],
                              "target_fraction": summary.get("target_fraction"),
                              "adaptive_triggered": summary.get("adaptive_triggered"),
                              "target_family_weights": summary.get("target_family_weights"),
                              "target_samples_by_family": summary.get("target_samples_by_family"),
                              "duration_seconds": summary["duration_seconds"],
                              "actual_elapsed_seconds": summary.get("actual_elapsed_seconds")})
    return {"rows": rows, "aggregates": aggregates, "comparisons": comparisons, "costs": costs}


def write_report(seeds: List[int], modes: List[str]) -> Path:
    result = aggregate(seeds, modes)
    lines = ["# Round 2 A-scenario: replay content comparison", "",
             "Four arms, order A stage 3 -> 4 (Calendar new; File/Database/Python old). "
             "Shared prefix, 10% replay budget, targeted/adaptive half uniform + half targeted. "
             "Historical test and independent natural final are separate suites.", ""]
    table_rows = []
    for agg in result["aggregates"]["historical"]:
        table_rows.append([
            agg["mode"], agg["n_seeds"],
            mm(agg["old_joint"]["mean"], agg["old_joint"]["std"]),
            mm(agg["old_answer"]["mean"], agg["old_answer"]["std"]),
            mm(agg["new_joint"]["mean"], agg["new_joint"]["std"]),
        ])
    lines += ["## Historical test (old families macro / Calendar)", "",
              table(["mode", "seeds", "old joint", "old answer", "new joint"], table_rows), ""]
    natural = []
    for agg in result["aggregates"]["natural_final"]:
        natural.append([
            agg["mode"], agg["n_seeds"],
            mm(agg["old_joint"]["mean"], agg["old_joint"]["std"]),
            mm(agg["old_answer"]["mean"], agg["old_answer"]["std"]),
        ])
    lines += ["## Independent natural final (old families macro)", "",
              table(["mode", "seeds", "joint", "answer"], natural), ""]
    comparison_rows = []
    for item in result["comparisons"]:
        comparison_rows.append([
            item["seed"],
            "%+.4f" % item["uniform_minus_none_old_joint"],
            "%+.4f" % item["targeted_minus_uniform_old_joint"],
            "%+.4f" % item["adaptive_minus_uniform_old_joint"],
            "%+.4f" % item["targeted_minus_uniform_natural"],
            "%+.4f" % item["adaptive_minus_uniform_natural"],
        ])
    lines += ["## Paired differences", "",
              table(["seed", "uniform-none hist", "targeted-uniform hist",
                     "adaptive-uniform hist", "targeted-uniform natural",
                     "adaptive-uniform natural"], comparison_rows), ""]
    cost_rows = []
    for item in result["costs"]:
        cost_rows.append([
            item["seed"], item["mode"], item["replay_input_tokens"],
            item["target_fraction"], item["adaptive_triggered"],
            item["target_samples_by_family"], "%.1f" % item["actual_elapsed_seconds"]
            if item["actual_elapsed_seconds"] is not None else "-",
        ])
    lines += ["## Replay plan / cost", "",
              table(["seed", "mode", "replay input", "target fraction",
                     "adaptive triggered", "target samples", "actual branch s"],
                    cost_rows), ""]
    lines += ["## Reading", "",
              "The historical test is the direct old-tool outcome. The natural final "
              "is independent and tests whether the targeted content transfers to "
              "unseen natural wording. The key comparison is targeted vs uniform; "
              "adaptive vs uniform is interpretable only when adaptive_triggered is true.",
              ""]
    report = OUT / "report.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    write_json(OUT / "results.json", result)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", nargs="+", type=int, default=SEEDS)
    parser.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    ensure_dir(OUT)
    if not args.report_only:
        train_all(args.seeds, args.modes)
        evaluate_all(args.seeds, args.modes)
    print("report:", write_report(args.seeds, args.modes), flush=True)


if __name__ == "__main__":
    main()
