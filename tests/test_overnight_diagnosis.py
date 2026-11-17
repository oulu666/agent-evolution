import tempfile
import unittest
from pathlib import Path

from fac_tinyagent.overnight_diagnosis import complete_unit, make_plan, restore_midpoint
from fac_tinyagent.utils import sha256_file, write_json, write_jsonl


class OvernightDiagnosisTests(unittest.TestCase):
    def test_plan_covers_all_stages_and_core_without_duplicate_ids(self):
        plan = make_plan()
        self.assertEqual(len(plan), 42)
        self.assertEqual(len({s['id'] for s in plan}), 42)
        historical = [s for s in plan if s['kind'] == 'historical']
        self.assertEqual(len(historical), 36)
        self.assertEqual(len(make_plan('core')), 12)
        counts = {'historical': 30, 'probe': 24, 'paired': 192}
        self.assertEqual(sum(counts[u.split('/')[0]] for s in plan for u in s['units']), 8208)

    def test_resume_requires_complete_matching_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            self.assertFalse(complete_unit(directory, ['one']))
            write_jsonl(directory / 'results.jsonl', [{'episode_id': 'one'}])
            write_json(directory / 'stage_report.json', {'n': 1})
            write_json(directory / 'complete.json', {
                'results_sha256': sha256_file(directory / 'results.jsonl'),
                'report_sha256': sha256_file(directory / 'stage_report.json')})
            self.assertTrue(complete_unit(directory, ['one']))
            with self.assertRaisesRegex(ValueError, 'IDs differ'):
                complete_unit(directory, ['another'])
            write_jsonl(directory / 'results.jsonl', [{'episode_id': 'modified'}])
            with self.assertRaisesRegex(ValueError, 'output changed'):
                complete_unit(directory, ['one'])

    def test_midpoint_eval_restores_frozen_parameters_and_checks_hash(self):
        import hashlib
        import torch
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            original = torch.nn.Linear(3, 2)
            values = {n: p.detach().clone() for n, p in original.named_parameters()}
            digest = hashlib.sha256()
            for name in sorted(values):
                digest.update(name.encode('utf-8'))
                digest.update(values[name].contiguous().view(torch.uint8).numpy().tobytes())
            expected = digest.hexdigest()
            torch.save({'parameters': values, 'parameter_hash': expected}, directory / 'training_state.pt')
            write_json(directory / 'manifest.json', {
                'state_sha256': sha256_file(directory / 'training_state.pt'), 'parameter_hash': expected})
            loaded = torch.nn.Linear(3, 2)
            for parameter in loaded.parameters():
                parameter.requires_grad_(False)
            self.assertEqual(restore_midpoint(loaded, directory), expected)
            for name, value in loaded.named_parameters():
                self.assertTrue(torch.equal(value, values[name]))
            self.assertFalse(loaded.training)
            with (directory / 'training_state.pt').open('ab') as stream:
                stream.write(b'changed')
            with self.assertRaisesRegex(ValueError, 'file checksum'):
                restore_midpoint(loaded, directory)


if __name__ == '__main__':
    unittest.main()
