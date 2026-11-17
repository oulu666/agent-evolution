"""Full 30-item final-adapter evaluation for the Phase 2 sweep."""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Dict, List, Optional, Tuple

from .sft.evaluate import evaluate_family, free_model, load_eval_model
from .utils import ensure_dir, read_json, read_jsonl, write_json

METRIC = "final_task_success_rate"


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


def completed_runs(root: Path) -> List[Path]:
    return sorted(
        directory for directory in Path(root).iterdir()
        if directory.is_dir()
        and (directory / "config.json").exists()
        and (directory / "summary.json").exists()
    )


def final_stage(config: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    stages = [stage for stage in config["stages"] if stage.get("family")]
    if not stages:
        raise ValueError("config has no learned stages")
    final = stages[-1]
    return final, config["stages"].index(final)


def evaluate_run(run_dir: Path, output_root: Path, force: bool = False,
                 limit: Optional[int] = None) -> Dict[str, Any]:
    config = read_json(run_dir / "config.json")
    run_name = config.get("run_name") or run_dir.name
    final, final_index = final_stage(config)
    adapter = run_dir / "checkpoints" / final["name"]
    if not (adapter / "adapter_model.safetensors").exists():
        raise FileNotFoundError("missing final adapter: %s" % adapter)
    run_out = ensure_dir(output_root / run_name)
    summary_path = run_out / "summary.json"
    if summary_path.exists() and not force:
        print("skip run", run_name, flush=True)
        return read_json(summary_path)
    data_root = Path(config["data_root"])
    db_path = str(data_root / "fixtures" / "toolbench.db")
    calendar_path = str(data_root / "fixtures" / "calendar.json")
    reports = []
    model = None
    tokenizer = None
    try:
        model, tokenizer = load_eval_model(config, str(adapter))
        for family in config["data"]["families"]:
            family_out = run_out / family
            existing = family_out / "stage_report.json"
            if existing.exists() and not force:
                reports.append(read_json(existing))
                print("skip family", run_name, family, flush=True)
                continue
            episodes = read_jsonl(data_root / family / "test.jsonl")
            if limit:
                episodes = episodes[:limit]
            stage = {
                "name": "%s_full" % final["name"],
                "family": final["family"],
                "index": final_index,
                "adapter": str(adapter),
            }
            reports.append(evaluate_family(
                model, tokenizer, episodes, config, stage, family_out,
                db_path, calendar_path))
    finally:
        if model is not None:
            free_model(model)
    write_json(summary_path, {
        "run_name": run_name,
        "run_dir": str(run_dir),
        "final_stage": final,
        "final_index": final_index,
        "adapter": str(adapter),
        "test_per_family": limit if limit else "all",
        "reports": reports,
    })
    return read_json(summary_path)


def report_rows(summary: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {report["family"]: report for report in summary["reports"]}


def load_full(root: Path) -> List[Dict[str, Any]]:
    runs = []
    for directory in sorted(Path(root).iterdir()):
        path = directory / "summary.json"
        if not path.exists():
            continue
        summary = read_json(path)
        name = summary.get("run_name") or directory.name
        match = re.match(r"([A-Za-z0-9]+)_seed(\d+)", name)
        runs.append({
            "name": name,
            "order": match.group(1) if match else name,
            "seed": int(match.group(2)) if match else None,
            "summary": summary,
            "rows": report_rows(summary),
        })
    return runs


def subset_values(run_name: str, runs_root: Path) -> Dict[str, Optional[float]]:
    path = runs_root / run_name / "summary.json"
    if not path.exists():
        return {}
    summary = read_json(path)
    pivot = summary.get("capability_matrix", {}).get("pivot", [])
    if not pivot:
        return {}
    final = max(row["stage_index"] for row in pivot)
    row = [item for item in pivot if item["stage_index"] == final][0]
    return {family: row.get(family) for family in
            ("file", "database", "python", "calendar")}


def write_report(output_root: Path, runs_root: Path) -> Path:
    runs = load_full(output_root)
    if not runs:
        raise SystemExit("No full-evaluation summaries under %s" % output_root)
    orders = sorted({run["order"] for run in runs})
    seeds = sorted({run["seed"] for run in runs if run["seed"] is not None})
    families = sorted({family for run in runs for family in run["rows"]})
    lines = [
        "# FAC-TinyAgent Phase 2 Full-Test Re-Evaluation",
        "",
        "- Final adapters from the Phase 2 sequential sweep",
        "- Test set: all available test episodes per family (30 in `data_phase2`)",
        "- Runs: %d" % len(runs),
        "- Orders: %s" % ", ".join(orders),
        "- Seeds: %s" % ", ".join(str(seed) for seed in seeds),
        "- No retraining; old checkpoints and subset evaluations are untouched",
        "",
        "## Final capability (full test set)",
        "",
    ]
    order_rows = []
    for order in orders:
        order_runs = [run for run in runs if run["order"] == order]
        row = [order]
        for family in families:
            values = [run["rows"].get(family, {}).get("metrics", {}).get(METRIC)
                      for run in order_runs]
            value, spread = mean_std(values)
            row.append(mm(value, spread))
        means = [mean([run["rows"][family]["metrics"][METRIC]
                       for family in families if family in run["rows"]])
                 for run in order_runs]
        value, spread = mean_std(means)
        row.append(mm(value, spread))
        order_rows.append(row)
    lines.append(table(["order"] + families + ["mean across families"], order_rows))
    lines.append("")
    family_rows = []
    for family in families:
        values = [run["rows"].get(family, {}).get("metrics", {}).get(METRIC)
                  for run in runs]
        value, spread = mean_std(values)
        family_rows.append((family, value, spread, len([
            item for item in values if item is not None])))
    family_rows.sort(key=lambda item: (item[1] is None, -(item[1] or 0.0)))
    lines += ["### Per family", ""]
    lines.append(table(
        ["family", "mean final", "runs"],
        [[family, mm(value, spread), count]
         for family, value, spread, count in family_rows]))
    lines.append("")
    lines += ["### Per run", ""]
    run_rows = []
    for run in sorted(runs, key=lambda item: item["name"]):
        row = [run["name"]]
        for family in families:
            value = run["rows"].get(family, {}).get("metrics", {}).get(METRIC)
            row.append("%.3f" % value if value is not None else "-")
        run_rows.append(row)
    lines.append(table(["run"] + families, run_rows))
    lines.append("")
    lines += ["## Comparison with the 6-item subset", ""]
    comparison = []
    for run in sorted(runs, key=lambda item: item["name"]):
        subset = subset_values(run["name"], runs_root)
        for family in families:
            full = run["rows"].get(family, {}).get("metrics", {}).get(METRIC)
            base = subset.get(family)
            if full is None or base is None:
                continue
            comparison.append({
                "run": run["name"], "order": run["order"],
                "family": family, "subset": base, "full": full,
                "delta": full - base,
            })
    comparison_rows = []
    for order in orders:
        for family in families:
            items = [item for item in comparison
                     if item["order"] == order and item["family"] == family]
            subset_value, subset_spread = mean_std([item["subset"] for item in items])
            full_value, full_spread = mean_std([item["full"] for item in items])
            delta_value, delta_spread = mean_std([item["delta"] for item in items])
            comparison_rows.append([
                order, family, mm(subset_value, subset_spread),
                mm(full_value, full_spread), mm(delta_value, delta_spread),
                len(items)])
    lines.append(table(
        ["order", "family", "6-item subset", "full", "full - subset", "runs"],
        comparison_rows))
    lines.append("")
    deltas = [item["delta"] for item in comparison]
    delta_value, delta_spread = mean_std(deltas)
    lines.append("Across %d run-family cells, the full test changes the score by "
                 "%s on average (full minus subset)."
                 % (len(deltas), mm(delta_value, delta_spread)))
    lines.append("")
    lines += ["## Key findings", ""]
    if order_rows:
        best = max(order_rows, key=lambda row: float(row[-1].split("±")[0])
                   if row[-1] != "-" else -1.0)
        worst = min(order_rows, key=lambda row: float(row[-1].split("±")[0])
                    if row[-1] != "-" else 2.0)
        lines.append("- Best order on the full test set: %s (%s); worst: %s (%s)."
                     % (best[0], best[-1], worst[0], worst[-1]))
    if family_rows:
        lines.append("- Final capability by family: %s."
                     % "; ".join("%s %s" % (family, mm(value, spread))
                                 for family, value, spread, _ in family_rows))
    order_family_full = {}
    for order in orders:
        order_runs = [run for run in runs if run["order"] == order]
        for family in families:
            values = [run["rows"].get(family, {}).get("metrics", {}).get(METRIC)
                      for run in order_runs]
            order_family_full[(order, family)] = mean_std(values)
    cells = [(order, family, value, spread)
             for (order, family), (value, spread) in order_family_full.items()
             if value is not None]
    low = min(cells, key=lambda item: item[2]) if cells else None
    high = max(cells, key=lambda item: item[2]) if cells else None
    if low and high:
        lines.append("- Lowest order-family cell: %s/%s %s; highest: %s/%s %s."
                     % (low[0], low[1], mm(low[2], low[3]),
                        high[0], high[1], mm(high[2], high[3])))
        low_items = [item for item in comparison
                     if item["order"] == low[0] and item["family"] == low[1]]
        subset_value, _ = mean_std([item["subset"] for item in low_items])
        if subset_value == 0.0 and low[2] > 0:
            lines.append(
                "  The 6-item subset reported 0.000 for this cell; the full 30-item "
                "test gives %s. The collapse is real, but the exact zero was a "
                "small-sample artifact." % mm(low[2], low[3]))
    zero_cells = [item for item in comparison if item["full"] == 0.0]
    if zero_cells:
        lines.append("- Cells with a full-test score of zero: %s."
                     % ", ".join("%s/%s" % (item["run"], item["family"])
                                 for item in zero_cells))
    if deltas:
        delta_value, delta_spread = mean_std(deltas)
        largest = max(comparison, key=lambda item: abs(item["delta"]))
        lines.append(
            "- Across %d cells, full minus subset is %s on average; individual "
            "cells shift by up to %.3f. The largest shift is %s/%s %.3f -> %.3f."
            % (len(deltas), mm(delta_value, delta_spread),
               max(abs(item) for item in deltas),
               largest["run"], largest["family"], largest["subset"],
               largest["full"]))
    lines += ["", "## Limitations", "",
              "- Only the final adapter is re-evaluated; intermediate-stage "
              "matrices still use the 6-item subset.",
              "- Three seeds and one model; no formal significance test.",
              "- Full evaluation measures final retention, not the shape of "
              "forgetting during the sequence.",
              "", "## Output", "",
              "- Per-run results: `%s/<run>/<family>/`" % output_root,
              ""]
    report_path = output_root / "report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    write_json(output_root / "report.json", {
        "orders": orders,
        "seeds": seeds,
        "families": families,
        "runs": [run["name"] for run in runs],
        "family_final": [
            {"family": family, "mean": value, "std": spread, "runs": count}
            for family, value, spread, count in family_rows],
        "comparison": comparison,
    })
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-root", default="runs_phase2")
    parser.add_argument("--output-root", default="runs_phase2_full")
    parser.add_argument("--runs", nargs="+", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    runs_root = Path(args.runs_root)
    output_root = ensure_dir(Path(args.output_root))
    run_dirs = completed_runs(runs_root)
    if args.runs:
        wanted = set(args.runs)
        run_dirs = [directory for directory in run_dirs
                    if directory.name in wanted]
    if not run_dirs:
        raise SystemExit("No completed runs selected under %s" % runs_root)
    if not args.report_only:
        for run_dir in run_dirs:
            print("full eval start", run_dir.name, flush=True)
            evaluate_run(run_dir, output_root, force=args.force, limit=args.limit)
            print("full eval done", run_dir.name, flush=True)
    print("report:", write_report(output_root, runs_root), flush=True)


if __name__ == "__main__":
    main()
