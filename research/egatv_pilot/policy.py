"""Policy sees only evidence, contract scope, model confidence, cost and availability."""
from dataclasses import dataclass

from tasks import SCOPES

METHODS = ("direct","status","fixed","matched","reuse_matched","mutation","full","fallback_first","uncertainty","generic_risk","egatv")
PROBE_COST = .06
FALLBACK_COST = .25
ERROR_FLOOR = .05


@dataclass(frozen=True)
class Evidence:
    generated: bool
    observed: bool
    scope: int
    passed: bool


def choose(method, scope, history, call_probe, library, confidence, severity, fallback):
    alternatives = list(range(len(SCOPES)))
    recover = "fallback" if fallback else "defer"
    if method == "direct":
        return "primary"
    if method == "fallback_first":
        return "fallback" if fallback else "primary"
    if method == "status":
        return "primary" if history.passed else recover
    if method == "reuse_matched":
        usable = history.generated and history.observed and history.scope == scope
        result = history if usable else call_probe(scope)
        return "primary" if result.passed else recover
    if method in ("fixed", "matched", "mutation", "full"):
        if method == "full":
            selected = [scope, 1-scope]
        elif method == "matched":
            selected = [scope]
        elif method == "fixed":
            selected = [0]
        else:
            # Three calibration mutants: shift every width; shift only the
            # multi-codepoint emoji presentation; sum scalar display widths.
            selected = [max(alternatives, key=lambda q: len(library["kills"][q]))]
        results = [(q, call_probe(q)) for q in selected]
        if method == "full":
            failed = any(not record.passed for q,record in results if q == scope)
        else:
            failed = not results[0][1].passed
        return recover if failed else "primary"

    worlds = library["worlds"]
    # Rows are measured probe pass vectors from the two development releases.
    def update(weights, likelihood):
        products = [w*x for w,x in zip(weights, likelihood)]
        total = sum(products)
        return [x/total for x in products] if total else weights

    def observation(w, q):
        return .95 if w[q] else .05

    def terminal(weights, consequence):
        fail = sum(a*(not w[scope]) for a,w in zip(weights,worlds))
        risk = 1-confidence*(1-(ERROR_FLOOR + (1-2*ERROR_FLOOR)*fail))
        losses = {"primary": consequence*risk, "defer": 1.}
        if fallback:
            losses["fallback"] = FALLBACK_COST + consequence*(1-confidence)
        action = min(losses,key=losses.get)
        return losses[action], action

    weights = [1/len(worlds)] * len(worlds)
    if method == "egatv":
        likelihood = [observation(w,scope) for w in worlds] if (
            history.generated and history.observed and history.scope == scope) else [1.]*len(worlds)
    else:
        # Marginalize the four equally represented history mechanisms when
        # only a suite's colour survives in the scalar report.
        likelihood = [(2 + observation(w,scope) + observation(w,1-scope))/4 for w in worlds]
    if not history.passed:
        likelihood = [1-x for x in likelihood]
    weights = update(weights,likelihood)
    if method == "uncertainty":
        return terminal(weights,1.)[1]
    # A deterministic supported check for this same scope cannot supply new evidence twice.
    if method == "egatv" and history.generated and history.observed and history.scope == scope:
        return terminal(weights,severity)[1]
    current, action = terminal(weights,severity)
    best, next_q = current,None
    for q in alternatives:
        likelihood = [observation(w,q) for w in worlds]
        p = sum(a*l for a,l in zip(weights,likelihood))
        passed = terminal(update(weights,likelihood),severity)[0]
        failed = terminal(update(weights,[1-x for x in likelihood]),severity)[0]
        loss = PROBE_COST + p*passed + (1-p)*failed
        if loss < best:
            best, next_q = loss,q
    if next_q is None:
        return action
    evidence = call_probe(next_q)
    likelihood = [observation(w,next_q) for w in worlds]
    if not evidence.passed:
        likelihood = [1-x for x in likelihood]
    return terminal(update(weights,likelihood),severity)[1]

