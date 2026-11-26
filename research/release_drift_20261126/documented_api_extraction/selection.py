"""Bounded selection of documented API obligations.

Downloads pinned sdists and writes a screening log. It does not import the
subject libraries and does not call them. Inclusion is the frozen linguistic
patterns below plus the documented signature. Sentences that do not determine
both inputs are examined and excluded.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

from outcomes import (
    EXAMINE_CAP,
    FORBIDDEN,
    FUNCTION_CAP,
    INCLUDE_CAP,
    LIBRARY_CAP,
    audit_driver,
    build_driver,
)


_PREDICATE = Path(__file__).resolve().parents[1] / "documented_predicate_binding"
if str(_PREDICATE) not in sys.path:
    sys.path.insert(0, str(_PREDICATE))

from sentence_grounded import audit_human, is_obligation, quote_in_document, split_sentences, strip_markup  # noqa: E402


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROTOCOL = HERE / "protocol.md"
SCREENING = HERE / "screening.json"
CASES = HERE / "cases.json"
DOCS = HERE / "docs"
SOURCES = DOCS / "sources"
USER_AGENT = "documented-api-extraction/1.0"
SDIST_BYTE_CAP = 80 * 1024 * 1024

POOL = (
    {"pypi": "click", "roots": ("click",), "import_name": "click"},
    {"pypi": "requests", "roots": ("requests",), "import_name": "requests"},
    {"pypi": "httpx", "roots": ("httpx",), "import_name": "httpx"},
    {"pypi": "pydantic", "roots": ("pydantic",), "import_name": "pydantic"},
    {"pypi": "pytest", "roots": ("pytest",), "import_name": "pytest"},
    {"pypi": "Jinja2", "roots": ("jinja2",), "import_name": "jinja2"},
    {"pypi": "flask", "roots": ("flask",), "import_name": "flask"},
    {"pypi": "werkzeug", "roots": ("werkzeug",), "import_name": "werkzeug"},
    {"pypi": "marshmallow", "roots": ("marshmallow",), "import_name": "marshmallow"},
    {"pypi": "jsonschema", "roots": ("jsonschema",), "import_name": "jsonschema"},
    {"pypi": "python-dateutil", "roots": ("dateutil",), "import_name": "dateutil"},
    {"pypi": "arrow", "roots": ("arrow",), "import_name": "arrow"},
    {"pypi": "attrs", "roots": ("attr", "attrs"), "import_name": "attr"},
    {"pypi": "rich", "roots": ("rich",), "import_name": "rich"},
    {"pypi": "hypothesis", "roots": ("hypothesis",), "import_name": "hypothesis"},
    {"pypi": "lxml", "roots": ("lxml",), "import_name": "lxml"},
    {"pypi": "beautifulsoup4", "roots": ("bs4",), "import_name": "bs4"},
    {"pypi": "PyYAML", "roots": ("yaml",), "import_name": "yaml"},
    {"pypi": "tomli", "roots": ("tomli",), "import_name": "tomli"},
)

SKIP_PARTS = {
    "tests", "test", "testing", "docs", "doc", "examples", "example",
    "benchmarks", "benchmark", "vendor", "vendored", "_vendor", "typings",
}
SKIP_DECORATORS = {
    "property", "cached_property", "contextmanager", "asynccontextmanager",
    "overload", "command", "group", "option", "argument", "pass_context",
    "pass_obj", "fixture", "hookimpl", "hookspec", "route", "get", "post",
    "put", "delete", "patch", "head", "before_request", "errorhandler",
    "endpoint", "validator", "field_validator", "model_validator", "given",
    "example", "settings", "app_context", "request_context",
}
DENY_NAMES = {
    "now", "utcnow", "today", "sleep", "urlopen", "urlretrieve", "time",
    "random", "randrange", "uuid4", "uuid1", "uuid",
}
GENERIC_PARAMS = {
    "value", "input", "obj", "object", "number", "item", "data", "text",
    "string", "arg", "argument",
}
PARAM_BLOCK = {
    "if", "when", "unless", "is", "not", "a", "an", "the", "otherwise",
    "else", "and", "or", "returns", "return", "true", "false", "none",
}
_EXC = (
    r"[A-Z][A-Za-z0-9]*(?:Error|Exception|Warning)|StopIteration|"
    r"StopAsyncIteration|GeneratorExit|KeyboardInterrupt|SystemExit"
)
_EXC_RE = re.compile(rf"\b({_EXC})\b")
_LEAD = r"(?:(?:the|a|an|this|it)\s+)?"
_SUBJECT = r"(?:(?:function|method|result|value|output)\s+)?"
_VERB = r"(?<![A-Za-z])(?:returns|return|equals|is|are)(?![A-Za-z])"
_PARAM = r"(?:the\s+)?([A-Za-z_][A-Za-z0-9_]*)"
_RETURN_IF = re.compile(
    rf"(?is)^{_LEAD}{_SUBJECT}{_VERB}\s+(.+?)\s+(?:if|when)\s+{_PARAM}\s+(.+?)\s+"
    rf"(?:,|and)\s+(?:(?:returns|is|equals)\s+)?(.+?)\s+(?:otherwise|else)$"
)
_RETURN_ELSE = re.compile(
    rf"(?is)^{_LEAD}{_SUBJECT}{_VERB}\s+(.+?)\s+(?:if|when)\s+{_PARAM}\s+(.+?)\s+else\s+(.+)$"
)
_RAISE_LEAD = re.compile(
    rf"(?is)^if\s+{_PARAM}\s+(.+?)\s*,\s+(?:(?:a|an)\s+)?"
    rf"(?:({_EXC})\s+is\s+raised|(?:raises|raise|raising)\s+(?:(?:a|an)\s+)?({_EXC}))$"
)
_RAISE_TRAIL = re.compile(
    rf"(?is)^(?:.*?)\b(?:raises|raise|raising|raised)\s+(?:(?:a|an)\s+)?({_EXC})\b"
    rf"\s+(if|when|unless)\s+{_PARAM}\s+(.+)$"
)
_RAISE_IS = re.compile(
    rf"(?is)^(?:(?:a|an)\s+)?({_EXC})\s+is\s+raised\s+(if|when|unless)\s+{_PARAM}\s+(.+)$"
)
_RETURN_CLAUSE = re.compile(
    r"(?is)(?<![A-Za-z])(?:returns|return)\s+(.+?)(?=\s+and\s+(?:raises|raise|raising|raised)\b|"
    r"\s*,\s*(?:raises|raise|raising|raised)\b|$)"
)
_TYPE_TAIL = r"(?:integer|int|number|float|value|string|str|bool|boolean)"
_QUALITIES = (
    ("strictly positive", "pos", False),
    ("strictly negative", "neg", False),
    ("non-negative", "nonneg", False),
    ("non-positive", "nonpos", False),
    ("greater than or equal to", "ge", True),
    ("less than or equal to", "le", True),
    ("greater than", "gt", True),
    ("less than", "lt", True),
    ("equal to", "eq", True),
    ("at least", "ge", True),
    ("at most", "le", True),
    ("nonnegative", "nonneg", False),
    ("nonpositive", "nonpos", False),
    ("positive", "pos", False),
    ("negative", "neg", False),
    ("even", "even", False),
    ("odd", "odd", False),
    ("zero", "zero", False),
    ("true", "true", False),
    ("false", "false", False),
)
_QUALITY_HUMAN = (
    ("strictly positive", {"op": "return_holds", "translation": ">0"}),
    ("strictly negative", {"op": "return_holds", "translation": "<0"}),
    ("non-negative", {"op": "return_holds", "translation": ">=0"}),
    ("non-positive", {"op": "return_holds", "translation": "<=0"}),
    ("nonnegative", {"op": "return_holds", "translation": ">=0"}),
    ("nonpositive", {"op": "return_holds", "translation": "<=0"}),
    ("positive", {"op": "return_holds", "translation": ">0"}),
    ("negative", {"op": "return_holds", "translation": "<0"}),
)
_PRIORITY = {"return_if": 0, "return_and_raise": 1, "raise_if": 2, "ambiguous": 0}


def clean_sentence(sentence: str) -> str:
    text = strip_markup(sentence or "").strip()
    if text.endswith("."):
        text = text[:-1].strip()
    return re.sub(r"\s+", " ", text)


def exception_names(text: str) -> list[str]:
    found = []
    for name in _EXC_RE.findall(text or ""):
        if name not in found:
            found.append(name)
    return found


def when_true_false(kind: str, number: int | None):
    if kind == "pos":
        return 1, 0
    if kind == "neg":
        return -1, 0
    if kind == "zero":
        return 0, 1
    if kind == "true":
        return True, False
    if kind == "false":
        return False, True
    if kind == "even":
        return 0, 1
    if kind == "odd":
        return 1, 0
    if kind == "nonneg":
        return 0, -1
    if kind == "nonpos":
        return 0, 1
    if type(number) is not int:
        return None
    if kind == "gt":
        return number + 1, number
    if kind == "ge":
        return number, number - 1
    if kind == "lt":
        return number - 1, number
    if kind == "le":
        return number, number + 1
    if kind == "eq":
        return number, number + 1
    return None


def parse_condition(text: str):
    """Return (when_true, when_false) for the condition as written, or None."""
    body = text.strip().rstrip(".").strip()
    negated = False
    changed = True
    while changed:
        changed = False
        for pattern, flips in (
            (r"(?i)^is\s+not\s+", True),
            (r"(?i)^is\s+", False),
            (r"(?i)^not\s+", True),
        ):
            match = re.match(pattern, body)
            if match:
                negated = negated ^ flips
                body = body[match.end():].strip()
                changed = True
                break
    body = re.sub(r"(?i)^(?:a|an|the)\s+", "", body).strip()
    operator = re.match(rf"^(<=|>=|==|!=|<|>)\s*(-?\d+)(?:\s+{_TYPE_TAIL})?\s*$", body)
    if operator:
        mapping = {"<": "lt", ">": "gt", "<=": "le", ">=": "ge", "==": "eq", "!=": "eq"}
        kind = mapping[operator.group(1)]
        if operator.group(1) == "!=":
            negated = not negated
        pair = when_true_false(kind, int(operator.group(2)))
    else:
        pair = None
        for phrase, kind, needs_number in _QUALITIES:
            if needs_number:
                match = re.match(
                    rf"(?i)^{re.escape(phrase)}\s+(-?\d+)(?:\s+{_TYPE_TAIL})?\s*$",
                    body,
                )
                if match:
                    pair = when_true_false(kind, int(match.group(1)))
                    break
            else:
                match = re.match(rf"(?i)^{re.escape(phrase)}(?:\s+{_TYPE_TAIL})?\s*$", body)
                if match:
                    pair = when_true_false(kind, None)
                    break
    if not pair:
        return None
    when_true, when_false = pair
    if negated:
        when_true, when_false = when_false, when_true
    if type(when_true) not in {int, bool} or type(when_false) not in {int, bool}:
        return None
    if when_true == when_false and type(when_true) is type(when_false):
        return None
    return when_true, when_false


def literal_expr(text: str):
    cleaned = strip_markup(text or "").strip().rstrip(".").strip()
    cleaned = re.sub(r"(?i)^(?:a|an|the)\s+", "", cleaned).strip()
    if re.fullmatch(r"(?i)true", cleaned):
        return {"op": "return_equals", "value": True}
    if re.fullmatch(r"(?i)false", cleaned):
        return {"op": "return_equals", "value": False}
    if re.fullmatch(r"(?i)none|null", cleaned):
        return {"op": "return_equals", "value": None}
    if re.fullmatch(r"-?\d+", cleaned):
        return {"op": "return_equals", "value": int(cleaned)}
    quoted = re.fullmatch(r"""["']([^"']{1,40})["']""", cleaned)
    if quoted and "://" not in quoted.group(1) and "/" not in quoted.group(1):
        return {"op": "return_equals", "value": quoted.group(1)}
    for phrase, expr in _QUALITY_HUMAN:
        if re.match(rf"(?i)^{re.escape(phrase)}\b", cleaned):
            return dict(expr)
    return None


def _same(left, right) -> bool:
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def _if_count(text: str) -> int:
    return len(re.findall(r"(?i)(?<![A-Za-z])if(?![A-Za-z])", text))


def _blocked_param(name: str) -> bool:
    return name.lower() in PARAM_BLOCK


def _contrast(param: str, condition: str, first: str, second: str, sentence: str):
    if _blocked_param(param) or _if_count(sentence) > 1:
        return "ambiguous"
    parsed = parse_condition(condition)
    if not parsed:
        return None
    left = literal_expr(first)
    right = literal_expr(second)
    if left is None or right is None:
        return None
    if _same(left, right):
        return "ambiguous"
    when_true, when_false = parsed
    return {
        "pattern": "return_if",
        "param": param,
        "legal": when_true,
        "violating": when_false,
        "human": left,
    }


def try_return_if(sentence: str):
    match = _RETURN_IF.match(sentence) or _RETURN_ELSE.match(sentence)
    if not match:
        return None
    first, param, condition, second = match.groups()
    return _contrast(param, condition, first, second, sentence)


def try_return_and_raise(sentence: str):
    if not re.search(r"(?i)(?<![A-Za-z])(?:returns|return)(?![A-Za-z])", sentence):
        return None
    raised = try_raise(sentence)
    if raised is None or raised == "ambiguous":
        return raised
    clause = _RETURN_CLAUSE.search(sentence)
    if not clause:
        return None
    body = clause.group(1).strip()
    if re.search(r"(?i)(?<![A-Za-z])(?:if|when|unless)(?![A-Za-z])", body):
        return None
    human = literal_expr(body)
    if human is None:
        return None
    if _same(human, {"op": "raises", "type": raised["exc"]}):
        return "ambiguous"
    return {
        "pattern": "return_and_raise",
        "param": raised["param"],
        "legal": raised["legal"],
        "violating": raised["violating"],
        "human": human,
    }


def try_raise(sentence: str):
    if not re.search(r"(?i)(?<![A-Za-z])(?:raises|raise|raising|raised)(?![A-Za-z])", sentence):
        return None
    names = exception_names(sentence)
    if len(names) > 1:
        return "ambiguous"
    if len(names) != 1:
        return None
    found = []
    lead = _RAISE_LEAD.match(sentence)
    if lead:
        param, condition, exc_a, exc_b = lead.groups()
        found.append((exc_a or exc_b, "if", param, condition))
    trail = _RAISE_TRAIL.match(sentence)
    if trail:
        found.append(trail.groups())
    passive = _RAISE_IS.match(sentence)
    if passive:
        found.append(passive.groups())
    if len(found) != 1:
        return "ambiguous" if len(found) > 1 else None
    exc, conj, param, condition = found[0]
    if _blocked_param(param) or exc not in names:
        return "ambiguous" if exc not in names else None
    parsed = parse_condition(condition)
    if not parsed:
        return None
    when_true, when_false = parsed
    if conj == "unless":
        legal, violating = when_true, when_false
    else:
        legal, violating = when_false, when_true
    return {
        "pattern": "raise_if",
        "param": param,
        "legal": legal,
        "violating": violating,
        "human": {"op": "raises", "type": exc},
        "exc": exc,
    }


def linguistic(sentence: str):
    cleaned = clean_sentence(sentence)
    # Long sentences are not pattern-matched. They can still be examined and excluded.
    if len(cleaned) > 400:
        return "none", None
    for matcher in (try_return_if, try_return_and_raise, try_raise):
        found = matcher(cleaned)
        if found == "ambiguous":
            return "ambiguous", None
        if found:
            return "match", found
    return "none", None


def priority_of(sentence: str) -> int:
    status, found = linguistic(sentence)
    if status == "match":
        return _PRIORITY[found["pattern"]]
    if status == "ambiguous":
        return 2
    return 3


def bind_signature(param: str, parameters: list[str], required: list[str], posonly: list[str]):
    names = [name for name in parameters if name not in {"self", "cls"}]
    needed = [name for name in required if name not in {"self", "cls"}]
    ordered_posonly = [name for name in posonly if name not in {"self", "cls"}]
    if param in names:
        chosen = param
        reason = None
    elif param.lower() in GENERIC_PARAMS and len(needed) == 1:
        chosen = needed[0]
        reason = None
    else:
        return None, "inputs_not_determined_by_sentence"
    others = [name for name in needed if name != chosen]
    if others:
        return None, "needs_extra_arguments"
    if chosen in ordered_posonly and ordered_posonly.index(chosen) != 0:
        return None, "needs_extra_arguments"
    passing = "positional" if chosen in ordered_posonly else "keyword"
    return {"param": chosen, "passing": passing, "rebound": chosen != param}, reason


def propose(sentence: str, parameters: list[str], required: list[str], posonly: list[str]):
    status, found = linguistic(sentence)
    if status == "ambiguous":
        return {"ok": False, "reason": "ambiguous_obligation", "pattern": None}
    if status != "match":
        return {"ok": False, "reason": "inputs_not_determined_by_sentence", "pattern": None}
    bound, reason = bind_signature(found["param"], parameters, required, posonly)
    if reason:
        return {"ok": False, "reason": reason, "pattern": found["pattern"], "param": found["param"]}
    human = found["human"]
    if not audit_human(human, sentence):
        return {
            "ok": False,
            "reason": "not_in_expression_language",
            "pattern": found["pattern"],
            "param": bound["param"],
            "human": human,
        }
    return {
        "ok": True,
        "reason": "include",
        "pattern": found["pattern"],
        "param": bound["param"],
        "passing": bound["passing"],
        "rebound": bound["rebound"],
        "legal": found["legal"],
        "violating": found["violating"],
        "human": human,
    }


class SelectionState:
    def __init__(self):
        self.library = Counter()
        self.function = Counter()
        self.keys = set()


def obligation_key(qualname: str, param: str, human) -> str:
    return json.dumps([qualname, param, human], sort_keys=True, ensure_ascii=False)


def judge(candidate: dict, state: SelectionState, texts: dict[str, str] | None = None) -> dict:
    proposal = propose(
        candidate["sentence"],
        candidate["parameters"],
        candidate["required"],
        candidate["posonly"],
    )
    source = candidate.get("source")
    if source is None and texts is not None:
        source = texts[candidate["file_sha256"]]
    record = {
        "library": candidate["library"],
        "pypi": candidate["pypi"],
        "version": candidate.get("version"),
        "import_name": candidate["import_name"],
        "module": candidate["module"],
        "qualname": candidate["qualname"],
        "attrs": candidate["attrs"],
        "path": candidate["path"],
        "file_sha256": candidate["file_sha256"],
        "quote": candidate["sentence"],
        "docstring": candidate["docstring"],
        "doc_source": candidate["doc_source"],
        "pattern": proposal.get("pattern"),
        "param": proposal.get("param"),
        "legal": proposal.get("legal"),
        "violating": proposal.get("violating"),
        "human_from_sentence": proposal.get("human"),
        "priority": priority_of(candidate["sentence"]),
    }
    if source is None or not quote_in_document(candidate["sentence"], source):
        record["decision"] = "exclude"
        record["reason"] = "quote_not_in_file"
        return record
    if not quote_in_document(candidate["sentence"], candidate["docstring"]):
        record["decision"] = "exclude"
        record["reason"] = "quote_not_in_docstring"
        return record
    if not proposal["ok"]:
        record["decision"] = "exclude"
        record["reason"] = proposal["reason"]
        return record
    key = obligation_key(candidate["qualname"], proposal["param"], proposal["human"])
    if key in state.keys:
        record["decision"] = "exclude"
        record["reason"] = "duplicate_obligation"
        return record
    if state.function[candidate["qualname"]] >= FUNCTION_CAP:
        record["decision"] = "exclude"
        record["reason"] = "function_cap"
        return record
    if state.library[candidate["library"]] >= LIBRARY_CAP:
        record["decision"] = "exclude"
        record["reason"] = "library_cap"
        return record
    driver = build_driver(
        candidate["module"], candidate["attrs"], proposal["param"], proposal["passing"]
    )
    audit_driver(driver, candidate["import_name"])
    state.keys.add(key)
    state.function[candidate["qualname"]] += 1
    state.library[candidate["library"]] += 1
    record["decision"] = "include"
    record["reason"] = "include"
    record["passing"] = proposal["passing"]
    record["driver"] = driver
    return record


def examine(queues: dict[str, list[dict]], texts: dict[str, str] | None = None) -> dict:
    state = SelectionState()
    records = []
    included = 0
    while len(records) < EXAMINE_CAP and included < INCLUDE_CAP:
        progress = False
        for spec in POOL:
            library = spec["pypi"]
            queue = queues.get(library) or []
            if not queue:
                continue
            candidate = queue.pop(0)
            record = judge(candidate, state, texts)
            record["id"] = f"{len(records) + 1:02d}-{library}"
            records.append(record)
            progress = True
            if record["decision"] == "include":
                included += 1
                if included >= INCLUDE_CAP:
                    break
            if len(records) >= EXAMINE_CAP:
                break
        if not progress:
            break
    if included >= INCLUDE_CAP:
        stopped = "12_included"
    elif len(records) >= EXAMINE_CAP:
        stopped = "40_examined"
    else:
        stopped = "pool_exhausted"
    remaining = sum(len(queue) for queue in queues.values())
    return {"records": records, "stopped_because": stopped, "unexamined_candidates": remaining}


def _decorator_names(node: ast.AST) -> list[str]:
    names = []
    for decorator in getattr(node, "decorator_list", []):
        current = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(current, ast.Name):
            names.append(current.id)
        elif isinstance(current, ast.Attribute):
            names.append(current.attr)
        else:
            names.append("unknown")
    return names


def _signature(node: ast.FunctionDef):
    args = node.args
    positional = list(args.posonlyargs) + list(args.args)
    default_count = len(args.defaults)
    parameters = []
    required = []
    posonly = [arg.arg for arg in args.posonlyargs]
    for index, arg in enumerate(positional):
        parameters.append(arg.arg)
        has_default = index >= len(positional) - default_count
        if not has_default:
            required.append(arg.arg)
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        parameters.append(arg.arg)
        if default is None:
            required.append(arg.arg)
    return parameters, required, posonly


def _candidate_from_function(node: ast.FunctionDef, docstring: str, doc_source: str, meta: dict, skipped: Counter):
    if node.name.startswith("_") and node.name != "__init__":
        skipped["private_function"] += 1
        return []
    if isinstance(node, ast.AsyncFunctionDef):
        skipped["async"] += 1
        return []
    if node.name in DENY_NAMES:
        skipped["denylist"] += 1
        return []
    decorators = _decorator_names(node)
    if any(name in SKIP_DECORATORS or name == "unknown" for name in decorators):
        skipped["decorator"] += 1
        return []
    if not docstring:
        return []
    parameters, required, posonly = _signature(node)
    found = []
    for index, sentence in enumerate(split_sentences(docstring)):
        if not is_obligation(strip_markup(sentence)):
            continue
        item = dict(meta)
        item.update({
            "sentence": sentence,
            "sentence_index": index,
            "docstring": docstring,
            "doc_source": doc_source,
            "parameters": parameters,
            "required": required,
            "posonly": posonly,
            "lineno": getattr(node, "lineno", 0),
        })
        found.append(item)
    return found


def candidates_in_source(text: str, meta: dict, skipped: Counter) -> list[dict]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        skipped["parse_error"] += 1
        return []
    found = []
    for node in tree.body:
        if isinstance(node, ast.AsyncFunctionDef):
            skipped["async"] += 1
            continue
        if isinstance(node, ast.FunctionDef):
            doc = ast.get_docstring(node) or ""
            local = {
                **meta,
                "attrs": [node.name],
                "qualname": meta["module"] + "." + node.name,
            }
            found.extend(_candidate_from_function(node, doc, "function", local, skipped))
            continue
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name.startswith("_"):
            skipped["private_class"] += 1
            continue
        init = next(
            (item for item in node.body if isinstance(item, ast.FunctionDef) and item.name == "__init__"),
            None,
        )
        method_count = sum(
            1
            for item in node.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name != "__init__"
        )
        skipped["methods"] += method_count
        if init is None:
            skipped["no_explicit_init"] += 1
            continue
        init_doc = ast.get_docstring(init) or ""
        class_doc = ast.get_docstring(node) or ""
        if init_doc:
            doc, doc_source = init_doc, "init"
        else:
            doc, doc_source = class_doc, "class"
        local = {
            **meta,
            "attrs": [node.name],
            "qualname": meta["module"] + "." + node.name,
        }
        found.extend(_candidate_from_function(init, doc, doc_source, local, skipped))
    return found


def _skip_path(path: Path, package_dir: Path) -> str | None:
    rel_parts = path.relative_to(package_dir).parts
    if path.name.startswith("test_") or path.name.endswith("_test.py") or path.name == "conftest.py":
        return "test_file"
    parents = rel_parts[:-1]
    if any(part in SKIP_PARTS for part in parents):
        return "skipped_dir"
    if any(part.startswith("_") and part != "__init__.py" for part in parents):
        return "private_module"
    if path.name.startswith("_") and path.name != "__init__.py":
        return "private_module"
    return None


def module_name(package_dir: Path, path: Path) -> str:
    relative = path.relative_to(package_dir.parent).with_suffix("")
    name = ".".join(relative.parts)
    if name.endswith(".__init__"):
        name = name[: -len(".__init__")]
    return name


def _family_counts(candidates: list[dict]) -> dict:
    families = Counter()
    for item in candidates:
        status, found = linguistic(item["sentence"])
        if status == "match":
            families[found["pattern"]] += 1
        else:
            families[status] += 1
    return dict(families)


def collect_tree(package_dirs: list[Path], library: dict, version: str | None = None) -> dict:
    skipped = Counter()
    candidates = []
    texts = {}
    seen_files = set()
    for package_dir in package_dirs:
        for path in sorted(package_dir.rglob("*.py")):
            reason = _skip_path(path, package_dir)
            if reason:
                skipped[reason] += 1
                continue
            resolved = str(path.resolve())
            if resolved in seen_files:
                continue
            seen_files.add(resolved)
            try:
                raw = path.read_bytes()
            except OSError:
                skipped["read_error"] += 1
                continue
            digest = hashlib.sha256(raw).hexdigest()
            try:
                source = raw.decode("utf-8")
            except UnicodeDecodeError:
                skipped["decode_error"] += 1
                continue
            texts[digest] = source
            meta = {
                "library": library["pypi"],
                "pypi": library["pypi"],
                "import_name": library["import_name"],
                "version": version,
                "module": module_name(package_dir, path),
                "attrs_prefix": [],
                "path": str(path),
                "file_sha256": digest,
            }
            candidates.extend(candidates_in_source(source, meta, skipped))
    candidates.sort(key=lambda item: (priority_of(item["sentence"]), item["path"], item["lineno"], item["sentence_index"]))
    return {
        "candidates": candidates,
        "texts": texts,
        "skipped": dict(skipped),
        "families": _family_counts(candidates),
    }


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze_commit() -> str:
    return subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--",
         "research/release_drift_20261126/documented_api_extraction/protocol.md"],
        cwd=ROOT,
        text=True,
    ).strip()


def assert_select_ready() -> None:
    paths = [PROTOCOL, HERE / "selection.py", HERE / "outcomes.py"]
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--", *[str(path) for path in paths]],
        cwd=ROOT,
        text=True,
    )
    if dirty.strip():
        raise SystemExit("selection files have uncommitted changes; refusing to select\n" + dirty)
    if SCREENING.exists() or CASES.exists():
        raise SystemExit("screening.json or cases.json already exists; refusing to overwrite decisions")
    for spec in POOL:
        if FORBIDDEN.search(spec["pypi"]) or FORBIDDEN.search(spec["import_name"]):
            raise SystemExit(f"forbidden library in pool: {spec['pypi']}")


def _request(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(request, timeout=60)


def fetch_release(pypi: str) -> dict:
    if FORBIDDEN.search(pypi):
        raise SystemExit(f"refusing forbidden package {pypi}")
    with _request(f"https://pypi.org/pypi/{pypi}/json") as response:
        payload = json.load(response)
    info = payload["info"]
    version = info["version"]
    urls = payload["releases"].get(version) or payload["urls"]
    sdists = [item for item in urls if item.get("packagetype") == "sdist"]
    wheels = [item for item in urls if item.get("packagetype") == "bdist_wheel"]
    chosen = sdists[0] if sdists else (wheels[0] if wheels else None)
    if not chosen:
        return {"pypi": pypi, "version": version, "error": "no_artifact"}
    if FORBIDDEN.search(chosen.get("url", "")):
        raise SystemExit(f"refusing artifact url for {pypi}")
    return {
        "pypi": pypi,
        "version": version,
        "packagetype": chosen["packagetype"],
        "url": chosen["url"],
        "filename": chosen["filename"],
        "sha256": (chosen.get("digests") or {}).get("sha256"),
        "size": chosen.get("size"),
    }


def _safe_members_ok(names: list[str], dest: Path) -> None:
    root = dest.resolve()
    for name in names:
        target = (root / name).resolve()
        if target != root and not str(target).startswith(str(root) + os.sep):
            raise RuntimeError(f"unsafe archive path: {name}")


def download_artifact(spec: dict, dest: Path) -> Path:
    if spec.get("size") and spec["size"] > SDIST_BYTE_CAP:
        raise RuntimeError("sdist_too_large")
    archive = dest / spec["filename"]
    with _request(spec["url"]) as response:
        data = response.read(SDIST_BYTE_CAP + 1)
    if len(data) > SDIST_BYTE_CAP:
        raise RuntimeError("sdist_too_large")
    digest = hashlib.sha256(data).hexdigest()
    if spec.get("sha256") and digest != spec["sha256"]:
        raise RuntimeError("sdist_hash_mismatch")
    spec["sha256"] = digest
    archive.write_bytes(data)
    extracted = dest / "tree"
    extracted.mkdir()
    if spec["filename"].endswith(".zip") or spec["packagetype"] == "bdist_wheel":
        with zipfile.ZipFile(archive) as handle:
            _safe_members_ok(handle.namelist(), extracted)
            handle.extractall(extracted)
    else:
        with tarfile.open(archive, mode="r:*") as handle:
            _safe_members_ok([member.name for member in handle.getmembers()], extracted)
            handle.extractall(extracted, filter="data")
    return extracted


def collect_release(tree: Path, library: dict, version: str) -> dict:
    skipped = Counter()
    candidates = []
    texts = {}
    used = []
    for root_name in library["roots"]:
        matches = []
        for path in tree.rglob(root_name):
            if set(path.parts) & SKIP_PARTS:
                continue
            if path.is_dir() and (path / "__init__.py").is_file():
                matches.append(path)
            elif path.is_file() and path.name == f"{root_name}.py":
                matches.append(path)
        if not matches:
            skipped["root_missing"] += 1
            continue
        matches.sort(key=lambda item: (len(item.parts), str(item)))
        chosen = matches[0]
        used.append(str(chosen.relative_to(tree)))
        if chosen.is_file():
            raw = chosen.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            try:
                source = raw.decode("utf-8")
            except UnicodeDecodeError:
                skipped["decode_error"] += 1
                continue
            texts[digest] = source
            meta = {
                "library": library["pypi"],
                "pypi": library["pypi"],
                "import_name": library["import_name"],
                "version": version,
                "module": root_name,
                "attrs_prefix": [],
                "path": str(chosen.relative_to(tree)),
                "file_sha256": digest,
            }
            candidates.extend(candidates_in_source(source, meta, skipped))
        else:
            batch_info = collect_tree([chosen], library, version)
            for key, value in batch_info["skipped"].items():
                skipped[key] += value
            texts.update(batch_info["texts"])
            for item in batch_info["candidates"]:
                item["path"] = str(Path(item["path"]).resolve().relative_to(tree.resolve()))
                item["version"] = version
                candidates.append(item)
    candidates.sort(key=lambda item: (priority_of(item["sentence"]), item["path"], item["lineno"], item["sentence_index"]))
    return {
        "candidates": candidates,
        "texts": texts,
        "skipped": dict(skipped),
        "families": _family_counts(candidates),
        "package_paths": used,
    }


def _public_record(record: dict) -> dict:
    hidden = {"driver"}
    return {key: value for key, value in record.items() if key not in hidden}


def write_outputs(screen: dict, texts: dict[str, str]) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    SOURCES.mkdir(parents=True, exist_ok=True)
    groups = []
    copied = set()
    for record in screen["records"]:
        digest = record["file_sha256"]
        if digest not in copied:
            payload = texts[digest].encode("utf-8")
            if hashlib.sha256(payload).hexdigest() != digest:
                raise SystemExit(f"source text does not round-trip to {digest}")
            (SOURCES / f"{digest}.txt").write_bytes(payload)
            copied.add(digest)
        if record["decision"] != "include":
            continue
        docstring_path = DOCS / f"{record['id']}.docstring.txt"
        docstring_path.write_text(record["docstring"], encoding="utf-8")
        groups.append({
            "id": record["id"],
            "library": record["library"],
            "pypi": record["pypi"],
            "version": record["version"],
            "import_name": record["import_name"],
            "module": record["module"],
            "qualname": record["qualname"],
            "attrs": record["attrs"],
            "path": record["path"],
            "file_sha256": record["file_sha256"],
            "source_file": f"docs/sources/{digest}.txt",
            "docstring_file": f"docs/{record['id']}.docstring.txt",
            "docstring_sha256": hashlib.sha256(record["docstring"].encode("utf-8")).hexdigest(),
            "quote": record["quote"],
            "pattern": record["pattern"],
            "param": record["param"],
            "passing": record["passing"],
            "legal": record["legal"],
            "violating": record["violating"],
            "human_from_sentence": record["human_from_sentence"],
            "driver": record["driver"],
            "doc_source": record["doc_source"],
        })
    public_records = []
    for record in screen["records"]:
        item = _public_record(record)
        item.pop("source", None)
        item.pop("source_bytes", None)
        item.pop("docstring", None)
        item["source_file"] = f"docs/sources/{item['file_sha256']}.txt"
        public_records.append(item)
    screening = {
        "freeze_commit": screen["freeze_commit"],
        "protocol_sha256": screen["protocol_sha256"],
        "selection_sha256": file_sha(HERE / "selection.py"),
        "outcomes_sha256": file_sha(HERE / "outcomes.py"),
        "stopped_because": screen["stopped_because"],
        "examined": len(public_records),
        "included": len(groups),
        "libraries_included": sorted({group["library"] for group in groups}),
        "unexamined_candidates": screen["unexamined_candidates"],
        "pool": [item["pypi"] for item in POOL],
        "versions": screen["versions"],
        "records": public_records,
    }
    cases = {
        "freeze_commit": screen["freeze_commit"],
        "protocol_sha256": screen["protocol_sha256"],
        "groups": groups,
    }
    SCREENING.write_text(json.dumps(screening, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    CASES.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    assert_select_ready()
    queues = {}
    texts = {}
    versions = {}
    work = Path(tempfile.mkdtemp(prefix="dae-select-"))
    try:
        for library in POOL:
            print(f"fetch {library['pypi']}", flush=True)
            release = fetch_release(library["pypi"])
            entry = {
                "version": release.get("version"),
                "packagetype": release.get("packagetype"),
                "url": release.get("url"),
                "sha256": release.get("sha256"),
                "error": release.get("error"),
            }
            if release.get("error"):
                versions[library["pypi"]] = entry
                queues[library["pypi"]] = []
                continue
            try:
                tree = download_artifact(release, work / library["pypi"])
                collected = collect_release(tree, library, release["version"])
            except Exception as exc:  # noqa: BLE001 — one bad sdist must not invent cases
                entry["error"] = type(exc).__name__ + ": " + str(exc)[:300]
                versions[library["pypi"]] = entry
                queues[library["pypi"]] = []
                print(f"skip {library['pypi']}: {entry['error']}", flush=True)
                continue
            entry["sha256"] = release.get("sha256")
            entry["candidates"] = len(collected["candidates"])
            entry["families"] = collected["families"]
            entry["skipped"] = collected["skipped"]
            entry["package_paths"] = collected["package_paths"]
            versions[library["pypi"]] = entry
            texts.update(collected["texts"])
            queues[library["pypi"]] = collected["candidates"]
            print(
                f"  {release['version']} candidates={len(collected['candidates'])} families={collected['families']}",
                flush=True,
            )
        screened = examine(queues, texts)
        screened["versions"] = versions
        screened["freeze_commit"] = freeze_commit()
        screened["protocol_sha256"] = file_sha(PROTOCOL)
        write_outputs(screened, texts)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print(json.dumps({
        "stopped_because": screened["stopped_because"],
        "examined": len(screened["records"]),
        "included": sum(1 for record in screened["records"] if record["decision"] == "include"),
        "unexamined_candidates": screened["unexamined_candidates"],
    }, indent=2))


if __name__ == "__main__":
    main()
