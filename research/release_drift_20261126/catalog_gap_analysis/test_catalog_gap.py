"""Checks for the qualitative catalog-gap analysis. No scoring run."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import analyze


class DecisionRuleTest(unittest.TestCase):
    def test_keep_requires_a_stated_predicate_on_a_blind_group(self):
        decision = analyze.decide([
            {"id": "example", "justifies_scoring_protocol": True, "normalization_separates_blind_group": False}
        ])
        self.assertEqual(decision["decision"], "keep")
        self.assertFalse(decision["new_scoring_run"])

    def test_refine_requires_a_normalization_that_separates_a_blind_group(self):
        decision = analyze.decide(
            [{"id": "example", "justifies_scoring_protocol": False, "normalization_separates_blind_group": False}],
            [{"candidate": "markup", "separates_blind_group": True}],
        )
        self.assertEqual(decision["decision"], "refine")

    def test_otherwise_drop(self):
        decision = analyze.decide([
            {"id": "example", "justifies_scoring_protocol": False, "normalization_separates_blind_group": False}
        ])
        self.assertEqual(decision["decision"], "drop")
        self.assertEqual(decision["reason"], "recorded_drift_not_stated_as_predicate")


class CorpusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = analyze.build_analysis()
        cls.by_id = {case["id"]: case for case in cls.report["cases"]}

    def test_frozen_files_and_zero_checks(self):
        self.assertTrue(self.report["frozen_hashes_match"])
        self.assertEqual(self.report["frozen_study_commit"], "22a843467bfdc9d7b9663c0582f05f37cecd3a77")
        self.assertIsNone(self.report["ranking"])
        self.assertFalse(self.report["new_scoring_run"])
        for case_id, counts in self.report["check_counts"].items():
            self.assertEqual(counts["bind"], 0, case_id)
            self.assertEqual(counts["jdoctor_pattern"], 0, case_id)

    def test_twelve_groups_and_decision(self):
        self.assertEqual(
            [case["id"] for case in self.report["cases"]],
            list(analyze.DENOMINATOR),
        )
        self.assertEqual(self.report["decision"]["decision"], "drop")
        self.assertEqual(self.report["decision"]["justifying_groups"], [])
        self.assertEqual(self.report["decision"]["separating_normalizations"], [])
        for case in self.report["cases"]:
            self.assertFalse(case["justifies_scoring_protocol"])

    def test_drift_classes(self):
        expected = {
            "humanize-273": "implicit_visual_or_format",
            "humanize-254": "implicit_visual_or_format",
            "humanize-250": "implicit_visual_or_format",
            "humanize-218": "implicit_visual_or_format",
            "humanize-216": "parent_doc_encodes_bug",
            "prettytable-378": "exception_versus_value",
            "prettytable-356": "implicit_visual_or_format",
            "prettytable-355": "exception_versus_value",
            "prettytable-345": "exception_versus_value",
            "more-itertools-1088": "exception_versus_value",
            "more-itertools-1082": "exception_versus_value",
            "rich-3718": "implicit_visual_or_format",
        }
        actual = {case["id"]: case["drift_class"] for case in self.report["cases"]}
        self.assertEqual(actual, expected)
        blind = [case["id"] for case in self.report["cases"] if case["blind"]]
        self.assertEqual(
            blind,
            [
                "humanize-273",
                "humanize-254",
                "humanize-250",
                "humanize-218",
                "humanize-216",
                "prettytable-356",
                "rich-3718",
            ],
        )

    def test_catalog_stops_on_the_focal_sentences(self):
        stops = {
            "humanize-273": "period_splits_illustration",
            "humanize-254": "quantity_before_verb",
            "humanize-250": "no_catalog_verb",
            "humanize-218": "removed_before_match",
            "prettytable-378": "verb_without_quality",
            "prettytable-356": "tokens_between_verb_and_quality",
            "more-itertools-1088": "tokens_between_verb_and_quality",
            "more-itertools-1082": "verb_without_quality",
            "rich-3718": "python_none_without_catalog_verb",
        }
        chosen = {
            "humanize-273": 'becomes "1.0 million"',
            "humanize-254": "a value of zero will be returned",
            "humanize-250": "str: Human readable representation of a filesize",
            "humanize-218": "'3.0 MB'",
            "prettytable-378": "should be an iterable of lists",
            "prettytable-356": "if False return an empty string",
            "more-itertools-1088": "Return ``True`` if exactly ``n`` items in the iterable are ``True``",
            "more-itertools-1082": "``ValueError`` will be raised if the given *element* isn't in the product",
            "rich-3718": "Defaults to None",
        }
        for case_id, quote in chosen.items():
            focal = next(item for item in self.by_id[case_id]["focal"] if item["quote"] == quote)
            self.assertEqual(focal["stop"], stops[case_id], case_id)
        should = next(item for item in self.by_id["prettytable-378"]["focal"] if "should be" in item["quote"])
        self.assertIn("positive_should_not_rewritten", should["flags"])
        coaxed = next(item for item in self.by_id["humanize-273"]["focal"] if item["quote"].startswith("be coaxed"))
        self.assertEqual(coaxed["stop"], "verb_without_quality")

    def test_portuguese_slots_repeat_the_parent_word(self):
        case = self.by_id["humanize-216"]
        self.assertEqual(case["views"]["edge_parent"]["fine"], "2.0 bilhão")
        self.assertEqual(case["views"]["edge_repair"]["fine"], "2.0 bilhões")
        self.assertEqual(case["gettext"]["entries"][0]["slots"], ["bilhão", "bilhão"])
        french = self.by_id["humanize-273"]["gettext"]
        self.assertFalse(french["encoded"])
        self.assertEqual(french["parent_only_words_in_doc"], ["millions"])
        self.assertEqual(french["repair_only_words_in_doc"], ["million"])

    def test_counterfactuals_are_not_scores(self):
        backticks, should, portuguese, french = self.report["counterfactuals"]
        self.assertFalse(backticks["executed_as_score"])
        self.assertEqual(backticks["translation"], "==true")
        self.assertEqual(backticks["walkthrough_class"], "inversion")
        self.assertEqual(backticks["outcomes_on_stored_returns"]["edge_repair"], "alarm")
        self.assertEqual(backticks["outcomes_on_stored_returns"]["edge_parent"], "no_return")
        self.assertFalse(backticks["separates_blind_group"])
        self.assertIsNone(should["translation"])
        self.assertFalse(should["separates_blind_group"])
        self.assertFalse(portuguese["executed"])
        self.assertFalse(french["executed"])
        self.assertEqual(portuguese["slots_that_repeat_parent_word"][0]["slots"], ["bilhão", "bilhão"])
        self.assertEqual(french["slots_that_repeat_parent_word"], [])

    def test_recorded_differences_are_the_stored_replay(self):
        expected = {
            "humanize-273": ("1.0 millions", "1.0 million"),
            "humanize-254": ("60 seconds", "1 minute"),
            "humanize-250": ("1.0 Byte", "1 Byte"),
            "humanize-218": ("-1.3 MB", "3.0 MB"),
            "prettytable-356": ("└", "├"),
            "rich-3718": (None, "blue"),
        }
        for case_id, (parent, repair) in expected.items():
            views = self.by_id[case_id]["views"]
            self.assertEqual(views["edge_parent"]["fine"], parent)
            self.assertEqual(views["edge_repair"]["fine"], repair)
            self.assertEqual(views["edge_parent"]["coarse"], views["edge_repair"]["coarse"])
        rich = self.by_id["rich-3718"]
        self.assertIsNone(rich["views"]["edge_parent"]["fine"])
        self.assertFalse(any("blue" in (item["sentence"] or "") for item in rich["focal"]))


class ReportTest(unittest.TestCase):
    def test_report_states_the_drop_and_names_every_group(self):
        report = (analyze.HERE / "REPORT_ZH.md").read_text(encoding="utf-8")
        self.assertIn("决定是**停止**", report)
        self.assertIn("没有新的计分运行", report)
        self.assertIn("f40de3285593d246fa03e969826e6375c654d426", report)
        for case_id in analyze.DENOMINATOR:
            number = case_id.rsplit("-", 1)[1]
            self.assertIn(number, report)


class AllowlistTest(unittest.TestCase):
    def test_summary_json_is_readable_and_sealed_paths_are_refused(self):
        summary = json.loads(analyze.SUMMARY.read_text(encoding="utf-8"))
        self.assertEqual(summary["decision"]["decision"], "refine")
        self.assertEqual(summary["decision"]["reason"], "catalog_gap")
        with self.assertRaises(SystemExit):
            analyze.assert_allowed(analyze.ROOT / "environment_receipts" / "pandas.json")


if __name__ == "__main__":
    unittest.main()
