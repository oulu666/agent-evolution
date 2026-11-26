import unittest
from copy import deepcopy
from fractions import Fraction

from freeze_guards import (BudgetExhausted, Decision, ExtraCalls, check_search_parity, delivery_change,
                           direct_delivery, disposition, expected_task_loss,
                           replay_choice, replay_group, transferred_verdict)


class GuardsTest(unittest.TestCase):
    def test_search_parity_rejects_weaker_static_search(self):
        settings = dict.fromkeys(("task_pack", "candidates", "prior", "transition", "legal_actions",
                                  "terminal_score", "pruning", "tie_break"), "fixture-id")
        settings.update(depth=3, scoring_limit=100)
        check_search_parity(settings, dict(settings))
        for change in ({"depth": 2}, {"scoring_limit": 50}, {"prior": "different"}):
            with self.assertRaises(ValueError):
                check_search_parity({**settings, **change}, settings)

    def test_last_call_and_delivery_credit(self):
        self.assertEqual(expected_task_loss(0, 1, 0), 1)
        self.assertEqual(expected_task_loss(Fraction(1, 2), 0, Fraction(1, 2)), Fraction(5, 2))
        with self.assertRaises(ValueError):
            expected_task_loss(1, 1, 0)
        blocked = delivery_change("wrong", "deferred")
        self.assertTrue(blocked["blocked_by_deferral"])
        self.assertFalse(blocked["wrong_to_correct"])
        self.assertEqual(blocked["loss_reduction"], 4)
        self.assertTrue(delivery_change("wrong", "correct")["wrong_to_correct"])

    def test_transfer_requires_expected_and_observed_relation(self):
        rule = {"relation": "scaled_quantity", "factor": 2, "clause": "size",
                "operation": "count", "expected": {"op": "length", "input": ["items"]},
                "observed": ["n"]}
        probe = {"clause": "size", "operation": "count", "endpoint": "test",
                 "snapshot": "initial", "inputs": {"items": [0, 1]}, "response": {"n": 1}}
        target = {**probe, "inputs": {"items": [0, 1, 2, 3]}, "response": {"n": 2}}
        self.assertEqual(transferred_verdict(rule, probe, target), "violated")
        for change in ({"snapshot": "later"}, {"clause": "other"}, {"response": {}},
                       {"response": {"n": 4}}, {"inputs": {"items": []}}):
            self.assertEqual(transferred_verdict(rule, probe, {**target, **change}), "undetermined")
        expressions = {"count": rule["expected"]}
        self.assertEqual(direct_delivery("count", target["inputs"], expressions), ("available", 4))
        self.assertEqual(direct_delivery("report", target["inputs"], expressions), ("unavailable", None))
        restricted = deepcopy(rule)
        restricted["expected"]["when"] = [{"op": "equals", "input": ["mode"], "value": "exact"}]
        self.assertEqual(transferred_verdict(restricted, probe, target), "undetermined")
        self.assertEqual(direct_delivery("count", target["inputs"], {"count": restricted["expected"]}),
                         ("unavailable", None))

    def test_coupled_observation_only_as_minimal_feasible_group(self):
        def policy(context, history):
            n = history[-1]["response"]["n"]
            return Decision({"id": str(n)}, (), "check total")

        def feasible(r):
            return r["n"] == len(r["items"])

        history = [{"response": {"n": 2, "items": ["a", "b"], "tag": "x"}}]
        before = deepcopy(history)
        logged = policy({}, history)
        group = [(["n"], 1), (["items"], ["a"])]
        for field in group:
            result = replay_group(policy, {}, history, logged, [field], feasible)
            self.assertEqual(result["effect"], "unauditable")
        result = replay_group(policy, {}, history, logged, group, feasible)
        self.assertEqual(result["effect"], "request_changed")
        padded = group + [(["tag"], "y")]
        result = replay_group(policy, {}, history, logged, padded, feasible)
        self.assertEqual(result["effect"], "unauditable")
        self.assertEqual(history, before)

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
