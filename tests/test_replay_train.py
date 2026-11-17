"""CPU invariants for paired replay allocation, exposure, and whole episodes."""
from __future__ import annotations

import random
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fac_tinyagent.replay_train import (allocation_weights, assign_to_positions,
                                       common_replay_positions, fixed_new_order,
                                       make_replay_plan, validate_probe_separation,
                                       _prepare_rows, _probe)

try:
    import torch
except ImportError:
    torch = None


def pool(lengths):
    return {family: [{"family": family, "row_index": i,
                      "episode_id": "%s_%d" % (family, i),
                      "input_tokens": length, "supervised_tokens": length // 2}
                     for i, length in enumerate(values)]
            for family, values in lengths.items()}


class ReplayTests(unittest.TestCase):
    def test_probe_cannot_overlap_training_even_with_a_new_id(self):
        train = [{"episode_id": "train_1", "messages": [{"role": "user", "content": "one"}]}]
        validate_probe_separation(train, {"a": [
            {"episode_id": "probe_1", "messages": [{"role": "user", "content": "two"}]}]})
        for probe in (
                {"episode_id": "train_1", "messages": [{"role": "user", "content": "two"}]},
                {"episode_id": "probe_1", "messages": train[0]["messages"]}):
            with self.assertRaises(ValueError):
                validate_probe_separation(train, {"a": [probe]})

    def test_old_dialogue_over_max_length_is_excluded_whole(self):
        from tests.test_cpu import FakeTokenizer
        row = {"episode_id": "long_old", "messages": [
            {"role": "user", "content": "x" * 200},
            {"role": "assistant", "content": "answer"}]}
        prepared, excluded = _prepare_rows([row], FakeTokenizer(), 50, "a", complete_only=True)
        self.assertEqual(prepared, [])
        self.assertEqual(excluded[0]["episode_id"], "long_old")
        self.assertGreater(excluded[0]["input_tokens"], 50)

    def test_new_exposure_is_exact_and_independent_of_global_rng(self):
        first = fixed_new_order(80, 2, 20261108)
        random.seed(123)
        for _ in range(100):
            random.random()
        self.assertEqual(first, fixed_new_order(80, 2, 20261108))
        self.assertEqual(sorted(first[:80]), list(range(80)))
        self.assertEqual(sorted(first[80:]), list(range(80)))
        self.assertNotEqual(first[:80], first[80:])

    def test_positive_drop_and_uniform_floor(self):
        start = {"a": 0.8, "b": 0.5, "c": 0.0}
        mid = {"a": 0.4, "b": 0.7, "c": 0.0}
        weights = allocation_weights("adaptive", start, mid)
        self.assertAlmostEqual(weights["a"], 0.8 + 0.2 / 3)
        self.assertAlmostEqual(weights["b"], 0.2 / 3)
        self.assertAlmostEqual(weights["c"], 0.2 / 3)
        self.assertAlmostEqual(sum(weights.values()), 1)
        self.assertEqual(allocation_weights("none", start, mid), dict.fromkeys(start, 0.0))

    def test_zero_drop_exactly_matches_uniform(self):
        start = {"a": 0.2, "b": 0.4, "c": 0.7}
        mid = {"a": 0.2, "b": 0.5, "c": 0.8}
        uniform = allocation_weights("uniform", start, mid)
        adaptive = allocation_weights("adaptive", start, mid)
        self.assertEqual(uniform, adaptive)
        pools = pool({"a": [103, 111], "b": [89, 131], "c": [97, 107]})
        self.assertEqual(make_replay_plan(pools, uniform, 2000, 2),
                         make_replay_plan(pools, adaptive, 2000, 2))

    def test_complete_episodes_hard_budget_and_audit(self):
        pools = pool({"a": [101, 117], "b": [83, 129], "c": [107, 133]})
        weights = {"a": 1 / 3, "b": 1 / 3, "c": 1 / 3}
        plan = make_replay_plan(pools, weights, 7494, 123)
        self.assertLessEqual(plan["actual_input_tokens"], 7494)
        self.assertTrue(plan["within_one_percent_of_budget"])
        self.assertEqual(plan, make_replay_plan(pools, weights, 7494, 123))
        for item in plan["items"]:
            self.assertIn(item, pools[item["family"]])
        self.assertEqual(sum(plan["actual_tokens_by_family"].values()), plan["actual_input_tokens"])
        self.assertEqual(sum(x["supervised_tokens"] for x in plan["items"]),
                         plan["actual_supervised_tokens"])
        for family in weights:
            self.assertAlmostEqual(plan["quota_error_tokens_by_family"][family],
                                   plan["actual_tokens_by_family"][family] - 7494 / 3)

    def test_small_budget_never_truncates_and_unfillable_is_explicit(self):
        pools = pool({"a": [100], "b": [100], "c": [100]})
        weights = dict.fromkeys(pools, 1 / 3)
        tiny = make_replay_plan(pools, weights, 99, 3)
        self.assertEqual(tiny["items"], [])
        self.assertEqual(tiny["unused_input_tokens"], 99)
        self.assertFalse(tiny["within_one_percent_of_budget"])
        unfillable = make_replay_plan(pools, weights, 777, 3)
        self.assertEqual(unfillable["actual_input_tokens"], 700)
        self.assertEqual(unfillable["unused_input_tokens"], 77)
        self.assertFalse(unfillable["within_one_percent_of_budget"])

    def test_repeated_rows_allowed_without_manufacturing_examples(self):
        pools = pool({"a": [100]})
        plan = make_replay_plan(pools, {"a": 1.0}, 1000, 3)
        self.assertEqual(len(plan["items"]), 10)
        self.assertTrue(all(item == pools["a"][0] for item in plan["items"]))

    def test_packing_preserves_each_familys_coverage_floor(self):
        pools = pool({"a": [301, 317, 329], "b": [341, 359, 371],
                      "c": [401, 417, 433]})
        for target in pools:
            weights = allocation_weights("adaptive", dict.fromkeys(pools, 1.0),
                                         {f: 0.5 if f == target else 1.0 for f in pools})
            for seed in range(5):
                plan = make_replay_plan(pools, weights, 7494, seed)
                self.assertTrue(all(count >= 1 for count in plan["samples_by_family"].values()))
                self.assertLessEqual(plan["actual_input_tokens"], 7494)

    def test_both_arms_have_exact_same_insertion_times(self):
        positions = common_replay_positions(160, 80, 19, 16, 8)
        self.assertEqual(len(positions), 10)
        self.assertEqual(len(set(positions)), len(positions))
        self.assertTrue(all(80 < x < 160 for x in positions))
        for n in (19, 16):
            items = [{"i": i} for i in range(n)]
            assignments = assign_to_positions(items, positions)
            self.assertEqual(sorted(assignments), positions)
            self.assertTrue(all(assignments[p] for p in positions))
            self.assertEqual([x for p in positions for x in assignments[p]], items)

    def test_invalid_inputs_fail_before_sampling(self):
        for value in (-0.1, 1.1, float("nan")):
            with self.assertRaises(ValueError):
                allocation_weights("adaptive", {"a": value}, {"a": 0.0})
        with self.assertRaises(ValueError):
            allocation_weights("adaptive", {"a": 0.5}, {"b": 0.5})
        with self.assertRaises(ValueError):
            make_replay_plan({"a": []}, {"a": 1.0}, 100, 1)
        with self.assertRaises(ValueError):
            assign_to_positions([{"i": 0}], [])

    @unittest.skipIf(torch is None, "CPU torch is not installed in this interpreter")
    def test_probe_uses_joint_score_and_restores_training_and_rng(self):
        import numpy as np
        model = torch.nn.Linear(2, 1)
        model.config = SimpleNamespace(use_cache=False)
        model.train()
        tokenizer = SimpleNamespace(padding_side="right")
        random.seed(21)
        np.random.seed(21)
        torch.manual_seed(21)
        before_python = random.getstate()
        before_numpy = np.random.get_state()
        before_torch = torch.get_rng_state().clone()

        def fake_evaluate(*args):
            from fac_tinyagent.metrics import evaluate_stage_family
            self.assertFalse(model.training)
            tokenizer.padding_side = "left"
            model.config.use_cache = True
            random.random()
            np.random.random()
            torch.rand(3)
            rows = [{"tool_correct": i == 0, "arguments_correct": i == 0,
                     "execution_success": i == 0, "final_correct": i < 3,
                     "skill_labels": ["probe_skill"]} for i in range(4)]
            # Exercise the real report writer, including its required stage index.
            report = evaluate_stage_family(rows, args[4], "a", args[5])
            report["inference_usage"] = {
                "generation_batches": 2, "inference_calls": 4,
                "input_tokens": 20, "output_tokens": 10}
            return report

        with tempfile.TemporaryDirectory() as tmp, \
                patch("fac_tinyagent.sft.evaluate.evaluate_family", side_effect=fake_evaluate):
            report = _probe(model, tokenizer, {"a": [{}, {}]}, {}, {"name": "probe"},
                            Path(tmp), "unused", "unused")
        self.assertEqual(report["scores"], {"a": 0.25})
        self.assertEqual(report["score_metric"], "joint_success_rate")
        self.assertEqual(report["input_tokens"], 20)
        self.assertEqual(report["generated_tokens"], 10)
        self.assertEqual(report["generation_calls"], 2)
        self.assertEqual(report["logical_generation_requests"], 4)
        self.assertTrue(model.training)
        self.assertFalse(model.config.use_cache)
        self.assertEqual(tokenizer.padding_side, "right")
        self.assertEqual(random.getstate(), before_python)
        self.assertEqual(np.random.get_state()[0], before_numpy[0])
        self.assertTrue(np.array_equal(np.random.get_state()[1], before_numpy[1]))
        self.assertTrue(torch.equal(torch.get_rng_state(), before_torch))


if __name__ == "__main__":
    unittest.main()
