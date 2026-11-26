"""Unit proofs for the calibration harness. These tests do not read public corpora."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness
from freeze_guards import BudgetExhausted


class BudgetTests(unittest.TestCase):
    def test_fourth_online_call_is_intercepted_before_dispatch(self):
        seen = []

        def dispatch(request):
            seen.append(request)
            return {"ok": True}

        budget = harness.SharedBudget(dispatch)
        budget.shared_first({"role": "shared-first"})
        for step in range(3):
            budget.online("probe", {"role": "probe", "n": step})
        fourth = {"role": "probe", "n": 4}
        with self.assertRaises(BudgetExhausted):
            budget.online("probe", fourth)
        self.assertNotIn(fourth, seen)
        self.assertEqual(len(budget.extra_events), 3)
        self.assertEqual([event["completed"] for event in budget.extra_events], [True, True, True])

    def test_failed_call_consumes_budget(self):
        seen = []

        def dispatch(request):
            seen.append(request["role"])
            if request["role"] == "backup":
                raise OSError("down")
            return {"ok": True}

        budget = harness.SharedBudget(dispatch)
        budget.shared_first({"role": "shared-first"})
        with self.assertRaises(OSError):
            budget.online("backup", {"role": "backup"})
        budget.online("restore", {"role": "restore"})
        budget.online("probe", {"role": "probe"})
        with self.assertRaises(BudgetExhausted):
            budget.online("reset", {"role": "reset"})
        self.assertEqual([event["completed"] for event in budget.extra_events], [False, True, True])
        self.assertEqual([event["purpose"] for event in budget.extra_events], ["backup", "restore", "probe"])
        self.assertEqual(seen, ["shared-first", "backup", "restore", "probe"])

    def test_online_reset_backup_restore_share_the_extra_budget(self):
        seen = []

        def dispatch(request):
            seen.append(request["role"])
            return {"ok": True}

        budget = harness.SharedBudget(dispatch)
        budget.shared_first({"role": "shared-first"})
        budget.online("reset", {"role": "reset"})
        budget.online("backup", {"role": "backup"})
        budget.online("restore", {"role": "restore"})
        with self.assertRaises(BudgetExhausted):
            budget.online("probe", {"role": "probe"})
        self.assertEqual([event["purpose"] for event in budget.extra_events], ["reset", "backup", "restore"])
        self.assertEqual(seen, ["shared-first", "reset", "backup", "restore"])

    def test_shared_first_then_at_most_three_extras(self):
        seen = []

        def dispatch(request):
            seen.append(request)
            return {"ok": True}

        budget = harness.SharedBudget(dispatch)
        budget.shared_first({"role": "shared-first", "n": 0})
        for step, purpose in enumerate(("probe", "backup", "restore"), start=1):
            budget.online(purpose, {"role": purpose, "n": step})
        with self.assertRaises(BudgetExhausted):
            budget.online("reset", {"role": "reset", "n": 4})
        self.assertEqual(len(seen), 4)
        self.assertEqual(len(budget.extra_events), 3)
        self.assertTrue(all(event["request"]["role"] != "shared-first" for event in budget.extra_events))
        self.assertFalse(budget.first["request"] in [event["request"] for event in budget.extra_events])

    def test_failed_shared_first_does_not_consume_an_extra(self):
        def dispatch(request):
            raise OSError("down")

        budget = harness.SharedBudget(dispatch)
        with self.assertRaises(OSError):
            budget.shared_first({"role": "shared-first"})
        self.assertEqual(budget.extra_events, [])
        self.assertFalse(budget.first["completed"])

    def test_unregistered_purpose_does_not_consume_budget(self):
        budget = harness.SharedBudget(lambda request: request)
        budget.shared_first({"role": "shared-first"})
        with self.assertRaises(ValueError):
            budget.online("schema-offline", {"role": "schema-offline"})
        self.assertEqual(budget.extra_events, [])

    def test_scripted_demo_intercepts_restore_on_stored_payloads(self):
        report = harness.budget_demo([{"a": 1}, {"a": 2}])
        self.assertFalse(report["restore_dispatched"])
        self.assertFalse(report["live_adapter"])
        self.assertEqual([event["purpose"] for event in report["extra_events"]], ["probe", "verification", "reset"])
        self.assertEqual([event["completed"] for event in report["extra_events"]], [True, False, True])
        self.assertIsNotNone(report["intercepted"])

        short = harness.budget_demo([{"only": True}])
        self.assertEqual([event["completed"] for event in short["extra_events"]], [False, False, True])
        self.assertFalse(short["restore_dispatched"])


class ArithmeticTests(unittest.TestCase):
    def test_disposition_and_loss_on_tiny_fixture(self):
        result = harness.arithmetic_check()
        self.assertEqual(result["label"], "calibration")
        self.assertFalse(result["case_rows_used"])
        self.assertEqual(result["losses"], [0, 1, 5])
        self.assertEqual(result["actions"], {
            "violated_verified": "deliver_replacement",
            "violated_unverified": "defer",
            "satisfied": "deliver_current",
            "undetermined": "deliver_current",
        })


class ReplayTests(unittest.TestCase):
    def test_field_group_replay_rejects_illegal_replacements(self):
        report = harness.replay_public({"visible": True, "cell_text": "hello world"})
        attempts = report["attempts"]
        self.assertEqual(report["status"], "ran")
        self.assertFalse(report["signoff_ready"])
        self.assertTrue(attempts["overlapping"]["rejected"])
        self.assertEqual(attempts["overlapping"]["exception"], "ValueError")
        self.assertEqual(attempts["infeasible"]["reason"], "infeasible observation")
        self.assertEqual(attempts["unchanged"]["reason"], "no field changed")
        self.assertEqual(attempts["nonminimal"]["reason"], "smaller feasible intervention exists")
        self.assertEqual(attempts["missing"]["exception"], "KeyError")
        self.assertFalse(attempts["legal"]["rejected"])
        self.assertEqual(attempts["legal"]["effect"], "request_changed")
        self.assertFalse(attempts["legal"]["attribution"])

        duration = harness.replay_public([1.0, "[h]:mm"])
        self.assertEqual(duration["status"], "ran")
        self.assertTrue(duration["attempts"]["overlapping"]["rejected"])
        self.assertEqual(duration["attempts"]["infeasible"]["reason"], "infeasible observation")
        self.assertFalse(duration["attempts"]["legal"]["rejected"])

    def test_unregistered_shapes_are_not_wrapped(self):
        for sample in ("calibration-string", {"deliver": True, "v": ["ok", "green-oak"]}, [{"import_error": "x"}]):
            report = harness.replay_public(sample)
            self.assertEqual(report["status"], "gap")
            self.assertFalse(report["wrapped"])
            self.assertNotIn("attempts", report)

    def test_formal_entry_is_replay_group(self):
        source = Path(harness.__file__).read_text(encoding="utf-8")
        self.assertIn("replay_group", source)
        self.assertNotIn("replay_choice", source)
        for banned in ("import xlsxwriter", "import babel", "import pandas", "import slugify",
                       "from PIL", "import scipy", "upstream_functional_witnesses"):
            self.assertNotIn(banned, source)


class ScopeTests(unittest.TestCase):
    def test_refuses_paths_outside_the_public_calibration_list(self):
        with self.assertRaises(SystemExit):
            harness.require_allowed(harness.REPO / "runs_blind_pairs_20261124" / "sealed_frame.json")
        with self.assertRaises(SystemExit):
            harness.require_allowed(harness.REPO / "research/release_drift_20261126/frame.json")
        with self.assertRaises(SystemExit):
            harness.require_allowed(Path("/tmp/not-in-repo.json"))

    def test_static_sequence_is_not_invented(self):
        report = harness.static_report(True)
        self.assertEqual(report["status"], "gap")
        self.assertFalse(report["sequence_enumerated"])
        self.assertFalse(report["development_preplanned_used"])
        self.assertTrue(report["empty_settings_rejected"])
        self.assertNotIn("preplanned", report["rejection"])
        self.assertTrue(harness.development_preplanned_is_present(
            {"1": {"static_info": {"preplanned": [2], "rows": [{"outcome": "wrong"}]}}}))
        self.assertFalse(harness.development_preplanned_is_present({}))

    def test_pack_loader_does_not_invent_a_pack(self):
        report = harness.pack_report({"applicable_versions": "public_fixture_only"}, ["note"])
        self.assertEqual(report["status"], "ran")
        self.assertFalse(report["signoff_ready"])
        self.assertIsNone(report["shared_pack_file"])
        self.assertEqual(report["fields"]["applicable_versions"], "public_fixture_only")
        self.assertEqual(report["fields"]["old_schema"], "absent")
        self.assertTrue((harness.REPO / "research/release_drift_20261126/freeze_guards.py").is_file())


if __name__ == "__main__":
    unittest.main()
