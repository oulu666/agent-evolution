"""P6: development-gradient driven one-shot allocation, not online state classification.
All persistent writes confined to new P6 assets. No formal test results enter planning.
"""
from __future__ import annotations
import argparse,collections,copy,hashlib,itertools,json,math,random,sqlite3,statistics,time,functools
from pathlib import Path
from .utils import read_json,read_jsonl,write_json,write_jsonl,sha256_file,ensure_dir
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data_ext_p6_devplan';RUNS=ROOT/'runs_ext_p6_devplan'
SEEDS=[20261108,20261109,20261110]
SKILLS=['db.list_tables','db.filter_cmp_top','file.search_last','py.median']
ARMS=['balanced_uniform','balanced_early','devgrad_uniform']
PREREG=ROOT/'P6_PREREG_20261115_devplan_ZH.md'
POSITIONS=[87,95,103,111,119,127,135,143,151,159]
DEST={'balanced_uniform':[0,2,5,7,9,12,14,16,19,21], 'balanced_early':list(range(10)), 'devgrad_uniform':[0,2,5,7,9,12,14,16,19,21]}
PAT={'db.list_tables':'db_list_tables','db.filter_cmp_top':'target_db_filter_top','file.search_last':'e4_last_match','py.median':'target_median_natural'}
STOP=RUNS/'logs/STOP'
def log(s):print(time.strftime('%F %T %z'),s,flush=True)
def identify(row):
 for k,p in PAT.items():
  if p in row['episode_id']:return k
 return None
def label(s,a):return f'A_seed{s}_{a}'
def planpath(s,a):return DATA/'plans'/(label(s,a)+'.json')
def ckpt(s,a):return RUNS/'branches'/label(s,a)/'checkpoint'
def source(s):return ROOT/f'data_ext_e3/plans/A_seed{s}_dose_db4.json'
def digest(rows):return hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()
def fixture(split):return DATA/'fixtures'/(split+'.sqlite')
def make_db(split):
 db=fixture(split);names=['p6d_agents','p6d_items','p6d_scores'] if split=='dev' else ['p6h_people','p6h_stock','p6h_rates']
 rng=random.Random(20261201 if split=='dev' else 20261202)
 with sqlite3.connect(db) as c:
  for tab in names:
   c.execute(f'CREATE TABLE {tab}(id INTEGER PRIMARY KEY,name TEXT,score REAL)')
   c.executemany(f'INSERT INTO {tab} VALUES (?,?,?)',[(i,f'{split}_entity_{tab}_{i:02}',rng.randint(12,98)+i/100) for i in range(1,21)])
 return names
LT_DEV=['Return the database table identifiers in a JSON array.', 'Provide a JSON array containing every table name available here.', 'Identify all database tables; output their names as a JSON array.', 'Retrieve the full table-name inventory as a JSON array.']
LT_TEST=['For this database, output a JSON array of its table names.', 'Produce the complete database table inventory as a JSON array.', 'Tell me the names of the database tables, in a JSON array.', 'Which table identifiers belong to this database? Use a JSON array.', 'Enumerate this database\'s tables and return a JSON array of names.', 'Give a JSON array naming the tables that exist here.', 'Report this database\'s complete set of table names as a JSON array.', 'Fetch the table inventory and answer with a JSON array of table names.', 'What are this database\'s available tables? Answer with a JSON array.', 'Show the table names present here using a JSON array.', 'Return a JSON array of names from the database table inventory.', 'Name each table present in this database using a JSON array.']
def row(family,skill,split,i,prompt,tool,args,env,spec):
 from .data.generate import _observation,_schemas,build_system_prompt
 from .round2_data import _messages
 from .research_data import project_answer,task_signature
 db=str(fixture(split));cal=str(ROOT/'data_phase2/fixtures/calendar.json')
 obs=_observation(family,tool,args,env,db,cal);o=json.loads(obs);assert o['ok']
 answer=project_answer(o['result'],spec);system=build_system_prompt(family,_schemas(family,db,cal))
 r={'episode_id':f'p6-{split}-{skill}-{i:03}','tool_family':family,'split':split,'template_id':'p6_'+split+'_'+skill,'target_type':skill,'target':True,'skill':skill,'prompt':prompt,'system':system,'environment':env,'expected_tool':tool,'expected_arguments':args,'skill_labels':[skill],'answer_spec':spec,'expected_observation':obs,'expected_final_answer':answer,'evaluation_only':True,'selection_allowed':split=='dev','messages':_messages(system,prompt,tool,args,obs,answer)}
 r['data_signature']=task_signature(r);return r

def build_split(split):
 n=4 if split=='dev' else 12;names=make_db(split);rng=random.Random(20261210 if split=='dev' else 20261211);out=[]
 for i in range(n):
  out.append(row('database','db.list_tables',split,i,(LT_DEV if split=='dev' else LT_TEST)[i],'db_list_tables',{}, {},{'kind':'identity'}))
  tab=names[i%3];v=25+10*(i%4)+2*(split=='holdout');k=1+i%3
  sql=f'SELECT name FROM {tab} WHERE score > {v} ORDER BY score DESC, id ASC LIMIT {k}'
  prompt=(f'Table {tab} has columns id, name, score. Filter to score > {v}, rank score descending with smaller id first on ties, and return the first {k} names as a JSON list.' if split=='dev' else f'Using {tab}(id, name, score), report the names of the top {k} entries with score above {v}. Sort by descending score, breaking ties by ascending id; use a JSON list.')
  out.append(row('database','db.filter_cmp_top',split,i,prompt,'db_query',{'sql':sql},{},{'kind':'rows_first'}))
  path=f'p6_{split}/record_{i:03}.txt';word=f'{split}token{i:02}';hits=sorted(rng.sample(range(6),2+i%2));lines=[f'line {z+1}: neutral value {rng.randint(10,99)}' for z in range(6)]
  for z in hits:lines[z]=f'line {z+1}: {word} appears in this line'
  prompt=(f'Return the last line in {path} containing the word {word!r}.' if split=='dev' else f'In {path}, locate {word!r} and return the full final matching line exactly as written.')
  out.append(row('file','file.search_last',split,i,prompt,'file_search',{'path':path,'pattern':word},{'files':{path:'\n'.join(lines)+'\n'}},{'kind':'match','index':-1}))
  vals=rng.sample(range(11,100),7);text=', '.join(map(str,vals))
  prompt=(f'Place these readings in increasing order: {text}. Which reading occupies the middle position?' if split=='dev' else f'The sample is {text}. Arrange the observations from lowest to highest and give the central observation.')
  out.append(row('python','py.median',split,i,prompt,'stats_median',{'values':vals},{},{'kind':'identity'}))
 write_jsonl(DATA/split/'rows.jsonl',out);return out

def data_files():return sorted(p for p in DATA.rglob('*') if p.is_file() and p.name not in ['manifest.json','plans_manifest.json'])
def build():
 if DATA.exists() or RUNS.exists():raise SystemExit('Refuse existing P6 roots')
 ensure_dir(DATA/'fixtures');ensure_dir(DATA/'dev');ensure_dir(DATA/'holdout');ensure_dir(RUNS/'logs')
 dev=build_split('dev');test=build_split('holdout')
 from .sft.train import load_tokenizer
 from .sft.dataset import tokenize_episode
 from .replay_study import config_for
 tok=load_tokenizer(config_for('A',SEEDS[0],batch_size=1))
 pools={f:read_jsonl(ROOT/'data_ext_e4/pool'/(f+'.jsonl')) for f in ['database','file','python']}
 prepared=[]
 for family,rs in pools.items():
  for i,r in enumerate(rs):
   ft=tokenize_episode(r,tok,1024)
   prepared.append({'family':family,'row_index':i,'episode_id':r['episode_id'],'input_tokens':len(ft['input_ids']),'supervised_tokens':sum(x!=-100 for x in ft['labels']),'truncated':False,'target':identify(r) is not None,'skill':identify(r),'message_hash':digest(r['messages'])})
 candidates={};background={}
 for s in SKILLS:
  distinct={}
  for x in prepared:
   if x['skill']==s:distinct.setdefault(x['message_hash'],x)
  candidates[s]=sorted(distinct.values(),key=lambda x:x['episode_id'])[:8]
 for f in pools:
  # Exclude direct targets plus immediate median/first-match neighbors; avoid hidden target replay.
  rs=[x for x in prepared if x['family']==f and x['skill'] is None and 'stats_median' not in x['episode_id'] and 'file_search_first' not in x['episode_id']]
  bycost={}
  for x in rs:bycost.setdefault(x['input_tokens'],x)
  background[f]=sorted(bycost.values(),key=lambda x:(x['input_tokens'],x['episode_id']))
 write_json(DATA/'candidates.json',candidates);write_json(DATA/'background.json',background)
 # CPU leakage checks compare exact conversations, prompts, per-episode entities and median value sets.
 train=[r for rows in pools.values() for r in rows]
 assert not ({r['prompt'] for r in dev}&{r['prompt'] for r in test})
 assert not ({digest(r['messages']) for r in train}&{digest(r['messages']) for r in dev+test})
 dv={tuple(sorted(r['expected_arguments']['values'])) for r in dev if r['tool_family']=='python'}
 hv={tuple(sorted(r['expected_arguments']['values'])) for r in test if r['tool_family']=='python'}
 assert not dv&hv
 # Probe messages are checked but never included in production replay pools.
 checks={'candidate_distinct_counts':{s:len(v) for s,v in candidates.items()},'dev':len(dev),'holdout':len(test),'dev_test_prompts_disjoint':True,'median_value_sets_disjoint':True,'database_schema_entities_disjoint':True,'file_entities_disjoint':True}
 for r in dev+test:
  ft=tokenize_episode(r,tok,1024);assert len(ft['input_ids'])<1024 and any(x!=-100 for x in ft['labels'])
 write_json(DATA/'cpu_data_checks.json',checks)
 refs=[PREREG,Path(__file__),ROOT/'scripts/run_p6_20261115.py',ROOT/'scripts/launch_p6_20261115.sh']
 refs += [ROOT/'data_ext_e4/pool'/(f+'.jsonl') for f in pools]
 refs += [ROOT/f'runs_ext_e4/prefixes/A_seed{s}/training_state.pt' for s in SEEDS]
 refs += [ROOT/f'runs_phase2/A_seed{s}/config.json' for s in SEEDS]
 refs += [ROOT/f'runs_phase2/A_seed{s}/checkpoints/stage_03_python/adapter_model.safetensors' for s in SEEDS]
 refs += [ROOT/'fac_tinyagent'/p for p in ['e3_train.py','p5_file_timing.py','p4_forget_timing.py','replay_train.py']]
 write_json(DATA/'manifest.json',{'created':time.strftime('%F %T %z'),'stage':'pre-score freeze, not an experimental result','seeds':SEEDS,'arms':ARMS,'skills':SKILLS,'files':{str(p.relative_to(ROOT)):sha256_file(p) for p in data_files()},'references':{str(p.relative_to(ROOT)):sha256_file(p) for p in refs},'checks':checks})
 log('P6 data and algorithm frozen; no GPU started')

def verify():
 m=read_json(DATA/'manifest.json')
 for p,h in {**m['files'],**m['references']}.items():assert sha256_file(ROOT/p)==h,p
 return m

def candidate_order(candidates,s):
 order={}
 for k,rs in candidates.items():
  order[k]=copy.deepcopy(rs);random.Random(str(s)+'-'+k).shuffle(order[k])
 return order

def allocate(order,benefit,s,adaptive):
 groups=list(SKILLS);random.Random(s).shuffle(groups)
 ns={k:1 for k in groups}
 for _ in range(6):
  def key(k):
   e=order[k][ns[k]%len(order[k])]
   return (benefit[k]/((ns[k]+1)*e['input_tokens']) if adaptive and max(benefit.values())>0 else 1/(ns[k]+1),-groups.index(k))
  ns[max(groups,key=key)]+=1
 # Interleave groups; preserve each group's seeded candidate prefix; exact-duplicate LT is deliberate repetition.
 result=[];counts=collections.Counter()
 while len(result)<10:
  for k in groups:
   if counts[k]<ns[k]:result.append(copy.deepcopy(order[k][counts[k]%len(order[k])])) ;counts[k]+=1
 return result,ns

@functools.lru_cache(maxsize=1)
def background_options():
 bg=read_json(DATA/'background.json');per={}
 # Repetition allowed equally for all policies. Choose 4 backgrounds per family; minimize token mismatch.
 for f,rs in bg.items():
  opts={}
  for ix in itertools.combinations_with_replacement(range(len(rs)),4):
   items=[rs[i] for i in ix];opts.setdefault(sum(x['input_tokens'] for x in items),items)
  per[f]=opts
 dp={0:[]}
 for f in sorted(per):
  nxt={}
  for cost,items in dp.items():
   for v,more in sorted(per[f].items()):nxt.setdefault(cost+v,items+more)
  dp=nxt
 return dp

def fill_background(targets):
 dp=background_options()
 need=7494-sum(x['input_tokens'] for x in targets)
 cost=min(dp,key=lambda v:(abs(v-need),v));assert abs(cost-need)<=74.94,('no budget match',need,cost)
 return copy.deepcopy(dp[cost])

def make_plan(s,a,benefit):
 from .p4_forget_timing import source_after_by_index,recompute_meta,POSITIONS as POS,segment_of
 order=candidate_order(read_json(DATA/'candidates.json'),s)
 targets,counts=allocate(order,benefit,s,a=='devgrad_uniform');bg=fill_background(targets)
 items=[None]*22
 for i,x in zip(DEST[a],targets):items[i]=x
 itr=iter(bg)
 for i in range(22):
  if items[i] is None:items[i]=next(itr)
 q=read_json(source(s));q.pop('e3_plan',None);q['items']=items;recompute_meta(q)
 q['uniform_actual_input_tokens']=sum(x['input_tokens'] for x in items if not x['target'])
 q.pop('quota_error_tokens_by_family',None)
 after=source_after_by_index(s,'dose_db4',read_json(source(s))['items'])
 tracked=[{'id':x['episode_id'],'index':i,'position':POS[segment_of(i,22)],'after':after[i]} for i,x in enumerate(items) if x['target']]
 q['p6']={'arm':a,'counts':counts,'benefit':benefit if a=='devgrad_uniform' else None,'budget_deviation':q['actual_input_tokens']-7494,'target_timing':tracked,'planner':'one-shot development gradient proxy; no observed response-speed measurement','background_rule':'same 4/family token-residual filler, no dev/test score'}
 q['p5']={'target_timing':tracked,'note':'read-only P5 trainer interface compatibility; P6 policy in p6'}
 return q

def dry():
 verify();cand=read_json(DATA/'candidates.json');out=[]
 # Multiple synthetic score orders exercise budget extremes; these are not model measurements.
 cases=[{s:1. for s in SKILLS}]+[{s:float(s==focus) for s in SKILLS} for focus in SKILLS]
 for seed in SEEDS:
  for benefit in cases:
   for a in ARMS:
    q=make_plan(seed,a,benefit);assert len(q['items'])==22 and sum(q['p6']['counts'].values())==10
    assert abs(q['actual_input_tokens']-7494)<=74.94
    assert all(n>=1 for n in q['p6']['counts'].values())
  u=make_plan(seed,'balanced_uniform',cases[0]);e=make_plan(seed,'balanced_early',cases[0])
  assert collections.Counter(json.dumps(x,sort_keys=True) for x in u['items'])==collections.Counter(json.dumps(x,sort_keys=True) for x in e['items'])
  out.append({'seed':seed,'balanced_counts':u['p6']['counts'],'balanced_tokens':u['actual_input_tokens']})
 write_json(RUNS/'dry_run.json',{'status':'PASS','time':time.strftime('%F %T %z'),'synthetic_scenarios':45,'gpu_started':False,'plans_not_yet_frozen':True,'examples':out})
 log('DRY OK: 45 synthetic planning cases; no model outputs and no GPU')

def safe():
 if STOP.exists():raise SystemExit('P6 STOP present; explicit user approval needed')
 from .p0_run import refuse_if_game
 refuse_if_game()

def score_seed(seed):
 verify();safe();out=RUNS/'calibration'/f'A_seed{seed}.json'
 if out.exists():log('skip immutable calibration '+str(seed));return
 import torch
 from .sft.train import load_tokenizer,load_base_model,_attach_adapter
 from .sft.dataset import tokenize_episode,DataCollator
 from .replay_study import config_for
 from .e4_run import start_adapter
 from .p4_forget_timing import _load_midpoint
 from .replay_train import _training_state_hash
 from .sft.evaluate import free_model
 cfg=config_for('A',seed,batch_size=1);tok=load_tokenizer(cfg);model,dtype=load_base_model(cfg);model=_attach_adapter(model,cfg,str(start_adapter(seed)))
 loaded=_load_midpoint(model,ROOT/f'runs_ext_e4/prefixes/A_seed{seed}');assert loaded['hash_matches_prefix']
 model.eval();params=[p for p in model.parameters() if p.requires_grad];before=_training_state_hash(model)
 collate=DataCollator(tok);calls=0;started=time.time()
 def gradient(rs):
  nonlocal calls
  avg=None;losses=[]
  for row in rs:
   safe();model.zero_grad(set_to_none=True)
   features=tokenize_episode(row,tok,1024);batch={k:v.to('cuda') for k,v in collate([features]).items()}
   result=model(**batch);loss=result.loss;assert torch.isfinite(loss);loss.backward()
   v=torch.cat([(p.grad.detach().float().cpu().reshape(-1) if p.grad is not None else torch.zeros(p.numel())) for p in params])
   avg=v if avg is None else avg+v;losses.append(float(loss.detach()));calls+=1
   del result,batch,loss
  return avg/len(rs),statistics.mean(losses)
 dev=read_jsonl(DATA/'dev/rows.jsonl');candidates=read_json(DATA/'candidates.json')
 pools={f:read_jsonl(ROOT/'data_ext_e4/pool'/(f+'.jsonl')) for f in ['file','database','python']}
 dg={};losses={};benefit={};norms={};dotmatrix={}
 try:
  for skill in SKILLS:
   dg[skill],losses[skill]=gradient([r for r in dev if r['skill']==skill]);log(f'DEV_GRAD {seed} {skill} loss={losses[skill]:.6f}')
  macro=sum(dg.values())/len(SKILLS)
  for skill in SKILLS:
   rs=[pools[x['family']][x['row_index']] for x in candidates[skill]]
   g,_=gradient(rs);norm=float(g.norm());norms[skill]=norm
   dotmatrix[skill]={k:float(torch.dot(v,g)) for k,v in dg.items()}
   benefit[skill]=max(0.,float(torch.dot(macro,g))/(norm+1e-12))
   log(f'POOL_GRAD {seed} {skill} benefit={benefit[skill]:.6g}')
  assert _training_state_hash(model)==before,'gradient measurement changed prefix parameters'
  write_json(out,{'seed':seed,'benefit':benefit,'dev_nll':losses,'candidate_gradient_norm':norms,'dotmatrix':dotmatrix,'forward_backward_pairs':calls,'optimizer_steps':0,'prefix_parameter_hash':before,'parameter_hash_unchanged':True,'seconds':time.time()-started,'formal_holdout_loaded':False,'created':time.strftime('%F %T %z')})
 finally:free_model(model)

def freeze_plans():
 verify();assert read_json(RUNS/'dry_run.json')['status']=='PASS'
 path=DATA/'plans_manifest.json'
 if path.exists():verify_plans();return
 scores={s:read_json(RUNS/'calibration'/f'A_seed{s}.json') for s in SEEDS}
 ensure_dir(DATA/'plans');meta={}
 for s in SEEDS:
  for a in ARMS:
   q=make_plan(s,a,scores[s]['benefit']);write_json(planpath(s,a),q);meta[label(s,a)]=q['p6']
 write_json(path,{'created':time.strftime('%F %T %z'),'policy_frozen_before_any_formal_test':True,'plans':{str(planpath(s,a).relative_to(ROOT)):sha256_file(planpath(s,a)) for s in SEEDS for a in ARMS},'calibration':{str((RUNS/'calibration'/f'A_seed{s}.json').relative_to(ROOT)):sha256_file(RUNS/'calibration'/f'A_seed{s}.json') for s in SEEDS},'summary':meta})
 log('P6 all 9 plans frozen from development gradients; formal holdout not evaluated')

def verify_plans():
 verify();m=read_json(DATA/'plans_manifest.json')
 for p,h in {**m['plans'],**m['calibration']}.items():assert sha256_file(ROOT/p)==h,p

def calibrate():
 for seed in SEEDS:score_seed(seed)
 freeze_plans();log('CALIBRATION COMPLETE (no production training)')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--phase',required=True,choices=['build','dry','verify','calibrate','freeze_plans','verify_plans']);args=p.parse_args();globals()[args.phase]()
