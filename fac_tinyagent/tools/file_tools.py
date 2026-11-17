"""Sandboxed deterministic file tools."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List

from .base import ToolError, ToolRegistry, require_str

MAX_FILE_BYTES = 65536


class FileSandbox:
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, path: str) -> Path:
        if not isinstance(path, str) or not path:
            raise ToolError("path must be a non-empty string")
        if "\x00" in path:
            raise ToolError("path contains a null byte")
        relative = Path(path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ToolError("path must stay inside the sandbox")
        target = (self.root / relative).resolve()
        try:
            common = os.path.commonpath([str(self.root), str(target)])
        except ValueError:
            raise ToolError("path escapes the sandbox")
        if common != str(self.root):
            raise ToolError("path escapes the sandbox")
        return target

    def list_files(self, directory: str) -> List[str]:
        base = self.resolve(directory)
        if not base.exists():
            raise ToolError("directory does not exist: %s" % directory)
        if not base.is_dir():
            raise ToolError("not a directory: %s" % directory)
        files = []
        for path in base.rglob("*"):
            if path.is_file():
                files.append(str(path.relative_to(self.root)).replace(os.sep, "/"))
        return sorted(files)

    def read(self, path: str) -> str:
        target = self.resolve(path)
        if not target.is_file():
            raise ToolError("file does not exist: %s" % path)
        if target.stat().st_size > MAX_FILE_BYTES:
            raise ToolError("file is larger than %d bytes" % MAX_FILE_BYTES)
        try:
            return target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise ToolError("file is not valid UTF-8 text")

    def search(self, path: str, pattern: str) -> List[Dict[str, Any]]:
        content = self.read(path)
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            raise ToolError("invalid regular expression: %s" % exc)
        matches = []
        for number, line in enumerate(content.splitlines(), 1):
            if regex.search(line):
                matches.append({"line": number, "text": line})
                if len(matches) >= 50:
                    break
        return matches

    def write(self, path: str, content: str) -> Dict[str, Any]:
        if len(content) > MAX_FILE_BYTES:
            raise ToolError("content is larger than %d characters" % MAX_FILE_BYTES)
        target = self.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"path": path, "characters": len(content)}


def materialize_sandbox(files: Dict[str, str], root: str) -> FileSandbox:
    sandbox = FileSandbox(root)
    for path, content in files.items():
        sandbox.write(path, content)
    return sandbox


def build_file_registry(sandbox: FileSandbox) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        "file_list",
        "List all files under a directory, recursively. Paths are relative to the sandbox.",
        {"type": "object", "properties": {"directory": {"type": "string"}},
         "required": ["directory"], "additionalProperties": False},
        lambda args: sandbox.list_files(require_str(args, "directory")),
    )
    registry.register(
        "file_read",
        "Read a UTF-8 text file from the sandbox and return its contents.",
        {"type": "object", "properties": {"path": {"type": "string"}},
         "required": ["path"], "additionalProperties": False},
        lambda args: sandbox.read(require_str(args, "path")),
    )
    registry.register(
        "file_search",
        "Search a sandbox text file with a regular expression; return matching lines.",
        {"type": "object",
         "properties": {"path": {"type": "string"}, "pattern": {"type": "string"}},
         "required": ["path", "pattern"], "additionalProperties": False},
        lambda args: sandbox.search(require_str(args, "path"),
                                    require_str(args, "pattern", max_length=256)),
    )
    registry.register(
        "file_write",
        "Write UTF-8 text to a file inside the sandbox and report the character count.",
        {"type": "object",
         "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
         "required": ["path", "content"], "additionalProperties": False},
        lambda args: sandbox.write(require_str(args, "path"),
                                   require_str(args, "content", max_length=MAX_FILE_BYTES)),
    )
    return registry
