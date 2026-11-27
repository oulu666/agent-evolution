"""Select an observable from action/no-action demonstrations; no tool-specific branches."""
import json
from decimal import Decimal


def equivalent(left, right, kind):
    if kind == "full_string":
        kind = "text"
    elif kind == "parsed_value":
        kind = "json"
    if kind == "byte":
        return left == right
    if kind == "text":
        def normalize(value):
            return value.replace("\r\n", "\n").removesuffix("\n")
        return normalize(left) == normalize(right)
    if kind != "json":
        raise ValueError(kind)
    def parse(value):
        return json.loads(value, parse_int=Decimal, parse_float=Decimal)
    try:
        return parse(left) == parse(right)
    except ValueError:
        return left == right


def select(demos, kind, control):
    candidates = []
    for position in range(len(demos[0]["after"])):
        if all(equivalent(d["after"][position], d["expected"], kind)
               and (not control or not equivalent(d["before"][position], d["expected"], kind))
               for d in demos):
            candidates.append(position)
    return candidates


def evaluate(demos, rows, receiver, kind):
    learned = select(demos, kind, True)
    after_only = select(demos, kind, False)
    snapshots = {}
    for r in rows:
        snapshots.setdefault(r["input"], r["after"])
    for r in rows:
        reference = r["expected"]
        values = r["after"]
        def decision(positions):
            if len(positions) == 1:
                return equivalent(values[positions[0]], reference, kind)
            return None
        r["truth"] = equivalent(values[receiver], reference, kind)
        r["decisions"] = {
            "learned": decision(learned), "after_only": decision(after_only),
            "lookup": decision([receiver]),
            "fixed_replay": all(equivalent(x, y, kind) for x, y in zip(values, snapshots[r["input"]], strict=True))}
    return {"slots_learned": learned, "slots_after_only": after_only, "receiver": receiver,
            "demos": demos, "rows": rows}
