"""Evidence-constrained binding and the frozen keep/drop/refine rule."""

from __future__ import annotations

import re

from jdoctor_patterns import holds, simple_match


RESULT_WORDS = {"result", "return", "returns", "it", "value", "output"}
TAGGED = {"param", "return", "raises"}
PRIORITY = ("inversion", "false_alarm", "both_alarm", "hit", "both_clear", "no_check")

_HEADER = re.compile(
    r"(?im)^(?P<header>[ \t]*(?:Parameters|Parameter|Returns|Return|Raises|Raise|"
    r"Yields|Exceptions|Args|Arguments)\s*:?\s*)$"
)
_TAG = re.compile(
    r"(?im)^(?P<tag>[ \t]*(?::(?:param|parameter|arg|argument|return|returns|rtype|"
    r"raises|raise|except|exception)\b[^\n]*|@(?:param|return|throws|exception)\b[^\n]*))$"
)
_DUTY = (
    ("must not return", " is not "),
    ("must never return", " is not "),
    ("must not be", " is not "),
    ("must never be", " is not "),
    ("will not be", " is not "),
    ("will never be", " is not "),
    ("can't be", " is not "),
    ("cannot be", " is not "),
    ("should not be", " is not "),
    ("shouldn't be", " is not "),
    ("may not be", " is not "),
    ("must be", " is "),
    ("will be", " is "),
)
_NON_NULL = (
    ("non-null", "!=null"),
    ("nonnull", "!=null"),
    ("non-empty", "not empty"),
    ("nonempty", "not empty"),
)


def preprocess(text: str) -> str:
    rewritten = text
    for source, target in _NON_NULL:
        rewritten = re.sub(re.escape(source), target, rewritten, flags=re.IGNORECASE)
    rewritten = re.sub(r"\bmay be\b", "", rewritten, flags=re.IGNORECASE)
    rewritten = re.sub(r"\bcan be\b", "", rewritten, flags=re.IGNORECASE)
    for source, target in _DUTY:
        rewritten = re.sub(re.escape(source), target, rewritten, flags=re.IGNORECASE)
    if rewritten.lstrip().lower().startswith("whether"):
        rewritten = re.sub(r"(?i)^\s*whether", "True if", rewritten, count=1) + ", false otherwise"
    return re.sub(r"[ \t]{2,}", " ", rewritten)


def strip_doctests(text: str) -> tuple[str, int]:
    lines = text.splitlines()
    kept = []
    count = 0
    index = 0
    while index < len(lines):
        if lines[index].lstrip().startswith(">>>"):
            count += 1
            index += 1
            while index < len(lines) and lines[index].lstrip().startswith((">>>", "...")):
                index += 1
            if index < len(lines) and lines[index].strip():
                index += 1
            continue
        kept.append(lines[index])
        index += 1
    return "\n".join(kept), count


def _kind(header: str) -> str:
    token = header.strip().lower().lstrip("@").lstrip(":")
    token = token.split()[0].rstrip(":")
    if token in {"parameters", "parameter", "args", "arguments", "param", "arg", "argument"}:
        return "param"
    if token in {"raises", "raise", "exceptions", "except", "exception", "throws"}:
        return "raises"
    if token in {"returns", "return", "rtype", "yields"}:
        return "return"
    return "prose"


def split_blocks(text: str) -> list[dict]:
    marks = []
    for match in _HEADER.finditer(text):
        marks.append((match.start(), match.end(), match.group("header")))
    for match in _TAG.finditer(text):
        marks.append((match.start(), match.end(), match.group("tag")))
    marks.sort()
    if not marks:
        return [{"kind": "prose", "body": text}]
    blocks = []
    if marks[0][0] > 0:
        blocks.append({"kind": "prose", "body": text[: marks[0][0]]})
    for index, (start, end, header) in enumerate(marks):
        stop = marks[index + 1][0] if index + 1 < len(marks) else len(text)
        inline = header.split(":", 1)[1] if ":" in header else ""
        rest = text[end:stop]
        body = (inline + "\n" + rest).strip()
        blocks.append({"kind": _kind(header), "body": body})
    return blocks


def _sentences(body: str) -> list[str]:
    parts = re.split(r"[\n.]+", body)
    return [part.strip() for part in parts if part.strip()]


def _subject_and_predicate(sentence: str) -> tuple[str, str]:
    match = re.search(
        r"(?<![A-Za-z])(is equal to|are equal to|equals to|returns|return|is|are|be)(?![A-Za-z])",
        sentence,
        re.IGNORECASE,
    )
    if not match:
        return sentence, ""
    return sentence[: match.start()], sentence[match.start() :]


def translate_document(text: str, method: str) -> dict:
    stripped, doctests = strip_doctests(text or "")
    prepared = preprocess(stripped)
    checks = []
    untranslated = []
    tagged = False
    for block in split_blocks(prepared):
        if block["kind"] in TAGGED:
            tagged = True
        if method == "jdoctor" and block["kind"] not in TAGGED:
            continue
        for sentence in _sentences(block["body"]):
            subject, predicate = _subject_and_predicate(sentence)
            if not predicate:
                continue
            matched = simple_match(predicate)
            if not matched:
                continue
            if not matched["translation"]:
                untranslated.append({"sentence": sentence, "reason": matched["untranslated"]})
                continue
            words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", subject.lower()))
            checks.append(
                {
                    "method": method,
                    "kind": block["kind"],
                    "sentence": sentence,
                    "subject_words": sorted(words),
                    "translation": matched["translation"],
                    "span": matched["span"],
                }
            )
    return {
        "checks": checks,
        "untranslated": untranslated,
        "doctests": doctests,
        "tagged": tagged,
    }


def _target(check: dict, value):
    if check["kind"] in {"param", "raises"}:
        return None, "not_evaluable"
    words = set(check["subject_words"])
    if isinstance(value, dict):
        keys = [key for key in value if key.lower() in words]
        if check["method"] == "bind" and len(keys) == 1:
            return value[keys[0]], None
        if check["method"] == "bind" and len(keys) > 1:
            return None, "subject_unbound"
    if check["method"] == "jdoctor" and check["kind"] == "return":
        return value, None
    if check["kind"] == "return" and (not words or words & RESULT_WORDS):
        return value, None
    if words & RESULT_WORDS:
        return value, None
    return None, "subject_unbound"


def apply_check(check: dict, view: dict, observer: str) -> str:
    if not view.get("ok"):
        return "no_return"
    value = view.get("fine") if observer == "full" else view.get("coarse")
    target, reason = _target(check, value)
    if target is None and reason:
        return reason
    verdict = holds(check["translation"], target)
    if verdict is None:
        return "cannot_apply"
    return "alarm" if verdict is False else "clear"


def combine(classes: list[str]) -> str:
    present = set(classes)
    for name in PRIORITY:
        if name in present:
            return name
    return "no_check"


def classify_edges(ordinary_parent: str, ordinary_repair: str, edge_parent: str, edge_repair: str) -> str:
    if "alarm" in {ordinary_parent, ordinary_repair}:
        return "false_alarm"
    if edge_repair == "alarm" and edge_parent != "alarm":
        return "inversion"
    if edge_parent == "alarm" and edge_repair == "alarm":
        return "both_alarm"
    if edge_parent == "alarm" and edge_repair != "alarm":
        return "hit"
    if edge_parent == "clear" and edge_repair == "clear":
        return "both_clear"
    return "no_check"


def classify_rows(pairs: list[tuple[str, str]]) -> str:
    parent_only = False
    for parent, repair in pairs:
        if repair == "alarm" and parent != "alarm":
            return "inversion"
        if parent == "alarm" and repair == "alarm":
            return "both_alarm"
        if parent == "alarm" and repair != "alarm":
            parent_only = True
    if parent_only:
        return "hit"
    if pairs and all(parent == "clear" and repair == "clear" for parent, repair in pairs):
        return "both_clear"
    return "no_check"


def method_class(checks: list[dict], views: dict, shape: str) -> dict:
    if not checks:
        return {"class": "no_check", "checks": []}
    per_check = []
    for check in checks:
        if shape == "edges":
            outcomes = {
                name: apply_check(check, views[name], "full")
                for name in ("ordinary_parent", "ordinary_repair", "edge_parent", "edge_repair")
            }
            label = classify_edges(
                outcomes["ordinary_parent"],
                outcomes["ordinary_repair"],
                outcomes["edge_parent"],
                outcomes["edge_repair"],
            )
            coarse = {
                name: apply_check(check, views[name], "coarse")
                for name in ("edge_parent", "edge_repair")
            }
        else:
            outcomes = [
                (apply_check(check, parent, "full"), apply_check(check, repair, "full"))
                for parent, repair in views["pairs"]
            ]
            label = classify_rows(outcomes)
            coarse = None
        per_check.append(
            {
                "translation": check["translation"],
                "kind": check["kind"],
                "sentence": check["sentence"],
                "class": label,
                "full": outcomes,
                "coarse_edge": coarse,
            }
        )
    return {"class": combine([item["class"] for item in per_check]), "checks": per_check}


def status_class(views: dict, shape: str) -> str:
    def one(view: dict) -> str:
        return "alarm" if not view.get("ok") else "clear"

    if shape == "edges":
        return classify_edges(
            one(views["ordinary_parent"]),
            one(views["ordinary_repair"]),
            one(views["edge_parent"]),
            one(views["edge_repair"]),
        )
    return classify_rows([(one(parent), one(repair)) for parent, repair in views["pairs"]])


def skeleton(value) -> str:
    return re.sub(r"[A-Za-z]+", "a", re.sub(r"\d+", "0", str(value)))


def agora_invariants(parent_views: list[dict]) -> list[dict]:
    if len(parent_views) < 2:
        return []
    invariants = []
    if all(view.get("ok") for view in parent_views):
        invariants.append({
            "translation": "ok",
            "sentence": "parent rows all succeed",
            "kind": "return",
            "subject_words": ["ok"],
            "method": "agora",
            "agora": ("ok", "ok", True),
        })
    fines = [view.get("fine") for view in parent_views]
    if all(isinstance(item, dict) for item in fines):
        keys = set.intersection(*(set(item) for item in fines))
        for key in sorted(keys):
            column = [item[key] for item in fines]
            invariants.extend(_column_invariants(key, column))
    else:
        invariants.extend(_column_invariants("fine", fines))
    return invariants


def _column_invariants(name: str, column: list) -> list[dict]:
    found = []
    if all(item == column[0] for item in column):
        found.append(
            {
                "translation": f"equals:{name}:{column[0]!r}",
                "sentence": f"{name} constant on parent rows",
                "kind": "return",
                "subject_words": [name],
                "method": "agora",
                "agora": ("equals", name, column[0]),
            }
        )
    if all(isinstance(item, str) for item in column):
        form = skeleton(column[0])
        if all(skeleton(item) == form for item in column):
            found.append(
                {
                    "translation": f"skeleton:{name}:{form}",
                    "sentence": f"{name} skeleton on parent rows",
                    "kind": "return",
                    "subject_words": [name],
                    "method": "agora",
                    "agora": ("skeleton", name, form),
                }
            )
    return found


def apply_invariant(check: dict, view: dict) -> str:
    kind, name, constant = check["agora"]
    if kind == "ok":
        return "clear" if view.get("ok") else "alarm"
    if name == "fine":
        value = view.get("fine")
    else:
        fine = view.get("fine")
        if not isinstance(fine, dict) or name not in fine:
            return "cannot_apply"
        value = fine[name]
    if kind == "equals":
        return "clear" if value == constant else "alarm"
    return "clear" if isinstance(value, str) and skeleton(value) == constant else "alarm"


def agora_class(parent_views: list[dict], views: dict, shape: str) -> dict:
    checks = agora_invariants(parent_views)
    if not checks:
        return {"class": "no_check", "checks": [], "invariants": []}
    per_check = []
    for check in checks:
        if shape == "edges":
            outcomes = {name: apply_invariant(check, views[name]) for name in (
                "ordinary_parent", "ordinary_repair", "edge_parent", "edge_repair")}
            label = classify_edges(
                outcomes["ordinary_parent"], outcomes["ordinary_repair"],
                outcomes["edge_parent"], outcomes["edge_repair"])
        else:
            outcomes = [(apply_invariant(check, parent), apply_invariant(check, repair))
                        for parent, repair in views["pairs"]]
            label = classify_rows(outcomes)
        per_check.append({"translation": check["translation"], "class": label, "full": outcomes})
    return {
        "class": combine([item["class"] for item in per_check]),
        "checks": per_check,
        "invariants": [check["translation"] for check in checks],
    }


def audit(document: dict, parse_error: str | None, fetch_error: str | None, evaluable: bool) -> str:
    if fetch_error:
        return "fetch_failed"
    if parse_error:
        return "parse_error"
    if document["checks"] and evaluable:
        return "evaluable"
    if document["checks"]:
        return "not_evaluable"
    if document["tagged"]:
        return "catalog_gap"
    if document["doctests"]:
        return "doctest_only"
    return "doc_silent"


def decide(groups: list[dict]) -> dict:
    bind_hits = [group for group in groups if group["bind"] == "hit"]
    projects = {group["project"] for group in bind_hits}
    status_ids = {group["id"] for group in groups if group["status"] == "hit"}
    jdoctor_ids = {group["id"] for group in groups if group["jdoctor"] == "hit"}
    extra = [group for group in bind_hits if group["id"] not in status_ids]
    inversions = [group["id"] for group in groups if group["bind"] == "inversion"]
    false_alarms = [group["id"] for group in groups if group["bind"] == "false_alarm"]
    gap_projects = {group["project"] for group in groups if group["catalog_gap"]}
    keep = (
        len(projects) >= 2
        and len(extra) >= 1
        and any(group["id"] not in jdoctor_ids for group in extra)
        and not inversions
        and not false_alarms
    )
    if keep:
        decision, reason = "keep", "bind_separates_two_projects"
    elif inversions or false_alarms:
        decision, reason = "drop", "inversion" if inversions else "false_alarm"
    elif bind_hits and all(group["id"] in status_ids for group in bind_hits):
        decision, reason = "drop", "status_covers"
    elif bind_hits and all(group["id"] in jdoctor_ids for group in bind_hits):
        decision, reason = "drop", "baseline_covers"
    elif bind_hits and len(projects) == 1:
        decision, reason = "refine", "single_project"
    elif len(gap_projects) >= 2:
        decision, reason = "refine", "catalog_gap"
    else:
        decision, reason = "drop", "no_gain"
    return {
        "decision": decision,
        "reason": reason,
        "bind_hits": [group["id"] for group in bind_hits],
        "projects": sorted(projects),
        "inversions": inversions,
        "false_alarms": false_alarms,
        "catalog_gap_projects": sorted(gap_projects),
    }
