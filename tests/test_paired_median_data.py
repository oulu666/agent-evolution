"""CPU checks for paired diagnostic task identity, exclusion and executable gold."""
import json
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path
from statistics import median

from fac_tinyagent.config import PROJECT_ROOT
from fac_tinyagent.data.generate import build_system_prompt
from fac_tinyagent.metrics import answers_equal, observations_equal
from fac_tinyagent.paired_median_data import generate_paired_median
from fac_tinyagent.research_data import task_signature
from fac_tinyagent.tools import build_stats_registry
from fac_tinyagent.utils import read_jsonl, write_jsonl


class PairedMedianDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = generate_paired_median()

    def test_pairs_have_identical_numeric_tasks_and_distinct_wording(self):
        pairs = defaultdict(list)
        for row in self.rows:
            pairs[row["pair_id"]].append(row)
        self.assertEqual(len(self.rows), 192)
        self.assertEqual(len(pairs), 96)
        self.assertEqual(len({row["episode_id"] for row in self.rows}), 192)
        self.assertEqual(len({task_signature(row) for row in self.rows}), 192)
        numeric_instances = set()
        for index, pair in enumerate(pairs.values()):
            self.assertEqual(len(pair), 2)
            explicit, natural = pair
            self.assertEqual([row["wording"] for row in pair], ["explicit", "natural"])
            self.assertEqual(explicit["expected_arguments"], natural["expected_arguments"])
            self.assertEqual(explicit["expected_observation"], natural["expected_observation"])
            self.assertEqual(explicit["expected_final_answer"], natural["expected_final_answer"])
            self.assertIn("median", explicit["prompt"])
            self.assertNotIn("median", natural["prompt"])
            self.assertIn("ordering them from smallest to largest", natural["prompt"])
            values = explicit["expected_arguments"]["values"]
            self.assertEqual(len(values) % 2, 1)
            self.assertEqual(len(set(values)), len(values))
            self.assertTrue(all(10 <= value <= 100 for value in values))
            numeric_instances.add(tuple(sorted(values)))
            for row in pair:
                self.assertEqual(row["pair_index"], index)
                self.assertEqual(row["episode_id"].split("-")[2], row["template_id"])
                self.assertEqual(row["split"], "diagnostic")
                self.assertTrue(row["evaluation_only"] and row["diagnostic_only"])
                self.assertFalse(row["final_evaluation_allowed"])
        self.assertEqual(len(numeric_instances), 96)

    def test_executable_gold_and_evaluator_message_contract(self):
        registry = build_stats_registry()
        expected_system = build_system_prompt("python", registry.schemas())
        for row in self.rows:
            observation = registry.observation(row["expected_tool"], row["expected_arguments"])
            self.assertTrue(json.loads(observation)["ok"])
            self.assertTrue(observations_equal(observation, row["expected_observation"]))
            self.assertTrue(answers_equal(median(row["expected_arguments"]["values"]),
                                          row["expected_final_answer"]))
            self.assertEqual(row["system"], expected_system)
            messages = row["messages"]
            self.assertEqual([m["role"] for m in messages],
                             ["system", "user", "assistant", "user", "assistant"])
            self.assertEqual(messages[0]["content"], expected_system)
            self.assertEqual(messages[1]["content"], row["prompt"])
            self.assertEqual(json.loads(messages[2]["content"]), {
                "tool": row["expected_tool"], "arguments": row["expected_arguments"]})
            self.assertEqual(messages[3]["content"], "TOOL RESULT:\n" + observation)
            self.assertEqual(json.loads(messages[4]["content"])["answer"],
                             row["expected_final_answer"])

    def test_disjoint_from_existing_median_instances(self):
        generated = {tuple(sorted(row["expected_arguments"]["values"])) for row in self.rows}
        existing = set()
        for root_name in ("data_phase2", "data_replay_study"):
            for path in (PROJECT_ROOT / root_name / "python").glob("*.jsonl"):
                for row in read_jsonl(path):
                    if row["expected_tool"] == "stats_median":
                        existing.add(tuple(sorted(row["expected_arguments"]["values"])))
        self.assertTrue(existing)
        self.assertFalse(generated & existing)

    def test_exclusion_skips_a_matching_instance_even_when_reordered(self):
        original = generate_paired_median(n_pairs=2, exclusion_roots=[])
        first_values = original[0]["expected_arguments"]["values"]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_jsonl(root / "python" / "train.jsonl", [{
                "expected_tool": "stats_median", "expected_arguments": {
                    "values": list(reversed(first_values))}}])
            fresh = generate_paired_median(n_pairs=1, exclusion_roots=[root])
        self.assertNotEqual(sorted(first_values), sorted(fresh[0]["expected_arguments"]["values"]))
        self.assertEqual(fresh[0]["expected_arguments"], original[2]["expected_arguments"])

    def test_reproducible_prefix_and_input_validation(self):
        self.assertEqual(self.rows, generate_paired_median())
        self.assertEqual(self.rows[:48], generate_paired_median(n_pairs=24))
        self.assertNotEqual(self.rows[0]["expected_arguments"],
                            generate_paired_median(n_pairs=1, seed=20261111)[0]["expected_arguments"])
        for count in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                generate_paired_median(n_pairs=count)
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileNotFoundError):
                generate_paired_median(exclusion_roots=[Path(temp)])


if __name__ == "__main__":
    unittest.main()
