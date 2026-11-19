"""CPU only: non-destructive P14v2 correction, exact tokenizer ledger, P15 freeze."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='',HF_HUB_OFFLINE='1',TOKENIZERS_PARALLELISM='false',PYTHONDONTWRITEBYTECODE='1')
import collections,copy,gzip,itertools,json,hashlib,shutil,sys,time
from pathlib import Path
from core import *

def protect():
 prior=RUN/'protected_before.json'
 if prior.exists():before=read(prior)
 else:
  old=read(ROOT/'runs_ext_p14_eval_protocol/protected_sources_before.json')
  for folder in ('fac_tinyagent','scripts','tests','configs','data_ext_p14_eval_protocol','runs_ext_p14_eval_protocol'):
   for p in (ROOT/folder).rglob('*'):
    if p.is_file() and '__pycache__' not in p.parts and p.suffix in ('.py','.json','.jsonl','.md','.sha256','.zip','.log','.txt'):
     old[str(p.relative_to(ROOT))]=h(p.read_bytes())
  for p in ROOT.glob('*.md'):old[str(p.relative_to(ROOT))]=h(p.read_bytes())
  before=old;write(prior,before,True)
 for path,digest in before.items():assert h((ROOT/path).read_bytes())==digest,'Protected old file changed: '+path
 return before

def correct_v2():
 assert h((V1/'manifest.json').read_bytes())=='944b8e3d9b254e928559a55623aef3c41060234a8b04f010b9f1919f0f0b3881'
 for p,meta in read(V1/'manifest.json')['files'].items():assert h((ROOT/p).read_bytes())==meta['sha256']
 allrows={};reconcile=[];counts={};isolates={};month_changes=[]
 for split in ('train','dev','test'):
  fixture=read(V1/'fixtures'/f'{split}.json');events=fixture['events']
  install(DATA/'fixtures'/f'{split}.json',(V1/'fixtures'/f'{split}.json').read_bytes())
  rr=[]
  for line in (V1/split/'rows.jsonl').read_text().splitlines():
   old=json.loads(line);r=copy.deepcopy(old);r['continual_group']=r['strata']['operation_group']
   r['fixture_path']=f'data_ext_p14_eval_protocol_v2/fixtures/{split}.json'
   d=old['entity_set']['dates'][0];m=d[:7];r['target_date']=d
   day=[e for e in events if e['date']==d];month=[e for e in events if e['date'].startswith(m+'-')]
   r['strata'].pop('event_count');r['strata']['target_date_event_count']=len(day);r['strata']['month_total_event_count']=len(month)
   r['strata'].pop('interference_eligible');r['strata']['interference_status']='eligible hypothesis only; see operation_matrix.json'
   r['strata']['eligible_operation_pairs']=[name for name,a,b,label in OP_PAIRS if r['skill'] in (a,b)]
   scope=month if 'month' in r['expected_arguments'] else day
   r['entity_set']={'dates':sorted({e['date'] for e in scope}|{d}),'months':[m],
    'event_ids':sorted(e['id'] for e in scope),'titles':sorted({e['title'] for e in scope}),
    'locations':sorted({e['location'] for e in scope}),'people':sorted({p for e in scope for p in e['attendees']})}
   keys=['episode_id','tool_family','skill','prompt','query','template_id','template_text','system','messages','expected_tool','expected_arguments','expected_observation','expected_final_answer','answer_spec','data_signature']
   assert all(r[k]==old[k] for k in keys)
   reconcile.append({'episode_id':r['episode_id'],'gold_and_task_unchanged':True,'old_immutable_payload_sha256':h(cj({k:old[k] for k in keys}).encode()),'new_immutable_payload_sha256':h(cj({k:r[k] for k in keys}).encode())})
   if 'month' in r['expected_arguments']:month_changes.append({'episode_id':r['episode_id'],'old_event_count':old['strata']['event_count'],'target_date_event_count':len(day),'month_total_event_count':len(month),'added_entity_ids':sorted(set(r['entity_set']['event_ids'])-set(old['entity_set']['event_ids']))})
   rr.append(r)
  allrows[split]=rr;counts[split]=dict(collections.Counter(r['continual_group'] for r in rr))
  install(DATA/split/'rows.jsonl',(''.join(cj(r)+'\n' for r in rr)).encode())
  isolates[split]={k:set(v for r in rr for v in r['entity_set'][k]) for k in rr[0]['entity_set']}
  isolates[split].update(query={r['query'] for r in rr},template={r['template_text'] for r in rr})
 for a,b in itertools.combinations(allrows,2):assert all(not(isolates[a][k]&isolates[b][k]) for k in isolates[a]),(a,b)
 write(DATA/'gold_reconciliation.json',reconcile,True);write(DATA/'month_metadata_changes.json',month_changes,True)
 write(DATA/'operation_matrix.json',{'hypotheses':[{'id':n,'a':a,'b':b,'hypothesis':l,'observed_strength':None} for n,a,b,l in OP_PAIRS],
       'six_coarse_orders_do_not_identify_pure_interference':True},True)
 payload={str(p.relative_to(ROOT)):h(p.read_bytes()) for p in sorted(DATA.rglob('*')) if p.is_file() and p.name not in ('manifest.json','manifest.sha256') and 'features' not in p.name}
 write(DATA/'manifest.json',{'version':'P14-v2-metadata-only-20261119','parent_manifest_sha256':h((V1/'manifest.json').read_bytes()),'files':payload,'group_counts':counts,
  'template_texts_per_split':{s:len({r['template_text'] for r in rr}) for s,rr in allrows.items()},'gold_unchanged_rows':len(reconcile),'template_expansion':False},True)
 install(DATA/'manifest.sha256',(h((DATA/'manifest.json').read_bytes())+'  manifest.json\n').encode())
 for split,rr in allrows.items():
  bound=BoundCalendar(split)
  for r in rr:
   actual=bound.execute(r);assert actual==json.loads(r['expected_observation'])
   assert project(actual['result'],r['answer_spec'])==r['expected_final_answer']
 return allrows

def model_identity():
 base=Path(CONFIG['model_name_or_path']);files={}
 for p in sorted(base.glob('*.safetensors')):
  digest=hashlib.sha256()
  with p.open('rb') as f:
   for chunk in iter(lambda:f.read(8*1024*1024),b''):digest.update(chunk)
  files[p.name]={'sha256':digest.hexdigest(),'bytes':p.stat().st_size}
 assert files
 write(RUN/'base_model_identity.json',{'path':str(base),'weight_files':files,'CPU_streaming_hash_only':True,'model_instantiated':False},True)

def prepare():
 before=protect();model_identity();rr=correct_v2();write(RUN/'milestone_v2.json',{'status':'PASS','v2_gold_unchanged':1392,'groups':{s:dict(collections.Counter(r['continual_group'] for r in rs)) for s,rs in rr.items()},'gpu_training_started':False,'protected_files':len(before)})
 from transformers import AutoTokenizer
 tok=AutoTokenizer.from_pretrained(CONFIG['model_name_or_path'],local_files_only=True,trust_remote_code=False)
 if tok.pad_token_id is None:tok.pad_token=tok.eos_token
 started=time.perf_counter();features=encode_all(tok,[r for rs in rr.values() for r in rs]);elapsed=time.perf_counter()-started
 b=gzip.compress(cj(features).encode(),mtime=0);install(RUN/'token_features.json.gz',b)
 diag=fixed_diag(rr['dev']);trainprobe=[next(r for r in rr['train'] if r['skill']==s) for s in SKILLS]
 # Two different train entities per skill, fixed and split-disjoint from dev diagnostics.
 trainprobe=[r for s in SKILLS for r in sorted([x for x in rr['train'] if x['skill']==s],key=lambda x:x['episode_id'])[:2]]
 write(RUN/'diagnostic_subsets.json',{'dev_ids':[r['episode_id'] for r in diag],'train_loss_ids':[r['episode_id'] for r in trainprobe],
   'dev_by_skill':dict(collections.Counter(r['skill'] for r in diag)),'test_used_for_selection':False},True)
 streams={};ledger={}
 for seed in SEEDS:
  streams[str(seed)]={};ledger[str(seed)]={}
  for g in GROUPS:
   ss=new_stream(rr['train'],features,seed,g);streams[str(seed)][g]=ss
   rs=load_group(rr['train'],g)
   ledger[str(seed)][g]={'pool_rows':len(rs),'updates_exact':len(ss),'new_rows_actual':sum(len(x['ids']) for x in ss),
    'new_input_tokens_actual':sum(x['input_tokens'] for x in ss),'new_supervised_tokens_actual':sum(x['supervised_tokens'] for x in ss),
    'new_input_cap':STEPS*NEW_CAP[0],'new_supervised_cap':STEPS*NEW_CAP[1],
    'input_utilization':sum(x['input_tokens'] for x in ss)/(STEPS*NEW_CAP[0]),
    'supervision_utilization':sum(x['supervised_tokens'] for x in ss)/(STEPS*NEW_CAP[1]),
    'unique_new_ids':len(set(e for x in ss for e in x['ids'])),
    'pool_once_input_tokens':sum(features[r['episode_id']]['input_tokens'] for r in rs),
    'pool_once_supervised_tokens':sum(features[r['episode_id']]['supervised_tokens']['both'] for r in rs)}
 write(RUN/'new_streams.json',streams,True)
 pairs=operation_pairs(rr['train'],features);lookup={r['episode_id']:r for r in rr['train']}
 paired=[]
 for cond in pairs:
  for seed in SEEDS:
   for side in ('left','right'):
    ss=pair_stream(cond[side+'_ids'],lookup,features,seed)
    paired.append({'condition':cond['id'],'seed':seed,'side':side,'updates':len(ss),'input_actual':sum(x['input_tokens'] for x in ss),'supervision_actual':sum(x['supervised_tokens'] for x in ss)})
 write(RUN/'operation_pair_conditions.json',pairs,True);write(RUN/'operation_pair_CPU_schedules.json',paired,True)
 cohort=[]
 for order in itertools.permutations(GROUPS):
  for seed in SEEDS:
   for method in METHODS:
    cohort.append({'id':method+'__'+'-'.join(order)+f'__s{seed}','method':method,'order':list(order),'seed':seed,'steps':3*STEPS,
                   'new_input_tokens_exact':sum(ledger[str(seed)][g]['new_input_tokens_actual'] for g in order),
                   'new_supervised_tokens_exact':sum(ledger[str(seed)][g]['new_supervised_tokens_actual'] for g in order),
                   'replay_input_cap':0 if method=='seqft' else 2*STEPS*REPLAY_CAP[0],
                   'replay_supervised_cap':0 if method=='seqft' else 2*STEPS*REPLAY_CAP[1]})
 write(RUN/'cohort.json',cohort,True);write(RUN/'config.json',CONFIG,True)
 optional=[{**c,'id':c['id'].replace(c['method']+'__','full_replay__',1),'method':'full_replay','replay_input_cap':None,'replay_supervised_cap':None} for c in cohort if c['method']=='seqft']
 write(RUN/'optional_full_replay_cohort.json',optional,True)
 # Exact CPU tokenizer counts; generated outputs and wall time are unknown, only bounded.
 corpus={split:{'rows':len(rs),'input_tokens':sum(features[r['episode_id']]['input_tokens'] for r in rs),
    'supervised_tokens':sum(features[r['episode_id']]['supervised_tokens']['both'] for r in rs),'max_sequence':max(features[r['episode_id']]['input_tokens'] for r in rs)} for split,rs in rr.items()}
 prompt_budgets={}
 funcs=tokenizer_functions()
 for split,rs in rr.items():
  prompt_budgets[split]={'tool_prompt_tokens_exact':0,'gold_final_prompt_tokens_exact':0,'real_final_prompt_tokens_unknown':True}
  for r in rs:
   prompt_budgets[split]['tool_prompt_tokens_exact']+=len(tok.encode(funcs['conversation_text'](tok,r['messages'][:2],True),add_special_tokens=False))
   prompt_budgets[split]['gold_final_prompt_tokens_exact']+=len(tok.encode(funcs['conversation_text'](tok,r['messages'][:4],True),add_special_tokens=False))
 adaptive=[m for m in METHODS if m in ('p11_priority','layer_replay','no_priority','no_layer')]
 diag_episodes=0
 for c in cohort:
  if c['method'] in adaptive:
   for stage in (1,2):diag_episodes+=2*sum(r['continual_group'] in c['order'][:stage] for r in diag)
 mc=read(Path(CONFIG['model_name_or_path'])/'config.json');dim=mc['hidden_size'];hd=mc.get('head_dim',dim//mc['num_attention_heads']);q=hd*mc['num_attention_heads'];kv=hd*mc.get('num_key_value_heads',mc['num_attention_heads']);inter=mc['intermediate_size'];layers=mc['num_hidden_layers'];rank=8
 n=layers*rank*((dim+q)+2*(dim+kv)+(q+dim)+3*(dim+inter))
 full_ref=[]
 for order in itertools.permutations(GROUPS):
  for seed in SEEDS:
   old=[];cost_i=cost_s=0
   for g in order:
    cost_i+=STEPS*sum(features[r['episode_id']]['input_tokens'] for r in old)
    cost_s+=STEPS*sum(features[r['episode_id']]['supervised_tokens']['both'] for r in old)
    old+=load_group(rr['train'],g)
   full_ref.append({'order':order,'seed':seed,'extra_replay_input_exact':cost_i,'extra_replay_supervision_exact':cost_s,'optimizer_updates':3*STEPS})
 # 4 adapters plus 3 end-stage optimizer states per trajectory. Emergency snapshots are additive.
 disk_base=len(cohort)*(4*4*n+3*8*n)
 budget={'budget_kind':{'new_stream':'exact matched within each order/seed across all methods; caps across groups; actual tokens NOT all equal',
    'optimizer_updates':'exact 128/stage, 384/trajectory','replay':'dual HARD CAPS per update; actual chosen rows/masks and utilization logged at runtime; no truncation or semantic/answer clipping',
    'tolerance':'none silently applied; cap != exact. Cross-stage residual label-ratio/length utilization confounds reported.',
    'seqft':'NO replay, so NOT matched total supervision to replay arms','full_replay':'optional resource-intensive reference; not performance upper bound'},
  'new_data_ledger':ledger,'corpus_tokenized':corpus,'eval_prompt_tokens':prompt_budgets,
  'required_methods':METHODS,'orders':6,'seeds':SEEDS,'trajectories_per_method':18,'required_trajectories':len(cohort),
  'optimizer_updates_required_exact':len(cohort)*3*STEPS,
  'new_input_tokens_required_exact':sum(c['new_input_tokens_exact'] for c in cohort),
  'new_supervised_tokens_required_exact':sum(c['new_supervised_tokens_exact'] for c in cohort),
  'replay_input_tokens_required_cap':sum(c['replay_input_cap'] for c in cohort),'replay_supervised_tokens_required_cap':sum(c['replay_supervised_cap'] for c in cohort),
  'dev_checkpoints_per_trajectory':4,'test_checkpoints_per_trajectory':4,
  'dev_episodes':len(cohort)*4*len(rr['dev']),'test_episodes':len(cohort)*4*len(rr['test']),
  'dev_generation_requests':len(cohort)*4*len(rr['dev'])*3,'test_generation_requests':len(cohort)*4*len(rr['test'])*3,
  'diagnostic_dev_episodes_additional_cap':diag_episodes,'diagnostic_dev_generation_requests_cap':diag_episodes*3,
  'teacher_forced_train_probe_forward_sequences':len(cohort)*4*len(trainprobe),
  'diagnostic_extra_backward':0,'diagnostic_extra_optimizer_updates':0,'virtual_update_or_gradient_conflict_runs':0,
  'generation_output_cap_tokens_each_episode':128+256+256,
  'required_generation_output_tokens_cap':(len(cohort)*8*348+diag_episodes)*(128+256+256),
  'runtime_wall_time_GPU_hours':None,'wall_time_note':'NO GPU timing measured; do not extrapolate invented hours. Per-call wall/forward/backward counts will be logged.',
  'full_replay_optional_trajectories':18,'full_replay_optional_exact_costs':full_ref,'full_replay_in_default_cohort':False,
  'lora_trainable_parameters_structure_estimate':n,'lora_parameter_note':'architecture arithmetic from local config; actual trainable numel must equal at GPU startup; not measured GPU allocation',
  'disk_adapter_optimizer_payload_estimate_bytes':disk_base,'disk_conservative_reserve_bytes':disk_base*2+2_000_000_000,
  'disk_free_bytes_measured_now':shutil.disk_usage(ROOT).free,'disk_strategy':'one base model in existing model dir; 4 adapter checkpoints + 3 optimizer/RNG states/trajectory, no per-step model copies; prediction JSONL stores IDs/raw answers/usages, not repeated prompts/logits. No old files deleted. Emergency snapshots add cost.',
  'tokenizer_cpu_elapsed_seconds_measured_first_prepare':round(elapsed,3)}
 # CPU timing differs across invocations: freeze scientific ledger, retain first measured elapsed separately.
 if (RUN/'budget_ledger.json').exists():
  prior_budget=read(RUN/'budget_ledger.json')
  for k in ('tokenizer_cpu_elapsed_seconds_measured_first_prepare','disk_free_bytes_measured_now'):budget[k]=prior_budget[k]
 write(RUN/'budget_ledger.json',budget,True)
 detail=[]
 for order in itertools.permutations(GROUPS):
  stages=[]
  for j,g in enumerate(order):
   subset=[r for r in diag if r['continual_group'] in order[:j]]
   ti=gf=0
   for r in subset:
    ti+=len(tok.encode(funcs['conversation_text'](tok,r['messages'][:2],True),add_special_tokens=False))
    gf+=len(tok.encode(funcs['conversation_text'](tok,r['messages'][:4],True),add_special_tokens=False))
   stages.append({'stage':j+1,'new_group':g,'diagnostic_refreshes':2 if j else 0,'old_dev_subset_rows':len(subset),
    'extra_generate_requests_cap':6*len(subset),'extra_tool_prompt_tokens_exact':2*ti,'extra_gold_final_prompt_tokens_exact':2*gf,
    'extra_real_final_prompt_tokens':'unknown until predicted tool executes; context ceiling 4096 incl output',
    'extra_backward':0,'extra_optimizer_updates':0,'GPU_wall_seconds':None})
  detail.append({'order':order,'per_adaptive_trajectory_stages':stages})
 write(RUN/'diagnostic_budget_detail.json',{'per_order':detail,'adaptive_methods':adaptive,'fixed_dev_subset_rows':len(diag),
  'train_loss_forward_tokens_required_exact':len(cohort)*4*sum(features[r['episode_id']]['input_tokens'] for r in trainprobe),
  'train_loss_probe_rows_per_node':len(trainprobe),'train_loss_backward':0,
  'optional_full_extra_dev_requests':18*4*348*3,'optional_full_extra_test_requests':18*4*348*3,
  'optional_full_extra_teacher_forced_sequences':18*4*len(trainprobe),
  'optional_full_extra_disk_payload_estimate_bytes':18*(4*4*n+3*8*n),
  'no_actual_GPU_wall_measurement':True},True)
 tokenfiles={p.name:h(p.read_bytes()) for p in Path(CONFIG['model_name_or_path']).glob('*') if p.name in ('tokenizer.json','tokenizer_config.json','vocab.json','merges.txt','special_tokens_map.json','config.json')}
 write(RUN/'tokenizer_identity.json',{'local_dir':CONFIG['model_name_or_path'],'files':tokenfiles,'no_weight_files_read':True,'features_sha256':h(b),'mask_definition':'unchanged existing assistant_spans; full call turn vs full final turn including im_end; no token truncation'},True)
 protect();write(RUN/'protected_after.json',before,True)
 write(RUN/'milestone_token_budget.json',{'status':'PASS','templates_per_split':read(DATA/'manifest.json')['template_texts_per_split'],'train_groups':{g:ledger['17'][g] for g in GROUPS},'required_trajectories':len(cohort),'gpu_started':False,'v2_manifest_sha256':h((DATA/'manifest.json').read_bytes())})
 print(cj({'CPU_PREPARE':'PASS','group_counts':{g:ledger['17'][g] for g in GROUPS},'v2_manifest':h((DATA/'manifest.json').read_bytes()),'trajectories':len(cohort),'max_tokens':corpus,'diagnostic_size':len(diag)}))

def finalize():
 protect();assert read(RUN/'cpu_tests.json')['status']=='PASS'
 docs=['P14_V2_REVISION_20261119_ZH.md','P15_PREREG_20261119_ZH.md','P15_ALGORITHM_SPEC_20261119_ZH.md']
 refs=[ROOT/x for x in docs]+list(CODE.glob('*.py'))+[DATA/'manifest.json']+[RUN/n for n in ['config.json','cohort.json','optional_full_replay_cohort.json','diagnostic_budget_detail.json','new_streams.json','budget_ledger.json','diagnostic_subsets.json','operation_pair_conditions.json','operation_pair_CPU_schedules.json','token_features.json.gz','tokenizer_identity.json','base_model_identity.json','protected_before.json','cpu_tests.json']]
 write(RUN/'runtime_manifest.json',{'status':'FROZEN_NOT_STARTED','training_started':False,'default_cohort_trajectories':108,
     'files':{str(p.relative_to(ROOT)):h(p.read_bytes()) for p in sorted(refs)},'v1_manifest_sha256':h((V1/'manifest.json').read_bytes()),'v2_manifest_sha256':h((DATA/'manifest.json').read_bytes()),
     'STOP_policy':'sticky; no automatic clearing, including historical STOPs. Current phase does not authorize GPU start; requires separate parent launch approval artifact.'},True)
 install(RUN/'runtime_manifest.sha256',(h((RUN/'runtime_manifest.json').read_bytes())+'  runtime_manifest.json\n').encode())
 print(cj({'P15_RUNTIME_FROZEN':h((RUN/'runtime_manifest.json').read_bytes()),'GPU_started':False}))
if __name__=='__main__':
 if '--finalize' in sys.argv:finalize()
 else:prepare()
