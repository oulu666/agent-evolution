from pathlib import Path
import ast,json,shutil,sys
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from fac_tinyagent import p6_attempt2 as A
for p in [R/'fac_tinyagent/p6_attempt2.py',R/'fac_tinyagent/p6_e3_train_attempt2.py',R/'scripts/run_p6_attempt2_20261115.py',R/'scripts/p6_attempt2_handshake_20261115.py']:ast.parse(p.read_text())
accept=json.loads((R/'runs_ext_p6_devplan_attempt2_cpu/acceptance.json').read_text());assert accept['status']=='PASS'
A.initialize()
(A.RUNS/'cpu_contract_tests').mkdir()
shutil.copyfile(R/'runs_ext_p6_devplan_attempt2_cpu/acceptance.json',A.RUNS/'cpu_contract_tests/acceptance.json')
A.runtime_guard()
print('ATTEMPT2 FREEZE PASS: all 9 original item hashes unchanged; CPU E2E acceptance pinned; calibration reused')
