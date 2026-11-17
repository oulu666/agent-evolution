"""P5: cross-tool fixed-experience timing, additive files only. No learned classifier."""
from __future__ import annotations
import argparse, copy, itertools, json, os, statistics, time
from pathlib import Path
from .utils import read_json, read_jsonl, sha256_file, write_json, ensure_dir
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data_ext_p5_file_timing'
RUNS=ROOT/'runs_ext_p5_file_timing'
SEEDS=[20261108,20261109,20261110]
ARMS=['early','uniform','late']
DEST={'early':[0,1,2,3], 'uniform':[0,7,14,21], 'late':[18,19,20,21]}
IDS=['file-train-e4_last_match-%03d'%i for i in [0,6,7,14]]
SUITES=['natv2_file','p2_file','natv2_database','natv2_python','v3fix']
PREREG=ROOT/'P5_PREREG_20261115_file_timing_ZH.md'
STOP=RUNS/'logs/STOP'

def label(s,a): return f'A_seed{s}_{a}'
def planpath(s,a): return DATA/'plans'/(label(s,a)+'.json')
def ckpt(s,a): return RUNS/'branches'/label(s,a)/'checkpoint'
def log(m): print(time.strftime('%F %T %z'),m,flush=True)
def protected(it): return it['target'] and it['family']!='file' or 'file_search_first' in it['episode_id']
def source(s): return ROOT/'data_ext_e3/plans'/f'A_seed{s}_dose_db4.json'
def files():
 from .p1_run import suite_rows
 paths=[PREREG,Path(__file__), ROOT/'scripts/run_p5_20261115.py',ROOT/'scripts/launch_p5_20261115.sh']
 paths += [ROOT/'data_ext_e4/pool'/(f+'.jsonl') for f in ['file','database','python']]
 paths += [ROOT/'data_phase2/calendar/train.jsonl']
 paths += [ROOT/'data_ext_monitor_v2'/(f+'.jsonl') for f in ['file','database','python']]
 for s in SEEDS:
  paths += [source(s), ROOT/f'runs_phase2/A_seed{s}/checkpoints/stage_03_python/adapter_model.safetensors', ROOT/f'runs_ext_e4/prefixes/A_seed{s}/manifest.json', ROOT/f'runs_ext_e4/prefixes/A_seed{s}/training_state.pt']
 # P1 validates official frozen suites; also snapshot hashes of physical files/fixtures.
 for suite in SUITES: suite_rows(suite)
 paths += [ROOT/'data_ext_e4/final_v2'/(f+'.jsonl') for f in ['file','database','python']]
 paths += [ROOT/'data_phase2/file/test.jsonl',ROOT/'data_ext_p0_cal_titlecount/final/title_count_v3fix.jsonl',ROOT/'data_ext_cal_v3/fixtures/calendar_v3.json',ROOT/'data_phase2/fixtures/toolbench.db',ROOT/'data_phase2/fixtures/calendar.json']
 return paths

def make(s, cache):
 from .p4_forget_timing import recompute_meta,source_after_by_index,POSITIONS,segment_of
 p=read_json(source(s)); old=p['items']; assert len(old)==22
 targets=[copy.deepcopy(cache[x]) for x in IDS]
 ft=[x for x in old if x['family']=='file' and x['target']]
 assert len(ft)==1
 bgidx=[i for i,x in enumerate(old) if x['family']=='file' and not x['target'] and 'file_search_first' not in x['episode_id']]
 # Remove exactly 3 same-family background entries. Sole objective is matching input tokens.
 def key(c):
  total=p['actual_input_tokens']-sum(old[i]['input_tokens'] for i in c)-ft[0]['input_tokens']+sum(t['input_tokens'] for t in targets)
  return (abs(total-7494),c)
 remove=min(itertools.combinations(bgidx,3),key=key)
 keep=[copy.deepcopy(x) for i,x in enumerate(old) if i not in remove and x is not ft[0]]
 assert len(keep)==18
 prot=[x for x in keep if protected(x)]
 available=sorted(set(range(22))-set(sum(DEST.values(),[])))
 assert len(prot)<=len(available)
 fixed=dict(zip(available,prot))
 background=[x for x in keep if not protected(x)]
 after=source_after_by_index(s,'dose_db4',old)
 result={}
 for a in ARMS:
  q=copy.deepcopy(p); placement=dict(fixed); placement.update(zip(DEST[a],targets))
  it=iter(copy.deepcopy(background))
  q['items']=[copy.deepcopy(placement[i]) if i in placement else next(it) for i in range(22)]
  recompute_meta(q)
  # Drop inherited design claims that no longer describe P5.
  q.pop('e3_plan',None)
  q['p5']={'seed':s,'arm':a,'source_plan':str(source(s).relative_to(ROOT)), 'source_sha256':sha256_file(source(s)),
   'removed_ids':[old[i]['episode_id'] for i in remove]+[ft[0]['episode_id']],
   'target_ids':IDS,'fixed_protected':{str(i):x['episode_id'] for i,x in fixed.items()},
   'target_timing':[{'id':q['items'][i]['episode_id'],'index':i,'position':POSITIONS[segment_of(i,22)],'after':after[i]} for i in DEST[a]],
   'budget_deviation':q['actual_input_tokens']-7494,'expected_optimizer_steps':23}
  assert abs(q['actual_input_tokens']-7494)<=74.94
  result[a]=q
 assert len({json.dumps(sorted((x['episode_id'],x['input_tokens']) for x in q['items'])) for q in result.values()})==1
 return result

def build():
 if DATA.exists() or RUNS.exists(): raise SystemExit('Refuse existing P5 directories')
 from .p4_forget_timing import token_cache
 cache=token_cache()
 from .sft.train import load_tokenizer
 from .sft.dataset import tokenize_episode
 from .replay_study import config_for
 tok=load_tokenizer(config_for('A',SEEDS[0],batch_size=1))
 for i,row in enumerate(read_jsonl(ROOT/'data_ext_e4/pool/file.jsonl')):
  if row['episode_id'] in IDS and row['episode_id'] not in cache:
   ft=tokenize_episode(row,tok,1024)
   cache[row['episode_id']]={'family':'file','row_index':i,'episode_id':row['episode_id'],'input_tokens':len(ft['input_ids']),'supervised_tokens':sum(x!=-100 for x in ft['labels']),'truncated':False,'target':True}
 assert all(x in cache for x in IDS)
 allplans={s:make(s,cache) for s in SEEDS}
 refs=files()
 ensure_dir(DATA/'plans'); ensure_dir(RUNS/'logs')
 for s,ps in allplans.items():
  for a,q in ps.items(): write_json(planpath(s,a),q)
 write_json(DATA/'manifest.json', {'created':time.strftime('%F %T %z'),'seeds':SEEDS,'arms':ARMS,'target_ids':IDS,'suites':SUITES,'steps':23,'budget':7494,'protocol':'Protocol-B1',
  'references':{str(p.relative_to(ROOT)):sha256_file(p) for p in refs},
  'plans':{str(planpath(s,a).relative_to(ROOT)):sha256_file(planpath(s,a)) for s in SEEDS for a in ARMS}})
 log('P5 frozen')

def verify():
 m=read_json(DATA/'manifest.json')
 for rel,h in {**m['references'],**m['plans']}.items():
  assert sha256_file(ROOT/rel)==h, 'changed: '+rel
 return m

def dry():
 verify()
 from .p4_forget_timing import token_cache, source_after_by_index
 from .sft.train import load_tokenizer
 from .sft.dataset import tokenize_episode
 from .replay_study import config_for
 from .replay_train import assign_to_positions, common_replay_positions
 from .p1_run import suite_rows
 config=config_for('A',SEEDS[0],batch_size=1); tok=load_tokenizer(config)
 pools={f:read_jsonl(ROOT/'data_ext_e4/pool'/(f+'.jsonl')) for f in ['file','database','python']}
 actual={}
 # Tokenize only unique planned rows, with original tokenizer and loss masking. No model/GPU.
 for s in SEEDS:
  ps={a:read_json(planpath(s,a)) for a in ARMS}
  for a,q in ps.items():
   for x in q['items']:
    row=pools[x['family']][x['row_index']]
    assert row['episode_id']==x['episode_id']
    if x['episode_id'] not in actual:
     f=tokenize_episode(row,tok,1024)
     actual[x['episode_id']]=(len(f['input_ids']),sum(i!=-100 for i in f['labels']))
    assert actual[x['episode_id']]==(x['input_tokens'],x['supervised_tokens'])
   positions=common_replay_positions(160,80,22,22,8)
   sched=assign_to_positions(q['items'],positions)
   micro=0; tracked=[]
   for pos in range(81,161):
    micro+=1
    for x in sched.get(pos,[]):
     micro+=1
     if x['episode_id'] in IDS: tracked.append((x['episode_id'],pos,micro))
   total=(micro+7)//8
   assert total==13 # prefix contributes 10 optimizer steps; suffix contributes 13 = 23 total
   # Existing trainer counters are restored from prefix; source logs use total counters.
   expected=q['p5']['target_timing']
   assert [(eid,pos) for eid,pos,mi in tracked]==[(x['id'],x['position']) for x in expected]
   assert [total-((mi+80-1)//8+1)+10+1 for eid,pos,mi in tracked]==[x['after'] for x in expected]
   log(f'DRY {s} {a} tokens={q["actual_input_tokens"]} targets={expected}')
  assert len({q['actual_input_tokens'] for q in ps.values()})==1
  for i in range(22):
   if str(i) in ps['early']['p5']['fixed_protected']:
    assert len({q['items'][i]['episode_id'] for q in ps.values()})==1
 for name in SUITES:
  rows,db,cal,h=suite_rows(name); assert rows
 write_json(RUNS/'dry_run.json',{'finished':time.strftime('%F %T %z'),'status':'PASS','unique_tokenized_rows':len(actual),'cuda_model_loaded':False,'gpu_started':False,'total_optimizer_steps':23,'suffix_microsteps':102,'suites':SUITES})
 log('DRY OK: CPU tokenizer, 9 plans, exact suffix schedule, immutable references')

def safe():
 if STOP.exists(): raise SystemExit('STOP present; explicit user resume needed')
 from .p0_run import refuse_if_game
 refuse_if_game()

def train(s,a):
 from . import e3_data as D
 from .e3_run import guards,v3_leakage_guard
 from .e3_train import train_replay_stage_e3
 from .e4_run import CALENDAR_PATH, DB_PATH, OLD, leakage_guard,start_adapter
 from .replay_study import config_for
 verify(); safe(); guards()
 q=read_json(planpath(s,a)); ck=ckpt(s,a)
 if (ck/'train_summary.json').exists(): return
 if ck.parent.exists():
  ck.parent.rename(ck.parent.with_name(ck.parent.name+'_partial_'+str(int(time.time()))))
 prefix=ROOT/f'runs_ext_e4/prefixes/A_seed{s}'
 # Read-only prefix reuse: training loader never writes an existing valid prefix.
 assert (prefix/'manifest.json').exists()
 cfg=config_for('A',s,batch_size=1)
 pools={f:str(ROOT/'data_ext_e4/pool'/(f+'.jsonl')) for f in OLD}
 probes={f:str(ROOT/'data_ext_monitor_v2'/(f+'.jsonl')) for f in OLD}
 new=str(ROOT/'data_phase2/calendar/train.jsonl')
 rows=read_jsonl(new)+[r for p in [*pools.values(),*probes.values()] for r in read_jsonl(p)]
 leakage_guard(rows); v3_leakage_guard(rows)
 def override(pools,extra_pools,budget,seed):
  assert budget==7494
  index={(f,r['row_index'],r['episode_id']):r for f,rs in pools.items() for r in rs}
  for x in q['items']:
   r=index[(x['family'],x['row_index'],x['episode_id'])]
   assert all(r[k]==x[k] for k in ['input_tokens','supervised_tokens'])
  return copy.deepcopy(q)
 log('TRAIN '+label(s,a))
 summary=train_replay_stage_e3(config=cfg,stage=dict(cfg['stages'][4],index=4),train_path=new,old_train_paths=pools,probe_paths=probes,previous_adapter=str(start_adapter(s)),output_dir=str(ck),db_path=str(DB_PATH),calendar_path=str(CALENDAR_PATH),mode='targeted',replay_ratio=.10,uniform_floor=.2,prefix_dir=str(prefix),target_ids=read_json(ROOT/'data_ext_e4/manifest.json')['target_ids'],target_fraction=D.TF25,target_family_weights={f:1/len(OLD) for f in OLD},plan_override=override,extra_replay_family=None,require_prefix_reuse=True)
 assert summary['optimizer_steps']==23
 assert summary['replay_input_tokens']==q['actual_input_tokens']
 logs=read_jsonl(ck/'training_log.jsonl')
 target=[x for x in logs if x['kind']!='new' and x['episode_id'] in IDS]
 got=[(x['episode_id'],x['new_position'],23-((x['microstep']-1)//8+1)+1) for x in target]
 want=[(x['id'],x['position'],x['after']) for x in q['p5']['target_timing']]
 assert got==want,(got,want)
 write_json(ck.parent/'p5_meta.json',{'plan_sha256':sha256_file(planpath(s,a)),'actual_timing':got,'optimizer_steps':23,'replay_input_tokens':summary['replay_input_tokens']})
 verify()

def evaluate(s,a):
 from .p1_run import suite_rows
 from .replay_study import config_for
 from .sft.evaluate import load_eval_model,evaluate_family,free_model
 out=RUNS/'evaluation'/label(s,a)
 todo=[n for n in SUITES if not (out/n/'stage_report.json').exists()]
 if not todo: return
 safe(); verify()
 cfg=config_for('A',s,batch_size=1); cfg['evaluation']['batch_size']=1
 model,tok=load_eval_model(cfg,str(ckpt(s,a)))
 try:
  for n in todo:
   safe(); rows,db,cal,h=suite_rows(n); t=time.time()
   rep=evaluate_family(model,tok,rows,cfg,{'name':'P5_B1_'+label(s,a),'index':4,'adapter':str(ckpt(s,a))},out/n,db,cal)
   assert rep['evaluation_protocol']['batch_size']==1
   write_json(out/n/'p5_meta.json',{'protocol':'Protocol-B1','suite_sha256':h,'seconds':time.time()-t})
 finally: free_model(model)

def summarize():
 def score(p,exclude=False):
  if not p.exists(): return None
  rows=read_jsonl(p)
  if exclude: rows=[r for r in rows if 'file_last_match' not in r['episode_id']]
  return {'n':len(rows),**{k:sum(bool(r[k]) for r in rows)/len(rows) for k in ['joint_success','tool_correct','arguments_correct','final_correct']}}
 data=[]
 for s in SEEDS:
  for a in ARMS:
   ev=RUNS/'evaluation'/label(s,a)
   data.append({'seed':s,'arm':a,**{n:score(ev/n/'results.jsonl') for n in SUITES},'file_nontarget':score(ev/'p2_file/results.jsonl',True)})
 pairs={}
 for a,b in [('early','uniform'),('early','late'),('uniform','late')]:
  ds=[]
  for s in SEEDS:
   x=next(r for r in data if r['seed']==s and r['arm']==a)['natv2_file']; y=next(r for r in data if r['seed']==s and r['arm']==b)['natv2_file']
   ds.append(None if x is None or y is None else x['joint_success']-y['joint_success'])
  pairs[a+'-'+b]={'per_seed':ds,'mean':statistics.mean(ds) if all(d is not None for d in ds) else None}
 write_json(RUNS/'summary.json',{'generated':time.strftime('%F %T %z'),'rows':data,'paired_primary':pairs})
 md=['# P5 File固定集合时机：B1汇总','','|种子|臂|nat File joint|phase2 File joint|非target File joint|Calendar joint|','|---|---|---|---|---|---|']
 for r in data:
  f=lambda n:'—' if r[n] is None else '%.3f'%r[n]['joint_success']
  md.append(f'|{r["seed"]}|{r["arm"]}|{f("natv2_file")}|{f("p2_file")}|{f("file_nontarget")}|{f("v3fix")}|')
 md+=['',json.dumps(pairs,ensure_ascii=False,indent=2)]
 (RUNS/'summary_tables_ZH.md').write_text('\n'.join(md)+'\n')

def queue():
 verify(); assert read_json(RUNS/'dry_run.json')['status']=='PASS'
 for a in ARMS:
  for s in SEEDS:
   safe(); train(s,a); evaluate(s,a); summarize()
 log('QUEUE COMPLETE')

if __name__=='__main__':
 p=argparse.ArgumentParser(); p.add_argument('--phase',required=True,choices=['build','dry','queue','summarize','verify']); args=p.parse_args()
 globals()[args.phase]()
