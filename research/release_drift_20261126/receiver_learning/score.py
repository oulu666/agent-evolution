"""Freeze one check from healthy demos, then score baselines on later rows.

`truth_receiver` labels the real delivery slot for scoring only. Selection does
not read it. `lookup_action` is read only by the lookup baseline.
"""
from baselines import lookup_positions, metrics
from learn import equivalent, select
from oracle import parses_json, synthesize_oracle


def _one(values, reference, relation, positions):
    if relation is None or len(positions) != 1:
        return None
    return equivalent(values[positions[0]], reference, relation)


def score_study(demos, rows, requirement, truth_receiver, lookup_action):
    sources = [demo["expected"] for demo in demos]
    oracle = synthesize_oracle(requirement, sources)
    relation = oracle["relation"]
    if relation is None:
        learned, after_only = [], []
    else:
        learned = select(demos, relation, True)
        after_only = select(demos, relation, False)
    lookup_slots = lookup_positions(lookup_action)
    snapshots = {}
    for row in rows:
        snapshots.setdefault(row["input"], row["after"])
    scored = []
    for row in rows:
        reference = row["expected"]
        values = row["after"]
        source_ok = relation != "parsed_value" or parses_json(reference)
        if relation is None or not source_ok:
            decisions = {name: None for name in (
                "learned", "after_only", "lookup", "fixed_replay",
                "all_readable_all_match", "all_readable_any_match")}
            flags = None
            truth = None
            row_note = None if relation is None else "source_incompatible"
        else:
            flags = [equivalent(value, reference, relation) for value in values]
            decisions = {
                "learned": _one(values, reference, relation, learned),
                "after_only": _one(values, reference, relation, after_only),
                "lookup": _one(values, reference, relation, lookup_slots),
                "fixed_replay": all(equivalent(left, right, relation)
                                    for left, right in zip(values, snapshots[row["input"]], strict=True)),
                "all_readable_all_match": all(flags),
                "all_readable_any_match": any(flags),
            }
            truth = equivalent(values[truth_receiver], reference, relation)
            row_note = None
        item = dict(row)
        item["truth"] = truth
        item["decisions"] = decisions
        item["slot_matches"] = flags
        item["row_note"] = row_note
        scored.append(item)
    return {
        "oracle": oracle,
        "slots_learned": learned,
        "slots_after_only": after_only,
        "lookup_action": lookup_action,
        "lookup_slots": lookup_slots,
        "truth_receiver": truth_receiver,
        "receiver": truth_receiver,
        "demos": demos,
        "rows": scored,
        "metrics": metrics(scored),
    }


def logical_slot_reads(n_slots, n_demos, n_rows, n_inputs, learned_unique, after_unique, lookup_hit):
    """Counts implied by each rule. The study still read every slot on every shared action."""
    return {
        "learned": {"build": n_demos * 2 * n_slots, "run": n_rows if learned_unique else 0},
        "after_only": {"build": n_demos * n_slots, "run": n_rows if after_unique else 0},
        "lookup": {"build": 0, "run": n_rows if lookup_hit else 0},
        "fixed_replay": {"build": n_inputs * n_slots, "run": (n_rows - n_inputs) * n_slots},
        "all_readable_all_match": {"build": 0, "run": n_rows * n_slots},
        "all_readable_any_match": {"build": 0, "run": n_rows * n_slots},
    }


def observation_cost(demos, rows, learned, after_only, lookup_slots):
    n_slots = len(demos[0]["after"])
    n_inputs = len({row["input"] for row in rows})
    return {
        "model_calls": {"build": 0, "run": 0},
        "tool_actions": {"build": len(demos), "run": len(rows)},
        "observation_seconds": {
            "build": sum(demo["seconds"] for demo in demos),
            "run": sum(row["seconds"] for row in rows),
        },
        "logical_slot_reads": logical_slot_reads(
            n_slots, len(demos), len(rows), n_inputs,
            len(learned) == 1, len(after_only) == 1, len(lookup_slots) == 1),
    }
