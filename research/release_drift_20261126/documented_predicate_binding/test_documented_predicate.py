"""Synthetic checks for the frozen extractor, inclusion rule, and decision."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

from run import audit_driver, run_driver
from screening import (
    EXAMINE_CAP,
    INCLUDE_CAP,
    POOL,
    adjudicate,
    is_test_path,
    parent_line_numbers,
    queue_skip_reason,
    relevance,
)
from sentence_grounded import (
    audit_human,
    decide,
    extract,
    is_obligation,
    obligation_sentences,
    select_obligation,
    split_sentences,
    summarize_grounded,
    summarize_human,
    summarize_status,
    summarize_translated,
)


def _counts(status=0, jdoctor=0, bind=0, sentence=0, human=0, full=6,
            status_e=6, jdoctor_e=0, bind_e=0, sentence_e=0, human_e=0, full_e=6):
    return {
        "status_only": {"executable": status_e, "separates": status},
        "jdoctor_pattern": {"executable": jdoctor_e, "separates": jdoctor},
        "bind": {"executable": bind_e, "separates": bind},
        "sentence_grounded": {"executable": sentence_e, "separates": sentence},
        "human_from_sentence": {"executable": human_e, "separates": human},
        "full_output": {"executable": full_e, "separates": full},
    }


class ExtractorTests(unittest.TestCase):
    def test_unconditional_number_quality_and_string(self):
        self.assertEqual(extract("Returns 0.")[0]["translation"], "==0")
        self.assertEqual(extract("Returns: 0.")[0]["translation"], "==0")
        self.assertEqual(extract("Must be positive.")[0]["translation"], ">0")
        self.assertEqual(extract("The result is not positive.")[0]["translation"], "<=0")
        self.assertEqual(extract("The result is greater than or equal to 0.")[0]["translation"], ">=0")
        self.assertEqual(extract("Returns 'ascii'.")[0]["literal"], "ascii")
        self.assertEqual(extract("Returns None.")[0]["translation"], "==null")

    def test_backticks_do_not_block_a_literal(self):
        checks = extract("Returns ``True``.")
        self.assertEqual(checks[0]["translation"], "==true")
        translated = summarize_translated("jdoctor_pattern", "Returns ``True``.", {"ok": True, "value": True}, {"ok": True, "value": True})
        self.assertEqual(translated["checks"], [])

    def test_conditionals_hedges_and_negated_raises_emit_nothing(self):
        self.assertEqual(extract("Returns True if ready."), [])
        self.assertEqual(extract("Returns 0 on success."), [])
        self.assertEqual(extract("Raises ValueError if x is negative."), [])
        self.assertEqual(extract("Should return 0."), [])
        self.assertEqual(extract("Never raises ValueError."), [])
        self.assertTrue(obligation_sentences("Returns True if ready."))
        self.assertTrue(is_obligation("Should return 0."))

    def test_exception_and_subject_limits(self):
        self.assertEqual(extract("Always raises ValueError.")[0]["exc_type"], "ValueError")
        self.assertEqual(extract("The size is positive."), [])
        self.assertEqual(extract("Returns 1 or 2."), [])
        parent = {"ok": False, "exc_type": "TypeError", "message": "bad"}
        fix = {"ok": False, "exc_type": "ValueError", "message": "bad"}
        summary = summarize_grounded("Raises ValueError.", parent, fix)
        self.assertTrue(summary["separates"])
        self.assertEqual(summarize_translated("jdoctor_pattern", "Raises ValueError.", parent, fix)["checks"], [])
        self.assertEqual(summarize_translated("bind", "Raises ValueError.", parent, fix)["checks"], [])

    def test_decimal_point_is_not_a_sentence_boundary(self):
        parts = split_sentences("The result is 1.0. Next returns 2.")
        self.assertEqual(parts[0], "The result is 1.0.")
        self.assertIn("1.0", parts[0])
        self.assertEqual(extract("The result is 1.0.")[0]["translation"], "==1.0")

    def test_doctest_is_not_an_obligation(self):
        text = ">>> example()\n1\n\nReturns 0.\n"
        self.assertEqual([item["translation"] for item in extract(text)], ["==0"])

    def test_separation_labels(self):
        parent = {"ok": True, "value": 1}
        fix = {"ok": True, "value": 0}
        self.assertTrue(summarize_grounded("Returns 0.", parent, fix)["separates"])
        both = summarize_grounded("Returns 0.", parent, {"ok": True, "value": 1})
        self.assertEqual(both["class"], "both_alarm")
        self.assertFalse(both["separates"])
        clear = summarize_grounded("Returns 0.", {"ok": True, "value": 0}, {"ok": True, "value": 0})
        self.assertEqual(clear["class"], "both_clear")
        inverted = summarize_grounded("Returns 0.", {"ok": True, "value": 0}, parent)
        self.assertEqual(inverted["class"], "inversion")
        ordinary = {
            "parent": {"ok": True, "value": 5},
            "fix": {"ok": True, "value": 0},
        }
        alarmed = summarize_grounded("Returns 0.", parent, fix, ordinary)
        self.assertEqual(alarmed["class"], "false_alarm")

    def test_status_and_bind_on_a_return(self):
        parent = {"ok": False, "exc_type": "ValueError", "message": "x"}
        fix = {"ok": True, "value": 1}
        self.assertTrue(summarize_status(parent, fix)["separates"])
        self.assertFalse(summarize_status(fix, fix)["separates"])
        bound = summarize_translated(
            "bind",
            "Returns\nThe result is positive.\n",
            {"ok": True, "value": -1},
            {"ok": True, "value": 3},
        )
        self.assertTrue(bound["separates"])


class HumanCeilingTests(unittest.TestCase):
    def test_condition_is_not_an_automatic_check(self):
        sentence = "Raises ValueError if year is less than 1."
        self.assertEqual(extract(sentence), [])
        expr = {"op": "raises", "type": "ValueError", "when": {"input": "year", "relation": "<", "number": 1}}
        self.assertTrue(audit_human(expr, sentence))
        self.assertFalse(audit_human({"op": "raises", "type": "KeyError"}, sentence))
        self.assertFalse(audit_human(
            {"op": "raises", "type": "ValueError", "when": {"input": "year", "relation": "<", "number": 9}},
            sentence,
        ))
        summary = summarize_human(
            expr,
            {"ok": True, "value": 0},
            {"ok": False, "exc_type": "ValueError", "message": "bad"},
            {"year": 0},
        )
        self.assertTrue(summary["separates"])

    def test_not_positive_licenses_the_negated_translation(self):
        sentence = "The result is not positive."
        self.assertTrue(audit_human({"op": "return_holds", "translation": "<=0"}, sentence))
        self.assertFalse(audit_human({"op": "return_holds", "translation": ">0"}, sentence))


class InclusionTests(unittest.TestCase):
    def test_shared_token_and_survival(self):
        document = "Raises ValueError if year is less than 1."
        prose = "parse raises ValueError on a negative year"
        choice = select_obligation(obligation_sentences(document), prose, "parse")
        self.assertEqual(choice["reason"], "include")
        judged = adjudicate(
            [{"key": "a", "qualname": "parse", "document": document, "path": "m.py", "url": "u", "file_sha256": "0"}],
            prose,
            lambda _key: document,
        )
        self.assertEqual(judged["decision"], "include")
        missing = adjudicate(
            [{"key": "a", "qualname": "parse", "document": document, "path": "m.py", "url": "u", "file_sha256": "0"}],
            prose,
            lambda _key: "Returns a new contract.",
        )
        self.assertEqual(missing["reason"], "parent_sentence_absent_from_fix")

    def test_type_only_text_and_ambiguous_predicates_are_excluded(self):
        self.assertEqual(obligation_sentences("Returns a string."), [])
        judged = adjudicate(
            [{"key": "a", "qualname": "parse", "document": "Returns a string.", "path": "m.py"}],
            "fix parse",
            lambda _key: "Returns a string.",
        )
        self.assertEqual(judged["reason"], "no_parent_sentence")
        document = "Raises ValueError.\n\nRaises TypeError."
        ambiguous = adjudicate(
            [{"key": "a", "qualname": "parse", "document": document, "path": "m.py"}],
            "fix ValueError and TypeError",
            lambda _key: document,
        )
        self.assertEqual(ambiguous["reason"], "ambiguous_obligation")

    def test_function_name_link_needs_one_sentence(self):
        document = "The result is positive."
        choice = select_obligation(obligation_sentences(document), "incorrect value from normalize", "pkg.normalize")
        self.assertEqual(choice["link"], "function_name_and_behavior")
        many = "The result is positive.\n\nReturns 0."
        choice = select_obligation(obligation_sentences(many), "incorrect value from normalize", "pkg.normalize")
        self.assertEqual(choice["reason"], "ambiguous_obligation")

    def test_search_bounds_and_permanent_exclusions(self):
        self.assertEqual(EXAMINE_CAP, 40)
        self.assertEqual(INCLUDE_CAP, 10)
        self.assertEqual(len(POOL), 20)
        for name in ("pandas", "Pillow", "SciPy"):
            self.assertNotIn(name.lower(), [item.lower() for item in POOL])
        self.assertEqual(queue_skip_reason("Textualize/rich", 3718, "Fix title"), "excluded_prior_study")
        self.assertEqual(queue_skip_reason("python-attrs/attrs", 1428, "Fix title"), "excluded_prior_study")
        self.assertEqual(queue_skip_reason("pallets/click", 10, "Fix typo in help"), "title_not_behavior")
        self.assertIsNone(queue_skip_reason("pallets/click", 10, "Fix raise on bad values"))
        self.assertLess(relevance("Fix raise of ValueError"), relevance("Fix incorrect return"))
        self.assertTrue(is_test_path("pkg/tests/test_a.py"))
        self.assertFalse(is_test_path("pkg/core.py"))
        patch = "@@ -10,3 +10,3 @@\n context\n-old\n+new\n context2\n"
        self.assertEqual(parent_line_numbers(patch), {10, 11, 12})


class DecisionTests(unittest.TestCase):
    def test_pre_registered_order(self):
        self.assertEqual(decide(5, _counts(full=5, full_e=5), False)["decision"], "insufficient_denominator")
        loss = decide(6, _counts(human=2, human_e=2), False)
        self.assertEqual(loss["decision"], "extraction_loss")
        self.assertEqual(loss["reason"], "extraction_loss_human_separates")
        observed = decide(6, _counts(), False)
        self.assertEqual(observed["reason"], "extraction_loss_observation_only")
        tied = decide(6, _counts(jdoctor=2, bind=2, sentence=2, jdoctor_e=2, bind_e=2, sentence_e=2), False)
        self.assertEqual(tied["decision"], "no_new_method")
        gained = decide(6, _counts(jdoctor=1, bind=1, sentence=3, jdoctor_e=1, bind_e=1, sentence_e=3), False)
        self.assertEqual(gained["decision"], "complement_positive")
        unsafe = decide(6, _counts(jdoctor=1, bind=1, sentence=3, jdoctor_e=1, bind_e=1, sentence_e=3), True)
        self.assertEqual(unsafe["decision"], "no_gain")
        self.assertIsNone(gained["ranking"])

    def test_archived_trees_and_forbidden_names_stay_out(self):
        root = Path(__file__).resolve().parents[3]
        diff = subprocess.check_output(
            ["git", "diff", "--name-only", "HEAD", "--",
             "research/release_drift_20261126/contract_binding",
             "research/release_drift_20261126/catalog_gap_analysis",
             "research/release_drift_20261126/repair_gate",
             "research/release_drift_20261126/boundary_gap"],
            cwd=root,
            text=True,
        )
        self.assertEqual(diff.strip(), "")
        source = (Path(__file__).resolve().parent / "sentence_grounded.py").read_text(encoding="utf-8")
        self.assertNotIn("pandas", source.lower())
        with self.assertRaises(SystemExit):
            audit_driver("def call():\n    assert False\n", "click")


class HarnessTests(unittest.TestCase):
    def test_driver_return_and_exception(self):
        driver = "def call():\n    if inputs['x'] < 0:\n        raise ValueError('no')\n    return inputs['x']\n"
        raised = run_driver(sys.executable, driver, {"x": -1})
        self.assertEqual(raised["exc_type"], "ValueError")
        value = run_driver(sys.executable, driver, {"x": 2})
        self.assertEqual(value["value"], 2)
        opaque = run_driver(sys.executable, "def call():\n    return object()\n", {})
        self.assertFalse(opaque["jsonable"])


if __name__ == "__main__":
    unittest.main()
