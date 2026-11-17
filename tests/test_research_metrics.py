"""CPU-only research metrics, accounting, batching and prompt-isolation tests."""
from __future__ import annotations

import copy
import itertools
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fac_tinyagent.metrics import (
    METRIC_KEYS, joint_success, summarize_result_file, summarize_results,
    summarize_skills, summarize_usage,
)
from fac_tinyagent.phase2_report import write_phase2_report
from fac_tinyagent.sft import evaluate
from fac_tinyagent.utils import canonical_json, read_jsonl, write_jsonl


def result_row(tool=True, arguments=True, execution=True, final=True):
    return {
        "tool_family": "python", "tool_correct": tool,
        "arguments_correct": arguments, "execution_success": execution,
        "final_correct": final, "skill_labels": ["numeric"],
        "tool_call_raw": "{}", "answer_raw": "{}",
    }


class ResearchMetricTests(unittest.TestCase):
    def test_joint_requires_every_component_and_ignores_stale_derived_field(self):
        rows = []
        for flags in itertools.product((False, True), repeat=4):
            row = result_row(*flags)
            row["joint_success"] = True  # Re-derive archived metrics from their facts.
            self.assertEqual(joint_success(row), all(flags))
            rows.append(row)
        metrics = summarize_results(rows)
        self.assertEqual(metrics["joint_success_rate"], 1 / 16)
        for metric in METRIC_KEYS:
            self.assertEqual(metrics[metric], 0.5)

    def test_conditional_arguments_uses_only_correct_tools(self):
        rows = [result_row(True, True), result_row(True, False),
                result_row(False, True), result_row(False, True)]
        metrics = summarize_results(rows)
        self.assertEqual(metrics["argument_accuracy"], 0.75)
        self.assertEqual(metrics["conditional_argument_accuracy"], 0.5)
        self.assertEqual(metrics["conditional_argument_denominator"], 2)
        self.assertEqual(metrics["conditional_argument_numerator"], 1)
        self.assertEqual(summarize_skills(rows)["numeric"], metrics)

    def test_conditional_zero_denominator_is_null(self):
        for rows in ([], [result_row(False, True)]):
            metrics = summarize_results(rows)
            self.assertIsNone(metrics["conditional_argument_accuracy"])
            self.assertEqual(metrics["conditional_argument_denominator"], 0)
            self.assertEqual(metrics["conditional_argument_numerator"], 0)
        self.assertEqual(summarize_results([])["final_task_success_rate"], 0.0)

    def test_legacy_usage_is_unknown_except_recoverable_call_count(self):
        usage = summarize_usage([result_row(), result_row()])
        self.assertEqual(usage["inference_calls"], 4)
        self.assertEqual(usage["inferred_inference_call_episodes"], 2)
        self.assertIsNone(usage["input_tokens"])
        self.assertIsNone(usage["output_tokens"])
        self.assertIsNone(usage["generation_seconds"])
        self.assertIsNone(usage["generation_batches"])
        self.assertEqual(usage["usage_coverage"]["input_tokens"], 0)

    def test_partial_usage_does_not_underreport_as_complete(self):
        measured = result_row()
        measured.update(inference_calls=2, input_tokens=10, output_tokens=5,
                        total_tokens=15, generation_seconds=0.25)
        usage = summarize_usage([measured, result_row()])
        self.assertEqual(usage["inference_calls"], 4)
        self.assertIsNone(usage["total_tokens"])
        self.assertEqual(usage["recorded_totals"]["total_tokens"], 15)
        self.assertEqual(usage["usage_coverage"]["total_tokens"], 1)

    def test_offline_summary_preserves_source_and_groups_families(self):
        rows = [result_row(), result_row(False, True)]
        rows[1]["tool_family"] = "file"
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "results.jsonl"
            write_jsonl(source, rows)
            before = source.read_bytes()
            report = summarize_result_file(source)
            self.assertEqual(source.read_bytes(), before)
            self.assertEqual(list(Path(tmp).iterdir()), [source])
            self.assertEqual(report["metrics"]["joint_success_rate"], 0.5)
            self.assertEqual(report["by_family"]["python"]["metrics"]["joint_success_rate"], 1)
            self.assertIsNone(report["by_family"]["file"]["metrics"]["conditional_argument_accuracy"])
        with self.assertRaises(FileNotFoundError):
            summarize_result_file(source)


class CpuTensor:
    """Minimal tensor protocol; .to('cuda') intentionally performs no GPU work."""

    def __init__(self, values):
        self.values = values

    @property
    def shape(self):
        if self.values and isinstance(self.values[0], list):
            return len(self.values), len(self.values[0])
        return (len(self.values),)

    def __getitem__(self, index):
        return CpuTensor(self.values[index])

    def to(self, device):
        if device != "cuda":
            raise AssertionError(device)
        return self

    def tolist(self):
        return self.values

    def sum(self):
        return CpuTensor(sum(self.values))

    def item(self):
        return self.values


class GenerationTokenizer:
    chat_template = None
    padding_side = "right"
    pad_token_id = 1
    eos_token_id = 2

    def __init__(self):
        self.encoded_lengths = []
        self.seen_padding_sides = []

    def convert_tokens_to_ids(self, token):
        return 3 if token == "<|im_end|>" else -1

    def __call__(self, text, return_tensors, add_special_tokens, padding=False):
        texts = text if isinstance(text, list) else [text]
        values = [[100 + ord(character) for character in item] for item in texts]
        width = max(len(item) for item in values)
        self.encoded_lengths = [len(item) for item in values]
        self.seen_padding_sides.append(self.padding_side)
        masks = [[0] * (width - len(item)) + [1] * len(item) for item in values]
        values = [[self.pad_token_id] * (width - len(item)) + item for item in values]
        return {"input_ids": CpuTensor(values), "attention_mask": CpuTensor(masks)}

    def decode(self, values, skip_special_tokens):
        values = values.tolist() if hasattr(values, "tolist") else values
        return "".join(chr(value - 100) for value in values if value >= 100)


class GenerationModel:
    def __init__(self, suffixes):
        self.suffixes = suffixes
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        prompts = kwargs["input_ids"].tolist()
        return CpuTensor([prompt + suffix for prompt, suffix in zip(prompts, self.suffixes)])


class GenerationUsageTests(unittest.TestCase):
    def test_single_generation_keeps_decoding_options_and_text_api(self):
        tokenizer = GenerationTokenizer()
        model = GenerationModel([[100 + ord("x"), tokenizer.eos_token_id]])
        messages = [{"role": "user", "content": "Question"}]
        text, usage = evaluate.generate_with_usage(model, tokenizer, messages, 7)
        self.assertEqual(text, "x")
        self.assertEqual(usage["input_tokens"], tokenizer.encoded_lengths[0])
        self.assertEqual(usage["output_tokens"], 2)
        self.assertEqual(usage["inference_calls"], 1)
        self.assertEqual(usage["total_tokens"], usage["input_tokens"] + 2)
        self.assertGreaterEqual(usage["generation_seconds"], 0)
        kwargs = model.calls[0]
        self.assertEqual(set(kwargs), {"input_ids", "attention_mask", "max_new_tokens",
                                      "do_sample", "pad_token_id", "eos_token_id"})
        self.assertEqual(kwargs["max_new_tokens"], 7)
        self.assertFalse(kwargs["do_sample"])
        self.assertEqual(kwargs["eos_token_id"], [2, 3])
        self.assertEqual(evaluate.generate_text(model, tokenizer, messages, 7), "x")

    def test_batch_counts_exclude_left_padding_and_post_eos_padding(self):
        tokenizer = GenerationTokenizer()
        model = GenerationModel([[220, 2, 1, 1], [221, 222, 223, 3],
                                 [220, 221, 222, 223]])
        conversations = [[{"role": "user", "content": text}]
                         for text in ("short", "longer question", "third")]
        results = evaluate.generate_batch_with_usage(model, tokenizer, conversations, 4)
        self.assertEqual([text for text, _ in results], ["x", "yz{", "xyz{"])
        self.assertEqual([usage["output_tokens"] for _, usage in results], [2, 4, 4])
        self.assertEqual([usage["input_tokens"] for _, usage in results], tokenizer.encoded_lengths)
        self.assertEqual(tokenizer.seen_padding_sides, ["left"])
        self.assertEqual(tokenizer.padding_side, "right")
        self.assertTrue(model.calls[0]["use_cache"])
        self.assertFalse(model.calls[0]["do_sample"])
        self.assertAlmostEqual(sum(usage["generation_seconds"] for _, usage in results),
                               results[0][1]["batch_generation_seconds"])
        self.assertEqual(evaluate.generate_batch_with_usage(model, tokenizer, [], 4), [])


class EvaluationIsolationTests(unittest.TestCase):
    def test_single_and_batch_use_real_observations_and_charge_both_generations(self):
        episodes = []
        for kind in ("correct", "wrong", "invalid"):
            episodes.append({
                "episode_id": kind, "tool_family": "python", "split": "test",
                "skill_labels": ["numeric"],
                "messages": [{"role": "system", "content": "Call a statistics tool."},
                             {"role": "user", "content": kind},
                             {"role": "assistant", "content": "GOLD_ASSISTANT"},
                             {"role": "user", "content": "GOLD_OBSERVATION"},
                             {"role": "assistant", "content": "GOLD_FINAL"}],
                "expected_tool": "stats_mean", "expected_arguments": {"values": [1, 3]},
                "expected_observation": canonical_json({"ok": True, "result": 2.0}),
                "expected_final_answer": 2,
            })
        for batch_size in (1, 2):
            with self.subTest(batch_size=batch_size), tempfile.TemporaryDirectory() as tmp:
                prompts = []

                def generation(model, tokenizer, messages, max_new_tokens):
                    prompts.append(copy.deepcopy(messages))
                    self.assertNotIn("GOLD_", json.dumps(messages))
                    if len(messages) == 2:
                        kind = messages[1]["content"]
                        text = ("malformed" if kind == "invalid" else canonical_json({
                            "tool": "stats_mean",
                            "arguments": {"values": [3, 5] if kind == "wrong" else [1, 3]},
                        }))
                    else:
                        kind = messages[1]["content"]
                        observation = messages[-1]["content"].split("TOOL RESULT:\n", 1)[1]
                        if kind == "wrong":
                            self.assertEqual(json.loads(observation)["result"], 4.0)
                            self.assertNotEqual(observation, episodes[1]["expected_observation"])
                        elif kind == "invalid":
                            self.assertFalse(json.loads(observation)["ok"])
                        text = '{"answer":2}'
                    return text, {"inference_calls": 1, "input_tokens": 10,
                                  "output_tokens": 3, "total_tokens": 13,
                                  "generation_seconds": 0.25, "batch_size": 1}

                def generation_batch(model, tokenizer, conversations, max_new_tokens):
                    return [generation(model, tokenizer, messages, max_new_tokens)
                            for messages in conversations]

                config = {"evaluation": {"batch_size": batch_size,
                                         "max_new_tokens_tool": 128,
                                         "max_new_tokens_answer": 64}}
                with patch.object(evaluate, "generate_with_usage", side_effect=generation), \
                        patch.object(evaluate, "generate_batch_with_usage", side_effect=generation_batch), \
                        patch.object(evaluate, "gpu_reset_peak"), \
                        patch.object(evaluate, "gpu_peak_gb", return_value=0):
                    report = evaluate.evaluate_family(
                        None, None, episodes, config, {"index": 1, "name": "test_stage"},
                        Path(tmp), "unused.db", "unused.json")
                rows = read_jsonl(Path(tmp) / "results.jsonl")
                self.assertEqual(len(prompts), 6)
                self.assertEqual([row["joint_success"] for row in rows], [True, False, False])
                self.assertEqual(report["metrics"]["final_task_success_rate"], 1)
                self.assertEqual(report["metrics"]["joint_success_rate"], 0.333333)
                self.assertEqual(report["metrics"]["conditional_argument_accuracy"], 0.5)
                usage = report["inference_usage"]
                self.assertEqual(usage["inference_calls"], 6)
                self.assertEqual(usage["generation_batches"], 6 if batch_size == 1 else 4)
                self.assertEqual(usage["input_tokens"], 60)
                self.assertEqual(usage["output_tokens"], 18)
                self.assertEqual(usage["total_tokens"], 78)
                self.assertEqual(usage["generation_seconds"], 1.5)
                self.assertEqual(summarize_result_file(Path(tmp) / "results.jsonl")["metrics"],
                                 report["metrics"])


class ReportLabelTests(unittest.TestCase):
    def test_eligible_runs_label_does_not_claim_positive_forgetting(self):
        summary = {
            "config": {"stages": [{}, {"family": "file"}, {"family": "python"}]},
            "capability_matrix": {"families": ["file"], "pivot": [
                {"stage_index": index, "stage_name": "s%d" % index, "file": 1.0}
                for index in (0, 1, 2)]},
            "forgetting": {"family_rows": [{
                "family": "file", "metric": "final_task_success_rate", "stage_index": 2,
                "peak": 1.0, "value": 1.0, "forgetting": 0.0}], "skill_rows": []},
        }
        run = {"name": "A_seed1", "order": "A", "seed": 1,
               "summary": summary, "config": summary["config"]}
        with tempfile.TemporaryDirectory() as tmp, \
                patch("fac_tinyagent.phase2_report.load_runs", return_value=[run]), \
                patch("fac_tinyagent.phase2_report.full_eval_summary", return_value=None):
            output = write_phase2_report(Path(tmp), Path(tmp) / "report.md")
            report = output.read_text(encoding="utf-8")
            self.assertIn("| eligible runs |", report)
            self.assertNotIn("runs with forgetting", report)


if __name__ == "__main__":
    unittest.main()
