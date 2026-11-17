"""P5 CPU provenance and final readiness audit; no GPU imports."""
import ast,hashlib,json,time
from pathlib import Path
R=Path(__file__).resolve().parents[1]
D=R/'data_ext_p5_file_timing';O=R/'runs_ext_p5_file_timing'
def j(p):return json.loads(p.read_text())
def jl(p):return [json.loads(x) for x in p.read_text().splitlines() if x]
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
evidence={'time':time.strftime('%F %T %z'),'p4_summary_sha256':h(R/'runs_ext_p4_forget_timing/summary.json'),'p4_pairs':j(R/'runs_ext_p4_forget_timing/summary.json')['pairs'],'file_B1':[]}
for s in [20261108,20261109,20261110]:
 for a in ['stage_02_database','stage_03_python','none']:
  p=R/f'runs_ext_p1_b1/evaluation/A_seed{s}_{a}/natv2_file/results.jsonl';rows=jl(p)
  evidence['file_B1'].append({'seed':s,'arm':a,'source':str(p.relative_to(R)),'sha256':h(p),'n':len(rows),'joint_count':sum(bool(x['joint_success']) for x in rows)})
(O/'evidence_audit.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
files=[R/'fac_tinyagent'/n for n in ['e3_train.py','replay_train.py','p1_run.py','e3_run.py','e4_run.py','p4_forget_timing.py','p0_run.py','replay_study.py','utils.py']]
files += [R/'fac_tinyagent/sft'/n for n in ['train.py','dataset.py','evaluate.py']]
files += [R/f'runs_phase2/A_seed{s}/config.json' for s in [20261108,20261109,20261110]]
files += [R/'scripts'/n for n in ['finalize_p5_20261115.py','test_p5_safety_20261115.py','p5_audit_20261115.py']]
files += [R/'P5_PLAN_READY_20261115_ZH.md']
for p in files:
 if p.suffix=='.py':ast.parse(p.read_text())
lock={'created':time.strftime('%F %T %z'),'note':'Supplemental immutable provenance; no design changes or P5 GPU results used. Original source-allocation fields retained only as provenance; actual budget fields authoritative.','files':{str(p.relative_to(R)):h(p) for p in files}}
p=D/'implementation_lock.json'
if p.exists():assert j(p)['files']==lock['files']
else:p.write_text(json.dumps(lock,ensure_ascii=False,indent=2)+'\n')
assert not (O/'logs/gpu_child.pid').exists()
assert not (O/'branches').exists()
assert j(O/'dry_run.json')['status']=='PASS'
print('CPU readiness audit PASS; no P5 GPU child/branch; 9 plans frozen')
for x in evidence['file_B1']: print(x['seed'],x['arm'],x['joint_count'],x['n'])
