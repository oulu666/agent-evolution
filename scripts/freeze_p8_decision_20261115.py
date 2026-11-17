from pathlib import Path
import sys,json,hashlib,ast,collections,time
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from fac_tinyagent import p8_decision_data_20261115 as D
from fac_tinyagent.utils import read_json,read_jsonl,write_json,sha256_file
assert not (D.DATA/'manifest.json').exists(),'freeze once'
assert read_json(D.RUN/'cpu_contract/acceptance.json')['status']=='PASS'
checks=read_json(D.DATA/'cpu_data_checks.json');assert checks['gold_checks']==116 and checks['counterexamples']['SQL_where_individually_required']>0 and checks['counterexamples']['SQL_tie_individually_required']>0
refs=[R/'P8_PREREG_20261115_decision_ZH.md']+[R/'fac_tinyagent'/f for f in ['p8_decision_data_20261115.py','p8_decision_20261115.py','p8_train_20261115.py','p7_fullstate_v2_20261115.py','p6_e3_train_attempt2.py','replay_train.py','sft/train.py','sft/dataset.py','sft/evaluate.py','metrics.py','p1_run.py']]
refs += [R/'scripts'/f for f in ['run_p8_decision_20261115.py','generate_p8_trainer_20261115.py','test_p8_contract_20261115.py','prepare_p8_contract_20261115.py','p8_refine_cpu_20261115.py','prepare_p8_supervisor_20261115.py','freeze_p8_decision_20261115.py']]
refs += [D.RUN/'cpu_contract/acceptance.json',R/'runs_ext_p7_statefix_v2_20261115/cpu_contract/acceptance.json',R/'.venv/lib/python3.12/site-packages/bitsandbytes/optim/optimizer.py',R/'data_phase2/calendar/train.jsonl',R/'data_phase2/fixtures/calendar.json']
for fam in ['database','file','python']:refs += [R/f'data_ext_e4/pool/{fam}.jsonl',R/f'data_ext_monitor_v2/{fam}.jsonl',R/f'data_phase2/{fam}/test.jsonl']
reuse={}
for seed in D.SEEDS:
 a=read_json(D.source(seed));b=read_json(D.planpath(seed));sa=read_json(D.oldck(seed)/'train_summary.json');stage=read_json(D.oldck(seed)/'stage_config.json');manifest=read_json(R/f'runs_ext_e4/prefixes/A_seed{seed}/manifest.json')
 assert len(a['items'])==len(b['items'])==22
 assert [x for x in a['items'] if not x['target']]==[x for x in b['items'] if not x['target']]
 assert [x['skill'] for x in a['items'] if x['target']]==[x['skill'] for x in b['items'] if x['target']]
 assert abs(b['actual_input_tokens']-7494)<=74 and sa['optimizer_steps']==23 and sa['prefix_reused']
 assert sa['shared_prefix_path']==str(R/f'runs_ext_e4/prefixes/A_seed{seed}')
 assert stage['config']['training']==manifest['metadata']['training']
 for f in ['adapter_model.safetensors','adapter_config.json','train_summary.json','optimizer_step_audit.json','optimizer_update_log.jsonl','training_log.jsonl','stage_config.json']:refs.append(D.oldck(seed)/f)
 refs += [D.source(seed),R/f'runs_ext_e4/prefixes/A_seed{seed}/manifest.json',R/f'runs_ext_e4/prefixes/A_seed{seed}/training_state.pt',R/f'runs_phase2/A_seed{seed}/checkpoints/stage_03_python/adapter_model.safetensors']
 reuse[str(seed)]={'old_A_adapter_sha256':sha256_file(D.oldck(seed)/'adapter_model.safetensors'),'old_A_23_updates_checked':True,'12_background_items_identical':True,'10_target_skill_slots_identical':True,'prefix_and_training_hyperparameters_identical':True,'A_training_reused_no_new_optimizer_work':True}
from fac_tinyagent.p1_run import suite_rows
_,db,cal,_=suite_rows('v3fix');refs += [Path(db),Path(cal),R/'data_ext_p0_cal_titlecount/final/title_count_v3fix.jsonl']
for p in [*refs,*D.DATA.rglob('*')]:
 if p.is_file() and p.suffix=='.py':ast.parse(p.read_text())
files={str(p.relative_to(R)):sha256_file(p) for p in [*refs,*[x for x in D.DATA.rglob('*') if x.is_file()]]}
write_json(D.DATA/'manifest.json',{'created':time.strftime('%F %T %z'),'stage':'frozen before any P8 model evaluation','arms':['original','decision'],'seeds':D.SEEDS,'training_new_branches':3,'new_optimizer_updates':39,'GPU_dev_diagnostic_updates':0,'main_holdout_per_skill':12,'dev_per_skill':4,'holdout_total':56,'B1_suites':42,'files':files,'reuse_A_evidence':reuse,'actual_budget':checks['plans'],'no_C_fallback':'Uniform fixed scheduling; no uninformative duplicate C arm'})
from fac_tinyagent.p8_decision_20261115 import runtime_guard
runtime_guard();print('P8 FREEZE PASS: exact A provenance, 12 background/schedule fixed, 3 new B trains, 116 gold, CPU real training/fullstate/B1 boundary PASS')
