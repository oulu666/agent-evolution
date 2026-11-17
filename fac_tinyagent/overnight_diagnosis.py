"""Resumable, evaluation-only queue for the next tool-learning diagnosis."""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean

from .metrics import joint_success
from .replay_study import checkpoint, config_for, paired
from .utils import (canonical_json, now_iso, read_json, read_jsonl, sha256_file,
                    write_json, write_jsonl)

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "runs_replay_study_v2_20261109"
SEEDS = [20261108, 20261109, 20261110]
FAMILIES = ["file", "database", "python", "calendar"]
OLD = FAMILIES[:3]


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    write_json(temporary, value)
    temporary.replace(path)


def model_state(order, seed, index, kind="historical"):
    config, stage, adapter = checkpoint(order, seed, index)
    identifier = f"{order}_seed{seed}_{stage['name']}"
    prefix = None
    if kind == "midpoint":
        identifier = f"A_seed{seed}_v2_midpoint"
        prefix = STUDY / "prefixes" / f"A_seed{seed}"
    elif kind == "none":
        identifier = f"A_seed{seed}_v2_none_final"
        adapter = STUDY / "branches" / f"A_seed{seed}_none" / "checkpoint"
    return {"id": identifier, "order": order, "seed": seed, "index": index,
            "kind": kind, "adapter": str(adapter),
            "prefix": str(prefix) if prefix else None,
            "stage": dict(stage, name=identifier, adapter=str(adapter)),
            "config": config, "units": []}


def make_plan(profile="full", smoke=False):
    # Core first: the same questions on both historical and replay trajectories.
    states = []
    seeds = SEEDS[:1] if smoke else SEEDS
    for seed in seeds:
        selected = [(3, "midpoint")] if smoke else [
            (3, "historical"), (3, "midpoint"), (4, "none"), (4, "historical")]
        for index, kind in selected:
            state = model_state("A", seed, index, kind)
            state["units"] = ([f"historical/{f}" for f in FAMILIES]
                              + [f"probe/{f}" for f in OLD] + ["paired/python"])
            states.append(state)
    if profile == "full" and not smoke:
        present = {s["id"] for s in states}
        for order in ("A", "B", "C"):
            for seed in SEEDS:
                for index in range(1, 5):
                    state = model_state(order, seed, index)
                    if state["id"] not in present:
                        state["units"] = [f"historical/{f}" for f in FAMILIES]
                        states.append(state)
    return states


def prepare_data(output, n_pairs, smoke=False):
    from .paired_median_data import generate_paired_median
    paired_rows = generate_paired_median(n_pairs=n_pairs, seed=20261110)
    destination = output / "data" / "paired_median.jsonl"
    if destination.exists():
        if read_jsonl(destination) != paired_rows:
            raise ValueError("Existing paired data differs; choose a new output directory")
    else:
        write_jsonl(destination, paired_rows)
    datasets = {"paired/python": paired_rows}
    sources = [destination]
    for name, data_root, split, families in [
            ("historical", ROOT / "data_phase2", "test", FAMILIES),
            ("probe", ROOT / "data_replay_study", "probe", OLD)]:
        for family in families:
            source = data_root / family / f"{split}.jsonl"
            rows = read_jsonl(source)
            if not rows:
                raise ValueError(f"Missing or empty data: {source}")
            datasets[f"{name}/{family}"] = rows[:2] if smoke else rows
            sources.append(source)
    return datasets, sources


def frozen_protocol(states, datasets, sources, args):
    files = set(sources)
    for data_root in (ROOT / "data_phase2", ROOT / "data_replay_study"):
        files.update((data_root / "fixtures").iterdir())
    # Exclusion data and all evaluator source files are part of the commitment.
    files.update((ROOT / "data_phase2").rglob("*.jsonl"))
    files.update((ROOT / "data_replay_study").rglob("*.jsonl"))
    # Other experiments may be edited in parallel; commit only this queue's dependencies.
    modules = ["overnight_diagnosis.py", "paired_median_data.py", "metrics.py", "replay_study.py",
               "utils.py", "config.py", "research_data.py", "data/generate.py", "data/templates.py",
               "sft/evaluate.py", "sft/train.py", "sft/dataset.py"]
    files.update(ROOT / "fac_tinyagent" / module for module in modules)
    files.update((ROOT / "fac_tinyagent" / "tools").glob("*.py"))
    for state in states:
        adapter = Path(state["adapter"])
        files.update([adapter / "adapter_model.safetensors", adapter / "adapter_config.json"])
        if state["prefix"]:
            files.update(Path(state["prefix"]) / n for n in ("training_state.pt", "manifest.json"))
    missing = [str(p) for p in files if not p.is_file()]
    if missing:
        raise FileNotFoundError("Missing experiment inputs: " + ", ".join(missing))
    return {"version": 1, "profile": args.profile, "smoke": args.smoke,
            "n_pairs": args.pairs, "batch_size": 32, "training": False,
            "purpose": "development diagnosis; paired tasks are not a final policy test",
            "states": states,
            "dataset_counts": {key: len(rows) for key, rows in datasets.items()},
            "input_sha256": {str(p): sha256_file(p) for p in sorted(files)}}


def restore_midpoint(model, prefix):
    """Restore only locally recorded adapter tensors, then verify exact bytes."""
    import torch
    prefix = Path(prefix)
    manifest = read_json(prefix / "manifest.json")
    path = prefix / "training_state.pt"
    if sha256_file(path) != manifest["state_sha256"]:
        raise ValueError("Midpoint checkpoint file checksum differs")
    # Local experiment state also contains optimizer/RNG objects; never load external input here.
    state = torch.load(path, map_location="cpu", weights_only=False)
    parameters = dict(model.named_parameters())
    expected = state["parameters"]
    if not expected or not set(expected).issubset(parameters):
        raise ValueError("Midpoint adapter parameters do not match the model")
    with torch.no_grad():
        for name, tensor in expected.items():
            target = parameters[name]
            if target.shape != tensor.shape:
                raise ValueError(f"Midpoint shape mismatch: {name}")
            target.copy_(tensor.to(device=target.device, dtype=target.dtype))
    digest = hashlib.sha256()
    for name in sorted(expected):
        digest.update(name.encode("utf-8"))
        digest.update(parameters[name].detach().contiguous().view(torch.uint8).cpu().numpy().tobytes())
    if digest.hexdigest() != manifest["parameter_hash"] or digest.hexdigest() != state["parameter_hash"]:
        raise ValueError("Restored midpoint parameter checksum differs")
    model.eval()
    return digest.hexdigest()


def complete_unit(directory, expected_ids):
    marker = directory / "complete.json"
    if not marker.exists():
        return False
    done = read_json(marker)
    result = directory / "results.jsonl"
    report = directory / "stage_report.json"
    if not result.exists() or not report.exists():
        raise ValueError(f"Completed unit is missing output: {directory}")
    if (done["results_sha256"] != sha256_file(result)
            or done["report_sha256"] != sha256_file(report)):
        raise ValueError(f"Completed unit output changed: {directory}")
    if [r["episode_id"] for r in read_jsonl(result)] != expected_ids:
        raise ValueError(f"Completed unit task IDs differ: {directory}")
    return True


def pct(value):
    return f"{100 * value:.2f}%"


def write_report(output, states, datasets):
    cells, wording, transitions = [], [], []
    paired_meta = {r["episode_id"]: r for r in datasets["paired/python"]}
    for state in states:
        for unit in state["units"]:
            directory = output / "evaluations" / state["id"] / unit
            if not (directory / "complete.json").exists():
                continue
            rows = read_jsonl(directory / "results.jsonl")
            report = read_json(directory / "stage_report.json")
            cells.append({"state": state["id"], "order": state["order"],
                          "seed": state["seed"], "index": state["index"], "kind": state["kind"],
                          "unit": unit, "n": len(rows), "metrics": report["metrics"],
                          "duration_seconds": report["duration_seconds"]})
            if unit == "paired/python":
                for n_pairs in (12, 24, 48, 96):
                    if n_pairs > len(paired_meta) // 2:
                        continue
                    # A fixed nested prefix changes sample count while keeping the same wording pair.
                    pair_ids = list(dict.fromkeys(r["pair_id"] for r in datasets[unit]))[:n_pairs]
                    selected = set(pair_ids)
                    grouped = defaultdict(list)
                    for row in rows:
                        metadata = paired_meta[row["episode_id"]]
                        if metadata["pair_id"] in selected:
                            grouped[metadata["wording"]].append(row)
                    scores = {label: {"joint": mean(joint_success(r) for r in part),
                                      "answer": mean(r["final_correct"] for r in part),
                                      "tool": mean(r["tool_correct"] for r in part),
                                      "arguments": mean(r["arguments_correct"] for r in part)}
                              for label, part in grouped.items()}
                    wording.append({"state": state["id"], "seed": state["seed"],
                                    "n_pairs": n_pairs, "scores": scores})
    # Match identical episodes before/after on each learning trajectory.
    indexed = {(s["order"], s["seed"], s["index"], s["kind"]): s for s in states}
    for state in states:
        if state["kind"] == "historical" and state["index"] > 1:
            before = indexed.get((state["order"], state["seed"], state["index"] - 1, "historical"))
        elif state["kind"] in ("midpoint", "none"):
            before = indexed.get(("A", state["seed"], 3, "historical"))
        else:
            before = None
        baselines = [before] if before else []
        if state["kind"] == "none":
            midpoint = indexed.get(("A", state["seed"], 3, "midpoint"))
            if midpoint:
                baselines.append(midpoint)
        for baseline in baselines:
            for unit in sorted(set(state["units"]) & set(baseline["units"])):
                left = output / "evaluations" / baseline["id"] / unit
                right = output / "evaluations" / state["id"] / unit
                if all((p / "complete.json").exists() for p in (left, right)):
                    a, b = [read_jsonl(p / "results.jsonl") for p in (left, right)]
                    transitions.append({"before": baseline["id"], "after": state["id"], "unit": unit,
                                        "joint": paired(a, b, "joint_success"), "answer": paired(a, b)})
    total_units = sum(len(s["units"]) for s in states)
    atomic_json(output / "summary.json", {"completed_units": len(cells), "total_units": total_units,
                                          "cells": cells, "wording": wording, "transitions": transitions})
    lines = ["# 夜间诊断实验结果", "", f"已完成 {len(cells)}/{total_units} 个评估单元。",
             "", "任务为已有模型的评估；成对中位数题用于开发诊断。", "",
             "## 同模型两套试卷与完整学习轨迹", "",
             "| 模型状态 | 题集/工具 | 题数 | 联合成功率 | 答案成功率 |",
             "|---|---|---:|---:|---:|"]
    for cell in cells:
        m = cell["metrics"]
        lines.append(f"| {cell['state']} | {cell['unit']} | {cell['n']} | {pct(m['joint_success_rate'])} | {pct(m['final_task_success_rate'])} |")
    lines += ["", "## 中位数成对问法", "",
              "下表使用完整成对题池；12/24/48/96组的嵌套结果保存在summary.json。嵌套题量用于观察测量变化。", "",
              "| 模型状态 | 每种问法题数 | 问法 | 工具选择 | 参数正确 | 联合成功率 | 答案成功率 |",
              "|---|---:|---|---:|---:|---:|---:|"]
    for item in wording:
        if item["n_pairs"] != len(paired_meta) // 2:
            continue
        for label, scores in item["scores"].items():
            lines.append(f"| {item['state']} | {item['n_pairs']} | {label} | {pct(scores['tool'])} | {pct(scores['arguments'])} | {pct(scores['joint'])} | {pct(scores['answer'])} |")
    lines += ["", "## 相同题目的丢失与获得", "",
              "| 学习前 | 学习后 | 题集/工具 | 原对后错 | 原错后对 | 联合成功率净下降 |",
              "|---|---|---|---:|---:|---:|"]
    for transition in transitions:
        p = transition["joint"]
        lines.append(f"| {transition['before']} | {transition['after']} | {transition['unit']} | {p['lost']} | {p['gained']} | {100*p['net_drop']:+.2f}个百分点 |")
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(cells)


def run(args):
    output = Path(args.output_root).resolve()
    if output == ROOT or output in (STUDY, ROOT / "runs_phase2"):
        raise ValueError("Choose a separate diagnosis output directory")
    output.mkdir(parents=True, exist_ok=True)
    # Advisory lock is released automatically on exit, including interruption.
    import fcntl
    with (output / ".run.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("This diagnosis queue is already running")
        states = make_plan(args.profile, args.smoke)
        datasets, sources = prepare_data(output, args.pairs, args.smoke)
        protocol = frozen_protocol(states, datasets, sources, args)
        tasks = sum(len(datasets[u]) for s in states for u in s["units"])
        units = sum(len(s["units"]) for s in states)
        print(json.dumps({"states": len(states), "units": units, "task_evaluations": tasks,
                          "logical_generation_requests": 2 * tasks, "output": str(output)}, ensure_ascii=False), flush=True)
        if args.dry_run:
            return
        commitment = output / "protocol.json"
        if commitment.exists():
            if read_json(commitment) != protocol:
                raise ValueError("Protocol/input changed; use a new output directory")
        else:
            atomic_json(commitment, protocol)
        if args.report_only:
            write_report(output, states, datasets)
            return
        from .sft.evaluate import evaluate_family, load_eval_model
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable")
        started = time.monotonic()
        completed = 0
        status = {"status": "running", "pid": os.getpid(), "started_at": now_iso(),
                  "total_units": units, "total_task_evaluations": tasks, "completed_units": 0}
        atomic_json(output / "status.json", status)
        try:
            for state in states:
                pending = []
                for unit in state["units"]:
                    directory = output / "evaluations" / state["id"] / unit
                    ids = [r["episode_id"] for r in datasets[unit]]
                    if complete_unit(directory, ids):
                        completed += 1
                    else:
                        pending.append(unit)
                if not pending:
                    continue
                status.update(current_state=state["id"], completed_units=completed, updated_at=now_iso())
                atomic_json(output / "status.json", status)
                print("MODEL", state["id"], "pending", len(pending), flush=True)
                model, tokenizer = load_eval_model(state["config"], state["adapter"])
                try:
                    verified = None
                    if state["prefix"]:
                        verified = restore_midpoint(model, state["prefix"])
                        print("MIDPOINT VERIFIED", verified, flush=True)
                    for unit in pending:
                        status.update(current_unit=unit, updated_at=now_iso())
                        atomic_json(output / "status.json", status)
                        directory = output / "evaluations" / state["id"] / unit
                        fixture_root = ROOT / ("data_phase2" if unit.startswith("historical/") else "data_replay_study") / "fixtures"
                        evaluate_family(model, tokenizer, datasets[unit], state["config"], state["stage"], directory,
                                        str(fixture_root / "toolbench.db"), str(fixture_root / "calendar.json"))
                        result_path = directory / "results.jsonl"
                        if [r["episode_id"] for r in read_jsonl(result_path)] != [r["episode_id"] for r in datasets[unit]]:
                            raise ValueError(f"Incomplete evaluation: {state['id']} {unit}")
                        atomic_json(directory / "complete.json", {
                            "n": len(datasets[unit]), "completed_at": now_iso(),
                            "state_id": state["id"], "loaded_adapter": state["adapter"],
                            "midpoint_prefix": state["prefix"], "midpoint_parameter_sha256": verified,
                            "results_sha256": sha256_file(result_path),
                            "report_sha256": sha256_file(directory / "stage_report.json")})
                        completed += 1
                        status.update(completed_units=completed, updated_at=now_iso(),
                                      invocation_elapsed_seconds=round(time.monotonic() - started, 1))
                        atomic_json(output / "status.json", status)
                finally:
                    del model, tokenizer
                    gc.collect()
                    torch.cuda.empty_cache()
                write_report(output, states, datasets)
            write_report(output, states, datasets)
            status.update(status="completed", completed_units=completed, finished_at=now_iso(),
                          invocation_elapsed_seconds=round(time.monotonic() - started, 1))
            atomic_json(output / "status.json", status)
            print("COMPLETED", output / "report.md", flush=True)
        except BaseException as error:
            status.update(status="interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
                          error=f"{type(error).__name__}: {error}", updated_at=now_iso())
            atomic_json(output / "status.json", status)
            write_report(output, states, datasets)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", default=str(ROOT / "runs_overnight_diagnosis_20261110"))
    parser.add_argument("--profile", choices=["core", "full"], default="full")
    parser.add_argument("--pairs", type=int, choices=[2, 12, 24, 48, 96], default=96)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    if args.smoke:
        args.pairs = 2
    run(args)


if __name__ == "__main__":
    main()
