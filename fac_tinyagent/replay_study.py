"""Reproducible, resumable pilot: historical audit then budgeted tool replay.

Historical test scores choose a transition; sealed_test never chooses a policy.
Existing checkpoints, data and reports are read only throughout.
"""
from __future__ import annotations

import argparse
import gc
from pathlib import Path
from statistics import mean, stdev

from .utils import read_json, read_jsonl, write_json, sha256_file, now_iso

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs_replay_study_v2_20261109"
HISTORICAL = ROOT / "runs_replay_study_20261109" / "historical_batch32"
SEEDS = [20261108, 20261109, 20261110]
FAMILIES = ["file", "database", "python", "calendar"]
MODES = ["none", "uniform", "adaptive"]


def config_for(order, seed, batch_size=32):
    config = read_json(ROOT / "runs_phase2" / f"{order}_seed{seed}" / "config.json")
    config["data_root"] = str(ROOT / "data_phase2")
    config["evaluation"]["batch_size"] = batch_size
    config["evaluation"]["test_limit"] = None
    return config


def checkpoint(order, seed, index):
    config = config_for(order, seed)
    stage = dict(config["stages"][index])
    stage["index"] = index
    adapter = ROOT / "runs_phase2" / f"{order}_seed{seed}" / "checkpoints" / stage["name"]
    stage["adapter"] = str(adapter)
    return config, stage, adapter


def score_rows(rows, key="final_correct"):
    if key == "joint_success":
        return mean(all(row.get(k, False) for k in (
            "tool_correct", "arguments_correct", "execution_success", "final_correct")) for row in rows)
    return mean(bool(row[key]) for row in rows)


def paired(before, after, key="final_correct"):
    right = {r["episode_id"]: r for r in after}
    if {r["episode_id"] for r in before} != set(right):
        raise ValueError("Paired evaluations must contain identical episode IDs")
    def correct(row):
        if key == "joint_success":
            return all(row[k] for k in ("tool_correct", "arguments_correct", "execution_success", "final_correct"))
        return bool(row[key])
    lost = sum(correct(r) and not correct(right[r["episode_id"]]) for r in before)
    gained = sum(not correct(r) and correct(right[r["episode_id"]]) for r in before)
    return {"n": len(before), "before": score_rows(before, key),
            "after": score_rows(after, key), "lost": lost, "gained": gained,
            "net_drop": (lost - gained) / len(before)}


def evaluate_adapter(config, stage, adapter, data_root, split, output):
    from .sft.evaluate import load_eval_model, evaluate_family
    import torch
    missing = [f for f in FAMILIES if not (output / f / "stage_report.json").exists()]
    if not missing:
        return
    model, tokenizer = load_eval_model(config, str(adapter))
    try:
        for family in missing:
            rows = read_jsonl(data_root / family / f"{split}.jsonl")
            evaluate_family(model, tokenizer, rows, config, stage, output / family,
                            str(data_root / "fixtures" / "toolbench.db"),
                            str(data_root / "fixtures" / "calendar.json"))
    finally:
        del model, tokenizer
        gc.collect()
        torch.cuda.empty_cache()


def supplement(orders):
    # Both endpoints use one evaluation protocol; no mixing new batching and old scores.
    for order in orders:
        for seed in SEEDS:
            for index in (3, 4):
                config, stage, adapter = checkpoint(order, seed, index)
                evaluate_adapter(config, stage, adapter, ROOT / "data_phase2", "test",
                                 HISTORICAL / f"{order}_seed{seed}" / stage["name"])
    historical_report(orders)


def historical_report(orders):
    records = []
    for order in orders:
        for seed in SEEDS:
            config = config_for(order, seed)
            old = [s["family"] for s in config["stages"][1:4]]
            for family in FAMILIES:
                paths = [HISTORICAL / f"{order}_seed{seed}" /
                         config["stages"][i]["name"] / family / "results.jsonl" for i in (3, 4)]
                if not all(p.exists() for p in paths):
                    continue
                before, after = [read_jsonl(p) for p in paths]
                records.append({"order": order, "seed": seed, "family": family,
                                "is_old": family in old,
                                "final": paired(before, after),
                                "joint": paired(before, after, "joint_success")})
    summary = []
    for order in orders:
        per_seed = []
        for seed in SEEDS:
            rows = [r for r in records if r["order"] == order and r["seed"] == seed and r["is_old"]]
            if len(rows) == 3:
                per_seed.append({"seed": seed,
                                 "old_net_drop": mean(r["joint"]["net_drop"] for r in rows),
                                 "old_answer_net_drop": mean(r["final"]["net_drop"] for r in rows)})
        summary.append({"order": order, "seeds": per_seed,
                        "mean_old_net_drop": mean(r["old_net_drop"] for r in per_seed) if per_seed else None,
                        "positive_seeds": sum(r["old_net_drop"] > 0 for r in per_seed)})
    write_json(OUT / "historical_summary.json", {"records": records, "orders": summary})
    lines = ["# Historical transition audit", "", "Both endpoints evaluated with identical batch protocol.", "",
             "| Order | Seed | Tool | Old | Before | After | Lost | Gained | Joint before | Joint after |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in records:
        a, j = r["final"], r["joint"]
        lines.append(f"| {r['order']} | {r['seed']} | {r['family']} | {r['is_old']} | {a['before']:.3f} | {a['after']:.3f} | {a['lost']} | {a['gained']} | {j['before']:.3f} | {j['after']:.3f} |")
    (OUT / "historical_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("HISTORICAL SUMMARY", summary, flush=True)


def freeze(order):
    data = ROOT / "data_replay_study"
    manifest = data / "manifest.json"
    if not manifest.exists():
        raise FileNotFoundError(manifest)
    protocol = {
        "created_at": now_iso(), "version": 2, "order": order, "seeds": SEEDS, "modes": MODES,
        "shared_prefix": "One measured prefix per seed; every arm restores the same persisted midpoint adapter, optimizer, scaler, and RNG state.",
        "v1_invalidated_reason": "Midpoint parameters differed across arms before any replay; no efficacy claims from v1.",
        "branch_stage": 3, "new_stage": 4, "replay_ratio_to_new_input_tokens": .1,
        "uniform_floor": .2, "monitor_at_new_exposure_fractions": [0, .5],
        "replay_only_after_midpoint": True, "evaluation_batch_size": 32,
        "primary_outcome": "macro-average joint success on three old tools",
        "secondary_outcomes": ["new-tool joint success", "answer success", "paired loss/gain", "cost"],
        "probe_signal": "nonnegative decrease of joint success from branch start to midpoint",
        "sealed_test_used_for_policy_selection": False,
        "transition_selection": "Historical tests only; this is an exploratory pilot.",
        "source_sha256": {str(p.relative_to(ROOT)): sha256_file(p) for p in [
            ROOT / "fac_tinyagent" / "replay_train.py",
            ROOT / "fac_tinyagent" / "research_data.py",
            ROOT / "fac_tinyagent" / "sft" / "evaluate.py",
            ROOT / "fac_tinyagent" / "metrics.py"]},
        "starting_adapter_sha256": {str(seed): sha256_file(checkpoint(order, seed, 3)[2] / "adapter_model.safetensors") for seed in SEEDS},
        "data_manifest_sha256": sha256_file(manifest),
        "data_sha256": {str(p.relative_to(data)): sha256_file(p)
                        for p in sorted(data.rglob("*.jsonl"))},
        "limitations": ["one model, three seeds, simulated tool functions",
                        "family provided; no cross-family routing",
                        "held-out instances/wording, not proven structural OOD"],
    }
    path = OUT / "protocol.json"
    if path.exists():
        existing = read_json(path)
        for key in ("order", "data_manifest_sha256", "data_sha256", "source_sha256", "starting_adapter_sha256"):
            if existing[key] != protocol[key]:
                raise ValueError(f"Frozen protocol mismatch: {key}")
        return existing
    write_json(path, protocol)
    return protocol


def study(order, modes=None, seeds=None):
    from .replay_train import train_replay_stage
    freeze(order)
    data = ROOT / "data_replay_study"
    original = ROOT / "data_phase2"
    for seed in seeds or SEEDS:
        config, base_stage, adapter = checkpoint(order, seed, 3)
        stage = dict(config["stages"][4], index=4)
        old = [s["family"] for s in config["stages"][1:4]]
        for mode in modes or MODES:
            run = OUT / "branches" / f"{order}_seed{seed}_{mode}"
            ckpt = run / "checkpoint"
            if not (ckpt / "train_summary.json").exists():
                write_json(run / "config.json", config)
                train_replay_stage(
                    config=config, stage=stage, train_path=str(original / stage["family"] / "train.jsonl"),
                    old_train_paths={f: str(original / f / "train.jsonl") for f in old},
                    probe_paths={f: str(data / f / "probe.jsonl") for f in old},
                    previous_adapter=str(adapter), output_dir=str(ckpt),
                    db_path=str(data / "fixtures" / "toolbench.db"),
                    calendar_path=str(data / "fixtures" / "calendar.json"),
                    mode=mode, replay_ratio=.1, uniform_floor=.2,
                    prefix_dir=str(OUT / "prefixes" / f"{order}_seed{seed}"))
            # Evaluate only after a branch is trained. Scores never feed its policy.
            evaluate_adapter(config, dict(stage, adapter=str(ckpt)), ckpt,
                             data, "sealed_test", run / "sealed")
        evaluate_adapter(config, base_stage, adapter, data, "sealed_test",
                         OUT / "starting" / f"{order}_seed{seed}")


def study_report():
    protocol = read_json(OUT / "protocol.json")
    order = protocol["order"]
    records = []
    costs = []
    for seed in SEEDS:
        config = config_for(order, seed)
        old = [s["family"] for s in config["stages"][1:4]]
        for mode in MODES:
            run = OUT / "branches" / f"{order}_seed{seed}_{mode}"
            summary_path = run / "checkpoint" / "train_summary.json"
            if summary_path.exists():
                costs.append({"seed": seed, "mode": mode, "summary": read_json(summary_path)})
            for family in FAMILIES:
                p = run / "sealed" / family / "results.jsonl"
                baseline = OUT / "starting" / f"{order}_seed{seed}" / family / "results.jsonl"
                if not p.exists() or not baseline.exists():
                    continue
                before, after = read_jsonl(baseline), read_jsonl(p)
                if len(after) != len(before):
                    continue
                records.append({"seed": seed, "mode": mode, "family": family,
                                "is_old": family in old,
                                "final": paired(before, after),
                                "joint": paired(before, after, "joint_success")})
    rows = []
    for seed in SEEDS:
        for mode in MODES:
            selected = [r for r in records if r["seed"] == seed and r["mode"] == mode]
            if len(selected) != 4:
                continue
            old = [r for r in selected if r["is_old"]]
            new = [r for r in selected if not r["is_old"]][0]
            rows.append({"seed": seed, "mode": mode,
                         "old_joint_before": mean(r["joint"]["before"] for r in old),
                         "old_joint": mean(r["joint"]["after"] for r in old),
                         "old_answer_before": mean(r["final"]["before"] for r in old),
                         "old_answer": mean(r["final"]["after"] for r in old),
                         "new_joint_before": new["joint"]["before"],
                         "new_joint": new["joint"]["after"],
                         "new_answer_before": new["final"]["before"],
                         "new_answer": new["final"]["after"],
                         "old_lost": sum(r["joint"]["lost"] for r in old),
                         "old_gained": sum(r["joint"]["gained"] for r in old)})
    aggregates = []
    for mode in MODES:
        part = [r for r in rows if r["mode"] == mode]
        if part:
            aggregates.append({"mode": mode, "n_seeds": len(part), **{
                key: {"mean": mean(r[key] for r in part),
                      "std": stdev(r[key] for r in part) if len(part) > 1 else None}
                for key in ("old_joint", "old_answer", "new_joint", "new_answer")}})
    comparisons = []
    allocations = []
    for seed in SEEDS:
        by_mode = {r["mode"]: r for r in rows if r["seed"] == seed}
        if len(by_mode) == 3:
            comparisons.append({
                "seed": seed,
                "uniform_minus_none_old_joint": by_mode["uniform"]["old_joint"] - by_mode["none"]["old_joint"],
                "adaptive_minus_none_old_joint": by_mode["adaptive"]["old_joint"] - by_mode["none"]["old_joint"],
                "adaptive_minus_uniform_old_joint": by_mode["adaptive"]["old_joint"] - by_mode["uniform"]["old_joint"],
                "uniform_minus_none_old_answer": by_mode["uniform"]["old_answer"] - by_mode["none"]["old_answer"],
                "adaptive_minus_none_old_answer": by_mode["adaptive"]["old_answer"] - by_mode["none"]["old_answer"],
                "adaptive_minus_uniform_old_answer": by_mode["adaptive"]["old_answer"] - by_mode["uniform"]["old_answer"],
                "adaptive_minus_uniform_new_joint": by_mode["adaptive"]["new_joint"] - by_mode["uniform"]["new_joint"],
                "adaptive_minus_uniform_new_answer": by_mode["adaptive"]["new_answer"] - by_mode["uniform"]["new_answer"]})
        path = OUT / "branches" / f"{order}_seed{seed}_adaptive" / "checkpoint" / "replay_plan.json"
        if path.exists():
            plan = read_json(path)
            allocations.append({"seed": seed, "weights": plan["weights"],
                                "baseline": plan["baseline_probe_scores"],
                                "midpoint": plan["midpoint_probe_scores"],
                                "drops": plan["positive_drops"],
                                "targeting_triggered": any(v > 0 for v in plan["positive_drops"].values()),
                                "tokens_by_family": plan["actual_tokens_by_family"]})
    detection = []
    for item in allocations:
        weights = item["weights"]
        detection.append({
            "seed": item["seed"],
            "targeting_triggered": item["targeting_triggered"],
            "positive_drops": item["drops"],
            "weights": weights,
            "adaptive_equals_uniform_weights": all(
                abs(value - 1.0 / len(weights)) < 1e-12
                for value in weights.values()),
        })
    detection_summary = {
        "seeds_total": len(detection),
        "seeds_targeting": sum(1 for item in detection if item["targeting_triggered"]),
        "all_adaptive_equal_uniform": all(
            item["adaptive_equals_uniform_weights"] for item in detection)
        if detection else None,
    }
    audit = []
    for seed in SEEDS:
        group = [r["summary"] for r in costs if r["seed"] == seed]
        if len(group) != 3:
            continue
        invariant_keys = ["new_order_sha256", "start_trainable_state_sha256",
                          "midpoint_trainable_state_sha256", "new_input_tokens", "new_samples"]
        invariants = {key: len({r[key] for r in group}) == 1 for key in invariant_keys}
        replay = [r for r in group if r["mode"] != "none"]
        budget_gap = abs(replay[0]["replay_input_tokens"] - replay[1]["replay_input_tokens"])
        audit.append({"seed": seed, "invariants": invariants, "all_invariants_pass": all(invariants.values()),
                      "replay_input_token_gap": budget_gap,
                      "replay_gap_fraction_of_budget": budget_gap / replay[0]["budget_input_tokens"]})
    cost_summary = []
    for mode in MODES:
        group = [r["summary"] for r in costs if r["mode"] == mode]
        if group:
            cost_summary.append({"mode": mode, **{key: mean(r[key] for r in group) for key in (
                "new_input_tokens", "replay_input_tokens", "new_supervised_tokens", "replay_supervised_tokens",
                "probe_input_tokens", "probe_generated_tokens", "training_and_overhead_seconds",
                "probe_duration_seconds", "optimizer_steps")}})
            item = cost_summary[-1]
            item["reference_full_flow_seconds"] = mean(r["duration_seconds"] for r in group)
            item["actual_branch_seconds"] = mean(
                r.get("actual_elapsed_seconds", r["duration_seconds"]) for r in group)
            item["shared_prefix_reference_seconds"] = mean(
                r["duration_seconds"] - r.get("actual_elapsed_seconds", r["duration_seconds"])
                for r in group)
            item["reference_probe_seconds"] = mean(r["probe_duration_seconds"] for r in group)
            item["actual_probe_seconds"] = mean(
                r.get("actual_probe_duration_seconds", r["probe_duration_seconds"])
                for r in group)
            item["actual_training_seconds"] = (
                item["actual_branch_seconds"] - item["actual_probe_seconds"])
            item["actual_experiment_seconds"] = item["actual_branch_seconds"]
            item["algorithm_required_monitor_seconds"] = (
                item["reference_probe_seconds"] if mode == "adaptive" else 0.0)
    write_json(OUT / "results.json", {
        "protocol": protocol, "rows": rows, "aggregates": aggregates,
        "paired_comparisons": comparisons, "details": records, "costs": costs,
        "cost_summary": cost_summary, "invariant_audit": audit,
        "adaptive_allocations": allocations, "detection": detection,
        "detection_summary": detection_summary})
    lines = ["# Budgeted old-tool replay pilot", "",
             "Order: %s; completed branches: %d/9." % (order, len(rows)), "",
             "All values are proportions. Joint success requires correct tool, arguments, execution and final answer.", "",
             "## Per-seed results", "",
             "| Seed | Method | Old joint before | Old joint | Old answer before | Old answer | New joint before | New joint | New answer | Old lost | Old gained |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append("| %s | %s | %.4f | %.4f | %.4f | %.4f | %.4f | %.4f | %.4f | %d | %d |" % (
            r["seed"], r["mode"], r["old_joint_before"], r["old_joint"],
            r["old_answer_before"], r["old_answer"], r["new_joint_before"],
            r["new_joint"], r["new_answer"], r["old_lost"], r["old_gained"]))
    lines += ["", "## Paired differences vs no replay", "",
              "| Seed | uniform-none old joint | adaptive-none old joint | adaptive-uniform old joint | uniform-none old answer | adaptive-none old answer | adaptive-uniform new joint |",
              "|---|---|---|---|---|---|---|"]
    for c in comparisons:
        lines.append("| %s | %+.4f | %+.4f | %+.4f | %+.4f | %+.4f | %+.4f |" % (
            c["seed"], c["uniform_minus_none_old_joint"],
            c["adaptive_minus_none_old_joint"],
            c["adaptive_minus_uniform_old_joint"],
            c["uniform_minus_none_old_answer"],
            c["adaptive_minus_none_old_answer"],
            c["adaptive_minus_uniform_new_joint"]))
    lines += ["", "## Monitor detection", "",
              "| Seed | database drop | file drop | python drop | targeting triggered | weights |",
              "|---|---|---|---|---|---|"]
    for item in detection:
        drops = item["positive_drops"]
        weights = item["weights"]
        weight_text = ", ".join("%s=%.3f" % (family, weights[family])
                                for family in sorted(weights))
        lines.append("| %s | %.3f | %.3f | %.3f | %s | %s |" % (
            item["seed"], drops.get("database", 0.0), drops.get("file", 0.0),
            drops.get("python", 0.0), item["targeting_triggered"], weight_text))
    lines += ["", "Adaptive triggered in %d/%d seeds. %s" % (
        detection_summary["seeds_targeting"], detection_summary["seeds_total"],
        "All adaptive plans fell back to uniform weights."
        if detection_summary["all_adaptive_equal_uniform"]
        else "Some adaptive plans differed from uniform.")]
    lines += ["", "## Cost: actual versus reference time", "",
              "| Method | Reference full-flow s | Actual branch s | Shared-prefix reference s | Reference probe s | Actual probe s | Actual training s |",
              "|---|---|---|---|---|---|---|"]
    for r in cost_summary:
        lines.append("| %s | %.1f | %.1f | %.1f | %.1f | %.1f | %.1f |" % (
            r["mode"], r["reference_full_flow_seconds"], r["actual_branch_seconds"],
            r["shared_prefix_reference_seconds"], r["reference_probe_seconds"],
            r["actual_probe_seconds"], r["actual_training_seconds"]))
    lines += ["", "## Cost: tokens", "",
              "| Method | New input | Replay input | New supervised | Replay supervised | Monitor input | Monitor output | Optimizer steps |",
              "|---|---|---|---|---|---|---|---|"]
    for r in cost_summary:
        lines.append("| %s | %.0f | %.0f | %.0f | %.0f | %.0f | %.0f | %.0f |" % (
            r["mode"], r["new_input_tokens"], r["replay_input_tokens"],
            r["new_supervised_tokens"], r["replay_supervised_tokens"],
            r["probe_input_tokens"], r["probe_generated_tokens"],
            r["optimizer_steps"]))
    lines += ["", "Reference full-flow includes the shared prefix. Actual branch is physically executed time; "
              "for replay arms, shared-prefix reference is the reused portion. Actual probe is 0 for replay arms "
              "because prefix probes were not rerun. Monitor tokens are inference tokens; training tokens are separate.",
              "Training/probe cost records, task-level transitions and frozen protocol are in results.json.",
              "Three seeds are exploratory; do not infer significance from pooled task counts."]
    lines += ["", "## Invariant audit", "", "```json", __import__('json').dumps(audit, indent=2), "```", "",
              "Joint success is a strict exact-call metric: semantically equivalent SQL arguments may fail it. Answer success is reported separately.",
              "All arms were monitored to isolate allocation. A deployed uniform/no-replay policy does not require the adaptive monitor."]
    lines += ["", "## Interpretation", "",
              "- Adaptive did not detect a decline in any seed: all midpoint drops are zero, so its weights are uniform and it is not practically distinct from uniform.",
              "- The sealed test does not reproduce the historical degradation: old-tool joint starts at 0.5222 and rises to 0.5426 (none), 0.5500 (uniform), 0.5463 (adaptive), while the historical A-order audit showed a 5.19pp drop on its own test set.",
              "- Replay shows no reliable benefit: uniform is +0.74pp and adaptive +0.37pp over none in old joint; adaptive is -0.37pp vs uniform on average, driven by one seed (-1.11pp). New-tool joint is 0.9167 in all arms.",
              "- Because adaptive equals uniform when no drops are detected, this is a null-signal pilot, not evidence for or against targeted allocation.",
              "- The next step is monitor validation on the historical-like degradation task types, not a larger replay budget."]
    lines += ["", "V2 shares a persisted prefix per seed. Probe times/tokens above are reference costs of that prefix, not repeated physical executions. Actual experimental time is recorded separately; model loading time is outside these training timers."]
    (OUT / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("STUDY AGGREGATES", aggregates, flush=True)


def run_all():
    supplement(["A", "C"])
    historical = read_json(OUT / "historical_summary.json")
    eligible = [r["order"] for r in historical["orders"]
                if r["mean_old_net_drop"] is not None and r["mean_old_net_drop"] > 0
                and r["positive_seeds"] >= 2 and len(r["seeds"]) == 3]
    if not eligible:
        write_json(OUT / "decision.json", {"status": "no_transition_met_exploratory_gate",
                   "historical": historical["orders"], "sealed_scores_used": False})
        print("NO TRANSITION MET GATE; no adaptive superiority claim.", flush=True)
        return
    order = eligible[0]  # A is predeclared first choice, C is the fallback.
    write_json(OUT / "decision.json", {"status": "transition_selected", "order": order,
                                      "eligible_orders": eligible, "sealed_scores_used": False})
    study(order)
    study_report()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["all", "supplement", "historical-report", "freeze", "study", "report"])
    p.add_argument("--orders", nargs="+", default=["A", "C"])
    p.add_argument("--order", default="A")
    p.add_argument("--modes", nargs="+", choices=MODES)
    p.add_argument("--seeds", nargs="+", type=int)
    args = p.parse_args()
    if args.action == "all": run_all()
    elif args.action == "supplement": supplement(args.orders)
    elif args.action == "historical-report": historical_report(args.orders)
    elif args.action == "freeze": freeze(args.order)
    elif args.action == "study": study(args.order, args.modes, args.seeds)
    else: study_report()


if __name__ == "__main__":
    main()
