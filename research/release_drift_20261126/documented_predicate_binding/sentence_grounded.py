"""Conservative sentence-grounded checks, inclusion detector, and decision rule.

Operational definition frozen with protocol.md. This module does not read repair
outputs, gold tables, or call arguments. `jdoctor_pattern` elsewhere is the
Toradocu 3.0 simpleMatch transcription, not original Jdoctor.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path


_CONTRACT = Path(__file__).resolve().parents[1] / "contract_binding"
if str(_CONTRACT) not in sys.path:
    sys.path.insert(0, str(_CONTRACT))

from binding import apply_check as bind_apply_check  # noqa: E402
from binding import combine, strip_doctests, translate_document  # noqa: E402
from jdoctor_patterns import holds  # noqa: E402


MIN_SCORED = 6
NOT_RUN = (
    {
        "name": "Jdoctor",
        "reason": "Java source in, Java expressions out. jdoctor_pattern only transcribes Toradocu 3.0 simpleMatch.",
    },
    {
        "name": "SPARK",
        "reason": "These cases have no SPARK/Ada contracts.",
    },
    {
        "name": "Gay et al. 2015",
        "reason": "No mutants are generated and no expected-value oracle is given to an extractor.",
    },
    {
        "name": "AGORA+",
        "reason": "The REST/Daikon tool is not run.",
    },
    {
        "name": "SpecFuzzer",
        "reason": "Java trace fuzzing is not run.",
    },
    {
        "name": "Hypothesis",
        "reason": "Would synthesize new inputs. The frozen synthesizer stays paused.",
    },
)

_EXECUTABLE = {"hit", "inversion", "both_alarm", "both_clear", "false_alarm"}
_SUBJECT_OK = {
    "the", "a", "an", "this", "it", "value", "result", "output", "return",
    "returned", "function", "method", "always", "will", "must", "shall",
    "then", "also", "still", "call",
}
_TRAILING = {
    "integer", "int", "number", "float", "value", "string", "str", "bool",
    "boolean", "object", "result", "output",
}
_PHRASES = (
    ("greater than or equal to", ">="),
    ("less than or equal to", "<="),
    ("greater than", ">"),
    ("less than", "<"),
    ("at least", ">="),
    ("at most", "<="),
    ("equal to", "=="),
)
_QUALITIES = (
    ("strictly positive", ">0"),
    ("strictly negative", "<0"),
    ("non-negative", ">=0"),
    ("non-positive", "<=0"),
    ("nonnegative", ">=0"),
    ("nonpositive", "<=0"),
    ("positive", ">0"),
    ("negative", "<0"),
    ("true", "==true"),
    ("false", "==false"),
    ("none", "==null"),
    ("null", "==null"),
    ("zero", "==0"),
)
_QUALITY_RE = (
    "strictly positive|strictly negative|non-negative|non-positive|"
    "nonnegative|nonpositive|positive|negative|true|false|null|none|zero"
)
_HEDGE = re.compile(r"(?i)(?<![A-Za-z])(?:should|could|might|may|can)(?![A-Za-z])")
_COND = re.compile(
    r"(?i)(?<![A-Za-z])(?:if|when|unless|whether|provided|otherwise)(?![A-Za-z])|"
    r"\bon (?:success|failure|error)\b"
)
_NEG = re.compile(r"(?i)(?<![A-Za-z])(?:not|never)(?![A-Za-z])")
_RAISE = re.compile(
    r"(?i)(?<![A-Za-z])(?:raising|raises|raised|raise|thrown|throws|throw)(?![A-Za-z])"
)
_EXC = re.compile(
    r"\b([A-Z][A-Za-z0-9]*(?:Error|Exception|Warning)|StopIteration|"
    r"StopAsyncIteration|GeneratorExit|KeyboardInterrupt|SystemExit)\b"
)
_VERB = re.compile(r"(?i)(?<![A-Za-z])(returns|return|equals|is|are|be)(?![A-Za-z])")
_OBL_VERB = re.compile(
    r"(?i)(?<![A-Za-z])(returns|return|equals|is|are|be|must|shall|will)(?![A-Za-z])"
)
_SKIP = re.compile(
    r"(?i)^(a|an|the|value|result|output|of|to|always|number|string|str|int|"
    r"integer|float|bool|boolean)\b"
)
_QUOTE = re.compile(r"\"([^\"\\]|\\.)*\"|'([^'\\]|\\.)*'")
_FENCE = re.compile(r"(?ms)^[ \t]*(```|~~~).*?^[ \t]*\1[ \t]*\n?")
_BEHAVIOR_WORDS = re.compile(
    r"(?i)(?<![A-Za-z])(?:raise|raises|raised|exception|return|returns|incorrect|"
    r"wrong|crash|negative|positive|zero|invalid|overflow|underflow)(?![A-Za-z])|"
    r"out of range|off-by-one|greater than|less than"
)


def strip_fences(text: str) -> str:
    return _FENCE.sub("", text or "")


def prepare_document(text: str) -> str:
    cleaned = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    cleaned = strip_fences(cleaned)
    cleaned, _doctests = strip_doctests(cleaned)
    cleaned = re.sub(r"(?<!\n)\n(?!\n)", " ", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    return cleaned


def split_sentences(text: str) -> list[str]:
    """Sentence slices after joining wrapped lines. Decimal points stay inside numbers."""
    prepared = prepare_document(text)
    sentences = []
    boundary = re.compile(r"(?<!\d)\.(?=\s|$)|(?<=\d)\.(?=\s+[A-Z]|\s*$)|[!?](?=\s|$)")
    for paragraph in re.split(r"\n+", prepared):
        start = 0
        for match in boundary.finditer(paragraph):
            piece = paragraph[start:match.end()].strip()
            if piece:
                sentences.append(piece)
            start = match.end()
        tail = paragraph[start:].strip()
        if tail:
            sentences.append(tail)
    return sentences


def strip_markup(text: str) -> str:
    stripped = re.sub(
        r":[A-Za-z][A-Za-z0-9_]*:`~?([^`]+)`",
        lambda match: match.group(1).split(".")[-1],
        text or "",
    )
    stripped = re.sub(r"``([^`]*)``", r"\1", stripped)
    stripped = re.sub(r"`([^`]*)`", r"\1", stripped)
    stripped = re.sub(r"\*(\w+)\*", r"\1", stripped)
    return re.sub(r"\s+", " ", stripped).strip()


def _without_quotes(text: str) -> str:
    return _QUOTE.sub(" ", text)


def _norm_number(token: str) -> str:
    if re.fullmatch(r"-?\d+", token):
        return str(int(token))
    return token


def negate_translation(translation: str) -> str:
    flips = {
        "==true": "!=true",
        "!=true": "==true",
        "==false": "!=false",
        "!=false": "==false",
        "==null": "!=null",
        "!=null": "==null",
        ">0": "<=0",
        "<0": ">=0",
        ">=0": "<0",
        "<=0": ">0",
    }
    if translation in flips:
        return flips[translation]
    match = re.fullmatch(r"(<=|>=|<|>|!=|==)(-?\d+(?:\.\d+)?)", translation)
    if not match:
        return translation
    inverse = {"==": "!=", "!=": "==", ">": "<=", "<": ">=", ">=": "<", "<=": ">"}
    return inverse[match.group(1)] + match.group(2)


def _subject_ok(before: str) -> bool:
    words = re.findall(r"[A-Za-z]+", before.lower())
    return all(word in _SUBJECT_OK for word in words)


def _skip_gap(text: str) -> tuple[str, bool]:
    negated = False
    while True:
        text = text.lstrip(" \t:,")
        negation = re.match(r"(?i)^(not|never)\b", text)
        if negation:
            negated = not negated
            text = text[negation.end():]
            continue
        skip = _SKIP.match(text)
        if skip:
            text = text[skip.end():]
            continue
        return text, negated


def _match_predicate(text: str):
    raw = text.lstrip()
    lowered = raw.lower()
    for phrase, operator in _PHRASES:
        if lowered.startswith(phrase):
            after = raw[len(phrase):].lstrip()
            number = re.match(r"(-?\d+(?:\.\d+)?)(?!\d)(?!\.\d)", after)
            if number:
                return f"{operator}{_norm_number(number.group(1))}", None, after[number.end():]
            return None
    operator = re.match(r"(<=|>=|==|!=|<|>)\s*(-?\d+(?:\.\d+)?)(?!\d)(?!\.\d)", raw)
    if operator:
        return f"{operator.group(1)}{_norm_number(operator.group(2))}", None, raw[operator.end():]
    for word, translation in _QUALITIES:
        found = re.match(rf"(?i)^{re.escape(word)}(?![A-Za-z])", raw)
        if found:
            return translation, None, raw[found.end():]
    literal = re.match(r"^(True|False|None)\b", raw)
    if literal:
        mapped = {"True": "==true", "False": "==false", "None": "==null"}[literal.group(1)]
        return mapped, None, raw[literal.end():]
    quoted = _QUOTE.match(raw)
    if quoted:
        value = ast.literal_eval(quoted.group(0))
        if isinstance(value, str):
            return "==str", value, raw[quoted.end():]
        return None
    number = re.match(r"^(-?\d+(?:\.\d+)?)(?!\d)(?!\.\d)", raw)
    if number:
        return "==" + _norm_number(number.group(1)), None, raw[number.end():]
    return None


def _trailing_ok(remainder: str) -> bool:
    text = remainder.strip().strip(".;:!")
    text = text.strip().strip(".;:!")
    return text == "" or text.lower() in _TRAILING


def _value_from_sentence(cleaned: str):
    found = []
    for match in _VERB.finditer(cleaned):
        if not _subject_ok(cleaned[:match.start()]):
            continue
        rest, negated = _skip_gap(cleaned[match.end():])
        parsed = _match_predicate(rest)
        if not parsed:
            continue
        translation, literal, remainder = parsed
        if not _trailing_ok(remainder):
            continue
        if negated:
            translation = "!=str" if translation == "==str" else negate_translation(translation)
        found.append((translation, literal))
    if len(found) != 1:
        return None
    translation, literal = found[0]
    return {
        "kind": "value",
        "translation": translation,
        "literal": literal,
        "exc_type": None,
    }


def _exception_from_sentence(cleaned: str):
    if _NEG.search(cleaned) or not _RAISE.search(cleaned):
        return None
    names = []
    for name in _EXC.findall(_without_quotes(cleaned)):
        if name not in names:
            names.append(name)
    if len(names) != 1:
        return None
    return {"kind": "exception", "translation": None, "literal": None, "exc_type": names[0]}


def sentence_check(cleaned: str):
    """One unconditional check, or None. Conditionals and hedges emit nothing."""
    if not cleaned or _COND.search(cleaned) or _HEDGE.search(cleaned):
        return None
    exception = _exception_from_sentence(cleaned)
    value = _value_from_sentence(cleaned)
    if exception and value:
        return None
    return exception or value


def extract(text: str) -> list[dict]:
    """Executable checks from a parent document. No arguments and no repair values."""
    checks = []
    for sentence in split_sentences(text):
        check = sentence_check(strip_markup(sentence))
        if check:
            check["sentence"] = sentence
            checks.append(check)
    return checks


def _has_comparison(cleaned: str) -> bool:
    if re.search(r"(<=|>=|<|>)", cleaned):
        return bool(re.search(r"-?\d+(?:\.\d+)?", cleaned))
    for phrase, _operator in _PHRASES:
        if phrase in cleaned.lower() and re.search(r"-?\d+(?:\.\d+)?", cleaned):
            return True
    return False


def _has_literal(cleaned: str) -> bool:
    if re.search(r"\b(?:True|False|None)\b", cleaned):
        return True
    if _QUOTE.search(cleaned):
        return True
    return bool(re.search(r"(?<![\d.])-?\d+(?:\.\d+)?(?!\d)(?!\.\d)", cleaned))


def is_obligation(cleaned: str) -> bool:
    """Inclusion detector. Conditionals and hedges still count; extract() does not emit them."""
    if _RAISE.search(cleaned) and _EXC.search(_without_quotes(cleaned)):
        return True
    if not _OBL_VERB.search(cleaned):
        return False
    if re.search(rf"(?i)(?<![A-Za-z])(?:{_QUALITY_RE})(?![A-Za-z])", cleaned):
        return True
    if _has_comparison(cleaned) or _has_literal(cleaned):
        return True
    return False


def obligation_sentences(text: str) -> list[str]:
    return [sentence for sentence in split_sentences(text) if is_obligation(strip_markup(sentence))]


def apply_grounded(check: dict, observation: dict) -> str:
    if check["kind"] == "exception":
        if observation.get("ok"):
            return "alarm"
        return "clear" if observation.get("exc_type") == check["exc_type"] else "alarm"
    if not observation.get("ok"):
        return "no_return"
    if observation.get("jsonable") is False:
        return "cannot_apply"
    value = observation.get("value")
    if check["translation"] in {"==str", "!=str"}:
        if not isinstance(value, str):
            return "cannot_apply"
        same = value == check["literal"]
        holds_now = same if check["translation"] == "==str" else (not same)
        return "clear" if holds_now else "alarm"
    verdict = holds(check["translation"], value)
    if verdict is None:
        return "cannot_apply"
    return "clear" if verdict else "alarm"


def classify_outcomes(parent: str, fix: str, ordinary_parent: str | None = None,
                      ordinary_fix: str | None = None) -> str:
    """Strict form of the contract-binding labels.

    A hit requires the fix side to be clear. contract_binding treats any
    non-alarm on the fix side as a hit; this study does not.
    """
    if ordinary_parent == "alarm" or ordinary_fix == "alarm":
        return "false_alarm"
    if fix == "alarm" and parent != "alarm":
        return "inversion"
    if parent == "alarm" and fix == "alarm":
        return "both_alarm"
    if parent == "alarm" and fix == "clear":
        return "hit"
    if parent == "clear" and fix == "clear":
        return "both_clear"
    return "no_check"


def _pair_summary(labels: list[str]) -> dict:
    combined = combine(labels) if labels else "no_check"
    return {
        "class": combined,
        "executable": combined in _EXECUTABLE,
        "separates": combined == "hit",
    }


def summarize_grounded(text: str, parent: dict, fix: dict, ordinary=None) -> dict:
    per = []
    for check in extract(text):
        parent_out = apply_grounded(check, parent)
        fix_out = apply_grounded(check, fix)
        ordinary_parent = ordinary_fix = None
        if ordinary is not None:
            ordinary_parent = apply_grounded(check, ordinary["parent"])
            ordinary_fix = apply_grounded(check, ordinary["fix"])
        per.append({
            "class": classify_outcomes(parent_out, fix_out, ordinary_parent, ordinary_fix),
            "parent": parent_out,
            "fix": fix_out,
            "sentence": check["sentence"],
            "kind": check["kind"],
            "translation": check["translation"],
            "literal": check["literal"],
            "exc_type": check["exc_type"],
        })
    summary = _pair_summary([item["class"] for item in per])
    summary["checks"] = per
    return summary


def _view(observation: dict) -> dict:
    if not observation.get("ok") or observation.get("jsonable") is False:
        return {"ok": False, "fine": None, "coarse": None}
    value = observation.get("value")
    return {"ok": True, "fine": value, "coarse": value}


def summarize_translated(method: str, text: str, parent: dict, fix: dict, ordinary=None) -> dict:
    """Unchanged contract_binding translator. method is bind or jdoctor_pattern."""
    name = "jdoctor" if method == "jdoctor_pattern" else "bind"
    document = translate_document(text, name)
    per = []
    for check in document["checks"]:
        def outcome(observation: dict) -> str:
            if observation.get("jsonable") is False and observation.get("ok"):
                return "cannot_apply"
            return bind_apply_check(check, _view(observation), "full")

        parent_out = outcome(parent)
        fix_out = outcome(fix)
        ordinary_parent = ordinary_fix = None
        if ordinary is not None:
            ordinary_parent = outcome(ordinary["parent"])
            ordinary_fix = outcome(ordinary["fix"])
        per.append({
            "class": classify_outcomes(parent_out, fix_out, ordinary_parent, ordinary_fix),
            "parent": parent_out,
            "fix": fix_out,
            "sentence": check.get("sentence"),
            "translation": check.get("translation"),
            "kind": check.get("kind"),
        })
    summary = _pair_summary([item["class"] for item in per])
    summary["checks"] = per
    summary["tagged"] = document["tagged"]
    summary["doctests"] = document["doctests"]
    return summary


def status_outcome(observation: dict) -> str:
    return "clear" if observation.get("ok") else "alarm"


def summarize_status(parent: dict, fix: dict, ordinary=None) -> dict:
    ordinary_parent = ordinary_fix = None
    if ordinary is not None:
        ordinary_parent = status_outcome(ordinary["parent"])
        ordinary_fix = status_outcome(ordinary["fix"])
    label = classify_outcomes(
        status_outcome(parent), status_outcome(fix), ordinary_parent, ordinary_fix
    )
    return {"class": label, "executable": True, "separates": label == "hit"}


def canonical(observation: dict) -> str:
    if not observation.get("ok"):
        payload = {
            "kind": "exception",
            "type": observation.get("exc_type"),
            "message": observation.get("message"),
        }
    elif observation.get("jsonable") is False:
        payload = {"kind": "repr", "repr": observation.get("repr")}
    else:
        payload = {"kind": "return", "value": observation.get("value")}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def full_separates(parent: dict, fix: dict) -> bool:
    return canonical(parent) != canonical(fix)


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def quote_in_document(quote: str, document: str) -> bool:
    return normalized(quote) in normalized(document)


def _number_in(number, text: str) -> bool:
    token = _norm_number(str(number)) if not isinstance(number, float) else str(number)
    if isinstance(number, float) or (isinstance(number, str) and "." in str(number)):
        token = str(number)
    pattern = rf"(?<![\d.]){re.escape(str(number))}(?!\d)(?!\.\d)"
    if re.search(pattern, text):
        return True
    if isinstance(number, int) and not isinstance(number, bool):
        return re.search(rf"(?<![\d.]){number}(?!\d)(?!\.\d)", text) is not None
    return token in text


def _literal_in_sentence(value, text: str) -> bool:
    if isinstance(value, bool):
        word = "true" if value else "false"
        return re.search(rf"(?i)(?<![A-Za-z]){word}(?![A-Za-z])", text) is not None
    if value is None:
        return re.search(r"(?i)(?<![A-Za-z])(?:none|null)(?![A-Za-z])", text) is not None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _number_in(value, text)
    if isinstance(value, str):
        return value in text
    return False


def _relation_in_sentence(relation: str, number, text: str) -> bool:
    if not _number_in(number, text):
        return False
    lowered = text.lower()
    zero = number == 0
    bare_lt = re.search(r"(?<!<)<(?!=)", text) is not None
    bare_gt = re.search(r"(?<!>)>(?!=)", text) is not None
    if relation == "<":
        return bare_lt or ("less than" in lowered and "or equal" not in lowered) or (zero and _word(lowered, "negative"))
    if relation == ">":
        return bare_gt or ("greater than" in lowered and "or equal" not in lowered) or (zero and _word(lowered, "positive"))
    if relation == "<=":
        return "<=" in text or "at most" in lowered or "less than or equal" in lowered
    if relation == ">=":
        return (
            ">=" in text or "at least" in lowered or "greater than or equal" in lowered
            or (zero and ("non-negative" in lowered or _word(lowered, "nonnegative")))
        )
    if relation == "==":
        return "==" in text or "equal" in lowered or (zero and _word(lowered, "zero"))
    if relation == "!=":
        return "!=" in text or "not equal" in lowered
    return False


def _word(text: str, word: str) -> bool:
    return re.search(rf"(?i)(?<![A-Za-z-]){re.escape(word)}(?![A-Za-z-])", text) is not None


def _translation_in_sentence(translation: str, text: str) -> bool:
    if not isinstance(translation, str):
        return False
    lowered = text.lower()
    if translation in {"==true", "!=true"}:
        present = _word(lowered, "true")
    elif translation in {"==false", "!=false"}:
        present = _word(lowered, "false")
    elif translation in {"==null", "!=null"}:
        present = _word(lowered, "none") or _word(lowered, "null")
    elif translation == ">0":
        present = (_word(lowered, "positive") and not _NEG.search(text)) or re.search(r"(?<!>)>(?!=)", text) is not None
    elif translation == "<0":
        present = (_word(lowered, "negative") and not _NEG.search(text)) or re.search(r"(?<!<)<(?!=)", text) is not None
    elif translation == ">=0":
        present = (
            "non-negative" in lowered or _word(lowered, "nonnegative") or ">=" in text
            or (bool(_NEG.search(text)) and _word(lowered, "negative"))
        )
    elif translation == "<=0":
        present = (
            "non-positive" in lowered or _word(lowered, "nonpositive") or "<=" in text
            or (bool(_NEG.search(text)) and _word(lowered, "positive"))
        )
    else:
        present = False
    if translation in {"==true", "!=true", "==false", "!=false", "==null", "!=null", ">0", "<0", ">=0", "<=0"}:
        if not present:
            return False
        if translation.startswith("!="):
            return _NEG.search(text) is not None
        return True
    match = re.fullmatch(r"(<=|>=|<|>|!=|==)(-?\d+(?:\.\d+)?)", translation)
    if not match:
        return False
    number = float(match.group(2)) if "." in match.group(2) else int(match.group(2))
    return _relation_in_sentence(match.group(1), number, text)


def _audit_when(when, text: str) -> bool:
    if not isinstance(when, dict):
        return False
    if "all" in when:
        return isinstance(when["all"], list) and bool(when["all"]) and all(_audit_when(item, text) for item in when["all"])
    if "any" in when:
        return isinstance(when["any"], list) and bool(when["any"]) and all(_audit_when(item, text) for item in when["any"])
    name = when.get("input")
    if not isinstance(name, str) or not re.search(rf"(?i)(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", text):
        return False
    if when.get("relation") == "==" and "value" in when:
        return _literal_in_sentence(when["value"], text)
    if "relation" not in when or "number" not in when:
        return False
    return _relation_in_sentence(when["relation"], when["number"], text)


def audit_human(expr, sentence: str) -> bool:
    """Every literal in a human ceiling check must occur in the included sentence."""
    if expr is None:
        return True
    if not isinstance(expr, dict):
        return False
    text = strip_markup(sentence)
    if "when" in expr and not _audit_when(expr["when"], text):
        return False
    op = expr.get("op")
    if op == "raises":
        return isinstance(expr.get("type"), str) and re.search(rf"\b{re.escape(expr['type'])}\b", text) is not None
    if op == "return_equals":
        return _literal_in_sentence(expr.get("value"), text)
    if op == "return_compare":
        return _relation_in_sentence(expr.get("relation"), expr.get("number"), text)
    if op == "return_holds":
        return _translation_in_sentence(expr.get("translation"), text)
    return False


def _when_holds(when, inputs: dict) -> bool:
    if "all" in when:
        return all(_when_holds(item, inputs) for item in when["all"])
    if "any" in when:
        return any(_when_holds(item, inputs) for item in when["any"])
    if when["input"] not in inputs:
        return False
    observed = inputs[when["input"]]
    if when.get("relation") == "==" and "value" in when:
        expected = when["value"]
        if isinstance(expected, bool) or expected is None:
            return observed is expected
        return observed == expected and type(observed) is type(expected)
    number = when["number"]
    if isinstance(observed, bool) or not isinstance(observed, (int, float)):
        return False
    relation = when["relation"]
    if relation == "<":
        return observed < number
    if relation == ">":
        return observed > number
    if relation == "<=":
        return observed <= number
    if relation == ">=":
        return observed >= number
    if relation == "==":
        return observed == number
    if relation == "!=":
        return observed != number
    return False


def eval_human(expr, observation: dict, inputs: dict) -> str:
    if expr is None:
        return "no_check"
    if "when" in expr and not _when_holds(expr["when"], inputs or {}):
        return "not_applicable"
    op = expr["op"]
    if op == "raises":
        if observation.get("ok"):
            return "alarm"
        return "clear" if observation.get("exc_type") == expr["type"] else "alarm"
    if not observation.get("ok"):
        return "no_return"
    if observation.get("jsonable") is False:
        return "cannot_apply"
    value = observation.get("value")
    if op == "return_equals":
        expected = expr["value"]
        if isinstance(expected, bool) or expected is None:
            return "clear" if value is expected else "alarm"
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return "cannot_apply"
            return "clear" if value == expected else "alarm"
        if isinstance(expected, str):
            if not isinstance(value, str):
                return "cannot_apply"
            return "clear" if value == expected else "alarm"
        return "cannot_apply"
    if op == "return_compare":
        translation = f"{expr['relation']}{_norm_number(str(expr['number']))}"
        verdict = holds(translation, value)
        if verdict is None:
            return "cannot_apply"
        return "clear" if verdict else "alarm"
    if op == "return_holds":
        verdict = holds(expr["translation"], value)
        if verdict is None:
            return "cannot_apply"
        return "clear" if verdict else "alarm"
    return "no_check"


def summarize_human(expr, parent: dict, fix: dict, inputs: dict, ordinary=None) -> dict:
    if expr is None:
        return {"class": "no_check", "executable": False, "separates": False, "parent": None, "fix": None}
    parent_out = eval_human(expr, parent, inputs)
    fix_out = eval_human(expr, fix, inputs)
    ordinary_parent = ordinary_fix = None
    if ordinary is not None:
        ordinary_parent = eval_human(expr, ordinary["parent"], ordinary["inputs"])
        ordinary_fix = eval_human(expr, ordinary["fix"], ordinary["inputs"])
    label = classify_outcomes(parent_out, fix_out, ordinary_parent, ordinary_fix)
    return {
        "class": label,
        "executable": label in _EXECUTABLE,
        "separates": label == "hit",
        "parent": parent_out,
        "fix": fix_out,
    }


def strong_tokens(sentence: str) -> set[str]:
    cleaned = strip_markup(sentence)
    tokens = set()
    for name in _EXC.findall(_without_quotes(cleaned)):
        tokens.add("exc:" + name)
    for match in re.finditer(rf"(?i)(?<![A-Za-z])({_QUALITY_RE})(?![A-Za-z])", cleaned):
        tokens.add("q:" + match.group(1).lower())
    for match in _QUOTE.finditer(cleaned):
        try:
            value = ast.literal_eval(match.group(0))
        except (SyntaxError, ValueError):
            continue
        if isinstance(value, str) and len(value) >= 2:
            tokens.add("str:" + value)
    for match in re.finditer(r"(?<![\d.])(-?\d{2,}(?:\.\d+)?|-?\d+\.\d+)(?!\d)(?!\.\d)", cleaned):
        tokens.add("num:" + match.group(1))
    return tokens


def token_in_prose(token: str, prose: str) -> bool:
    kind, value = token.split(":", 1)
    if kind == "exc":
        return re.search(rf"\b{re.escape(value)}\b", prose or "") is not None
    if kind == "q":
        return re.search(rf"(?i)(?<![A-Za-z]){re.escape(value)}(?![A-Za-z])", prose or "") is not None
    if kind == "str":
        return value in (prose or "")
    if kind == "num":
        return re.search(rf"(?<![\d.]){re.escape(value)}(?!\d)(?!\.\d)", prose or "") is not None
    return False


def behavior_word(prose: str) -> bool:
    return _BEHAVIOR_WORDS.search(prose or "") is not None


def select_obligation(sentences: list[str], prose: str, qualname: str) -> dict:
    """Link one parent sentence to the recorded repair, or refuse."""
    if not sentences:
        return {"sentence": None, "reason": "no_parent_sentence", "link": None, "tokens": []}
    matched = []
    for sentence in sentences:
        hits = [token for token in sorted(strong_tokens(sentence)) if token_in_prose(token, prose)]
        if hits:
            matched.append((sentence, hits))
    if len(matched) == 1:
        return {
            "sentence": matched[0][0],
            "reason": "include",
            "link": "shared_token",
            "tokens": matched[0][1],
        }
    if len(matched) > 1:
        return {
            "sentence": None,
            "reason": "ambiguous_obligation",
            "link": None,
            "tokens": [],
            "candidates": [item[0] for item in matched],
        }
    if len(sentences) != 1:
        return {"sentence": None, "reason": "ambiguous_obligation", "link": None, "tokens": []}
    last = (qualname or "").split(".")[-1]
    if len(last) >= 3 and re.search(rf"\b{re.escape(last)}\b", prose or "") and behavior_word(prose):
        return {
            "sentence": sentences[0],
            "reason": "include",
            "link": "function_name_and_behavior",
            "tokens": [],
        }
    return {
        "sentence": None,
        "reason": "predicate_not_about_recorded_difference",
        "link": None,
        "tokens": [],
    }


def decide(n_scored: int, counts: dict, sentence_unsafe: bool) -> dict:
    """Pre-registered decision. ranking is always null; unrun tools are not ordered."""
    if n_scored < MIN_SCORED:
        return {
            "decision": "insufficient_denominator",
            "reason": "fewer_than_6_reproduced",
            "ranking": None,
        }
    extractors = ("bind", "jdoctor_pattern", "sentence_grounded")
    if all(counts[name]["separates"] == 0 for name in extractors):
        human = counts["human_from_sentence"]["separates"]
        full = counts["full_output"]["separates"]
        if human > 0 or full > 0:
            reason = "extraction_loss_human_separates" if human > 0 else "extraction_loss_observation_only"
            return {"decision": "extraction_loss", "reason": reason, "ranking": None}
    same_executable = len({counts[name]["executable"] for name in extractors}) == 1
    same_separates = len({counts[name]["separates"] for name in extractors}) == 1
    if same_executable and same_separates:
        return {"decision": "no_new_method", "reason": "sentence_grounded_ties_baselines", "ranking": None}
    sentence = counts["sentence_grounded"]["separates"]
    if sentence > counts["bind"]["separates"] and sentence > counts["jdoctor_pattern"]["separates"] and not sentence_unsafe:
        return {"decision": "complement_positive", "reason": "sentence_grounded_separates_more", "ranking": None}
    return {"decision": "no_gain", "reason": "no_clean_gain_over_extractors", "ranking": None}
