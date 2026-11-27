"""Tests for joint Receiver–Oracle learning and the four-system comparison."""
import hashlib
import inspect
import json
import subprocess
import sys
import unittest
from pathlib import Path

from baselines import lookup_positions
from joint import (
    RANK_DETERMINED,
    RANK_RECEIVER_OPEN,
    RANK_RELATION_OPEN,
    choose_observation,
    decide_row,
    decision_rank,
    initial_H,
    learn_joint,
    refine_by_consumer_slot,
)
from joint_oracle import RELATIONS, fixed_oracle
from joint_score import independent_gain_rows, score_case
from joint_systems import autoloc_fixed_oracle, lookup_fixed_oracle, lookup_synthesized_oracle, run_systems
from joint_task import build_receipt, write_receipt
from joint_world import CASES, EXTRA_BUDGET, HealthyObserver, collect_case
from learn import equivalent, select
from oracle import synthesize_oracle

HERE = Path(__file__).resolve().parent
RECEIPT = HERE / "joint-receipt.json"
def _main_checkout():
    here = Path(__file__).resolve().parent
    repo = here.parents[2]
    if (repo / "research/release_drift_20261126/receiver_learning/test_oracle.py").exists():
        return repo
    return Path("/workspace/agent-evolution-main-88ca0d20")


MAIN = _main_checkout()
VOLATILE = "local_cpu_seconds"


class EmptyObserver:
    def __init__(self):
        self.calls = 0
        self.log = []

    def subsequent_reads(self, input_name):
        self.calls += 1
        self.log.append({"name": "subsequent_reads"})
        return []


class JointLearningTests(unittest.TestCase):
    def _case(self, case_id):
        case = next(item for item in CASES if item["id"] == case_id)
        return collect_case(case)

    def test_closed_relation_set_unchanged(self):
        self.assertEqual(RELATIONS, ("byte", "full_string", "parsed_value"))

    def test_joint_requirement_underspecified(self):
        public, hidden = self._case("synthetic_joint_receiver_oracle")
        sources = [demo["expected"] for demo in public["demos"]]
        oracle = synthesize_oracle(public["requirement"], sources)
        self.assertIsNone(oracle["relation"])
        self.assertEqual(oracle["abstain"], "underspecified_relation")
        self.assertEqual(fixed_oracle(public["requirement"], public["action"])["relation"], "full_string")
        self.assertEqual(hidden["truth_relation"], "parsed_value")

    def test_initial_H_contains_wrong_and_true_pairs(self):
        public, hidden = self._case("synthetic_joint_receiver_oracle")
        pairs, _ = initial_H(public["demos"], public["slots"], public["requirement"])
        self.assertIn((3, "byte"), pairs)
        self.assertIn((3, "full_string"), pairs)
        self.assertIn((3, "parsed_value"), pairs)
        self.assertIn((4, "parsed_value"), pairs)
        self.assertNotIn((4, "full_string"), pairs)
        self.assertNotIn((4, "byte"), pairs)
        self.assertNotIn((1, "parsed_value"), pairs)  # preview excluded by delivery type
        self.assertEqual(decision_rank(pairs), RANK_RECEIVER_OPEN)

    def test_consumer_evidence_leaves_only_true_pair(self):
        public, hidden = self._case("synthetic_joint_receiver_oracle")
        pairs, _ = initial_H(public["demos"], public["slots"], public["requirement"])
        residual = refine_by_consumer_slot(pairs, hidden["truth_receiver"])
        self.assertEqual(residual, [(4, "parsed_value")])
        self.assertEqual(decision_rank(residual), RANK_DETERMINED)

    def test_observation_value_is_about_release_decision(self):
        public, hidden = self._case("synthetic_joint_receiver_oracle")
        pairs, _ = initial_H(public["demos"], public["slots"], public["requirement"])
        choice = choose_observation(pairs, public["demos"])
        self.assertEqual(choice["action"], "subsequent_reads")
        by_kind = {item["kind"]: item for item in choice["scores"]}
        self.assertTrue(by_kind["subsequent_reads"]["can_improve_decision"])
        self.assertTrue(by_kind["contrast_canaries"]["can_improve_decision"])
        self.assertFalse(by_kind["reread_known_slot"]["can_improve_decision"])
        # Canaries change more outputs but do not outrank a consumer-read
        # that induces the same partition of H.
        self.assertEqual(
            by_kind["subsequent_reads"]["mean_outcome_rank"],
            by_kind["contrast_canaries"]["mean_outcome_rank"],
        )
        self.assertEqual(choice["chosen"]["kind"], "subsequent_reads")

    def test_learn_joint_unique_on_synergy_case(self):
        public, hidden = self._case("synthetic_joint_receiver_oracle")
        observer = HealthyObserver(hidden["world"], public["demos"], budget=EXTRA_BUDGET)
        learned = learn_joint(
            public["demos"], public["slots"], public["requirement"], observer, budget=EXTRA_BUDGET)
        self.assertIsNone(learned["abstain"])
        self.assertEqual(learned["pairs"], [(4, "parsed_value")])
        self.assertEqual(learned["extra_observations"], 1)
        self.assertNotIn("truth_receiver", inspect.signature(learn_joint).parameters)
        self.assertNotIn("truth_relation", inspect.signature(learn_joint).parameters)

    def test_empty_consumer_trace_abstains(self):
        public, hidden = self._case("synthetic_joint_receiver_oracle")
        learned = learn_joint(
            public["demos"], public["slots"], public["requirement"], EmptyObserver(), budget=EXTRA_BUDGET)
        self.assertEqual(learned["abstain"], "no_subsequent_read")
        self.assertEqual(learned["pairs"], [])

    def test_split_systems_fail_synergy_case(self):
        public, hidden = self._case("synthetic_joint_receiver_oracle")
        one = lookup_fixed_oracle(public)
        two = autoloc_fixed_oracle(public, hidden)
        three = lookup_synthesized_oracle(public)
        self.assertIsNotNone(one["abstain"])
        self.assertEqual(two["positions"], [3])
        self.assertEqual(two["relation"], "full_string")
        self.assertIsNone(two["abstain"])
        self.assertIn("lookup_not_unique", three["abstain"])
        self.assertIn("underspecified_relation", three["abstain"])
        systems = run_systems(public, hidden)
        scored = score_case(public, hidden, systems)
        metrics = scored["metrics"]
        self.assertEqual(metrics["lookup_fixed_oracle"]["correct_block"], 0)
        self.assertEqual(metrics["autoloc_fixed_oracle"]["false_release"], 2)
        self.assertEqual(metrics["lookup_synthesized_oracle"]["correct_block"], 0)
        self.assertEqual(metrics["joint"]["correct_block"], 2)
        self.assertEqual(metrics["joint"]["false_release"], 0)
        self.assertEqual(metrics["joint"]["retention"], 6)
        self.assertEqual(metrics["joint"]["false_block"], 0)
        self.assertEqual(metrics["strong_control"]["correct_block"], 2)
        gain = scored["independent_gain_rows"]
        self.assertEqual(len(gain["vs_three_split_systems"]), 2)
        self.assertEqual(gain["vs_strong_control"], [])

    def test_preview_case_degenerates_to_split_systems(self):
        public, hidden = self._case("synthetic_preview_cache_download")
        systems = run_systems(public, hidden)
        scored = score_case(public, hidden, systems)
        for name in ("lookup_fixed_oracle", "autoloc_fixed_oracle", "lookup_synthesized_oracle", "joint"):
            self.assertEqual(scored["metrics"][name]["correct_block"], 2)
            self.assertEqual(scored["metrics"][name]["false_release"], 0)
            self.assertEqual(scored["metrics"][name]["retention"], 6)
            self.assertEqual(scored["accuracy"][name]["receiver_correct"], True)
        self.assertEqual(systems["joint"]["extra_observations"], 0)
        self.assertEqual(scored["independent_gain_rows"]["vs_three_split_systems"], [])

    def test_two_file_case_joint_ties_autoloc_not_independent(self):
        public, hidden = self._case("synthetic_two_download_files")
        systems = run_systems(public, hidden)
        scored = score_case(public, hidden, systems)
        self.assertEqual(scored["metrics"]["autoloc_fixed_oracle"]["correct_block"], 2)
        self.assertEqual(scored["metrics"]["joint"]["correct_block"], 2)
        self.assertEqual(scored["metrics"]["lookup_fixed_oracle"]["correct_block"], 0)
        self.assertEqual(scored["metrics"]["lookup_synthesized_oracle"]["correct_block"], 0)
        # Auto-loc + fixed oracle already blocks, so this is not joint synergy.
        self.assertEqual(scored["independent_gain_rows"]["vs_three_split_systems"], [])
        self.assertEqual(systems["joint"]["extra_observations"], 1)
        self.assertEqual(systems["joint"]["positions"], [4])

    def test_decide_row_defers_when_hypotheses_disagree(self):
        values = ["title", "preview", "cache", '{"port":99}', '{\n  "port": 0\n}']
        reference = '{"port":99}'
        pairs = [(3, "full_string"), (4, "parsed_value")]
        self.assertIsNone(decide_row(values, reference, pairs))
        self.assertTrue(decide_row(["a", "b", "c", reference, "{\n  \"port\": 99\n}"], reference, pairs))

    def test_select_still_ambiguous_under_truth_relation(self):
        public, hidden = self._case("synthetic_joint_receiver_oracle")
        candidates = select(public["demos"], hidden["truth_relation"], True)
        self.assertGreater(len(candidates), 1)
        self.assertIn(hidden["truth_receiver"], candidates)

    def test_prebound_lookup_unbound(self):
        for case in CASES:
            public, _ = collect_case(case)
            self.assertEqual(lookup_positions(public["action"]), [])

    def test_pretty_and_compact_relations(self):
        compact = '{"port":41}'
        pretty = '{\n  "port": 41\n}'
        cache = compact + "\n"
        self.assertTrue(equivalent(pretty, compact, "parsed_value"))
        self.assertFalse(equivalent(pretty, compact, "full_string"))
        self.assertFalse(equivalent(pretty, compact, "byte"))
        self.assertTrue(equivalent(cache, compact, "full_string"))
        self.assertTrue(equivalent(cache, compact, "parsed_value"))
        self.assertFalse(equivalent(cache, compact, "byte"))

    def test_algorithms_do_not_take_hidden_labels(self):
        from joint_systems import joint_system, strong_control, autoloc_fixed_oracle as auto
        for fn in (learn_joint, joint_system, strong_control, auto, lookup_fixed_oracle, lookup_synthesized_oracle):
            params = inspect.signature(fn).parameters
            self.assertNotIn("truth_receiver", params, fn)
            self.assertNotIn("truth_relation", params, fn)


class ReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = build_receipt()
        cls.path, cls.digest = write_receipt(cls.receipt, RECEIPT)

    def test_receipt_written(self):
        self.assertTrue(RECEIPT.exists())
        loaded = json.loads(RECEIPT.read_text())
        self.assertEqual(loaded["base_head"], "88ca0d2090794b363c8db82a4106f2c952b69aec")
        self.assertTrue(loaded["synthetic_only"])
        self.assertTrue(loaded["core_algorithm_not_established"])
        self.assertTrue(loaded["auto_oracle_generation_not_a_novelty_claim"])
        self.assertEqual(loaded["model_calls"], 0)
        self.assertTrue(loaded["public_transfer"]["searched"])
        self.assertFalse(loaded["public_transfer"]["qualified_case_found"])

    def test_receipt_matches_live_run_except_cpu(self):
        live = json.loads(json.dumps(self.receipt))
        stored = json.loads(RECEIPT.read_text())
        live.pop(VOLATILE, None)
        stored.pop(VOLATILE, None)
        self.assertEqual(live, stored)

    def test_independent_gain_only_on_joint_case(self):
        gain = self.receipt["independent_gain"]
        self.assertEqual(gain["by_case"]["synthetic_preview_cache_download"]["vs_three_split_systems"], [])
        self.assertEqual(gain["by_case"]["synthetic_two_download_files"]["vs_three_split_systems"], [])
        self.assertEqual(len(gain["by_case"]["synthetic_joint_receiver_oracle"]["vs_three_split_systems"]), 2)
        self.assertFalse(gain["any_independent_gain_vs_strong_control"])
        self.assertTrue(gain["any_independent_gain_vs_split"])

    def test_digest_stable_without_cpu(self):
        stored = json.loads(RECEIPT.read_text())
        stored.pop(VOLATILE, None)
        digest = hashlib.sha256((json.dumps(stored, ensure_ascii=False, indent=1) + "\n").encode()).hexdigest()
        self.assertEqual(len(digest), 64)


class FrozenTests(unittest.TestCase):
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
