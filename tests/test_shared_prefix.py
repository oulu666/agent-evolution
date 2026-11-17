import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch
from fac_tinyagent.replay_train import save_prefix, load_prefix, _training_state_hash


class PrefixTests(unittest.TestCase):
    def test_roundtrip_restores_parameters_optimizer_and_rng(self):
        with tempfile.TemporaryDirectory() as temp, patch('torch.cuda.get_rng_state_all', return_value=[]), patch('torch.cuda.set_rng_state_all'):
            model = torch.nn.Linear(3, 2)
            optimizer = torch.optim.AdamW(model.parameters())
            scaler = torch.amp.GradScaler('cuda', enabled=False)
            model(torch.ones(1, 3)).sum().backward()
            optimizer.step()
            optimizer.zero_grad(set_to_none=True)
            expected_hash = _training_state_hash(model)
            save_prefix(temp, model, optimizer, scaler, {'seed': 1}, {'new_samples': 80}, {'start': {}, 'midpoint': {}}, 1.0)
            expected_random = (random.random(), np.random.random(), torch.rand(1))
            fresh = torch.nn.Linear(3, 2)
            fresh_optimizer = torch.optim.AdamW(fresh.parameters())
            restored = load_prefix(temp, fresh, fresh_optimizer, scaler, {'seed': 1})
            self.assertEqual(expected_hash, _training_state_hash(fresh))
            self.assertEqual(restored['counters']['new_samples'], 80)
            self.assertEqual(random.random(), expected_random[0])
            self.assertEqual(np.random.random(), expected_random[1])
            self.assertTrue(torch.equal(torch.rand(1), expected_random[2]))
            for a, b in zip(optimizer.state.values(), fresh_optimizer.state.values()):
                for key in a:
                    self.assertTrue(torch.equal(a[key], b[key]))
            with self.assertRaisesRegex(ValueError, 'metadata'):
                load_prefix(temp, fresh, fresh_optimizer, scaler, {'seed': 2})
            with open(Path(temp) / 'training_state.pt', 'ab') as handle:
                handle.write(b'changed')
            with self.assertRaisesRegex(ValueError, 'hash'):
                load_prefix(temp, fresh, fresh_optimizer, scaler, {'seed': 1})


if __name__ == '__main__':
    unittest.main()
