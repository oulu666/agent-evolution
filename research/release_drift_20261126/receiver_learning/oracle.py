"""Map a task requirement and trusted sources onto one program-checkable relation.

The map is a closed phrase table. It does not read observations, name a receiver,
or call a language model. A requirement that does not land on exactly one
compatible relation is refused and produces no check.
"""
import json
from decimal import Decimal

PHRASES = {
    "byte": ("字节一致", "byte-for-byte", "byte identity"),
    "full_string": ("按文本", "全文一致", "文本与原文一致", "full-string identity"),
    "parsed_value": ("精确十进制", "数值和结构", "parsed-value identity"),
}

GENERIC = ("内容保真", "faithful content")

# Clauses already separated in protocol.md. Passing the whole unsplit sentence
# is a refusal case, not a study input.
STUDY_REQUIREMENTS = {
    "copy": "内容保真，复制按文本",
    "jq": "内容保真，按精确十进制数值和结构比较",
}


def parses_json(value):
    if not isinstance(value, str):
        return False
    try:
        json.loads(value, parse_int=Decimal, parse_float=Decimal)
    except ValueError:
        return False
    return True


def _hit(requirement, phrase):
    if phrase.isascii():
        return phrase.lower() in requirement.lower()
    return phrase in requirement


def synthesize_oracle(requirement, sources):
    """Choose byte, full_string, or parsed_value, or record why no check exists."""
    if not isinstance(requirement, str) or requirement.strip() == "":
        return _refuse("empty_requirement", requirement, sources)
    hits = [relation for relation, phrases in PHRASES.items() if any(_hit(requirement, phrase) for phrase in phrases)]
    generic = any(_hit(requirement, phrase) for phrase in GENERIC)
    if len(hits) > 1:
        return _refuse("ambiguous_requirement", requirement, sources, hits=hits, generic=generic)
    if len(hits) == 0:
        reason = "underspecified_relation" if generic else "unmapped_requirement"
        return _refuse(reason, requirement, sources, generic=generic)
    relation = hits[0]
    if sources is None or len(sources) == 0 or any(not isinstance(source, str) for source in sources):
        return _refuse("no_trusted_reference", requirement, sources, hits=hits, generic=generic)
    if relation == "parsed_value" and not all(parses_json(source) for source in sources):
        return _refuse("source_incompatible", requirement, sources, hits=hits, generic=generic)
    return {
        "relation": relation,
        "abstain": None,
        "requirement": requirement,
        "source_count": len(sources),
        "hits": hits,
        "generic_also_present": generic,
    }


def _refuse(reason, requirement, sources, hits=None, generic=False):
    return {
        "relation": None,
        "abstain": reason,
        "requirement": requirement,
        "source_count": 0 if not sources else len(sources),
        "hits": hits or [],
        "generic_also_present": generic,
    }
