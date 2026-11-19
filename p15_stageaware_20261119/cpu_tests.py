"""CPU engineering acceptance, not a scientific promotion gate. No pretrained models."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='',HF_HUB_OFFLINE='1',TOKENIZERS_PARALLELISM='false',PYTHONDONTWRITEBYTECODE='1')
import copy,gzip,io,itertools,json,math,random,sys,time,types
from core import *
from guards import safety_decision

def main():
 from prepare import protect
 before=protect();checks={};features=json.loads(gzip.decompress((RUN/'token_features.json.gz').read_bytes()));allrows={s:rows(s) for s in ('train','dev','test')}
 v2=read(DATA/'manifest.json');assert v2['group_counts']['train']=={'counts':120,'locations':480,'fields':96};assert v2['template_texts_per_split']=={'train':21,'dev':21,'test':21}
 checks['six_review_counts_templates_confirmed']=True
 assert v2['gold_unchanged_rows']==1392 and all(r['gold_and_task_unchanged'] for r in read(DATA/'gold_reconciliation.json'))
 n=0;wrong=0;month=0
 for split,rr in allrows.items():
  bound=BoundCalendar(split);fixture=read(DATA/'fixtures'/f'{split}.json')['events']
  for r in rr:
   assert bound.execute(r)==json.loads(r['expected_observation']);n+=1
   scope=[e for e in fixture if e['date'].startswith(r['expected_arguments']['month']+'-')] if 'month' in r['expected_arguments'] else [e for e in fixture if e['date']==r['expected_arguments']['date']]
   assert set(r['entity_set']['event_ids'])=={e['id'] for e in scope}
   f=features[r['episode_id']];assert len(f['input_ids'])<=4096
   assert all((a!=-100)+(b!=-100)==(c!=-100) for a,b,c in zip(f['masks']['call'],f['masks']['final'],f['masks']['both']))
   if 'month' in r['expected_arguments']:
    month+=1;assert r['strata']['month_total_event_count']==r['expected_final_answer']
  for other in allrows:
   if other!=split:
    try:BoundCalendar(split,DATA/'fixtures'/f'{other}.json')
    except ValueError:wrong+=1
    else:raise AssertionError('Wrong fixture should fail closed')
    # A valid wrong-bound registry must also reject the row, even if the expected result is an empty list.
    try:BoundCalendar(other).execute(rr[0])
    except ValueError:wrong+=1
    else:raise AssertionError('Wrong row binding accepted')
 checks['v2_execution_gold_rows']=n;checks['wrong_fixture_negative_cases']=wrong;checks['month_entity_closure_rows']=month;checks['mask_partition_rows']=n
 for split in allrows:
  for other in allrows:
   if split>=other:continue
   for key in allrows[split][0]['entity_set']:
    a={v for r in allrows[split] for v in r['entity_set'][key]};b={v for r in allrows[other] for v in r['entity_set'][key]};assert not a&b
 checks['v2_entity_split_overlap']=0
 streams=read(RUN/'new_streams.json')
 for seed in SEEDS:
  for group in GROUPS:
   actual=new_stream(allrows['train'],features,seed,group);assert actual==streams[str(seed)][group];assert len(actual)==128
 checks['reproducible_new_streams_seed_group']=9
 cohort=read(RUN/'cohort.json');optional=read(RUN/'optional_full_replay_cohort.json')
 assert len(cohort)==108 and len(optional)==18 and collections.Counter(c['method'] for c in cohort)=={m:18 for m in METHODS}
 assert {c['method'] for c in optional}=={'full_replay'}
 checks['cohort_108_plus_optional_18']=True
 # Synthetic profiles evaluate rules, never any real model performance.
 base={s:{'tool_correct':1.,'arguments_correct':1.,'execution_success':1.,'final_correct':1.,'gold_final_correct':1.,'tool_args_core':1.,'joint_success':1.,'n':12} for s in SKILLS}
 cur=copy.deepcopy(base);cur[SKILLS[0]].update(tool_correct=.25,tool_args_core=.25,joint_success=.25)
 cur[SKILLS[1]].update(final_correct=.25,gold_final_correct=.25,joint_success=.25)
 p=priority('layer_replay',SKILLS,cur,base);assert p['components'][SKILLS[0]]=='call' and p['components'][SKILLS[1]]=='final'
 assert p['weights'][SKILLS[0]]>p['weights'][SKILLS[2]] and min(p['weights'].values())>=.25/len(SKILLS) and abs(sum(p['weights'].values())-1)<1e-12
 ab1=priority('no_priority',SKILLS,cur,base);assert len(set(ab1['weights'].values()))==1 and ab1['components']==p['components']
 ab2=priority('no_layer',SKILLS,cur,base);assert ab2['weights']==p['weights'] and set(ab2['components'].values())=={'both'}
 legacy=priority('p11_priority',SKILLS,cur,base);assert legacy['weights'][SKILLS[1]]>legacy['weights'][SKILLS[2]]
 checks['algorithm_two_modules_and_two_ablations']=True
 replay_count=0
 for method in METHODS:
  for i in range(50):
   a=choose_replay(method,allrows['train'],features,priority(method,SKILLS,cur,base),random.Random(i))
   assert sum(features[e]['input_tokens'] for e,m in a)<=REPLAY_CAP[0]
   assert sum(features[e]['supervised_tokens'][m] for e,m in a)<=REPLAY_CAP[1]
   if method=='seqft':assert not a
   replay_count+=1
 try:choose_replay('uniform',allrows['dev'],features,p,random.Random(1))
 except AssertionError:pass
 else:raise AssertionError('Dev leaked into replay candidates')
 checks['whole_row_replay_dual_cap_cases']=replay_count;checks['dev_candidate_negative_test']=True
 from fac_tinyagent.metrics import joint_success
 for values in itertools.product((False,True),repeat=4):assert joint_success(dict(zip(('tool_correct','arguments_correct','execution_success','final_correct'),values)))==all(values)
 checks['B1_truth_table']=16
 nodes=[];lookup={}
 for t in range(4):
  node=[]
  for i,g in enumerate(GROUPS):
   eid=g;lookup[eid]={'continual_group':g};v=bool(t>=i+1 and not(i==0 and t>=2))
   node.append({'episode_id':eid,'skill':'skill_'+g,**{k:v for k in ('tool_correct','arguments_correct','execution_success','final_correct','gold_final_correct','tool_args_core','joint_success')}})
  nodes.append(node)
 l=longitudinal(nodes,GROUPS,lookup)['joint_success'];assert l['at_risk']==2 and l['lost']==1 and l['forgetting_rate']==.5 and l['BWT']==-.5 and l['FWT']==0
 checks['BWT_FWT_at_risk_denominators']=True
 assert l['per_skill']['skill_counts']['terminal_lost']==1 and l['per_skill']['skill_counts']['old_skill_stage_transitions'][0]['lost']==1
 checks['per_skill_acquisition_retention_transitions']=True
 from analyze import paired_summary,holm
 ds={(tuple(order),s):.1 for order in itertools.permutations(GROUPS) for s in SEEDS};sm=paired_summary(ds);assert sm['paired_order_seed_units']==18 and sm['seed_block_signflip_two_sided_p']==.25
 json.loads(json.dumps(sm));checks['statistics_JSON_roundtrip']=True
 assert holm({'a':.01,'b':.03,'c':.5})=={'a':.03,'b':.06,'c':.5}
 checks['paired_unit_and_Holm']=True
 for stops,game,power,others,projects,ac,expected in [([],False,80,[],[],True,True),(['STOP'],False,80,[],[],True,False),([],True,80,[],[],True,False),([],False,59,[],[],True,False),([],False,80,[1],[],True,False),([],False,80,[],[1],True,False),([],False,80,[],[],False,False)]:assert safety_decision(stops,game,power,others,projects,ac)==expected
 checks['STOP_Apex_low_power_gpu_AC_project_cases']=7
 from runner import require_start
 try:require_start('train',False)
 except PermissionError:pass
 else:raise AssertionError('CPU default allowed a training launch')
 assert not (RUN/'START_APPROVED.json').exists(),'Parent approval should NOT be created in CPU phase'
 checks['default_no_GPU_launch']=True
 # Same optimizer engine used by runtime, on an explicitly CPU-only tiny random model.
 import torch,numpy as np
 from optimization import optimizer_update
 class Tiny(torch.nn.Module):
  def __init__(self):super().__init__();self.emb=torch.nn.Embedding(8,6);self.drop=torch.nn.Dropout(.1);self.out=torch.nn.Linear(6,8)
  def forward(self,input_ids,attention_mask,labels):
   logits=self.out(self.drop(self.emb(input_ids)))[:,:-1];y=labels[:,1:]
   return types.SimpleNamespace(loss=torch.nn.functional.cross_entropy(logits.reshape(-1,8),y.reshape(-1),ignore_index=-100))
 class OK:
  def check(self):pass
 f={'one':{'input_ids':[1,2,3,4,5],'masks':{'both':[-100,2,3,4,5],'call':[-100,2,3,-100,-100],'final':[-100,-100,-100,4,5]},'supervised_tokens':{'both':4,'call':2,'final':2}}}
 torch.manual_seed(123);random.seed(123);np.random.seed(123);model=Tiny();opt=torch.optim.AdamW(model.parameters(),lr=.001)
 c=optimizer_update(model,opt,None,f,[('one','both','new'),('one','final','replay')],'cpu',OK());assert c['forward_sequences']==c['backward_sequences']==2 and c['supervised_tokens']==6
 mem=io.BytesIO();torch.save({'model':model.state_dict(),'opt':opt.state_dict(),'torch':torch.get_rng_state(),'python':random.getstate(),'numpy':np.random.get_state()},mem);mem.seek(0);state=torch.load(mem,map_location='cpu',weights_only=False)
 optimizer_update(model,opt,None,f,[('one','call','replay')],'cpu',OK());expected=copy.deepcopy(model.state_dict())
 model.load_state_dict(state['model']);opt.load_state_dict(state['opt']);torch.set_rng_state(state['torch']);random.setstate(state['python']);np.random.set_state(state['numpy'])
 optimizer_update(model,opt,None,f,[('one','call','replay')],'cpu',OK());assert all(torch.equal(expected[n],v) for n,v in model.state_dict().items())
 assert not torch.cuda.is_initialized(),'CPU tests must not initialize CUDA'
 checks['exact_CPU_gradient_optimizer_RNG_restore_continuation']=True
 checks['CUDA_initialized']=False;checks['pretrained_model_or_weights_loaded']=False
 protect();write(RUN/'protected_after.json',before,True)
 result={'tested_source_hashes':{p.name:h(p.read_bytes()) for p in sorted(CODE.glob('*.py'))},'status':'PASS','CPU_only':True,'scientific_algorithm_effectiveness_claim':False,'checks':checks,'protected_old_files_unchanged':len(before),
   'limits':'CPU toy update/restoration tested; actual 4-bit GPU model path, VRAM, CUDA AMP and throughput NOT run. No automatic mid-stage recovery is promised; incomplete runs fail closed pending separately audited recovery.'}
 write(RUN/'cpu_tests.json',result,True);print(cj(result))
if __name__=='__main__':main()
