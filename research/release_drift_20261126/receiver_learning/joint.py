"""Joint Receiver–Oracle learning: maintain H = {(r, o)} and pick observations
by whether they can improve the eventual release decision.

The algorithm never reads a fault location, a version label, or the scorer's
(r, o). Relations stay in the frozen closed set byte / full_string / parsed_value.
"""
from learn import equivalent
from joint_oracle import RELATIONS, compile_task_structure

# Ranks used only to compare observation value for the release decision.
RANK_EMPTY = -1
RANK_RECEIVER_OPEN = 0
RANK_RELATION_OPEN = 1
RANK_DETERMINED = 2


def pair_key(pair):
    receiver, relation = pair
    return [receiver, relation]


def hypothesis_set(pairs):
    return {(int(receiver), str(relation)) for receiver, relation in pairs}


def consistent_with_demo(demo, receiver, relation):
    after = demo["after"][receiver]
    before = demo["before"][receiver]
    expected = demo["expected"]
    return equivalent(after, expected, relation) and not equivalent(before, expected, relation)


def allowed_receivers(slots, structure):
    allowed = structure.get("allowed_slot_types") or ()
    excluded = set(structure.get("excluded_slot_types") or ())
    indices = list(range(len(slots)))
    if not allowed:
        return [index for index in indices if slots[index]["type"] not in excluded]
    return [
        index for index in indices
        if slots[index]["type"] in allowed and slots[index]["type"] not in excluded
    ]


def initial_H(demos, slots, requirement):
    sources = [demo["expected"] for demo in demos]
    structure = compile_task_structure(requirement, sources, slots)
    receivers = allowed_receivers(slots, structure)
    pairs = []
    for receiver in receivers:
        for relation in RELATIONS:
            if all(consistent_with_demo(demo, receiver, relation) for demo in demos):
                pairs.append((receiver, relation))
    return pairs, structure


def refine_by_consumer_slot(pairs, slot):
    return [(receiver, relation) for receiver, relation in pairs if receiver == slot]


def refine_by_canary(pairs, overlays, consumer):
    hits = [index for index, canary in overlays.items() if consumer == canary]
    if len(hits) != 1:
        return []
    return refine_by_consumer_slot(pairs, hits[0])


def receivers_of(pairs):
    return tuple(sorted({receiver for receiver, _ in pairs}))


def relations_of(pairs):
    return tuple(sorted({relation for _, relation in pairs}))


def decision_rank(pairs):
    """How determined a release decision can be from remaining hypotheses.

    Multiple relations at one receiver are 'relation_open': a later row may
    still force a deferral if those relations disagree. Distinct receivers are
    'receiver_open': rows that corrupt only one candidate will disagree.
    """
    if not pairs:
        return RANK_EMPTY
    if len(receivers_of(pairs)) > 1:
        return RANK_RECEIVER_OPEN
    if len(relations_of(pairs)) > 1:
        return RANK_RELATION_OPEN
    return RANK_DETERMINED


def decide_row(values, reference, pairs):
    """Release only when every remaining (r, o) agrees; otherwise defer."""
    if not pairs:
        return None
    votes = [equivalent(values[receiver], reference, relation) for receiver, relation in pairs]
    if all(votes):
        return True
    if not any(votes):
        return False
    return None


def canaries_for(pairs, expected):
    return {receiver: f"CANARY-{receiver}:{expected}" for receiver in receivers_of(pairs)}


def _value_record(kind, current_rank, outcome_ranks, note=None):
    """Value is about the release decision, not about how many outputs change."""
    improving = [rank for rank in outcome_ranks if rank > current_rank]
    determining = [rank for rank in outcome_ranks if rank == RANK_DETERMINED]
    return {
        "kind": kind,
        "current_rank": current_rank,
        "outcome_ranks": list(outcome_ranks),
        "can_improve_decision": len(improving) > 0,
        "can_determine": len(determining) > 0,
        "n_improving_outcomes": len(improving),
        "mean_outcome_rank": (sum(outcome_ranks) / len(outcome_ranks)) if outcome_ranks else current_rank,
        "max_outcome_rank": max(outcome_ranks) if outcome_ranks else current_rank,
        "note": note,
    }


def score_observations(pairs, demos):
    """Score legal next observations by release-decision value only.

    Re-reading a slot already present in the demonstrations cannot split H.
    Overlaying more canaries changes more outputs but does not outrank a
    consumer-read that induces the same partition of H.
    """
    current = decision_rank(pairs)
    reports = []
    if not pairs or current == RANK_DETERMINED:
        return current, reports

    read_ranks = []
    for receiver in receivers_of(pairs):
        residual = refine_by_consumer_slot(pairs, receiver)
        read_ranks.append(decision_rank(residual))
    reports.append(_value_record("subsequent_reads", current, read_ranks,
                                 note="partition_by_consumed_slot"))

    canary_ranks = list(read_ranks)
    reports.append(_value_record("contrast_canaries", current, canary_ranks,
                                 note="same_partition_as_consumer_read"))

    # A no-new-information action: re-read a known demonstration slot.
    reports.append(_value_record("reread_known_slot", current, [current],
                                 note="demo_channels_already_observed"))
    return current, reports


def choose_observation(pairs, demos):
    current, reports = score_observations(pairs, demos)
    if current == RANK_DETERMINED or not pairs:
        return {"action": "stop", "rank": current, "scores": reports, "chosen": None}
    useful = [item for item in reports if item["can_improve_decision"] and item["kind"] != "reread_known_slot"]
    if not useful:
        # Unique receiver with several still-open relations: freeze the receiver
        # and defer later only if those relations disagree. That is a stop, not
        # a localization failure. Abstain only when the receiver is still open.
        action = "stop" if current == RANK_RELATION_OPEN else "abstain"
        return {"action": action, "rank": current, "scores": reports, "chosen": None}
    # Prefer the higher mean decision rank; break ties toward the less
    # invasive subsequent_reads rather than the canary that mutates more slots.
    preferred = ("subsequent_reads", "contrast_canaries")
    useful.sort(key=lambda item: (-item["mean_outcome_rank"], -item["can_determine"], preferred.index(item["kind"]) if item["kind"] in preferred else 99))
    chosen = useful[0]
    return {"action": chosen["kind"], "rank": current, "scores": reports, "chosen": chosen}


def apply_observation(pairs, action, observer, demos):
    input_name = demos[0]["input"]
    if action == "subsequent_reads":
        events = observer.subsequent_reads(input_name)
        reads = [event["slot"] for event in events if event.get("op") == "consumer_read"]
        if not reads:
            return [], "no_subsequent_read", {"events": "empty_or_no_consumer_read"}
        if len(set(reads)) != 1:
            return [], "ambiguous_consumer_read", {"slots": sorted(set(reads))}
        residual = refine_by_consumer_slot(pairs, reads[0])
        if not residual:
            return [], "consumer_slot_inconsistent", {"slot": reads[0]}
        return residual, None, {"consumer_slot": reads[0]}
    if action == "contrast_canaries":
        overlays = canaries_for(pairs, demos[0]["expected"])
        consumer = observer.contrast_canaries(input_name, overlays)
        residual = refine_by_canary(pairs, overlays, consumer)
        if not residual:
            return [], "canary_inconsistent", None
        return residual, None, {"consumer_slot": residual[0][0]}
    raise ValueError(action)


def learn_joint(demos, slots, requirement, observer, budget=1, force_observation=None, always_observe=False):
    """Learn a check by eliminating H. Observations are optional and budgeted.

    always_observe: used by the stronger control, which is allowed to take the
    consumer-read even if a heuristic might skip it. It still cannot see the
    scorer's (r, o). force_observation is for tests only.
    """
    pairs, structure = initial_H(demos, slots, requirement)
    extra = 0
    notes = []
    choice = choose_observation(pairs, demos)
    planned = force_observation or choice["action"]
    if always_observe and decision_rank(pairs) != RANK_DETERMINED and "subsequent_reads" in {item["kind"] for item in choice["scores"] if item["can_improve_decision"]}:
        planned = "subsequent_reads"
    if planned in {"subsequent_reads", "contrast_canaries"}:
        if budget < 1 and not always_observe:
            notes.append("budget_exhausted")
            planned = "abstain"
        else:
            pairs, abstain, detail = apply_observation(pairs, planned, observer, demos)
            extra = 1
            notes.append(planned)
            if detail:
                notes.append(detail)
            if abstain is not None:
                return {
                    "pairs": pairs,
                    "abstain": abstain,
                    "structure": structure,
                    "extra_observations": extra,
                    "choice": choice,
                    "notes": notes,
                    "rank": decision_rank(pairs),
                }
            choice_after = choose_observation(pairs, demos)
            choice = {**choice, "after": choice_after}
    rank = decision_rank(pairs)
    abstain = None
    if not pairs:
        abstain = "no_consistent_pair"
    elif rank in {RANK_RECEIVER_OPEN, RANK_EMPTY}:
        abstain = "ambiguous_hypotheses"
    # relation_open and determined both freeze a usable (possibly multi-relation)
    # check: decide_row defers later if the remaining relations disagree.
    return {
        "pairs": pairs,
        "abstain": abstain,
        "structure": structure,
        "extra_observations": extra,
        "choice": choice,
        "notes": notes,
        "rank": rank,
    }


def learned_positions(result):
    if result["abstain"] is not None:
        return []
    receivers = receivers_of(result["pairs"])
    return list(receivers)


def learned_relations(result):
    if result["abstain"] is not None:
        return []
    return list(relations_of(result["pairs"]))
