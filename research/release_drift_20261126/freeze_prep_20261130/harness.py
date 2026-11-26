"""Calibration-only wiring of public fixtures through freeze_guards.

The witness policy and the budget dispatcher are drivers for the existing
guards. They are not candidate methods and they do not score cases.
"""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from freeze_guards import (BudgetExhausted, Decision, ExtraCalls, check_search_parity,
                           disposition, expected_task_loss, replay_group, _read)

REPO = HERE.parents[2]
LABEL = "calibration"
BANNER = (
    "这是校准，不是正式结果。此处的数字不能替换正式分母，"
    "也不能用来在看见密封结局之后修改已经预注册的正式方法。"
    "本次运行没有密封结局。"
)
ONLINE_PURPOSES = frozenset({
    "probe", "verification", "replay", "compare",
    "reset", "backup", "restore", "recovery",
})
PACK_FIELDS = (
    "registered_operation", "user_requirement", "applicable_versions", "old_schema",
    "pre_upgrade_public_docs", "original_regression_inputs",
    "original_regression_expectations", "candidate_requests", "criteria",
    "shared_backup_actions", "material_version", "provenance",
)
SEARCH_KEYS = ("task_pack", "candidates", "prior", "transition", "legal_actions",
               "terminal_score", "pruning", "tie_break")
ALLOWED = frozenset({
    "runs_upstream_functional_20261124/paired_releases.json",
    "research/release_drift_20261126/dev_parallel/results/column.json",
    "research/release_drift_20261126/dev_parallel/results/duration.json",
    "research/release_drift_20261126/dev_parallel/results/week.json",
    "runs_contract_synthesis_gate_20261125/sample.json",
    "runs_contract_synthesis_gate_20261125/tasks.json",
    "runs_contract_synthesis_gate_20261125/observations.json",
    "runs_contract_synthesis_gate_20261125/checks.json",
    "runs_contract_synthesis_gate_20261125/revealed_slugify.json",
    "runs_contract_synthesis_gate_20261125/python-slugify-1.txt",
    "runs_contract_synthesis_gate_20261125/python-slugify-2.txt",
    "runs_contract_synthesis_gate_20261125/python-slugify-3.txt",
})
FORBIDDEN = re.compile(r"(?i)pandas|pillow|scipy|sealed|environment_receipts")
DUMMY = "calibration-alt"
WITNESS_REQUEST = {"role": "calibration-witness"}
WITNESS_ALT = {"role": "calibration-witness-alt"}
SLUGIFY_IDS = ("python-slugify-1", "python-slugify-2", "python-slugify-3")
DEV_CASES = (
    ("xlsx-column", "XlsxWriter", "column"),
    ("xlsx-duration", "XlsxWriter", "duration"),
    ("babel-week", "Babel", "week"),
)


class SharedBudget:
    """One shared first request, then one ExtraCalls counter for every online purpose."""

    def __init__(self, dispatch):
        self._dispatch = dispatch
        self._first = None
        self._extras = ExtraCalls(dispatch)

    @property
    def first(self):
        return deepcopy(self._first)

    @property
    def extra_events(self):
        return self._extras.events

    def shared_first(self, request):
        if self._first is not None:
            raise ValueError("shared first request already issued")
        self._first = {"request": deepcopy(request), "completed": False}
        result = self._dispatch(request)
        self._first["completed"] = True
        return result

    def online(self, purpose, request):
        if self._first is None:
            raise ValueError("shared first request has not been issued")
        if purpose not in ONLINE_PURPOSES:
            raise ValueError("unregistered online purpose")
        return self._extras.call(purpose, request)


def calibration_witness(context, history):
    """Replay driver. Not a candidate method."""
    observed = _read(history[-1]["response"], context["field"])
    request = context["logged_request"] if observed == context["logged_observed"] else context["alternate_request"]
    return Decision(request, (), "calibration-witness")


def arithmetic_check():
    losses = [expected_task_loss(*masses) for masses in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
    if losses != [0, 1, 5]:
        raise RuntimeError("arithmetic check drifted from 0, 1, 5")
    actions = {
        "violated_verified": disposition("violated", verified_replacement=True),
        "violated_unverified": disposition("violated", verified_replacement=False),
        "satisfied": disposition("satisfied", verified_replacement=False),
        "undetermined": disposition("undetermined", verified_replacement=True),
    }
    expected = {
        "violated_verified": "deliver_replacement",
        "violated_unverified": "defer",
        "satisfied": "deliver_current",
        "undetermined": "deliver_current",
    }
    if actions != expected:
        raise RuntimeError("disposition check drifted")
    return {"label": LABEL, "fixture": "protocol-tiny", "case_rows_used": False,
            "losses": [int(value) for value in losses], "actions": actions}


def require_allowed(path):
    resolved = Path(path).resolve()
    try:
        relative = resolved.relative_to(REPO).as_posix()
    except ValueError:
        raise SystemExit(f"refusing path outside the repository: {path}")
    if FORBIDDEN.search(relative):
        raise SystemExit(f"refusing sealed or out-of-study path: {path}")
    if relative not in ALLOWED:
        raise SystemExit(f"refusing path outside the public calibration allow list: {path}")
    return relative


def digest_allowed(relative):
    path = REPO / relative
    require_allowed(path)
    return sha256(path.read_bytes()).hexdigest()


def load_allowed(relative):
    path = REPO / relative
    require_allowed(path)
    return json.loads(path.read_text(encoding="utf-8"))


def column_feasible(response):
    return isinstance(response, dict) and type(response.get("visible")) is bool and isinstance(response.get("cell_text"), str)


def duration_feasible(response):
    return (isinstance(response, list) and len(response) == 2
            and isinstance(response[0], float) and isinstance(response[1], str))


def classify_response(response):
    if column_feasible(response) and set(response) == {"visible", "cell_text"}:
        return "column"
    if duration_feasible(response):
        return "duration"
    return None


def _attempt(response, replacements, feasible, field):
    context = {"field": list(field), "logged_observed": _read(response, field),
               "logged_request": dict(WITNESS_REQUEST), "alternate_request": dict(WITNESS_ALT)}
    history = [{"response": response}]
    logged = calibration_witness(context, history)
    try:
        audit = replay_group(calibration_witness, context, history, logged, replacements, feasible)
    except (ValueError, KeyError, IndexError) as exc:
        return {"rejected": True, "exception": type(exc).__name__, "message": str(exc)}
    if audit.get("effect") == "unauditable":
        return {"rejected": True, "effect": "unauditable", "reason": audit.get("reason")}
    return {"rejected": False, "effect": audit.get("effect"), "attribution": False,
            "alternative": DUMMY, "note": "calibration witness only; not an active-method attribution"}


def replay_public(response):
    kind = classify_response(response)
    if kind is None:
        return {"name": "field_group_replay", "status": "gap", "signoff_ready": False, "wrapped": False,
                "observed_type": type(response).__name__,
                "reason": "返回值没有登记的字段路径。没有包一层新的结构，也没有改选另一行。"}
    if kind == "column":
        field, feasible = ["cell_text"], column_feasible
        attempts = {
            "overlapping": ([(["visible"], False), (["visible"], True)]),
            "infeasible": ([(["visible"], "hidden")]),
            "unchanged": ([(["cell_text"], response["cell_text"])]),
            "nonminimal": ([(["visible"], False), (["cell_text"], DUMMY)]),
            "missing": ([(["missing"], 0)]),
            "legal": ([(["cell_text"], DUMMY)]),
        }
    else:
        field, feasible = [1], duration_feasible
        attempts = {
            "overlapping": ([([1], DUMMY), ([1], "other")]),
            "infeasible": ([([0], "hidden")]),
            "unchanged": ([([1], response[1])]),
            "nonminimal": ([([0], response[0]), ([1], DUMMY)]),
            "missing": ([([2], 0)]),
            "legal": ([([1], DUMMY)]),
        }
    done = {name: _attempt(response, replacements, feasible, field) for name, replacements in attempts.items()}
    return {"name": "field_group_replay", "status": "ran", "signoff_ready": False, "shape": kind,
            "wrapped": False, "registered_normal_value": False, "coupled_invariant": False,
            "attempts": done,
            "reason": "replay_group 在已承认的形状上执行了。替代值是校准占位符，不是登记过的正常值，不能用于签收。"}


def incomplete_settings():
    settings = {"depth": 3, "scoring_limit": None}
    settings.update({key: "" for key in SEARCH_KEYS})
    return settings


def static_report(preplanned_present):
    settings = incomplete_settings()
    try:
        check_search_parity(settings, dict(settings))
    except ValueError as exc:
        rejection = str(exc)
    else:
        raise RuntimeError("incomplete static settings were accepted")
    return {"name": "static_sequence", "status": "gap", "signoff_ready": False,
            "guard_invoked": True, "empty_settings_rejected": True, "rejection": rejection,
            "sequence_enumerated": False, "development_preplanned_present": bool(preplanned_present),
            "development_preplanned_used": False,
            "reason": "没有登记静态序列。残缺设置被 check_search_parity 拒绝。没有枚举序列，也没有使用开发实验的 preplanned 值。"}


def development_preplanned_is_present(results):
    if not isinstance(results, dict):
        return False
    found = False
    for side in results.values():
        static = side.get("static_info") if isinstance(side, dict) else None
        if isinstance(static, dict) and "preplanned" in static:
            found = True
    return found


def pack_report(public_fields, notes):
    fields = {}
    for name in PACK_FIELDS:
        status = public_fields.get(name, "absent")
        if status not in {"absent", "public_fixture_only"}:
            raise RuntimeError("pack field status drifted")
        fields[name] = status
    return {"name": "shared_pack_summary_loader", "status": "ran", "signoff_ready": False,
            "shared_pack_file": None, "fields": fields, "notes": notes,
            "reason": "装载器读完了允许的公开夹具。没有共同资料包文件，不能做两侧共用的摘要。"}


def budget_demo(records):
    dispatched = []

    def dispatch(request):
        dispatched.append(request["role"])
        if request["role"] == "unavailable":
            raise OSError("calibration dispatcher has no live adapter")
        index = request.get("index")
        if not isinstance(index, int) or index < 0 or index >= len(records):
            raise OSError("calibration dispatcher has no stored payload")
        return {"stored_payload_type": type(records[index]).__name__}

    budget = SharedBudget(dispatch)
    try:
        budget.shared_first({"role": "shared-first", "index": 0})
        first_completed = True
    except OSError:
        first_completed = False
    plan = (("probe", {"role": "probe", "index": 1}),
            ("verification", {"role": "unavailable"}),
            ("reset", {"role": "reset", "index": 0}))
    for purpose, request in plan:
        try:
            budget.online(purpose, request)
        except OSError:
            pass
    intercepted = None
    try:
        budget.online("restore", {"role": "restore", "index": 0})
    except BudgetExhausted as exc:
        intercepted = str(exc)
    events = [{"step": event["step"], "purpose": event["purpose"], "completed": event["completed"]}
              for event in budget.extra_events]
    report = {"name": "budget_enforcement", "status": "ran", "signoff_ready": False,
              "live_adapter": False, "adapters_invoked": [], "shared_first_completed": first_completed,
              "shared_first_charged": False, "extra_events": events, "dispatched_roles": dispatched,
              "restore_dispatched": "restore" in dispatched, "intercepted": intercepted,
              "reason": "计数器按脚本执行了。分派的是存档载荷的类型，不是库适配器。"}
    if [event["purpose"] for event in events] != ["probe", "verification", "reset"]:
        raise RuntimeError("budget script did not keep the registered purpose order")
    if len(events) != 3 or intercepted is None or report["restore_dispatched"]:
        raise RuntimeError("fourth online call was not intercepted")
    if not any(not event["completed"] for event in events):
        raise RuntimeError("scripted failure did not consume a slot")
    if budget.first is None or budget.first["request"]["role"] == "restore":
        raise RuntimeError("shared first request was not kept apart from the extra counter")
    return report


def disposition_report(canonical):
    local = arithmetic_check()
    if local != canonical:
        raise RuntimeError("per-case arithmetic check diverged")
    return {"name": "disposition_and_expected_task_loss", "status": "ran", "signoff_ready": False,
            "fixture": "protocol-tiny", "case_rows_used": False,
            "reason": "调用了共同函数。输入是协议里的小夹具，不是这个案例的行。"}


def load_archive():
    data = load_allowed("runs_upstream_functional_20261124/paired_releases.json")
    loaded = {}
    for key in ("column", "duration", "week"):
        block = data[key]
        sample = block["before"]["rows"][0]
        loaded[key] = {"source": block["source"],
                       "versions": [block["before"]["version"], block["after"]["version"]],
                       "wheels_present": all(isinstance(block[side].get("sha256"), str) and block[side]["sha256"]
                                             for side in ("before", "after")),
                       "n_rows": len(block["before"]["rows"]),
                       "input_field": "input" in sample, "expected_field": "expected" in sample,
                       "actual_type": type(sample["actual"]).__name__,
                       "detected_inputs_present": "detected_inputs" in block,
                       "detected_inputs_recomputed": False}
    return loaded


def load_dev_case(name):
    data = load_allowed(f"research/release_drift_20261126/dev_parallel/results/{name}.json")
    captures = data["captures"]
    first = captures[0]["initial"][0]["observed"]
    bank = [item["observed"] for item in captures[0]["bank"]]
    return {"source": data.get("source"), "versions": data.get("versions"),
            "wheels_present": isinstance(data.get("wheels"), list) and bool(data["wheels"]),
            "n_initial": len(captures[0]["initial"]), "n_bank": len(captures[0]["bank"]),
            "n_endpoints": len(captures), "first_observed": first,
            "replay_pool": [first, *bank[:2]],
            "development_preplanned_present": development_preplanned_is_present(data.get("results")),
            "development_results_copied": False}


def release_notes():
    return ["适用版本、出处和轮子摘要只出现在公开夹具里。",
            "校准输入不是正式任务的升级前回归集。",
            "存档 expected 不是已登记的契约表达式。",
            "开发探针库不升格为资料包中的候选请求。"]


def release_case(archive_row, dev_row, case_id, library, canonical):
    if archive_row["versions"] != dev_row["versions"] or archive_row["source"] != dev_row["source"]:
        raise ValueError(f"{case_id} public fixtures disagree on version or source")
    response = dev_row["first_observed"]
    return {"id": case_id, "library": library, "label": LABEL, "source": archive_row["source"],
            "versions": archive_row["versions"], "n_archive_rows": archive_row["n_rows"],
            "n_capture_initial": dev_row["n_initial"], "n_capture_bank": dev_row["n_bank"],
            "archive_actual_type": archive_row["actual_type"],
            "capture_observed_type": type(response).__name__,
            "detected_inputs_recomputed": False, "development_results_copied": False,
            "artifacts": {
                "shared_pack_summary_loader": pack_report({
                    "applicable_versions": "public_fixture_only",
                    "provenance": "public_fixture_only",
                    "material_version": "public_fixture_only" if archive_row["wheels_present"] else "absent",
                    "original_regression_inputs": "public_fixture_only" if archive_row["input_field"] else "absent",
                    "original_regression_expectations": "public_fixture_only" if archive_row["expected_field"] else "absent",
                }, release_notes()),
                "static_sequence": static_report(dev_row["development_preplanned_present"]),
                "field_group_replay": replay_public(response),
                "disposition_and_expected_task_loss": disposition_report(canonical),
                "budget_enforcement": budget_demo(dev_row["replay_pool"]),
            }}


def slugify_payload(parent):
    if not isinstance(parent, dict):
        return {"kind": "missing", "records": [], "counts": {}}
    counts = {key: len(parent[key]) for key in ("assertions", "properties", "deliveries")
              if isinstance(parent.get(key), list)}
    if "import_error" in parent:
        text = parent["import_error"]
        return {"kind": "import_error", "records": [parent], "counts": counts,
                "import_error": text if isinstance(text, str) else "present"}
    deliveries = parent.get("deliveries")
    if isinstance(deliveries, list) and deliveries:
        return {"kind": "deliveries", "records": deliveries, "counts": counts}
    return {"kind": "missing", "records": [], "counts": counts}


def load_slugify():
    sample = [row for row in load_allowed("runs_contract_synthesis_gate_20261125/sample.json")
              if row.get("project") == "python-slugify"]
    tasks = load_allowed("runs_contract_synthesis_gate_20261125/tasks.json").get("python-slugify")
    observations = load_allowed("runs_contract_synthesis_gate_20261125/observations.json")
    checks = load_allowed("runs_contract_synthesis_gate_20261125/checks.json")
    revealed = load_allowed("runs_contract_synthesis_gate_20261125/revealed_slugify.json")
    by_id = {row["id"]: row for row in sample}
    loaded = {"n_task_rows": len(tasks) if isinstance(tasks, list) else 0,
              "task_expected_present": isinstance(tasks, list) and all(isinstance(row, list) and len(row) >= 3 for row in tasks),
              "revealed_ids": [key for key in SLUGIFY_IDS if key in revealed],
              "revealed_values_copied": False, "ids": {}}
    for case_id in SLUGIFY_IDS:
        observed = observations.get(case_id, {})
        parent = observed.get("parent") if isinstance(observed, dict) else None
        payload = slugify_payload(parent)
        meta = by_id.get(case_id, {})
        loaded["ids"][case_id] = {"parent_commit": meta.get("parent"), "rev_commit": meta.get("rev"),
                                  "readme": meta.get("readme"), "doc_hash_present": isinstance(meta.get("doc_hash"), str),
                                  "n_checks": len(checks[case_id]) if isinstance(checks.get(case_id), list) else 0,
                                  "payload": payload, "compared_parent_and_rev": False}
    return loaded


def _slugify_shape(payload):
    if payload["records"]:
        return payload["records"][0]
    return "missing"


def slugify_case(case_id, row, canonical, inventory):
    payload = row["payload"]
    notes = ["parent 与 rev 没有比较。",
             "parent/rev 是另一项公开研究里的提交标识，不是静默漂移资料包中的版本对。",
             "readme 已摘要，但没有当作升级前公开文档。",
             "tasks 与 checks 里的期望值不是已登记的契约表达式。"]
    if payload["kind"] == "import_error":
        notes.append("parent 侧的公开记录是导入错误，没有工具返回。")
    return {"id": case_id, "library": "python-slugify", "label": LABEL,
            "parent_commit": row["parent_commit"], "rev_commit": row["rev_commit"],
            "payload_side": "parent", "payload_kind": payload["kind"],
            "record_counts": payload["counts"], "n_checks": row["n_checks"],
            "compared_parent_and_rev": False, "revealed_values_copied": False,
            "import_error": payload.get("import_error"),
            "artifacts": {
                "shared_pack_summary_loader": pack_report({
                    "applicable_versions": "public_fixture_only" if row["parent_commit"] and row["rev_commit"] else "absent",
                    "provenance": "public_fixture_only" if row["parent_commit"] else "absent",
                    "material_version": "public_fixture_only" if row["doc_hash_present"] else "absent",
                    "original_regression_inputs": "public_fixture_only" if inventory["n_task_rows"] else "absent",
                    "original_regression_expectations": "public_fixture_only" if inventory["task_expected_present"] else "absent",
                }, notes),
                "static_sequence": static_report(False),
                "field_group_replay": replay_public(_slugify_shape(payload)),
                "disposition_and_expected_task_loss": disposition_report(canonical),
                "budget_enforcement": budget_demo(payload["records"]),
            }}


def error_case(case_id, library, exc):
    return {"id": case_id, "library": library, "label": LABEL, "status": "gap",
            "reason": f"{type(exc).__name__}: {exc}", "artifacts": {}}


def collect_gaps(cases):
    gaps = [
        {"id": "no_shared_pack", "blocks_freeze_signoff": True,
         "detail": "没有两侧共用的资料包文件。装载器只能指出公开夹具里散落的字段。"},
        {"id": "no_static_sequence", "blocks_freeze_signoff": True,
         "detail": "没有登记候选生成器、合法动作、先验、转移、终端评分和深度为三的序列。残缺设置会被拒绝。开发实验的 preplanned 未使用。"},
        {"id": "adapters_not_plugged_into_freeze_guards", "blocks_freeze_signoff": True,
         "detail": "XlsxWriter、Babel 和 slugify 的工具适配器没有接到 ExtraCalls 后面。试跑分派的是存档载荷。"},
        {"id": "no_hash_freeze_helper", "blocks_freeze_signoff": True,
         "detail": "没有对可部署参数、任务注册表、合理预期和处置规则做哈希冻结的辅助函数。输入文件摘要不能代替它。"},
        {"id": "no_registered_contract_expressions", "blocks_freeze_signoff": True,
         "detail": "这些案例没有登记 contract_value、direct_delivery 或 transferred_verdict 的表达式表。"},
        {"id": "no_registered_normal_replacements", "blocks_freeze_signoff": True,
         "detail": "没有登记正常替代值和字段间不变量。校准占位符不能用于反事实签收。"},
        {"id": "disposition_not_applied_to_case_rows", "blocks_freeze_signoff": True,
         "detail": "案例行没有登记的任务裁决。0、1、5 只来自协议小夹具。"},
        {"id": "no_offline_cost_counters", "blocks_freeze_signoff": True,
         "detail": "离线 Schema、离线备用和初态快照复位的另计次数还没有实现。"},
        {"id": "freeze_checklist_not_ticked", "blocks_freeze_signoff": True,
         "detail": "11 月 30 日清单没有勾选，正式方法也没有冻结。"},
    ]
    for case in cases:
        replay = case.get("artifacts", {}).get("field_group_replay")
        if replay and replay.get("status") == "gap":
            gaps.append({"id": f"{case['id']}_replay_not_addressable", "blocks_freeze_signoff": True,
                         "detail": replay["reason"]})
        elif case.get("status") == "gap":
            gaps.append({"id": f"{case['id']}_not_completed", "blocks_freeze_signoff": True,
                         "detail": case.get("reason", "案例没有完成")})
        if case.get("id") == "xlsx-duration" and case.get("archive_actual_type") not in {"dict", "list"}:
            gaps.append({"id": "duration_archive_scalar_not_addressable", "blocks_freeze_signoff": True,
                         "detail": "paired_releases 的时长 actual 不是可寻址的字段结构。试跑没有把开发捕获回写成该标量。"})
    return gaps


def git_text(args):
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()


def build_receipt():
    canonical = arithmetic_check()
    digests = {}
    missing = []
    for relative in sorted(ALLOWED):
        try:
            digests[relative] = digest_allowed(relative)
        except FileNotFoundError:
            digests[relative] = None
            missing.append(relative)
    protocol_path = HERE / "protocol.md"
    cases = []
    try:
        archive = load_archive()
        dev = {name: load_dev_case(name) for _, _, name in DEV_CASES}
    except Exception as exc:
        archive = dev = None
        for case_id, library, _ in DEV_CASES:
            cases.append(error_case(case_id, library, exc))
    if archive is not None:
        for case_id, library, name in DEV_CASES:
            try:
                cases.append(release_case(archive[name], dev[name], case_id, library, canonical))
            except RuntimeError:
                raise
            except Exception as exc:
                cases.append(error_case(case_id, library, exc))
    try:
        slugify = load_slugify()
    except Exception as exc:
        slugify = None
        for case_id in SLUGIFY_IDS:
            cases.append(error_case(case_id, "python-slugify", exc))
    if slugify is not None:
        for case_id in SLUGIFY_IDS:
            try:
                cases.append(slugify_case(case_id, slugify["ids"][case_id], canonical, slugify))
            except RuntimeError:
                raise
            except Exception as exc:
                cases.append(error_case(case_id, "python-slugify", exc))
    status = git_text(["status", "--porcelain"])
    return {"label": LABEL, "banner": BANNER, "preparation_not_formal_result": True,
            "cannot_replace_formal_denominators": True,
            "cannot_change_preregistered_method_after_sealed_outcomes": True,
            "sealed_outcomes_used": False, "method_frozen": False, "methods_ranked": False,
            "checklist_boxes_ticked": False, "formal_paired_comparison_started": False,
            "new_algorithm": False, "budget_limit": 3, "live_library_execution": False,
            "protocol_commit": git_text(["log", "-1", "--format=%H", "--",
                                         "research/release_drift_20261126/freeze_prep_20261130/protocol.md"]),
            "head": git_text(["rev-parse", "HEAD"]),
            "protocol_sha256": sha256(protocol_path.read_bytes()).hexdigest(),
            "git_status": status.splitlines(), "python": sys.version,
            "entry": "research/release_drift_20261126/freeze_prep_20261130/run.py",
            "arithmetic_check": canonical,
            "slugify_inventory": None if slugify is None else {
                "n_task_rows": slugify["n_task_rows"], "task_expected_present": slugify["task_expected_present"],
                "revealed_ids": slugify["revealed_ids"], "revealed_values_copied": False},
            "missing_allow_list_files": missing, "cases": cases, "gaps": collect_gaps(cases),
            "hash_freeze_helper": {"status": "gap",
                                   "reason": "输入摘要不是参数、注册表、预期和处置规则的哈希冻结。",
                                   "calibration_input_digests_are_not_that_freeze": True,
                                   "digests": digests}}
