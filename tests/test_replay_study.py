import unittest

from fac_tinyagent.replay_study import paired


def row(name, tool=True, arguments=True, execution=True, final=True):
    return dict(episode_id=name, tool_correct=tool, arguments_correct=arguments,
                execution_success=execution, final_correct=final)


class PairingTests(unittest.TestCase):
    def test_offsetting_losses_and_gains_are_visible(self):
        before = [row("lost"), row("gained", final=False)]
        after = [row("gained"), row("lost", final=False)]
        result = paired(before, after)
        self.assertEqual(result["net_drop"], 0)
        self.assertEqual(result["lost"], 1)
        self.assertEqual(result["gained"], 1)

    def test_joint_failure_with_correct_answer(self):
        result = paired([row("x")], [row("x", tool=False)], "joint_success")
        self.assertEqual(result["lost"], 1)
        self.assertEqual(result["after"], 0)

    def test_missing_ids_rejected(self):
        with self.assertRaises(ValueError):
            paired([row("x")], [row("y")])


if __name__ == "__main__":
    unittest.main()
