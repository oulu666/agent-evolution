"""CPU-only tests: tools, data generation, masking and metrics."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from fac_tinyagent.config import load_config
from fac_tinyagent.data.generate import generate_all
from fac_tinyagent.metrics import (answers_equal, average_forgetting,
                                   forgetting_rows)
from fac_tinyagent.sft.dataset import assistant_spans, tokenize_episode
from fac_tinyagent.tools import create_fixture
from fac_tinyagent.tools.db_tools import build_db_registry
from fac_tinyagent.tools.file_tools import (FileSandbox, build_file_registry,
                                            materialize_sandbox)
from fac_tinyagent.tools.stats_tools import build_stats_registry


class FakeTokenizer:
    chat_template = None
    pad_token_id = 0
    eos_token_id = 1001

    def __init__(self):
        self.special = {"<|im_start|>": 1000, "<|im_end|>": 1001}

    def _tokenize(self, text):
        ids = []
        index = 0
        while index < len(text):
            for token, value in self.special.items():
                if text.startswith(token, index):
                    ids.append(value)
                    index += len(token)
                    break
            else:
                ids.append(3000 + ord(text[index]))
                index += 1
        return ids

    def encode(self, text, add_special_tokens=False):
        return self._tokenize(text)

    def __call__(self, text, add_special_tokens=False, truncation=True,
                 max_length=1024, return_attention_mask=False):
        return {"input_ids": self._tokenize(text)[:max_length]}

    def convert_tokens_to_ids(self, token):
        return self.special.get(token, 0)


class ToolTests(unittest.TestCase):
    def test_file_sandbox(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = build_file_registry(materialize_sandbox(
                {"a.txt": "alpha\nbeta alpha\n", "sub/b.md": "x\n"}, tmp))
            self.assertTrue(registry.execute("file_read", {"path": "a.txt"})["ok"])
            self.assertFalse(registry.execute("file_read", {"path": "../x"})["ok"])
            result = registry.execute("file_search",
                                      {"path": "a.txt", "pattern": "alpha"})
            self.assertEqual(len(result["result"]), 2)
            self.assertTrue(registry.execute("file_write",
                                             {"path": "sub/c.txt", "content": "ok"})["ok"])

    def test_database_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = create_fixture(str(Path(tmp) / "test.db"), force=True)
            registry = build_db_registry(str(db_path))
            count = registry.execute("db_query",
                                     {"sql": "SELECT COUNT(*) FROM employees"})
            self.assertEqual(count["result"]["rows"][0][0], 12)
            self.assertFalse(registry.execute("db_query",
                                              {"sql": "DELETE FROM employees"})["ok"])
            self.assertFalse(registry.execute("db_query",
                                              {"sql": "SELECT 1; SELECT 2"})["ok"])
            tables = registry.execute("db_list_tables", {})["result"]
            self.assertEqual(tables, ["employees", "products", "sales"])

    def test_stats(self):
        registry = build_stats_registry()
        self.assertEqual(registry.execute("stats_mean", {"values": [1, 2, 3]})["result"], 2.0)
        self.assertEqual(registry.execute("stats_median", {"values": [1, 2, 3, 4]})["result"], 2.5)
        self.assertEqual(registry.execute("stats_percentile",
                                          {"values": [1, 2, 3, 4],
                                           "percentile": 25})["result"], 1.75)
        self.assertFalse(registry.execute("stats_correlation",
                                          {"xs": [1, 1, 1],
                                           "ys": [1, 2, 3]})["ok"])


class DataTests(unittest.TestCase):
    def test_generate_and_verify(self):
        config = copy.deepcopy(load_config())
        with tempfile.TemporaryDirectory() as tmp:
            config["data_root"] = tmp
            config["data"]["train_per_family"] = 8
            config["data"]["val_per_family"] = 2
            config["data"]["test_per_family"] = 6
            manifest = generate_all(config, verify=True)
            for family, item in manifest["families"].items():
                self.assertEqual(item["counts"], {"train": 8, "val": 2, "test": 6})
                train_templates = set(item["templates"]["train"])
                test_templates = set(item["templates"]["test"])
                self.assertFalse(train_templates & test_templates)
                rows = [json.loads(line) for line in
                        (Path(tmp) / family / "test.jsonl").read_text(
                            encoding="utf-8").splitlines() if line]
                for row in rows:
                    self.assertEqual([message["role"] for message in row["messages"]],
                                     ["system", "user", "assistant", "user", "assistant"])

    def test_assistant_masking(self):
        tokenizer = FakeTokenizer()
        config = copy.deepcopy(load_config())
        with tempfile.TemporaryDirectory() as tmp:
            config["data_root"] = tmp
            config["data"]["train_per_family"] = 8
            config["data"]["val_per_family"] = 2
            config["data"]["test_per_family"] = 6
            generate_all(config, verify=False)
            row = json.loads((Path(tmp) / "file" / "train.jsonl")
                             .read_text(encoding="utf-8").splitlines()[0])
        encoded = tokenize_episode(row, tokenizer, 5000)
        spans = assistant_spans(encoded["input_ids"], tokenizer)
        self.assertEqual(len(spans), 2)
        labeled = [index for index, value in enumerate(encoded["labels"])
                   if value != -100]
        self.assertEqual(len(labeled), sum(end - start for start, end in spans))
        user_header = tokenizer.encode("<|im_start|>user\n", add_special_tokens=False)
        for index in range(len(encoded["input_ids"]) - len(user_header) + 1):
            if encoded["input_ids"][index:index + len(user_header)] == user_header:
                self.assertEqual(encoded["labels"][index + len(user_header)], -100)


class MetricTests(unittest.TestCase):
    def test_answers_equal(self):
        self.assertTrue(answers_equal(1.0, 1.0000001))
        self.assertTrue(answers_equal({"a": [1, 2]}, {"a": [1, 2]}))
        self.assertFalse(answers_equal(1, 2))

    def test_forgetting_formula(self):
        evaluations = [
            {"stage_index": 1, "stage_name": "s1", "family": "file",
             "metrics": {"n": 30, "tool_selection_accuracy": 0.8,
                         "argument_accuracy": 0.8, "execution_success_rate": 0.8,
                         "final_task_success_rate": 0.8},
             "skill_metrics": {}},
            {"stage_index": 2, "stage_name": "s2", "family": "file",
             "metrics": {"n": 30, "tool_selection_accuracy": 0.5,
                         "argument_accuracy": 0.5, "execution_success_rate": 0.5,
                         "final_task_success_rate": 0.5},
             "skill_metrics": {}},
        ]
        family_rows, _ = forgetting_rows(evaluations, {"file": 1})
        first = [row for row in family_rows
                 if row["metric"] == "final_task_success_rate"][0]
        self.assertEqual(first["forgetting"], 0.3)
        self.assertEqual(first["peak"], 0.8)
        self.assertEqual(first["n"], 30)

    def test_forgetting_peak_is_prior_max(self):
        evaluations = [
            {"stage_index": 1, "stage_name": "s1", "family": "file",
             "metrics": {"n": 10, "tool_selection_accuracy": 0.5,
                         "argument_accuracy": 0.5, "execution_success_rate": 0.5,
                         "final_task_success_rate": 0.5},
             "skill_metrics": {}},
            {"stage_index": 2, "stage_name": "s2", "family": "file",
             "metrics": {"n": 10, "tool_selection_accuracy": 0.7,
                         "argument_accuracy": 0.7, "execution_success_rate": 0.7,
                         "final_task_success_rate": 0.7},
             "skill_metrics": {}},
            {"stage_index": 3, "stage_name": "s3", "family": "file",
             "metrics": {"n": 10, "tool_selection_accuracy": 0.6,
                         "argument_accuracy": 0.6, "execution_success_rate": 0.6,
                         "final_task_success_rate": 0.6},
             "skill_metrics": {}},
        ]
        family_rows, _ = forgetting_rows(evaluations, {"file": 1})
        final_rows = [row for row in family_rows
                      if row["metric"] == "final_task_success_rate"]
        self.assertEqual(final_rows[0]["peak"], 0.5)
        self.assertEqual(final_rows[0]["forgetting"], 0.0)
        self.assertEqual(final_rows[1]["peak"], 0.7)
        self.assertEqual(final_rows[1]["forgetting"], 0.1)

    def test_weighted_forgetting(self):
        rows = [
            {"stage_index": 3, "metric": "final_task_success_rate",
             "forgetting": 1.0, "n": 1},
            {"stage_index": 3, "metric": "final_task_success_rate",
             "forgetting": 0.0, "n": 9},
        ]
        self.assertEqual(
            average_forgetting(rows)["3"]["final_task_success_rate"], 0.5)
        self.assertEqual(
            average_forgetting(rows, weighted=True)["3"]["final_task_success_rate"],
            0.1)


if __name__ == "__main__":
    unittest.main()
