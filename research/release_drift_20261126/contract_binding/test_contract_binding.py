"""Synthetic checks for the frozen translator and decision rule."""

from pathlib import Path
import unittest

from binding import apply_check, audit, decide, translate_document
from jdoctor_patterns import holds, simple_match
from run import assert_allowed


class PatternTests(unittest.TestCase):
    def test_positive_and_negation(self):
        self.assertEqual(simple_match("is positive")["translation"], ">0")
        self.assertEqual(simple_match("is not null")["translation"], "!=null")
        self.assertEqual(simple_match("returns true")["translation"], "==true")
        self.assertIsNone(simple_match("is empty")["translation"])
        self.assertIsNone(simple_match("this"))
        self.assertTrue(holds(">0", 3))
        self.assertFalse(holds(">0", -1))
        self.assertIsNone(holds(">0", True))
        self.assertIsNone(holds(">0", "3"))

    def test_sections_and_subjects(self):
        text = "The size is positive.\n\nReturns\nmust be positive\n"
        bind = translate_document(text, "bind")
        jdoctor = translate_document(text, "jdoctor")
        self.assertEqual([item["translation"] for item in bind["checks"]], [">0", ">0"])
        self.assertEqual(len(jdoctor["checks"]), 1)
        view = {"ok": True, "fine": -1, "coarse": -1}
        self.assertEqual(apply_check(bind["checks"][0], view, "full"), "subject_unbound")
        self.assertEqual(apply_check(bind["checks"][1], view, "full"), "alarm")
        self.assertEqual(audit({"checks": [], "tagged": True, "doctests": 0}, None, None, False), "catalog_gap")

    def test_doctest_is_not_applied(self):
        document = translate_document(">>> example()\n1\n", "bind")
        self.assertEqual(document["doctests"], 1)
        self.assertEqual(document["checks"], [])

    def test_decision_order(self):
        def group(name, project, bind, jdoctor="no_check", status="no_check", gap=False):
            return {"id": name, "project": project, "bind": bind, "jdoctor": jdoctor, "status": status, "catalog_gap": gap}

        kept = decide([
            group("a", "humanize", "hit"),
            group("b", "rich", "hit"),
        ])
        self.assertEqual(kept["decision"], "keep")
        covered = decide([
            group("a", "humanize", "hit", status="hit"),
            group("b", "rich", "hit", status="hit"),
        ])
        self.assertEqual(covered["reason"], "status_covers")
        unsafe = decide([group("a", "humanize", "inversion", gap=True), group("b", "rich", "no_check", gap=True)])
        self.assertEqual(unsafe["decision"], "drop")
        single = decide([group("a", "humanize", "hit"), group("b", "rich", "no_check")])
        self.assertEqual(single["reason"], "single_project")
        gap = decide([group("a", "humanize", "no_check", gap=True), group("b", "rich", "no_check", gap=True)])
        self.assertEqual(gap["reason"], "catalog_gap")
        none = decide([group("a", "humanize", "no_check"), group("b", "rich", "no_check")])
        self.assertEqual(none["reason"], "no_gain")

    def test_sealed_path_is_refused(self):
        with self.assertRaises(SystemExit):
            assert_allowed(Path("/tmp/sealed/frame.json"))

    def test_extractors_do_not_read_expected_labels(self):
        directory = Path(__file__).resolve().parent
        source = (directory / "binding.py").read_text(encoding="utf-8")
        source += (directory / "jdoctor_patterns.py").read_text(encoding="utf-8")
        self.assertNotIn("expected", source)
        self.assertNotIn("callback_already_wrong", source)


if __name__ == "__main__":
    unittest.main()
