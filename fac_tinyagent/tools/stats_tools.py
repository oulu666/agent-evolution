"""Pre-defined deterministic statistical operations; no eval or shell."""
from __future__ import annotations

import math
from typing import Any, Dict, List

from .base import ToolError, ToolRegistry, require_number, require_number_list


def _clean(value: float) -> float:
    value = round(float(value), 6)
    if abs(value) < 1e-12:
        return 0.0
    return value


def _values(arguments: Dict[str, Any], key: str = "values") -> List[float]:
    return require_number_list(arguments.get(key), key)


def stats_mean(arguments: Dict[str, Any]) -> float:
    values = _values(arguments)
    return _clean(sum(values) / len(values))


def stats_median(arguments: Dict[str, Any]) -> float:
    values = sorted(_values(arguments))
    middle = len(values) // 2
    if len(values) % 2:
        return _clean(values[middle])
    return _clean((values[middle - 1] + values[middle]) / 2.0)


def stats_std(arguments: Dict[str, Any]) -> float:
    values = _values(arguments)
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return _clean(math.sqrt(variance))


def stats_percentile(arguments: Dict[str, Any]) -> float:
    values = sorted(_values(arguments))
    percentile = require_number(arguments, "percentile")
    if percentile < 0 or percentile > 100:
        raise ToolError("percentile must be between 0 and 100")
    if len(values) == 1:
        return _clean(values[0])
    position = (len(values) - 1) * percentile / 100.0
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return _clean(values[lower])
    weight = position - lower
    return _clean(values[lower] * (1.0 - weight) + values[upper] * weight)


def stats_correlation(arguments: Dict[str, Any]) -> float:
    xs = require_number_list(arguments.get("xs"), "xs")
    ys = require_number_list(arguments.get("ys"), "ys")
    if len(xs) != len(ys):
        raise ToolError("xs and ys must have the same length")
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denom_x = sum((x - mean_x) ** 2 for x in xs)
    denom_y = sum((y - mean_y) ** 2 for y in ys)
    if denom_x <= 0 or denom_y <= 0:
        raise ToolError("correlation is undefined for constant input")
    return _clean(numerator / math.sqrt(denom_x * denom_y))


def stats_linear_regression(arguments: Dict[str, Any]) -> Dict[str, float]:
    xs = require_number_list(arguments.get("xs"), "xs")
    ys = require_number_list(arguments.get("ys"), "ys")
    if len(xs) != len(ys):
        raise ToolError("xs and ys must have the same length")
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom <= 0:
        raise ToolError("regression is undefined for constant x")
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / denom
    intercept = mean_y - slope * mean_x
    return {"slope": _clean(slope), "intercept": _clean(intercept)}


VALUE_SCHEMA = {"type": "array", "items": {"type": "number"},
                "minItems": 2, "maxItems": 100}
PAIR_SCHEMA = {"type": "object",
               "properties": {"xs": VALUE_SCHEMA, "ys": VALUE_SCHEMA},
               "required": ["xs", "ys"], "additionalProperties": False}


def build_stats_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        "stats_mean",
        "Return the arithmetic mean of a list of numbers.",
        {"type": "object", "properties": {"values": VALUE_SCHEMA},
         "required": ["values"], "additionalProperties": False},
        stats_mean,
    )
    registry.register(
        "stats_median",
        "Return the median of a list of numbers.",
        {"type": "object", "properties": {"values": VALUE_SCHEMA},
         "required": ["values"], "additionalProperties": False},
        stats_median,
    )
    registry.register(
        "stats_std",
        "Return the population standard deviation of a list of numbers.",
        {"type": "object", "properties": {"values": VALUE_SCHEMA},
         "required": ["values"], "additionalProperties": False},
        stats_std,
    )
    registry.register(
        "stats_percentile",
        "Return a percentile (0-100, linear interpolation) of a list of numbers.",
        {"type": "object",
         "properties": {"values": VALUE_SCHEMA, "percentile": {"type": "number"}},
         "required": ["values", "percentile"], "additionalProperties": False},
        stats_percentile,
    )
    registry.register(
        "stats_correlation",
        "Return the Pearson correlation between two equal-length number lists.",
        PAIR_SCHEMA,
        stats_correlation,
    )
    registry.register(
        "stats_linear_regression",
        "Return the slope and intercept of an ordinary least-squares line for y on x.",
        PAIR_SCHEMA,
        stats_linear_regression,
    )
    return registry
