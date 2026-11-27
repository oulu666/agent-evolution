"""Tests for the cost–correctness curve addendum. The original joint
denominators and joint-receipt decision counts must stay unchanged.
"""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

from cost_curve import (
    BUDGETS,
    LEGAL_OBSERVATIONS,
    quality_equal,
    quality_strictly_better,
)
from cost_curve_task import build_receipt, write_receipt
from joint_world import CASES, EXTRA_BUDGET

HERE = Path(__file__).resolve().parent
RECEIPT = HERE / "cost-curve-receipt.json"
JOINT_RECEIPT = HERE / "joint-receipt.json"
JOINT_REPORT = HERE / "JOINT_REPORT_ZH.md"
CURVE_REPORT = HERE / "COST_CURVE_ZH.md"
ARCHIVE_REPORT = HERE.parents[2] / "REPORT_ZH.md"
SOURCE_DRAFT_RECEIPT = Path(
    "/workspace/agent-evolution-drafts/joint_receiver_oracle_20261127"
    "/research/release_drift_20261126/receiver_learning/joint-receipt.json"
)
SOURCE_CHECKSUM = (
    "da365415937f629f91566e6bcc7731726185eb24bd8d086c053bd8351a722f42"
)
VOLATILE = "local_cpu_seconds"
CASE_IDS = (
    "synthetic_preview_cache_download",
    "synthetic_two_download_files",
    "synthetic_joint_receiver_oracle",
)
CONCLUSIONS = (
    "联合学习在第三个合成案例中获得 2 行相对拆分方法的收益。",
    "强完整追踪方法达到同样结果，无法将收益独立归因于联合选择。",
    "当前停止该分支的复杂化，真实任务泛化和预算效率均未得到验证。",
)


def _main_checkout():
    here = Path(__file__).resolve().parent
    repo = here.parents[2]
    oracle = repo / "research/release_drift_20261126/receiver_learning/test_oracle.py"
    if oracle.exists():
        return repo
    return Path("/workspace/agent-evolution-main-88ca0d20")


MAIN = _main_checkout()


def _drop_cpu(payload):
    data = json.loads(json.dumps(payload))
    data.pop(VOLATILE, None)
    return data


def _point(curve, name, budget):
    for item in curve[name]:
        if item["budget"] == budget:
            return item
    raise KeyError((name, budget))


def _perfect():
    return {
        "violation_rows": 2,
        "healthy_rows": 6,
        "false_release": 0,
        "correct_block": 2,
        "violation_deferred": 0,
        "retention": 6,
        "false_block": 0,
        "healthy_deferred": 0,
    }


def _defer_all():
    return {
        "violation_rows": 2,
        "healthy_rows": 6,
        "false_release": 0,
        "correct_block": 0,
        "violation_deferred": 2,
        "retention": 0,
        "false_block": 0,
        "healthy_deferred": 6,
    }


class CostCurveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = build_receipt()
        cls.path, cls.digest = write_receipt(cls.receipt, RECEIPT)
        top = HERE.parents[2] / "cost-curve-receipt.json"
        top.write_text(RECEIPT.read_text(encoding="utf-8"), encoding="utf-8")

    def test_head_and_flags(self):
        self.assertEqual(self.receipt["base_head"], "88ca0d2090794b363c8db82a4106f2c952b69aec")
        self.assertEqual(self.receipt["original_joint_base_head"], "88ca0d2090794b363c8db82a4106f2c952b69aec")
        self.assertTrue(self.receipt["does_not_replace_joint_receipt"])
        self.assertTrue(self.receipt["does_not_change_original_denominators"])
        self.assertTrue(self.receipt["synthetic_only"])
        self.assertTrue(self.receipt["core_algorithm_not_established"])
        self.assertTrue(self.receipt["does_not_establish_eswa_core_contribution"])
        self.assertTrue(self.receipt["no_fourth_synthetic_case"])
        self.assertTrue(self.receipt["no_gpu_or_paid_model"])
        self.assertEqual(self.receipt["model_calls"], 0)
        self.assertEqual(self.receipt["default_extra_observation_budget"], EXTRA_BUDGET)
        self.assertEqual(tuple(self.receipt["cases"]), CASE_IDS)
        self.assertEqual(len(CASES), 3)

    def test_source_joint_receipt_not_rewritten(self):
        # This path exists only on the development box that holds the earlier
        # joint-learning draft. In a checkout of this increment alone, skip it;
        # the in-tree joint-receipt decision counts are locked separately.
        if not SOURCE_DRAFT_RECEIPT.exists():
            self.skipTest("original joint draft directory is not on this machine")
        digest = hashlib.sha256(SOURCE_DRAFT_RECEIPT.read_bytes()).hexdigest()
        self.assertEqual(digest, SOURCE_CHECKSUM)

    def test_original_joint_denominators_locked(self):
        original = json.loads(JOINT_RECEIPT.read_text(encoding="utf-8"))
        locked = self.receipt["original_joint_locked_metrics"]
        self.assertEqual(original["independent_gain"], locked["independent_gain"])
        self.assertTrue(original["independent_gain"]["any_independent_gain_vs_split"])
        self.assertFalse(original["independent_gain"]["any_independent_gain_vs_strong_control"])
        split = original["independent_gain"]["by_case"]["synthetic_joint_receiver_oracle"]["vs_three_split_systems"]
        self.assertEqual(len(split), 2)
        self.assertEqual(
            original["independent_gain"]["by_case"]["synthetic_joint_receiver_oracle"]["vs_strong_control"],
            [],
        )
        for case_id in CASE_IDS:
            self.assertEqual(
                original["cases"][case_id]["metrics"],
                locked["cases"][case_id]["metrics"],
            )
            joint = original["cases"][case_id]["metrics"]["joint"]
            self.assertEqual(joint["violation_rows"], 2)
            self.assertEqual(joint["healthy_rows"], 6)
            self.assertEqual(joint["false_release"], 0)
            self.assertEqual(joint["correct_block"], 2)
            self.assertEqual(joint["retention"], 6)

    def test_counting_rule_distinguishes_real_ops_from_logical_reads(self):
        rule = self.receipt["counting_rule"]
        for kind in ("generate", "consumer_read", "artifact_read"):
            self.assertIn(kind, rule["real_tool_operations"])
        for phase in ("demo_collection", "extra_observation", "runtime_accept"):
            self.assertIn(phase, rule["phases"])
        self.assertIn("equivalent()", rule["not_real_tool_operations"])

    def test_preview_case_default_budget(self):
        curve = self.receipt["cases"]["synthetic_preview_cache_download"]["curve"]
        perfect = _perfect()
        for budget in BUDGETS:
            joint = _point(curve, "joint", budget)
            static = _point(curve, "optimal_static", budget)
            self.assertEqual(joint["metrics"], perfect)
            self.assertEqual(static["metrics"], perfect)
            self.assertEqual(joint["cost"]["real_tool_operations_total"], 10)
            self.assertEqual(static["cost"]["real_tool_operations_total"], 10)
            self.assertEqual(joint["extra_observations"], 0)
            self.assertEqual(static["search"]["selected_plan"], [])
            self.assertEqual(joint["cost"]["by_phase"], {
                "demo_collection": 2, "extra_observation": 0, "runtime_accept": 8,
            })
        self.assertEqual(curve["lookup"]["metrics"], perfect)
        self.assertEqual(curve["lookup"]["cost"]["real_tool_operations_total"], 8)
        self.assertEqual(curve["lookup"]["cost"]["by_phase"]["demo_collection"], 0)
        self.assertEqual(_point(curve, "full_trace_same_budget", 0)["cost"]["real_tool_operations_total"], 10)
        self.assertEqual(_point(curve, "full_trace_same_budget", 1)["cost"]["real_tool_operations_total"], 12)
        self.assertEqual(_point(curve, "full_trace_same_budget", 1)["metrics"], perfect)
        self.assertEqual(_point(curve, "full_trace_same_budget", 2)["cost"]["real_tool_operations_total"], 14)
        self.assertEqual(curve["full_trace_unlimited"]["cost"]["real_tool_operations_total"], 14)
        self.assertEqual(curve["full_trace_unlimited"]["metrics"], perfect)
        self.assertEqual(curve["full_trace_unlimited"]["extra_observations"], 2)
        self.assertFalse(curve["joint"][1]["note"]["only_decided_after_consumption_trace"])

    def test_ambiguous_cases_need_one_consumption_observation(self):
        perfect = _perfect()
        deferred = _defer_all()
        for case_id in ("synthetic_two_download_files", "synthetic_joint_receiver_oracle"):
            curve = self.receipt["cases"][case_id]["curve"]
            self.assertEqual(curve["lookup"]["metrics"], deferred)
            self.assertEqual(curve["lookup"]["cost"]["real_tool_operations_total"], 0)
            self.assertEqual(_point(curve, "joint", 0)["metrics"], deferred)
            self.assertEqual(_point(curve, "joint", 0)["cost"]["real_tool_operations_total"], 2)
            self.assertEqual(_point(curve, "optimal_static", 0)["metrics"], deferred)
            self.assertEqual(_point(curve, "full_trace_same_budget", 0)["metrics"], deferred)
            for budget in (1, 2):
                joint = _point(curve, "joint", budget)
                static = _point(curve, "optimal_static", budget)
                full_b = _point(curve, "full_trace_same_budget", budget)
                self.assertEqual(joint["metrics"], perfect)
                self.assertEqual(static["metrics"], perfect)
                self.assertEqual(full_b["metrics"], perfect)
                self.assertEqual(joint["cost"]["real_tool_operations_total"], 12)
                self.assertEqual(static["cost"]["real_tool_operations_total"], 12)
                self.assertEqual(joint["extra_observations"], 1)
                self.assertEqual(joint["plan"], ["subsequent_reads"])
                self.assertEqual(static["search"]["selected_plan"], ["subsequent_reads"])
                self.assertEqual(joint["positions"], [4])
            # Budget 2 does not make joint take a second observation.
            self.assertEqual(_point(curve, "joint", 2)["extra_observations"], 1)
            self.assertEqual(_point(curve, "full_trace_same_budget", 1)["cost"]["real_tool_operations_total"], 12)
            self.assertEqual(_point(curve, "full_trace_same_budget", 2)["cost"]["real_tool_operations_total"], 14)
            self.assertEqual(curve["full_trace_unlimited"]["metrics"], perfect)
            self.assertEqual(curve["full_trace_unlimited"]["cost"]["real_tool_operations_total"], 14)
            self.assertTrue(_point(curve, "joint", 1)["note"]["only_decided_after_consumption_trace"])
        # The third case uniquely locks (4, parsed_value).
        joint3 = _point(
            self.receipt["cases"]["synthetic_joint_receiver_oracle"]["curve"], "joint", 1)
        self.assertEqual(joint3["relations"], ["parsed_value"])
        self.assertTrue(joint3["note"]["required_consumption_evidence_to_unique_pair"])

    def test_real_tool_events_for_subsequent_reads(self):
        curve = self.receipt["cases"]["synthetic_joint_receiver_oracle"]["curve"]
        events = _point(curve, "joint", 1)["cost"]["events"]
        phases = [event["phase"] for event in events]
        kinds = [event["kind"] for event in events]
        self.assertEqual(phases.count("demo_collection"), 2)
        self.assertEqual(phases.count("extra_observation"), 2)
        self.assertEqual(phases.count("runtime_accept"), 8)
        self.assertEqual(kinds, [
            "generate", "generate", "generate", "consumer_read",
        ] + ["artifact_read"] * 8)
        extra = [event for event in events if event["phase"] == "extra_observation"]
        self.assertEqual(extra[0]["kind"], "generate")
        self.assertEqual(extra[1]["kind"], "consumer_read")
        self.assertEqual(extra[1]["slot"], 4)

    def test_legal_observation_set_is_searched(self):
        self.assertEqual(
            LEGAL_OBSERVATIONS,
            ("subsequent_reads", "contrast_canaries", "reread_known_slot"),
        )
        search = _point(
            self.receipt["cases"]["synthetic_joint_receiver_oracle"]["curve"],
            "optimal_static",
            1,
        )["search"]
        plans = {tuple(item["plan"]) for item in search["plans"]}
        self.assertEqual(plans, {(), ("subsequent_reads",), ("contrast_canaries",), ("reread_known_slot",)})
        self.assertEqual(search["n_plans_evaluated"], 4)
        reread = next(item for item in search["plans"] if item["plan"] == ["reread_known_slot"])
        self.assertEqual(reread["metrics"], _defer_all())

    def test_joint_does_not_beat_optimal_static(self):
        comparisons = self.receipt["comparisons"]
        self.assertFalse(comparisons["joint_strictly_better_than_optimal_static_any_budget"])
        self.assertFalse(comparisons["optimal_static_strictly_better_than_joint_any_budget"])
        self.assertTrue(comparisons["quality_tied_with_optimal_static_at_default_budget_all_cases"])
        self.assertFalse(comparisons["same_budget_joint_outperforms_optimal_static"])
        self.assertTrue(comparisons["active_selection_value_not_shown"])
        self.assertTrue(comparisons["accept_negative_result"])
        self.assertTrue(comparisons["stop_adding_complexity"])
        self.assertTrue(comparisons["does_not_establish_real_task_generalization"])
        self.assertTrue(comparisons["does_not_establish_eswa_core_contribution"])
        self.assertEqual(
            comparisons["only_decided_after_consumption_trace_by_case"],
            {
                "synthetic_preview_cache_download": False,
                "synthetic_two_download_files": True,
                "synthetic_joint_receiver_oracle": True,
            },
        )
        self.assertEqual(
            comparisons["shared_static_plan"]["1"]["selected_plan"],
            ["subsequent_reads"],
        )
        self.assertEqual(comparisons["shared_static_plan"]["1"]["real_tool_operations_total_sum"], 36)
        # Per-case joint at the default budget sums to 34, not 36.
        total = 0
        for case_id in CASE_IDS:
            total += _point(self.receipt["cases"][case_id]["curve"], "joint", 1)["cost"]["real_tool_operations_total"]
        self.assertEqual(total, 34)
        for case_id in CASE_IDS:
            rows = comparisons["per_case"][case_id]["by_budget"]
            for row in rows:
                self.assertTrue(row["quality_tie_with_optimal_static"])
                self.assertFalse(row["joint_strictly_better_quality_than_optimal_static"])
                self.assertTrue(row["quality_tie_with_full_trace_same_budget"])
                if row["budget"] >= 1:
                    self.assertTrue(row["quality_tie_with_full_trace_unlimited"])

    def test_quality_helpers_agree_with_locked_metrics(self):
        self.assertTrue(quality_equal(_perfect(), _perfect()))
        self.assertFalse(quality_strictly_better(_perfect(), _perfect()))
        self.assertTrue(quality_strictly_better(_perfect(), _defer_all()))

    def test_reports_record_the_three_conclusions_and_negative_result(self):
        paths = [JOINT_REPORT, CURVE_REPORT]
        if ARCHIVE_REPORT.exists():
            paths.append(ARCHIVE_REPORT)
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for sentence in CONCLUSIONS:
                self.assertIn(sentence, text, path)
        curve = CURVE_REPORT.read_text(encoding="utf-8")
        self.assertIn("没有优于逐案最优静态观察", curve)
        self.assertIn("应当接受负结果", curve)
        self.assertIn("不能证明真实任务泛化", curve)
        self.assertIn("也不能让 ESWA 核心贡献成立", curve)
        self.assertIn("健康示范采集", curve)
        self.assertIn("无预算限制", curve)
        self.assertIn("得到完整消费轨迹之后才选对", curve)
        # Original score tables in the joint report body are still present.
        body = JOINT_REPORT.read_text(encoding="utf-8")
        self.assertIn("| 联合学习 | 正确，位置 4 | `parsed_value`，唯一 | 0/2 | 2 | 0 | 6/6 | 0 | 0 | 1 |", body)

    def test_receipt_matches_live_run_except_cpu(self):
        live = _drop_cpu(self.receipt)
        stored = _drop_cpu(json.loads(RECEIPT.read_text(encoding="utf-8")))
        self.assertEqual(live, stored)

    def test_frozen_oracle_suite_still_passes(self):
        result = subprocess.run(
            [sys.executable, str(MAIN / "research/release_drift_20261126/receiver_learning/test_oracle.py")],
            cwd=str(MAIN),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
