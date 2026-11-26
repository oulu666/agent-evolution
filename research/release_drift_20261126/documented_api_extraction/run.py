"""Score frozen documented-API cases. Refuse a dirty freeze or a short denominator.

Extractors see the frozen docstring only. They do not see input labels, the
function body, or a gold table.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from outcomes import (
    FORBIDDEN,
    METHODS,
    MIN_INCLUDED,
    MIN_LIBRARIES,
    NOT_RUN,
    audit_driver,
    decide,
    score_grounded,
    score_human,
    score_translated,
    tally,
)


_PREDICATE = Path(__file__).resolve().parents[1] / "documented_predicate_binding"
if str(_PREDICATE) not in sys.path:
    sys.path.insert(0, str(_PREDICATE))

from sentence_grounded import audit_human, quote_in_document  # noqa: E402


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
DOCS = HERE / "docs"
CASES = HERE / "cases.json"
SCREENING = HERE / "screening.json"
RESULTS = HERE / "results"
OBS = RESULTS / "observations"
PROTOCOL = HERE / "protocol.md"
INSTALL_TIMEOUT = 300
CALL_TIMEOUT = 45
NOTE = (
    "This is extractor feasibility on current documented APIs. "
    "It is not silent-drift detection, not a repair-catching study, "
    "and it cannot replace the ISSRE 12 groups or the formal sealed four."
)


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze_commit() -> str:
    return subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--",
         "research/release_drift_20261126/documented_api_extraction/protocol.md"],
        cwd=ROOT,
        text=True,
    ).strip()


def assert_score_ready() -> None:
    paths = [
        PROTOCOL,
        HERE / "outcomes.py",
        HERE / "selection.py",
        HERE / "run.py",
        CASES,
        SCREENING,
        DOCS,
    ]
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


def load_json(path: Path) -> dict:
    if FORBIDDEN.search(str(path)):
        raise SystemExit(f"refusing sealed or out-of-study path: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def assert_matches_screening(cases: dict, screening: dict) -> None:
    included = [item["id"] for item in screening.get("records") or [] if item.get("decision") == "include"]
    chosen = [group["id"] for group in cases.get("groups") or []]
    if included != chosen or len(included) != len(set(included)):
        raise SystemExit("cases.json does not match the screening includes")


def validate(cases: dict, screening: dict) -> None:
    assert_matches_screening(cases, screening)
    screened = {item["id"]: item for item in screening["records"]}
    for group in cases["groups"]:
        if FORBIDDEN.search(group["pypi"]) or FORBIDDEN.search(group["import_name"]):
            raise SystemExit(f"forbidden library in {group['id']}")
        row = screened[group["id"]]
        if row["quote"] != group["quote"] or row["legal"] != group["legal"] or row["violating"] != group["violating"]:
            raise SystemExit(f"{group['id']} does not match the screening row")
        if group["legal"] == group["violating"] and type(group["legal"]) is type(group["violating"]):
            raise SystemExit(f"{group['id']} legal and violating inputs are the same")
        source = HERE / group["source_file"]
        docstring_path = HERE / group["docstring_file"]
        if file_sha(source) != group["file_sha256"]:
            raise SystemExit(f"source hash mismatch: {group['id']}")
        document = docstring_path.read_text(encoding="utf-8")
        if hashlib.sha256(document.encode("utf-8")).hexdigest() != group["docstring_sha256"]:
            raise SystemExit(f"docstring hash mismatch: {group['id']}")
        if document != (DOCS / f"{group['id']}.docstring.txt").read_text(encoding="utf-8"):
            raise SystemExit(f"docstring path mismatch: {group['id']}")
        source_text = source.read_text(encoding="utf-8")
        if not quote_in_document(group["quote"], source_text):
            raise SystemExit(f"quote is not in the frozen source: {group['id']}")
        if not quote_in_document(group["quote"], document):
            raise SystemExit(f"quote is not in the frozen docstring: {group['id']}")
        if not audit_human(group["human_from_sentence"], group["quote"]):
            raise SystemExit(f"human check is not grounded in the sentence: {group['id']}")
        audit_driver(group["driver"], group["import_name"])


def run_driver(python: str, driver: str, value) -> dict:
    with tempfile.TemporaryDirectory(prefix="dae-call-") as tmp:
        folder = Path(tmp)
        (folder / "dae_driver.py").write_text("inputs = {}\n" + driver, encoding="utf-8")
        harness = folder / "dae_harness.py"
        harness.write_text(
            "import importlib.util, json, socket, sys\n"
            "socket.setdefaulttimeout(2)\n"
            "folder = sys.argv[1]\n"
            "spec = importlib.util.spec_from_file_location('dae_driver', folder + '/dae_driver.py')\n"
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
        try:
            completed = subprocess.run(
                [python, str(harness), str(folder), json.dumps({"value": value})],
                cwd=folder,
                text=True,
                capture_output=True,
                timeout=CALL_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return {"ok": False, "exc_type": "TimeoutError", "message": str(exc)[:2000]}
    if completed.returncode != 0:
        return {
            "ok": False,
            "exc_type": "HarnessError",
            "message": (completed.stderr or completed.stdout or "harness failed")[:2000],
        }
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "exc_type": "HarnessError", "message": (completed.stdout or "")[:2000]}


def install_library(work: Path, pypi: str, version: str) -> dict:
    venv = work / "venv"
    created = subprocess.run(
        [sys.executable, "-m", "venv", str(venv)],
        check=False, capture_output=True, text=True, timeout=120,
    )
    if created.returncode != 0:
        return {"ok": False, "exc_type": "InstallError", "message": (created.stderr or "")[-2000:]}
    python = venv / "bin" / "python"
    pip = venv / "bin" / "pip"
    env = {**os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1", "GIT_TERMINAL_PROMPT": "0"}
    installed = subprocess.run(
        [str(pip), "install", "--disable-pip-version-check", f"{pypi}=={version}"],
        check=False, capture_output=True, text=True, timeout=INSTALL_TIMEOUT, env=env,
    )
    if installed.returncode != 0:
        message = (installed.stderr or installed.stdout or "pip failed")[-2000:]
        return {"ok": False, "exc_type": "InstallError", "message": message, "python": str(python)}
    probed = subprocess.run(
        [str(python), "-c",
         "import importlib.metadata as meta, sys\n"
         f"print(meta.version({pypi!r}))\n"
         "print(sys.version.split()[0])\n"],
        check=False, capture_output=True, text=True, timeout=30,
    )
    lines = (probed.stdout or "").splitlines()
    return {
        "ok": probed.returncode == 0 and bool(lines),
        "python": str(python),
        "package_version": lines[0] if lines else None,
        "python_version": lines[1] if len(lines) > 1 else None,
        "exc_type": None if probed.returncode == 0 else "InstallError",
        "message": (probed.stderr or "")[-2000:],
    }


def score_group(group: dict, legal_obs: dict, violating_obs: dict) -> dict:
    document = (DOCS / f"{group['id']}.docstring.txt").read_text(encoding="utf-8")
    return {
        "id": group["id"],
        "library": group["library"],
        "qualname": group["qualname"],
        "pattern": group["pattern"],
        "quote": group["quote"],
        "param": group["param"],
        "legal_input": group["legal"],
        "violating_input": group["violating"],
        "jdoctor_pattern": score_translated("jdoctor_pattern", document, group["quote"], legal_obs, violating_obs),
        "bind": score_translated("bind", document, group["quote"], legal_obs, violating_obs),
        "sentence_grounded": score_grounded(document, group["quote"], legal_obs, violating_obs),
        "human_from_sentence": score_human(group["human_from_sentence"], legal_obs, violating_obs),
    }


def write_summary(payload: dict) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def denominator_summary(cases: dict) -> dict:
    libraries = sorted({group["library"] for group in cases["groups"]})
    return {
        "freeze_commit": freeze_commit(),
        "scoring_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "protocol_sha256": file_sha(PROTOCOL),
        "included": len(cases["groups"]),
        "libraries_included": libraries,
        "scored": False,
        "decision": "insufficient_denominator",
        "reason": "fewer_than_8_or_fewer_than_3_libraries",
        "ranking": None,
        "counts": None,
        "not_run": list(NOT_RUN),
        "groups": [],
        "note": NOTE,
    }


def main() -> None:
    assert_score_ready()
    cases = load_json(CASES)
    screening = load_json(SCREENING)
    validate(cases, screening)
    if len(cases["groups"]) < MIN_INCLUDED or len({group["library"] for group in cases["groups"]}) < MIN_LIBRARIES:
        summary = denominator_summary(cases)
        write_summary(summary)
        print(json.dumps({"decision": summary["decision"], "included": summary["included"]}, indent=2))
        return
    OBS.mkdir(parents=True, exist_ok=True)
    by_library = {}
    for group in cases["groups"]:
        by_library.setdefault((group["pypi"], group["version"]), []).append(group)
    scored = []
    installs = {}
    for (pypi, version), groups in by_library.items():
        pending = [group for group in groups if not (OBS / f"{group['id']}.json").exists()]
        installed = None
        if pending:
            work = Path(tempfile.mkdtemp(prefix=f"dae-{pypi}-"))
            try:
                installed = install_library(work, pypi, version)
                installs[pypi] = {
                    "requested": version,
                    "package_version": installed.get("package_version"),
                    "python_version": installed.get("python_version"),
                    "ok": bool(installed.get("ok")),
                }
                if not installed.get("ok"):
                    failure = {
                        "ok": False,
                        "exc_type": "InstallError",
                        "message": installed.get("message", "")[:2000],
                    }
                else:
                    failure = None
                for group in pending:
                    started = time.perf_counter()
                    if failure:
                        legal_obs = dict(failure)
                        violating_obs = dict(failure)
                    else:
                        legal_obs = run_driver(installed["python"], group["driver"], group["legal"])
                        violating_obs = run_driver(installed["python"], group["driver"], group["violating"])
                    payload = {
                        "id": group["id"],
                        "pypi": pypi,
                        "version": version,
                        "package_version": None if failure else installed.get("package_version"),
                        "python_version": None if failure else installed.get("python_version"),
                        "seconds": round(time.perf_counter() - started, 3),
                        "legal": legal_obs,
                        "violating": violating_obs,
                    }
                    (OBS / f"{group['id']}.json").write_text(
                        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                    )
            finally:
                shutil.rmtree(work, ignore_errors=True)
        for group in groups:
            observed = json.loads((OBS / f"{group['id']}.json").read_text(encoding="utf-8"))
            result = score_group(group, observed["legal"], observed["violating"])
            result["seconds"] = observed.get("seconds")
            result["package_version"] = observed.get("package_version")
            result["legal_observation"] = observed["legal"]
            result["violating_observation"] = observed["violating"]
            scored.append(result)
    counts = tally(scored)
    decision = decide(len(scored), len({group["library"] for group in scored}), counts)
    summary = {
        "freeze_commit": freeze_commit(),
        "scoring_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "protocol_sha256": file_sha(PROTOCOL),
        "included": len(scored),
        "libraries_included": sorted({group["library"] for group in scored}),
        "scored": True,
        "decision": decision["decision"],
        "reason": decision["reason"],
        "ranking": None,
        "counts": counts,
        "installs": installs,
        "not_run": list(NOT_RUN),
        "groups": scored,
        "note": NOTE,
    }
    write_summary(summary)
    printable = {
        "decision": summary["decision"],
        "reason": summary["reason"],
        "included": summary["included"],
        "counts": {
            name: {
                "executable": counts[name]["executable"],
                "full_success": counts[name]["full_success"],
                "labels": counts[name]["labels"],
            }
            for name in METHODS
        },
    }
    print(json.dumps(printable, indent=2))


if __name__ == "__main__":
    main()
