"""One-stage, paired replay experiment; imports remain usable without a GPU.

All arms consume exactly the same new-example sequence.  Replay is confined to
the second half, with one allocation decision made from independent probes at
the start and midpoint.  The optimizer is never recreated at the midpoint.
"""
from __future__ import annotations

import hashlib
import math
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set

from .utils import (append_jsonl, canonical_json, ensure_dir, gpu_peak_gb,
                    now_iso, read_json, read_jsonl, set_seed, sha256_file, write_json)


def save_prefix(path, model, optimizer, scaler, metadata, counters, probes, duration):
    import torch
    import numpy as np
    path = ensure_dir(path)
    state = {
        "parameters": {n: p.detach().cpu().clone() for n, p in model.named_parameters() if p.requires_grad},
        "optimizer": optimizer.state_dict(), "scaler": scaler.state_dict(),
        "python_rng": random.getstate(), "numpy_rng": np.random.get_state(),
        "torch_rng": torch.get_rng_state(), "cuda_rng": torch.cuda.get_rng_state_all(),
        "counters": dict(counters), "probes": probes, "duration_seconds": duration,
        "parameter_hash": _training_state_hash(model),
    }
    torch.save(state, path / "training_state.pt")
    write_json(path / "manifest.json", {"metadata": metadata,
               "state_sha256": sha256_file(path / "training_state.pt"),
               "parameter_hash": state["parameter_hash"]})


def load_prefix(path, model, optimizer, scaler, metadata):
    import torch
    import numpy as np
    path = Path(path)
    manifest = read_json(path / "manifest.json")
    if manifest["metadata"] != metadata:
        raise ValueError("Shared prefix metadata mismatch")
    if sha256_file(path / "training_state.pt") != manifest["state_sha256"]:
        raise ValueError("Shared prefix state hash mismatch")
    # This file is created locally by this experiment, never an external checkpoint.
    state = torch.load(path / "training_state.pt", map_location="cpu", weights_only=False)
    required = {"parameters", "optimizer", "scaler", "python_rng", "numpy_rng",
                "torch_rng", "cuda_rng", "counters", "probes", "duration_seconds", "parameter_hash"}
    if not required.issubset(state):
        raise ValueError("Incomplete shared prefix state")
    params = {n: p for n, p in model.named_parameters() if p.requires_grad}
    if set(params) != set(state["parameters"]):
        raise ValueError("Shared prefix parameter names mismatch")
    with torch.no_grad():
        for name, parameter in params.items():
            parameter.copy_(state["parameters"][name].to(parameter.device, dtype=parameter.dtype))
    optimizer.load_state_dict(state["optimizer"])
    # bitsandbytes' integer optimizer state must keep its stored dtype.
    for parameter, values in optimizer.state.items():
        for key, value in values.items():
            if torch.is_tensor(value):
                values[key] = value.to(parameter.device)
    scaler.load_state_dict(state["scaler"])
    optimizer.zero_grad(set_to_none=True)
    if _training_state_hash(model) != state["parameter_hash"]:
        raise ValueError("Restored midpoint parameters differ")
    random.setstate(state["python_rng"])
    np.random.set_state(state["numpy_rng"])
    torch.set_rng_state(state["torch_rng"])
    torch.cuda.set_rng_state_all(state["cuda_rng"])
    return state


MODES = ("none", "uniform", "targeted", "adaptive")


def fixed_new_order(size: int, epochs: int, seed: int) -> List[int]:
    """A local RNG makes the new stream independent of replay/probe activity."""
    if size < 1 or epochs < 1:
        raise ValueError("New data and epochs must both be nonempty")
    rng = random.Random(seed)
    result = []
    for _ in range(epochs):
        order = list(range(size))
        rng.shuffle(order)
        result.extend(order)
    return result


def allocation_weights(mode: str, baseline: Mapping[str, float],
                       midpoint: Mapping[str, float],
                       uniform_floor: float = 0.2) -> Dict[str, float]:
    if mode not in MODES:
        raise ValueError("Unknown replay mode: %s" % mode)
    if not baseline or set(baseline) != set(midpoint):
        raise ValueError("Start and midpoint probes must cover the same families")
    if not 0.0 <= uniform_floor <= 1.0:
        raise ValueError("uniform_floor must be in [0, 1]")
    families = sorted(baseline)
    for values in (baseline, midpoint):
        if any(not math.isfinite(values[f]) or not 0 <= values[f] <= 1
               for f in families):
            raise ValueError("Probe success rates must be finite values in [0, 1]")
    if mode == "none":
        return {family: 0.0 for family in families}
    drops = {f: max(0.0, baseline[f] - midpoint[f]) for f in families}
    total = sum(drops.values())
    if mode == "uniform" or total == 0:
        return {f: 1.0 / len(families) for f in families}
    return {f: uniform_floor / len(families)
            + (1.0 - uniform_floor) * drops[f] / total for f in families}


def _fill_whole_rows(candidates: Sequence[Dict[str, Any]], limit: int,
                     rng: random.Random) -> List[Dict[str, Any]]:
    """Unbounded integer packing; used only to repair a small greedy suffix."""
    representatives = {}
    shuffled = list(candidates)
    rng.shuffle(shuffled)
    for item in shuffled:
        representatives.setdefault(int(item["input_tokens"]), item)
    coins = list(representatives.items())
    predecessor = [None] * (limit + 1)
    predecessor[0] = (0, None)
    for amount in range(1, limit + 1):
        for tokens, item in coins:
            if tokens <= amount and predecessor[amount - tokens] is not None:
                predecessor[amount] = (amount - tokens, item)
                break
    amount = next(i for i in range(limit, -1, -1)
                  if predecessor[i] is not None)
    result = []
    while amount:
        amount, item = predecessor[amount]
        result.append(dict(item))
    return result


def make_replay_plan(pools: Mapping[str, Sequence[Dict[str, Any]]],
                     weights: Mapping[str, float], budget: int,
                     seed: int) -> Dict[str, Any]:
    """Select complete old episodes with replacement under a hard token cap.

    Pool entries contain family, row_index, episode_id, input_tokens and
    supervised_tokens.  Integer episode sizes make family quotas approximate;
    errors are reported explicitly.  A short packing repair improves utilization
    without truncating a conversation or exceeding the total token budget.
    """
    if budget < 0 or not isinstance(budget, int):
        raise ValueError("budget must be a nonnegative integer")
    if not pools or set(pools) != set(weights):
        raise ValueError("Pool families must equal allocation families")
    if any(not math.isfinite(w) or w < 0 for w in weights.values()):
        raise ValueError("Invalid allocation weights")
    weight_sum = sum(weights.values())
    if weight_sum and not math.isclose(weight_sum, 1.0, abs_tol=1e-8):
        raise ValueError("Nonzero allocation weights must sum to one")
    families = sorted(pools)
    for family in families:
        for item in pools[family]:
            if (item["family"] != family or int(item["input_tokens"]) <= 0
                    or not 0 < int(item["supervised_tokens"]) <= int(item["input_tokens"])):
                raise ValueError("Invalid replay pool entry")
    targets = {f: budget * weights[f] for f in families}
    rng = random.Random(seed)
    plan = []
    actual = {f: 0 for f in families}
    if budget and weight_sum:
        if any(weights[f] > 0 and not pools[f] for f in families):
            raise ValueError("Positive replay quota has no eligible complete episodes")
        for family in families:
            while True:
                remaining = targets[family] - actual[family]
                eligible = [r for r in pools[family]
                            if r["input_tokens"] <= remaining]
                if not eligible:
                    break
                item = dict(rng.choice(eligible))
                plan.append(item)
                actual[family] += item["input_tokens"]
        candidates = [r for f in families if weights[f] > 0 for r in pools[f]]
        # Fill residual capacity while favoring the most underallocated family.
        while True:
            remaining = budget - sum(actual.values())
            eligible = [r for r in candidates if r["input_tokens"] <= remaining]
            if not eligible:
                break
            deficits = {f: targets[f] - actual[f] for f in families}
            best_family = max({r["family"] for r in eligible},
                              key=lambda f: (deficits[f], f))
            item = dict(rng.choice([r for r in eligible if r["family"] == best_family]))
            plan.append(item)
            actual[best_family] += item["input_tokens"]

        def score(rows):
            totals = {f: sum(r["input_tokens"] for r in rows if r["family"] == f)
                      for f in families}
            unused = budget - sum(totals.values())
            quota_error = sum(abs(totals[f] - targets[f]) for f in families)
            # Once within the declared 1% tolerance, prefer faithful allocation
            # over chasing the very last token by changing the family mix.
            return ((0, quota_error, unused) if unused <= budget * 0.01
                    else (1, unused, quota_error))

        # Never remove a family's last selected episode to improve packing:
        # that would erase the intended uniform coverage floor.
        family_counts = {f: sum(r["family"] == f for r in plan) for f in families}
        removable = []
        for index in range(len(plan) - 1, -1, -1):
            family = plan[index]["family"]
            if family_counts[family] > 1:
                removable.append(index)
                family_counts[family] -= 1
            if len(removable) == 4:
                break
        best = list(plan)
        for removed in range(len(removable) + 1):
            excluded_indices = set(removable[:removed])
            prefix = [item for index, item in enumerate(plan) if index not in excluded_indices]
            remaining = budget - sum(r["input_tokens"] for r in prefix)
            repaired = prefix + _fill_whole_rows(candidates, remaining, rng)
            if score(repaired) < score(best):
                best = repaired
        plan = best
        rng.shuffle(plan)
    actual = {f: sum(r["input_tokens"] for r in plan if r["family"] == f)
              for f in families}
    spent = sum(actual.values())
    return {
        "items": plan, "budget_input_tokens": budget,
        "actual_input_tokens": spent,
        "actual_supervised_tokens": sum(r["supervised_tokens"] for r in plan),
        "unused_input_tokens": budget - spent,
        "unused_fraction": (budget - spent) / budget if budget else 0.0,
        "within_one_percent_of_budget": (budget - spent) <= budget * 0.01,
        "weights": dict(weights), "target_tokens_by_family": targets,
        "actual_tokens_by_family": actual,
        "quota_error_tokens_by_family": {f: actual[f] - targets[f] for f in families},
        "samples_by_family": {f: sum(r["family"] == f for r in plan) for f in families},
    }


def make_hybrid_plan(pools: Mapping[str, Sequence[Dict[str, Any]]],
                     budget: int, seed: int, target_fraction: float,
                     target_family_weights: Optional[Mapping[str, float]] = None
                     ) -> Dict[str, Any]:
    """Uniform family coverage plus a targeted fraction of the same budget."""
    if not 0.0 <= target_fraction <= 1.0:
        raise ValueError("target_fraction must be in [0, 1]")
    families = sorted(pools)
    target_pools = {family: [row for row in pools[family] if row.get("target")]
                    for family in families}
    target_families = [family for family in families if target_pools[family]]
    if target_fraction > 0 and not target_families:
        target_fraction = 0.0
    uniform_budget = int(budget * (1.0 - target_fraction))
    uniform_pools = pools
    if target_fraction > 0 and target_families:
        uniform_pools = {family: [row for row in pools[family]
                                  if not row.get("target")]
                         for family in families}
    uniform = make_replay_plan(
        uniform_pools, {family: 1.0 / len(families) for family in families},
        uniform_budget, seed)
    if target_fraction <= 0 or not target_families:
        plan = uniform
        target_plan = None
        target_weights = {}
    else:
        raw = target_family_weights or {
            family: 1.0 / len(target_families) for family in target_families}
        weights = {family: max(0.0, float(raw.get(family, 0.0)))
                   for family in target_families}
        total = sum(weights.values())
        if total <= 0:
            weights = {family: 1.0 / len(target_families)
                       for family in target_families}
        else:
            weights = {family: value / total for family, value in weights.items()}
        target_budget = budget - uniform_budget
        target_plan = make_replay_plan(
            {family: target_pools[family] for family in target_families},
            weights, target_budget, seed + 1)
        seen = set()
        items = []
        for item in uniform["items"] + target_plan["items"]:
            key = (item["family"], item["row_index"], item["episode_id"])
            if key not in seen:
                seen.add(key)
                items.append(item)
        remaining = budget - sum(item["input_tokens"] for item in items)
        if remaining > 0:
            fill_pools = {family: [row for row in pools[family]
                                   if (family, row["row_index"], row["episode_id"])
                                   not in seen]
                          for family in families}
            candidates = [row for family in families for row in fill_pools[family]]
            items.extend(_fill_whole_rows(candidates, remaining,
                                          __import__("random").Random(seed + 3)))
        plan = {
            "items": items, "budget_input_tokens": budget,
            "actual_input_tokens": sum(item["input_tokens"] for item in items),
            "actual_supervised_tokens": sum(item["supervised_tokens"] for item in items),
            "weights": {family: 1.0 / len(families) for family in families},
            "target_family_weights": weights,
            "target_fraction": target_fraction,
            "actual_target_fraction": (
                sum(item["input_tokens"] for item in items if item.get("target"))
                / max(1, sum(item["input_tokens"] for item in items))),
            "uniform_actual_input_tokens": sum(
                item["input_tokens"] for item in items if not item.get("target")),
            "target_actual_input_tokens": sum(
                item["input_tokens"] for item in items if item.get("target")),
            "actual_tokens_by_family": {
                family: sum(item["input_tokens"] for item in items
                            if item["family"] == family)
                for family in families},
            "target_samples_by_family": {
                family: sum(item["family"] == family and item.get("target")
                            for item in items)
                for family in target_families},
            "quota_error_tokens_by_family": {family: 0 for family in families},
        }
        plan["unused_input_tokens"] = budget - plan["actual_input_tokens"]
        plan["unused_fraction"] = (plan["unused_input_tokens"] / budget
                                   if budget else 0.0)
        plan["within_one_percent_of_budget"] = (
            plan["unused_input_tokens"] <= budget * 0.01)
        plan["samples_by_family"] = {
            family: sum(item["family"] == family for item in items)
            for family in families}
    plan.setdefault("target_fraction", target_fraction)
    plan.setdefault("target_family_weights", {})
    plan.setdefault("uniform_actual_input_tokens", plan["actual_input_tokens"])
    plan.setdefault("target_actual_input_tokens", 0)
    return plan


def common_replay_positions(total_new: int, midpoint: int,
                            uniform_samples: int, adaptive_samples: int,
                            accumulation: int) -> List[int]:
    """Identical insertion positions for both arms; a new example follows each.

    Positions count already-consumed new examples, independent of replay length.
    There is no posthoc-only replay tail after the final new example.
    """
    if not 0 < midpoint < total_new or accumulation < 1:
        raise ValueError("Invalid midpoint or accumulation")
    available = total_new - midpoint - 1
    slots = min(uniform_samples, adaptive_samples, available,
                max(1, (total_new - midpoint) // accumulation))
    if slots < 1:
        return []
    return [midpoint + ((i + 1) * available // slots) for i in range(slots)]


def assign_to_positions(items: Sequence[Dict[str, Any]],
                        positions: Sequence[int]) -> Dict[int, List[Dict[str, Any]]]:
    if not positions:
        if items:
            raise ValueError("No common replay positions for a nonempty plan")
        return {}
    if len(items) < len(positions) or sorted(set(positions)) != list(positions):
        raise ValueError("Replay positions must be unique and each receive an episode")
    return {position: list(items[i * len(items) // len(positions):
                                 (i + 1) * len(items) // len(positions)])
            for i, position in enumerate(positions)}


def _training_state_hash(model) -> str:
    import torch
    digest = hashlib.sha256()
    for name, parameter in sorted(model.named_parameters(), key=lambda pair: pair[0]):
        if parameter.requires_grad:
            digest.update(name.encode("utf-8"))
            digest.update(parameter.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes())
    return digest.hexdigest()


def _probe(model, tokenizer, probe_rows, config, stage, output_dir,
           db_path, calendar_path) -> Dict[str, Any]:
    """Use the normal evaluator while preserving optimizer, gradients and RNG."""
    import torch
    from .sft.evaluate import evaluate_family
    stage = dict(stage)
    stage.setdefault("index", 0)
    try:
        import numpy as np
    except ImportError:
        np = None
    python_rng = random.getstate()
    numpy_rng = np.random.get_state() if np is not None else None
    training = model.training
    padding = tokenizer.padding_side
    use_cache = model.config.use_cache
    costs = {"generation_calls": 0, "logical_generation_requests": 0,
             "input_tokens": 0, "generated_tokens": 0}
    started = time.time()
    scores = {}
    state_hash = _training_state_hash(model)
    try:
        devices = [torch.cuda.current_device()] if torch.cuda.is_available() else []
        with torch.random.fork_rng(devices=devices):
            model.eval()
            for family in sorted(probe_rows):
                report = evaluate_family(model, tokenizer, probe_rows[family], config,
                                         stage, Path(output_dir) / family,
                                         db_path, calendar_path)
                scores[family] = report["metrics"]["joint_success_rate"]
                usage = report["inference_usage"]
                costs["generation_calls"] += usage["generation_batches"]
                costs["logical_generation_requests"] += usage["inference_calls"]
                costs["input_tokens"] += usage["input_tokens"]
                costs["generated_tokens"] += usage["output_tokens"]
    finally:
        tokenizer.padding_side = padding
        model.config.use_cache = use_cache
        model.train(training)
        random.setstate(python_rng)
        if np is not None:
            np.random.set_state(numpy_rng)
    if _training_state_hash(model) != state_hash:
        raise AssertionError("Probe evaluation modified trainable model parameters")
    result = {"scores": scores, "score_metric": "joint_success_rate",
              "duration_seconds": round(time.time() - started, 3),
              "episodes": sum(len(rows) for rows in probe_rows.values()),
              "trainable_state_sha256": state_hash, **costs}
    write_json(Path(output_dir) / "probe_summary.json", result)
    return result


def _prepare_rows(rows, tokenizer, max_length, family, complete_only=False):
    from .sft.dataset import conversation_text, tokenize_episode
    prepared, excluded = [], []
    for index, row in enumerate(rows):
        full_length = len(tokenizer.encode(conversation_text(tokenizer, row["messages"]),
                                           add_special_tokens=False))
        if complete_only and full_length > max_length:
            excluded.append({"episode_id": row["episode_id"], "input_tokens": full_length,
                             "reason": "complete_dialogue_exceeds_max_seq_length"})
            continue
        features = tokenize_episode(row, tokenizer, max_length)
        prepared.append({"family": family, "row_index": index,
                         "episode_id": row["episode_id"],
                         "input_tokens": len(features["input_ids"]),
                         "supervised_tokens": sum(token != -100 for token in features["labels"]),
                         "truncated": full_length > max_length, "features": features})
    return prepared, excluded


def _load_checked_rows(path, family, label):
    rows = read_jsonl(path)
    if not rows:
        raise ValueError("Empty %s: %s" % (label, path))
    if any(row["tool_family"] != family for row in rows):
        raise ValueError("Mixed or incorrect family in %s" % path)
    return rows


def validate_probe_separation(training_rows, probe_rows) -> None:
    """Fail before model loading if a monitor can replay an identical episode."""
    training_ids = {r["episode_id"] for r in training_rows}
    training_messages = {canonical_json(r["messages"]) for r in training_rows}
    if any(r["episode_id"] in training_ids or canonical_json(r["messages"]) in training_messages
           for rows in probe_rows.values() for r in rows):
        raise ValueError("Probe episodes overlap the training/replay pool")


def train_replay_stage(config: Dict[str, Any], stage: Dict[str, Any],
                       train_path: str, old_train_paths: Mapping[str, str],
                       probe_paths: Mapping[str, str], previous_adapter: str,
                       output_dir: str, db_path: str, calendar_path: str,
                       mode: str = "none", replay_ratio: float = 0.1,
                       uniform_floor: float = 0.2,
                       prefix_dir: Optional[str] = None,
                       target_ids: Optional[Mapping[str, Sequence[str]]] = None,
                       target_fraction: float = 0.5,
                       target_family_weights: Optional[Mapping[str, float]] = None
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
