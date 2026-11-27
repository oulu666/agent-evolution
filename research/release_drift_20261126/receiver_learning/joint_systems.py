"""The four compared systems, the stronger all-channel control, and replay.

None of these functions receive a truth receiver, a truth relation, or a
version label. Pre-bound LOOKUP is reported separately and is not the fair
unseen-workflow baseline.
"""
from baselines import lookup_positions
from learn import select
from oracle import synthesize_oracle
from joint import (
    decision_rank,
    learn_joint,
    receivers_of,
    relations_of,
)
from joint_baselines import transferable_lookup_positions
from joint_oracle import compile_task_structure, fixed_oracle
from joint_world import EXTRA_BUDGET, HealthyObserver


def _record(name, pairs, abstain, extra, note=None, relation=None, positions=None):
    pairs = list(pairs or [])
    if positions is None:
        positions = list(receivers_of(pairs)) if abstain is None else []
    if relation is None:
        rels = list(relations_of(pairs)) if abstain is None else []
        relation = rels[0] if len(rels) == 1 else None
        relations = rels
    else:
        relations = [relation] if relation is not None else []
    unique_r = abstain is None and len(positions) == 1
    unique_o = abstain is None and len(relations) == 1
    return {
        "name": name,
        "pairs": pairs,
        "positions": positions,
        "relations": relations,
        "relation": relation,
        "abstain": abstain,
        "extra_observations": extra,
        "unique_receiver": unique_r,
        "unique_relation": unique_o,
        "rank": decision_rank(pairs) if pairs else None,
        "note": note,
    }


def lookup_fixed_oracle(public):
    """System 1: transferable lookup + conventional fixed relation."""
    requirement = public["requirement"]
    slots = public["slots"]
    action = public["action"]
    positions = transferable_lookup_positions(requirement, slots, action)
    oracle = fixed_oracle(requirement, action)
    if len(positions) != 1 or oracle["relation"] is None:
        abstain = "lookup_or_oracle_not_unique" if len(positions) != 1 else oracle["abstain"]
        return _record("lookup_fixed_oracle", [], abstain, 0,
                       note="transferable_lookup", relation=oracle["relation"],
                       positions=positions if len(positions) == 1 else [])
    pairs = [(positions[0], oracle["relation"])]
    return _record("lookup_fixed_oracle", pairs, None, 0,
                   note="transferable_lookup", relation=oracle["relation"])


def _auto_localize(public, relation, observer, budget=EXTRA_BUDGET):
    """Strong automatic localizer given a single relation: select, type
    constraints, then one consumer-read if still ambiguous.
    """
    demos = public["demos"]
    slots = public["slots"]
    requirement = public["requirement"]
    if relation is None:
        return [], "no_relation", 0, "no_relation"
    candidates = select(demos, relation, True)
    structure = compile_task_structure(
        requirement, [demo["expected"] for demo in demos], slots)
    allowed = set(structure["allowed_slot_types"] or [])
    excluded = set(structure["excluded_slot_types"] or [])
    if allowed:
        candidates = [
            index for index in candidates
            if slots[index]["type"] in allowed and slots[index]["type"] not in excluded
        ]
    if len(candidates) == 1:
        return candidates, None, 0, "select_and_type"
    if len(candidates) == 0:
        return [], "no_candidate", 0, "select_and_type"
    if budget < 1:
        return [], "ambiguous_candidates", 0, "budget_exhausted"
    events = observer.subsequent_reads(demos[0]["input"])
    reads = [event["slot"] for event in events if event.get("op") == "consumer_read"]
    hits = [slot for slot in reads if slot in candidates]
    if len(set(hits)) == 1:
        return [hits[0]], None, 1, "consumer_read"
    if not reads:
        return [], "no_subsequent_read", 1, "no_subsequent_read"
    if hits and set(hits).isdisjoint(candidates):
        return [], "consumer_slot_not_in_candidates", 1, "consumer_inconsistent"
    if reads and reads[0] not in candidates:
        return [], "consumer_slot_not_in_candidates", 1, "consumer_inconsistent"
    return [], "ambiguous_candidates", 1, "consumer_not_unique"


def autoloc_fixed_oracle(public, hidden, budget=EXTRA_BUDGET):
    """System 2: automatic localization + conventional fixed relation."""
    oracle = fixed_oracle(public["requirement"], public["action"])
    observer = HealthyObserver(hidden["world"], public["demos"], budget=budget)
    positions, abstain, extra, note = _auto_localize(
        public, oracle["relation"], observer, budget=budget)
    if abstain is not None or oracle["relation"] is None:
        return _record("autoloc_fixed_oracle", [], abstain or oracle["abstain"], extra,
                       note=note, relation=oracle["relation"], positions=positions)
    pairs = [(positions[0], oracle["relation"])]
    result = _record("autoloc_fixed_oracle", pairs, None, extra, note=note,
                     relation=oracle["relation"])
    result["observer_log"] = observer.log
    return result


def lookup_synthesized_oracle(public):
    """System 3: transferable lookup + phrase-table oracle synthesis."""
    requirement = public["requirement"]
    slots = public["slots"]
    action = public["action"]
    positions = transferable_lookup_positions(requirement, slots, action)
    sources = [demo["expected"] for demo in public["demos"]]
    oracle = synthesize_oracle(requirement, sources)
    if len(positions) != 1 or oracle["relation"] is None:
        reasons = []
        if len(positions) != 1:
            reasons.append("lookup_not_unique")
        if oracle["relation"] is None:
            reasons.append(oracle["abstain"] or "oracle_refused")
        abstain = "+".join(reasons)
        return _record("lookup_synthesized_oracle", [], abstain, 0,
                       note="transferable_lookup_plus_phrase_table",
                       relation=oracle["relation"],
                       positions=positions if len(positions) == 1 else [])
    pairs = [(positions[0], oracle["relation"])]
    return _record("lookup_synthesized_oracle", pairs, None, 0,
                   note="transferable_lookup_plus_phrase_table",
                   relation=oracle["relation"])


def joint_system(public, hidden, budget=EXTRA_BUDGET):
    """System 4: joint H = {(r, o)} learning with decision-value observations."""
    observer = HealthyObserver(hidden["world"], public["demos"], budget=budget)
    learned = learn_joint(
        public["demos"], public["slots"], public["requirement"], observer, budget=budget)
    result = _record(
        "joint", learned["pairs"], learned["abstain"], learned["extra_observations"],
        note=learned.get("notes"))
    result["choice"] = learned["choice"]
    result["structure"] = {
        "allowed_slot_types": learned["structure"]["allowed_slot_types"],
        "excluded_slot_types": learned["structure"]["excluded_slot_types"],
        "compatible_slots": learned["structure"]["compatible_slots"],
        "abstain": learned["structure"]["abstain"],
        "relation": learned["structure"]["relation"],
    }
    result["observer_log"] = observer.log
    result["rank"] = learned["rank"]
    return result


def strong_control(public, hidden, budget=EXTRA_BUDGET):
    """Stronger control: all demo channels plus a downstream consumer read.

    Same task text, same closed relation set. It may inspect every channel
    already present in the demonstrations and always take a subsequent read
    when H is not yet determined. It does not read the scorer's (r, o).
    """
    observer = HealthyObserver(
        hidden["world"], public["demos"], budget=budget, unlimited=True)
    learned = learn_joint(
        public["demos"], public["slots"], public["requirement"], observer,
        budget=budget, always_observe=True)
    result = _record(
        "strong_control", learned["pairs"], learned["abstain"], learned["extra_observations"],
        note=["all_channels_and_downstream"] + list(learned.get("notes") or []))
    result["choice"] = learned["choice"]
    result["observer_log"] = observer.log
    result["rank"] = learned["rank"]
    result["used_all_demo_channels"] = True
    return result


def prebound_lookup_fixed(public, hidden):
    """Known-task pre-bound lookup, not a fair unseen-workflow baseline."""
    positions = lookup_positions(public["action"])
    oracle = fixed_oracle(public["requirement"], public["action"])
    if len(positions) != 1 or oracle["relation"] is None:
        return _record("prebound_lookup_fixed", [], "unbound_workflow", 0,
                       note="prebound", relation=oracle["relation"])
    return _record("prebound_lookup_fixed", [(positions[0], oracle["relation"])], None, 0,
                   note="prebound", relation=oracle["relation"])


def replay_pairs(public, hidden):
    """Fixed replay does not localize. Decision is computed in the scorer."""
    return _record("fixed_replay", [], "not_a_localizer", 0, note="fixed_replay")


def all_readable_record(name):
    return _record(name, [], "not_a_localizer", 0, note=name)


def run_systems(public, hidden, budget=EXTRA_BUDGET):
    return {
        "lookup_fixed_oracle": lookup_fixed_oracle(public),
        "autoloc_fixed_oracle": autoloc_fixed_oracle(public, hidden, budget=budget),
        "lookup_synthesized_oracle": lookup_synthesized_oracle(public),
        "joint": joint_system(public, hidden, budget=budget),
        "strong_control": strong_control(public, hidden, budget=budget),
        "prebound_lookup_fixed": prebound_lookup_fixed(public, hidden),
        "fixed_replay": replay_pairs(public, hidden),
        "all_readable_all_match": all_readable_record("all_readable_all_match"),
        "all_readable_any_match": all_readable_record("all_readable_any_match"),
    }
