"""[ext 2026-11-11] Target-fraction sweep on the Round-2 A scenario.

Same setting as round2_study (A order, stage 3 -> 4, Calendar new, File/
Database/Python old, Round-2 replay pool and targets, 10% budget, batch 1,
fixed target family weights 1/3 each) except:
  * target_fraction in {0, .25, .5, .75} (0 == uniform replay),
  * probes = monitor v2 (data_ext_monitor_v2) -> a fresh shared prefix,
  * output under runs_ext_tf/ (never touches runs_round2).
Optional ``none`` arm for the same prefix.  ``--smoke`` uses 16 new examples,
1 epoch, 4 probes/family and 3 eval episodes/family under runs_ext_tf_smoke/.
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
from statistics import mean, stdev
from typing import Any, Dict, List, Optional

from .ext_rescore import corrected_joint
from .replay_study import config_for
from .utils import ensure_dir, read_json, read_jsonl, write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data_round2"
MV2 = ROOT / "data_ext_monitor_v2"
OLD = ["file", "database", "python"]
FAMILIES = OLD + ["calendar"]
SEEDS = [20261108, 20261109, 20261110]
FRACTIONS = [0.0, 0.25, 0.5, 0.75]
DB_PATH = ROOT / "data_phase2" / "fixtures" / "toolbench.db"
CALENDAR_PATH = ROOT / "data_replay_study" / "fixtures" / "calendar.json"


def out_root(smoke: bool) -> Path:
    return ROOT / ("runs_ext_tf_smoke" if smoke else "runs_ext_tf")


def arm_name(tf: Optional[float]) -> str:
    return "none" if tf is None else "tf%02d" % int(round(tf * 100))


def branch_dir(seed: int, arm: str, smoke: bool) -> Path:
    return out_root(smoke) / "branches" / ("A_seed%d_%s" % (seed, arm))


def _smoke_inputs(seed: int) -> Dict[str, str]:
    base = out_root(True) / "inputs"
    ensure_dir(base)
    new = base / "calendar_train16.jsonl"
    if not new.exists():
        write_jsonl(new, read_jsonl(ROOT / "data_phase2" / "calendar" / "train.jsonl")[:16])
    probes = {}
    for f in OLD:
        p = base / ("probe_%s.jsonl" % f)
        if not p.exists():
            write_jsonl(p, read_jsonl(MV2 / (f + ".jsonl"))[::8])
        probes[f] = str(p)
    return {"new": str(new), **{"probe_" + f: probes[f] for f in OLD}}


def train(seed: int, tf: Optional[float], smoke: bool) -> Dict[str, Any]:
    from .replay_train import train_replay_stage
    target_ids = read_json(DATA / "manifest.json")["target_ids"]
    config = config_for("A", seed, batch_size=32)
    stage = dict(config["stages"][4], index=4)
    new_path = str(ROOT / "data_phase2" / "calendar" / "train.jsonl")
    probes = {f: str(MV2 / (f + ".jsonl")) for f in OLD}
    if smoke:
        config["training"]["num_epochs"] = 1
        inputs = _smoke_inputs(seed)
        new_path = inputs["new"]
        probes = {f: inputs["probe_" + f] for f in OLD}
    arm = arm_name(tf)
    run = branch_dir(seed, arm, smoke)
    ckpt = run / "checkpoint"
    if (ckpt / "train_summary.json").exists():
        print("skip train", run.name, flush=True)
        return read_json(ckpt / "train_summary.json")
    if run.exists():
        aside = run.parent / (run.name + "_partial_%d" % int(time.time()))
        print("moving partial run aside:", aside, flush=True)
        shutil.move(str(run), str(aside))
    print("train", run.name, flush=True)
    return train_replay_stage(
        config=config, stage=stage, train_path=new_path,
        old_train_paths={f: str(DATA / "pool" / (f + ".jsonl")) for f in OLD},
        probe_paths=probes,
        previous_adapter=str(ROOT / "runs_phase2" / ("A_seed%d" % seed) / "checkpoints" / "stage_03_python"),
        output_dir=str(ckpt), db_path=str(DB_PATH), calendar_path=str(CALENDAR_PATH),
        mode="none" if tf is None else "targeted", replay_ratio=0.1, uniform_floor=0.2,
        prefix_dir=str(out_root(smoke) / "prefixes" / ("A_seed%d" % seed)),
        target_ids=target_ids, target_fraction=0.0 if tf is None else tf,
        target_family_weights={f: 1.0 / len(OLD) for f in OLD})


def suites(smoke: bool) -> List[Dict[str, Any]]:
    return [
        {"name": "historical", "families": FAMILIES,
         "path": lambda f: ROOT / "data_phase2" / f / "test.jsonl", "fix": ROOT / "data_phase2" / "fixtures"},
        {"name": "natural_final", "families": OLD,
         "path": lambda f: DATA / "final" / (f + ".jsonl"), "fix": ROOT / "data_replay_study" / "fixtures"},
        {"name": "monitor_v2_end", "families": OLD,
         "path": lambda f: MV2 / (f + ".jsonl"), "fix": ROOT / "data_phase2" / "fixtures"},
    ]


def evaluate(seed: int, tf: Optional[float], smoke: bool) -> None:
    from .sft.evaluate import evaluate_family, free_model, load_eval_model
    arm = arm_name(tf)
    ckpt = branch_dir(seed, arm, smoke) / "checkpoint"
    if not (ckpt / "train_summary.json").exists():
        raise FileNotFoundError("no finished checkpoint: %s" % ckpt)
    todo = []
    for spec in suites(smoke):
        for f in spec["families"]:
            out = out_root(smoke) / "evaluation" / ("A_seed%d_%s" % (seed, arm)) / spec["name"] / f
            if not (out / "stage_report.json").exists():
                todo.append((spec, f, out))
    if not todo:
        print("skip eval", seed, arm, flush=True)
        return
    config = config_for("A", seed, batch_size=32)
    model, tok = load_eval_model(config, str(ckpt))
    stage = {"name": "A_seed%d_%s_eval" % (seed, arm), "index": 4, "adapter": str(ckpt)}
    try:
        for spec, f, out in todo:
            rows = read_jsonl(spec["path"](f))
            if smoke:
                rows = rows[:3]
            evaluate_family(model, tok, rows, config, stage, out,
                            str(spec["fix"] / "toolbench.db"), str(spec["fix"] / "calendar.json"))
    finally:
        free_model(model)


def _score(path: Path, corrected: bool) -> Optional[float]:
    if not path.exists():
        return None
    rows = read_jsonl(path)
    return mean(bool(corrected_joint(r)) if corrected else bool(r["joint_success"]) for r in rows) if rows else None


def _ms(values):
    values = [v for v in values if v is not None]
    if not values:
        return None, None
    return mean(values), (stdev(values) if len(values) > 1 else 0.0)


def collect(smoke: bool = False) -> Dict[str, Any]:
    root = out_root(smoke)
    rows = []
    arms = [arm_name(t) for t in FRACTIONS] + ["none"]
    for seed in SEEDS:
        for arm in arms:
            ev = root / "evaluation" / ("A_seed%d_%s" % (seed, arm))
            summ = branch_dir(seed, arm, smoke) / "checkpoint" / "train_summary.json"
            if not summ.exists():
                continue
            s = read_json(summ)
            plan_path = summ.parent / "replay_plan.json"
            plan = read_json(plan_path) if plan_path.exists() else {}
            row = {"seed": seed, "arm": arm, "target_fraction": s.get("target_fraction"),
                   "actual_target_fraction": plan.get("actual_target_fraction"),
                   "replay_input_tokens": s.get("replay_input_tokens"),
                   "budget_input_tokens": s.get("budget_input_tokens"),
                   "target_samples_by_family": s.get("target_samples_by_family"),
                   "duration_seconds": s.get("duration_seconds"),
                   "actual_elapsed_seconds": s.get("actual_elapsed_seconds"),
                   "probe_start": s["probes"]["start"]["scores"],
                   "probe_mid": s["probes"]["midpoint"]["scores"],
                   "replay_positions": len(plan.get("common_replay_positions", []))}
            for f in OLD:
                p = ev / "natural_final" / f / "results.jsonl"
                row["nat_raw_" + f] = _score(p, False)
                row["nat_fix_" + f] = _score(p, True)
                row["hist_" + f] = _score(ev / "historical" / f / "results.jsonl", False)
                row["mv2end_" + f] = _score(ev / "monitor_v2_end" / f / "results.jsonl", False)
            row["calendar_hist"] = _score(ev / "historical" / "calendar" / "results.jsonl", False)
            for key in ("nat_raw", "nat_fix", "hist"):
                vals = [row[key + "_" + f] for f in OLD]
                row[key + "_old_macro"] = mean(vals) if all(v is not None for v in vals) else None
            rows.append(row)
    agg = []
    for arm in arms:
        part = [r for r in rows if r["arm"] == arm]
        if not part:
            continue
        entry = {"arm": arm, "n_seeds": len(part)}
        for key in ["nat_raw_old_macro", "nat_fix_old_macro", "hist_old_macro", "calendar_hist",
                    "actual_elapsed_seconds", "replay_input_tokens", "actual_target_fraction"] + \
                   ["nat_fix_" + f for f in OLD] + ["hist_" + f for f in OLD]:
            m, sd = _ms([r.get(key) for r in part])
            entry[key] = {"mean": m, "std": sd}
        agg.append(entry)
    return {"rows": rows, "aggregates": agg}


def report(smoke: bool = False) -> Path:
    res = collect(smoke)
    root = out_root(smoke)
    ensure_dir(root)
    write_json(root / "results.json", res)
    f = lambda d: "-" if d is None or d.get("mean") is None else (
        "%.3f" % d["mean"] if not d.get("std") else "%.3f±%.3f" % (d["mean"], d["std"]))
    lines = ["# Target-fraction sweep (A scenario, 10% budget)", "",
             "nat = independent natural final, old-family macro joint; fix = File last-match re-scored "
             "against the asked-for last line; raw = original Round-2 labels. hist = historical test.", "",
             "| arm | seeds | nat fix | nat raw | hist old | Calendar | File fix | DB | Py | target frac (actual) | branch s |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for a in res["aggregates"]:
        lines.append("| %s | %d | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            a["arm"], a["n_seeds"], f(a["nat_fix_old_macro"]), f(a["nat_raw_old_macro"]),
            f(a["hist_old_macro"]), f(a["calendar_hist"]), f(a["nat_fix_file"]),
            f(a["nat_fix_database"]), f(a["nat_fix_python"]), f(a["actual_target_fraction"]),
            f(a["actual_elapsed_seconds"])))
    lines += ["", "## Runs", ""]
    for r in res["rows"]:
        lines.append("- seed%d %s: %s" % (r["seed"], r["arm"], json.dumps(
            {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()
             if k not in ("seed", "arm")}, ensure_ascii=False)))
    path = root / "report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["train", "eval", "report", "check-smoke"], required=True)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--arm", help="tf00|tf25|tf50|tf75|none")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    tf = None
    if args.arm and args.arm != "none":
        tf = int(args.arm[2:]) / 100.0
    if args.phase == "train":
        summary = train(args.seed, tf, args.smoke)
        print("TRAIN_OK", args.seed, args.arm, summary.get("actual_elapsed_seconds"), flush=True)
    elif args.phase == "eval":
        evaluate(args.seed, tf, args.smoke)
        print("EVAL_OK", args.seed, args.arm, flush=True)
    elif args.phase == "check-smoke":
        bad = []
        for arm in ("tf00", "tf50"):
            ck = branch_dir(args.seed, arm, True) / "checkpoint"
            s = read_json(ck / "train_summary.json")
            plan = read_json(ck / "replay_plan.json")
            if not s.get("completed") or s["replay_input_tokens"] <= 0:
                bad.append("%s: no replay" % arm)
            if arm == "tf50" and not plan.get("target_actual_input_tokens"):
                bad.append("tf50: no target tokens")
            if arm == "tf00" and plan.get("target_actual_input_tokens"):
                bad.append("tf00: unexpected target tokens")
            ev = out_root(True) / "evaluation" / ("A_seed%d_%s" % (args.seed, arm))
            for suite, fams in (("historical", FAMILIES), ("natural_final", OLD), ("monitor_v2_end", OLD)):
                for fam in fams:
                    if not (ev / suite / fam / "stage_report.json").exists():
                        bad.append("%s missing eval %s/%s" % (arm, suite, fam))
            print(arm, "replay", s["replay_input_tokens"], "budget", s["budget_input_tokens"],
                  "target_tokens", plan.get("target_actual_input_tokens"),
                  "actual_tf", plan.get("actual_target_fraction"), flush=True)
        if bad:
            print("SMOKE_FAIL", bad, flush=True)
            raise SystemExit(2)
        print("SMOKE_OK", flush=True)
    print("report:", report(args.smoke), flush=True)


if __name__ == "__main__":
    main()
