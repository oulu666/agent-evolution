"""Unit proofs for the gap follow-up. These tests do not read public corpora."""

import ast
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import followup
from calibration_call import CalibrationCallError, dispatch
from freeze_guards import direct_delivery


class ExpressionTests(unittest.TestCase):
    def test_integer_identity_is_registered_only_as_the_complete_output(self):
        inputs = [{"n": 4}, {"n": 7}]
        expected = [4, 7]
        table = followup.registered_expressions(inputs, expected, "int")
        self.assertEqual(table, [{"op": "integer", "input": ["n"]}])
        self.assertEqual(direct_delivery("out", {"n": 4}, {"out": table[0]}), ("available", 4))

    def test_length_and_scale_need_the_same_complete_output_rule(self):
        length = followup.registered_expressions([{"items": [1, 2, 3]}], [3], "int")
        self.assertEqual(length, [{"op": "length", "input": ["items"]}])
        scaled = followup.registered_expressions([{"n": 2}, {"n": 5}], [6, 15], "int")
        self.assertEqual(scaled, [{"op": "scale_integer", "input": ["n"], "factor": 3}])
        self.assertEqual(direct_delivery("out", {"n": 2}, {"out": scaled[0]}), ("available", 6))

    def test_public_shapes_keep_an_empty_rule_table(self):
        for kind, expected in (("dict", [{"visible": True}]), ("str", ["2003-W24-7"]),
                               ("float", [1]), ("str", ["green-oak"])):
            self.assertEqual(followup.registered_expressions([{"n": 1}], expected, kind), [])
        mixed = followup.registered_expressions([{"n": 1}, {"n": 59.5}], [1, 59.5], "int")
        self.assertEqual(mixed, [])
        self.assertEqual(direct_delivery("out", {"n": 1}, {}), ("unavailable", None))

    def test_two_matching_rules_are_not_guessed(self):
        # factor 1 would also be integer identity; only the integer operation is kept.
        self.assertEqual(followup.registered_expressions([{"n": 4}], [4], "int"),
                         [{"op": "integer", "input": ["n"]}])


class StaticTests(unittest.TestCase):
    def test_depth_three_enumeration_counts_replacements(self):
        enumerated = followup.enumerate_sequences("toy", 2)
        self.assertEqual(enumerated["n_sequences"], 1 + 2 + 4 + 8)
        self.assertEqual(enumerated["depth"], 3)
        stopped = followup.budget_transition({"used": 0, "sequence": []}, None)
        self.assertTrue(stopped["terminal"])
        stepped = followup.budget_transition({"used": 2, "sequence": ["a", "b"]}, "c")
        self.assertEqual(stepped["used"], 3)
        blocked = followup.budget_transition(stepped, "d")
        self.assertTrue(blocked["terminal"])
        self.assertEqual(blocked["used"], 3)

    def test_shared_settings_pass_and_do_not_select_a_sequence(self):
        settings = followup.search_settings("pack-sha")
        followup.check_search_parity(settings, dict(settings))
        other = dict(settings)
        other["prior"] = "invented-masses"
        with self.assertRaises(ValueError):
            followup.check_search_parity(settings, other)
        report = followup.preplanned_match([2], ["{\"case\":\"toy\",\"index\":0}"])
        self.assertFalse(report["matches_direction_gate"])
        self.assertFalse(report["development_preplanned_used"])
        self.assertEqual(report["value"], [2])


class ReplayAndAddressTests(unittest.TestCase):
    def test_registered_normal_value_is_not_a_placeholder(self):
        report = followup.normal_replacements("xlsx-column", {"visible": True, "cell_text": ""},
                                              {"visible": True, "cell_text": ""})
        self.assertTrue(report["registered"])
        self.assertEqual(report["cross_field_invariants"], [])
        self.assertTrue(all(row["reason"] == "no field changed" for row in report["attempts"]))
        self.assertTrue(all(row["placeholder"] is False for row in report["attempts"]))

        duration = followup.normal_replacements("xlsx-duration", 1, [1.0, "[h]:mm"])
        self.assertTrue(duration["registered"])
        self.assertTrue(all(row["reason"] == "no field changed" for row in duration["attempts"]))

        week = followup.normal_replacements("babel-week", "2003-W24-7", "2003-W24-7")
        self.assertFalse(week["registered"])
        self.assertEqual(week["status"], "gap")

    def test_strings_and_scalars_are_not_wrapped(self):
        week = followup.address_unwrapped("str")
        scalar = followup.address_unwrapped("float")
        self.assertFalse(week["wrapped"])
        self.assertFalse(week["addressable"])
        self.assertFalse(scalar["addressable"])
        slug = followup.address_slugify({"deliveries": [{"method": "type", "v": ["ok", "green-oak"],
                                                         "deliver": True, "calls": 1, "ns": 5}]})
        self.assertFalse(slug["wrapped"])
        self.assertEqual(slug["status"], "ran")
        self.assertTrue(any(item["path"] == ["v", 1] and item["type"] == "str" for item in slug["paths"]))
        broken = followup.address_slugify({"import_error": "AttributeError: module 'slugify' has no attribute 'slugify'"})
        self.assertEqual(broken["paths"][0]["path"], ["import_error"])
        self.assertFalse(broken["wrapped"])
        self.assertIn("no attribute 'slugify'", broken["stored_import_error"])


class BudgetAndCounterTests(unittest.TestCase):
    def test_offline_costs_do_not_enter_the_online_counter(self):
        report = followup.offline_on("column", {"visible": True, "cell_text": "hello world"})
        self.assertEqual([event["kind"] for event in report["events"]], ["backup", "schema", "snapshot_reset"])
        self.assertTrue(all(event["elapsed_ns"] >= 0 for event in report["events"]))
        self.assertFalse(report["entered_extra_calls"])
        self.assertTrue(report["schema"]["accepted"])

    def test_script_intercepts_the_fourth_call_and_charges_the_failure(self):
        seen = []

        def fake(request):
            seen.append(request["role"])
            if request["op"] != "calibration-input":
                raise CalibrationCallError("unregistered calibration operation")
            return {"version": "fake", "result": {"visible": True}, "compared_to_expected": False}

        report = followup.budget_script("toy", "before", 2, fake)
        self.assertEqual(seen, ["shared-first", "probe", "verification", "reset"])
        self.assertFalse(report["verification"]["completed"])
        self.assertFalse(report["restore_dispatched"])
        self.assertIsNotNone(report["intercepted"])
        self.assertEqual([event["purpose"] for event in report["extra_events"]],
                         ["probe", "verification", "reset"])
        self.assertEqual([event["completed"] for event in report["extra_events"]], [True, False, True])

    def test_unregistered_adapter_operation_fails_before_a_library_call(self):
        with self.assertRaises(CalibrationCallError):
            dispatch({"op": "unregistered", "case_id": "toy", "arm": "before"})

    def test_case_row_disposition_stays_undetermined_without_masses(self):
        report = followup.case_row_disposition([])
        self.assertEqual(report["verdict"], "undetermined")
        self.assertEqual(report["action"], "deliver_current")
        self.assertIsNone(report["expected_task_loss"])
        self.assertEqual(report["direct_delivery"], "unavailable")
        self.assertFalse(report["transferred_verdict_called"])
        self.assertFalse(report["formal_score"])


class FreezeHashTests(unittest.TestCase):
    def test_hash_lists_the_four_registered_inputs(self):
        pin = {"cpython_3_11_pin": "unset", "random_arm_ran": False}
        frozen = followup.hash_freeze(followup.deployable_parameters(pin), [{"case_id": "toy"}],
                                      {"toy": []})
        self.assertEqual(frozen["input_set"], ["deployable_parameters", "disposition_rules",
                                               "expectations", "task_registry"])
        again = followup.hash_freeze(followup.deployable_parameters(pin), [{"case_id": "toy"}],
                                     {"toy": []})
        self.assertEqual(frozen["sha256"], again["sha256"])
        self.assertFalse(frozen["formal_checklist_ticked"])
        self.assertEqual(len(frozen["sha256"]), 64)

    def test_pin_helper_does_not_accept_3_12(self):
        self.assertIsNone(__import__("shutil").which("python3.11"))
        pin = followup.interpreter_pin()
        self.assertEqual(pin["cpython_3_11_pin"], "unset")
        self.assertFalse(pin["random_arm_ran"])
        followup.refuse_false_pin(pin)
        with self.assertRaises(RuntimeError):
            followup.refuse_false_pin({"cpython_3_11_pin": "satisfied", "random_arm_ran": False,
                                       "python3_11_path": None})


class ScopeTests(unittest.TestCase):
    def test_modules_do_not_import_sealed_libraries_or_read_corpora_in_assertions(self):
        for name in ("followup.py", "calibration_call.py", "calibration_worker.py", "run_followup.py"):
            source = (HERE / name).read_text(encoding="utf-8")
            tree = ast.parse(source)
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module.split(".")[0])
            for banned in ("pandas", "PIL", "pillow", "scipy", "xlsxwriter", "babel", "slugify"):
                if name == "calibration_worker.py" and banned in {"xlsxwriter", "babel", "slugify"}:
                    continue
                self.assertNotIn(banned, imports)
        self.assertNotIn("calibration-alt", (HERE / "followup.py").read_text(encoding="utf-8"))
        with self.assertRaises(ValueError):
            followup.pack_relative("../frame")
        self.assertTrue(followup.checklist_still_unticked())


if __name__ == "__main__":
    unittest.main()
