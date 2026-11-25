"""Frozen task generator, public priors and detectors. Detectors never receive the target label."""
import hashlib
import itertools
import re
from functools import lru_cache

WORDS = ("order", "item", "user", "file", "key", "parse", "record", "data", "base",
         "database", "path", "name", "pathname", "tag")
SHORT = ("api", "url", "http", "xml", "id", "io", "uuid")
VOCAB = WORDS + SHORT
METHODS = ("examples", "regex", "suffix", "alias", "dictionary")
CANARIES = {"inflection": [("DeviceType", "device_type")],
            "humps": [("rubyTuesdays", "ruby_tuesdays"), ("APIResponse", "api_response")]}


def tasks():
    rows = []
    def add(group, parts, spelling):
        rows.append(dict(id=f"{group}-{len(rows):03}", group=group, raw=spelling,
                         target="_".join(parts)))
    for group, pool in (
        ("ordinary", itertools.product(WORDS, WORDS)),
        ("one_acronym", itertools.product(SHORT, WORDS)),
        ("two_acronyms", itertools.product(SHORT, SHORT, WORDS)),
        ("unlisted", itertools.product(SHORT, ("ledger", "receipt", "invoice", "batch"), WORDS)),
    ):
        chosen = sorted(pool, key=lambda parts: hashlib.sha256("/".join(parts).encode()).digest())[:24]
        for parts in chosen:
            raw = "".join(w.upper() if w in SHORT else w.title() for w in parts)
            add(group, parts, raw)
    for raw, prefix, split in (("DATABASEKey", "database", ("data", "base")),
                               ("PATHNAMEKey", "pathname", ("path", "name"))):
        add("ambiguous", (prefix, "key"), raw)
        add("ambiguous", split + ("key",), raw)
    return rows


def standard(raw):
    words = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", raw)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", words).lower()


def alternative(raw):
    return re.sub("|".join(sorted((w.upper() for w in SHORT), key=len, reverse=True)),
                  lambda match: match[0].title(), raw)


@lru_cache(maxsize=None)
def splits(raw):
    if not raw:
        return [()]
    paths = []
    for word in VOCAB:
        if raw.startswith(word):
            paths.extend((word,) + tail for tail in splits(raw[len(word):]))
            if len(paths) > 1:
                return paths[:2]
    return paths


def decide(method, raw, observations, examples_ok):
    actual = observations[raw]
    if "error" in actual:
        return "alert"
    output = actual["value"]
    if method == "examples":
        return "pass" if examples_ok else "alert"
    if method == "regex":
        ok = output == standard(raw)
    elif method in ("suffix", "alias"):
        other = raw + "Record" if method == "suffix" else alternative(raw)
        if raw == other:
            return "unknown"
        partner = observations[other]
        if "error" in partner:
            return "unknown"
        ok = partner["value"] == (output + "_record" if method == "suffix" else output)
    else:
        options = splits(raw.lower())
        if len(options) != 1:
            return "unknown"
        ok = output == "_".join(options[0])
    return "pass" if ok else "alert"
