"""Diagnose whether the replay monitor sees the known old-tool degradation.

End-probe evaluation is read-only: it loads the no-replay branch checkpoint and
evaluates the probe split. Historical test results are read from the batch32 audit.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from .replay_study import config_for, evaluate_adapter
from .utils import ensure_dir, read_json, read_jsonl, write_json

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "runs_replay_study_v2_20261109"
DATA = ROOT / "data_replay_study"
HISTORICAL = ROOT / "runs_replay_study_20261109" / "historical_batch32"
SEEDS = [20261108, 20261109, 20261110]
OLD = ["file", "database", "python"]
FAMILIES = ["file", "database", "python", "calendar"]


def joint(row: Dict[str, Any]) -> bool:
    return all(row.get(key, False) for key in (
        "tool_correct", "arguments_correct", "execution_success", "final_correct"))


def answer(row: Dict[str, Any]) -> bool:
    return bool(row.get("final_correct", False))


def score(path: Path) -> Dict[str, float]:
    rows = read_jsonl(path)
    return {"n": len(rows), "joint": mean(joint(row) for row in rows),
            "answer": mean(answer(row) for row in rows)}


def probe_path(seed: int, position: str, family: str) -> Path:
    if position == "end":
        return STUDY / "probes_end" / f"A_seed{seed}" / family / "results.jsonl"
    return (STUDY / "branches" / f"A_seed{seed}_none" / "checkpoint" /
            "probes" / position / family / "results.jsonl")


def run_end_probes(order: str, seeds: List[int]) -> None:
    for seed in seeds:
        config = config_for(order, seed)
        stage = dict(config["stages"][4], index=4)
        adapter = STUDY / "branches" / f"{order}_seed{seed}_none" / "checkpoint"
        output = STUDY / "probes_end" / f"{order}_seed{seed}"
        print("probe end start", seed, flush=True)
        evaluate_adapter(config, stage, adapter, DATA, "probe", output)
        print("probe end done", seed, flush=True)


def historical_drops(order: str) -> List[Dict[str, Any]]:
    stage3 = "stage_03_python" if order == "A" else "stage_03_calendar"
    stage4 = "stage_04_calendar" if order == "A" else "stage_04_python"
    drops = []
    for seed in SEEDS:
        for family in FAMILIES:
            before_path = HISTORICAL / f"{order}_seed{seed}" / stage3 / family / "results.jsonl"
            after_path = HISTORICAL / f"{order}_seed{seed}" / stage4 / family / "results.jsonl"
            if not before_path.exists() or not after_path.exists():
                continue
            before = read_jsonl(before_path)
            after = read_jsonl(after_path)
            by_template_before = defaultdict(list)
            by_template_after = defaultdict(list)
            for row in before:
                by_template_before[row["episode_id"].split("-")[2]].append(joint(row))
            for row in after:
                by_template_after[row["episode_id"].split("-")[2]].append(joint(row))
            for template, values in by_template_before.items():
                if template not in by_template_after:
                    continue
                old = mean(values)
                new = mean(by_template_after[template])
                if old > new:
                    drops.append({
                        "order": order, "seed": seed, "family": family,
                        "template": template, "before": old, "after": new,
                        "n": len(values)})
    return drops


def write_report(order: str) -> Path:
    rows = []
    for seed in SEEDS:
        for family in OLD:
            entry = {"seed": seed, "family": family}
            for position in ("start", "midpoint", "end"):
                path = probe_path(seed, position, family)
                entry[position] = score(path) if path.exists() else None
            rows.append(entry)
    drops = historical_drops(order)
    probe_templates = set()
    for family in OLD:
        for row in read_jsonl(DATA / family / "probe.jsonl"):
            probe_templates.add(row.get("template_id"))
    drop_templates = sorted({item["template"] for item in drops})
    overlap = sorted(set(drop_templates) & probe_templates)
    lines = [
        "# Monitor probe diagnosis", "",
        "Order %s; no-replay branch; probe start/midpoint/end; no training." % order, "",
        "## Probe scores", "",
        "| Seed | Tool | Start joint | Midpoint joint | End joint | Start answer | Midpoint answer | End answer |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for entry in rows:
        cells = []
        for key in ("start", "midpoint", "end"):
            value = entry[key]
            cells.append("-" if value is None else "%.3f" % value["joint"])
        for key in ("start", "midpoint", "end"):
            value = entry[key]
            cells.append("-" if value is None else "%.3f" % value["answer"])
        lines.append("| %s | %s | %s |" % (
            entry["seed"], entry["family"], " | ".join(cells)))
    lines += ["", "## Historical per-template drops", "",
              "| Seed | Tool | Template | Before | After | n |",
              "|---|---|---|---|---|---|"]
    for item in drops:
        lines.append("| %s | %s | %s | %.3f | %.3f | %d |" % (
            item["seed"], item["family"], item["template"],
            item["before"], item["after"], item["n"]))
    lines += ["", "## Coverage check", "",
              "Historical drop templates: %s." % (", ".join(drop_templates) or "none"),
              "Probe template coverage: %s." % (", ".join(sorted(probe_templates)) or "none"),
              "Exact template overlap: %s." % (", ".join(overlap) or "none"),
              "", "The probe uses `study_*` templates and explicit tool wording; the "
              "historical drops occur on different test templates. A zero overlap means "
              "the monitor's null signal is a coverage result, not evidence that old "
              "skills are retained.", ""]
    report = STUDY / "monitor_probe_report.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    write_json(STUDY / "monitor_probe_results.json", {
        "order": order, "rows": rows, "historical_drops": drops,
        "probe_templates": sorted(probe_templates),
        "drop_templates": drop_templates, "overlap": overlap,
    })
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--order", default="A")
    parser.add_argument("--seeds", nargs="+", type=int, default=SEEDS)
    parser.add_argument("--skip-eval", action="store_true")
    args = parser.parse_args()
    ensure_dir(STUDY)
    if not args.skip_eval:
        run_end_probes(args.order, args.seeds)
    print("report:", write_report(args.order), flush=True)


if __name__ == "__main__":
    main()
