"""Checks for the phrase table, slot rule, and the rescored 7a2971af artifacts."""
import ast
import json
import unittest
from pathlib import Path

import baselines
from learn import equivalent, select
from oracle import PHRASES, STUDY_REQUIREMENTS, synthesize_oracle
from score import score_study
from score_artifact import PROTOCOL_SENTENCE, build_receipt

HERE = Path(__file__).resolve().parent


def _copy_demos():
    def demo(name, text):
        return {"input": name, "expected": text, "seconds": 0.0,
                "before": ["Configuration - scm-engine", "pending delivery", text + "\n"],
                "after": ["Configuration - scm-engine", text, text + "\n"]}
    return [demo("demo-a", "count: 41"), demo("demo-b", "count: 73")]


def _jq_demos():
    def demo(number):
        source = f"[{number}]"
        return {"input": f"demo-{number}", "expected": source, "seconds": 0.0,
                "before": ["", source, "pending delivery", ""],
                "after": ["", source, "pending delivery", source]}
    return [demo(41), demo(73)]


class OracleTests(unittest.TestCase):
    def test_study_clauses_map_to_one_relation(self):
        copy = synthesize_oracle(STUDY_REQUIREMENTS["copy"], ["count: 41", "count: 73"])
        jq = synthesize_oracle(STUDY_REQUIREMENTS["jq"], ["[41]", "[73]"])
        self.assertEqual(copy["relation"], "full_string")
        self.assertIsNone(copy["abstain"])
        self.assertEqual(jq["relation"], "parsed_value")
        self.assertIsNone(jq["abstain"])

    def test_refusals_do_not_invent_a_relation(self):
        cases = {
            "": "empty_requirement",
            PROTOCOL_SENTENCE: "ambiguous_requirement",
            "内容保真": "underspecified_relation",
            "页面应当便于阅读": "unmapped_requirement",
            "按文本，并按精确十进制数值和结构比较": "ambiguous_requirement",
        }
        for requirement, reason in cases.items():
            result = synthesize_oracle(requirement, ["count: 41"])
            self.assertIsNone(result["relation"], requirement)
            self.assertEqual(result["abstain"], reason)
        missing = synthesize_oracle("内容保真，复制按文本", [None])
        self.assertEqual(missing["abstain"], "no_trusted_reference")
        self.assertIsNone(missing["relation"])
        incompatible = synthesize_oracle("按精确十进制数值和结构比较", ["count: 41"])
        self.assertEqual(incompatible["abstain"], "source_incompatible")
        self.assertIsNone(incompatible["relation"])

    def test_byte_keeps_one_trailing_newline(self):
        oracle = synthesize_oracle("字节一致", ["a\n"])
        self.assertEqual(oracle["relation"], "byte")
        self.assertFalse(equivalent("a\n", "a", "byte"))
        self.assertTrue(equivalent("a\n", "a", "full_string"))
        self.assertTrue(equivalent("a\n", "a", "text"))

    def test_parsed_value_distinguishes_precision(self):
        self.assertFalse(equivalent("[10000000000000000999]", "[\n  1e+19\n]\n", "parsed_value"))
        self.assertTrue(equivalent("[1E-999]", "[\n  1E-999\n]\n", "json"))
        with self.assertRaises(ValueError):
            equivalent("a", "a", "yaml")


class SelectionTests(unittest.TestCase):
    def test_before_constraint_drops_the_page_slot(self):
        demos = _copy_demos()
        self.assertEqual(select(demos, "full_string", True), [1])
        self.assertEqual(select(demos, "text", True), [1])
        self.assertEqual(select(demos, "full_string", False), [1, 2])

    def test_stdout_and_file_slots_follow_the_value_rule(self):
        demos = _jq_demos()
        self.assertEqual(select(demos, "parsed_value", True), [3])
        file_demos = []
        for demo in demos:
            file_demos.append({**demo, "after": ["", demo["expected"], demo["expected"], ""]})
        self.assertEqual(select(file_demos, "parsed_value", True), [2])

    def test_learned_decision_ignores_the_label_and_the_lookup_table(self):
        demos = _copy_demos()
        faulty = {"input": "original", "expected": "count: 41", "version": "bad",
                  "before": demos[0]["before"],
                  "after": ["count: 41", "count: 41\n\n", "count: 41\n"]}
        baselines.LOOKUP["toy-title"] = 0
        try:
            labeled = score_study(demos, [faulty], STUDY_REQUIREMENTS["copy"], 1, "toy-title")
            other = score_study(demos, [faulty], STUDY_REQUIREMENTS["copy"], 0, "not-registered")
        finally:
            del baselines.LOOKUP["toy-title"]
        self.assertEqual(labeled["slots_learned"], [1])
        self.assertEqual(labeled["rows"][0]["decisions"]["learned"], other["rows"][0]["decisions"]["learned"])
        self.assertFalse(labeled["rows"][0]["decisions"]["learned"])
        self.assertTrue(labeled["rows"][0]["decisions"]["lookup"])
        self.assertIsNone(other["rows"][0]["decisions"]["lookup"])
        self.assertFalse(labeled["rows"][0]["truth"])
        self.assertTrue(other["rows"][0]["truth"])
        self.assertTrue(labeled["rows"][0]["decisions"]["all_readable_any_match"])
        self.assertFalse(labeled["rows"][0]["decisions"]["all_readable_all_match"])

    def test_replay_accepts_its_own_bad_recording(self):
        demos = _jq_demos()
        source = "[10000000000000000999]"
        old = {"input": "n", "expected": source, "version": "1.6",
               "after": ["", source, "pending delivery", "[\n  1e+19\n]\n"]}
        new = {"input": "n", "expected": source, "version": "1.7.1",
               "after": ["", source, "pending delivery", "[\n  10000000000000000999\n]\n"]}
        scored = score_study(demos, [old, new], STUDY_REQUIREMENTS["jq"], 3, "jq-stdout")
        self.assertEqual([row["truth"] for row in scored["rows"]], [False, True])
        self.assertEqual([row["decisions"]["learned"] for row in scored["rows"]], [False, True])
        self.assertEqual([row["decisions"]["fixed_replay"] for row in scored["rows"]], [True, False])
        self.assertEqual([row["decisions"]["all_readable_any_match"] for row in scored["rows"]], [True, True])
        self.assertEqual([row["decisions"]["all_readable_all_match"] for row in scored["rows"]], [False, False])

    def test_selector_sources_do_not_name_clipboard(self):
        for name in ("learn.py", "oracle.py"):
            tree = ast.parse((HERE / name).read_text(encoding="utf-8"))
            words = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    words.append(node.value)
            joined = "\n".join(words)
            self.assertNotIn("clipboard", joined)
            self.assertNotIn("navigator", joined)


class ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.receipt = build_receipt()

    def test_frozen_decisions_are_unchanged(self):
        self.assertEqual(self.receipt["frozen_decision_mismatches"], {"copy": [], "jq": {"stdout": [], "file": []}})
        self.assertEqual(self.receipt["copy"]["slots_learned"], [1])
        self.assertEqual(self.receipt["copy"]["slots_after_only"], [1, 2])
        self.assertEqual(self.receipt["jq"]["modes"]["stdout"]["slots_learned"], [3])
        self.assertEqual(self.receipt["jq"]["modes"]["stdout"]["slots_after_only"], [1, 3])
        self.assertEqual(self.receipt["jq"]["modes"]["file"]["slots_learned"], [2])
        self.assertEqual(self.receipt["jq"]["modes"]["file"]["slots_after_only"], [1, 2])
        self.assertEqual(self.receipt["copy"]["oracle"]["relation"], "full_string")
        self.assertEqual(self.receipt["jq"]["modes"]["stdout"]["oracle"]["relation"], "parsed_value")
        self.assertFalse(self.receipt["provenance"]["observations_recollected"])
        self.assertEqual(self.receipt["provenance"]["head_sha"], "7a2971af11aedf919814d9ffbec69ed5c0afddf6")

    def test_metrics_and_the_keep_rule(self):
        copy = self.receipt["copy"]["metrics"]
        self.assertEqual(copy["learned"]["false_release"], 0)
        self.assertEqual(copy["learned"]["violation_rows"], 1)
        self.assertEqual(copy["learned"]["retention"], 2)
        self.assertEqual(copy["learned"]["healthy_rows"], 2)
        self.assertEqual(copy["lookup"], copy["learned"])
        self.assertEqual(copy["fixed_replay"]["false_release"], 0)
        self.assertEqual(copy["fixed_replay"]["retention"], 2)
        self.assertEqual(copy["after_only"]["violation_deferred"], 1)
        self.assertEqual(copy["after_only"]["retention"], 0)
        self.assertEqual(copy["all_readable_any_match"]["false_release"], 1)
        self.assertEqual(copy["all_readable_any_match"]["retention"], 2)
        self.assertEqual(copy["all_readable_all_match"]["false_release"], 0)
        self.assertEqual(copy["all_readable_all_match"]["retention"], 0)
        self.assertEqual(copy["all_readable_all_match"]["false_block"], 2)
        stdout = self.receipt["jq"]["modes"]["stdout"]["metrics"]
        file_mode = self.receipt["jq"]["modes"]["file"]["metrics"]
        self.assertEqual(stdout, file_mode)
        self.assertEqual(stdout["learned"]["false_release"], 0)
        self.assertEqual(stdout["learned"]["violation_rows"], 3)
        self.assertEqual(stdout["learned"]["retention"], 45)
        self.assertEqual(stdout["learned"]["healthy_rows"], 45)
        self.assertEqual(stdout["lookup"], stdout["learned"])
        self.assertEqual(stdout["fixed_replay"]["false_release"], 3)
        self.assertEqual(stdout["fixed_replay"]["retention"], 42)
        self.assertEqual(stdout["fixed_replay"]["false_block"], 3)
        self.assertEqual(stdout["all_readable_any_match"]["false_release"], 3)
        self.assertEqual(stdout["all_readable_any_match"]["retention"], 45)
        self.assertEqual(stdout["all_readable_all_match"]["retention"], 0)
        self.assertEqual(stdout["all_readable_all_match"]["false_block"], 45)
        self.assertEqual(stdout["after_only"]["retention"], 0)
        self.assertEqual(stdout["after_only"]["violation_deferred"], 3)
        self.assertTrue(all(self.receipt["lookup_ties_learned"].values()))
        self.assertFalse(self.receipt["replay_ties_learned"]["stdout"])
        self.assertEqual(self.receipt["question_selection"], "not_opened")
        self.assertIsNone(self.receipt["ranking"])
        self.assertFalse(self.receipt["mechanism_b"]["implemented"])
        violations = self.receipt["jq"]["independent_violation_inputs"]
        self.assertEqual(len(violations), 3)
        self.assertTrue(all(version == "1.6" for version, _name in violations))

    def test_cost_is_split_and_has_no_model_calls(self):
        copy = self.receipt["copy"]["cost"]
        stdout = self.receipt["jq"]["modes"]["stdout"]["cost"]
        self.assertEqual(copy["model_calls"], {"build": 0, "run": 0})
        self.assertEqual(stdout["model_calls"], {"build": 0, "run": 0})
        self.assertEqual(copy["tool_actions"], {"build": 2, "run": 3})
        self.assertEqual(stdout["tool_actions"], {"build": 2, "run": 48})
        self.assertGreater(copy["observation_seconds"]["build"], 0)
        self.assertGreater(stdout["observation_seconds"]["run"], 0)
        self.assertEqual(copy["logical_slot_reads"]["learned"], {"build": 12, "run": 3})
        self.assertEqual(copy["logical_slot_reads"]["lookup"], {"build": 0, "run": 3})
        self.assertEqual(copy["logical_slot_reads"]["all_readable_any_match"]["run"], 9)
        self.assertEqual(stdout["logical_slot_reads"]["learned"], {"build": 16, "run": 48})
        self.assertEqual(stdout["logical_slot_reads"]["fixed_replay"], {"build": 96, "run": 96})

    def test_committed_receipt_matches_the_rescore(self):
        committed = json.loads((HERE / "increment-receipt.json").read_text(encoding="utf-8"))
        fresh = json.loads(json.dumps(self.receipt))
        committed.pop("local_rescore_cpu_seconds")
        fresh.pop("local_rescore_cpu_seconds")
        self.assertEqual(committed, fresh)

    def test_addendum_lists_every_phrase(self):
        text = (HERE / "INCREMENT_ZH.md").read_text(encoding="utf-8")
        for phrases in PHRASES.values():
            for phrase in phrases:
                self.assertIn(phrase, text)

    def test_report_quotes_the_locked_counts(self):
        report = (HERE / "REPORT_ZH.md").read_text(encoding="utf-8")
        for text in ("45916565880", "7a2971af", "0/1", "2/2", "0/3", "45/45", "3/3", "42/45", "1/1"):
            self.assertIn(text, report)
        self.assertIn("not_opened", report)


if __name__ == "__main__":
    unittest.main()
