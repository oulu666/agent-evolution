"""[ext 2026-11-11] Monitor v2 decision rule (pure Python, no GPU).

The Round-2 adaptive rule flags a family only when its probe score drops
between the stage start and the midpoint (drop > 0).  That rule cannot see a
skill that is already absent at the stage start (floor effect) and treats any
one-item wobble as a drop.  This module adds:

* DEGRADED   : significant within-stage drop (one-sided two-proportion test).
* DEFICIENT  : the current level is confidently below a competence target tau
               (Wilson upper bound < tau), whatever happened before.
* INSUFFICIENT_EVIDENCE : too few probe items, or a drop/level that the probe
               cannot resolve.  Policy: do not target, keep the uniform share.
* OK         : no significant drop and the level is compatible with tau.

No existing code is modified; replay_train.py keeps the v1 behaviour.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

Z90 = 1.6448536269514722
DEFAULTS = {"tau": 0.8, "delta": 0.10, "alpha": 0.10, "n_min": 8,
            "ie_margin": 0.25}
SEVERITY = {"DEGRADED": 3, "DEFICIENT": 2, "INSUFFICIENT_EVIDENCE": 1, "OK": 0}
FLAGGED = ("DEGRADED", "DEFICIENT")


def wilson(k: int, n: int, z: float = Z90) -> Tuple[float, float]:
    if n <= 0:
        return 0.0, 1.0
    p = k / n
    denom = 1.0 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - half) / denom), min(1.0, (centre + half) / denom)


def drop_pvalue(k0: int, n0: int, k1: int, n1: int) -> float:
    """One-sided p-value for H1: p1 < p0 (pooled two-proportion z test)."""
    if n0 <= 0 or n1 <= 0:
        return 1.0
    p0, p1 = k0 / n0, k1 / n1
    pooled = (k0 + k1) / (n0 + n1)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n0 + 1 / n1))
    if se == 0:
        return 0.0 if p1 < p0 else 1.0
    z = (p0 - p1) / se
    return 0.5 * math.erfc(z / math.sqrt(2))


def decide(k0: int, n0: int, k1: int, n1: int,
           params: Optional[Mapping[str, float]] = None) -> Dict[str, Any]:
    """Decision for one family/subset from start (k0/n0) and check (k1/n1)."""
    cfg = dict(DEFAULTS, **(params or {}))
    if n0 < cfg["n_min"] or n1 < cfg["n_min"]:
        return {"status": "INSUFFICIENT_EVIDENCE", "reason": "too_few_items",
                "n0": n0, "n1": n1, "gap": 0.0}
    p0, p1 = k0 / n0, k1 / n1
    drop = p0 - p1
    pval = drop_pvalue(k0, n0, k1, n1)
    lo, hi = wilson(k1, n1)
    base = {"n0": n0, "n1": n1, "p0": p0, "p1": p1, "drop": drop,
            "p_value": pval, "ci90": [lo, hi]}
    if drop >= cfg["delta"] and pval < cfg["alpha"]:
        status, reason = "DEGRADED", "significant_drop"
    elif hi < cfg["tau"]:
        status, reason = "DEFICIENT", "level_below_tau"
    elif drop >= cfg["delta"]:
        status, reason = "INSUFFICIENT_EVIDENCE", "drop_not_significant"
    elif lo < cfg["tau"] - cfg["ie_margin"]:
        status, reason = "INSUFFICIENT_EVIDENCE", "level_ci_too_wide"
    else:
        status, reason = "OK", "no_drop_level_ok"
    gap = 0.0
    if status in FLAGGED:
        gap = max(drop if status == "DEGRADED" else 0.0, cfg["tau"] - p1, 1e-6)
    return dict(base, status=status, reason=reason, gap=gap)


def combine(decisions: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Subset-max: the most severe subset decides the family."""
    decisions = list(decisions)
    if not decisions:
        return {"status": "INSUFFICIENT_EVIDENCE", "reason": "no_subsets", "gap": 0.0}
    worst = max(decisions, key=lambda d: (SEVERITY[d["status"]], d.get("gap", 0.0)))
    return dict(worst, n_subsets=len(decisions))


def v1_flag(p0: float, p1: float) -> bool:
    """The Round-2 adaptive trigger: any positive probe drop."""
    return (p0 - p1) > 0


def target_weights(family_decisions: Mapping[str, Dict[str, Any]]) -> Dict[str, float]:
    """Gap-proportional target weights over flagged families; {} -> uniform only."""
    gaps = {f: d.get("gap", 0.0) for f, d in family_decisions.items()
            if d["status"] in FLAGGED and d.get("gap", 0.0) > 0}
    total = sum(gaps.values())
    return {f: g / total for f, g in gaps.items()} if total > 0 else {}
