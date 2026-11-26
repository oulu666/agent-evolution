"""After-arm calibration for the six public fixtures.

The before and parent arms stay in the earlier receipt. This module dispatches
only the pack's counterpart arm. It does not score a paired comparison.
"""

from fractions import Fraction
from hashlib import sha256
from itertools import product
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import calibration_call
import followup
import harness
from freeze_guards import disposition, expected_task_loss


LABEL = "calibration"
ADDENDUM = "research/release_drift_20261126/freeze_prep_20261130/PROTOCOL_AFTER_ARM_ZH.md"
PRIOR_RECEIPT = "research/release_drift_20261126/freeze_prep_20261130/results/gaps_followup_receipt.json"
PIN_CHECK = HERE / "pin_check.py"
EXACT_PIN = re.compile(r"(?i)(?<![A-Za-z0-9_.-])unidecode\s*==\s*([0-9]+(?:\.[0-9]+){1,2})")
COUNTERPART = {
    "xlsx-column": "after",
    "xlsx-duration": "after",
    "babel-week": "after",
    "python-slugify-1": "rev",
    "python-slugify-2": "rev",
    "python-slugify-3": "rev",
}
STORED_SIDE = {case_id: "parent" if arm == "rev" else "before" for case_id, arm in COUNTERPART.items()}
DECLARATION_FILES = ("setup.py", "setup.cfg", "pyproject.toml", "requirements.txt")


def is_mass_triple(value):
    if not isinstance(value, dict) or set(value) != {"correct", "deferred", "wrong"}:
        return False
    try:
        masses = [Fraction(value[key]) for key in ("correct", "deferred", "wrong")]
    except (TypeError, ValueError, ZeroDivisionError):
        return False
    return min(masses) >= 0 and sum(masses) == 1


def admissible_prior(value):
    return isinstance(value, dict) and value.get("applies_to") == "every-legal-sequence" and is_mass_triple(value.get("masses"))


def select_static_sequence(case_id, n_inputs, prior):
    """Score sequences only for the one registered prior shape."""
    refused = {"sequence_selected": False, "sequence_scored": False, "loss": None,
               "selected": None, "label": LABEL, "formal_score": False}
    if prior is None:
        return {**refused, "reason": "没有顶层 outcome_prior。没有构造质量，也没有对序列调用 expected_task_loss。"}
    if not admissible_prior(prior):
        return {**refused, "reason": "outcome_prior 不是每条合法序列共用的三元质量。没有选出序列。"}
    masses = prior["masses"]
    loss = expected_task_loss(masses["correct"], masses["deferred"], masses["wrong"])
    identifiers = [followup.request_id(case_id, index) for index in range(n_inputs)]
    best = None
    total = 0
    for length in range(4):
        for sequence in product(identifiers, repeat=length):
            total += 1
            sequence_id = json.dumps(list(sequence), ensure_ascii=False, separators=(",", ":"))
            key = (loss, length, sequence_id)
            if best is None or key < best[0]:
                best = (key, list(sequence))
    return {"sequence_selected": True, "sequence_scored": True, "loss": str(loss),
            "selected": best[1], "n_sequences": total, "label": LABEL, "formal_score": False,
            "reason": "每条合法序列共用已登记质量。平局先取更短的序列，再按序列标识。"}


def scan_unidecode_pins(named_texts):
    mentions = []
    pins = []
    for name, text in named_texts:
        if "unidecode" not in text.lower():
            continue
        mentions.append(name)
        for version in EXACT_PIN.findall(text):
            pins.append({"file": name, "version": version})
    unique = sorted({item["version"] for item in pins})
    return {"mentions": mentions, "pins": pins, "unique_versions": unique,
            "exact_pin": unique[0] if len(unique) == 1 else None,
            "conflict": len(unique) > 1}


def fixture_texts():
    named = []
    for case_id in COUNTERPART:
        relative = followup.pack_relative(case_id)
        named.append((relative, (harness.REPO / relative).read_text(encoding="utf-8")))
    for relative in sorted(harness.ALLOWED):
        named.append((relative, (harness.REPO / relative).read_text(encoding="utf-8")))
    return named


def library_unidecode_declaration(commit):
    """Record a checkout's own specifier. It is not a public-fixture pin."""
    try:
        directory = calibration_call.slugify_tree(commit)
    except Exception as exc:
        return {"lines": [], "exact_pin": None, "fixture_pin": False,
                "error_type": type(exc).__name__, "error": str(exc)}
    lines = []
    for name in DECLARATION_FILES:
        path = directory / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "unidecode" in line.lower():
                lines.append({"file": name, "line": line.strip()})
    found = []
    for item in lines:
        found.extend(EXACT_PIN.findall(item["line"]))
    unique = sorted(set(found))
    return {"lines": lines, "exact_pin": unique[0] if len(unique) == 1 else None,
            "fixture_pin": False, "error": None}


def case_row_assessment(expression_table, both_arms_ran, verdict, row_prior, verified_replacement=False):
    row = {"label": LABEL, "formal_score": False, "case_rows_used": False,
           "both_arms_ran": bool(both_arms_ran), "evidence_sufficient": False,
           "expected_task_loss": None, "verdict": None, "action": None,
           "transferred_verdict_called": False}
    if not expression_table:
        row.update(verdict="undetermined",
                   action=disposition("undetermined", verified_replacement=False),
                   reason="空规则表不能提供已登记裁决。预期任务损失留空。")
        return row
    ready = (both_arms_ran and verdict in {"violated", "satisfied", "undetermined"}
             and is_mass_triple(row_prior))
    if not ready:
        row["reason"] = "表达式、两臂、裁决或三元质量没有同时齐备。预期任务损失留空。"
        return row
    loss = expected_task_loss(row_prior["correct"], row_prior["deferred"], row_prior["wrong"])
    row.update(evidence_sufficient=True, case_rows_used=True, expected_task_loss=str(loss),
               verdict=verdict, action=disposition(verdict, verified_replacement=verified_replacement),
               reason="四项证据齐备。这个数是校准，不是正式分数。")
    return row


def field_confirmation(case_id, archive_type):
    if case_id == "xlsx-column":
        report = followup.address_column()
    elif case_id in {"babel-week", "xlsx-duration"}:
        report = followup.address_unwrapped(archive_type)
    else:
        report = {"name": "field_address", "status": "partial", "signoff_ready": False,
                  "addressable": False, "wrapped": False,
                  "reason": "slugify 只沿用上一份回执已经能读的现成键。本试跑不新包结构。"}
    report = dict(report)
    report["cross_field_invariants"] = []
    report["new_wrapper"] = False
    report["signoff_ready"] = False
    return report


def accept_pin_report(report):
    if not isinstance(report, dict):
        return False
    version_info = report.get("version_info")
    if report.get("implementation") != "CPython":
        return False
    if not isinstance(version_info, list) or version_info[:2] != [3, 11]:
        return False
    if not str(report.get("version") or "").startswith("3.11"):
        return False
    if not str(report.get("executable") or "").strip():
        return False
    if report.get("libraries_called") or report.get("formal_paired_comparison_started") or report.get("sample_drawn"):
        return False
    tasks = report.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return False
    if any(item.get("seed") != 20261126 or item.get("sample_drawn") for item in tasks):
        return False
    return True


def _unset_pin(reason, notes=None, error_type=None):
    return {"cpython_3_11_pin": "unset", "executable": None, "version": None,
            "version_info": None, "implementation": None, "pin_check_ran": False,
            "random_arm_comparison_ran": False, "formal_paired_comparison_started": False,
            "parent_python": sys.version, "reason": reason, "notes": notes or [],
            "error_type": error_type, "uninstall": "uv python uninstall 3.11"}


def _uv_binary():
    found = shutil.which("uv")
    if found:
        return found
    candidate = Path.home() / ".local" / "bin" / "uv"
    if candidate.is_file():
        return str(candidate)
    return None


def _install_uv(notes):
    env = os.environ.copy()
    env["UV_NO_MODIFY_PATH"] = "1"
    command = "curl -LsSf https://astral.sh/uv/install.sh | sh"
    proc = subprocess.run(["sh", "-c", command], env=env, capture_output=True, text=True, timeout=180, check=False)
    notes.append({"command": command, "returncode": proc.returncode, "stderr_tail": proc.stderr[-400:]})
    return _uv_binary()


def _uv_find(uv, notes):
    env = os.environ.copy()
    env["UV_PYTHON_INSTALL_DIR"] = str(Path.home() / ".local" / "share" / "uv" / "python")
    proc = subprocess.run([uv, "python", "find", "3.11"], env=env, capture_output=True, text=True,
                          timeout=60, check=False)
    notes.append({"command": [uv, "python", "find", "3.11"], "returncode": proc.returncode,
                  "stdout": proc.stdout.strip(), "stderr_tail": proc.stderr[-400:]})
    if proc.returncode != 0:
        return None
    path = Path(proc.stdout.strip())
    if not path.is_file():
        return None
    resolved = path.resolve()
    repo = harness.REPO.resolve()
    if resolved == repo or repo in resolved.parents:
        raise RuntimeError("refusing a CPython 3.11 install inside the repository")
    return resolved


def locate_python311():
    try:
        return _locate_python311()
    except Exception as exc:
        return _unset_pin(str(exc), error_type=type(exc).__name__)


def _locate_python311():
    notes = []
    before_path = shutil.which("python3.11")
    uv = _uv_binary()
    if uv is None:
        uv = _install_uv(notes)
    if uv is None:
        return _unset_pin("uv is not available and the documented installer did not provide it", notes)
    executable = _uv_find(uv, notes)
    if executable is None:
        env = os.environ.copy()
        env["UV_PYTHON_INSTALL_DIR"] = str(Path.home() / ".local" / "share" / "uv" / "python")
        proc = subprocess.run([uv, "python", "install", "3.11"], env=env, capture_output=True, text=True,
                              timeout=300, check=False)
        notes.append({"command": [uv, "python", "install", "3.11"], "returncode": proc.returncode,
                      "stderr_tail": proc.stderr[-400:]})
        if proc.returncode != 0:
            return _unset_pin("uv python install 3.11 failed", notes)
        executable = _uv_find(uv, notes)
    if executable is None:
        return _unset_pin("uv python find 3.11 did not return an interpreter", notes)
    after_path = shutil.which("python3.11")
    if before_path is None and after_path is not None and Path(after_path).is_symlink():
        Path(after_path).unlink()
        notes.append({"removed_path_symlink": after_path})
    home_shim = Path.home() / ".local" / "bin" / "python3.11"
    uv_root = (Path.home() / ".local" / "share" / "uv" / "python").resolve()
    if before_path is None and home_shim.is_symlink() and uv_root in home_shim.resolve().parents:
        home_shim.unlink()
        notes.append({"removed_home_shim": str(home_shim)})
    proc = subprocess.run([str(executable), str(PIN_CHECK), json.dumps(list(COUNTERPART))],
                          capture_output=True, text=True, timeout=60, check=False)
    if proc.returncode != 0:
        notes.append({"pin_check_returncode": proc.returncode, "stderr_tail": proc.stderr[-400:]})
        return _unset_pin("the 3.11 pin-check process failed", notes)
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return _unset_pin("the pin-check process did not return JSON", notes)
    if not accept_pin_report(report):
        return _unset_pin("the pin-check report is not a CPython 3.11 report", notes)
    if Path(report["executable"]).resolve() != executable:
        return _unset_pin("the pin-check executable does not match uv python find", notes)
    if shutil.which("python3.11") and before_path is None:
        return _unset_pin("python3.11 remained on PATH after the documented install", notes)
    return {"cpython_3_11_pin": "satisfied", "executable": str(executable),
            "version": report["version"], "version_info": report["version_info"],
            "implementation": report["implementation"], "pin_check_ran": True,
            "random_arm_comparison_ran": False, "formal_paired_comparison_started": False,
            "sample_drawn": False, "tasks": report["tasks"], "parent_python": sys.version,
            "reason": "针脚检查进程自报 CPython 3.11。正式随机对照和四项配对比较没有运行。",
            "notes": notes, "uninstall": "uv python uninstall 3.11"}


def _load_json_file(relative):
    if harness.FORBIDDEN.search(relative):
        raise SystemExit(f"refusing sealed or out-of-study path: {relative}")
    path = (harness.REPO / relative).resolve()
    if not path.is_relative_to(harness.REPO):
        raise SystemExit(f"refusing path outside the repository: {relative}")
    return json.loads(path.read_text(encoding="utf-8"))


def stored_arm_record(receipt, case_id, pack):
    side = STORED_SIDE[case_id]
    rows = [case for case in receipt.get("cases", []) if case.get("id") == case_id]
    expected = pack["arms"][side].get("version") or pack["arms"][side].get("commit")
    if len(rows) != 1:
        return {"ran": False, "side": side, "requested_version": expected,
                "reason": "上一份回执没有唯一的案例行。"}
    case = rows[0]
    budget = case.get("artifacts", {}).get("budget_enforcement") or {}
    purposes = [event.get("purpose") for event in budget.get("extra_events") or []]
    observed = []
    for step in ("shared_first", "probe", "reset"):
        item = budget.get(step) or {}
        if item.get("completed"):
            observed.append(item.get("version"))
    ran = (case.get("label") == LABEL and budget.get("status") == "ran"
           and purposes == ["probe", "verification", "reset"]
           and budget.get("restore_dispatched") is False and bool(budget.get("intercepted"))
           and case.get("arm_ids", {}).get(side) == expected
           and all(value == expected for value in observed))
    return {"ran": ran, "side": side, "requested_version": expected,
            "observed_versions": observed, "receipt": PRIOR_RECEIPT,
            "reason": "上一份回执已经走完这一臂的预算脚本。" if ran else "上一份回执不能证明这一臂已经按脚本执行。"}


def run_counterpart(case_id, pack):
    arm = COUNTERPART[case_id]
    requested = pack["arms"][arm].get("version") or pack["arms"][arm].get("commit")
    try:
        report = followup.budget_script(case_id, arm, len(pack["inputs"]), calibration_call.dispatch)
    except Exception as exc:
        return {"name": "budget_enforcement", "status": "gap", "signoff_ready": False,
                "arm": arm, "requested_version": requested, "observed_versions": [],
                "version_matches_pack": False, "compared_to_expected": False,
                "error_type": type(exc).__name__, "error": str(exc),
                "reason": "另一臂没有走完预算脚本。没有改用另一个案例。"}
    observed = []
    for step in ("shared_first", "probe", "reset"):
        item = report.get(step) or {}
        if item.get("completed"):
            observed.append(item.get("version"))
    report = dict(report)
    report.update(arm=arm, requested_version=requested, observed_versions=observed,
                  version_matches_pack=bool(observed) and all(value == requested for value in observed),
                  compared_to_expected=False, signoff_ready=False)
    return report


def find_outcome_prior():
    for case_id in COUNTERPART:
        pack = followup.load_pack(case_id)["pack"]
        if isinstance(pack, dict) and "outcome_prior" in pack:
            return {"source": followup.pack_relative(case_id), "value": pack["outcome_prior"]}
    for relative in sorted(harness.ALLOWED):
        if not relative.endswith(".json"):
            continue
        data = harness.load_allowed(relative)
        if isinstance(data, dict) and "outcome_prior" in data:
            value = data["outcome_prior"]
            del data
            return {"source": relative, "value": value}
        del data
    return None


def slugify_quality(scan, budget, installed_from_fixture=False):
    """A live slug is not a sign-off receipt unless the fixture named the dependency."""
    resolved = []
    for step in ("shared_first", "probe", "reset"):
        item = budget.get(step) or {}
        dependency = item.get("dependency") or {}
        if item.get("completed") and dependency.get("unidecode"):
            resolved.append(dependency["unidecode"])
    pin = scan["exact_pin"]
    matched = bool(pin) and not scan["conflict"] and bool(resolved) and all(version == pin for version in resolved)
    return {"fixture_pin": pin, "resolved_versions": resolved, "matches_fixture_pin": matched,
            "signoff_quality_receipt": matched, "installed_from_fixture": bool(installed_from_fixture)}


def _unidecode_resolution(scan, installed):
    if scan["conflict"]:
        return "conflict"
    if scan["exact_pin"] is None:
        return "environment-gap"
    if installed:
        return "fixture-pin"
    return "fixture-pin-install-failed"


def install_exact_unidecode(version):
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,2}", version or ""):
        raise RuntimeError("refusing an Unidecode install that is not an exact fixture pin")
    command = [sys.executable, "-m", "pip", "install", "--user", f"Unidecode=={version}"]
    proc = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
    return {"command": command, "returncode": proc.returncode, "installed": proc.returncode == 0}


def _preplanned_value(case_name):
    found = followup.load_preplanned(case_name)
    values = list(found.values())
    if values and all(item == values[0] for item in values):
        return values[0]
    return found or None


def build_case(case_id, pack_record, stored_receipt, scan, prior, archive_types, installed_from_fixture):
    pack = pack_record["pack"]
    table = followup.validate_expression_table(pack["allowed_offline_criteria"], pack["inputs"],
                                               pack["expected"], pack["observation_kind"])
    stored = stored_arm_record(stored_receipt, case_id, pack)
    budget = run_counterpart(case_id, pack)
    both = bool(stored["ran"] and budget.get("status") == "ran")
    row = case_row_assessment(table, both, None, None)
    if pack["library"] == "python-slugify":
        preplanned = None
        declaration = library_unidecode_declaration(pack["arms"]["rev"]["commit"])
        quality = slugify_quality(scan, budget, installed_from_fixture)
        addressed = field_confirmation(case_id, None)
    else:
        case_name = {"xlsx-column": "column", "xlsx-duration": "duration", "babel-week": "week"}[case_id]
        preplanned = _preplanned_value(case_name)
        declaration = None
        quality = None
        addressed = field_confirmation(case_id, archive_types[case_name])
    static = followup.static_artifact(case_id, pack_record, preplanned)
    if static["development_preplanned"]["development_preplanned_used"]:
        raise RuntimeError("development preplanned was used")
    selection = select_static_sequence(case_id, len(pack["inputs"]), prior["value"] if prior else None)
    if selection["sequence_selected"] and not (prior and admissible_prior(prior["value"])):
        raise RuntimeError("a sequence was selected without an admissible prior")
    return {"id": case_id, "library": pack["library"], "label": LABEL,
            "pack_sha256": pack_record["sha256"], "expression_table": table,
            "expression_table_label": "空规则表" if not table else "registered",
            "stored_arm": stored, "budget_enforcement": budget,
            "both_arms_ran": both, "case_row": row, "static_sequence": static,
            "registered_prior_selection": selection, "field_address": addressed,
            "library_unidecode_declaration": declaration, "slugify_quality": quality,
            "signoff_ready": False, "compared_to_expected": False}


def assess_gaps(cases, pin, scan):
    release_ids = [case_id for case_id, arm in COUNTERPART.items() if arm == "after"]
    slug_ids = [case_id for case_id, arm in COUNTERPART.items() if arm == "rev"]
    by_id = {case["id"]: case for case in cases}

    def version_ok(case):
        budget = case["budget_enforcement"]
        return budget.get("status") == "ran" and budget.get("version_matches_pack") is True and budget.get("intercepted")

    def script_ok(case):
        budget = case["budget_enforcement"]
        purposes = [event.get("purpose") for event in budget.get("extra_events") or []]
        return (budget.get("status") == "ran" and purposes == ["probe", "verification", "reset"]
                and budget.get("restore_dispatched") is False and budget.get("intercepted"))

    if all(version_ok(by_id[case_id]) for case_id in COUNTERPART):
        arm_status = "closed"
        arm_detail = "六个另一臂的成功调用都进入了资料包命名的版本。失败校验占用一次，第四次没有进入适配器。"
    elif all(version_ok(by_id[case_id]) for case_id in release_ids) and all(script_ok(by_id[case_id]) for case_id in slug_ids):
        arm_status = "partial"
        arm_detail = "XlsxWriter 与 Babel 的 after 臂进入了资料包命名的版本。slugify 的 rev 已按脚本分派，但没有可签收的库版本。"
    else:
        arm_status = "open"
        arm_detail = "另一臂没有全部按资料包版本走完预算脚本。"
    prior_ok = all(case["static_sequence"]["check_search_parity"] == "passed"
                   and case["static_sequence"]["sequence_selected"] is False
                   and case["static_sequence"]["development_preplanned"]["development_preplanned_used"] is False
                   and case["registered_prior_selection"]["sequence_selected"] is False
                   for case in cases)
    rows_present = all(case["case_row"]["action"] == "deliver_current"
                       and case["case_row"]["expected_task_loss"] is None
                       and case["case_row"]["evidence_sufficient"] is False
                       for case in cases)
    pin_closed = (pin["cpython_3_11_pin"] == "satisfied" and pin["pin_check_ran"]
                  and str(pin.get("version") or "").startswith("3.11")
                  and pin["random_arm_comparison_ran"] is False)
    fields_partial = all(case["field_address"]["wrapped"] is False and case["field_address"]["new_wrapper"] is False
                         and case["field_address"]["cross_field_invariants"] == []
                         for case in cases)
    week_open = by_id["babel-week"]["field_address"].get("addressable") is False
    duration_open = by_id["xlsx-duration"]["field_address"].get("addressable") is False
    unidecode_closed = bool(scan["exact_pin"]) and not scan["conflict"] and all(
        (case["slugify_quality"] or {}).get("matches_fixture_pin") for case in cases if case["library"] == "python-slugify")
    return [
        {"id": "after_rev_arms", "status": arm_status, "detail": arm_detail},
        {"id": "unidecode_pin", "status": "closed" if unidecode_closed else "open",
         "detail": (f"公开夹具的精确钉扎是 {scan['exact_pin']}。" if unidecode_closed
                    else "公开夹具没有 Unidecode 的精确钉扎。未安装未钉扎版本。slugify 现场返回不是签收质量回执。")},
        {"id": "outcome_prior", "status": "partial" if prior_ok else "open",
         "detail": "深度 3 的枚举和核对仍然通过。开发 preplanned 未使用。没有已登记的 outcome_prior，所以没有选出序列。"
         if prior_ok else "静态序列登记没有保持未选。"},
        {"id": "case_row_loss", "status": "partial" if rows_present else "open",
         "detail": "案例行进入了未定处置。预期任务损失留空，因为空规则表和缺失的三元质量不够。"
         if rows_present else "案例行没有按证据规则留下损失。"},
        {"id": "cpython_3_11_pin", "status": "closed" if pin_closed else "open",
         "detail": (f"针脚检查使用 {pin.get('executable')}，版本 {pin.get('version')!r}。正式随机对照没有运行。"
                    if pin_closed else f"针脚为 {pin['cpython_3_11_pin']}。没有把 3.12 写成 3.11。")},
        {"id": "field_addressability", "status": "partial" if fields_partial and week_open and duration_open else "open",
         "detail": "没有新增包裹，也没有新增跨字段不变量。周历年字符串和时长档案标量仍不可寻址。"},
    ]


def build_receipt():
    if not followup.checklist_still_unticked():
        raise RuntimeError("formal freeze checklist is ticked")
    pin = locate_python311()
    if pin["cpython_3_11_pin"] == "satisfied" and not str(pin.get("version") or "").startswith("3.11"):
        raise RuntimeError("pin satisfaction does not name CPython 3.11")
    if sys.version.startswith("3.12") and pin["cpython_3_11_pin"] == "satisfied":
        if not pin.get("executable") or Path(pin["executable"]).resolve() == Path(sys.executable).resolve():
            raise RuntimeError("the 3.12 parent was recorded as the 3.11 pin")
    rebuilt = followup.materialize_packs()
    loaded = {case_id: followup.load_pack(case_id) for case_id in rebuilt}
    followup.packs_match_fixtures(loaded, rebuilt)
    calibration_call.bind_packs({case_id: item["pack"] for case_id, item in loaded.items()})
    scan = scan_unidecode_pins(fixture_texts())
    install_report = None
    installed_from_fixture = False
    if scan["exact_pin"] and not scan["conflict"]:
        install_report = install_exact_unidecode(scan["exact_pin"])
        installed_from_fixture = bool(install_report["installed"])
    prior = find_outcome_prior()
    if prior is not None and not admissible_prior(prior["value"]):
        prior = {"source": prior["source"], "value": prior["value"], "admissible": False}
    elif prior is not None:
        prior = {"source": prior["source"], "value": prior["value"], "admissible": True}
    else:
        prior = {"source": None, "value": None, "admissible": False}
    stored = _load_json_file(PRIOR_RECEIPT)
    if stored.get("label") != LABEL:
        raise RuntimeError("stored before/parent receipt is not calibration")
    archive = harness.load_archive()
    archive_types = {name: archive[name]["actual_type"] for name in ("column", "duration", "week")}
    cases = [build_case(case_id, loaded[case_id], stored, scan, prior, archive_types, installed_from_fixture)
             for case_id in COUNTERPART]
    gaps = assess_gaps(cases, pin, scan)
    expectations = {case["id"]: case["expression_table"] for case in cases}
    registry = [{"case_id": case["id"], "pack_sha256": case["pack_sha256"],
                 "counterpart": case["budget_enforcement"].get("arm"),
                 "requested_version": case["budget_enforcement"].get("requested_version")}
                for case in cases]
    parameters = {"budget_limit": 3, "depth": 3, "scoring_limit": None,
                  "loss_weights": {"correct": 0, "deferred": 1, "wrong": 5},
                  "tie_break": followup.SEARCH_IDS["tie_break"], "pruning": followup.SEARCH_IDS["pruning"],
                  "online_purposes": sorted(harness.ONLINE_PURPOSES),
                  "cpython_3_11_pin": pin["cpython_3_11_pin"], "random_arm_comparison_ran": False,
                  "formal_paired_comparison_started": False, "unidecode_fixture_pin": scan["exact_pin"]}
    frozen = followup.hash_freeze(parameters, registry, expectations)
    status = followup.git_text(["status", "--porcelain"])
    return {"label": LABEL, "banner": harness.BANNER, "preparation_not_formal_result": True,
            "cannot_replace_formal_denominators": True,
            "cannot_change_preregistered_method_after_sealed_outcomes": True,
            "sealed_outcomes_used": False, "method_frozen": False, "methods_ranked": False,
            "checklist_boxes_ticked": False, "formal_paired_comparison_started": False,
            "compared_arms_scored": False, "new_algorithm": False, "budget_limit": 3,
            "addendum": ADDENDUM,
            "addendum_commit": followup.git_text(["log", "-1", "--format=%H", "--", ADDENDUM]),
            "head": followup.git_text(["rev-parse", "HEAD"]),
            "addendum_sha256": sha256((harness.REPO / ADDENDUM).read_bytes()).hexdigest(),
            "git_status": status.splitlines(), "parent_python": sys.version, "pin": pin,
            "unidecode": {**scan, "installed": installed_from_fixture, "install_report": install_report,
                          "resolution": _unidecode_resolution(scan, installed_from_fixture)},
            "outcome_prior": {"source": prior["source"], "admissible": prior["admissible"],
                              "development_preplanned_used": False,
                              "expected_outputs_are_masses": False,
                              "development_row_outcomes_used": False},
            "arithmetic_check": harness.arithmetic_check(),
            "stored_receipt": PRIOR_RECEIPT, "cases": cases, "gaps": gaps,
            "hash_freeze_helper": frozen, "entry": "research/release_drift_20261126/freeze_prep_20261130/run_after_arm.py"}


def render_log(receipt):
    pin = receipt["pin"]
    lines = ["label: calibration", receipt["banner"], f"addendum_commit: {receipt['addendum_commit']}",
             f"head: {receipt['head']}", f"parent_python: {receipt['parent_python']}",
             f"cpython_3_11_pin: {pin['cpython_3_11_pin']}",
             f"pin_executable: {pin.get('executable')}", f"pin_version: {pin.get('version')}",
             "random_arm_comparison_ran: false", "formal_paired_comparison_started: false",
             "method_frozen: false", "checklist_boxes_ticked: false",
             f"unidecode_fixture_pin: {receipt['unidecode']['exact_pin']}",
             f"outcome_prior_admissible: {receipt['outcome_prior']['admissible']}",
             "arithmetic_note: 0、1、5 仍是协议小夹具，不是案例分数。"]
    for case in receipt["cases"]:
        budget = case["budget_enforcement"]
        lines.append(f"case: {case['id']} arm: {budget.get('arm')} requested: {budget.get('requested_version')} "
                     f"match: {budget.get('version_matches_pack')} both_arms_ran: {case['both_arms_ran']}")
        lines.append(f"  loss: {case['case_row']['expected_task_loss']} evidence: {case['case_row']['evidence_sufficient']}")
        lines.append(f"  sequence_selected: {case['registered_prior_selection']['sequence_selected']}")
        if case.get("slugify_quality") is not None:
            lines.append(f"  signoff_quality_receipt: {case['slugify_quality']['signoff_quality_receipt']}")
    lines.append("gaps:")
    for gap in receipt["gaps"]:
        lines.append(f"- {gap['id']}: {gap['status']}: {gap['detail']}")
    return "\n".join(lines) + "\n"
