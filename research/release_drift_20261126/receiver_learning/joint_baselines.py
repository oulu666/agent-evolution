"""Transferable action-type lookup. It binds slot types, not a workflow index.

Unknown workflows are not added to the pre-bound LOOKUP table in baselines.py.
"""

TRANSFERABLE_PHRASES = (
    (("导出", "下载", "export", "download", "供另一个程序", "for another program"),
     ("downloaded_file", "destination_file")),
    (("重定向", "redirect"), ("destination_file",)),
    (("标准输出", "stdout"), ("stdout",)),
    (("复制",), ("copy_buffer",)),
)


def transferable_types(requirement, action=""):
    text = f"{requirement or ''}\n{action or ''}"
    lowered = text.lower()
    types = []
    for phrases, slot_types in TRANSFERABLE_PHRASES:
        for phrase in phrases:
            hit = phrase.lower() in lowered if phrase.isascii() else phrase in text
            if hit:
                for slot_type in slot_types:
                    if slot_type not in types:
                        types.append(slot_type)
                break
    return tuple(types)


def transferable_lookup_positions(requirement, slots, action=""):
    """Return a unique slot whose type matches the task, or empty if not unique."""
    types = set(transferable_types(requirement, action))
    if not types or slots is None:
        return []
    hits = [index for index, slot in enumerate(slots) if slot["type"] in types]
    if len(hits) == 1:
        return hits
    return []
