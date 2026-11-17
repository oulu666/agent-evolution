"""Aggregate Phase 2 multi-order, multi-seed runs into a report."""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Dict, List, Optional, Tuple

from .utils import ensure_dir, read_json, write_json

METRIC = "final_task_success_rate"
COMPLEXITY = {"file": 1, "python": 2, "calendar": 2, "database": 3}
POSITION_NAMES = {1: "first", 2: "second", 3: "third", 4: "fourth"}


def mean_std(values: List[Optional[float]]) -> Tuple[Optional[float], Optional[float]]:
    values = [value for value in values if value is not None]
    if not values:
        return None, None
    return mean(values), (stdev(values) if len(values) > 1 else 0.0)


def _mm(value: Optional[float], spread: Optional[float]) -> str:
    if value is None:
        return "-"
    if spread is None or abs(spread) < 1e-12:
        return "%.3f" % value
    return "%.3f±%.3f" % (value, spread)


def _table(headers: List[str], rows: List[List[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |",
             "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def load_runs(root: Path) -> List[Dict[str, Any]]:
    runs = []
    for directory in sorted(Path(root).iterdir()):
        if not (directory / "summary.json").exists():
            continue
        summary = read_json(directory / "summary.json")
        run = read_json(directory / "run.json") if (directory / "run.json").exists() else {}
        config = summary.get("config", {})
        name = run.get("run_name") or config.get("run_name") or directory.name
        match = re.match(r"([A-Za-z0-9]+)_seed(\d+)", name)
        order = match.group(1) if match else name
        seed = int(match.group(2)) if match else config.get("seed")
        runs.append({"dir": directory, "name": name, "order": order,
                     "seed": seed, "summary": summary, "config": config})
    return runs


def pivot_value(summary: Dict[str, Any], stage_index: int,
                family: str) -> Optional[float]:
    for row in summary.get("capability_matrix", {}).get("pivot", []):
        if row["stage_index"] == stage_index:
            return row.get(family)
    return None


def final_stage(summary: Dict[str, Any]) -> int:
    rows = summary.get("capability_matrix", {}).get("pivot", [])
    return max([row["stage_index"] for row in rows], default=0)


def final_pivot_row(summary: Dict[str, Any]) -> Dict[str, Any]:
    final = final_stage(summary)
    for row in summary.get("capability_matrix", {}).get("pivot", []):
        if row["stage_index"] == final:
            return row
    return {}


def full_eval_summary(runs_root: Path) -> Optional[Dict[str, Any]]:
    path = Path(runs_root).parent / "runs_phase2_full" / "report.json"
    return read_json(path) if path.exists() else None


def stage_names(summary: Dict[str, Any]) -> Dict[int, str]:
    return {row["stage_index"]: row["stage_name"]
            for row in summary.get("capability_matrix", {}).get("pivot", [])}


def family_final_rows(summary: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    final = final_stage(summary)
    result = {}
    for row in summary.get("forgetting", {}).get("family_rows", []):
        if row["metric"] == METRIC and row["stage_index"] == final:
            result[row["family"]] = row
    return result


def skill_final_rows(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    final = final_stage(summary)
    return [row for row in summary.get("forgetting", {}).get("skill_rows", [])
            if row["metric"] == METRIC and row["stage_index"] == final]


def write_phase2_report(runs_root: Path, output: Optional[Path] = None) -> Path:
    runs = load_runs(runs_root)
    if not runs:
        raise SystemExit("No completed runs under %s" % runs_root)
    runs_root = Path(runs_root)
    full_eval = full_eval_summary(runs_root)
    output = Path(output) if output else runs_root / "reports" / "phase2_report.md"
    ensure_dir(output.parent)
    orders = sorted({run["order"] for run in runs})
    seeds = sorted({run["seed"] for run in runs})
    families = sorted({family for run in runs
                       for family in run["summary"].get(
                           "capability_matrix", {}).get("families", [])})
    final = max(final_stage(run["summary"]) for run in runs)
    test_limit = runs[0]["config"].get("evaluation", {}).get("test_limit")
    model = runs[0]["config"].get("model_name_or_path")
    lines = [
        "# FAC-TinyAgent Phase 2 Report",
        "",
        "- Model: `%s`" % model,
        "- Tool families: %s" % ", ".join(families),
        "- Learning orders: %s" % ", ".join(orders),
        "- Seeds: %s" % ", ".join(str(seed) for seed in seeds),
        "- Completed runs: %d" % len(runs),
        "- Capability evaluation: all families at every stage; test subset per family = %s"
        % test_limit,
        "- Method: sequential QLoRA SFT, natural forgetting, no replay",
        "",
        "## Complete capability matrix",
        "",
    ]
    # Per-order matrices (mean across seeds).
    for order in orders:
        order_runs = [run for run in runs if run["order"] == order]
        names = stage_names(order_runs[0]["summary"])
        rows = []
        for stage_index in sorted(names):
            cells = []
            for family in families:
                values = [pivot_value(run["summary"], stage_index, family)
                          for run in order_runs]
                value, spread = mean_std(values)
                cells.append(_mm(value, spread))
            rows.append([names[stage_index]] + cells)
        lines.append("### Order %s" % order)
        lines.append(_table(["stage"] + families, rows))
        lines.append("")
    # Pooled matrix across orders/seeds.
    pooled_rows = []
    for stage_index in range(final + 1):
        cells = []
        for family in families:
            values = [pivot_value(run["summary"], stage_index, family)
                      for run in runs]
            value, spread = mean_std(values)
            cells.append(_mm(value, spread))
        pooled_rows.append(["stage_%02d" % stage_index] + cells)
    lines.append("### Pooled across orders and seeds")
    lines.append(_table(["stage"] + families, pooled_rows))
    lines.append("")
    # Acquisition vs retention. Peak is the best post-learning value before the final stage.
    lines += ["### Acquisition vs retention", "",
              "`peak` is the best observed value after the family was learned and before "
              "the final stage; `final` is the final-stage value; `forgetting` is the "
              "per-run max(0, peak - final), averaged over seeds. The family learned last "
              "has no later re-evaluation, so its peak and forgetting are `-`, but its "
              "final capability is still shown.", ""]
    acquisition_rows = []
    peak_final_summary = []
    for order in orders:
        order_runs = [run for run in runs if run["order"] == order]
        for family in families:
            rows = [family_final_rows(run["summary"]).get(family)
                    for run in order_runs]
            present = [row for row in rows if row]
            if present:
                peak_value, peak_spread = mean_std([row["peak"] for row in present])
                final_value, final_spread = mean_std([row["value"] for row in present])
                forget_value, forget_spread = mean_std(
                    [row["forgetting"] for row in present])
                acquisition_rows.append([
                    order, family, _mm(peak_value, peak_spread),
                    _mm(final_value, final_spread),
                    _mm(forget_value, forget_spread), len(present)])
                peak_final_summary.append({
                    "order": order, "family": family,
                    "peak": peak_value, "final": final_value,
                    "forgetting": forget_value, "runs": len(present)})
            else:
                final_values = [pivot_value(run["summary"],
                                           final_stage(run["summary"]), family)
                                for run in order_runs]
                final_value, final_spread = mean_std(final_values)
                acquisition_rows.append([order, family, "-",
                                         _mm(final_value, final_spread), "-", 0])
                peak_final_summary.append({
                    "order": order, "family": family,
                    "peak": None, "final": final_value,
                    "forgetting": None, "runs": 0})
    lines.append(_table(["order", "family", "peak", "final", "forgetting",
                         "eligible runs"], acquisition_rows))
    lines.append("")
    lines += ["### Final capability by family (all orders)", ""]
    family_capability_rows = []
    for family in families:
        values = [pivot_value(run["summary"], final_stage(run["summary"]), family)
                  for run in runs]
        value, spread = mean_std(values)
        family_capability_rows.append(
            (family, value, spread, len([item for item in values
                                         if item is not None])))
    family_capability_rows.sort(
        key=lambda item: (item[1] is None, -(item[1] or 0.0)))
    lines.append(_table(
        ["family", "mean final", "runs"],
        [[family, _mm(value, spread), count]
         for family, value, spread, count in family_capability_rows]))
    lines.append("")
    # Forgetting per run/order.
    lines.append("## Forgetting")
    lines.append("")
    order_forgetting = []
    for order in orders:
        order_runs = [run for run in runs if run["order"] == order]
        run_averages = []
        for run in order_runs:
            rows = family_final_rows(run["summary"])
            if rows:
                run_averages.append(mean(row["forgetting"] for row in rows.values()))
        value, spread = mean_std(run_averages)
        order_forgetting.append([order, _mm(value, spread), len(order_runs)])
    lines.append(_table(["order", "family-mean forgetting", "runs"],
                        order_forgetting))
    lines.append("")
    lines.append("Each order mean covers the three families that were re-evaluated "
                 "after a later stage; the last-learned family has no forgetting "
                 "estimate, so the family sets differ across orders.")
    lines.append("")
    # Family by order, with learning position.
    family_rows = []
    for family in families:
        cells = []
        all_values = []
        for order in orders:
            order_runs = [run for run in runs if run["order"] == order]
            positions = {stage.get("family"): index
                         for index, stage in enumerate(
                             order_runs[0]["config"].get("stages", []))
                         if stage.get("family")}
            values = []
            for run in order_runs:
                row = family_final_rows(run["summary"]).get(family)
                if row:
                    values.append(row["forgetting"])
                    all_values.append(row["forgetting"])
            value, spread = mean_std(values)
            position = positions.get(family)
            cells.append("%s %s" % (POSITION_NAMES.get(position, position),
                                    _mm(value, spread)))
        value, spread = mean_std(all_values)
        family_rows.append([family] + cells + [_mm(value, spread)])
    lines.append(_table(["family"] + ["order %s" % order for order in orders]
                        + ["overall"], family_rows))
    lines.append("")
    # Position effect (descriptive; family and position are partly confounded).
    position_values = defaultdict(list)
    for run in runs:
        positions = {stage.get("family"): index
                     for index, stage in enumerate(run["config"].get("stages", []))
                     if stage.get("family")}
        for family, row in family_final_rows(run["summary"]).items():
            position_values[positions.get(family)].append(row["forgetting"])
    position_rows = []
    for position in (1, 2, 3, 4):
        if position in position_values:
            value, spread = mean_std(position_values[position])
            position_rows.append([POSITION_NAMES.get(position, position),
                                  _mm(value, spread),
                                  len(position_values[position])])
        else:
            position_rows.append([POSITION_NAMES.get(position, position),
                                  "- (no later stage)", 0])
    lines += ["### Learning position", "",
              _table(["position", "mean forgetting", "observations"], position_rows), ""]
    # Complexity table.
    complexity_rows = []
    for family in families:
        values = []
        for run in runs:
            row = family_final_rows(run["summary"]).get(family)
            if row:
                values.append(row["forgetting"])
        value, spread = mean_std(values)
        complexity_rows.append([family, COMPLEXITY.get(family),
                                _mm(value, spread), len(values)])
    lines += ["### Family complexity (descriptive)", "",
              _table(["family", "complexity", "mean forgetting", "observations"],
                     complexity_rows), ""]
    # Skill ranking.
    skill_values = defaultdict(list)
    for run in runs:
        for row in skill_final_rows(run["summary"]):
            key = (row["family"], row["skill"])
            skill_values[key].append((row["forgetting"], row.get("n", 0)))
    skill_rows = []
    for key, values in skill_values.items():
        weighted = (sum(forgetting * n for forgetting, n in values)
                    / sum(n for _, n in values)) if sum(n for _, n in values) else 0.0
        skill_rows.append([key[0], key[1], _mm(weighted, None),
                           sum(n for _, n in values), len(values)])
    skill_rows.sort(key=lambda row: float(row[2].split("±")[0]), reverse=True)
    lines += ["### Skill-level forgetting (weighted by n)", "",
              _table(["family", "skill", "mean forgetting", "total n", "runs"],
                     skill_rows[:15]), ""]
    # Answers.
    overall_family = []
    for family in families:
        values = []
        for run in runs:
            row = family_final_rows(run["summary"]).get(family)
            if row:
                values.append(row["forgetting"])
        value, spread = mean_std(values)
        overall_family.append((family, value, spread, len(values)))
    ranked = sorted([item for item in overall_family if item[1] is not None],
                    key=lambda item: item[1], reverse=True)
    positive = [item for item in overall_family
                if item[1] is not None and item[1] > 0]
    # Key findings computed from the current sweep, not hard-coded.
    order_final = []
    for order in orders:
        values = []
        for run in runs:
            if run["order"] != order:
                continue
            row = final_pivot_row(run["summary"])
            present = [row.get(family) for family in families
                       if row.get(family) is not None]
            if present:
                values.append(mean(present))
        value, spread = mean_std(values)
        order_final.append((order, value, spread, len(values)))
    order_final.sort(key=lambda item: (item[1] is None, -(item[1] or 0.0)))
    order_family_final = {}
    for order in orders:
        for family in families:
            values = [pivot_value(run["summary"],
                                  final_stage(run["summary"]), family)
                      for run in runs if run["order"] == order]
            value, _ = mean_std(values)
            order_family_final[(order, family)] = value
    gap = None
    for family in families:
        pairs = [(order, order_family_final[(order, family)])
                 for order in orders
                 if order_family_final[(order, family)] is not None]
        if len(pairs) < 2:
            continue
        high = max(pairs, key=lambda pair: pair[1])
        low = min(pairs, key=lambda pair: pair[1])
        width = high[1] - low[1]
        if gap is None or width > gap[0]:
            gap = (width, family, high, low)
    transfer_values = []
    for run in runs:
        stages = run["config"].get("stages", [])
        first_family = next((stage.get("family") for stage in stages
                             if stage.get("family")), None)
        if not first_family:
            continue
        for family in families:
            if family == first_family:
                continue
            before = pivot_value(run["summary"], 0, family)
            after = pivot_value(run["summary"], 1, family)
            if before is not None and after is not None:
                transfer_values.append(after - before)
    transfer_value, transfer_spread = mean_std(transfer_values)
    lines += ["## Key findings", ""]
    if order_final:
        lines.append(
            "- Mean final capability across the four families by order: %s. "
            "The best order is %s, the worst is %s."
            % ("; ".join("%s %s" % (order, _mm(value, spread))
                         for order, value, spread, _ in order_final),
               order_final[0][0], order_final[-1][0]))
    if family_capability_rows:
        lines.append(
            "- Mean final capability by family: %s."
            % "; ".join("%s %s" % (family, _mm(value, spread))
                        for family, value, spread, _ in family_capability_rows))
    if gap:
        lines.append(
            "- Largest order-dependent final-capability gap for one family: %s, "
            "%s in order %s versus %s in order %s."
            % (gap[1], _mm(gap[2][1], None), gap[2][0],
               _mm(gap[3][1], None), gap[3][0]))
        if gap[3][1] == 0.0:
            note = ("  The low cell is a final score of zero on the 6-item subset: "
                    "this is a practical failure, not only a small average drop.")
            if full_eval:
                items = [item for item in full_eval.get("comparison", [])
                         if item.get("order") == gap[3][0]
                         and item.get("family") == gap[1]]
                full_value, full_spread = mean_std([item["full"] for item in items])
                if full_value is not None:
                    note = ("  The low cell is 0.000 on the 6-item subset; the full "
                            "30-item test gives %s, so the exact zero was a small-sample "
                            "artifact, but the gap remains." % _mm(full_value, full_spread))
            lines.append(note)
            lines.append(
                "  The forgetting statistic must be read together with the absolute "
                "final value.")
    if transfer_value is not None:
        lines.append(
            "- Training the first family also raises the untrained families by %s on "
            "average at the next stage (positive transfer), likely shared tool-call/"
            "output-format learning; capability changes are net of this transfer."
            % _mm(transfer_value, transfer_spread))
    lines.append(
        "- Forgetting is estimated only for families re-evaluated after a later stage; "
        "the fourth family in each order has no forgetting estimate. Position and "
        "family are therefore partly confounded.")
    lines.append("")
    lines += ["## Answers to the Phase 2 questions", ""]
    lines.append("### 1. Is forgetting consistent across orders and seeds?")
    if ranked:
        lines.append("Family-level final forgetting (mean±std across runs): %s."
                     % "; ".join("%s %s" % (item[0], _mm(item[1], item[2]))
                                 for item in overall_family if item[1] is not None))
        lines.append("Families with positive mean forgetting: %s."
                     % (", ".join(item[0] for item in positive) or "none"))
    else:
        lines.append("No forgetting rows were available.")
    lines += ["", "### 2. Which tools are forgotten most?"]
    lines.append("; ".join("%s %s" % (item[0], _mm(item[1], item[2]))
                           for item in ranked) or "No data.")
    lines += ["", "### 3. Which skills are forgotten most?"]
    lines.append("; ".join("%s/%s %s (n=%s)" % (row[0], row[1], row[2], row[3])
                           for row in skill_rows[:10]) or "No data.")
    lines += ["", "### 4. Order, schema and argument complexity"]
    lines.append("The family-by-order table above crosses each family with different "
                 "learning positions. The position table is descriptive: position and "
                 "family are partly confounded because each order contains each family "
                 "once. The complexity table is also descriptive with four families. "
                 "Treat order/complexity effects as hypotheses, not causal estimates.")
    lines += ["", "## Appendix: per-run final capability", ""]
    run_rows = []
    for run in runs:
        row = final_pivot_row(run["summary"])
        run_rows.append([run["name"]] + ["%.3f" % row[family]
                                         for family in families])
    lines.append(_table(["run"] + families, run_rows))
    if full_eval:
        comparison = full_eval.get("comparison", [])
        deltas = [item["delta"] for item in comparison]
        delta_value, delta_spread = mean_std(deltas)
        lines += ["", "## Full 30-item final re-evaluation", "",
                  "The final adapters were re-evaluated on all 30 test items per family "
                  "(no retraining). Across %d run-family cells, full minus subset is %s "
                  "on average; individual cells shift by up to %.3f."
                  % (len(deltas), _mm(delta_value, delta_spread),
                     max(abs(value) for value in deltas) if deltas else 0.0), ""]
        full_order_rows = []
        for order in orders:
            row = [order]
            order_runs = sorted({item["run"] for item in comparison
                                 if item["order"] == order})
            for family in families:
                values = [item["full"] for item in comparison
                          if item["order"] == order and item["family"] == family]
                value, spread = mean_std(values)
                row.append(_mm(value, spread))
            run_means = []
            for run_name in order_runs:
                values = [item["full"] for item in comparison
                          if item["run"] == run_name]
                if values:
                    run_means.append(mean(values))
            mean_value, mean_spread = mean_std(run_means)
            row.append(_mm(mean_value, mean_spread))
            full_order_rows.append(row)
        lines.append(_table(["order"] + families + ["mean across families"],
                            full_order_rows))
        lines.append("")
        lines.append("Per-family full-test means: %s."
                     % "; ".join(
                         "%s %s" % (item["family"], _mm(item["mean"], item["std"]))
                         for item in full_eval.get("family_final", [])))
        lines.append("")
        lines.append("Full report: `runs_phase2_full/report.md`.")
        lines.append("")
    lines += ["## Limitations", "",
              "- The stage-by-stage capability matrix uses a test subset per family "
              "(%s); only the final adapters were re-evaluated on all 30 items. "
              "Intermediate-stage scores are noisier than Phase 1." % test_limit,
              "- A small number of orders/seeds; no formal significance test.",
              "- One model (Qwen3-0.6B); validation losses in Phase 1 were near zero, "
              "so overfitting remains a concern.",
              "- Skill-level n is small; the skill ranking is exploratory.",
              "- Natural forgetting only; no replay or adaptive review is implemented.",
              "", "## Phase 3 implications", "",
              "- Use the per-family/per-skill estimates to seed a forgetting-aware "
              "monitor; replay should target the families and structural skills with "
              "the highest estimated forgetting.",
              "- Add more orders and seeds before fixing the monitor thresholds; the "
              "current order effect is not separable from family difficulty.",
              "- The next algorithmic step is a forgetting estimator plus a budgeted "
              "replay controller, not a larger fixed replay buffer.",
              ""]
    output.write_text("\n".join(lines), encoding="utf-8")
    summary = {
        "runs": [run["name"] for run in runs],
        "orders": orders, "seeds": seeds, "families": families,
        "test_limit": test_limit,
        "family_forgetting": [
            {"family": item[0], "mean": item[1], "std": item[2], "n": item[3]}
            for item in overall_family],
        "family_final": [
            {"family": family, "mean": value, "std": spread, "runs": count}
            for family, value, spread, count in family_capability_rows],
        "order_final": [
            {"order": order, "mean": value, "std": spread, "runs": count}
            for order, value, spread, count in order_final],
        "peak_final": peak_final_summary,
        "skill_forgetting": [
            {"family": row[0], "skill": row[1],
             "weighted_mean": float(row[2]),
             "n": row[3], "runs": row[4]} for row in skill_rows],
        "order_average": order_forgetting,
    }
    write_json(output.with_suffix(".json"), summary)
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-root", default="runs_phase2")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    path = write_phase2_report(Path(args.runs_root),
                               Path(args.output) if args.output else None)
    print("report: %s" % path)


if __name__ == "__main__":
    main()
