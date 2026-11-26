"""Shared pre-freeze controls for blind runs. No case labels or project rules."""

from copy import deepcopy
from dataclasses import dataclass
from time import perf_counter_ns


class BudgetExhausted(Exception):
    pass


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


def replay_choice(policy, context, history, logged, field_path, normal_value):
    """Intervene on one registered field of the last response. Offline only.

    The caller supplies a previously registered, feasible normal alternative.
    History consists of JSON-like request/response records. The policy must be
    a deterministic pure function and cannot dispatch a tool.
    """
    if not history or not field_path:
        raise ValueError("a prior response and field path are required")
    actual = policy(deepcopy(context), deepcopy(history))
    if actual != logged:
        raise ValueError("policy did not reproduce the frozen decision")
    alternative = deepcopy(history)
    parent = alternative[-1]["response"]
    for key in field_path[:-1]:
        parent = parent[key]
    key = field_path[-1]
    original = deepcopy(parent[key])
    parent[key] = deepcopy(normal_value)
    changed = policy(deepcopy(context), alternative)
    if logged.request == changed.request:
        effect = "same_action"
    elif logged.request is None or changed.request is None:
        effect = "stop_changed"
    else:
        effect = "request_changed"
    return {"field_path": list(field_path), "observed": original,
            "alternative_value": normal_value, "actual_request": logged.request,
            "counterfactual_request": changed.request, "effect": effect}
