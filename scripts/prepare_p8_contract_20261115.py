from pathlib import Path
import sys,collections,json,copy
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from fac_tinyagent import p8_decision_data_20261115 as D
from fac_tinyagent.p1_run import suite_rows
from fac_tinyagent.utils import write_jsonl,write_json
for fam in ['database','file','python']:
 rows,db,cal,h=suite_rows('p2_'+fam);eligible=[]
 for r in sorted(rows,key=lambda r:r['episode_id']):
  if any(k in r.get('skill_labels',[]) or k in r['episode_id'] for k in D.SKILLS):continue
  if r['expected_tool'] in ['stats_median','db_list_tables','file_search']:continue
  sql=r.get('expected_arguments',{}).get('sql','').lower()
  if 'where' in sql and 'order by' in sql:continue
  eligible.append(r)
 selected=[];seen=set()
 for r in eligible:
  if r['expected_tool'] not in seen:selected.append(r);seen.add(r['expected_tool'])
 selected=selected[:4]
 for r in eligible:
  if len(selected)>=4:break
  if r not in selected:selected.append(r)
 assert len(selected)==4;write_jsonl(D.DATA/f'nontarget_{fam}.jsonl',selected)
 print(fam,[r['episode_id'] for r in selected])
p=R/'fac_tinyagent/p8_decision_20261115.py';s=p.read_text().replace("for k in sorted({r['skill'] for r in rs}):", "for k in sorted({k for r in rs for k in r['skill_labels']}):").replace("val=score([r for r in rs if r['skill']==k])", "val=score([r for r in rs if k in r['skill_labels']])")
s=s.replace(" from .e4_run import DB_PATH,CALENDAR_PATH\n return read_jsonl(DATA/(name+'.jsonl')),str(DB_PATH),str(CALENDAR_PATH)", " from .p1_run import suite_rows as oldrows\n _,db,cal,_=oldrows('p2_'+fam)\n return read_jsonl(DATA/(name+'.jsonl')),db,cal")
p.write_text(s)
# Real runner/trainer contract CPU test, then mock B1/finalize boundary only.
base=(R/'scripts/test_p6_attempt2_contract_20261115.py').read_text();header=base[:base.index('# CPU-mocked evaluator')]
header=header.replace('p6_attempt2 as A,p6_e3_train_attempt2 as N','p8_decision_20261115 as A,p8_train_20261115 as N').replace('from fac_tinyagent import p6_devplan as D','from fac_tinyagent import p8_decision_data_20261115 as D')
header=header.replace("CPU=R/'runs_ext_p6_devplan_attempt2_cpu';CPU.mkdir(exist_ok=False)","CPU=D.RUN/'cpu_contract';CPU.mkdir(exist_ok=False)")
a=header.index('for s in D.SEEDS:');b=header.index('oldlog=')
header=header[:a]+"for s in D.SEEDS:write_json(PLANS/(str(s)+'.json'),read_json(D.planpath(s)))\n"+header[b:]
header=header.replace("D.RUNS/'branches/A_seed20261108_balanced_uniform/checkpoint/training_log.jsonl'","D.oldck(20261108)/'training_log.jsonl'")
a=header.index('for s in D.SEEDS:',header.index('cost={}'));b=header.index('prefix=torch.load',a)
header=header[:a]+"for s in D.SEEDS:\n for x in read_json(D.planpath(s))['items']:cost[x['episode_id']]=(x['input_tokens'],x['supervised_tokens'])\n"+header[b:]
a=header.index('# Rebind attempt2 paths');b=header.index('fakemodule=',a)
header=header[:a]+"A.RUNS=TESTROOT;A.ckpt=lambda s,a: D.oldck(s) if a=='original' else TESTROOT/'branches'/D.label(s,a)/'checkpoint'\nA.REPORT=TESTROOT/'CPU_ONLY_REPORT.md';A.HANDOVER=TESTROOT/'CPU_ONLY_HANDOVER.md'\nA.runtime_guard=lambda:None;A.safe=lambda:None\n"+header[b:]
header=header.replace("A.train(20261108,'balanced_uniform')","A.train(20261108)").replace("A.ckpt(20261108,'balanced_uniform')","A.ckpt(20261108,'decision')")
footer='''
assert (ck/'full_state_receipt.json').exists() and (ck/'prefix_full_state_receipt.json').exists()
def load_eval(cfg,adapter):return object(),Tok()
def evaluate(model,tok,rows,cfg,stage,out,db,cal):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 results=[dict(episode_id=r['episode_id'],skill_labels=r['skill_labels'],joint_success=False,tool_correct=False,arguments_correct=False,execution_success=False,final_correct=False,synthetic_cpu_contract=True) for r in rows]
 write_jsonl(out/'results.jsonl',results);report={'evaluation_protocol':{'batch_size':1},'synthetic_cpu_contract':True};write_json(out/'stage_report.json',report);return report
with patch.object(EV,'load_eval_model',load_eval),patch.object(EV,'evaluate_family',evaluate),patch.object(EV,'free_model',lambda model:None):
 A.evaluate(20261108,'decision',only=['database']);A.finalize(allow_cpu_mock=True);assert not read_json(TESTROOT/'summary.json')['complete']
 for seed in D.SEEDS:
  for arm in D.ARMS:A.evaluate(seed,arm)
 A.finalize(allow_cpu_mock=True);assert read_json(TESTROOT/'summary.json')['complete']
result={'status':'PASS','synthetic_cpu_contract':True,'real_P8_runner_trainer_summary_tail_and_disk_fullstate':True,'actual_suffix_updates':13,'prefix_updates':10,'total_updates':23,'actual_replay_tokens':summary['replay_input_tokens'],'all_required_summary_plan_fields_passed':True,'B1_and_partial_complete_finalize_interface_with_real_result_schema_mocked':True,'tiny_final_weight':value,'analytic_weight':expected,'GPU_started':False}
write_json(CPU/'acceptance.json',result);print(json.dumps(result,indent=2))
'''
(R/'scripts/test_p8_contract_20261115.py').write_text(header+footer)
