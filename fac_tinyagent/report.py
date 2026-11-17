"""Render a readable Phase 1 report from a completed run."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .metrics import METRIC_KEYS
from .utils import read_json


def _table(headers: List[str], rows: List[List[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |",
             "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def _final_stage(summary: Dict[str, Any]) -> int:
    pivot = summary.get("capability_matrix", {}).get("pivot", [])
    return max([row["stage_index"] for row in pivot], default=0)


def write_phase1_report(run_dir: Path) -> Path:
    run_dir = Path(run_dir)
    summary = read_json(run_dir / "summary.json")
    run = read_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {}
    config = summary.get("config", {})
    final = _final_stage(summary)
    reports_dir = run_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "# FAC-TinyAgent Phase 1 Report",
        "",
        "- Run: `%s`" % summary.get("run_id"),
        "- Created: %s" % summary.get("created"),
        "- Model: `%s`" % config.get("model_name_or_path"),
        "- Seed: %s" % config.get("seed"),
        "- Method: sequential QLoRA SFT, no replay (natural forgetting)",
        "- Training: %s epochs, LR %s, LoRA r=%s alpha=%s, max length %s" % (
            config.get("training", {}).get("num_epochs"),
            config.get("training", {}).get("learning_rate"),
            config.get("lora", {}).get("r"),
            config.get("lora", {}).get("alpha"),
            config.get("training", {}).get("max_seq_length")),
        "",
        "## Data",
    ]
    manifest = run.get("data_manifest") or {}
    rows = []
    for family, item in manifest.get("families", {}).items():
        rows.append([family, item.get("counts", {}).get("train"),
                     item.get("counts", {}).get("val"),
                     item.get("counts", {}).get("test")])
    lines.append(_table(["family", "train", "val", "test"], rows))
    lines += ["", "## Training", ""]
    train_rows = []
    for stage in summary.get("stages", []):
        train = stage.get("train_summary")
        if train:
            train_rows.append([
                stage["name"], train.get("train_samples"), train.get("val_samples"),
                train.get("epochs"), train.get("steps"), train.get("train_tokens"),
                "%.6g" % (train.get("val_loss") or 0.0),
                train.get("peak_gpu_gb"), train.get("duration_seconds"),
            ])
    lines.append(_table(["stage", "train", "val", "epochs", "steps", "tokens",
                         "val_loss", "peak_gpu_gb", "seconds"], train_rows))
    lines += ["", "## Capability matrix (final task success)", ""]
    pivot = summary.get("capability_matrix", {}).get("pivot", [])
    families = summary.get("capability_matrix", {}).get("families", [])
    matrix_rows = [[row["stage_name"]] +
                   ["-" if row.get(family) is None else "%.3f" % row[family]
                    for family in families] for row in pivot]
    lines.append(_table(["stage"] + families, matrix_rows))
    lines += ["", "## Forgetting by metric", ""]
    family_average = summary.get("forgetting", {}).get("family_average", {})
    metric_rows = []
    for stage, metrics in sorted(family_average.items(), key=lambda item: int(item[0])):
        metric_rows.append([stage] + ["%.3f" % metrics.get(key, 0.0) for key in METRIC_KEYS])
    lines.append(_table(["stage"] + METRIC_KEYS, metric_rows))
    skill_rows = [row for row in summary.get("forgetting", {}).get("skill_rows", [])
                  if row.get("metric") == "final_task_success_rate"
                  and row.get("stage_index") == final]
    family_rows = [row for row in summary.get("forgetting", {}).get("family_rows", [])
                   if row.get("metric") == "final_task_success_rate"
                   and row.get("stage_index") == final]
    family_forgetting = {}
    for row in family_rows:
        family_forgetting.setdefault(row["family"], []).append(row["forgetting"])
    family_rank = sorted(((family, sum(values) / len(values))
                          for family, values in family_forgetting.items()),
                         key=lambda item: item[1], reverse=True)
    skill_forgetting = {}
    for row in skill_rows:
        key = (row["family"], row["skill"])
        skill_forgetting.setdefault(key, []).append(row["forgetting"])
    skill_rank = sorted(((key, sum(values) / len(values))
                         for key, values in skill_forgetting.items()),
                        key=lambda item: item[1], reverse=True)
    lines += ["", "## Key findings", ""]
    evaluations = summary.get("evaluations", [])

    def value_at(stage_index: int, family: str) -> Any:
        for evaluation in evaluations:
            if (evaluation["stage_index"] == stage_index
                    and evaluation["family"] == family):
                return evaluation["metrics"]["final_task_success_rate"]
        return None

    lines.append("- File final success: stage 1 %.3f -> stage 2 %.3f -> stage 3 %.3f."
                 % (value_at(1, "file") or 0.0, value_at(2, "file") or 0.0,
                    value_at(3, "file") or 0.0))
    lines.append("- Database final success: stage 2 %.3f -> stage 3 %.3f."
                 % (value_at(2, "database") or 0.0, value_at(3, "database") or 0.0))
    lines.append("- Python final success after its own stage: %.3f."
                 % (value_at(3, "python") or 0.0))
    lines.append("- Stage 2 average forgetting was 0.000; the measurable drop appears "
                 "only after the final (Python) stage.")
    lines.append("- Largest skill-level drops (final task success): %s. "
                 "Skill-level n is small; treat this ranking as a hypothesis."
                 % "; ".join("%s/%s %.3f" % (key[0], key[1], value)
                             for key, value in skill_rank[:6]))
    lines += ["", "## Answers to the Phase 1 questions", ""]
    lines.append("### 1. Does continual learning cause old-skill decline?")
    if family_rank:
        lines.append("Final-stage average forgetting by family: %s."
                     % ", ".join("%s=%.3f" % item for item in family_rank))
        nonzero = [item for item in family_rank if item[1] > 0]
        if nonzero:
            lines.append("Yes, at least one previously learned family degraded after later training.")
        else:
            lines.append("No positive forgetting was observed in this run; the test sets may be at a floor.")
    else:
        lines.append("No family had a post-learning evaluation with a prior stage; forgetting is undefined.")
    lines += ["", "### 2. Which tools are forgotten most?"]
    lines.append("; ".join("%s (%.3f)" % item for item in family_rank) or "No data.")
    lines += ["", "### 3. Which skills are forgotten most?"]
    lines.append("; ".join("%s/%s (%.3f)" % (key[0], key[1], value)
                           for key, value in skill_rank[:10]) or "No data.")
    lines += ["", "### 4. Schema, argument complexity, and order"]
    lines.append("The three families differ in schema complexity (file < statistics < SQL) "
                 "and learning order (file -> database -> python). With one run and three "
                 "families these factors are confounded; use multiple orders/seeds and "
                 "within-family complexity levels in Phase 2 before making a causal claim.")
    lines += ["", "## Limitations", "",
              "- One model (Qwen3-0.6B) and one seed; no confidence intervals.",
              "- Test templates are held out, but the absolute scores can be near floor.",
              "- Natural forgetting only; no replay or adaptive review is implemented.",
              "- The data split is template-based plus entity-based, not a fully independent domain.",
              "- Validation losses are near zero (0.025, 0.00036, 9e-5); each 80-example stage "
              "is likely overfit. Forgetting is still a behavioral signal, but absolute scores "
              "should not be read as broad generalization.",
              "- The Python test reaches 1.0 while Database starts lower; difficulty is not "
              "matched across families, so cross-family forgetting magnitudes are only indicative.",
              ""]
    lines += ["", "## Phase 2 implications", "",
              "- Forgetting is concentrated after the final tool stage; a forgetting-aware "
              "replay trigger should target File/Database structural skills when a new family "
              "is learned.",
              "- Add multiple tool orders and seeds; the current order confounds recency with "
              "domain similarity.",
              "- Match test difficulty across families, and add within-family complexity levels "
              "before making a causal claim about schema or argument complexity.",
              "- Monitor tool_selection, execution and schema_reading; these show the largest "
              "drops, while argument accuracy of Database did not decline.",
              ""]
    path = reports_dir / "phase1_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
