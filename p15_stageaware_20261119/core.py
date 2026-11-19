"""P15 CPU-safe primitives. No model imports; independent continual_group axis."""
import ast,collections,copy,hashlib,itertools,json,math,random,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.dont_write_bytecode=True
V1=ROOT/'data_ext_p14_eval_protocol';DATA=ROOT/'data_ext_p14_eval_protocol_v2'
CODE=ROOT/'p15_stageaware_20261119';RUN=ROOT/'runs_ext_p15_stageaware_20261119'
GROUPS=['counts','locations','fields'];SEEDS=[17,29,43]
METHODS=['seqft','uniform','p11_priority','layer_replay','no_priority','no_layer']
STEPS=128;NEW_CAP=(8192,1024);REPLAY_CAP=(4096,512)
SKILLS=['cal.count_date','cal.count_month','cal.list_locations','cal.extract_title_sorted','cal.extract_location_sorted','cal.extract_id_sorted','cal.extract_start_sorted']
CONFIG={'model_name_or_path':'/home/egret/models/Qwen3-0.6B','trust_remote_code':False,
 'quantization':{'bnb_4bit_compute_dtype':'fp16'},
 'lora':{'r':8,'alpha':16,'dropout':0.0,'target_modules':['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj']},
 'training':{'learning_rate':1e-4,'gradient_checkpointing':True},
 'optimizer':'torch.optim.AdamW trainable adapter only, fp32 parameters/moments; betas=(.9,.999),eps=1e-8,weight_decay=0',
 'steps_per_stage':STEPS,'new_caps_per_update':NEW_CAP,'replay_caps_per_update':REPLAY_CAP,
 'diagnostic_updates':[0,64],'max_sequence_length_no_truncation':4096,
 'generation':{'batch_size':1,'tool_max_new_tokens':128,'answer_max_new_tokens':256,'do_sample':False},
 'method_hyperparameters':{'uniform_floor':.25,'priority_gain':2.0,'absolute_error_mix':.25,'component_tie':'both'},
 'stage_optimizer':'persist across all three stages; no optimizer recreation; no scheduler',
 'gradient_normalization':'new and replay label-token sums divided by their combined actual supervised tokens at each optimizer update',
 'optional_full_replay':'not in default cohort; all old rows once at EACH optimizer update, no replay caps'}
def cj(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def h(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def rows(split):
 assert split in ('train','dev','test')
 return [json.loads(s) for s in (DATA/split/'rows.jsonl').read_text().splitlines() if s]
def write(p,x,freeze=False):
 p=Path(p);b=(json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode();install(p,b,freeze)
def install(p,b,freeze=True):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 if freeze and p.exists():assert p.read_bytes()==b,'Do not overwrite frozen file '+str(p)
 else:p.write_bytes(b)
def source_function(path,name):
 node=next(n for n in ast.parse(Path(path).read_text()).body if isinstance(n,ast.FunctionDef) and n.name==name)
 node.returns=None
 for a in node.args.args:a.annotation=None
 ns={};exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),ns);return ns[name]
project=source_function(ROOT/'fac_tinyagent/research_data.py','project_answer')
p11_classify=source_function(ROOT/'fac_tinyagent/p11_eaar_v1_20261118.py','classify_skill')
def tokenizer_functions():
 # Execute unchanged CPU-pure helper definitions, not Dataset's optional torch import.
 src=ROOT/'fac_tinyagent/sft/dataset.py';tree=ast.parse(src.read_text())
 keep=[n for n in tree.body if isinstance(n,(ast.ImportFrom,ast.Assign,ast.FunctionDef)) and not(isinstance(n,ast.ImportFrom) and n.module not in ('typing','__future__'))]
 ns={};exec(compile(ast.Module(body=keep,type_ignores=[]),str(src),'exec'),ns);return ns

def encode_all(tokenizer,rr):
 funcs=tokenizer_functions();out={}
 for r in rr:
  full=funcs['conversation_text'](tokenizer,r['messages'],False)
  ids=tokenizer(full,add_special_tokens=False,return_attention_mask=False)['input_ids']
  assert len(ids)<=4096,(r['episode_id'],len(ids),'NO semantic truncation allowed')
  original=funcs['tokenize_episode'](r,tokenizer,len(ids)+1)
  assert original['input_ids']==ids
  spans=funcs['assistant_spans'](ids,tokenizer);assert len(spans)==2
  masks={}
  for mode,ss in [('call',spans[:1]),('final',spans[1:]),('both',spans)]:
   labels=[-100]*len(ids)
   for a,b in ss:
    for j in range(a,b):labels[j]=ids[j]
   assert sum(x!=-100 for x in labels)>0
   masks[mode]=labels
  assert masks['both']==original['labels']
  out[r['episode_id']]={'input_ids':ids,'masks':masks,'input_tokens':len(ids),'supervised_tokens':{k:sum(x!=-100 for x in v) for k,v in masks.items()}}
 return out

class BoundCalendar:
 def __init__(self,split,path=None):
  from fac_tinyagent.tools.calendar_tools import build_calendar_registry
  self.split=split;self.path=(DATA/'fixtures'/f'{split}.json').resolve()
  if path is not None and Path(path).resolve()!=self.path:raise ValueError('split-fixture mismatch')
  # Hash binding also detects a wrong fixture copied to the expected filename.
  man=read(DATA/'manifest.json') if (DATA/'manifest.json').exists() else None
  if man:
   want=man['files'][str(self.path.relative_to(ROOT))]
   if h(self.path.read_bytes())!=want:raise ValueError('fixture hash mismatch')
  self.registry=build_calendar_registry(str(self.path))
 def execute(self,r,tool=None,args=None):
  if r['split']!=self.split or (ROOT/r['fixture_path']).resolve()!=self.path:raise ValueError('row-fixture binding mismatch')
  return self.registry.execute(tool or r['expected_tool'],r['expected_arguments'] if args is None else args)

def load_group(rr,group):
 out=[r for r in rr if r['continual_group']==group]
 assert out and all(r['tool_family']=='calendar' for r in out)
 return out

def new_stream(rr,features,seed,group,steps=STEPS,caps=NEW_CAP):
 """Same exact whole-example stream for every method/order at given seed/group."""
 pool=load_group(rr,group);rng=random.Random(seed+GROUPS.index(group)*100003)
 order=list(pool);rng.shuffle(order);cursor=0;result=[]
 for step in range(steps):
  batch=[];ni=ns=0
  while True:
   if cursor>=len(order):order=list(pool);rng.shuffle(order);cursor=0
   r=order[cursor];f=features[r['episode_id']];i=f['input_tokens'];s=f['supervised_tokens']['both']
   assert i<=caps[0] and s<=caps[1]
   if ni+i>caps[0] or ns+s>caps[1]:break
   cursor+=1;batch.append(r['episode_id']);ni+=i;ns+=s
  assert batch
  result.append({'ids':batch,'input_tokens':ni,'supervised_tokens':ns})
 assert set(r['episode_id'] for r in pool)<=set(itertools.chain.from_iterable(b['ids'] for b in result)), 'Not all new rows exposed; fix pre-training budget before freeze'
 return result

def fixed_diag(rr):
 chosen=[]
 for s in SKILLS:
  rs=sorted([r for r in rr if r['skill']==s],key=lambda r:r['episode_id'])
  if s=='cal.count_date':
   for wording in sorted({r['strata']['count_wording'] for r in rs}):chosen += [r for r in rs if r['strata']['count_wording']==wording][:2]
  elif s=='cal.list_locations':
   for c in sorted({r['strata']['case'] for r in rs}):chosen += [r for r in rs if r['strata']['case']==c][:1]
  else:chosen+=rs # all 12 for each other skill, never a four-probe mastery decision
 return chosen

def profile(records):
 out={}
 for s in sorted({r['skill'] for r in records}):
  rr=[r for r in records if r['skill']==s]
  out[s]={k:sum(float(r[k]) for r in rr)/len(rr) for k in ['tool_correct','arguments_correct','execution_success','final_correct','gold_final_correct','tool_args_core','joint_success']}
  out[s]['n']=len(rr)
 return out

def priority(method,skills,current,reference):
 weights={};components={};details={}
 for s in sorted(skills):
  c=current[s];b=reference.get(s,c)
  deficits={k:max(0,b[k]-c[k])+.25*(1-c[k]) for k in ('tool_correct','arguments_correct','gold_final_correct')}
  route=max(deficits['tool_correct'],deficits['arguments_correct']);final=deficits['gold_final_correct']
  if method=='p11_priority':
   legacy=p11_classify({'skill':s,'joint':c['joint_success'],'tool':c['tool_correct'],'args':c['arguments_correct'],'execution':c['execution_success'],'final':c['final_correct']},1)
   weights[s]=1+legacy['priority'];details[s]={'legacy':legacy,'caution':'legacy true_forgetting_prior is low accuracy, NOT proof of forgetting'}
  elif method in ('layer_replay','no_layer'):weights[s]=1+2*(route+final);details[s]=deficits
  else:weights[s]=1.0;details[s]=deficits
  components[s]='both'
  if method in ('layer_replay','no_priority'):
   components[s]='call' if route>final+1e-12 else 'final' if final>route+1e-12 else 'both'
 total=sum(weights.values())
 probs={s:w/total for s,w in weights.items()}
 if method in ('layer_replay','no_layer'):probs={s:.25/len(probs)+.75*v for s,v in probs.items()}
 return {'weights':probs,'components':components,'details':details}

def choose_replay(method,pool,features,state,rng,caps=REPLAY_CAP):
 assert all(r['split']=='train' and r['replay_eligible'] for r in pool),'Replay can only read TRAIN candidates'
 if not pool or method=='seqft':return []
 if method=='full_replay':return [(r['episode_id'],'both') for r in sorted(pool,key=lambda r:r['episode_id'])]
 by=collections.defaultdict(list)
 for r in pool:by[r['skill']].append(r)
 actual_i=actual_s=0;chosen=[]
 while True:
  feasible={}
  for skill,rs in by.items():
   mode=state['components'][skill]
   valid=[r for r in rs if features[r['episode_id']]['input_tokens']+actual_i<=caps[0] and features[r['episode_id']]['supervised_tokens'][mode]+actual_s<=caps[1]]
   if valid:feasible[skill]=valid
  if not feasible:break
  ss=sorted(feasible);w=[state['weights'][s] for s in ss];skill=rng.choices(ss,weights=w,k=1)[0]
  r=rng.choice(feasible[skill]);eid=r['episode_id'];mode=state['components'][skill]
  chosen.append((eid,mode));actual_i+=features[eid]['input_tokens'];actual_s+=features[eid]['supervised_tokens'][mode]
 return chosen

OP_PAIRS=[('month_extract','cal.count_month','cal.extract_title_sorted','low_hypothesis'),
 ('date_extract','cal.count_date','cal.extract_title_sorted','medium_hypothesis'),
 ('unique_retain','cal.list_locations','cal.extract_location_sorted','high_hypothesis'),
 ('day_month','cal.count_date','cal.count_month','routing_separate_hypothesis')]
def operation_pairs(train,features):
 result=[]
 for name,a,b,label in OP_PAIRS:
  ra=[r for r in train if r['skill']==a];rb=[r for r in train if r['skill']==b]
  # Whole-example queues under identical dual caps/updates; actual I/S utilization remains measured, not magically equal.
  result.append({'id':name,'left_skill':a,'right_skill':b,'label':label,'observed_strength':None,
   'left_ids':[r['episode_id'] for r in ra],'right_ids':[r['episode_id'] for r in rb],
   'shared_tool':ra[0]['expected_tool']==rb[0]['expected_tool'],'updates_each':STEPS,'new_input_cap':NEW_CAP[0],
   'new_supervised_cap':NEW_CAP[1],'directions':['left_then_right','right_then_left'],
   'gpu_pair_experiment_started':False,'causal_claim_allowed':False,
   'execution_condition':'Filter these exact IDs, use same seed/initial state/optimizer and caps; schedule runnable by pair_stream; report achieved dual-token budgets before any strength claim.'})
 return result

def pair_stream(ids,lookup,features,seed,steps=STEPS):
 pool=[lookup[e] for e in ids];rng=random.Random(seed);order=list(pool);rng.shuffle(order);cursor=0;out=[]
 for t in range(steps):
  batch=[];i=s=0
  while True:
   if cursor==len(order):rng.shuffle(order);cursor=0
   eid=order[cursor]['episode_id'];f=features[eid];a=f['input_tokens'];b=f['supervised_tokens']['both']
   if i+a>NEW_CAP[0] or s+b>NEW_CAP[1]:break
   cursor+=1;batch.append(eid);i+=a;s+=b
  assert batch;out.append({'ids':batch,'input_tokens':i,'supervised_tokens':s})
 return out

def aggregate(records):
 p=profile(records);metric=['tool_correct','arguments_correct','execution_success','final_correct','gold_final_correct','tool_args_core','joint_success']
 groups={s:next(r['continual_group'] for r in records if r['skill']==s) for s in p}
 return {'n':len(records),'skills':p,
  'skill_macro':{k:sum(p[s][k] for s in p)/len(p) for k in metric},
  'stage_macro':{k:sum(sum(p[s][k] for s in p if groups[s]==g)/sum(groups[s]==g for s in p) for g in set(groups.values()))/len(set(groups.values())) for k in metric},
  'micro':{k:sum(r[k] for r in records)/len(records) for k in metric}}

def longitudinal(nodes,order,lookup):
 # nodes = baseline plus end of every trained stage. Compare SAME episode IDs.
 maps=[{r['episode_id']:r for r in n} for n in nodes];result={}
 for metric in ('tool_correct','arguments_correct','execution_success','final_correct','gold_final_correct','tool_args_core','joint_success'):
  at_risk=lost=0;bw=[];fw=[]
  for j,g in enumerate(order):
   ids=[e for e in maps[0] if lookup[e]['continual_group']==g]
   score=lambda t:sum(maps[t][e][metric] for e in ids)/len(ids)
   if j<len(order)-1:
    at_risk+=sum(maps[j+1][e][metric] for e in ids)
    lost+=sum(maps[j+1][e][metric] and not maps[-1][e][metric] for e in ids)
    bw.append(score(len(order))-score(j+1))
   if j>0:fw.append(score(j)-score(0))
  per_skill={}
  if all('skill' in r for r in nodes[0]):
   for skill in sorted({r['skill'] for r in nodes[0]}):
    ids=[r['episode_id'] for r in nodes[0] if r['skill']==skill]
    g=lookup[ids[0]]['continual_group'];j=order.index(g)
    score=lambda t:sum(maps[t][e][metric] for e in ids)/len(ids)
    risk=sum(maps[j+1][e][metric] for e in ids)
    losses=sum(maps[j+1][e][metric] and not maps[-1][e][metric] for e in ids)
    transitions=[]
    for t in range(j+2,len(nodes)):
     ar=sum(maps[t-1][e][metric] for e in ids)
     down=sum(maps[t-1][e][metric] and not maps[t][e][metric] for e in ids)
     up=sum(not maps[t-1][e][metric] and maps[t][e][metric] for e in ids)
     transitions.append({'after_stage':t,'at_risk':ar,'lost':down,'gained':up,'forgetting_rate':down/ar if ar else None})
    per_skill[skill]={'group':g,'n':len(ids),'stage_scores':[score(t) for t in range(len(nodes))],
     'baseline':score(0),'before_first_learning':score(j),'after_first_learning':score(j+1),
     'new_acquisition_gain':score(j+1)-score(j),'terminal':score(len(order)),
     'terminal_at_risk':risk,'terminal_lost':losses,'terminal_forgetting_rate':losses/risk if risk else None,
     'BWT':score(len(order))-score(j+1) if j<len(order)-1 else None,
     'FWT':score(j)-score(0) if j>0 else None,'old_skill_stage_transitions':transitions}
  bws=[v['BWT'] for v in per_skill.values() if v['BWT'] is not None];fws=[v['FWT'] for v in per_skill.values() if v['FWT'] is not None]
  result[metric]={'at_risk':at_risk,'lost':lost,'forgetting_rate':lost/at_risk if at_risk else None,
                  'BWT':sum(bw)/len(bw) if bw else None,'FWT':sum(fw)/len(fw) if fw else None,
                  'BWT_aggregation':'group macro, last group excluded','FWT_aggregation':'group macro, first group excluded',
                  'per_skill':per_skill,'BWT_skill_macro':sum(bws)/len(bws) if bws else None,'FWT_skill_macro':sum(fws)/len(fws) if fws else None}
 return result
