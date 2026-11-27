"""Task-structure compilation and a transferable fixed relation.

This module does not add a fourth comparison relation or a YAML parser.
It does not read a truth receiver, a pre-bound workflow oracle, or observations.
"""
from oracle import synthesize_oracle

RELATIONS = ("byte", "full_string", "parsed_value")

PROGRAM_CONSUMER_PHRASES = (
    "供另一个程序使用",
    "供另一个程序读取",
    "供程序读取",
    "for another program",
)
FILE_DELIVERY_PHRASES = (
    "下载文件",
    "导出为下载",
    "导出为文件",
    "导出文件",
    "配置文件",
    "download file",
    "exported file",
)
COPY_DELIVERY_PHRASES = ("复制",)
STDOUT_DELIVERY_PHRASES = ("标准输出", "stdout")
REDIRECT_DELIVERY_PHRASES = ("重定向", "redirect")

FILE_SLOT_TYPES = ("downloaded_file", "destination_file")
NON_ENDPOINT_WHEN_PROGRAM_FILE = ("ui_preview", "internal_cache", "ui_title", "stderr")

# Conventional relation cues for the fixed-oracle baseline. This is not
# synthesize_oracle: it does not inspect trusted sources, and it does not
# treat “JSON” as parsed_value (the frozen phrase table also does not).
# File-export / copy default to full_string; jq-style numeric structure
# defaults to parsed_value. Generic “内容保真” alone is not enough.
FIXED_ORACLE_CUES = (
    (("jq", "精确十进制", "数值和结构", "parsed-value identity"), "parsed_value"),
    (
        (
            "复制",
            "按文本",
            "全文一致",
            "文本与原文一致",
            "full-string identity",
            "导出",
            "下载",
            "export",
            "download",
            "供另一个程序",
            "redirect",
            "重定向",
            "标准输出",
            "stdout",
        ),
        "full_string",
    ),
)


def _any_phrase(text, phrases):
    if not isinstance(text, str):
        return False
    lowered = text.lower()
    for phrase in phrases:
        if phrase.isascii():
            if phrase.lower() in lowered:
                return True
        elif phrase in text:
            return True
    return False


def compile_task_structure(requirement, sources, slots=None):
    """Map a requirement onto a synthesized relation plus delivery-type constraints."""
    oracle = synthesize_oracle(requirement, sources)
    program_consumer = _any_phrase(requirement, PROGRAM_CONSUMER_PHRASES)
    wants_file = _any_phrase(requirement, FILE_DELIVERY_PHRASES)
    wants_copy = _any_phrase(requirement, COPY_DELIVERY_PHRASES)
    wants_stdout = _any_phrase(requirement, STDOUT_DELIVERY_PHRASES)
    wants_redirect = _any_phrase(requirement, REDIRECT_DELIVERY_PHRASES)
    allowed = []
    delivery_kind = None
    if program_consumer or wants_file or wants_redirect:
        allowed.extend(FILE_SLOT_TYPES)
        delivery_kind = "file_for_program" if program_consumer else "file_artifact"
    if wants_stdout:
        allowed.append("stdout")
        if delivery_kind is None:
            delivery_kind = "stdout"
    if wants_copy and not program_consumer:
        allowed.append("copy_buffer")
        if delivery_kind is None:
            delivery_kind = "copy"
    allowed = tuple(dict.fromkeys(allowed))
    excluded = NON_ENDPOINT_WHEN_PROGRAM_FILE if (program_consumer or wants_file) else ()
    compatible = []
    if slots is not None:
        for index, slot in enumerate(slots):
            slot_type = slot["type"] if isinstance(slot, dict) else slot
            if allowed and slot_type in allowed and slot_type not in excluded:
                compatible.append(index)
    structure = {
        "relation": oracle["relation"],
        "abstain": oracle["abstain"],
        "requirement": requirement,
        "source_count": oracle["source_count"],
        "hits": oracle["hits"],
        "generic_also_present": oracle["generic_also_present"],
        "trusted_references": list(sources) if sources else [],
        "program_consumer": program_consumer,
        "delivery_kind": delivery_kind,
        "allowed_slot_types": allowed,
        "excluded_slot_types": tuple(excluded),
        "compatible_slots": compatible,
        "constraint_abstain": None,
    }
    if oracle["relation"] is None and not allowed:
        return structure
    if slots is not None and allowed and len(compatible) != 1:
        structure["constraint_abstain"] = (
            "no_compatible_slot" if len(compatible) == 0 else "ambiguous_compatible_slots"
        )
    return structure


def fixed_oracle(requirement, action=""):
    """Return a conventional relation, or abstain. Does not read sources or slots."""
    text = f"{requirement or ''}\n{action or ''}"
    for phrases, relation in FIXED_ORACLE_CUES:
        if _any_phrase(text, phrases):
            return {"relation": relation, "abstain": None, "source": "fixed_conventional"}
    return {"relation": None, "abstain": "no_conventional_relation", "source": "fixed_conventional"}
