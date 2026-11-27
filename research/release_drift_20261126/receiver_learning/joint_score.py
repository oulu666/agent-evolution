"""Score the four systems and the stronger control. Hidden labels are used
only here, never in learning.
"""
from learn import equivalent
from joint import decide_row

COMPARED = (
    "lookup_fixed_oracle",
    "autoloc_fixed_oracle",
    "lookup_synthesized_oracle",
    "joint",
)
SPLIT_SYSTEMS = COMPARED[:3]
ALL_METHODS = COMPARED + (
    "strong_control",
    "prebound_lookup_fixed",
    "fixed_replay",
    "all_readable_all_match",
    "all_readable_any_match",
)


def _truth(values, reference, truth_receiver, truth_relation):
    return equivalent(values[truth_receiver], reference, truth_relation)


def _decision(method, row, result, snapshots, truth_relation):
    name = result["name"]
    values = row["after"]
    reference = row["expected"]
    if name == "fixed_replay":
        # Replay uses the labeled truth relation so it is not weakened.
        # The first snapshot of each input is kept as-is, including faults.
        return all(equivalent(left, right, truth_relation)
                   for left, right in zip(values, snapshots[row["input"]], strict=True))
    if name == "all_readable_all_match":
        return all(equivalent(value, reference, truth_relation) for value in values)
    if name == "all_readable_any_match":
        return any(equivalent(value, reference, truth_relation) for value in values)
    if result["abstain"] is not None or not result["pairs"]:
        return None
    return decide_row(values, reference, result["pairs"])


def metrics_for(rows, methods=ALL_METHODS):
    out = {}
    violations = [row for row in rows if row["truth"] is False]
    healthy = [row for row in rows if row["truth"] is True]
    for method in methods:
        def count(subset, value, method=method):
            return sum(row["decisions"][method] is value for row in subset)
        out[method] = {
            "violation_rows": len(violations),
            "healthy_rows": len(healthy),
            "false_release": count(violations, True),
            "correct_block": count(violations, False),
            "violation_deferred": count(violations, None),
            "retention": count(healthy, True),
            "false_block": count(healthy, False),
            "healthy_deferred": count(healthy, None),
        }
    return out


def localization_accuracy(result, truth_receiver, truth_relation):
    positions = list(result.get("positions") or [])
    relations = list(result.get("relations") or [])
    unique_r = result.get("unique_receiver") is True
    unique_o = result.get("unique_relation") is True
    return {
        "positions": positions,
        "relations": relations,
        "abstain": result.get("abstain"),
        "unique_receiver": unique_r,
        "unique_relation": unique_o,
        "receiver_correct": unique_r and positions[0] == truth_receiver,
        "receiver_wrong": unique_r and positions[0] != truth_receiver,
        "relation_correct": unique_o and relations[0] == truth_relation,
        "relation_wrong": unique_o and relations[0] != truth_relation,
        "extra_observations": result.get("extra_observations", 0),
        "note": result.get("note"),
    }


def independent_gain_rows(rows):
    """Violation rows that joint blocks and none of the three split systems block.

    False release and deferral are not correct blocks. Also report whether the
    stronger control already covers the same rows.
    """
    joint_only = []
    vs_strong = []
    for row in rows:
        if row["truth"] is not False:
            continue
        if row["decisions"]["joint"] is not False:
            continue
        split = {name: row["decisions"][name] for name in SPLIT_SYSTEMS}
        if any(value is False for value in split.values()):
            continue
        item = {
            "input": row["input"],
            "version": row["version"],
            "split_decisions": split,
            "strong_control": row["decisions"]["strong_control"],
        }
        joint_only.append(item)
        if row["decisions"]["strong_control"] is not False:
            vs_strong.append(item)
    return {
        "vs_three_split_systems": joint_only,
        "vs_strong_control": vs_strong,
    }


def score_case(public, hidden, systems):
    truth_receiver = hidden["truth_receiver"]
    truth_relation = hidden["truth_relation"]
    snapshots = {}
    for row in public["rows"]:
        snapshots.setdefault(row["input"], row["after"])
    scored = []
    for row in public["rows"]:
        values = row["after"]
        reference = row["expected"]
        truth = _truth(values, reference, truth_receiver, truth_relation)
        decisions = {}
        for name in ALL_METHODS:
            decisions[name] = _decision(systems[name], row, systems[name], snapshots, truth_relation)
        scored.append({
            "input": row["input"],
            "expected": row["expected"],
            "version": row["version"],
            "after": values,
            "seconds": row["seconds"],
            "truth": truth,
            "decisions": decisions,
            "slot_matches_truth_relation": [
                equivalent(value, reference, truth_relation) for value in values
            ],
        })
    accuracy = {
        name: localization_accuracy(result, truth_receiver, truth_relation)
        for name, result in systems.items()
    }
    return {
        "truth_receiver": truth_receiver,
        "truth_relation": truth_relation,
        "accuracy": accuracy,
        "rows": scored,
        "metrics": metrics_for(scored),
        "independent_gain_rows": independent_gain_rows(scored),
    }


def observation_cost(public, systems):
    n_slots = len(public["slots"])
    n_demos = len(public["demos"])
    n_rows = len(public["rows"])
    n_inputs = len({row["input"] for row in public["rows"]})
    costs = {}
    for name, result in systems.items():
        unique = result.get("unique_receiver") is True and result.get("abstain") is None
        extra = result.get("extra_observations", 0)
        if name == "fixed_replay":
            costs[name] = {
                "model_calls": {"build": 0, "run": 0},
                "tool_actions": {"build": n_inputs, "run": n_rows - n_inputs},
                "extra_observations": 0,
                "logical_slot_reads": {
                    "build": n_inputs * n_slots,
                    "run": (n_rows - n_inputs) * n_slots,
                },
            }
            continue
        if name in {"all_readable_all_match", "all_readable_any_match"}:
            costs[name] = {
                "model_calls": {"build": 0, "run": 0},
                "tool_actions": {"build": 0, "run": n_rows},
                "extra_observations": 0,
                "logical_slot_reads": {"build": 0, "run": n_rows * n_slots},
            }
            continue
        if name == "strong_control":
            build_reads = n_demos * 2 * n_slots
            costs[name] = {
                "model_calls": {"build": 0, "run": 0},
                "tool_actions": {"build": n_demos + extra, "run": n_rows},
                "extra_observations": extra,
                "used_all_demo_channels": True,
                "logical_slot_reads": {
                    "build": build_reads,
                    "run": n_rows if unique else 0,
                },
            }
            continue
        build_reads = 0 if name in {"lookup_fixed_oracle", "lookup_synthesized_oracle", "prebound_lookup_fixed"} else n_demos * 2 * n_slots
        costs[name] = {
            "model_calls": {"build": 0, "run": 0},
            "tool_actions": {
                "build": 0 if name in {"lookup_fixed_oracle", "lookup_synthesized_oracle", "prebound_lookup_fixed"} else n_demos + extra,
                "run": n_rows,
            },
            "extra_observations": extra,
            "logical_slot_reads": {
                "build": build_reads,
                "run": n_rows if unique else 0,
            },
        }
    return costs
