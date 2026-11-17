import ast,json,hashlib,time
from pathlib import Path
R=Path(__file__).resolve().parents[1];D=R/'data_ext_p6_devplan';O=R/'runs_ext_p6_devplan'
paths=[R/'fac_tinyagent/p6_trainqueue.py',R/'scripts/run_p6_queue_20261115.py',R/'scripts/launch_p6_queue_20261115.sh',R/'scripts/p6_launch_handshake_20261115.py',R/'scripts/test_p6_safety_20261115.py',R/'scripts/test_p6_planner_20261115.py',R/'scripts/p6_freeze_runtime_20261115.py']
paths += [R/'fac_tinyagent/sft'/n for n in ['train.py','dataset.py','evaluate.py']]
paths += [R/'fac_tinyagent'/n for n in ['p1_run.py','e3_run.py','e4_run.py','utils.py']]
paths += [R/'data_phase2/calendar/train.jsonl',R/'data_phase2/fixtures/calendar.json',R/'data_ext_p0_cal_titlecount/final/title_count_v3fix.jsonl',R/'data_ext_cal_v3/fixtures/calendar_v3.json',R/'data_phase2/file/test.jsonl']
for p in paths:
 if p.suffix=='.py':ast.parse(p.read_text())
obj={'created':time.strftime('%F %T %z'),'note':'Additional immutable implementation lock; no model outputs used','files':{str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
p=D/'runtime_lock.json'
if p.exists():assert json.loads(p.read_text())['files']==obj['files']
else:p.write_text(json.dumps(obj,indent=2)+'\n')
assert not (O/'calibration').exists() and not (O/'branches').exists()
print('RUNTIME LOCK PASS; production entry AST valid; no P6 GPU outputs before freeze')
