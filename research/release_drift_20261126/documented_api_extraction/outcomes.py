"""Labels for documented-API extractor feasibility.

The three extractors are reused unchanged. This module only decides whether a
check holds on a legal observation and fails on a violating one. It is not a
drift detector and it does not rank unrun tools.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


_CONTRACT = Path(__file__).resolve().parents[1] / "contract_binding"
_PREDICATE = Path(__file__).resolve().parents[1] / "documented_predicate_binding"
for place in (_CONTRACT, _PREDICATE):
    if str(place) not in sys.path:
        sys.path.insert(0, str(place))

from binding import apply_check as bind_apply_check  # noqa: E402
from binding import preprocess, translate_document  # noqa: E402
from sentence_grounded import apply_grounded, eval_human, extract, normalized, strip_markup  # noqa: E402


MIN_INCLUDED = 8
MIN_LIBRARIES = 3
EXAMINE_CAP = 40
INCLUDE_CAP = 12
LIBRARY_CAP = 4
FUNCTION_CAP = 2

LABELS = ("full_success", "inverted", "hold_only", "fail_only", "error", "no_check")
EXECUTABLE_LABELS = {"full_success", "inverted", "hold_only", "fail_only"}
METHODS = ("jdoctor_pattern", "bind", "sentence_grounded", "human_from_sentence")
EXTRACTORS = ("jdoctor_pattern", "bind", "sentence_grounded")

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
        "reason": "Would synthesize new inputs. The hypothesis library may be a subject API; the Hypothesis tool is not run.",
    },
)

FORBIDDEN = re.compile(r"(?i)pandas|pillow|scipy|sealed|environment_receipts")
_CALL_ERRORS = {"InstallError", "HarnessError", "TimeoutError"}


def side(raw: str) -> str:
    if raw == "clear":
        return "hold"
    if raw in {"alarm", "no_return"}:
        return "fail"
    return "error"


def pair_label(legal_raw: str, violating_raw: str) -> str:
    """One check on the two pre-registered observations.

    full_success means the check holds on the legal observation and fails on
    the violating observation. The opposite polarity is inverted, not success.
    """
    legal = side(legal_raw)
    violating = side(violating_raw)
    if legal == "error" or violating == "error":
        return "error"
    if legal == "hold" and violating == "fail":
        return "full_success"
    if legal == "fail" and violating == "hold":
        return "inverted"
    if legal == "hold":
        return "hold_only"
    if legal == "fail" and violating == "fail":
        return "fail_only"
    return "error"


def combine_labels(labels: list[str]) -> str:
    if not labels:
        return "no_check"
    for name in ("full_success", "inverted", "hold_only", "fail_only", "error"):
        if name in labels:
            return name
    return "no_check"


def norm_sentence(text: str) -> str:
    return strip_markup(normalized(text)).strip().rstrip(".").lower()


def sentence_matches(included: str, check_sentence: str | None) -> bool:
    """True when a check was emitted from the included sentence, not a neighbor."""
    if not check_sentence:
        return False
    left = {norm_sentence(included), norm_sentence(preprocess(included))}
    right = {norm_sentence(check_sentence), norm_sentence(preprocess(check_sentence))}
    left.discard("")
    right.discard("")
    if left & right:
        return True
    for left_text in left:
        for right_text in right:
            if left_text in right_text or right_text in left_text:
                shorter, longer = sorted((left_text, right_text), key=len)
                if longer and len(shorter) / len(longer) >= 0.8:
                    return True
    return False


def _view(observation: dict) -> dict:
    if not observation.get("ok") or observation.get("jsonable") is False:
        return {"ok": False, "fine": None, "coarse": None}
    value = observation.get("value")
    return {"ok": True, "fine": value, "coarse": value}


def _bind_one(check: dict, observation: dict) -> str:
    if observation.get("jsonable") is False and observation.get("ok"):
        return "cannot_apply"
    return bind_apply_check(check, _view(observation), "full")


def matched_grounded(docstring: str, quote: str) -> list[dict]:
    return [check for check in extract(docstring) if sentence_matches(quote, check.get("sentence"))]


def matched_translated(docstring: str, quote: str, method: str) -> list[dict]:
    name = "jdoctor" if method == "jdoctor_pattern" else "bind"
    document = translate_document(docstring or "", name)
    return [check for check in document["checks"] if sentence_matches(quote, check.get("sentence"))]


def _pack(label: str, checks: list[dict], details: list[dict], contradicts: bool = False) -> dict:
    return {
        "label": label,
        "emitted": bool(checks),
        "executable": label in EXECUTABLE_LABELS,
        "full_success": label == "full_success",
        "contradicts": contradicts,
        "checks": details,
    }


def score_checks(checks: list[dict], apply_one, legal_obs: dict, violating_obs: dict) -> dict:
    details = []
    labels = []
    for check in checks:
        legal_raw = apply_one(check, legal_obs)
        violating_raw = apply_one(check, violating_obs)
        label = pair_label(legal_raw, violating_raw)
        labels.append(label)
        details.append({
            "label": label,
            "legal": legal_raw,
            "violating": violating_raw,
            "sentence": check.get("sentence"),
            "kind": check.get("kind"),
            "translation": check.get("translation"),
            "exc_type": check.get("exc_type"),
            "literal": check.get("literal"),
        })
    label = combine_labels(labels)
    return _pack(label, checks, details, contradicts=("full_success" in labels and "inverted" in labels))


def call_failed(observation: dict | None) -> bool:
    return not observation or observation.get("exc_type") in _CALL_ERRORS


def score_grounded(docstring: str, quote: str, legal_obs: dict, violating_obs: dict) -> dict:
    checks = matched_grounded(docstring, quote)
    if call_failed(legal_obs) or call_failed(violating_obs):
        return _pack("error", checks, [])
    return score_checks(checks, apply_grounded, legal_obs, violating_obs)


def score_translated(method: str, docstring: str, quote: str, legal_obs: dict, violating_obs: dict) -> dict:
    checks = matched_translated(docstring, quote, method)
    if call_failed(legal_obs) or call_failed(violating_obs):
        return _pack("error", checks, [])
    return score_checks(checks, _bind_one, legal_obs, violating_obs)


def score_human(expr, legal_obs: dict, violating_obs: dict) -> dict:
    if expr is None:
        return _pack("no_check", [], [])
    if call_failed(legal_obs) or call_failed(violating_obs):
        return _pack("error", [expr], [])
    legal_raw = eval_human(expr, legal_obs, {})
    violating_raw = eval_human(expr, violating_obs, {})
    label = pair_label(legal_raw, violating_raw)
    details = [{"label": label, "legal": legal_raw, "violating": violating_raw, "human": expr}]
    return _pack(label, [expr], details)


def empty_counts() -> dict:
    return {
        name: {
            "emitted": 0,
            "executable": 0,
            "full_success": 0,
            "labels": {label: 0 for label in LABELS},
        }
        for name in METHODS
    }


def tally(groups: list[dict]) -> dict:
    counts = empty_counts()
    for group in groups:
        for name in METHODS:
            block = group[name]
            label = block["label"]
            counts[name]["labels"][label] += 1
            if block.get("emitted"):
                counts[name]["emitted"] += 1
            if block.get("executable"):
                counts[name]["executable"] += 1
            if block.get("full_success"):
                counts[name]["full_success"] += 1
    return counts


def _below_quarter(count: int, total: int) -> bool:
    return count * 4 < total


def _at_least_half(count: int, total: int) -> bool:
    return count * 2 >= total


def decide(n_included: int, n_libraries: int, counts: dict) -> dict:
    """Pre-registered decision. ranking is always null."""
    if n_included < MIN_INCLUDED or n_libraries < MIN_LIBRARIES:
        return {
            "decision": "insufficient_denominator",
            "reason": "fewer_than_8_or_fewer_than_3_libraries",
            "ranking": None,
        }
    near = all(_below_quarter(counts[name]["full_success"], n_included) for name in EXTRACTORS)
    human_ok = _at_least_half(counts["human_from_sentence"]["full_success"], n_included)
    if near and human_ok:
        return {
            "decision": "extraction_loss",
            "reason": "extractors_near_zero_human_succeeds",
            "ranking": None,
        }
    same_executable = len({counts[name]["executable"] for name in EXTRACTORS}) == 1
    same_success = len({counts[name]["full_success"] for name in EXTRACTORS}) == 1
    if same_executable and same_success:
        return {"decision": "no_new_method", "reason": "extractors_tie", "ranking": None}
    if any(counts[name]["full_success"] >= 1 for name in EXTRACTORS):
        return {
            "decision": "counts_reported",
            "reason": "extractor_full_success_is_not_drift_detection",
            "ranking": None,
        }
    return {"decision": "no_gain", "reason": "no_extractor_full_success", "ranking": None}


def build_driver(module: str, attrs: list[str], param: str, passing: str) -> str:
    if passing == "positional":
        invocation = "return target(inputs['value'])"
    elif passing == "keyword":
        invocation = f"return target(**{{{param!r}: inputs['value']}})"
    else:
        raise ValueError(f"unknown passing mode: {passing}")
    lines = [
        "def call():",
        "    import importlib",
        f"    target = importlib.import_module({module!r})",
        f"    for name in {attrs!r}:",
        "        target = getattr(target, name)",
        f"    {invocation}",
    ]
    return "\n".join(lines) + "\n"


def audit_driver(driver: str, import_name: str) -> None:
    if not isinstance(driver, str) or driver.count("\n") > 40:
        raise SystemExit("driver is missing or longer than 40 lines")
    if "def call(" not in driver:
        raise SystemExit("driver must define call()")
    if re.search(r"(?m)^\s*assert\b", driver) or re.search(r"\boracle\b", driver):
        raise SystemExit("driver must not assert or mention an oracle")
    if import_name not in driver:
        raise SystemExit(f"driver does not name {import_name}")
    if FORBIDDEN.search(driver):
        raise SystemExit("driver names a forbidden library")
    if "inputs['value']" not in driver and 'inputs["value"]' not in driver:
        raise SystemExit("driver must read inputs['value']")
