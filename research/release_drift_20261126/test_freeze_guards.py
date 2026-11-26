import unittest

from freeze_guards import BudgetExhausted, Decision, ExtraCalls, disposition, replay_choice


class GuardsTest(unittest.TestCase):
    def test_failure_and_recovery_share_limit(self):
        dispatched = []

        def dispatch(request):
            dispatched.append(request)
            if request == "unavailable":
                raise OSError
            return request

        calls = ExtraCalls(dispatch)
        calls.call("probe", "first")
        with self.assertRaises(OSError):
            calls.call("verification", "unavailable")
        calls.call("recovery", "replacement")
        with self.assertRaises(BudgetExhausted):
            calls.call("replay", "fourth")
        self.assertEqual(dispatched, ["first", "unavailable", "replacement"])
        self.assertEqual([e["completed"] for e in calls.events], [True, False, True])

    def test_only_task_violation_enables_replacement(self):
        for verdict in ["satisfied", "undetermined"]:
            for replacement in [False, True]:
                self.assertEqual(disposition(verdict, verified_replacement=replacement),
                                 "deliver_current")
        self.assertEqual(disposition("violated", verified_replacement=False), "defer")
        self.assertEqual(disposition("violated", verified_replacement=True), "deliver_replacement")

    def test_offline_intervention_and_reproducibility(self):
        trace = [{"response": {"count": 2}}]
        for normal_request, effect in [({"id": "a"}, "same_action"),
                                       ({"id": "b"}, "request_changed"),
                                       (None, "stop_changed")]:
            def policy(context, history):
                observed = history[-1]["response"]["count"]
                request = {"id": "a"} if observed == 2 else normal_request
                return Decision(request, (), f"inspect count {observed}")

            logged = policy({}, trace)
            audit = replay_choice(policy, {}, trace, logged, ["count"], 1)
            self.assertEqual(audit["effect"], effect)
            self.assertEqual(trace[-1]["response"]["count"], 2)
            with self.assertRaises(ValueError):
                replay_choice(policy, {}, trace, Decision(None, (), "unreproducible"),
                              ["count"], 1)


if __name__ == "__main__":
    unittest.main()
