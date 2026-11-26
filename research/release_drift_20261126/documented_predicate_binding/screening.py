"""Bounded public-repair search. No scores and no sealed labels.

The inclusion rule is select_obligation plus the survival and file checks below.
Search order, caps, and the title filter are fixed by protocol.md.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from sentence_grounded import (
    behavior_word,
    normalized,
    obligation_sentences,
    quote_in_document,
    select_obligation,
)


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
DOCS = HERE / "docs"
LOG_PATH = HERE / "screening.json"

POOL = (
    "click",
    "requests",
    "httpx",
    "pydantic",
    "pytest",
    "Jinja2",
    "flask",
    "werkzeug",
    "marshmallow",
    "jsonschema",
    "python-dateutil",
    "arrow",
    "attrs",
    "rich",
    "hypothesis",
    "lxml",
    "beautifulsoup4",
    "PyYAML",
    "toml",
    "tomli",
)
EXCLUDED_PRS = {
    "Textualize/rich": {3718},
    "python-attrs/attrs": {1427, 1428},
}
EXAMINE_CAP = 40
INCLUDE_CAP = 10
SEARCH_PAGE = 30
PY_FILES_PER_PR = 5
TITLE_SKIP = re.compile(r"(?i)\b(bump|dependency|dependencies|changelog|typo|spelling|whitespace)\b")
FORBIDDEN_REPO = re.compile(r"(?i)pandas|pillow|scipy")


def relevance(title: str) -> int:
    if re.search(r"(?i)\b(raise|raises|raised|exception)\b", title or ""):
        return 0
    if re.search(r"(?i)\b(return|returns|value|incorrect|wrong)\b", title or ""):
        return 1
    return 2


def queue_skip_reason(repo: str, number: int, title: str) -> str | None:
    if number in EXCLUDED_PRS.get(repo, set()):
        return "excluded_prior_study"
    if TITLE_SKIP.search(title or ""):
        return "title_not_behavior"
    return None


def is_test_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    lowered = path.lower()
    return (
        "/test/" in f"/{lowered}"
        or "/tests/" in f"/{lowered}"
        or name.startswith("test_")
        or name.endswith("_test.py")
        or "/testing/" in f"/{lowered}"
    )


def is_doc_path(path: str) -> bool:
    lowered = path.lower()
    if not lowered.endswith((".rst", ".md")):
        return False
    return lowered.startswith(("doc/", "docs/")) or "/doc/" in f"/{lowered}" or "/docs/" in f"/{lowered}"


def parent_line_numbers(patch: str | None) -> set[int]:
    lines = set()
    old = None
    for line in (patch or "").splitlines():
        if line.startswith("@@"):
            match = re.search(r"@@ -(\d+)", line)
            old = int(match.group(1)) if match else None
            continue
        if old is None or line.startswith("+") or line.startswith("\\"):
            continue
        lines.add(old)
        old += 1
    return lines


def iter_symbols(source: str) -> list[dict]:
    tree = ast.parse(source)
    found = []

    def walk(nodes, prefix: str) -> None:
        for node in nodes:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = f"{prefix}.{node.name}" if prefix else node.name
                found.append({
                    "qualname": name,
                    "lineno": node.lineno,
                    "end": getattr(node, "end_lineno", None) or node.lineno,
                    "doc": ast.get_docstring(node) or "",
                })
                walk(node.body, name)

    walk(tree.body, "")
    return found


def symbols_touching(symbols: list[dict], lines: set[int]) -> list[dict]:
    hits = []
    for symbol in symbols:
        span = set(range(symbol["lineno"], symbol["end"] + 1))
        if span & lines:
            hits.append(symbol)
    hits.sort(key=lambda item: (item["end"] - item["lineno"], item["lineno"]))
    return hits


def heading_sections(text: str) -> list[dict]:
    lines = text.splitlines()
    marks = []
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        markdown = re.match(r"^(#{1,6})\s+\S", stripped)
        if markdown:
            marks.append((index + 1, len(markdown.group(1)), lines[index]))
            index += 1
            continue
        if index + 1 < len(lines) and re.fullmatch(r"[=\-~^]{3,}", lines[index + 1].strip()) and stripped:
            marks.append((index + 1, 1, lines[index]))
            index += 2
            continue
        index += 1
    if not marks:
        if text.strip():
            return [{"heading": "", "text": text, "start": 1, "end": max(1, len(lines))}]
        return []
    sections = []
    for position, (start, _level, heading) in enumerate(marks):
        stop = marks[position + 1][0] - 1 if position + 1 < len(marks) else len(lines)
        body = "\n".join(lines[start - 1:stop])
        sections.append({"heading": heading.strip(), "text": body, "start": start, "end": stop})
    return sections


def evidence_snippet(prose: str, needle: str) -> str:
    for line in (prose or "").splitlines():
        if needle and needle.lower() in line.lower():
            return line.strip()[:300]
    compact = re.sub(r"\s+", " ", prose or "").strip()
    return compact[:300]


def case_id(project: str, number: int) -> str:
    return f"{project.lower()}-{number}"


def adjudicate(candidates: list[dict], prose: str, fix_text_for) -> dict:
    """Pick at most one surviving parent sentence.

    candidates: {key, qualname, document, path, url, file_sha256}
    fix_text_for(key) -> fix-side text or "".
    """
    evaluated = []
    for candidate in candidates:
        sentences = obligation_sentences(candidate.get("document") or "")
        choice = select_obligation(sentences, prose, candidate.get("qualname") or "")
        evaluated.append((candidate, sentences, choice))
    includes = []
    absent = []
    for candidate, _sentences, choice in evaluated:
        if choice["reason"] != "include" or not choice.get("sentence"):
            continue
        fix_text = fix_text_for(candidate["key"])
        if not quote_in_document(choice["sentence"], fix_text or ""):
            absent.append(choice["sentence"])
            continue
        includes.append((candidate, choice))
    if absent and includes:
        return {
            "decision": "exclude",
            "reason": "ambiguous_obligation",
            "quote": None,
            "candidates": [item[1]["sentence"] for item in includes] + absent,
        }
    if len(includes) == 1:
        candidate, choice = includes[0]
        return {
            "decision": "include",
            "reason": "parent_sentence_states_obligation",
            "link": choice["link"],
            "quote": choice["sentence"],
            "tokens": choice["tokens"],
            "qualname": candidate.get("qualname"),
            "path": candidate.get("path"),
            "url": candidate.get("url"),
            "file_sha256": candidate.get("file_sha256"),
            "key": candidate.get("key"),
            "document": candidate.get("document") or "",
        }
    if len(includes) > 1:
        token_hits = [item for item in includes if item[1]["link"] == "shared_token"]
        if len(token_hits) == 1:
            candidate, choice = token_hits[0]
            return {
                "decision": "include",
                "reason": "parent_sentence_states_obligation",
                "link": choice["link"],
                "quote": choice["sentence"],
                "tokens": choice["tokens"],
                "qualname": candidate.get("qualname"),
                "path": candidate.get("path"),
                "url": candidate.get("url"),
                "file_sha256": candidate.get("file_sha256"),
                "key": candidate.get("key"),
                "document": candidate.get("document") or "",
            }
        return {
            "decision": "exclude",
            "reason": "ambiguous_obligation",
            "quote": None,
            "candidates": [item[1]["sentence"] for item in includes],
        }
    if absent:
        return {"decision": "exclude", "reason": "parent_sentence_absent_from_fix", "quote": absent[0]}
    for _candidate, sentences, choice in evaluated:
        if sentences and choice["reason"] in {
            "ambiguous_obligation",
            "predicate_not_about_recorded_difference",
        }:
            return {"decision": "exclude", "reason": choice["reason"], "quote": None}
    if not any((candidate.get("document") or "").strip() for candidate in candidates):
        return {"decision": "exclude", "reason": "no_parent_sentence", "quote": None}
    return {"decision": "exclude", "reason": "no_parent_sentence", "quote": None}


def prose_has_behavior(prose: str) -> bool:
    return behavior_word(prose)


def _request(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "documented-predicate-binding"})
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read()


def pypi_github(name: str) -> tuple[str | None, str]:
    payload = json.loads(_request(f"https://pypi.org/pypi/{urllib.parse.quote(name)}/json").decode("utf-8"))
    info = payload.get("info") or {}
    urls = []
    for key in ("Source", "Source Code", "Repository", "Homepage", "Home"):
        value = (info.get("project_urls") or {}).get(key)
        if value:
            urls.append(value)
    if info.get("home_page"):
        urls.append(info["home_page"])
    for candidate in urls:
        match = re.search(r"github\.com[:/]+([^/\s]+)/([^/#\s]+)", candidate, re.I)
        if not match:
            continue
        repo = match.group(2)
        if repo.endswith(".git"):
            repo = repo[:-4]
        full = f"{match.group(1)}/{repo}"
        if FORBIDDEN_REPO.search(full) or FORBIDDEN_REPO.search(name):
            return None, candidate
        return full, candidate
    return None, ""


def gh_json(path: str):
    completed = subprocess.run(
        ["gh", "api", path],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "gh api failed")
    return json.loads(completed.stdout)


def search_fix_prs(repo: str) -> list[dict]:
    query = f"repo:{repo} is:pr is:merged fix in:title"
    encoded = urllib.parse.urlencode({
        "q": query,
        "sort": "updated",
        "order": "desc",
        "per_page": str(SEARCH_PAGE),
    })
    payload = gh_json(f"search/issues?{encoded}")
    if "items" not in payload:
        raise RuntimeError(str(payload)[:300])
    found = []
    for item in payload.get("items") or []:
        if "pull_request" not in item:
            continue
        found.append({
            "number": item["number"],
            "title": item.get("title") or "",
            "html_url": item.get("html_url") or "",
        })
    found.sort(key=lambda item: relevance(item["title"]))
    return found


def fetch_text(repo: str, sha: str, path: str) -> str:
    quoted = urllib.parse.quote(path, safe="/")
    url = f"https://raw.githubusercontent.com/{repo}/{sha}/{quoted}"
    data = _request(url)
    if len(data) > 1_000_000:
        raise RuntimeError("file_too_large")
    return data.decode("utf-8", errors="replace")


def file_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def linked_issue_number(repo: str, pr_number: int, body: str) -> int | None:
    for match in re.finditer(r"(?:https://github\.com/[^/\s]+/[^/\s]+/issues/|#)(\d+)", body or ""):
        number = int(match.group(1))
        if number != pr_number:
            return number
    return None


def assert_clean() -> str:
    paths = [
        HERE / "protocol.md",
        HERE / "sentence_grounded.py",
        HERE / "screening.py",
    ]
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--", *[str(path) for path in paths]],
        cwd=ROOT,
        text=True,
    )
    if dirty.strip():
        raise SystemExit("protocol or method files are dirty; refusing to screen\n" + dirty)
    for path in paths:
        text = str(path.resolve())
        if "sealed" in text.lower() or "environment_receipts" in text:
            raise SystemExit(f"refusing sealed path: {path}")
    return subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--", "research/release_drift_20261126/documented_predicate_binding/protocol.md"],
        cwd=ROOT,
        text=True,
    ).strip()


def _save(state: dict) -> None:
    LOG_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _behavior_quote(prose: str, quote: str, tokens: list[str]) -> str:
    needle = ""
    if tokens:
        needle = tokens[0].split(":", 1)[1]
    elif quote:
        words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", quote)
        needle = words[-1] if words else ""
    return evidence_snippet(prose, needle)


def examine(state: dict, project: str, repo: str, item: dict) -> dict:
    number = item["number"]
    record = {
        "id": case_id(project, number),
        "library": project,
        "repo": repo,
        "number": number,
        "title": item["title"],
        "pr_url": item["html_url"],
        "parent_sha": None,
        "fix_sha": None,
        "quote": None,
        "quote_path": None,
        "behavior_quote": None,
        "issue_url": None,
        "decision": "exclude",
        "reason": "api_error",
    }
    try:
        pull = gh_json(f"repos/{repo}/pulls/{number}")
    except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        record["reason"] = "api_error"
        record["error"] = str(exc)[:300]
        return record
    merge = pull.get("merge_commit_sha")
    if not merge:
        record["reason"] = "not_merged_on_github"
        return record
    try:
        commit = gh_json(f"repos/{repo}/commits/{merge}")
        parent = (commit.get("parents") or [{}])[0].get("sha")
    except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired, IndexError) as exc:
        record["error"] = str(exc)[:300]
        return record
    if not parent:
        record["reason"] = "not_merged_on_github"
        return record
    record["parent_sha"] = parent
    record["fix_sha"] = merge
    body = pull.get("body") or ""
    issue_number = linked_issue_number(repo, number, body)
    issue_body = ""
    if issue_number is not None:
        record["issue_url"] = f"https://github.com/{repo}/issues/{issue_number}"
        try:
            issue = gh_json(f"repos/{repo}/issues/{issue_number}")
            if "pull_request" not in issue:
                issue_body = issue.get("body") or ""
        except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired):
            issue_body = ""
    prose = "\n".join([item["title"], body, issue_body])
    try:
        files = gh_json(f"repos/{repo}/pulls/{number}/files?per_page=100")
    except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        record["error"] = str(exc)[:300]
        return record
    if not isinstance(files, list):
        record["reason"] = "api_error"
        record["error"] = "file list was not a list"
        return record
    py_files = [
        entry for entry in files
        if entry.get("status") == "modified"
        and str(entry.get("filename", "")).endswith(".py")
        and not is_test_path(entry.get("filename") or "")
    ][:PY_FILES_PER_PR]
    doc_files = [
        entry for entry in files
        if entry.get("status") == "modified" and is_doc_path(entry.get("filename") or "")
    ][:PY_FILES_PER_PR]
    if not py_files and not doc_files:
        record["reason"] = "not_a_behavior_repair"
        return record
    candidates = []
    fix_cache = {}

    def add_python(entry: dict) -> None:
        path = entry["filename"]
        try:
            source = fetch_text(repo, parent, path)
        except (urllib.error.URLError, RuntimeError, TimeoutError) as exc:
            record.setdefault("fetch_errors", []).append(f"{path}: {exc}"[:200])
            return
        try:
            symbols = iter_symbols(source)
        except SyntaxError:
            return
        touched = symbols_touching(symbols, parent_line_numbers(entry.get("patch")))
        for symbol in touched:
            if not symbol["doc"]:
                continue
            key = f"{path}:{symbol['qualname']}"
            candidates.append({
                "key": key,
                "qualname": symbol["qualname"],
                "document": symbol["doc"],
                "path": path,
                "url": f"https://github.com/{repo}/blob/{parent}/{path}",
                "file_sha256": file_sha(source),
            })

    def add_doc(entry: dict) -> None:
        path = entry["filename"]
        try:
            source = fetch_text(repo, parent, path)
        except (urllib.error.URLError, RuntimeError, TimeoutError) as exc:
            record.setdefault("fetch_errors", []).append(f"{path}: {exc}"[:200])
            return
        touched = parent_line_numbers(entry.get("patch"))
        for section in heading_sections(source):
            span = set(range(section["start"], section["end"] + 1))
            if touched and not (span & touched):
                continue
            key = f"{path}:{section['start']}"
            candidates.append({
                "key": key,
                "qualname": section["heading"].lstrip("#").strip(),
                "document": section["text"],
                "path": path,
                "url": f"https://github.com/{repo}/blob/{parent}/{path}",
                "file_sha256": file_sha(source),
            })

    for entry in py_files:
        add_python(entry)
    if not any(obligation_sentences(item["document"]) for item in candidates):
        for entry in doc_files:
            add_doc(entry)

    def fix_text_for(key: str) -> str:
        if key in fix_cache:
            return fix_cache[key]
        path, _, ident = key.partition(":")
        try:
            source = fetch_text(repo, merge, path)
        except (urllib.error.URLError, RuntimeError, TimeoutError):
            fix_cache[key] = ""
            return ""
        text = ""
        if path.endswith(".py"):
            try:
                for symbol in iter_symbols(source):
                    if symbol["qualname"] == ident:
                        text = symbol["doc"]
                        break
            except SyntaxError:
                text = ""
        else:
            text = source
        fix_cache[key] = text
        return text

    judged = adjudicate(candidates, prose, fix_text_for)
    record["decision"] = judged["decision"]
    record["reason"] = judged["reason"]
    record["quote"] = judged.get("quote")
    record["link"] = judged.get("link")
    record["tokens"] = judged.get("tokens")
    record["quote_path"] = judged.get("path")
    record["qualname"] = judged.get("qualname")
    record["parent_url"] = judged.get("url")
    record["file_sha256"] = judged.get("file_sha256")
    if judged["decision"] == "include":
        document = judged.get("document") or ""
        if not quote_in_document(judged.get("quote") or "", document):
            record["decision"] = "exclude"
            record["reason"] = "quote_not_in_fetched_parent"
            return record
        record["behavior_quote"] = _behavior_quote(prose, judged.get("quote") or "", judged.get("tokens") or [])
        DOCS.mkdir(parents=True, exist_ok=True)
        (DOCS / f"{record['id']}.txt").write_text(document, encoding="utf-8")
    return record


def screen() -> dict:
    freeze = assert_clean()
    if LOG_PATH.exists():
        state = json.loads(LOG_PATH.read_text(encoding="utf-8"))
    else:
        state = {
            "freeze_commit": freeze,
            "libraries": {},
            "queues": {},
            "title_skipped": [],
            "examined": [],
            "included_count": 0,
            "stopped_because": None,
        }
        for project in POOL:
            try:
                repo, source = pypi_github(project)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
                state["libraries"][project] = {"repo": None, "error": str(exc)[:300]}
                state["queues"][project] = []
                continue
            state["libraries"][project] = {"repo": repo, "source": source}
            if not repo:
                state["queues"][project] = []
                continue
            try:
                found = search_fix_prs(repo)
            except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
                state["libraries"][project]["error"] = str(exc)[:300]
                state["queues"][project] = []
                continue
            queue = []
            for item in found:
                reason = queue_skip_reason(repo, item["number"], item["title"])
                if reason:
                    state["title_skipped"].append({
                        "library": project,
                        "repo": repo,
                        "number": item["number"],
                        "title": item["title"],
                        "pr_url": item["html_url"],
                        "reason": reason,
                    })
                    continue
                queue.append(item)
            state["queues"][project] = queue
        _save(state)
    if state.get("stopped_because"):
        return state
    seen = {item["pr_url"] for item in state["examined"]}
    while state["included_count"] < INCLUDE_CAP and len(state["examined"]) < EXAMINE_CAP:
        progressed = False
        for project in POOL:
            if state["included_count"] >= INCLUDE_CAP or len(state["examined"]) >= EXAMINE_CAP:
                break
            queue = state["queues"].get(project) or []
            repo = (state["libraries"].get(project) or {}).get("repo")
            while queue and queue[0]["html_url"] in seen:
                queue.pop(0)
            if not queue or not repo:
                state["queues"][project] = queue
                continue
            item = queue.pop(0)
            state["queues"][project] = queue
            record = examine(state, project, repo, item)
            state["examined"].append(record)
            seen.add(item["html_url"])
            if record["decision"] == "include":
                state["included_count"] += 1
            progressed = True
            _save(state)
            print(f"{len(state['examined']):02d} {record['decision']:7} {record['id']} {record['reason']}", flush=True)
        if not progressed:
            state["stopped_because"] = "queues_exhausted"
            break
    if not state.get("stopped_because"):
        if state["included_count"] >= INCLUDE_CAP:
            state["stopped_because"] = "10_included"
        elif len(state["examined"]) >= EXAMINE_CAP:
            state["stopped_because"] = "40_examined"
        else:
            state["stopped_because"] = "queues_exhausted"
    state["freeze_commit"] = freeze
    _save(state)
    return state


if __name__ == "__main__":
    result = screen()
    print(json.dumps({
        "examined": len(result["examined"]),
        "included": result["included_count"],
        "stopped_because": result["stopped_because"],
        "freeze_commit": result["freeze_commit"],
    }, indent=2))
