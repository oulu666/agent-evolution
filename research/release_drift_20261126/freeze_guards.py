"""Shared pre-freeze controls for blind runs. No case labels or project rules."""

from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from time import perf_counter_ns
from types import MappingProxyType


class BudgetExhausted(Exception):
    pass


OUTCOME_LOSS = MappingProxyType({"correct": 0, "deferred": 1, "wrong": 5})


def expected_task_loss(correct, deferred, wrong):
    """Both planners pass exact probability masses, including terminal deferral."""
    masses = [Fraction(p) for p in (correct, deferred, wrong)]
    if min(masses) < 0 or sum(masses) != 1:
        raise ValueError("outcome probabilities must be nonnegative and sum to one")
    return sum(p * OUTCOME_LOSS[key] for p, key in zip(masses, ("correct", "deferred", "wrong")))


def delivery_change(baseline, method):
    delta = OUTCOME_LOSS[baseline] - OUTCOME_LOSS[method]
    return {"loss_reduction": delta,
            "blocked_by_deferral": baseline == "wrong" and method == "deferred",
            "wrong_to_correct": baseline == "wrong" and method == "correct",
            "new_wrong": baseline != "wrong" and method == "wrong"}


def check_search_parity(preplanned, active):
    """Check registered common settings. Actual search work is logged separately."""
    for settings in (preplanned, active):
        if settings["depth"] != 3 or type(settings["depth"]) is not int:
            raise ValueError("the common horizon is three remaining calls")
        limit = settings["scoring_limit"]
        if limit is not None and (type(limit) is not int or limit <= 0):
            raise ValueError("invalid scoring limit")
    for key in ("task_pack", "candidates", "prior", "transition", "legal_actions",
                "terminal_score", "pruning", "tie_break"):
        if not isinstance(preplanned[key], str) or not preplanned[key] or preplanned[key] != active[key]:
            raise ValueError(f"missing or different search setting: {key}")
    if preplanned["scoring_limit"] != active["scoring_limit"]:
        raise ValueError("different scoring limits")


def _read(document, path):
    if not isinstance(path, (tuple, list)) or not path:
        raise ValueError("expected a nonempty field path")
    for key in path:
        if type(document) is dict and type(key) is str:
            document = document[key]
        elif type(document) is list and type(key) is int and key >= 0:
            document = document[key]
        else:
            raise ValueError("field path does not address the declared structure")
    return document


def contract_value(expression, inputs):
    """Small offline expression vocabulary over public user inputs only."""
    for premise in expression.get("when", []):
        observed = _read(inputs, premise["input"])
        if premise["op"] == "equals":
            required = premise["value"]
            holds = type(observed) is type(required) and observed == required
        elif premise["op"] == "integer_range":
            lower, upper = premise["min"], premise["max"]
            holds = all(type(x) is int for x in (lower, observed, upper)) and lower <= observed <= upper
        else:
            raise ValueError("unsupported registered premise")
        if not holds:
            raise ValueError("registered premise is unsatisfied")
    value = _read(inputs, expression["input"])
    op = expression["op"]
    if op == "integer" and type(value) is int:
        return value
    if op == "length" and isinstance(value, (list, str)):
        return len(value)
    if op == "scale_integer" and type(value) is int and type(expression["factor"]) is int:
        return value * expression["factor"]
    raise ValueError("unsupported expression or input domain")


def direct_delivery(task_id, inputs, expressions):
    """Each entry supplies the full output of one registered scalar task."""
    if task_id not in expressions:
        return "unavailable", None
    try:
        value = contract_value(expressions[task_id], inputs)
    except (KeyError, IndexError, ValueError, TypeError):
        return "unavailable", None
    return "available", value


def transferred_verdict(rule, probe, target):
    """Prove an exact scalar obligation through a registered equality or unit map.

    The trusted runner binds clause, endpoint, snapshot, user inputs and raw
    observed fields. Applicability alone cannot establish a violation.
    """
    if rule["relation"] not in {"equal_quantity", "scaled_quantity"}:
        raise ValueError("unsupported registered implication")
    factor = 1 if rule["relation"] == "equal_quantity" else rule["factor"]
    if type(factor) is not int or factor == 0:
        raise ValueError("unit map needs a nonzero integer factor")
    try:
        for record in (probe, target):
            if (record["clause"] != rule["clause"] or
                    record["operation"] != rule["operation"]):
                return "undetermined"
        for field in ("endpoint", "snapshot"):
            if not probe[field] or probe[field] != target[field]:
                return "undetermined"
        expected_probe = contract_value(rule["expected"], probe["inputs"])
        expected_target = contract_value(rule["expected"], target["inputs"])
        observed_probe = _read(probe["response"], rule["observed"])
        observed_target = _read(target["response"], rule["observed"])
    except (KeyError, IndexError, ValueError, TypeError):
        return "undetermined"
    if type(observed_probe) is not int or type(observed_target) is not int:
        return "undetermined"
    if expected_target != factor * expected_probe or observed_target != factor * observed_probe:
        return "undetermined"
    return "violated" if observed_probe != expected_probe else "undetermined"


class ExtraCalls:
    """One instance per arm/task after the identical step-zero observation."""

    def __init__(self, dispatch):
        self._dispatch = dispatch
        self._events = []

    @property
    def events(self):
        return deepcopy(self._events)

    def call(self, purpose, request):
        if len(self._events) >= 3:
            raise BudgetExhausted("three additional calls already attempted")
        event = {"step": len(self._events) + 1, "purpose": purpose,
                 "request": deepcopy(request), "completed": False}
        self._events.append(event)
        start = perf_counter_ns()
        try:
            result = self._dispatch(request)
            event["completed"] = True
            return result
        finally:
            event["elapsed_ns"] = perf_counter_ns() - start


def disposition(target_verdict, *, verified_replacement):
    """Verdicts refer to the actual user task under its registered contract."""
    if target_verdict not in {"violated", "satisfied", "undetermined"}:
        raise ValueError("invalid task verdict")
    if target_verdict == "violated":
        return "deliver_replacement" if verified_replacement else "defer"
    return "deliver_current"


@dataclass(frozen=True)
class Decision:
    # None means stop. A request identifies the endpoint, operation and arguments.
    request: dict | None
    narrowed_hypotheses: tuple[str, ...]
    intent: str


def replay_group(policy, context, history, logged, replacements, feasible):
    """Use a frozen feasible alternative and an inclusion-minimal field set."""
    if not history or not replacements:
        raise ValueError("a prior response and registered replacements are required")
    actual = policy(deepcopy(context), deepcopy(history))
    if actual != logged:
        raise ValueError("policy did not reproduce the frozen decision")
    response = history[-1]["response"]
    paths = [tuple(path) for path, _ in replacements]
    for index, path in enumerate(paths):
        _read(response, path)
        if any(path[:len(other)] == other for j, other in enumerate(paths) if j != index):
            raise ValueError("duplicate or overlapping intervention paths")

    def replaced(subset):
        result = deepcopy(response)
        for path, value in subset:
            parent = _read(result, path[:-1]) if len(path) > 1 else result
            parent[path[-1]] = deepcopy(value)
        return result

    alternative_response = replaced(replacements)
    if all(type(_read(response, p)) is type(v) and _read(response, p) == v
           for p, v in replacements):
        return {"effect": "unauditable", "reason": "no field changed"}
    if not feasible(response) or not feasible(alternative_response):
        return {"effect": "unauditable", "reason": "infeasible observation"}
    for size in range(1, len(replacements)):
        if any(feasible(replaced(part)) for part in combinations(replacements, size)):
            return {"effect": "unauditable", "reason": "smaller feasible intervention exists"}
    alternative = deepcopy(history)
    alternative[-1]["response"] = alternative_response
    changed = policy(deepcopy(context), alternative)
    if logged.request == changed.request:
        effect = "same_action"
    elif logged.request is None or changed.request is None:
        effect = "stop_changed"
    else:
        effect = "request_changed"
    return {"fields": [{"path": list(path), "observed": _read(response, path),
                        "alternative": value} for path, value in replacements],
            "actual_request": logged.request,
            "counterfactual_request": changed.request, "effect": effect}


def replay_choice(policy, context, history, logged, field_path, normal_value):
    """Legacy single-field replay; the caller has already validated feasibility."""
    audit = replay_group(policy, context, history, logged,
                         [(field_path, normal_value)], lambda response: True)
    if audit.get("reason") == "no field changed":
        audit = {"effect": "same_action", "actual_request": logged.request,
                 "counterfactual_request": logged.request}
    audit.update(field_path=list(field_path), observed=_read(history[-1]["response"], field_path),
                 alternative_value=normal_value)
    return audit
