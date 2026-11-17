"""Sequential QLoRA learning: M0 -> File -> Database -> Python."""
from __future__ import annotations

from collections import defaultdict
import csv
import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import env_check
from .metrics import (write_capability_matrix, write_forgetting_reports,
                      METRIC_KEYS)
from .utils import (ensure_dir, now_iso, read_json, read_jsonl, set_seed,
                    write_json, write_oom_report, oom_advice)


def _run_id(seed: int) -> str:
    return "%s_seed%d" % (datetime.datetime.now().strftime("%Y%m%d_%H%M%S"), seed)


def _check_data(config: Dict[str, Any]) -> Path:
    data_root = Path(config["data_root"])
    for family in config["data"]["families"]:
        for split in ("train", "val", "test"):
            path = data_root / family / ("%s.jsonl" % split)
            if not path.exists():
                raise FileNotFoundError(
                    "Missing %s. Run `python -m fac_tinyagent.run gen-data` first." % path)
    fixture = data_root / "fixtures" / "toolbench.db"
    if not fixture.exists():
        raise FileNotFoundError("Missing fixture: %s" % fixture)
    calendar = data_root / "fixtures" / "calendar.json"
    if "calendar" in config["data"]["families"] and not calendar.exists():
        raise FileNotFoundError("Missing fixture: %s" % calendar)
    return data_root


def _test_subset(episodes: List[Dict[str, Any]], limit: Optional[int]
                 ) -> List[Dict[str, Any]]:
    if not limit or limit >= len(episodes):
        return episodes
    by_template = defaultdict(list)
    for episode in episodes:
        by_template[episode["template_id"]].append(episode)
    groups = [by_template[key] for key in sorted(by_template)]
    selected = []
    index = 0
    while len(selected) < limit and any(index < len(rows) for rows in groups):
        for rows in groups:
            if index < len(rows) and len(selected) < limit:
                selected.append(rows[index])
        index += 1
    return sorted(selected, key=lambda row: row["episode_id"])


def _write_stage_summary(run_dir: Path, stage: Dict[str, Any],
                         reports: List[Dict[str, Any]]) -> None:
    directory = ensure_dir(run_dir / "evaluation" / stage["name"])
    write_json(directory / "summary.json", {"stage": stage, "reports": reports})
    with (directory / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["stage", "family", "n"] + METRIC_KEYS)
        for report in reports:
            writer.writerow([stage["name"], report["family"], report["metrics"]["n"]]
                            + [report["metrics"][key] for key in METRIC_KEYS])


def _save_state(run_dir: Path, state: Dict[str, Any]) -> None:
    state["updated"] = now_iso()
    write_json(run_dir / "state.json", state)


def run_sequential(config: Dict[str, Any], run_id: Optional[str] = None
                   ) -> Dict[str, Any]:
    from .sft.evaluate import evaluate_family, free_model, load_eval_model
    from .sft.train import train_stage
    import torch

    data_root = _check_data(config)
    db_path = str(data_root / "fixtures" / "toolbench.db")
    calendar_path = str(data_root / "fixtures" / "calendar.json")
    test_limit = config.get("evaluation", {}).get("test_limit")
    all_families = bool(config.get("evaluation", {}).get("all_families", False))
    run_id = run_id or _run_id(int(config["seed"]))
    run_dir = Path(config["output_root"]) / run_id
    if run_dir.exists():
        raise FileExistsError("Run directory already exists; choose a new run id: %s"
                              % run_dir)
    ensure_dir(run_dir)
    ensure_dir(run_dir / "checkpoints")
    ensure_dir(run_dir / "evaluation")
    ensure_dir(run_dir / "reports")
    write_json(run_dir / "config.json", config)
    manifest_path = data_root / "manifest.json"
    manifest = read_json(manifest_path) if manifest_path.exists() else None
    write_json(run_dir / "run.json", {
        "run_id": run_id, "created": now_iso(), "seed": config["seed"],
        "model_name_or_path": config["model_name_or_path"],
        "run_name": config.get("run_name"),
        "config_path": config.get("_config_path"),
        "data_manifest": manifest,
        "test_limit": test_limit, "all_families": all_families,
    })
    environment = env_check.write_report(run_dir / "environment_report.txt")
    if not environment.get("pass"):
        raise SystemExit("Environment check failed; see %s"
                         % (run_dir / "environment_report.txt"))
    stages = [dict(stage, index=index, adapter=None)
              for index, stage in enumerate(config["stages"])]
    learned_stage = {stage["family"]: stage["index"]
                     for stage in stages if stage.get("family")}
    evaluations = []
    state = {"run_id": run_id, "completed_stages": [], "evaluations": 0}
    model = None
    current_stage = "initialization"
    try:
        base_stage = stages[0]
        current_stage = base_stage["name"]
        print("M0 evaluation on all families", flush=True)
        model, tokenizer = load_eval_model(config, None)
        base_reports = []
        for family in config["data"]["families"]:
            episodes = _test_subset(
                read_jsonl(data_root / family / "test.jsonl"), test_limit)
            report = evaluate_family(
                model, tokenizer, episodes, config, base_stage,
                run_dir / "evaluation" / base_stage["name"] / family,
                db_path, calendar_path)
            base_reports.append(report)
            evaluations.append(report)
        _write_stage_summary(run_dir, base_stage, base_reports)
        state["completed_stages"].append(base_stage["name"])
        state["evaluations"] = len(evaluations)
        _save_state(run_dir, state)
        print("M0 done", flush=True)
        free_model(model)
        model = None
        previous_adapter = None
        for stage in stages[1:]:
            current_stage = stage["name"]
            family = stage["family"]
            print("stage start", stage["name"], "family", family, flush=True)
            train_path = str(data_root / family / "train.jsonl")
            val_path = str(data_root / family / "val.jsonl")
            stage_dir = run_dir / "checkpoints" / stage["name"]
            summary = train_stage(config, stage, train_path, val_path,
                                  previous_adapter, str(stage_dir))
            stage["adapter"] = str(stage_dir)
            stage["train_summary"] = summary
            previous_adapter = str(stage_dir)
            model, tokenizer = load_eval_model(config, str(stage_dir))
            if all_families:
                eval_families = list(config["data"]["families"])
            else:
                eval_families = [item["family"] for item in stages[:stage["index"] + 1]
                                 if item.get("family")]
            stage_reports = []
            for seen_family in eval_families:
                episodes = _test_subset(
                    read_jsonl(data_root / seen_family / "test.jsonl"), test_limit)
                report = evaluate_family(
                    model, tokenizer, episodes, config, stage,
                    run_dir / "evaluation" / stage["name"] / seen_family,
                    db_path, calendar_path)
                stage_reports.append(report)
                evaluations.append(report)
            _write_stage_summary(run_dir, stage, stage_reports)
            state["completed_stages"].append(stage["name"])
            state["evaluations"] = len(evaluations)
            _save_state(run_dir, state)
            print("stage done", stage["name"], flush=True)
            free_model(model)
            model = None
        matrix = write_capability_matrix(run_dir / "reports", evaluations)
        forgetting = write_forgetting_reports(run_dir / "reports", evaluations,
                                              learned_stage)
        summary = {
            "run_id": run_id, "created": now_iso(),
            "config": config, "stages": stages,
            "evaluations": evaluations, "capability_matrix": matrix,
            "forgetting": forgetting,
        }
        write_json(run_dir / "summary.json", summary)
        from .report import write_phase1_report
        write_phase1_report(run_dir)
        return summary
    except torch.cuda.OutOfMemoryError as exc:
        write_oom_report(run_dir / "oom_report.txt", config, current_stage, str(exc))
        print(oom_advice())
        raise
    finally:
        if model is not None:
            try:
                free_model(model)
            except Exception:
                pass
