"""CPU-only P5 safety supervisor tests; no real processes or GPU launched."""
import importlib.util,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('supervisor',ROOT/'scripts/run_p5_20261115.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class Safety(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
  self.r=Path(self.tmp.name); self.patches=[patch.object(m,'R',self.r),patch.object(m,'L',self.r),patch.object(m,'STOP',self.r/'STOP'),patch.object(m,'log')]
  for p in self.patches:p.start();self.addCleanup(p.stop)
 def d(self,**extra): return dict(game=False,power_cap_W=90,compute_apps='',gpu='mock',stop_exists=False,**extra)
 def test_clear(self):
  with patch.object(m,'inspect',return_value=self.d()): self.assertEqual(m.preflight()['power_cap_W'],90)
 def checkrefuse(self,k,v):
  d=self.d();d[k]=v
  with patch.object(m,'inspect',return_value=d):
   with self.assertRaises(SystemExit):m.preflight()
 def test_game(self):self.checkrefuse('game',True)
 def test_power(self):self.checkrefuse('power_cap_W',59)
 def test_other_gpu(self):self.checkrefuse('compute_apps','123, other-trainer, 1000 MiB')
 def test_sticky_stop(self):self.checkrefuse('stop_exists',True)
 def test_empty_tasklist_fails(self):
  with patch.object(m,'command',return_value=''):
   with self.assertRaises(RuntimeError):m.inspect()
 def test_terminate_writes_stop(self):
  child=MagicMock();child.pid=999999;child.poll.return_value=None
  with patch.object(m.os,'killpg') as kill:m.terminate(child,'game test');kill.assert_called_once()
  self.assertEqual((self.r/'STOP').read_text(),'game test\n')
if __name__=='__main__':unittest.main()
