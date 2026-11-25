"""Shared bounded action space. No method receives the gold query at inference."""
import itertools
import re

AGG = ("", "MAX", "MIN", "COUNT", "SUM", "AVG")
OPS = ("=", ">", "<")
STOP = set("a an the is are was were in of to on for and with what which how that has have does do where when".split())
HINTS = ((), ("most", "highest", "largest", "maximum", "greatest", "latest", "longest"),
         ("least", "lowest", "smallest", "minimum", "earliest", "shortest"),
         ("how many", "number of", "count"), ("sum", "total"), ("average", "mean"))


def words(value):
    return re.findall(r"[^\W_]+", str(value).lower())


def signal(question, phrases):
    return any(" " + phrase + " " in question for phrase in phrases)


def slate(question, headers, types, rows):
    tokens = words(question)
    text = " " + " ".join(tokens) + " "
    bag = set(tokens) - STOP
    columns = []
    mentions = []
    for col, header in enumerate(headers):
        hw = words(header)
        overlap = len(bag & set(hw)) / max(1, len(set(hw) - STOP))
        named = float(bool(hw) and " " + " ".join(hw) + " " in text)
        columns.append((overlap, named))
        for value in {r[col] for r in rows}:
            if value is None:
                continue
            literal = str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)
            phrase = " ".join(words(literal))
            if phrase and phrase not in STOP and " " + phrase + " " in text:
                mentions.append((min(3, len(phrase.split())) + min(len(phrase), 18) / 20,
                                 col, value))
    mentions.sort(key=lambda m: (-m[0], m[1], str(m[2])))
    top = mentions[:5]
    op = 1 if signal(text, ("more than", "greater than", "after", "over", "above")) else (
        2 if signal(text, ("less than", "fewer than", "before", "under", "below")) else 0)
    conditions = {(): 0.0}
    for weight, col, value in top:
        conditions[((col, 0, value),)] = 1 + weight * .25
        if op and types[col] == "real":
            conditions[((col, op, value),)] = 1.5 + weight * .25
    for a, b in itertools.combinations(top[:4], 2):
        if a[1] != b[1]:
            pair = tuple(sorted(((a[1], 0, a[2]), (b[1], 0, b[2])), key=lambda x: x[0]))
            conditions[pair] = 1.6 + (a[0] + b[0]) * .15
    hints = [False] + [signal(text, patterns) for patterns in HINTS[1:]]
    hints[0] = not any(hints)
    candidates = []
    for sel in range(len(headers)):
        overlap, named = columns[sel]
        for cond, cond_score in conditions.items():
            same = any(c == sel for c, _, _ in cond)
            for agg in range(6):
                prior = (2.4 * overlap + .6 * named + 3.2 * hints[agg] + .3 * (agg == 0)
                         + cond_score - .95 * same - .7 * (agg in (4, 5) and types[sel] != "real"))
                candidates.append((prior, (sel, agg, cond)))
    candidates.sort(key=lambda z: -z[0])
    chosen = candidates[:48]
    examples = []
    common = sorted(bag)[:32]
    for rank, (score, (sel, agg, cond)) in enumerate(chosen):
        same = int(any(c == sel for c, _, _ in cond))
        overlap, named = columns[sel]
        f = dict(prior=score, rank=rank / 48, overlap=overlap, named=named, same=same,
                 conds=len(cond), mentioned=min(len(top), 3), hint=float(hints[agg]))
        f["agg=" + str(agg)] = 1
        f["aggtype=" + str(agg) + types[sel]] = 1
        f["size=" + str(len(cond)) + "/" + str(min(len(top), 3))] = 1
        for w in common:
            f[f"agg{agg}/{w}"] = 1
            f[f"count{len(cond)}/{w}"] = 1
        examples.append(f)
    return [v[1] for v in chosen], examples


def template(plan):
    _, agg, conds = plan
    return agg, tuple(sorted(c[1] for c in conds))


def delex(question, headers, plan_values):
    phrase = " " + " ".join(words(question)) + " "
    pairs = [(words(h), "field") for h in headers] + [(words(v), "value") for v in plan_values]
    for span, label in sorted(pairs, key=lambda t: -len(t[0])):
        if span:
            phrase = phrase.replace(" " + " ".join(span) + " ", " " + label + " ")
    return phrase.strip()
