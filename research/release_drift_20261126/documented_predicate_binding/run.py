"""Score frozen cases. Refuse dirty protocol, extractor, or case files.

Observations are cached under results/observations so a rerun does not reinstall.
Extractors see the cached parent document and those observations only.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from sentence_grounded import (
    NOT_RUN,
    audit_human,
    canonical,
    decide,
    full_separates,
    quote_in_document,
    summarize_grounded,
    summarize_human,
    summarize_status,
    summarize_translated,
)


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
DOCS = HERE / "docs"
CASES = HERE / "cases.json"
SCREENING = HERE / "screening.json"
RESULTS = HERE / "results"
OBS = RESULTS / "observations"
INSTALL_TIMEOUT = 300
CALL_TIMEOUT = 45
FORBIDDEN = re.compile(r"(?i)pandas|pillow|scipy|sealed|environment_receipts")


def assert_allowed(path: Path) -> None:
    text = str(path.resolve()).replace("\\", "/")
    if FORBIDDEN.search(text):
        raise SystemExit(f"refusing sealed or out-of-study path: {path}")


def file_sha(path: Path) -> str:
    assert_allowed(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze_commit() -> str:
    return subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--",
         "research/release_drift_20261126/documented_predicate_binding/protocol.md"],
        cwd=ROOT,
        text=True,
    ).strip()


def assert_score_ready() -> None:
    paths = [HERE / "protocol.md", HERE / "sentence_grounded.py", HERE / "run.py", CASES, DOCS]
    missing = [path for path in paths if not path.exists()]
    if missing:
        raise SystemExit("cases are not frozen; refusing to score: " + ", ".join(str(path) for path in missing))
    dirty = subprocess.check_output(
        ["git", "status", "--porcelain", "--", *[str(path) for path in paths]],
        cwd=ROOT,
        text=True,
    )
    if dirty.strip():
        raise SystemExit("freeze files have uncommitted changes; refusing to score\n" + dirty)
    for path in paths:
        assert_allowed(path)


def load_cases() -> dict:
    assert_allowed(CASES)
    return json.loads(CASES.read_text(encoding="utf-8"))


def assert_matches_screening(cases: dict) -> None:
    assert_allowed(SCREENING)
    log = json.loads(SCREENING.read_text(encoding="utf-8"))
    included = [item["id"] for item in log.get("examined") or [] if item.get("decision") == "include"]
    chosen = [group["id"] for group in cases.get("groups") or []]
    if set(included) != set(chosen) or len(included) != len(set(included)):
        raise SystemExit("cases.json does not match the screening includes")


def audit_driver(driver: str, import_name: str) -> None:
    if not isinstance(driver, str) or driver.count("\n") > 80:
        raise SystemExit("driver is missing or longer than 80 lines")
    if "def call(" not in driver:
        raise SystemExit("driver must define call()")
    if re.search(r"(?m)^\s*assert\b", driver) or re.search(r"\boracle\b", driver):
        raise SystemExit("driver must not assert or mention an oracle")
    if import_name not in driver:
        raise SystemExit(f"driver does not import {import_name}")
    if FORBIDDEN.search(driver):
        raise SystemExit("driver names a forbidden library")


def validate(cases: dict) -> None:
    seen = set()
    for group in cases.get("groups") or []:
        if group["id"] in seen:
            raise SystemExit(f"duplicate group {group['id']}")
        seen.add(group["id"])
        if FORBIDDEN.search(group.get("repo", "")) or FORBIDDEN.search(group.get("import_name", "")):
            raise SystemExit(f"forbidden library in {group['id']}")
        for side in ("parent_sha", "fix_sha"):
            if not re.fullmatch(r"[0-9a-f]{40}", group.get(side, "")):
                raise SystemExit(f"{group['id']} has no {side}")
        document_path = DOCS / f"{group['id']}.txt"
        assert_allowed(document_path)
        document = document_path.read_text(encoding="utf-8")
        if not quote_in_document(group["quote"], document):
            raise SystemExit(f"quote is not in the cached parent document: {group['id']}")
        expr = group.get("human_from_sentence")
        if expr is None:
            if group.get("human_reason") not in {"condition_not_encodable", "not_in_expression_language"}:
                raise SystemExit(f"{group['id']} needs a human check or an explicit reason")
        elif not audit_human(expr, group["quote"]):
            raise SystemExit(f"human check is not grounded in the parent sentence: {group['id']}")
        audit_driver(group["driver"], group["import_name"])
        if group.get("ordinary_driver"):
            audit_driver(group["ordinary_driver"], group["import_name"])
            if not isinstance(group.get("ordinary_inputs"), dict):
                raise SystemExit(f"{group['id']} ordinary driver needs inputs")
        if not isinstance(group.get("inputs"), dict):
            raise SystemExit(f"{group['id']} inputs must be an object")


def run_driver(python: str, driver: str, inputs: dict) -> dict:
    with tempfile.TemporaryDirectory(prefix="dpb-call-") as tmp:
        folder = Path(tmp)
        (folder / "dpb_driver.py").write_text("inputs = {}\n" + driver, encoding="utf-8")
        harness = folder / "dpb_harness.py"
        harness.write_text(
            "import importlib.util, json, sys\n"
            "folder = sys.argv[1]\n"
            "spec = importlib.util.spec_from_file_location('dpb_driver', folder + '/dpb_driver.py')\n"
            "module = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(module)\n"
            "module.inputs = json.loads(sys.argv[2])\n"
            "try:\n"
            "    value = module.call()\n"
            "except Exception as exc:\n"
            "    json.dump({'ok': False, 'exc_type': type(exc).__name__, 'message': str(exc)[:2000]}, sys.stdout)\n"
            "    sys.exit(0)\n"
            "try:\n"
            "    json.dumps(value)\n"
            "except (TypeError, ValueError):\n"
            "    json.dump({'ok': True, 'jsonable': False, 'repr': repr(value)[:2000]}, sys.stdout)\n"
            "    sys.exit(0)\n"
            "json.dump({'ok': True, 'jsonable': True, 'value': value}, sys.stdout)\n",
            encoding="utf-8",
        )
        completed = subprocess.run(
            [python, str(harness), str(folder), json.dumps(inputs)],
            cwd=folder,
            text=True,
            capture_output=True,
            timeout=CALL_TIMEOUT,
            check=False,
        )
    if completed.returncode != 0:
        return {
            "ok": False,
            "exc_type": "HarnessError",
            "message": (completed.stderr or completed.stdout or "harness failed")[:2000],
        }
    return json.loads(completed.stdout)


def pip_spec(repo: str, sha: str) -> str:
    return f"git+https://github.com/{repo}.git@{sha}"


def install_and_call(group: dict, sha: str, label: str) -> dict:
    work = Path(tempfile.mkdtemp(prefix=f"dpb-{group['id']}-{label}-"))
    try:
        venv = work / "venv"
        created = subprocess.run(
            [sys.executable, "-m", "venv", str(venv)],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if created.returncode != 0:
            return {"ok": False, "exc_type": "InstallError", "message": created.stderr[-2000:]}
        python = venv / "bin" / "python"
        pip = venv / "bin" / "pip"
        installed = subprocess.run(
            [str(pip), "install", "--disable-pip-version-check", pip_spec(group["repo"], sha)],
            check=False,
            capture_output=True,
            text=True,
            timeout=INSTALL_TIMEOUT,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "PIP_DISABLE_PIP_VERSION_CHECK": "1"},
        )
        if installed.returncode != 0:
            message = (installed.stderr or installed.stdout or "pip failed")[-2000:]
            return {"ok": False, "exc_type": "InstallError", "message": message}
        observation = run_driver(str(python), group["driver"], group["inputs"])
        ordinary = None
        if group.get("ordinary_driver"):
            ordinary = run_driver(str(python), group["ordinary_driver"], group["ordinary_inputs"])
        version = subprocess.run(
            [str(python), "-c", "import sys; print(sys.version.split()[0])"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {
            "observation": observation,
            "ordinary": ordinary,
            "python": version.stdout.strip(),
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def execute_group(group: dict) -> dict:
    started = time.perf_counter()
    parent = install_and_call(group, group["parent_sha"], "parent")
    fix = install_and_call(group, group["fix_sha"], "fix")
    payload = {
        "id": group["id"],
        "seconds": round(time.perf_counter() - started, 3),
        "parent_call": parent,
        "fix_call": fix,
    }
    parent_obs = parent.get("observation")
    fix_obs = fix.get("observation")
    runnable = (
        parent_obs and fix_obs
        and parent_obs.get("exc_type") != "InstallError"
        and fix_obs.get("exc_type") != "InstallError"
        and parent_obs.get("exc_type") != "HarnessError"
        and fix_obs.get("exc_type") != "HarnessError"
    )
    payload["runnable"] = bool(runnable)
    if not runnable:
        payload["error"] = "not_runnable"
    return payload


def score_group(group: dict, executed: dict) -> dict:
    document = (DOCS / f"{group['id']}.txt").read_text(encoding="utf-8")
    if not executed.get("runnable"):
        return {
            "id": group["id"],
            "project": group.get("project") or group["id"].split("-")[0],
            "pr_url": group["pr_url"],
            "quote": group["quote"],
            "runnable": False,
            "reproduced": False,
            "error": executed.get("error"),
            "seconds": executed.get("seconds"),
        }
    parent = executed["parent_call"]["observation"]
    fix = executed["fix_call"]["observation"]
    ordinary = None
    if executed["parent_call"].get("ordinary") and executed["fix_call"].get("ordinary"):
        ordinary = {
            "parent": executed["parent_call"]["ordinary"],
            "fix": executed["fix_call"]["ordinary"],
            "inputs": group.get("ordinary_inputs") or {},
        }
    reproduced = full_separates(parent, fix)
    result = {
        "id": group["id"],
        "project": group.get("project") or group["id"].split("-")[0],
        "pr_url": group["pr_url"],
        "issue_url": group.get("issue_url"),
        "parent_sha": group["parent_sha"],
        "fix_sha": group["fix_sha"],
        "quote": group["quote"],
        "qualname": group.get("qualname"),
        "doc_path": group.get("doc_path"),
        "runnable": True,
        "reproduced": reproduced,
        "seconds": executed.get("seconds"),
        "parent": parent,
        "fix": fix,
        "parent_canonical": canonical(parent),
        "fix_canonical": canonical(fix),
        "status_only": summarize_status(parent, fix, ordinary),
        "jdoctor_pattern": summarize_translated("jdoctor_pattern", document, parent, fix, ordinary),
        "bind": summarize_translated("bind", document, parent, fix, ordinary),
        "sentence_grounded": summarize_grounded(document, parent, fix, ordinary),
        "human_from_sentence": summarize_human(
            group.get("human_from_sentence"), parent, fix, group.get("inputs") or {}, ordinary
        ),
        "full_output": {"separates": reproduced, "executable": True},
    }
    return result


def tally(groups: list[dict]) -> dict:
    methods = (
        "status_only", "jdoctor_pattern", "bind", "sentence_grounded",
        "human_from_sentence", "full_output",
    )
    counts = {name: {"executable": 0, "separates": 0} for name in methods}
    for group in groups:
        for name in methods:
            block = group[name]
            if block.get("executable"):
                counts[name]["executable"] += 1
            if block.get("separates"):
                counts[name]["separates"] += 1
    return counts


def main() -> None:
    assert_score_ready()
    cases = load_cases()
    assert_matches_screening(cases)
    validate(cases)
    OBS.mkdir(parents=True, exist_ok=True)
    scored = []
    for group in cases["groups"]:
        cache = OBS / f"{group['id']}.json"
        assert_allowed(cache)
        if cache.exists():
            executed = json.loads(cache.read_text(encoding="utf-8"))
        else:
            executed = execute_group(group)
            cache.write_text(json.dumps(executed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        scored.append(score_group(group, executed))
    reproduced = [group for group in scored if group.get("reproduced")]
    counts = tally(reproduced) if reproduced else {
        name: {"executable": 0, "separates": 0}
        for name in (
            "status_only", "jdoctor_pattern", "bind", "sentence_grounded",
            "human_from_sentence", "full_output",
        )
    }
    unsafe = any(
        group.get("sentence_grounded", {}).get("class") in {"inversion", "false_alarm"}
        for group in reproduced
    )
    decision = decide(len(reproduced), counts, unsafe)
    summary = {
        "freeze_commit": freeze_commit(),
        "scoring_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "protocol_sha256": file_sha(HERE / "protocol.md"),
        "sentence_grounded_sha256": file_sha(HERE / "sentence_grounded.py"),
        "run_sha256": file_sha(HERE / "run.py"),
        "included": len(scored),
        "reproduced": len(reproduced),
        "not_runnable": [group["id"] for group in scored if not group.get("runnable")],
        "not_reproduced": [group["id"] for group in scored if group.get("runnable") and not group.get("reproduced")],
        "decision": decision["decision"],
        "reason": decision["reason"],
        "ranking": None,
        "not_run": list(NOT_RUN),
        "counts": counts,
        "sentence_unsafe": unsafe,
        "groups": scored,
        "note": "This sample cannot replace the ISSRE 12-group contract-binding denominator or the formal sealed four.",
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "decision": summary["decision"],
        "reason": summary["reason"],
        "included": summary["included"],
        "reproduced": summary["reproduced"],
        "counts": counts,
    }, indent=2))


if __name__ == "__main__":
    main()
