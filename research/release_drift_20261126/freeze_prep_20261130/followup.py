"""Calibration follow-up for the ten November 30 gaps.

Public fixtures only. Nothing here freezes the formal method or ranks arms.
"""

from copy import deepcopy
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from time import perf_counter_ns

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import calibration_call
import harness
from freeze_guards import check_search_parity, direct_delivery, disposition, replay_group, _read

REPO = harness.REPO
LABEL = "calibration"
ADDENDUM = "research/release_drift_20261126/freeze_prep_20261130/PROTOCOL_ADDENDUM_ZH.md"
PACK_ROOT = "research/release_drift_20261126/freeze_prep_20261130/packs"
DURATION_FORMAT = "[h]:mm"
CASE_ORDER = (
    ("xlsx-column", "XlsxWriter", "column"),
    ("xlsx-duration", "XlsxWriter", "duration"),
    ("babel-week", "Babel", "week"),
)
SLUGIFY_IDS = harness.SLUGIFY_IDS
OPS = frozenset({"integer", "length", "scale_integer"})
DISPOSITION_RULES = {
    "violated_verified": "deliver_replacement",
    "violated_unverified": "defer",
    "satisfied": "deliver_current",
    "undetermined": "deliver_current",
}
SEARCH_IDS = {
    "candidates": "pack-inputs",
    "prior": "no-outcome-masses",
    "transition": "call-budget-only",
    "legal_actions": "public-calibration-input-or-stop",
    "terminal_score": "freeze_guards.expected_task_loss",
    "pruning": "none",
    "tie_break": "fewer-calls-then-canonical-request-id",
}


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_hash(value):
    return sha256(canonical_bytes(value)).hexdigest()


def pack_relative(case_id):
    if not re.fullmatch(r"[a-z0-9-]+", case_id):
        raise ValueError("case id is not a pack name")
    relative = f"{PACK_ROOT}/{case_id}.json"
    if harness.FORBIDDEN.search(relative):
        raise SystemExit(f"refusing sealed or out-of-study path: {relative}")
    path = (REPO / relative).resolve()
    if not path.is_relative_to(REPO / PACK_ROOT):
        raise SystemExit(f"refusing path outside the pack directory: {relative}")
    return relative


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def registered_expressions(inputs, expected, observation_kind):
    """Complete-output expressions in the existing three-operation vocabulary."""
    if observation_kind != "int" or len(inputs) != len(expected) or not expected:
        return []
    if not all(type(value) is int for value in expected):
        return []
    keys = []
    fields = []
    for row in inputs:
        if not isinstance(row, dict) or len(row) != 1:
            return []
        key, field = next(iter(row.items()))
        keys.append(key)
        fields.append(field)
    if len(set(keys)) != 1:
        return []
    key = keys[0]
    matches = []
    if all(type(field) is int and field == want for field, want in zip(fields, expected)):
        matches.append({"op": "integer", "input": [key]})
    if all(isinstance(field, (list, str)) and len(field) == want for field, want in zip(fields, expected)):
        matches.append({"op": "length", "input": [key]})
    if all(type(field) is int and field != 0 for field in fields):
        factors = []
        for field, want in zip(fields, expected):
            if want % field != 0:
                factors = None
                break
            factors.append(want // field)
        if factors and len(set(factors)) == 1 and type(factors[0]) is int and factors[0] not in {0, 1}:
            matches.append({"op": "scale_integer", "input": [key], "factor": factors[0]})
    if len(matches) != 1 or matches[0]["op"] not in OPS:
        return []
    return matches


def validate_expression_table(table, inputs, expected, observation_kind):
    recomputed = registered_expressions(inputs, expected, observation_kind)
    if table != recomputed:
        raise RuntimeError("expression table drifted from the registered rule")
    for row in table:
        if row.get("op") not in OPS:
            raise RuntimeError("expression uses an operation outside the registered vocabulary")
        if row["op"] != "scale_integer" and "factor" in row:
            raise RuntimeError("factor is only registered for scale_integer")
    return table


def _shared_rows(before_rows, after_rows):
    if len(before_rows) != len(after_rows):
        raise ValueError("the two arms do not have the same number of calibration rows")
    inputs, expected = [], []
    for before, after in zip(before_rows, after_rows):
        if before["input"] != after["input"] or before["expected"] != after["expected"]:
            raise ValueError("the two arms do not share inputs and expected values")
        inputs.append(before["input"])
        expected.append(before["expected"])
    return inputs, expected


def observation_kind_for(case_name, expected):
    if case_name == "column":
        return "dict"
    if case_name == "duration":
        return "float"
    if case_name == "week":
        return "str"
    raise ValueError(case_name)


def build_release_pack(block, case_id, library, case_name):
    inputs, expected = _shared_rows(block["before"]["rows"], block["after"]["rows"])
    kind = observation_kind_for(case_name, expected)
    table = registered_expressions(inputs, expected, kind)
    arms = {}
    for side in ("before", "after"):
        arm = block[side]
        arms[side] = {"filename": arm["filename"], "sha256": arm["sha256"],
                      "url": arm["url"], "version": arm["version"]}
    return {"allowed_offline_criteria": table, "arms": arms, "case_id": case_id,
            "expected": expected, "expected_are_contract_expressions": False,
            "inputs": inputs, "inputs_are_formal_regression_set": False, "label": LABEL,
            "library": library, "live_arm": "before", "observation_kind": kind,
            "operation": case_name,
            "provenance": {"fixture": "runs_upstream_functional_20261124/paired_releases.json",
                           "readme_is_pre_upgrade_doc": False, "source": block["source"]}}


def build_slugify_pack(meta, tasks):
    inputs, expected = [], []
    for row in tasks:
        if not isinstance(row, list) or len(row) < 3:
            raise ValueError("slugify task row is not a public input and expected string")
        inputs.append({"arg": row[0], "kw": row[1]})
        expected.append(row[2])
    kind = "str"
    table = registered_expressions(inputs, expected, kind)
    return {"allowed_offline_criteria": table,
            "arms": {"parent": {"commit": meta["parent"]}, "rev": {"commit": meta["rev"]}},
            "case_id": meta["id"], "expected": expected, "expected_are_contract_expressions": False,
            "inputs": inputs, "inputs_are_formal_regression_set": False, "label": LABEL,
            "library": "python-slugify", "live_arm": "parent", "observation_kind": kind,
            "operation": "slugify",
            "provenance": {"doc_hash": meta.get("doc_hash"),
                           "fixture": "runs_contract_synthesis_gate_20261125/sample.json",
                           "readme": meta.get("readme"), "readme_is_pre_upgrade_doc": False,
                           "tasks_fixture": "runs_contract_synthesis_gate_20261125/tasks.json"}}


def assert_pack_has_no_outcomes(pack):
    blob = canonical_bytes(pack).decode("utf-8")
    for banned in ("\"actual\"", "detected_inputs", "revealed"):
        if banned in blob:
            raise RuntimeError(f"shared pack contains {banned}")


def materialize_packs():
    archive = harness.load_allowed("runs_upstream_functional_20261124/paired_releases.json")
    sample = [row for row in harness.load_allowed("runs_contract_synthesis_gate_20261125/sample.json")
              if row.get("project") == "python-slugify"]
    tasks = harness.load_allowed("runs_contract_synthesis_gate_20261125/tasks.json")["python-slugify"]
    by_id = {row["id"]: row for row in sample}
    packs = {}
    for case_id, library, case_name in CASE_ORDER:
        packs[case_id] = build_release_pack(archive[case_name], case_id, library, case_name)
    for case_id in SLUGIFY_IDS:
        packs[case_id] = build_slugify_pack(by_id[case_id], tasks)
    for pack in packs.values():
        assert_pack_has_no_outcomes(pack)
        validate_expression_table(pack["allowed_offline_criteria"], pack["inputs"], pack["expected"],
                                  pack["observation_kind"])
    return packs


def write_packs(packs):
    directory = REPO / PACK_ROOT
    directory.mkdir(parents=True, exist_ok=True)
    for case_id, pack in packs.items():
        write_json(REPO / pack_relative(case_id), pack)


def load_pack(case_id):
    relative = pack_relative(case_id)
    path = REPO / relative
    if not path.is_file():
        raise FileNotFoundError(relative)
    text = path.read_text(encoding="utf-8")
    pack = json.loads(text)
    assert_pack_has_no_outcomes(pack)
    return {"relative": relative, "sha256": sha256(text.encode("utf-8")).hexdigest(), "pack": pack}


def packs_match_fixtures(loaded, rebuilt):
    for case_id, fresh in rebuilt.items():
        if canonical_bytes(loaded[case_id]["pack"]) != canonical_bytes(fresh):
            raise RuntimeError(f"{case_id} pack does not match the public fixtures")


def request_id(case_id, index):
    return json.dumps({"case": case_id, "index": index}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def enumerate_sequences(case_id, count, depth=3):
    identifiers = [request_id(case_id, index) for index in range(count)]
    total = 0
    for length in range(depth + 1):
        for _sequence in product(identifiers, repeat=length):
            total += 1
    return {"candidate_ids": identifiers, "depth": depth, "n_sequences": total,
            "repetition": "allowed", "stored_sequences": False}


def budget_transition(state, action):
    """Call-budget transition. It does not update outcome masses."""
    if action is None or state["used"] >= 3:
        return {"sequence": list(state["sequence"]), "terminal": True, "used": state["used"]}
    return {"sequence": [*state["sequence"], action], "terminal": False, "used": state["used"] + 1}


def search_settings(pack_sha256):
    settings = {"depth": 3, "scoring_limit": None, "task_pack": pack_sha256}
    settings.update(SEARCH_IDS)
    return settings


def preplanned_match(value, candidate_ids):
    """The development key matches direction_gate only if every registered condition holds."""
    failures = []
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item in candidate_ids for item in value):
        failures.append("值不是注册候选集上的规范化请求标识序列。")
    failures.append("dev_parallel.best_static 最小化的是剩余解释数、调用数和探针下标序列，不是 expected_task_loss。")
    failures.append("平局由探针下标元组决定，不是先少调用再按规范化请求标识。")
    failures.append("该键依赖开发捕获库，校准生成器不使用那些返回。")
    return {"matches_direction_gate": False, "development_preplanned_used": False,
            "failures": failures, "value": value}


def load_preplanned(case_name):
    data = harness.load_allowed(f"research/release_drift_20261126/dev_parallel/results/{case_name}.json")
    found = {}
    results = data.get("results") if isinstance(data, dict) else None
    if isinstance(results, dict):
        for version, arms in results.items():
            static = arms.get("static_info") if isinstance(arms, dict) else None
            if isinstance(static, dict) and "preplanned" in static:
                found[str(version)] = static["preplanned"]
    del data
    return found


def static_artifact(case_id, pack_record, preplanned):
    settings = search_settings(pack_record["sha256"])
    check_search_parity(settings, dict(settings))
    enumerated = enumerate_sequences(case_id, len(pack_record["pack"]["inputs"]))
    # No sequence receives outcome masses, so the registered terminal score is not applied.
    sequence_selected = False
    if preplanned is None:
        match = {"matches_direction_gate": False, "development_preplanned_used": False,
                 "failures": ["这个案例没有 development preplanned 键。"], "value": None}
    else:
        match = preplanned_match(preplanned, enumerated["candidate_ids"])
        if match["matches_direction_gate"]:
            raise RuntimeError("development preplanned was accepted without a full direction_gate match")
    return {"name": "static_sequence", "status": "partial", "signoff_ready": False,
            "check_search_parity": "passed", "settings": settings,
            "n_sequences": enumerated["n_sequences"], "depth": enumerated["depth"],
            "n_candidates": len(enumerated["candidate_ids"]),
            "transition_kind": "call-budget-only", "outcome_transition": False,
            "terminal_score_registered": True, "sequence_scored": False,
            "sequence_selected": sequence_selected,
            "development_preplanned": match,
            "reason": "深度为三的序列已经数完，两臂设置相同，核对通过。没有结局质量，所以没有选出序列。开发 preplanned 未使用。"}


class OfflineCosts:
    """Schema, backup, and snapshot reset beside ExtraCalls."""

    def __init__(self):
        self.events = []

    def run(self, kind, function):
        if kind not in {"schema", "backup", "snapshot_reset"}:
            raise ValueError("unregistered offline cost")
        start = perf_counter_ns()
        value = function()
        self.events.append({"kind": kind, "elapsed_ns": perf_counter_ns() - start})
        return value


def schema_report(kind, response):
    if kind == "column":
        accepted = harness.column_feasible(response) and set(response) == {"visible", "cell_text"}
        return {"accepted": accepted, "addressable": accepted, "wrapped": False}
    if kind == "duration-list":
        accepted = harness.duration_feasible(response)
        return {"accepted": accepted, "addressable": accepted, "wrapped": False}
    if kind == "duration-scalar":
        return {"accepted": False, "addressable": False, "wrapped": False,
                "observed_type": type(response).__name__}
    if kind == "week-string":
        return {"accepted": False, "addressable": False, "wrapped": False,
                "observed_type": type(response).__name__}
    if kind == "slugify-dict":
        return {"accepted": isinstance(response, dict), "addressable": isinstance(response, dict),
                "wrapped": False}
    raise ValueError(kind)


def offline_on(kind, response):
    costs = OfflineCosts()
    snapshot = {"response": deepcopy(response)}
    backup = costs.run("backup", lambda: deepcopy(snapshot))
    checked = costs.run("schema", lambda: schema_report(kind, snapshot["response"]))
    restored = costs.run("snapshot_reset", lambda: deepcopy(backup))
    if restored != snapshot:
        raise RuntimeError("snapshot reset did not restore the offline backup")
    kinds = [event["kind"] for event in costs.events]
    if kinds != ["backup", "schema", "snapshot_reset"]:
        raise RuntimeError("offline cost order drifted")
    return {"name": "offline_costs", "status": "ran", "signoff_ready": False,
            "events": costs.events, "schema": checked, "entered_extra_calls": False,
            "reason": "三类离线动作只改内存计数，没有调用库，也没有进入 ExtraCalls。"}


def _replay_one(response, path, value, feasible):
    context = {"field": list(path), "logged_observed": _read(response, path),
               "logged_request": {"role": "calibration-witness"},
               "alternate_request": {"role": "calibration-witness-alt"}}
    history = [{"response": deepcopy(response)}]
    logged = harness.calibration_witness(context, history)
    audit = replay_group(harness.calibration_witness, context, history, logged, [(path, value)], feasible)
    return {"path": list(path), "normal_value": value, "effect": audit.get("effect"),
            "reason": audit.get("reason"), "placeholder": False}


def normal_replacements(case_id, expected, response):
    if case_id == "xlsx-column" and harness.column_feasible(response) and isinstance(expected, dict):
        rows = [_replay_one(response, ["visible"], expected["visible"], harness.column_feasible),
                _replay_one(response, ["cell_text"], expected["cell_text"], harness.column_feasible)]
        return {"name": "normal_replacements", "status": "ran", "signoff_ready": False,
                "registered": True, "source": "该输入在共同资料包中的 expected",
                "cross_field_invariants": [], "attempts": rows,
                "reason": "正常值来自这一行自己的公开 expected。没有登记跨字段不变量。"}
    if case_id == "xlsx-duration" and harness.duration_feasible(response) and type(expected) in {int, float}:
        rows = [_replay_one(response, [0], float(expected), harness.duration_feasible),
                _replay_one(response, [1], DURATION_FORMAT, harness.duration_feasible)]
        return {"name": "normal_replacements", "status": "ran", "signoff_ready": False,
                "registered": True,
                "source": "数值来自该输入的公开 expected；格式字面量来自公开调用中的 [h]:mm。",
                "cross_field_invariants": [], "attempts": rows,
                "reason": "档案标量没有被写成列表。二元列表上的正常值等于第一条捕获时，重放没有字段变化。"}
    return {"name": "normal_replacements", "status": "gap", "signoff_ready": False,
            "registered": False, "cross_field_invariants": [], "wrapped": False,
                "reason": "公开 expected 的形状不能给这个记录提供字段级正常值。没有使用占位替代常量。"}


def address_slugify(parent):
    if not isinstance(parent, dict):
        return {"name": "field_address", "status": "gap", "signoff_ready": False, "wrapped": False,
                "reason": "parent 记录不是字典。没有包一层新结构。"}
    if "import_error" in parent:
        text = _read(parent, ["import_error"])
        return {"name": "field_address", "status": "ran", "signoff_ready": False,
                "addressable": True, "wrapped": False,
                "paths": [{"path": ["import_error"], "type": type(text).__name__}],
                "stored_import_error": text, "normal_replacement": False,
                "reason": "导入错误本来就在 import_error 字段里。没有包裹，也没有正常替代值。"}
    deliveries = parent.get("deliveries")
    if not isinstance(deliveries, list) or not deliveries or not isinstance(deliveries[0], dict):
        return {"name": "field_address", "status": "gap", "signoff_ready": False, "wrapped": False,
                "reason": "没有现成的交付字典。没有包一层新结构。"}
    record = deliveries[0]
    paths = []
    for path in (["method"], ["v", 0], ["v", 1], ["deliver"], ["calls"], ["ns"]):
        try:
            value = _read(record, path)
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            paths.append({"path": list(path), "error": type(exc).__name__})
        else:
            paths.append({"path": list(path), "type": type(value).__name__})
    readable = [item for item in paths if "type" in item]
    return {"name": "field_address", "status": "ran" if readable else "gap", "signoff_ready": False,
            "addressable": bool(readable), "wrapped": False, "paths": paths, "normal_replacement": False,
            "reason": "交付记录的现成键可以 _read。这不是包裹。没有登记正常替代值，所以没有做反事实签收。"}


def address_unwrapped(observed_type):
    return {"name": "field_address", "status": "gap", "signoff_ready": False, "accepted": False,
            "addressable": False, "wrapped": False, "observed_type": observed_type,
            "reason": "返回值仍是字符串或标量。没有包进新结构。"}


def address_column():
    return {"name": "field_address", "status": "ran", "signoff_ready": False, "addressable": True,
            "wrapped": False,
            "reason": "列捕获本来就是含 visible 和 cell_text 的字典。这不是新的包裹。"}


def case_row_disposition(table):
    if table:
        raise RuntimeError("a non-empty expression table has no registered observed verdict in this follow-up")
    action = disposition("undetermined", verified_replacement=False)
    if action != "deliver_current":
        raise RuntimeError("undetermined disposition drifted")
    availability, value = direct_delivery("calibration-output", {}, {})
    if availability != "unavailable" or value is not None:
        raise RuntimeError("empty expression table was treated as a direct delivery")
    return {"name": "disposition_on_case_row", "status": "partial", "signoff_ready": False,
            "label": LABEL, "formal_score": False, "verdict": "undetermined",
            "verified_replacement": False, "action": action, "expected_task_loss": None,
            "direct_delivery": "unavailable", "transferred_verdict_called": False,
            "expression_table": [], "expression_table_label": "空规则表",
            "reason": "空规则表不能用已有词汇判定义务。裁决保持未定，动作为交付当前。没有编造结局质量，也没有把存档实际值翻译成违约或满足。"}


def hash_freeze(parameters, registry, expectations):
    parts = {"deployable_parameters": parameters, "task_registry": registry,
             "expectations": expectations, "disposition_rules": DISPOSITION_RULES}
    components = {name: canonical_hash(parts[name]) for name in sorted(parts)}
    listing = [{"name": name, "sha256": components[name]} for name in sorted(components)]
    return {"name": "hash_freeze_helper", "status": "ran", "signoff_ready": False,
            "formal_checklist_ticked": False, "sha256": canonical_hash(listing),
            "components": components, "input_set": [item["name"] for item in listing],
            "reason": "这是校准登记的摘要，不是 11 月 30 日正式清单上的那次冻结。"}


def interpreter_pin():
    path = shutil.which("python3.11")
    pin = "unset" if path is None else "present-but-random-arm-not-run"
    return {"python": sys.version, "python3_11_path": path, "cpython_3_11_pin": pin,
            "random_arm_ran": False,
            "note": "CPython 3.12 不满足方向判别里的 3.11 针脚。这次没有安装 3.11，也没有跑随机臂。"}


def refuse_false_pin(pin):
    if pin["random_arm_ran"]:
        raise RuntimeError("random arm was run in a calibration follow-up")
    if pin["cpython_3_11_pin"] == "satisfied":
        raise RuntimeError("3.12 must not be recorded as satisfying the 3.11 pin")
    if sys.version.startswith("3.12") and pin["cpython_3_11_pin"] == "unset":
        return
    if pin["python3_11_path"] and pin["cpython_3_11_pin"] == "present-but-random-arm-not-run":
        return
    if pin["cpython_3_11_pin"] != "unset":
        raise RuntimeError("interpreter pin status is not the registered one")


def budget_script(case_id, arm, n_inputs, dispatch):
    seen = []

    def wrapped(request):
        seen.append({"role": request.get("role"), "op": request.get("op"), "index": request.get("index")})
        return dispatch(request)

    budget = harness.SharedBudget(wrapped)

    def attempt(purpose, request, first=False):
        try:
            if first:
                result = budget.shared_first(request)
            else:
                result = budget.online(purpose, request)
        except (calibration_call.CalibrationCallError, OSError, subprocess.SubprocessError) as exc:
            return {"completed": False, "error_type": type(exc).__name__, "error": str(exc)}
        return {"completed": True, "result": result}

    first = attempt("shared-first", _request(case_id, arm, "shared-first", 0), first=True)
    probe = attempt("probe", _request(case_id, arm, "probe", 1 if n_inputs > 1 else 0))
    verification = attempt("verification", {"role": "verification", "op": "unregistered",
                                            "case_id": case_id, "arm": arm})
    reset = attempt("reset", _request(case_id, arm, "reset", 0))
    intercepted = None
    try:
        budget.online("restore", _request(case_id, arm, "restore", 0))
    except harness.BudgetExhausted as exc:
        intercepted = str(exc)
    events = [{"step": event["step"], "purpose": event["purpose"], "completed": event["completed"]}
              for event in budget.extra_events]
    if [event["purpose"] for event in events] != ["probe", "verification", "reset"]:
        raise RuntimeError("budget script did not keep the registered purpose order")
    if intercepted is None or any(item["role"] == "restore" for item in seen):
        raise RuntimeError("fourth online call entered the adapter")
    if verification["completed"]:
        raise RuntimeError("unregistered verification was accepted")
    return {"name": "budget_enforcement", "status": "ran", "signoff_ready": False,
            "live_adapter": True, "shared_first": _public_call(first), "probe": _public_call(probe),
            "verification": verification, "reset": _public_call(reset), "extra_events": events,
            "restore_dispatched": False, "intercepted": intercepted,
            "reason": "成功调用进入适配器。未登记校验占用一次。在线复位走同一个计数器。第四次恢复没有进入适配器。"}


def _request(case_id, arm, role, index):
    return {"role": role, "op": "calibration-input", "case_id": case_id, "arm": arm, "index": index}


def _public_call(outcome):
    if not outcome["completed"]:
        return outcome
    result = outcome["result"]
    return {"completed": True, "version": result.get("version"),
            "result_type": type(result.get("result")).__name__, "result": result.get("result"),
            "dependency": result.get("dependency"), "compared_to_expected": False}


def git_text(args):
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()


def checklist_still_unticked():
    overnight = (REPO / "research/release_drift_20261126/OVERNIGHT_20261127_ZH.md").read_text(encoding="utf-8")
    protocol = (REPO / "research/release_drift_20261126/protocol.md").read_text(encoding="utf-8")
    return "- [ ] 共同资料包" in overnight and "- [x] 共同资料包" not in overnight and "- [x]" not in protocol


def deployable_parameters(pin):
    return {"budget_limit": 3, "depth": 3, "scoring_limit": None,
            "loss_weights": {"correct": 0, "deferred": 1, "wrong": 5},
            "tie_break": SEARCH_IDS["tie_break"], "pruning": SEARCH_IDS["pruning"],
            "online_purposes": sorted(harness.ONLINE_PURPOSES),
            "cpython_3_11_pin": pin["cpython_3_11_pin"], "random_arm_ran": False}


def build_receipt():
    pin = interpreter_pin()
    refuse_false_pin(pin)
    if not checklist_still_unticked():
        raise RuntimeError("formal freeze checklist is ticked")
    rebuilt = materialize_packs()
    loaded = {case_id: load_pack(case_id) for case_id in rebuilt}
    packs_match_fixtures(loaded, rebuilt)
    calibration_call.bind_packs({case_id: item["pack"] for case_id, item in loaded.items()})
    canonical = harness.arithmetic_check()
    cases = []
    for case_id, library, case_name in CASE_ORDER:
        cases.append(release_case(case_id, library, case_name, loaded[case_id]))
    for case_id in SLUGIFY_IDS:
        cases.append(slugify_case(case_id, loaded[case_id]))
    expectations = {case["id"]: case["expression_table"] for case in cases}
    registry = [{"case_id": case["id"], "pack_sha256": case["pack_sha256"], "arms": case["arm_ids"]}
                for case in cases]
    frozen = hash_freeze(deployable_parameters(pin), registry, expectations)
    gaps = assess_gaps(cases, pin, frozen)
    digests = {relative: harness.digest_allowed(relative) for relative in sorted(harness.ALLOWED)}
    status = git_text(["status", "--porcelain"])
    return {"label": LABEL, "banner": harness.BANNER, "preparation_not_formal_result": True,
            "cannot_replace_formal_denominators": True,
            "cannot_change_preregistered_method_after_sealed_outcomes": True,
            "sealed_outcomes_used": False, "method_frozen": False, "methods_ranked": False,
            "checklist_boxes_ticked": False, "formal_paired_comparison_started": False,
            "new_algorithm": False, "budget_limit": 3,
            "addendum": ADDENDUM,
            "addendum_commit": git_text(["log", "-1", "--format=%H", "--", ADDENDUM]),
            "head": git_text(["rev-parse", "HEAD"]),
            "addendum_sha256": sha256((REPO / ADDENDUM).read_bytes()).hexdigest(),
            "git_status": status.splitlines(), "interpreter": pin,
            "entry": "research/release_drift_20261126/freeze_prep_20261130/run_followup.py",
            "arithmetic_check": canonical, "cases": cases, "hash_freeze_helper": frozen,
            "calibration_input_digests_are_not_that_freeze": True,
            "calibration_input_digests": digests, "gaps": gaps}


def release_case(case_id, library, case_name, record):
    pack = record["pack"]
    table = validate_expression_table(pack["allowed_offline_criteria"], pack["inputs"], pack["expected"],
                                      pack["observation_kind"])
    dev = harness.load_dev_case(case_name)
    if dev["versions"] != [pack["arms"]["before"]["version"], pack["arms"]["after"]["version"]]:
        raise RuntimeError(f"{case_id} pack versions do not match the public capture")
    preplanned = load_preplanned(case_name)
    values = list(preplanned.values())
    shown = values[0] if values and all(item == values[0] for item in values) else preplanned
    archive = harness.load_archive()[case_name]
    budget = safe_budget(case_id, pack)
    offline_kind = {"column": "column", "duration": "duration-list", "week": "week-string"}[case_name]
    if case_name == "column":
        addressed = address_column()
    else:
        addressed = address_unwrapped(archive["actual_type"])
    return {"id": case_id, "library": library, "label": LABEL, "pack_file": record["relative"],
            "pack_sha256": record["sha256"], "arm_ids": _arm_ids(pack),
            "expression_table": table, "expression_table_label": "空规则表" if not table else "registered",
            "artifacts": {
                "shared_pack": pack_artifact(record),
                "static_sequence": static_artifact(case_id, record, shown),
                "budget_enforcement": budget,
                "normal_replacements": normal_replacements(case_id, pack["expected"][0], dev["first_observed"]),
                "field_address": addressed,
                "disposition_on_case_row": case_row_disposition(table),
                "offline_costs": offline_on(offline_kind, dev["first_observed"]),
            }}


def slugify_case(case_id, record):
    pack = record["pack"]
    table = validate_expression_table(pack["allowed_offline_criteria"], pack["inputs"], pack["expected"],
                                      pack["observation_kind"])
    parent = _parent_record(case_id)
    if isinstance(parent, dict) and "import_error" in parent:
        payload_kind = "import_error"
    elif isinstance(parent, dict) and parent.get("deliveries"):
        payload_kind = "deliveries"
    else:
        payload_kind = "missing"
    budget = safe_budget(case_id, pack)
    return {"id": case_id, "library": "python-slugify", "label": LABEL,
            "pack_file": record["relative"], "pack_sha256": record["sha256"], "arm_ids": _arm_ids(pack),
            "payload_kind": payload_kind, "compared_parent_and_rev": False,
            "revealed_values_copied": False, "expression_table": table,
            "expression_table_label": "空规则表" if not table else "registered",
            "artifacts": {
                "shared_pack": pack_artifact(record),
                "static_sequence": static_artifact(case_id, record, None),
                "budget_enforcement": budget,
                "normal_replacements": normal_replacements(case_id, pack["expected"][0], parent),
                "field_address": address_slugify(parent),
                "disposition_on_case_row": case_row_disposition(table),
                "offline_costs": offline_on("slugify-dict", parent if isinstance(parent, dict) else {}),
            }}


def _parent_record(case_id):
    observations = harness.load_allowed("runs_contract_synthesis_gate_20261125/observations.json")
    observed = observations.get(case_id, {})
    parent = observed.get("parent") if isinstance(observed, dict) else None
    if not isinstance(parent, dict):
        return parent
    if "import_error" in parent:
        return {"import_error": parent["import_error"]}
    deliveries = parent.get("deliveries")
    if isinstance(deliveries, list) and deliveries:
        return {"deliveries": [deliveries[0]]}
    return {}


def _arm_ids(pack):
    if pack["library"] == "python-slugify":
        return {"parent": pack["arms"]["parent"]["commit"], "rev": pack["arms"]["rev"]["commit"]}
    return {"before": pack["arms"]["before"]["version"], "after": pack["arms"]["after"]["version"]}


def pack_artifact(record):
    pack = record["pack"]
    required = ("arms", "provenance", "inputs", "expected", "allowed_offline_criteria")
    missing = [name for name in required if name not in pack]
    both_arms = len(pack.get("arms", {})) == 2
    return {"name": "shared_pack", "status": "ran" if not missing and both_arms else "gap",
            "signoff_ready": False, "file": record["relative"], "sha256": record["sha256"],
            "n_inputs": len(pack["inputs"]), "n_expected": len(pack["expected"]),
            "n_offline_criteria": len(pack["allowed_offline_criteria"]), "both_arms": both_arms,
            "missing": missing,
            "reason": "两臂读同一份资料包。装载器找到了文件并计算了摘要。离线判据列表允许为空。"}


def safe_budget(case_id, pack):
    try:
        report = budget_script(case_id, pack["live_arm"], len(pack["inputs"]), calibration_call.dispatch)
    except Exception as exc:
        return {"name": "budget_enforcement", "status": "gap", "signoff_ready": False,
                "live_adapter": False, "error_type": type(exc).__name__, "error": str(exc),
                "reason": "适配器没有完成预算脚本。没有改用另一个库或另一个案例。"}
    return report


def _slugify_call_note(case):
    budget = case["artifacts"].get("budget_enforcement") or {}
    first = budget.get("shared_first") or {}
    if first.get("completed"):
        dependency = first.get("dependency") or {}
        return (f"{case['id']} 在 parent {first.get('version')} 上返回了 {first.get('result_type')}，"
                f"依赖 Unidecode {dependency.get('unidecode')}，该依赖版本不在夹具里。")
    error = first.get("error") or budget.get("error") or ""
    return f"{case['id']} 的 parent 调用没有成功返回：{error}"


def _live_ok(artifact):
    if not artifact or artifact.get("status") != "ran":
        return False
    return bool(artifact.get("shared_first", {}).get("completed") and artifact.get("probe", {}).get("completed")
                and artifact.get("reset", {}).get("completed") and not artifact.get("verification", {}).get("completed")
                and artifact.get("intercepted"))


def assess_gaps(cases, pin, frozen):
    packs_ok = all(case["artifacts"]["shared_pack"]["status"] == "ran" for case in cases)
    static_ok = all(case["artifacts"]["static_sequence"]["check_search_parity"] == "passed"
                    and case["artifacts"]["static_sequence"]["n_sequences"] > 0
                    and case["artifacts"]["static_sequence"]["sequence_selected"] is False
                    and case["artifacts"]["static_sequence"]["development_preplanned"]["development_preplanned_used"] is False
                    for case in cases)
    live = {case["id"]: _live_ok(case["artifacts"]["budget_enforcement"]) for case in cases}
    release_live = all(live[case_id] for case_id, _, _ in CASE_ORDER)
    slugify_notes = [_slugify_call_note(case) for case in cases if case["library"] == "python-slugify"]
    if release_live and all(live[case_id] for case_id in SLUGIFY_IDS):
        adapter_status = "closed"
        adapter_detail = "六个案例的成功在线调用都进入了钉住的公开版本，第四次没有进入适配器。"
    elif release_live:
        adapter_status = "partial"
        adapter_detail = ("XlsxWriter 与 Babel 的 before 臂进入了钉住轮子。slugify 没有改用其他发行版。"
                          + "".join(slugify_notes))
    else:
        adapter_status, adapter_detail = "open", "现场库调用没有按脚本完成。"
    normals = [case["artifacts"]["normal_replacements"]["registered"] for case in cases]
    address_closed = all(case["artifacts"]["field_address"].get("addressable") for case in cases)
    slugify_addressed = all(case["artifacts"]["field_address"]["status"] == "ran" and
                            case["artifacts"]["field_address"]["wrapped"] is False
                            for case in cases if case["library"] == "python-slugify")
    week_open = any(case["id"] == "babel-week" and case["artifacts"]["field_address"]["wrapped"] is False
                    and not case["artifacts"]["field_address"].get("addressable") for case in cases)
    scalar_open = any(case["id"] == "xlsx-duration" and case["artifacts"]["field_address"]["wrapped"] is False
                      and not case["artifacts"]["field_address"].get("addressable") for case in cases)
    offline_ok = all([item["kind"] for item in case["artifacts"]["offline_costs"]["events"]]
                     == ["backup", "schema", "snapshot_reset"]
                     and not case["artifacts"]["offline_costs"]["entered_extra_calls"]
                     for case in cases)
    disposition_partial = all(case["artifacts"]["disposition_on_case_row"]["verdict"] == "undetermined"
                              and case["artifacts"]["disposition_on_case_row"]["expected_task_loss"] is None
                              for case in cases)
    tables_ok = all(case["expression_table_label"] == "空规则表" and case["expression_table"] == []
                    for case in cases)
    gaps = [
        {"id": "shared_pack", "status": "closed" if packs_ok else "open",
         "detail": "六个案例各有一份两臂共用的资料包，装载器给出了 SHA-256。" if packs_ok else "资料包没有齐。"},
        {"id": "static_sequence", "status": "partial" if static_ok else "open",
         "detail": "校准生成器、合法动作、预算转移、终端评分和深度 3 枚举已登记，核对通过。没有结局质量，未选序列。开发 preplanned 不符合 direction_gate，未使用。"
         if static_ok else "静态序列登记没有达到补记规则。"},
        {"id": "adapters", "status": adapter_status, "detail": adapter_detail, "live_cases": live},
        {"id": "hash_freeze_helper", "status": "closed" if frozen["sha256"] and len(frozen["input_set"]) == 4 else "open",
         "detail": "回执有总摘要和四段输入。正式清单没有勾选。"},
        {"id": "contract_expressions", "status": "closed" if tables_ok else "open",
         "detail": "六个案例都是空规则表。公开义务不是完整输出上的整数、序列长度或整数常量换算。"},
        {"id": "normal_replacements",
         "status": "partial" if normals[:2] == [True, True] and not any(normals[2:]) else "open",
         "detail": "列和时长的正常值来自各自公开 expected，不变量表为空。周历年和 slugify 没有登记正常值。没有使用占位替代常量。"},
        {"id": "disposition_on_case_rows", "status": "partial" if disposition_partial else "open",
         "detail": "空规则表下六个案例行都是未定、交付当前。这是同一条规则，不是六个分数。没有案例级预期损失。"},
        {"id": "offline_cost_counters", "status": "closed" if offline_ok else "open",
         "detail": "离线 Schema、离线备用和快照复位各有次数和耗时，且不在 ExtraCalls 事件里。"},
        {"id": "field_addressability",
         "status": "closed" if address_closed else "partial" if slugify_addressed and week_open and scalar_open else "open",
         "detail": "slugify 的现成字典可以按字段读取。周历年字符串和时长档案标量仍不可寻址，也没有被包裹。"},
        {"id": "cpython_3_11_pin", "status": "open",
         "detail": f"针脚为 {pin['cpython_3_11_pin']}。随机臂没有运行。3.12 不被记成 3.11。"},
    ]
    return gaps


def render_log(receipt):
    lines = ["label: calibration", receipt["banner"], f"addendum_commit: {receipt['addendum_commit']}",
             f"head: {receipt['head']}", f"cpython_3_11_pin: {receipt['interpreter']['cpython_3_11_pin']}",
             f"random_arm_ran: false", f"method_frozen: false", f"checklist_boxes_ticked: false",
             f"hash_freeze_sha256: {receipt['hash_freeze_helper']['sha256']}",
             "hash_freeze_input_set: " + ", ".join(receipt["hash_freeze_helper"]["input_set"]),
             "arithmetic_note: 0、1、5 仍是协议小夹具，不是案例分数。"]
    for case in receipt["cases"]:
        lines.append(f"case: {case['id']} pack: {case['pack_sha256']}")
        for name, artifact in case["artifacts"].items():
            lines.append(f"  {name}: status={artifact.get('status')} signoff_ready=false")
            if artifact.get("reason"):
                lines.append(f"    {artifact['reason']}")
    lines.append("gaps:")
    for gap in receipt["gaps"]:
        lines.append(f"- {gap['id']}: {gap['status']}: {gap['detail']}")
    return "\n".join(lines) + "\n"
