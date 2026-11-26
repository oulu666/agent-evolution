"""Unit proofs for the after-arm calibration. These tests do not read public corpora."""

import ast
import json
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import after_arm
from calibration_call import CalibrationCallError, bind_packs, dispatch


class PriorTests(unittest.TestCase):
    def test_public_shapes_are_not_outcome_masses(self):
        for value in ("green-oak", 1, 59.5, {"visible": True, "cell_text": ""}, [2]):
            self.assertFalse(after_arm.is_mass_triple(value))
            self.assertFalse(after_arm.admissible_prior(value))

    def test_absent_prior_selects_nothing(self):
        report = after_arm.select_static_sequence("toy", 2, None)
        self.assertFalse(report["sequence_selected"])
        self.assertFalse(report["sequence_scored"])
        self.assertIsNone(report["loss"])
        self.assertFalse(report["formal_score"])
        malformed = {"applies_to": "per-request", "masses": {"correct": 1, "deferred": 0, "wrong": 0}}
        refused = after_arm.select_static_sequence("toy", 2, malformed)
        self.assertFalse(refused["sequence_selected"])

    def test_equal_loss_keeps_the_shorter_sequence(self):
        prior = {"applies_to": "every-legal-sequence", "masses": {"correct": 0, "deferred": 1, "wrong": 0}}
        report = after_arm.select_static_sequence("toy", 2, prior)
        self.assertTrue(report["sequence_selected"])
        self.assertEqual(report["selected"], [])
        self.assertEqual(report["loss"], "1")
        self.assertEqual(report["label"], "calibration")
        self.assertFalse(report["formal_score"])
        self.assertEqual(report["n_sequences"], 1 + 2 + 4 + 8)


class RowAndPinTests(unittest.TestCase):
    def test_case_row_loss_stays_unset_without_all_four_facts(self):
        empty = after_arm.case_row_assessment([], True, None, None)
        self.assertEqual(empty["verdict"], "undetermined")
        self.assertEqual(empty["action"], "deliver_current")
        self.assertIsNone(empty["expected_task_loss"])
        self.assertFalse(empty["evidence_sufficient"])
        self.assertEqual(empty["label"], "calibration")
        masses = {"correct": 1, "deferred": 0, "wrong": 0}
        table = [{"op": "integer", "input": ["n"]}]
        partial = after_arm.case_row_assessment(table, True, None, masses)
        self.assertIsNone(partial["expected_task_loss"])
        ready = after_arm.case_row_assessment(table, True, "satisfied", masses)
        self.assertEqual(ready["expected_task_loss"], "0")
        self.assertTrue(ready["evidence_sufficient"])
        self.assertFalse(ready["formal_score"])
        self.assertEqual(ready["label"], "calibration")

    def test_pin_report_rejects_3_12_and_library_calls(self):
        good = {"implementation": "CPython", "version_info": [3, 11, 14], "version": "3.11.14",
                "executable": "/tmp/python3.11", "libraries_called": False,
                "formal_paired_comparison_started": False, "sample_drawn": False,
                "tasks": [{"case_id": "toy", "seed": 20261126, "sample_drawn": False}]}
        self.assertTrue(after_arm.accept_pin_report(good))
        for change in ({"version_info": [3, 12, 3], "version": "3.12.3"},
                       {"libraries_called": True},
                       {"sample_drawn": True},
                       {"implementation": "PyPy"}):
            self.assertFalse(after_arm.accept_pin_report({**good, **change}))

    def test_pin_check_process_refuses_a_non_3_11_interpreter(self):
        if sys.version_info[:2] == (3, 11):
            self.skipTest("this interpreter is already CPython 3.11")
        proc = subprocess.run([sys.executable, str(after_arm.PIN_CHECK), json.dumps(["toy"])],
                              capture_output=True, text=True, check=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn("3.11", proc.stdout)


class UnidecodeAndAdapterTests(unittest.TestCase):
    def test_only_an_exact_equality_pin_is_accepted(self):
        ranged = after_arm.scan_unidecode_pins([("setup.py", "install_requires=['Unidecode>=0.04.16']")])
        self.assertIsNone(ranged["exact_pin"])
        self.assertEqual(ranged["mentions"], ["setup.py"])
        narrative = after_arm.scan_unidecode_pins([("note.md", "Unidecode 1.4.0 was used")])
        self.assertIsNone(narrative["exact_pin"])
        exact = after_arm.scan_unidecode_pins([("fixture.json", "Unidecode==1.4.0")])
        self.assertEqual(exact["exact_pin"], "1.4.0")
        conflict = after_arm.scan_unidecode_pins([
            ("a.json", "Unidecode==1.4.0"), ("b.json", "unidecode==1.3.6")])
        self.assertIsNone(conflict["exact_pin"])
        self.assertTrue(conflict["conflict"])

    def test_unknown_arm_fails_before_a_download(self):
        bind_packs({"toy": {"library": "XlsxWriter", "operation": "column",
                            "arms": {"before": {"version": "0"}, "after": {"version": "1"}},
                            "inputs": [0]}})
        try:
            with self.assertRaises(CalibrationCallError) as caught:
                dispatch({"op": "calibration-input", "case_id": "toy", "arm": "rev", "index": 0})
            self.assertIn("shared pack", str(caught.exception))
            with self.assertRaises(CalibrationCallError) as caught:
                dispatch({"op": "calibration-input", "case_id": "toy", "arm": "after", "index": 5})
            self.assertIn("index", str(caught.exception))
        finally:
            bind_packs({})

    def test_strings_are_still_not_wrapped(self):
        week = after_arm.field_confirmation("babel-week", "str")
        duration = after_arm.field_confirmation("xlsx-duration", "float")
        self.assertFalse(week["addressable"])
        self.assertFalse(week["wrapped"])
        self.assertFalse(week["new_wrapper"])
        self.assertEqual(week["cross_field_invariants"], [])
        self.assertFalse(duration["addressable"])
        self.assertFalse(duration["new_wrapper"])

    def test_slug_without_a_fixture_pin_is_not_a_quality_receipt(self):
        budget = {"shared_first": {"completed": True, "dependency": {"unidecode": "1.4.0"}}}
        quality = after_arm.slugify_quality({"exact_pin": None, "conflict": False}, budget)
        self.assertFalse(quality["signoff_quality_receipt"])
        self.assertEqual(quality["resolved_versions"], ["1.4.0"])


class ScopeTests(unittest.TestCase):
    def test_modules_do_not_import_sealed_libraries(self):
        for name in ("after_arm.py", "run_after_arm.py", "pin_check.py", "calibration_call.py"):
            source = (HERE / name).read_text(encoding="utf-8")
            tree = ast.parse(source)
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module.split(".")[0])
            for banned in ("pandas", "PIL", "pillow", "scipy", "xlsxwriter", "babel", "slugify"):
                self.assertNotIn(banned, imports, name)
        self.assertNotIn("calibration-alt", (HERE / "after_arm.py").read_text(encoding="utf-8"))
        self.assertTrue(after_arm.followup.checklist_still_unticked())


if __name__ == "__main__":
    unittest.main()
