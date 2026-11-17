"""CPU-only P6 launch gate: immutable signal, budget, LoRA-only gradient scope and leakage audit."""
import ast,collections,json,math,sys,time
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from fac_tinyagent import p6_devplan as P
P.verify_plans()
def j(p):return json.loads(p.read_text())
def enc(x):return json.dumps(x,sort_keys=True,ensure_ascii=False)
report={'time':time.strftime('%F %T %z'),'plans':{},'calibration':{},'data':{},'gpu_launched_by_this_audit':False}
for seed in P.SEEDS:
 c=j(P.RUNS/'calibration'/f'A_seed{seed}.json')
 assert c['optimizer_steps']==0 and c['parameter_hash_unchanged'] and not c['formal_holdout_loaded']
 assert c['forward_backward_pairs']==41 and all(math.isfinite(x) for x in c['benefit'].values())
 assert max(c['benefit'].values())>0
 report['calibration'][seed]={k:c[k] for k in ['benefit','forward_backward_pairs','optimizer_steps','parameter_hash_unchanged','formal_holdout_loaded']}
 plans={a:j(P.planpath(seed,a)) for a in P.ARMS}
 assert plans['devgrad_uniform']['p6']['counts']!=plans['balanced_uniform']['p6']['counts'],'no allocation manipulation'
 for arm,q in plans.items():
  assert len(q['items'])==22
  assert abs(q['actual_input_tokens']-7494)<=74.94
  assert q['actual_input_tokens']==sum(x['input_tokens'] for x in q['items'])
  assert sum(q['p6']['counts'].values())==10
  cfg=j(R/f'runs_phase2/A_seed{seed}/config.json');acc=cfg['training']['gradient_accumulation_steps'];assert acc==8
  assert math.ceil((160+len(q['items']))/acc)==23
  report['plans'][P.label(seed,arm)]={'counts':q['p6']['counts'],'tokens':q['actual_input_tokens'],'optimizer_steps':23,'items':22}
 assert collections.Counter(enc(x) for x in plans['balanced_uniform']['items'])==collections.Counter(enc(x) for x in plans['balanced_early']['items'])
# Prefix parameters are the same tensors the scorer restores. All trainable state tensors are LoRA.
import torch
for seed in P.SEEDS:
 state=torch.load(R/f'runs_ext_e4/prefixes/A_seed{seed}/training_state.pt',map_location='cpu',weights_only=False)
 names=list(state['parameters']);assert names and all('.lora_A.' in n or '.lora_B.' in n for n in names)
 assert state['parameter_hash']==j(P.RUNS/'calibration'/f'A_seed{seed}.json')['prefix_parameter_hash']
 report['calibration'][seed]['prefix_LoRA_tensor_count']=len(names)
 report['calibration'][seed]['only_LoRA_prefix_tensors']=True
 del state
# Inspect shared token loss routine: both dev and candidates call the same row-mean masked loss gradient.
src=(R/'fac_tinyagent/p6_devplan.py').read_text();tree=ast.parse(src)
assert 'params=[p for p in model.parameters() if p.requires_grad]' in src
assert 'loss=result.loss' in src and 'loss.backward()' in src and 'return avg/len(rs),statistics.mean(losses)' in src
attach=(R/'fac_tinyagent/sft/train.py').read_text()
assert 'prepare_model_for_kbit_training' in attach and 'is_trainable=True' in attach
report['gradient_definition']='requires_grad tensors from PEFT LoRA only; shared HF loss averages non--100 assistant labels per row; gradients averaged equally across rows for both dev and candidate groups'
train=[r for f in ['database','file','python'] for r in P.read_jsonl(R/'data_ext_e4/pool'/(f+'.jsonl'))]
dev=P.read_jsonl(P.DATA/'dev/rows.jsonl');hold=P.read_jsonl(P.DATA/'holdout/rows.jsonl')
for skill in P.SKILLS:
 t=[r for r in train if P.identify(r)==skill];d=[r for r in dev if r['skill']==skill];h=[r for r in hold if r['skill']==skill]
 assert len(d)==4 and len(h)==12
 assert not {P.digest(r['messages']) for r in t}&{P.digest(r['messages']) for r in d+h}
 assert not {P.digest(r['messages']) for r in d}&{P.digest(r['messages']) for r in h}
 key=lambda r:(enc(r['expected_arguments']),enc(r.get('environment',{})))
 # LT has the deliberately shared generic {} call; its DB fixture and answer table names are distinct.
 if skill!='db.list_tables':assert not {key(r) for r in t}&{key(r) for r in d+h}
 if skill=='py.median':
  sets=lambda rs:{tuple(sorted(r['expected_arguments']['values'])) for r in rs}
  assert not sets(t)&(sets(d)|sets(h)) and not sets(d)&sets(h)
 else:
  assert not {enc(r['expected_final_answer']) for r in t}&{enc(r['expected_final_answer']) for r in d+h}
  assert not {enc(r['expected_final_answer']) for r in d}&{enc(r['expected_final_answer']) for r in h}
 report['data'][skill]={'dev':4,'holdout':12,'exact_train_dev_test_episode_overlap':False,'train_dev_answer_literal_overlap':len({enc(r['expected_final_answer']) for r in t}&{enc(r['expected_final_answer']) for r in d}),'dev_holdout_answer_literal_overlap':len({enc(r['expected_final_answer']) for r in d}&{enc(r['expected_final_answer']) for r in h})}
report['note']='Coincident scalar median values are not episode leakage; full numeric multisets are disjoint. LT generic empty args intentionally recur, but DB schema entities and final names are disjoint.'
P.write_json(P.RUNS/'production_launch_gate.json',report)
print(json.dumps(report,ensure_ascii=False,indent=2))
