"""Thin adapters from ExtraCalls to the three public calibration libraries.

XlsxWriter and Babel run from the wheel named in the shared pack. slugify runs
only from the recorded parent commit. Another release is not substituted.
"""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.request import urlopen
from zipfile import ZipFile


class CalibrationCallError(Exception):
    pass


WORKER = Path(__file__).resolve().parent / "calibration_worker.py"
CACHE = Path(tempfile.gettempdir()) / "calibration-freeze-prep"
SLUGIFY_REMOTE = "https://github.com/un33k/python-slugify.git"
PACKS = {}


def bind_packs(packs):
    PACKS.clear()
    PACKS.update(packs)


def dispatch(request):
    """One online call. Unregistered operations fail inside the adapter."""
    if request.get("op") != "calibration-input":
        raise CalibrationCallError("unregistered calibration operation")
    case_id = request.get("case_id")
    pack = PACKS.get(case_id)
    if pack is None:
        raise CalibrationCallError("no shared pack is bound for this case")
    if request.get("arm") != pack["live_arm"]:
        raise CalibrationCallError("live calls are limited to the pack's before or parent arm")
    index = request.get("index")
    inputs = pack["inputs"]
    if type(index) is not int or index < 0 or index >= len(inputs):
        raise CalibrationCallError("calibration input index is outside the shared pack")
    if pack["library"] == "python-slugify":
        return _slugify(pack, inputs[index])
    return _wheel(pack, inputs[index])


def _wheel(pack, value):
    arm = pack["arms"][pack["live_arm"]]
    directory = _wheel_dir(arm["url"], arm["sha256"])
    return _run(directory, pack["library"], arm["version"], {
        "operation": pack["operation"],
        "input": value,
    })


def _slugify(pack, value):
    commit = pack["arms"]["parent"]["commit"]
    directory = _slugify_checkout(commit)
    return _run(directory, "python-slugify", commit, {"input": value, "commit": commit})


def _run(directory, library, version, payload):
    proc = subprocess.run(
        [sys.executable, "-I", str(WORKER), str(directory), library, version,
         json.dumps(payload, ensure_ascii=False)],
        capture_output=True, text=True, timeout=90, check=False)
    text = proc.stdout.strip()
    try:
        body = json.loads(text) if text else {}
    except json.JSONDecodeError:
        body = {"error_type": "CalibrationCallError", "error": text or proc.stderr.strip()}
    if proc.returncode != 0:
        message = body.get("error") or proc.stderr.strip() or "calibration library call failed"
        raise CalibrationCallError(f"{body.get('error_type', 'CalibrationCallError')}: {message}")
    body["compared_to_expected"] = False
    return body


def _wheel_dir(url, digest):
    root = CACHE / "wheels" / digest
    marker = root / ".ok"
    if marker.is_file():
        return root
    root.parent.mkdir(parents=True, exist_ok=True)
    blob = root.parent / f"{digest}.whl"
    if not blob.is_file():
        with urlopen(url, timeout=60) as response:
            data = response.read()
        if sha256(data).hexdigest() != digest:
            raise CalibrationCallError("downloaded wheel does not match the pack sha256")
        blob.write_bytes(data)
    else:
        if sha256(blob.read_bytes()).hexdigest() != digest:
            raise CalibrationCallError("cached wheel does not match the pack sha256")
    if root.exists():
        return _mark(root, marker)
    staging = Path(tempfile.mkdtemp(prefix="wheel-", dir=root.parent))
    with ZipFile(blob) as archive:
        archive.extractall(staging)
    staging.rename(root)
    return _mark(root, marker)


def _mark(root, marker):
    marker.write_text("ok\n", encoding="utf-8")
    return root


def _slugify_checkout(commit):
    repo = CACHE / "python-slugify.git"
    if not repo.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", SLUGIFY_REMOTE, str(repo)], check=True, timeout=180)
    probe = subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{commit}^{{commit}}"],
                           check=False, timeout=30)
    if probe.returncode != 0:
        raise CalibrationCallError(f"parent commit {commit} is not in {SLUGIFY_REMOTE}")
    dest = CACHE / "checkouts" / commit
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach", str(dest), commit],
                       check=True, timeout=60)
    return dest
