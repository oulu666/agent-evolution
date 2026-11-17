"""Deterministic tool registry and shared validation."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from ..utils import canonical_json


class ToolError(ValueError):
    """Raised for invalid tool input; converted into a tool error observation."""


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, name: str, description: str, input_schema: Dict[str, Any],
                 handler: Callable[[Dict[str, Any]], Any]) -> None:
        if name in self._tools:
            raise ValueError("Duplicate tool: %s" % name)
        self._tools[name] = ToolSpec(name, description, input_schema, handler)

    def names(self) -> List[str]:
        return sorted(self._tools)

    def schemas(self) -> List[Dict[str, Any]]:
        return [
            {"name": spec.name, "description": spec.description,
             "input_schema": spec.input_schema}
            for spec in self._tools.values()
        ]

    def execute(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name not in self._tools:
            return {"ok": False, "error": "unknown tool: %s" % name}
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            return {"ok": False, "error": "arguments must be a JSON object"}
        try:
            result = self._tools[name].handler(arguments)
            return {"ok": True, "result": result}
        except ToolError as exc:
            return {"ok": False, "error": str(exc)}
        except Exception as exc:  # keep tool failures deterministic and typed
            return {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}

    def observation(self, name: str, arguments: Dict[str, Any]) -> str:
        return canonical_json(self.execute(name, arguments))


def require_str(arguments: Dict[str, Any], key: str, max_length: int = 4096) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value:
        raise ToolError("argument %r must be a non-empty string" % key)
    if len(value) > max_length:
        raise ToolError("argument %r exceeds %d characters" % (key, max_length))
    return value


def require_number(arguments: Dict[str, Any], key: str) -> float:
    value = arguments.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ToolError("argument %r must be a number" % key)
    if not math.isfinite(float(value)):
        raise ToolError("argument %r must be finite" % key)
    return float(value)


def require_number_list(value: Any, name: str, min_len: int = 2,
                        max_len: int = 100) -> List[float]:
    if not isinstance(value, list):
        raise ToolError("%s must be a JSON array" % name)
    if len(value) < min_len or len(value) > max_len:
        raise ToolError("%s must have between %d and %d numbers" % (name, min_len, max_len))
    numbers = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ToolError("%s must contain only numbers" % name)
        number = float(item)
        if not math.isfinite(number):
            raise ToolError("%s must contain only finite numbers" % name)
        numbers.append(number)
    return numbers
