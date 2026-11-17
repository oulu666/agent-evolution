"""[ext 2026-11-11] E3 trainer: a verbatim copy of replay_train.train_replay_stage
(generated mechanically, every edit marked "[E3]") with two hooks:
  * plan_override(pools, extra_pools, budget, seed) -> plan  replaces the "targeted" plan
    (used for the Database dose arms and the compute-matched Calendar-only control);
  * extra_replay_family = new stage family -> its own training rows become a replay pool
    (control: extra Calendar-only micro-steps at the same insertion positions, no old-tool replay);
  * require_prefix_reuse -> refuse to train unless the shared midpoint prefix already exists.
Budget-sweep arms do NOT use this module; they call replay_train.train_replay_stage unchanged.
replay_train.py itself is not modified.
"""
from __future__ import annotations

import hashlib
import math
import time
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

from .replay_train import (MODES, _load_checked_rows, _prepare_rows, _probe, _training_state_hash,
                           allocation_weights, assign_to_positions, common_replay_positions,
                           fixed_new_order, load_prefix, make_hybrid_plan, make_replay_plan,
                           save_prefix, validate_probe_separation)
from .utils import (append_jsonl, canonical_json, ensure_dir, gpu_peak_gb,
                    now_iso, set_seed, sha256_file, write_json)


def train_replay_stage_e3(config: Dict[str, Any], stage: Dict[str, Any],
                       train_path: str, old_train_paths: Mapping[str, str],
                       probe_paths: Mapping[str, str], previous_adapter: str,
                       output_dir: str, db_path: str, calendar_path: str,
                       mode: str = "none", replay_ratio: float = 0.1,
                       uniform_floor: float = 0.2,
                       prefix_dir: Optional[str] = None,
                       target_ids: Optional[Mapping[str, Sequence[str]]] = None,
                       target_fraction: float = 0.5,
                       target_family_weights: Optional[Mapping[str, float]] = None,
                       plan_override: Optional[Callable[..., Dict[str, Any]]] = None,
                       extra_replay_family: Optional[str] = None,
                       require_prefix_reuse: bool = False
                       ) -> Dict[str, Any]:
    """Train a fresh branch from an existing adapter and return its audit summary.

    Checkpoint files are saved directly in output_dir.  This is intentionally a
    batch-size-one experiment to keep the new-example exposure invariant exact.
    No final test data are accepted by this training API.
    """
    if mode not in MODES or not math.isfinite(replay_ratio) or replay_ratio < 0:
        raise ValueError("Invalid replay mode or ratio")
    if not 0 <= uniform_floor <= 1:
        raise ValueError("uniform_floor must be in [0, 1]")
    if not old_train_paths or set(old_train_paths) != set(probe_paths):
        raise ValueError("Old training data and probes must cover the same families")
    if stage["family"] in old_train_paths:
        raise ValueError("The new family cannot be an old replay family")
    training = config["training"]
    if int(training["batch_size"]) != 1:
        raise ValueError("This paired experiment requires training.batch_size=1")
    accumulation = int(training["gradient_accumulation_steps"])
    if accumulation < 1:
        raise ValueError("gradient_accumulation_steps must be positive")
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Refusing to overwrite run: %s" % output)
    new_rows = _load_checked_rows(train_path, stage["family"], "new training data")
    old_rows = {f: _load_checked_rows(p, f, "old training data")
                for f, p in sorted(old_train_paths.items())}
    probe_rows = {f: _load_checked_rows(p, f, "probe data")
                  for f, p in sorted(probe_paths.items())}
    training_rows = new_rows + [r for rows in old_rows.values() for r in rows]
    validate_probe_separation(training_rows, probe_rows)

    import torch
    from bitsandbytes.optim import PagedAdamW8bit
    from .sft.dataset import DataCollator
    from .sft.train import _attach_adapter, load_base_model, load_tokenizer
    seed = int(config["seed"])
    epochs = int(training["num_epochs"])
    order = fixed_new_order(len(new_rows), epochs, seed)
    midpoint = len(order) // 2
    if len(order) < 4 or midpoint % accumulation:
        raise ValueError("The midpoint must follow a complete optimizer accumulation window")
    ensure_dir(output)
    set_seed(seed)
    tokenizer = load_tokenizer(config)
    max_length = int(training["max_seq_length"])
    new_data, _ = _prepare_rows(new_rows, tokenizer, max_length, stage["family"])
    old_data, excluded = {}, {}
    for family, rows in old_rows.items():
        old_data[family], excluded[family] = _prepare_rows(
            rows, tokenizer, max_length, family, complete_only=True)
    pools = {}
    for family, rows in old_data.items():
        ids = set((target_ids or {}).get(family, ()))
        pools[family] = [
            dict({k: v for k, v in row.items() if k != "features"},
                 target=row["episode_id"] in ids)
            for row in rows]
    target_families = [family for family in sorted(pools)
                       if any(row.get("target") for row in pools[family])]
    old_features = {f: {r["row_index"]: r["features"] for r in rows}
                    for f, rows in old_data.items()}
    # [E3] extra pool = the new family's own training rows (same features as the new stream)
    extra_pools = {}
    if extra_replay_family is not None:
        if extra_replay_family != stage["family"]:
            raise ValueError("extra_replay_family must be the new stage family")
        old_features[extra_replay_family] = {r["row_index"]: r["features"] for r in new_data}
        extra_pools[extra_replay_family] = [
            dict({k: v for k, v in r.items() if k != "features"}, target=False) for r in new_data]
    total_new_tokens = sum(new_data[i]["input_tokens"] for i in order)
    budget = int(math.floor(total_new_tokens * replay_ratio))
    model, dtype = load_base_model(config)
    model = _attach_adapter(model, config, previous_adapter)
    model.train()
    optimizer = PagedAdamW8bit([p for p in model.parameters() if p.requires_grad],
                              lr=float(training["learning_rate"]))
    scaler = torch.cuda.amp.GradScaler(enabled=dtype == torch.float16)
    collator = DataCollator(tokenizer)
    use_amp = dtype in (torch.bfloat16, torch.float16)
    optimizer.zero_grad(set_to_none=True)
    counters = {"microsteps": 0, "optimizer_steps": 0, "new_samples": 0,
                "replay_samples": 0, "new_input_tokens": 0, "replay_input_tokens": 0,
                "new_supervised_tokens": 0, "replay_supervised_tokens": 0}
    maximum_gpu = gpu_peak_gb()
    started = time.time()
    prefix_metadata = {"seed": seed, "training": training, "lora": config["lora"],
                       "quantization": config["quantization"],
                       "adapter_sha256": sha256_file(Path(previous_adapter) / "adapter_model.safetensors"),
                       "new_sha256": sha256_file(train_path),
                       "old_sha256": {f: sha256_file(p) for f, p in old_train_paths.items()},
                       "probe_sha256": {f: sha256_file(p) for f, p in probe_paths.items()},
                       "order": order, "midpoint": midpoint}
    restored = None
    prefix_reused = bool(prefix_dir and (Path(prefix_dir) / "manifest.json").exists())
    if require_prefix_reuse and not prefix_reused:  # [E3] formal runs must branch from the E4 midpoint
        raise RuntimeError("E3 requires an existing shared prefix at %s" % prefix_dir)
    if prefix_reused:
        restored = load_prefix(prefix_dir, model, optimizer, scaler, prefix_metadata)
        counters.update(restored["counters"])
        probe_start = restored["probes"]["start"]
    else:
        set_seed(seed)  # Import/model initialization must not consume training RNG.
        probe_start = _probe(model, tokenizer, probe_rows, config,
                         {"name": "probe_start", "family": None,
                          "index": int(stage.get("index", 0))},
                         output / "probes" / "start", db_path, calendar_path)
    maximum_gpu = max(maximum_gpu, gpu_peak_gb())
    start_hash = probe_start["trainable_state_sha256"]
    order_ids = [new_rows[i]["episode_id"] for i in order]
    order_hash = hashlib.sha256(canonical_json(order_ids).encode("utf-8")).hexdigest()
    manifest = {
        "mode": mode, "seed": seed, "stage": stage, "previous_adapter": previous_adapter,
        "new_data_sha256": sha256_file(train_path),
        "old_data_sha256": {f: sha256_file(p) for f, p in old_train_paths.items()},
        "probe_data_sha256": {f: sha256_file(p) for f, p in probe_paths.items()},
        "new_episode_order": order_ids, "new_order_sha256": order_hash,
        "new_samples": len(order), "new_input_tokens": total_new_tokens,
        "midpoint_new_samples": midpoint, "replay_ratio": replay_ratio,
        "budget_input_tokens": budget, "uniform_floor": uniform_floor,
        "excluded_replay_episodes": excluded, "start_trainable_state_sha256": start_hash,
    }
    write_json(output / "run_manifest.json", manifest)
    write_json(output / "stage_config.json", {"config": config, **manifest})
    schedule = {}
    plan = None
    probe_midpoint = None
    last_loss = None

    def train_one(features, kind, episode_id, new_position):
        nonlocal maximum_gpu, last_loss
        model.train()
        batch = {k: v.to("cuda") for k, v in collator([features]).items()}
        with torch.autocast(device_type="cuda", dtype=dtype, enabled=use_amp):
            outputs = model(**batch)
            loss = outputs.loss
        if not torch.isfinite(loss):
            raise RuntimeError("Non-finite loss in %s at new position %d" % (kind, new_position))
        scaler.scale(loss / accumulation).backward()
        counters["microsteps"] += 1
        counters[kind + "_samples"] += 1
        input_tokens = int(batch["attention_mask"].sum().item())
        supervised_tokens = int((batch["labels"] != -100).sum().item())
        counters[kind + "_input_tokens"] += input_tokens
        counters[kind + "_supervised_tokens"] += supervised_tokens
        if counters["microsteps"] % accumulation == 0:
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad(set_to_none=True)
            counters["optimizer_steps"] += 1
        last_loss = float(loss.item())
        maximum_gpu = max(maximum_gpu, gpu_peak_gb())
        append_jsonl(output / "training_log.jsonl", {
            "time": now_iso(), "kind": kind, "episode_id": episode_id,
            "new_position": new_position, "microstep": counters["microsteps"],
            "optimizer_steps": counters["optimizer_steps"], "loss": last_loss,
            "input_tokens": input_tokens, "supervised_tokens": supervised_tokens})

    for position, row_index in enumerate(order, 1):
        if prefix_reused and position < midpoint:
            continue
        item = new_data[row_index]
        if not (prefix_reused and position == midpoint):
            train_one(item["features"], "new", item["episode_id"], position)
        if position == midpoint:
            if prefix_reused:
                probe_midpoint = restored["probes"]["midpoint"]
            else:
                probe_midpoint = _probe(
                model, tokenizer, probe_rows, config,
                {"name": "probe_midpoint", "family": None,
                 "index": int(stage.get("index", 0))},
                output / "probes" / "midpoint", db_path, calendar_path)
                if prefix_dir:
                    save_prefix(prefix_dir, model, optimizer, scaler, prefix_metadata, counters,
                                {"start": probe_start, "midpoint": probe_midpoint}, time.time() - started)
                    restored = load_prefix(prefix_dir, model, optimizer, scaler, prefix_metadata)
            if restored is not None and _training_state_hash(model) != restored["parameter_hash"]:
                raise AssertionError("Branch does not start from saved common midpoint")
            maximum_gpu = max(maximum_gpu, gpu_peak_gb())
            baseline = probe_start["scores"]
            halfway = probe_midpoint["scores"]
            drops = {family: max(0.0, baseline[family] - halfway[family])
                     for family in baseline}
            fixed_weights = dict(target_family_weights or {})
            if not fixed_weights and target_families:
                fixed_weights = {family: 1.0 / len(target_families)
                                 for family in target_families}
            adaptive_weights = {family: drops.get(family, 0.0)
                                for family in target_families
                                if drops.get(family, 0.0) > 0}
            total_adaptive = sum(adaptive_weights.values())
            if total_adaptive > 0:
                adaptive_weights = {family: value / total_adaptive
                                    for family, value in adaptive_weights.items()}
            plans = {
                "uniform": make_replay_plan(
                    pools, allocation_weights("uniform", baseline, halfway,
                                               uniform_floor),
                    budget, seed + 104729),
                "targeted": make_hybrid_plan(
                    pools, budget, seed + 104729, target_fraction, fixed_weights),
            }
            if adaptive_weights:
                plans["adaptive"] = make_hybrid_plan(
                    pools, budget, seed + 104729, target_fraction,
                    adaptive_weights)
            else:
                plans["adaptive"] = make_replay_plan(
                    pools, allocation_weights("adaptive", baseline, halfway,
                                               uniform_floor),
                    budget, seed + 104729)
            if plan_override is not None:  # [E3] dose / compute-matched control plans
                plans["targeted"] = plan_override(pools=pools, extra_pools=extra_pools,
                                                  budget=budget, seed=seed + 104729)
            sample_counts = [len(plans[arm]["items"])
                             for arm in ("uniform", "targeted", "adaptive")
                             if plans[arm]["items"]]
            positions = common_replay_positions(
                len(order), midpoint,
                min(sample_counts) if sample_counts else 0,
                min(sample_counts) if sample_counts else 0, accumulation)
            if mode == "none":
                plan = make_replay_plan(pools, allocation_weights("none", baseline, halfway),
                                        0, seed + 104729)
            else:
                plan = plans[mode]
                schedule = (assign_to_positions(plan["items"], positions)
                            if plan["items"] else {})
            plan.update({
                "mode": mode, "baseline_probe_scores": baseline,
                "midpoint_probe_scores": halfway,
                "positive_drops": drops,
                "adaptive_triggered": bool(adaptive_weights) if mode == "adaptive" else False,
                "target_fraction": plan.get("target_fraction", 0.0),
                "target_family_weights": plan.get("target_family_weights", {}),
                "common_replay_positions": positions,
                "insertion_schedule": {str(k): v for k, v in schedule.items()},
                "uniform_actual_input_tokens": plan.get(
                    "uniform_actual_input_tokens",
                    plans["uniform"]["actual_input_tokens"]),
                "adaptive_actual_input_tokens": plans["adaptive"]["actual_input_tokens"],
                "targeted_actual_input_tokens": plans["targeted"]["actual_input_tokens"],
                "between_replay_arms_budget_difference": abs(
                    plans["uniform"]["actual_input_tokens"] - plans["adaptive"]["actual_input_tokens"]),
            })
            write_json(output / "replay_plan.json", plan)
        for replay in schedule.get(position, []):
            train_one(old_features[replay["family"]][replay["row_index"]],
                      "replay", replay["episode_id"], position)
    remainder = counters["microsteps"] % accumulation
    if remainder:
        # Make the final partial window a mean over its actual microbatches.
        for parameter in model.parameters():
            if parameter.grad is not None:
                parameter.grad.mul_(accumulation / remainder)
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad(set_to_none=True)
        counters["optimizer_steps"] += 1
    if counters["new_input_tokens"] != total_new_tokens:
        raise AssertionError("New-data exposure changed")
    if counters["replay_input_tokens"] != plan["actual_input_tokens"]:
        raise AssertionError("Replay plan and training diverged")
    model.save_pretrained(str(output))
    tokenizer.save_pretrained(str(output))
    elapsed = time.time() - started
    actual_elapsed = elapsed
    if prefix_reused:
        elapsed += restored["duration_seconds"]
    probe_seconds = probe_start["duration_seconds"] + probe_midpoint["duration_seconds"]
    summary = {
        "stage": stage["name"], "family": stage["family"], "mode": mode,
        "seed": seed, "previous_adapter": previous_adapter,
        "epochs": epochs, "train_samples": len(new_rows),
        "new_order_sha256": order_hash, "new_data_sha256": manifest["new_data_sha256"],
        "probe_data_sha256": manifest["probe_data_sha256"],
        "start_trainable_state_sha256": start_hash,
        "midpoint_trainable_state_sha256": probe_midpoint["trainable_state_sha256"],
        "train_tokens": counters["new_input_tokens"] + counters["replay_input_tokens"],
        "steps": counters["microsteps"], "last_loss": last_loss, **counters,
        "replay_ratio_requested": replay_ratio,
        "replay_ratio_actual": counters["replay_input_tokens"] / total_new_tokens,
        "budget_input_tokens": budget, "budget_unused_input_tokens": budget - counters["replay_input_tokens"],
        "quota_error_tokens_by_family": plan["quota_error_tokens_by_family"],
        "within_one_percent_of_budget": plan["within_one_percent_of_budget"] if mode != "none" else None,
        "actual_replay_tokens_by_family": plan["actual_tokens_by_family"],
        "adaptive_triggered": bool(adaptive_weights) if mode == "adaptive" else False,
        "target_fraction": plan.get("target_fraction", 0.0),
        "target_family_weights": plan.get("target_family_weights", {}),
        "target_samples_by_family": plan.get("target_samples_by_family", {}),
        "target_actual_input_tokens": plan.get("target_actual_input_tokens", 0),
        "uniform_actual_input_tokens": plan.get("uniform_actual_input_tokens", 0),
        "peak_gpu_gb": maximum_gpu, "compute_dtype": str(dtype),
        "duration_seconds": round(elapsed, 3), "probe_duration_seconds": round(probe_seconds, 3),
        "actual_elapsed_seconds": round(actual_elapsed, 3), "prefix_reused": prefix_reused,
        "shared_prefix_path": prefix_dir,
        "shared_prefix_state_sha256": (sha256_file(Path(prefix_dir) / "training_state.pt") if prefix_dir else None),
        "actual_probe_duration_seconds": 0.0 if prefix_reused else round(probe_seconds, 3),
        "probe_cost_basis": "reference cost of common prefix; actual elapsed/probe time recorded separately",
        "training_and_overhead_seconds": round(elapsed - probe_seconds, 3),
        "probe_input_tokens": probe_start["input_tokens"] + probe_midpoint["input_tokens"],
        "probe_generated_tokens": probe_start["generated_tokens"] + probe_midpoint["generated_tokens"],
        "probe_episodes": probe_start["episodes"] + probe_midpoint["episodes"],
        "probes": {"start": probe_start, "midpoint": probe_midpoint},
        "partial_accumulation_microsteps": remainder,
        "completed": True,
    }
    write_json(output / "train_summary.json", summary)
    print("replay train done", mode, "new tokens", total_new_tokens,
          "replay tokens", counters["replay_input_tokens"], "seconds", round(elapsed, 2), flush=True)
    return summary
