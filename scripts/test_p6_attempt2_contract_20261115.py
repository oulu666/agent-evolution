"""CPU contract E2E: real instrumented trainer, tiny model/SGD, fake B1 boundary only.
Outputs exclusively to runs_ext_p6_devplan_attempt2_cpu; NEVER scientific scores.
"""
import collections,copy,json,math,os,sys,types
from pathlib import Path
from unittest.mock import patch
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
import torch
from fac_tinyagent import p6_attempt2 as A,p6_e3_train_attempt2 as N
from fac_tinyagent import p6_devplan as D
from fac_tinyagent.sft import train as ST,evaluate as EV
from fac_tinyagent.utils import read_json,read_jsonl,write_json,write_jsonl
CPU=R/'runs_ext_p6_devplan_attempt2_cpu';CPU.mkdir(exist_ok=False)
TESTROOT=CPU/'cpu_contract_tests';TESTROOT.mkdir();PLANS=TESTROOT/'plans';PLANS.mkdir()
for s in D.SEEDS:
 for arm in D.ARMS:write_json(PLANS/(D.label(s,arm)+'.json'),A.adapt_plan(read_json(D.planpath(s,arm))))
oldlog=read_jsonl(D.RUNS/'branches/A_seed20261108_balanced_uniform/checkpoint/training_log.jsonl')
newcost={x['episode_id']:(x['input_tokens'],x['supervised_tokens']) for x in oldlog if x['kind']=='new'}
assert len(newcost)==80 and sum(x[0] for x in newcost.values())==37472
cost={}
for s in D.SEEDS:
 for arm in D.ARMS:
  for x in read_json(PLANS/(D.label(s,arm)+'.json'))['items']:cost[x['episode_id']]=(x['input_tokens'],x['supervised_tokens'])
prefix=torch.load(R/'runs_ext_e4/prefixes/A_seed20261108/training_state.pt',map_location='cpu',weights_only=False)
assert prefix['counters']['microsteps']==80 and prefix['counters']['optimizer_steps']==10
class TinyModel(torch.nn.Module):
 def __init__(self):super().__init__();self.w=torch.nn.Parameter(torch.ones(1))
 def forward(self,**batch):return types.SimpleNamespace(loss=self.w.square().sum()+batch['input_ids'].float().mean()*0)
 def save_pretrained(self,path):torch.save({'w':self.w.detach()},Path(path)/'cpu_model.pt')
class Tok:
 pad_token_id=0;padding_side='right'
 def save_pretrained(self,path):(Path(path)/'cpu_tokenizer.json').write_text('{}')
class TinySGD(torch.optim.SGD):
 def __init__(self,params,lr):super().__init__(params,lr=lr)
def prep(rows,tok,max_length,family,complete_only=False):
 out=[]
 for i,r in enumerate(rows):
  n,supervised=(newcost if family=='calendar' else cost).get(r['episode_id'],(330,30))
  features={'input_ids':[1]*n,'attention_mask':[1]*n,'labels':[1]*supervised+[-100]*(n-supervised)}
  out.append({'family':family,'row_index':i,'episode_id':r['episode_id'],'input_tokens':n,'supervised_tokens':supervised,'truncated':False,'features':features})
 return out,[]
def load_prefix(path,model,optimizer,scaler,metadata):
 return {'counters':copy.deepcopy(prefix['counters']),'probes':copy.deepcopy(prefix['probes']),'duration_seconds':prefix['duration_seconds'],'parameter_hash':N._training_state_hash(model)}
trained_models=[]
def base(cfg):
 model=TinyModel();trained_models.append(model);return model,torch.float32
oldkeys=N.__dict__.copy()
# Rebind attempt2 paths in memory only for tests; production constants/source remain unchanged.
A.RUNS=TESTROOT;A.planpath=lambda s,a:PLANS/(D.label(s,a)+'.json');A.ckpt=lambda s,a:TESTROOT/'branches'/D.label(s,a)/'checkpoint'
A.P.RUNS=TESTROOT;A.P.planpath=A.planpath;A.P.ckpt=A.ckpt
A.REPORT=TESTROOT/'CPU_ONLY_REPORT.md';A.HANDOVER=TESTROOT/'CPU_ONLY_HANDOVER.md'
A.runtime_guard=lambda:None;A.safe=lambda:None;A.P.safe=A.safe
fakemodule=types.ModuleType('bitsandbytes.optim');fakemodule.PagedAdamW8bit=TinySGD
with patch.dict(sys.modules,{'bitsandbytes.optim':fakemodule}),patch.object(ST,'load_base_model',base),patch.object(ST,'load_tokenizer',lambda cfg:Tok()),patch.object(ST,'_attach_adapter',lambda model,cfg,adapter:model),patch.object(N,'_prepare_rows',prep),patch.object(N,'load_prefix',load_prefix),patch.object(N,'gpu_peak_gb',lambda:0):
 A.train(20261108,'balanced_uniform')
ck=A.ckpt(20261108,'balanced_uniform');summary=read_json(ck/'train_summary.json');audit=read_json(ck/'optimizer_step_audit.json')
assert summary['optimizer_steps']==23 and summary['partial_accumulation_microsteps']==6
assert len(read_jsonl(ck/'optimizer_update_log.jsonl'))==13
value=float(torch.load(ck/'cpu_model.pt',weights_only=True)['w'])
expected=(1-2*1e-4)**13
assert abs(value-expected)<1e-6,(value,expected)
# CPU-mocked evaluator validates checkpoint -> B1 interface -> partial and complete finalize.
loads=[]
def load_eval(cfg,adapter):
 if not loads:assert (Path(adapter)/'cpu_model.pt').exists()
 loads.append(adapter);return object(),Tok()
def evaluate(model,tok,rows,cfg,stage,out,db,cal):
 assert cfg['evaluation']['batch_size']==1
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 results=[{'episode_id':r['episode_id'],'joint_success':False,'tool_correct':False,'arguments_correct':False,'final_correct':False,'synthetic_cpu_contract':True} for r in rows]
 write_jsonl(out/'results.jsonl',results)
 report={'evaluation_protocol':{'batch_size':1},'synthetic_cpu_contract':True};write_json(out/'stage_report.json',report);return report
with patch.object(EV,'load_eval_model',load_eval),patch.object(EV,'evaluate_family',evaluate),patch.object(EV,'free_model',lambda model:None):
 A.evaluate(20261108,'balanced_uniform',only=['p6_database'])
 assert (TESTROOT/'evaluation/A_seed20261108_balanced_uniform/p6_database/stage_report.json').exists()
 A.finalize(allow_cpu_mock=True);assert not read_json(TESTROOT/'summary.json')['complete']
 for s in D.SEEDS:
  for a in D.ARMS:A.evaluate(s,a)
 A.finalize(allow_cpu_mock=True);assert read_json(TESTROOT/'summary.json')['complete']
 assert read_json(TESTROOT/'summary.json')['synthetic_cpu_contract']
# Old P4/P5 show the same pre-tail last log 22 / final summary 23 distinction.
old_evidence=[]
for run,label in [('runs_ext_p4_forget_timing','A_seed20261108_db4_early'),('runs_ext_p5_file_timing','A_seed20261108_early')]:
 p=R/run/'branches'/label/'checkpoint';s=read_json(p/'train_summary.json');last=read_jsonl(p/'training_log.jsonl')[-1]
 old_evidence.append({'run':run,'last_microstep':last['microstep'],'last_logged_optimizer_steps':last['optimizer_steps'],'final_summary_steps':s['optimizer_steps'],'tail':s['partial_accumulation_microsteps']})
 assert last['optimizer_steps']==22 and s['optimizer_steps']==23 and s['partial_accumulation_microsteps']==6
result={'status':'PASS','synthetic_cpu_contract':True,'real_trainer_control_flow':True,'real_runner_plan_train_summary_checkpoint_boundary':True,'mocked_evaluator_B1_and_partial_complete_finalize':True,'actual_suffix_optimizer_calls':13,'prefix_steps':10,'total_steps':23,'tail_microsteps':6,'tiny_model_weight':value,'analytic_13_step_weight':expected,'all_required_plan_fields':A.required_plan_keys(),'old_round_step_evidence':old_evidence,'gpu_started':False}
write_json(CPU/'acceptance.json',result);print(json.dumps(result,indent=2))
