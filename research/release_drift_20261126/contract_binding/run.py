"""Run the frozen contract-binding feasibility. Refuse to score dirty freeze files."""

from __future__ import annotations

import ast
import hashlib
import html
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

from binding import (
    agora_class,
    apply_check,
    audit,
    classify_edges,
    classify_rows,
    decide,
    method_class,
    status_class,
    translate_document,
)


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
FREEZE = [
    HERE / "protocol.md",
    HERE / "cases.json",
    HERE / "jdoctor_patterns.py",
    HERE / "binding.py",
    HERE / "run.py",
]
REPLAY = ROOT / "runs_independent_20261124" / "replay.json"
PAIRED = ROOT / "runs_upstream_functional_20261124" / "paired_releases.json"
ARCHIVE = ROOT / "research/release_drift_20261126/boundary_gap/results/summary.json"
DOCS = HERE / "docs"
RESULTS = HERE / "results"


def assert_allowed(path: Path, write: bool = False) -> None:
    text = str(path.resolve()).replace("\\", "/")
    if "sealed" in text.lower() or "/environment_receipts/" in text:
        raise SystemExit(f"refusing sealed path: {path}")
    if write and "/boundary_gap/" in text:
        raise SystemExit(f"refusing to write archived results: {path}")
    allowed = (REPLAY.resolve(), PAIRED.resolve(), ARCHIVE.resolve())
    under_here = str(HERE.resolve())
    if path.resolve() == ARCHIVE.resolve() or path.resolve() in allowed or text.startswith(under_here):
        return
    if path.resolve() in {item.resolve() for item in FREEZE}:
        return
    raise SystemExit(f"path is outside the frozen allowlist: {path}")


def file_sha(path: Path) -> str:
    assert_allowed(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path):
    assert_allowed(path)
    return json.loads(path.read_text(encoding="utf-8"))


def freeze_ready() -> None:
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--", *[str(path) for path in FREEZE]], cwd=ROOT, text=True)
    if dirty.strip():
        raise SystemExit("freeze files have uncommitted changes; refusing to score\n" + dirty)


def normalize_replay(actual: dict) -> dict:
    if actual.get("ok"):
        return {"ok": True, "fine": actual.get("fine"), "coarse": actual.get("coarse")}
    return {"ok": False, "fine": None, "coarse": None}


def normalize_object(actual) -> dict:
    if isinstance(actual, dict):
        coarse = {key: value for key, value in actual.items() if isinstance(value, bool)}
        return {"ok": True, "fine": actual, "coarse": coarse or actual}
    return {"ok": True, "fine": actual, "coarse": actual}


def html_to_text(page: str) -> str:
    page = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", page)
    page = re.sub(r"(?is)<br\s*/?>", "\n", page)
    page = re.sub(r"(?is)</(p|div|h\d|li|tr)>", "\n", page)
    page = re.sub(r"(?is)<[^>]+>", " ", page)
    return html.unescape(page)


def collect_docs(node, prefix, docs):
    if isinstance(node, ast.ClassDef):
        name = f"{prefix}.{node.name}" if prefix else node.name
        docs[name] = ast.get_docstring(node) or ""
        for child in node.body:
            collect_docs(child, name, docs)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        name = f"{prefix}.{node.name}" if prefix else node.name
        docs[name] = ast.get_docstring(node) or ""


def extract_py(source: str, symbols: list[str]) -> tuple[str, list[str], str | None]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return "", symbols, f"SyntaxError: {exc}"
    docs = {}
    for node in tree.body:
        collect_docs(node, "", docs)
    found = []
    missing = []
    for symbol in symbols:
        if symbol in docs:
            found.append(f"# {symbol}\n{docs[symbol]}")
        else:
            missing.append(symbol)
    return "\n\n".join(found), missing, None


def fetch_url(url: str) -> tuple[bytes | None, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": "agent-evolution-contract-binding"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.read(), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def fetch_source(source: dict, cache: dict) -> dict:
    errors = []
    for url in source["urls"]:
        if url not in cache:
            data, error = fetch_url(url)
            cache[url] = (data, error)
        data, error = cache[url]
        if data is None:
            errors.append(f"{url} {error}")
            continue
        text = data.decode("utf-8", errors="replace")
        if url.endswith(".html") or text.lstrip().lower().startswith("<!doctype") or text.lstrip().lower().startswith("<html"):
            text = html_to_text(text)
        record = {"url": url, "sha256": hashlib.sha256(data).hexdigest(), "missing_symbols": [], "parse_error": None}
        if source["kind"] == "py":
            extracted, missing, parse_error = extract_py(text, source["symbols"])
            record.update(text=extracted, missing_symbols=missing, parse_error=parse_error, raw_chars=len(text))
        else:
            record.update(text=text, raw_chars=len(text))
        return record
    return {"url": None, "text": "", "sha256": None, "missing_symbols": source.get("symbols", []), "parse_error": None, "errors": errors}


def document_text(fetched: list[dict]) -> tuple[str, str | None, str | None]:
    parts = [item["text"] for item in fetched if item.get("text")]
    errors = [error for item in fetched for error in item.get("errors", [])]
    parse_errors = [item["parse_error"] for item in fetched if item.get("parse_error")]
    if not parts and errors:
        return "", "; ".join(parse_errors) or None, "; ".join(errors)
    return "\n\n".join(parts), "; ".join(parse_errors) or None, None


def evaluable(checks: list[dict], views: dict, shape: str) -> bool:
    observed = []
    if shape == "edges":
        observed = list(views.values())
    else:
        observed = [view for pair in views["pairs"] for view in pair]
    for check in checks:
        for view in observed:
            if apply_check(check, view, "full") in {"alarm", "clear"}:
                return True
    return False


def edge_views(parent_rows: list[dict], repair_rows: list[dict], normalize) -> dict:
    if len(parent_rows) != 2 or len(repair_rows) != 2:
        raise SystemExit("edge cases require two recorded rows on each side")
    return {
        "ordinary_parent": normalize(parent_rows[0]),
        "edge_parent": normalize(parent_rows[1]),
        "ordinary_repair": normalize(repair_rows[0]),
        "edge_repair": normalize(repair_rows[1]),
    }


def published_edges(parent_rows, repair_rows) -> dict:
    def flag(row, level: str) -> str:
        actual, expected = row["actual"], row["expected"]
        if level == "status":
            return "clear" if actual.get("ok") else "alarm"
        if not actual.get("ok"):
            return "alarm"
        if level == "coarse":
            return "clear" if actual.get("coarse") == expected.get("coarse") else "alarm"
        full_ok = actual.get("fine") == expected.get("fine") and actual.get("coarse") == expected.get("coarse")
        return "clear" if full_ok else "alarm"

    out = {}
    for level in ("status", "coarse", "full"):
        out[level] = classify_edges(
            flag(parent_rows[0], level), flag(repair_rows[0], level),
            flag(parent_rows[1], level), flag(repair_rows[1], level))
    return out


def published_pairs(before_rows, after_rows) -> dict:
    def flag(actual, expected, level: str) -> str:
        actual_view = normalize_object(actual)
        expected_view = normalize_object(expected)
        if level == "status":
            return "clear" if actual_view["ok"] else "alarm"
        key = "coarse" if level == "coarse" else "fine"
        return "clear" if actual_view[key] == expected_view[key] else "alarm"

    out = {}
    for level in ("status", "coarse", "full"):
        pairs = [(flag(before["actual"], before["expected"], level), flag(after["actual"], after["expected"], level))
                 for before, after in zip(before_rows, after_rows, strict=True)]
        out[level] = classify_rows(pairs)
    return out


def published_attrs(observations: list[dict]) -> dict:
    by_key = {(item["side"], item["task"]): item for item in observations}

    def flag(side: str, task: str, level: str) -> str:
        item = by_key[(side, task)]
        supplied = 100 if task == "default" else 200
        if level == "status":
            return "clear"
        coarse_ok = item["final"] == supplied
        if level == "coarse":
            return "clear" if coarse_ok else "alarm"
        full_ok = coarse_ok and item["callback"] == [supplied]
        return "clear" if full_ok else "alarm"

    out = {}
    for level in ("status", "coarse", "full"):
        out[level] = classify_edges(
            flag("parent", "default", level), flag("commit", "default", level),
            flag("parent", "explicit", level), flag("commit", "explicit", level))
    return out


def observer_gaps(result: dict) -> int:
    gaps = 0
    for check in result.get("checks", []):
        if check["class"] != "hit" or not check.get("coarse_edge"):
            continue
        coarse = check["coarse_edge"]
        if classify_edges("clear", "clear", coarse["edge_parent"], coarse["edge_repair"]) != "hit":
            gaps += 1
    return gaps


def main() -> None:
    freeze_ready()
    cases = load_json(HERE / "cases.json")["cases"]
    replay = {item["pr"]: item for item in load_json(REPLAY)["outcomes"]}
    paired = load_json(PAIRED)
    archive = load_json(ARCHIVE)
    DOCS.mkdir(exist_ok=True)
    RESULTS.mkdir(exist_ok=True)
    cache = {}
    scored = []
    for case in cases:
        fetched = [fetch_source(source, cache) for source in case["sources"]]
        text, parse_error, fetch_error = document_text(fetched)
        if not text and not fetch_error:
            missing = [symbol for item in fetched for symbol in item.get("missing_symbols", [])]
            if missing:
                fetch_error = "missing_symbol: " + ", ".join(missing)
        (DOCS / f"{case['id']}.txt").write_text(text, encoding="utf-8")
        bind_doc = translate_document(text, "bind")
        jdoctor_doc = translate_document(text, "jdoctor")
        if case.get("observations") == "archive":
            obs = archive["observations"]
            by_key = {(item["side"], item["task"]): item for item in obs}
            def archived(side, task):
                item = by_key[(side, task)]
                return {"ok": True, "fine": {"final": item["final"], "callback": item["callback"]}, "coarse": {"final": item["final"]}}
            views = {
                "ordinary_parent": archived("parent", "default"),
                "ordinary_repair": archived("commit", "default"),
                "edge_parent": archived("parent", "explicit"),
                "edge_repair": archived("commit", "explicit"),
            }
            parent_views = [views["ordinary_parent"], views["edge_parent"]]
            published = published_attrs(obs)
        elif case["shape"] == "edges":
            outcome = replay[case["pr"]]
            views = edge_views(outcome["parent_rows"], outcome["fixed_rows"], lambda row: normalize_replay(row["actual"]))
            parent_views = [views["ordinary_parent"], views["edge_parent"]]
            published = published_edges(outcome["parent_rows"], outcome["fixed_rows"])
        else:
            bundle = paired[case["data_key"]]
            pairs = [(normalize_object(before["actual"]), normalize_object(after["actual"]))
                     for before, after in zip(bundle["before"]["rows"], bundle["after"]["rows"], strict=True)]
            views = {"pairs": pairs}
            parent_views = [parent for parent, _repair in pairs]
            published = published_pairs(bundle["before"]["rows"], bundle["after"]["rows"])
        union = {"checks": bind_doc["checks"] + jdoctor_doc["checks"], "tagged": bind_doc["tagged"], "doctests": bind_doc["doctests"]}
        bind_result = method_class(bind_doc["checks"], views, case["shape"])
        jdoctor_result = method_class(jdoctor_doc["checks"], views, case["shape"])
        status = status_class(views, case["shape"])
        agora = agora_class(parent_views, views, case["shape"])
        label = audit(union, parse_error, fetch_error, evaluable(union["checks"], views, case["shape"]))
        scored.append({
            "id": case["id"],
            "project": case["project"],
            "stratum": case["stratum"],
            "denominator": case["denominator"],
            "same_group": case.get("same_group"),
            "audit": label,
            "catalog_gap": label == "catalog_gap",
            "doctests": bind_doc["doctests"],
            "fetch": [{key: value for key, value in item.items() if key != "text"} for item in fetched],
            "bind": bind_result,
            "jdoctor_pattern": jdoctor_result,
            "status_only": status,
            "agora_restricted": agora,
            "published_observer": published,
            "full_hit_coarse_miss": observer_gaps(bind_result),
            "views": views,
        })
    primary = [row for row in scored if row["denominator"]]
    decision = decide([
        {
            "id": row["id"],
            "project": row["project"],
            "bind": row["bind"]["class"],
            "jdoctor": row["jdoctor_pattern"]["class"],
            "status": row["status_only"],
            "catalog_gap": row["catalog_gap"],
        }
        for row in primary
    ])
    head = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", "research/release_drift_20261126/contract_binding/protocol.md"], cwd=ROOT, text=True).strip()
    summary = {
        "freeze_commit": head,
        "hashes": {path.name: file_sha(path) for path in FREEZE},
        "not_run": {
            "jdoctor_binary": "Java source in, Java expressions out; pattern transcription is not the original program",
            "spark_formal": "no SPARK or Ada contract in the frozen public cases",
            "gay_oracle_selection": "no mutation campaign; expected values are not given to the extractors",
            "agora_plus_binary": "REST and modified Daikon; only the restricted invariant instance ran",
            "specfuzzer": "Java trace inference; not ported",
            "hypothesis_and_frozen_synthesizer": "would generate new inputs or restart a paused ESWA prototype",
        },
        "decision": decision,
        "primary_classes": {row["id"]: {"bind": row["bind"]["class"], "jdoctor_pattern": row["jdoctor_pattern"]["class"], "status_only": row["status_only"], "agora_restricted": row["agora_restricted"]["class"], "audit": row["audit"], "published_observer": row["published_observer"], "full_hit_coarse_miss": row["full_hit_coarse_miss"]} for row in primary},
        "calibration_classes": {row["id"]: {"bind": row["bind"]["class"], "jdoctor_pattern": row["jdoctor_pattern"]["class"], "status_only": row["status_only"], "agora_restricted": row["agora_restricted"]["class"], "audit": row["audit"], "published_observer": row["published_observer"]} for row in scored if not row["denominator"]},
        "cases": scored,
    }
    destination = RESULTS / "summary.json"
    assert_allowed(destination, write=True)
    destination.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"decision": decision, "primary": summary["primary_classes"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
