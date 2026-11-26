"""Qualitative gap analysis for the frozen contract-binding study.

Reads stored docs and replay. Does not score a new method and does not write
into contract_binding/.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
CONTRACT = ROOT / "research/release_drift_20261126/contract_binding"
DOCS = CONTRACT / "docs"
REPLAY = ROOT / "runs_independent_20261124/replay.json"
SUMMARY = CONTRACT / "results/summary.json"
FREEZE = [HERE / "protocol.md", HERE / "analyze.py"]
RESULTS = HERE / "results" / "analysis.json"

sys.path.insert(0, str(CONTRACT))
from binding import (  # noqa: E402
    _sentences,
    _subject_and_predicate,
    preprocess,
    split_blocks,
    strip_doctests,
    translate_document,
)
from jdoctor_patterns import holds, simple_match  # noqa: E402


DENOMINATOR = (
    "humanize-273",
    "humanize-254",
    "humanize-250",
    "humanize-218",
    "humanize-216",
    "prettytable-378",
    "prettytable-356",
    "prettytable-355",
    "prettytable-345",
    "more-itertools-1088",
    "more-itertools-1082",
    "rich-3718",
)

FOCAL = {
    "humanize-273": [
        'becomes "1.0 million"',
        "str: Friendly text representation as a string, unless the value passed could not",
        "be coaxed into an `int`",
        "Plural-Forms: nplurals=2; plural=(n > 1);",
        'msgstr[0] "million"',
        'msgstr[1] "millions"',
    ],
    "humanize-254": [
        "Return a precise representation of a timedelta",
        "a value of zero will be returned",
    ],
    "humanize-250": [
        "str: Human readable representation of a filesize",
        "If `True`, uses binary suffixes",
    ],
    "humanize-218": [
        "str: Human readable representation of a filesize",
        "'3.0 MB'",
    ],
    "humanize-216": [
        "str: Friendly text representation as a string, unless the value passed could not",
        "be coaxed into an `int`",
        'msgstr[0] "bilhão"',
        'msgstr[1] "bilhão"',
    ],
    "prettytable-378": [
        "should be an iterable of lists",
    ],
    "prettytable-356": [
        "Return string representation of table in current state",
        "bottom_left_junction_char -",
        "single character string used to draw bottom-left line junctions",
        "if False return an empty string",
        "header - print a header showing field names (True or False)",
    ],
    "prettytable-355": [
        "Return a new PrettyTable instance",
        "sortby - name of field to sort rows by",
    ],
    "prettytable-345": [
        "Return string representation of HTML formatted version of table in current",
    ],
    "more-itertools-1088": [
        "Return ``True`` if exactly ``n`` items in the iterable are ``True``",
    ],
    "more-itertools-1082": [
        "``ValueError`` will be raised if the given *element* isn't in the product",
    ],
    "rich-3718": [
        "Defaults to None",
        'The style of the panel (border and contents)',
        "Defaults to False",
    ],
}

CLASS_ZH = {
    "exception_versus_value": "异常与返回值不是同一类契约",
    "parent_doc_encodes_bug": "父文本把缺陷形式写成了译文",
    "implicit_visual_or_format": "隐含视觉或格式约定",
}


def assert_allowed(path: Path) -> None:
    text = str(path.resolve()).replace("\\", "/")
    if "sealed" in text.lower() or "/environment_receipts/" in text:
        raise SystemExit(f"refusing sealed path: {path}")
    allowed = {DOCS.resolve(), REPLAY.resolve(), SUMMARY.resolve(), CONTRACT.resolve()}
    if path.resolve() in allowed or path.resolve().parent == DOCS.resolve():
        return
    if str(path.resolve()).startswith(str(HERE.resolve())):
        return
    if path.resolve().parent == CONTRACT.resolve():
        return
    raise SystemExit(f"path is outside the analysis allowlist: {path}")


def read_text(path: Path) -> str:
    assert_allowed(path)
    return path.read_text(encoding="utf-8")


def read_json(path: Path):
    assert_allowed(path)
    return json.loads(read_text(path))


def file_sha(path: Path) -> str:
    assert_allowed(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def letter_words(value) -> set[str]:
    if value is None:
        return set()
    return set(re.findall(r"[^\W\d_]+", str(value), flags=re.UNICODE))


def whole_word(text: str, word: str) -> bool:
    return re.search(rf"(?i)(?<!\w){re.escape(word)}(?!\w)", text) is not None


def plural_entries(text: str) -> list[dict]:
    entries = []
    current = None
    for line in text.splitlines():
        if line.startswith("msgid ") and not line.startswith("msgid_plural"):
            if current and current["slots"]:
                entries.append(current)
            current = {"msgid": line.split(" ", 1)[1].strip().strip('"'), "slots": {}}
        elif line.startswith("msgstr[") and current is not None:
            index, rest = line[len("msgstr["):].split("]", 1)
            current["slots"][index.strip()] = rest.strip().strip('"')
    if current and current["slots"]:
        entries.append(current)
    return entries


def parent_doc_encodes_bug(text: str, parent_fine, repair_fine) -> dict:
    parent_only = letter_words(parent_fine) - letter_words(repair_fine)
    repair_only = letter_words(repair_fine) - letter_words(parent_fine)
    matched = []
    for entry in plural_entries(text):
        slots = [entry["slots"].get("0"), entry["slots"].get("1")]
        if None in slots or slots[0] != slots[1]:
            continue
        surface = slots[0]
        if surface in parent_only and repair_only and all(not whole_word(text, word) for word in repair_only):
            matched.append({"msgid": entry["msgid"], "slots": slots})
    return {
        "encoded": bool(matched),
        "entries": matched,
        "parent_only_words": sorted(parent_only),
        "repair_only_words": sorted(repair_only),
        "parent_only_words_in_doc": sorted(word for word in parent_only if whole_word(text, word)),
        "repair_only_words_in_doc": sorted(word for word in repair_only if whole_word(text, word)),
    }


def stop_reason(sentence: str) -> dict:
    subject, predicate = _subject_and_predicate(sentence)
    flags = []
    if re.search(r"(?i)should be", sentence):
        flags.append("positive_should_not_rewritten")
    if not predicate:
        none_word = re.search(r"(?i)\bnone\b", sentence)
        if none_word:
            reason = "python_none_without_catalog_verb"
        elif re.search(r"(?i)\b(true|false|null|zero|positive|negative|empty)\b", sentence):
            reason = "quality_without_catalog_verb"
        elif re.search(r"(?i)\bbecomes\b", sentence):
            reason = "verb_outside_catalog"
        else:
            reason = "no_catalog_verb"
        return {"stop": reason, "flags": flags, "subject": subject, "predicate": predicate, "translation": None}
    matched = simple_match(predicate)
    if matched and matched.get("translation"):
        return {
            "stop": "translated",
            "flags": flags,
            "subject": subject,
            "predicate": predicate,
            "translation": matched["translation"],
        }
    if matched and matched.get("untranslated"):
        return {
            "stop": "untranslated_" + str(matched["untranslated"]),
            "flags": flags,
            "subject": subject,
            "predicate": predicate,
            "translation": None,
        }
    verb = re.search(
        r"(?i)(?<![A-Za-z])(is equal to|are equal to|equals to|returns|return|is|are|be)(?![A-Za-z])",
        predicate,
    )
    after = predicate[verb.end():] if verb else ""
    quality = re.search(r"(?i)\b(true|false|null|none|zero|positive|negative|empty)\b", after)
    if quality and quality.group(1).lower() == "none" and after[: quality.start()].strip(" ") == "":
        reason = "python_none_not_catalog_null"
    elif quality and quality.start() > 1 and after[: quality.start()].strip(" "):
        reason = "tokens_between_verb_and_quality"
    elif re.search(r"(?i)\b(zero|none)\b|\d", subject or ""):
        reason = "quantity_before_verb"
    else:
        reason = "verb_without_quality"
    return {"stop": reason, "flags": flags, "subject": subject, "predicate": predicate, "translation": None}


def locate_quote(raw: str, quote: str) -> dict:
    if quote not in raw:
        raise SystemExit(f"quote is not in the stored document: {quote}")
    stripped, _doctests = strip_doctests(raw)
    prepared = preprocess(stripped)
    prepared_quote = preprocess(quote).strip()
    if quote not in prepared and prepared_quote not in prepared:
        return {
            "quote": quote,
            "in_translated_text": False,
            "stop": "removed_before_match",
            "flags": ["doctest_not_applied"],
            "sentence": None,
            "kind": None,
        }
    for block in split_blocks(prepared):
        body = block["body"]
        if quote not in body and prepared_quote not in body:
            continue
        for sentence in _sentences(body):
            if quote in sentence or (prepared_quote and prepared_quote in sentence):
                found = stop_reason(sentence)
                found.update(quote=quote, in_translated_text=True, sentence=sentence, kind=block["kind"])
                return found
        fragment = next((sentence for sentence in _sentences(body) if "becomes" in sentence.lower()), None)
        return {
            "quote": quote,
            "in_translated_text": True,
            "stop": "period_splits_illustration",
            "flags": ["verb_outside_catalog"] if fragment else [],
            "sentence": fragment,
            "kind": block["kind"],
            "translation": None,
        }
    raise SystemExit(f"quote survived preprocessing but no block contained it: {quote}")


def sentence_binds_drift(raw: str, repair_fine, parent_fine, ordinary_parent, ordinary_repair) -> bool:
    stripped, _doctests = strip_doctests(raw)
    prepared = preprocess(stripped)
    repair_text = str(repair_fine)
    for block in split_blocks(prepared):
        for sentence in _sentences(block["body"]):
            if sentence.lstrip().startswith(("msgid", "msgstr")):
                continue
            found = stop_reason(sentence)
            if found["stop"] == "translated":
                continue
            if repair_text and repair_text in sentence:
                return True
            if not found["predicate"]:
                continue
            matched = simple_match(found["predicate"])
            translation = matched.get("translation") if matched else None
            if not translation:
                continue
            verdicts = [holds(translation, value) for value in (repair_fine, parent_fine, ordinary_parent, ordinary_repair)]
            if verdicts == [True, False, True, True]:
                return True
    return False


def edge_pair(outcome: dict) -> dict:
    parent = outcome["parent_rows"]
    repair = outcome["fixed_rows"]
    if len(parent) != 2 or len(repair) != 2:
        raise SystemExit(f"edge case {outcome['pr']} does not have two rows on each side")

    def view(row):
        actual = row["actual"]
        if actual.get("ok"):
            return {"ok": True, "fine": actual.get("fine"), "coarse": actual.get("coarse"), "input": row.get("input")}
        return {"ok": False, "fine": None, "coarse": None, "input": row.get("input"), "error": actual.get("error")}

    return {
        "ordinary_parent": view(parent[0]),
        "edge_parent": view(parent[1]),
        "ordinary_repair": view(repair[0]),
        "edge_repair": view(repair[1]),
    }


def classify_group(views: dict, encoded: bool) -> str:
    parent = views["edge_parent"]
    repair = views["edge_repair"]
    if not parent["ok"] and repair["ok"]:
        return "exception_versus_value"
    blind = (
        parent["ok"]
        and repair["ok"]
        and parent["coarse"] == repair["coarse"]
        and parent["fine"] != repair["fine"]
    )
    if not blind:
        raise SystemExit("group is neither an exception boundary nor a blind full-value difference")
    if encoded:
        return "parent_doc_encodes_bug"
    return "implicit_visual_or_format"


def counterfactual_backticks(views: dict) -> dict:
    raw = "Return ``True`` if exactly ``n`` items in the iterable are ``True``"
    prepared = preprocess(raw.replace("``", "").replace("`", ""))
    _subject, predicate = _subject_and_predicate(prepared)
    matched = simple_match(predicate)
    translation = matched.get("translation") if matched else None

    def verdict(view):
        if not view["ok"]:
            return "no_return"
        result = holds(translation, view["fine"])
        if result is None:
            return "cannot_apply"
        return "clear" if result else "alarm"

    outcomes = {name: verdict(views[name]) for name in views}
    inversion = (
        outcomes["ordinary_parent"] == "clear"
        and outcomes["ordinary_repair"] == "clear"
        and outcomes["edge_parent"] != "alarm"
        and outcomes["edge_repair"] == "alarm"
    )
    return {
        "candidate": "strip_backticks_then_simple_match",
        "executed_as_score": False,
        "transcription": "Toradocu 3.0 simpleMatch after deleting backticks; not the original Jdoctor program",
        "prepared_sentence": prepared,
        "translation": translation,
        "outcomes_on_stored_returns": outcomes,
        "walkthrough_class": "inversion" if inversion else "not_inversion",
        "separates_blind_group": False,
        "stop": "unconditional ==true alarms the stored repair return False; the group is an exception boundary",
    }


def counterfactual_should(sentence: str) -> dict:
    rewritten = re.sub(r"(?i)should be", " is ", sentence)
    prepared = preprocess(rewritten)
    _subject, predicate = _subject_and_predicate(prepared)
    matched = simple_match(predicate) if predicate else None
    translation = matched.get("translation") if matched else None
    return {
        "candidate": "rewrite_positive_should_be",
        "executed_as_score": False,
        "prepared_sentence": prepared,
        "translation": translation,
        "separates_blind_group": False,
        "stop": "after the rewrite, simpleMatch still has no quality word; the group throws and the record has no structured arguments",
    }


def counterfactual_gettext(text: str, parent_fine, repair_fine) -> dict:
    encoding = parent_doc_encodes_bug(text, parent_fine, repair_fine)
    return {
        "candidate": "execute_gettext_plural_slots",
        "executed_as_score": False,
        "executed": False,
        "slots_that_repeat_parent_word": encoding["entries"],
        "separates_blind_group": False,
        "stop": (
            "parent slots both state the parent surface form"
            if encoding["encoded"]
            else "the stored text does not identify the printed coefficient as n, so the slot pair was not executed"
        ),
    }


def frozen_summary_agreement(summary: dict) -> None:
    primary = summary["primary_classes"]
    if list(primary) != list(DENOMINATOR):
        raise SystemExit("frozen summary denominator does not match the public 12")
    for case_id, row in primary.items():
        if row["bind"] != "no_check" or row["jdoctor_pattern"] != "no_check":
            raise SystemExit(f"frozen summary is not the zero-check result this analysis cites: {case_id}")


def build_analysis() -> dict:
    summary = read_json(SUMMARY)
    frozen_summary_agreement(summary)
    replay = {item["pr"]: item for item in read_json(REPLAY)["outcomes"]}
    hashes = {name: file_sha(CONTRACT / name) for name in summary["hashes"]}
    if hashes != summary["hashes"]:
        raise SystemExit("frozen contract_binding files no longer match the archived hashes")
    cases = []
    check_counts = {}
    for case_id in DENOMINATOR:
        pr = int(case_id.rsplit("-", 1)[1])
        raw = read_text(DOCS / f"{case_id}.txt")
        views = edge_pair(replay[pr])
        bind_doc = translate_document(raw, "bind")
        jdoctor_doc = translate_document(raw, "jdoctor")
        if bind_doc["checks"] or jdoctor_doc["checks"]:
            raise SystemExit(f"frozen translator emitted a check for {case_id}")
        check_counts[case_id] = {
            "bind": len(bind_doc["checks"]),
            "jdoctor_pattern": len(jdoctor_doc["checks"]),
            "doctests_removed": bind_doc["doctests"],
            "tagged_section": bind_doc["tagged"],
        }
        encoded = parent_doc_encodes_bug(raw, views["edge_parent"]["fine"], views["edge_repair"]["fine"])
        drift_class = classify_group(views, encoded["encoded"])
        published = summary["primary_classes"][case_id]["published_observer"]
        blind = drift_class != "exception_versus_value"
        if blind:
            expected = {"status": "both_clear", "coarse": "both_clear", "full": "hit"}
        else:
            expected = {"status": "hit", "coarse": "hit", "full": "hit"}
        if published != expected:
            raise SystemExit(f"replay division disagrees with the frozen observer for {case_id}")
        justifies = False
        if blind:
            justifies = sentence_binds_drift(
                raw,
                views["edge_repair"]["fine"],
                views["edge_parent"]["fine"],
                views["ordinary_parent"]["fine"],
                views["ordinary_repair"]["fine"],
            )
        focal = [locate_quote(raw, quote) for quote in FOCAL[case_id]]
        cases.append({
            "id": case_id,
            "pr": pr,
            "drift_class": drift_class,
            "drift_class_zh": CLASS_ZH[drift_class],
            "blind": blind,
            "justifies_scoring_protocol": justifies,
            "normalization_separates_blind_group": False,
            "views": views,
            "gettext": encoded,
            "focal": focal,
            "frozen_audit": summary["primary_classes"][case_id]["audit"],
        })
    by_id = {case["id"]: case for case in cases}
    counterfactuals = [
        counterfactual_backticks(by_id["more-itertools-1088"]["views"]),
        counterfactual_should(FOCAL["prettytable-378"][0]),
        counterfactual_gettext(
            read_text(DOCS / "humanize-216.txt"),
            by_id["humanize-216"]["views"]["edge_parent"]["fine"],
            by_id["humanize-216"]["views"]["edge_repair"]["fine"],
        ),
        counterfactual_gettext(
            read_text(DOCS / "humanize-273.txt"),
            by_id["humanize-273"]["views"]["edge_parent"]["fine"],
            by_id["humanize-273"]["views"]["edge_repair"]["fine"],
        ),
    ]
    for case in cases:
        case["normalization_separates_blind_group"] = False
    decision = decide(cases, counterfactuals)
    return {
        "new_scoring_run": False,
        "ranking": None,
        "frozen_study_commit": summary["freeze_commit"],
        "frozen_hashes_match": True,
        "translator": "frozen Toradocu 3.0 simpleMatch transcription; original Jdoctor was not run",
        "not_run": summary["not_run"],
        "check_counts": check_counts,
        "decision": decision,
        "counterfactuals": counterfactuals,
        "cases": cases,
    }


def decide(cases: list[dict], counterfactuals: list[dict] | None = None) -> dict:
    justifying = [case["id"] for case in cases if case.get("justifies_scoring_protocol")]
    separating = [case["id"] for case in cases if case.get("normalization_separates_blind_group")]
    if counterfactuals:
        separating.extend(
            item["candidate"] for item in counterfactuals if item.get("separates_blind_group")
        )
    if justifying:
        decision, reason = "keep", "stated_predicate_of_recorded_drift"
    elif separating:
        decision, reason = "refine", "local_normalization_separates_blind_group"
    else:
        decision, reason = "drop", "recorded_drift_not_stated_as_predicate"
    return {
        "decision": decision,
        "reason": reason,
        "justifying_groups": justifying,
        "separating_normalizations": separating,
        "new_scoring_run": False,
    }


def freeze_ready() -> str:
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--", *[str(path) for path in FREEZE]],
        cwd=ROOT,
        text=True,
    )
    if dirty.strip():
        raise SystemExit("analysis protocol has uncommitted changes; refusing to write results\n" + dirty)
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def main() -> None:
    head = freeze_ready()
    report = build_analysis()
    report["protocol_commit"] = head
    report["protocol_sha256"] = file_sha(HERE / "protocol.md")
    RESULTS.parent.mkdir(exist_ok=True)
    assert_allowed(RESULTS)
    RESULTS.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "decision": report["decision"],
        "new_scoring_run": False,
        "protocol_commit": head,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
