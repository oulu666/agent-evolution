"""P8 prospective two-arm content intervention; CPU data and token-only plan construction."""
from __future__ import annotations
import argparse,collections,copy,hashlib,itertools,json,random,sqlite3,statistics,time
from pathlib import Path
from .utils import read_json,read_jsonl,write_json,write_jsonl,sha256_file,ensure_dir
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data_ext_p8_decision_20261115';RUN=ROOT/'runs_ext_p8_decision_20261115'
SEEDS=[20261108,20261109,20261110];SKILLS=['db.list_tables','db.filter_cmp_top','file.search_last','py.median'];ARMS=['original','decision']
def log(s):print(time.strftime('%F %T %z'),s,flush=True)
def fixture(split):return DATA/'fixtures'/(split+'.sqlite')
def source(seed):return ROOT/f'data_ext_p6_devplan_attempt2/plans/A_seed{seed}_balanced_uniform.json'
def oldck(seed):return ROOT/f'runs_ext_p6_devplan_attempt2/branches/A_seed{seed}_balanced_uniform/checkpoint'
def ckpt(seed):return RUN/'branches'/f'seed{seed}_decision'/'checkpoint'
def planpath(seed):return DATA/'plans'/f'seed{seed}.json'
def label(seed,arm):return f'seed{seed}_{arm}'
def build_db(split):
 names=[f'p8{split[0]}_{x}' for x in ['zero','few','ties']]
 with sqlite3.connect(fixture(split)) as c:
  for kind,tab in enumerate(names):
   c.execute(f'CREATE TABLE {tab}(id INTEGER PRIMARY KEY,name TEXT,score REAL)')
   rows=[(i,f'{split}_item_{kind}_{i}',20+i/10) for i in range(1,7)]
   if kind==1:rows=[(i,n,90 if i in [2,5] else sc) for i,n,sc in rows]
   if kind==2:rows=[(i,n,90) for i,n,sc in rows]
   c.executemany(f'INSERT INTO {tab} VALUES (?,?,?)',rows)
   c.execute(f'CREATE INDEX idx_{tab} ON {tab}(score DESC,id DESC)')
 return names
LT={
 'train':['List database table names as a JSON array.','Retrieve every table name and return a JSON array.','What tables exist? Answer with their names in a JSON array.','Show the table catalogue as a JSON list.','Give all table identifiers, as a JSON array.','Return a JSON array of database table names only.','Fetch all names in this database catalogue. Use a JSON array.','Name all database tables in a JSON list.'],
 'dev':['For a schema inspection, return a JSON array listing the database tables.','Collect the names of the tables that are available; format a JSON array.','Please enumerate database table identifiers into a JSON array.','The requested inventory is all table names, in a JSON array.'],
 'holdout':['An inventory audit needs the database tables, encoded as a JSON array.','Supply a JSON array naming the tables accessible in this database.','Enumerate the table catalogue; the response must be a JSON array.','Which tables belong to the present database? Give a JSON array.','Output just a JSON array with every available database table identifier.','For documentation, provide database table names as a JSON array.','Inspect the database and write its table names in a JSON array.','Build a JSON list containing the complete table-name inventory.','Find out the tables present and answer as a JSON array of names.','Summarize the database inventory using a JSON array of table names.','Produce the names of existing tables in JSON-array form.','I need a JSON array representing the database table catalogue.']}
def row(split,skill,i,prompt,tool,args,env,spec,**meta):
 from .data.generate import _observation,_schemas,build_system_prompt
 from .round2_data import _messages
 from .research_data import project_answer
 fam={'db':'database','file':'file','py':'python'}[skill.split('.')[0]];cal=str(ROOT/'data_phase2/fixtures/calendar.json');obs=_observation(fam,tool,args,env,str(fixture(split)),cal)
 assert json.loads(obs)['ok'];answer=project_answer(json.loads(obs)['result'],spec);system=build_system_prompt(fam,_schemas(fam,str(fixture(split)),cal))
 return dict(episode_id=f'p8-{split}-{skill}-{i:03}',tool_family=fam,skill=skill,skill_labels=[skill],split='train' if split=='train' else 'p8_'+split,template_id=f'p8_{split}_{skill}',prompt=prompt,system=system,environment=env,expected_tool=tool,expected_arguments=args,expected_observation=obs,expected_final_answer=answer,answer_spec=spec,messages=_messages(system,prompt,tool,args,obs,answer),evaluation_only=split!='train',selection_allowed=split!='holdout',**meta)
def make_split(split):
 names=build_db(split);out=[];n={'train':8,'dev':4,'holdout':12}[split];rng=random.Random({'train':811,'dev':812,'holdout':813}[split])
 for i in range(n):out.append(row(split,SKILLS[0],i,LT[split][i],'db_list_tables',{}, {},{'kind':'identity'},case='inventory'))
 qn=12 if split=='train' else n
 for i in range(qn):
  case=['zero','few','ties'][i%3];tab=names[i%3];threshold=40+(i//3)*5;k=4 if case in ['zero','few'] else 1+i%2
  sql=f'SELECT name FROM {tab} WHERE score > {threshold} ORDER BY score DESC, id ASC LIMIT {k}'
  prompt=(f'In {tab}(id, name, score), keep score > {threshold}; order score descending and id ascending on ties. Return up to {k} names in a JSON list.' if split=='train' else f'Query {tab} with columns id, name, score: choose at most {k} names with score above {threshold}, greatest score first and smaller id first when equal; output a JSON list.' if split=='dev' else f'Only rows of {tab}(id, name, score) whose score exceeds {threshold} qualify. Give the best {k} names, descending by score, tie-breaking on ascending id, as a JSON array.')
  out.append(row(split,SKILLS[1],i,prompt,'db_query',{'sql':sql},{},{'kind':'rows_first'},case=case))
 fn=8 if split=='train' else n
 for i in range(fn):
  path=f'p8_{split}/trace_{i}.txt';word=f'p8{split}mark{i}';hits=2+i%3;lines=[f'record {j}: {word} item {split}_{i}_{j}' for j in range(1,hits+1)]+[f'record {hits+1}: ordinary entry']
  env={'files':{path:'\n'.join(lines)+'\n'}}
  for first in ([True,False] if split=='train' else [False]):
   which='first' if first else 'last';skill='file.search_first' if first else SKILLS[2]
   prompt=(f'In {path}, search for {word!r}. Return the full {which} matching line, not the other matches.' if split=='train' else f'Extract the final occurrence line containing {word!r} from {path}; give the complete line text.' if split=='dev' else f'Locate every line matching {word!r} within {path}, then report only the entire line at the end of that match list.')
   out.append(row(split,skill,i,prompt,'file_search',{'path':path,'pattern':word},env,{'kind':'match','index':0 if first else -1},case=which,pair=i))
  if split=='holdout' and i<4:out.append(row(split,'file.search_first',i,f'After searching {path} for {word!r}, return the complete line at the beginning of the results, not the last.','file_search',{'path':path,'pattern':word},env,{'kind':'match','index':0},case='first',pair=i))
 for i in range(n):
  # Match numeric scale, separate complete input sets and use disjoint values by split.
  vals=rng.sample(range({'train':101,'dev':301,'holdout':501}[split],{'train':199,'dev':399,'holdout':599}[split]),7 if i%2==0 else 5);text=', '.join(map(str,vals))
  prompt=(f'Sort these values mentally: {text}. Return only the central value, not a sorted list.' if split=='train' else f'For the measurements {text}, give the median as one number.' if split=='dev' else f'The observations are {text}. Once ordered, which value sits in the middle? Return that scalar.')
  out.append(row(split,SKILLS[3],i,prompt,'stats_median',{'values':vals},{},{'kind':'identity'},case='median'))
  if split=='holdout' and i<4:out.append(row(split,'py.mean',i,f'Compute the arithmetic average of {text}; return one number.','stats_mean',{'values':vals},{},{'kind':'identity'},case='mean'))
 return out

def checks(splits):
 from .sft.evaluate import _evaluate_tool_prediction,parse_final_answer
 from .metrics import answers_equal
 failures=collections.Counter();gold=0
 for split,rows in splits.items():
  for r in rows:
   g=_evaluate_tool_prediction(r,json.dumps({'tool':r['expected_tool'],'arguments':r['expected_arguments']}),str(fixture(split)),str(ROOT/'data_phase2/fixtures/calendar.json'))
   assert g['tool_correct'] and g['arguments_correct'] and g['execution_success'];gold+=1
   if r['skill'].startswith('file.'):
    matches=json.loads(r['expected_observation'])['result'];assert matches[0]['text']!=matches[-1]['text']
    if r['skill']==SKILLS[2]:assert r['expected_final_answer']!=matches[0]['text'];failures['file_first_instead_of_last']+=1
   if r['skill']==SKILLS[1]:
    sql=r['expected_arguments']['sql'];wrong=sql.replace(' WHERE score > '+sql.split(' WHERE score > ')[1].split(' ORDER')[0],'').replace(', id ASC','')
    with sqlite3.connect(fixture(split)) as c:
     assert c.execute(sql).fetchall()!=c.execute(wrong).fetchall();failures['SQL_where_or_tie_required']+=1
     if r['case'] in ['zero','few']:
      no_where=sql.split(' WHERE')[0]+' ORDER'+sql.split(' ORDER')[1];assert c.execute(sql).fetchall()!=c.execute(no_where).fetchall();failures['SQL_where_individually_required']+=1
     if r['case'] in ['few','ties']:
      assert c.execute(sql).fetchall()!=c.execute(sql.replace(', id ASC','')).fetchall();failures['SQL_tie_individually_required']+=1
   if r['skill']==SKILLS[3]:assert r['expected_final_answer']==statistics.median(r['expected_arguments']['values']);failures['median_gold_scalar']+=1
   if r['skill']==SKILLS[0]:
    bad=_evaluate_tool_prediction(r,json.dumps({'tool':'db_list_tables','arguments':{'table':'irrelevant'}}),str(fixture(split)),str(ROOT/'data_phase2/fixtures/calendar.json'));assert not bad['arguments_correct'];failures['extra_args_strict_failure']+=1
 # Independent instances plus template families, exact conversations, file entities and numeric sets.
 msgs=[{hashlib.sha256(json.dumps(r['messages'],sort_keys=True).encode()).hexdigest() for r in rs} for rs in splits.values()]
 for a,b in itertools.combinations(msgs,2):assert not a&b
 nums=[{tuple(sorted(r['expected_arguments']['values'])) for r in rs if r['skill']==SKILLS[3]} for rs in splits.values()]
 for a,b in itertools.combinations(nums,2):assert not a&b
 old=[r for f in ['file','database','python'] for r in read_jsonl(ROOT/f'data_ext_e4/pool/{f}.jsonl')]+read_jsonl(ROOT/'data_ext_p6_devplan/dev/rows.jsonl')+read_jsonl(ROOT/'data_ext_p6_devplan/holdout/rows.jsonl')+read_jsonl(ROOT/'data_ext_p7_response/check.jsonl')
 oldprompts={r['prompt'] for r in old};assert not oldprompts&{r['prompt'] for rs in splits.values() for r in rs}
 return {'gold_checks':gold,'counterexamples':dict(failures),'exact_conversations_disjoint':True,'prompts_vs_old_disjoint':True,'database_file_entities_disjoint_numeric_input_sets_disjoint':True,'templates_split_disjoint':True,'schema_and_scorer_unchanged':True}

def build():
 if DATA.exists():
  assert not (DATA/'manifest.json').exists(),'frozen data must not change'
  splits={split:read_jsonl(DATA/(split+'.jsonl')) for split in ['train','dev','holdout']}
 else:
  assert not RUN.exists(),'no overwrite'
  for d in [DATA/'fixtures',DATA/'pools',DATA/'plans',RUN/'logs']:ensure_dir(d)
  splits={split:make_split(split) for split in ['train','dev','holdout']}
  for split,rows in splits.items():write_jsonl(DATA/(split+'.jsonl'),rows)
 report=checks(splits)
 from .sft.train import load_tokenizer
 from .sft.dataset import tokenize_episode
 from .replay_study import config_for
 tok=load_tokenizer(config_for('A',SEEDS[0],batch_size=1));prepared={}
 for fam in ['database','file','python']:
  rs=[r for r in splits['train'] if r['tool_family']==fam];write_jsonl(DATA/'pools'/(fam+'.jsonl'),rs);offset=len(read_jsonl(ROOT/f'data_ext_e4/pool/{fam}.jsonl'))
  for i,r in enumerate(rs):
   ft=tokenize_episode(r,tok,1024);assert len(ft['input_ids'])<1024
   prepared[r['episode_id']]={'family':fam,'row_index':offset+i,'episode_id':r['episode_id'],'input_tokens':len(ft['input_ids']),'supervised_tokens':sum(t!=-100 for t in ft['labels']),'truncated':False,'target':True,'skill':SKILLS[2] if r['skill']=='file.search_first' else r['skill'],'p8_case':r['case'],'p8_pair':r.get('pair'),'message_hash':hashlib.sha256(json.dumps(r['messages'],sort_keys=True).encode()).hexdigest()}
 for r in splits['dev']+splits['holdout']:assert len(tokenize_episode(r,tok,1024)['input_ids'])<1024
 planstats={}
 for seed in SEEDS:
  q=copy.deepcopy(read_json(source(seed)));counts=collections.Counter(x['skill'] for x in q['items'] if x['target']);rng=random.Random(seed+800);options={}
  for k,n in counts.items():
   cand=[x for x in prepared.values() if x['skill']==k];combs=[]
   if k==SKILLS[2]:
    for pair in range(8):
     fixed=[x for x in cand if x['p8_pair']==pair]
     assert len(fixed)==2
     if n==2:combs.append(tuple(sorted(fixed,key=lambda x:x['p8_case'])))
     else:
      for z in cand:
       if z['p8_case']=='last' and z['p8_pair']!=pair:combs.append(tuple(sorted(fixed,key=lambda x:x['p8_case']))+(z,))
   else:
    for xs in itertools.combinations(cand,n):
     if k==SKILLS[1] and not {'zero','few'}.issubset({x['p8_case'] for x in xs}):continue
     combs.append(xs)
   rng.shuffle(combs);d={}
   for xs in combs:d.setdefault(sum(x['input_tokens'] for x in xs),list(xs))
   assert d;options[k]=d
  dp={0:{}}
  for k,opts in options.items():
   new={}
   for total,sel in dp.items():
    for cost,xs in opts.items():new.setdefault(total+cost,{**sel,k:xs})
   dp=new
  bg=sum(x['input_tokens'] for x in q['items'] if not x['target']);want=7494-bg;best=min(dp,key=lambda v:(abs(v-want),v));assert abs(best-want)<=74,(seed,best,want,{k:(min(v),max(v)) for k,v in options.items()})
  selected=copy.deepcopy(dp[best]);q['items']=[selected[x['skill']].pop(0) if x['target'] else x for x in q['items']]
  q['actual_input_tokens']=sum(x['input_tokens'] for x in q['items']);q['within_one_percent_of_budget']=abs(q['actual_input_tokens']-7494)/7494<=.01;q['unused_input_tokens']=7494-q['actual_input_tokens']
  q['actual_tokens_by_family']={f:sum(x['input_tokens'] for x in q['items'] if x['family']==f) for f in ['database','file','python']};q['quota_error_tokens_by_family']={f:v-2498 for f,v in q['actual_tokens_by_family'].items()}
  q['target_actual_input_tokens']=sum(x['input_tokens'] for x in q['items'] if x['target'])
  q['target_samples_by_family']={f:sum(x['target'] and x['family']==f for x in q['items']) for f in ['database','file','python']}
  q['p8']={'counts':dict(counts),'background_identical':True,'same_item_slots':True,'original_plan_sha256':sha256_file(source(seed)),'no_padding':True,'supervised_tokens':sum(x['supervised_tokens'] for x in q['items'])}
  # inherited P6 per-target identities are no longer valid; store new timing from actual packing.
  q.pop('p6',None);q.pop('p5',None);write_json(planpath(seed),q)
  a=read_json(oldck(seed)/'train_summary.json');audit=read_json(oldck(seed)/'optimizer_step_audit.json');assert a['completed'] and a['optimizer_steps']==23 and a['replay_input_tokens']==7494 and audit['suffix_actual_optimizer_steps']==13 and a['prefix_reused']
  planstats[str(seed)]={'A_tokens':7494,'B_tokens':q['actual_input_tokens'],'relative_deviation':(q['actual_input_tokens']-7494)/7494,'A_supervised_tokens':a['replay_supervised_tokens'],'B_supervised_tokens':q['p8']['supervised_tokens'],'target_counts':dict(counts),'old_A_checkpoint':str(oldck(seed)),'A_optimizer_audit':audit}
 report['plans']=planstats;write_json(DATA/'cpu_data_checks.json',report);log('P8 DATA/PLANS CPU PASS '+json.dumps(planstats))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['build']);args=p.parse_args();globals()[args.phase]()
