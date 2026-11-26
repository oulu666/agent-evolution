"""Transcription of Jdoctor/Toradocu 3.0 Matcher.simpleMatch.

The source is albertogoffi/toradocu Matcher.java (pattern step only).
Lexical and semantic matching against Java code elements is not included.
"""

from __future__ import annotations

import re


VERBS = (
    r"(?<![A-Za-z])(?:is equal to|are equal to|equals to|returns|return|is|are|be)(?![A-Za-z])"
)
PREDICATES = (
    r"(true|false|null|this|empty|zero|positive|strictly positive|negative|"
    r"strictly negative|nonnegative|nonpositive)"
)
NUMBER = r"(zero|one|two|three|four|five|six|seven|eight|nine|-?\d+(?:\.\d+)?)"
WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}

IS_PATTERN = re.compile(VERBS + r"(?:==|=)? ?" + PREDICATES, re.IGNORECASE)
IS_NOT_PATTERN = re.compile(VERBS + r"(?:!=)? ?" + PREDICATES, re.IGNORECASE)
INEQUALITY_NUMBER = re.compile(
    VERBS + r"(<=|>=|<|>|!=|==|=)? ?(" + NUMBER + r")(?! )",
    re.IGNORECASE,
)
INEQUALITY_VAR = re.compile(
    VERBS + r"(<=|>=|<|>|!=|==|=) ?([A-Za-z]+[0-9]?(?:_?[A-Za-z0-9]+)*)",
    re.IGNORECASE,
)
INSTANCEOF = re.compile(r"(?<![A-Za-z])instanceof ([A-Za-z0-9_.]+)")
NEGATION = re.compile(
    r"\bnot\s+(?=true\b|false\b|null\b|empty\b|zero\b|positive\b|negative\b|"
    r"nonnegative\b|nonpositive\b|strictly\b)",
    re.IGNORECASE,
)


def _relation(symbol: str | None) -> str:
    if symbol is None or symbol == "=":
        return "=="
    return symbol


def _number(token: str) -> str:
    lowered = token.lower()
    if lowered in WORDS:
        return WORDS[lowered]
    if re.fullmatch(r"-?\d+", token):
        return str(int(token))
    return str(float(token))


def _quality(word: str, negated: bool) -> str | None:
    mapping = {
        "true": "==true",
        "false": "==false",
        "null": "==null",
        "this": "==receiver",
        "zero": "==0",
        "positive": ">0",
        "strictly positive": ">0",
        "negative": "<0",
        "strictly negative": "<0",
        "nonnegative": ">=0",
        "nonpositive": "<=0",
    }
    base = mapping.get(word.lower())
    if base is None:
        return None
    if negated and word.lower() in {"true", "false", "null", "zero"}:
        return base.replace("==", "!=", 1)
    if negated and base == ">0":
        return "<=0"
    if negated and base == "<0":
        return ">=0"
    if negated and base == ">=0":
        return "<0"
    if negated and base == "<=0":
        return ">0"
    if negated:
        return f"NOT({base})"
    return base


def simple_match(predicate: str) -> dict | None:
    """Return the first simpleMatch translation, or a note when the regex matches but does not translate."""
    text = predicate.strip()
    negated = False
    if NEGATION.search(text):
        text = NEGATION.sub("", text, count=1)
        negated = True
    is_match = IS_PATTERN.search(text)
    if is_match:
        word = is_match.group(1)
        translation = _quality(word, negated)
        if translation is None:
            return {"translation": None, "untranslated": word.lower(), "span": is_match.group(0)}
        return {"translation": translation, "untranslated": None, "span": is_match.group(0)}
    is_not = IS_NOT_PATTERN.search(text)
    if is_not:
        word = is_not.group(1)
        translation = _quality(word, True)
        if translation is None:
            return {"translation": None, "untranslated": word.lower(), "span": is_not.group(0)}
        return {"translation": translation, "untranslated": None, "span": is_not.group(0)}
    number = INEQUALITY_NUMBER.search(text)
    if number:
        relation = _relation(number.group(1))
        token = _number(number.group(2))
        translation = f"{relation}{token}"
        if negated:
            translation = f"NOT({translation})"
        return {"translation": translation, "untranslated": None, "span": number.group(0)}
    variable = INEQUALITY_VAR.search(text)
    if variable:
        return {
            "translation": None,
            "untranslated": "identifier:" + variable.group(2),
            "span": variable.group(0),
        }
    instance = INSTANCEOF.search(text)
    if instance:
        translation = "instanceof " + instance.group(1)
        if negated:
            translation = f"NOT({translation})"
        return {"translation": translation, "untranslated": None, "span": instance.group(0)}
    if text == "been set":
        return {"translation": "!=null", "untranslated": None, "span": text}
    return None


def holds(translation: str | None, value):
    """True or False when the translation applies, else None."""
    if not translation:
        return None
    negated = False
    current = translation
    if current.startswith("NOT(") and current.endswith(")"):
        negated = True
        current = current[4:-1]
    result = _holds_atom(current, value)
    if result is None:
        return None
    return (not result) if negated else result


def _holds_atom(translation: str, value):
    if translation == "==receiver" or translation.startswith("instanceof "):
        return None
    if translation == "==null":
        return value is None
    if translation == "!=null":
        return value is not None
    if translation == "==true":
        return value is True
    if translation == "==false":
        return value is False
    if translation == "!=true":
        return value is not True
    if translation == "!=false":
        return value is not False
    match = re.fullmatch(r"(<=|>=|<|>|!=|==)(-?\d+(?:\.\d+)?)", translation)
    if not match:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(match.group(2)) if "." in match.group(2) else int(match.group(2))
    op = match.group(1)
    if op == "==":
        return value == number
    if op == "!=":
        return value != number
    if op == ">":
        return value > number
    if op == "<":
        return value < number
    if op == ">=":
        return value >= number
    return value <= number
