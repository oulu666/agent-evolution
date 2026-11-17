"""Tool registry factories for the phase-1/phase-2 families."""
from __future__ import annotations

from typing import Any, Dict

from .base import ToolError, ToolRegistry
from .calendar_tools import build_calendar_registry, create_calendar_fixture
from .db_tools import build_db_registry, create_fixture
from .file_tools import FileSandbox, build_file_registry, materialize_sandbox
from .stats_tools import build_stats_registry

__all__ = [
    "ToolError", "ToolRegistry", "FileSandbox", "build_file_registry",
    "materialize_sandbox", "build_db_registry", "create_fixture",
    "build_stats_registry", "build_calendar_registry",
    "create_calendar_fixture", "build_registry",
]


def build_registry(family: str, environment: Dict[str, Any] = None) -> ToolRegistry:
    environment = environment or {}
    if family == "file":
        root = environment.get("sandbox_root")
        if not root:
            raise ValueError("file family requires environment['sandbox_root']")
        return build_file_registry(FileSandbox(root))
    if family == "database":
        path = environment.get("db_path")
        if not path:
            raise ValueError("database family requires environment['db_path']")
        return build_db_registry(path)
    if family == "python":
        return build_stats_registry()
    if family == "calendar":
        path = environment.get("calendar_path")
        if not path:
            raise ValueError("calendar family requires environment['calendar_path']")
        return build_calendar_registry(path)
    raise ValueError("unknown family: %s" % family)
