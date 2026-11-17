"""P6 attempt2: complete plan contract + actual step receipts, fresh runs only."""
from __future__ import annotations
import argparse,ast,collections,copy,hashlib,json,math,statistics,time,types
from pathlib import Path
from . import p6_devplan as D
from .utils import read_json,read_jsonl,write_json,sha256_file,ensure_dir
ROOT=D.ROOT;DATA=ROOT/'data_ext_p6_devplan_attempt2';RUNS=ROOT/'runs_ext_p6_devplan_attempt2'
REPORT=ROOT/'EXT_REPORT_20261115_p6_attempt2_ZH.md';HANDOVER=ROOT/'EXT_HANDOVER_20261115_p6_attempt2_ZH.md'
PREREG=ROOT/'P6_ATTEMPT2_AMEND_20261115_ZH.md'
SEEDS=D.SEEDS;ARMS=D.ARMS;STOP=RUNS/'logs/STOP'
SUITES=['p6_database','p6_file','p6_python','v3fix','p2_file']
def planpath(s,a):return DATA/'plans'/(D.label(s,a)+'.json')
def ckpt(s,a):return RUNS/'branches'/D.label(s,a)/'checkpoint'
def log(s):D.log('P6_A2 '+s)
def safe():
 if STOP.exists() or D.STOP.exists():raise SystemExit('P6 safety STOP present (old or attempt2); do not auto-clear')
 from .p0_run import refuse_if_game
 refuse_if_game()
def required_plan_keys():
 tree=ast.parse((ROOT/'fac_tinyagent/p6_e3_train_attempt2.py').read_text())
 return sorted({n.slice.value for n in ast.walk(tree) if isinstance(n,ast.Subscript) and isinstance(n.value,ast.Name) and n.value.id=='plan' and isinstance(n.slice,ast.Constant) and isinstance(n.slice.value,str)})
def adapt_plan(q):
 q=copy.deepcopy(q);fams=sorted(q['actual_tokens_by_family']);weights=q.get('weights',{})
 total=sum(float(weights.get(f,0)) for f in fams)
 reference={f:q['budget_input_tokens']*(float(weights.get(f,0))/total if total else 1/len(fams)) for f in fams}
 q['quota_error_tokens_by_family']={f:q['actual_tokens_by_family'][f]-reference[f] for f in fams}
 q['attempt2_contract']={'quota_reference':'Legacy nominal family weights only, not an enforced P6 token quota; diagnostic residual, never used to train/select.', 'required_keys':required_plan_keys(),'schedule_loss_updates_unchanged':True}
 missing=set(required_plan_keys())-set(q)
 if missing:raise ValueError('trainer plan contract missing '+str(sorted(missing)))
 assert q['actual_input_tokens']==sum(x['input_tokens'] for x in q['items'])==7494
 assert q['within_one_percent_of_budget']
 return q

def initialize():
 D.verify_plans()
 if DATA.exists() or RUNS.exists():raise SystemExit('attempt2 root exists; refuse replacement')
 ensure_dir(DATA/'plans');ensure_dir(RUNS/'logs')
 evidence={}
 for seed in SEEDS:
  for arm in ARMS:
   old=read_json(D.planpath(seed,arm));q=adapt_plan(old)
   assert q['items']==old['items'] and q['p6']==old['p6'] and q['p5']==old['p5']
   write_json(planpath(seed,arm),q)
   evidence[D.label(seed,arm)]={'original_plan_sha256':sha256_file(D.planpath(seed,arm)),'new_plan_sha256':sha256_file(planpath(seed,arm)),'original_items_sha256':D.digest(old['items']),'new_items_sha256':D.digest(q['items']),'tokens':q['actual_input_tokens']}
 refs=[Path(__file__),PREREG,ROOT/'fac_tinyagent/p6_e3_train_attempt2.py',ROOT/'fac_tinyagent/e3_train.py',ROOT/'scripts/run_p6_attempt2_20261115.py',ROOT/'scripts/launch_p6_attempt2_20261115.sh',ROOT/'scripts/p6_attempt2_handshake_20261115.py',ROOT/'scripts/test_p6_attempt2_contract_20261115.py',ROOT/'scripts/p6_a2_generate_trainer_20261115.py']
 refs += [ROOT/'runs_ext_p6_devplan_attempt2_cpu/acceptance.json']
 refs += [D.DATA/'manifest.json',D.DATA/'plans_manifest.json',D.DATA/'runtime_lock.json']
 refs += [D.RUNS/'calibration'/f'A_seed{s}.json' for s in SEEDS]
 write_json(DATA/'manifest.json',{'created':time.strftime('%F %T %z'),'attempt':'P6_attempt2','reason':'missing mandatory plan summary field; distinguish pre-tail microstep log from actual optimizer updates','required_plan_keys':required_plan_keys(),'references':{str(p.relative_to(ROOT)):sha256_file(p) for p in refs},'plans':{str(planpath(s,a).relative_to(ROOT)):sha256_file(planpath(s,a)) for s in SEEDS for a in ARMS},'evidence':evidence,'calibration_reused_without_updates':True,'formal_holdout_and_algorithm_unchanged':True})
 log('initialized fresh attempt2; all original items/allocations unchanged')

def runtime_guard():
 D.verify_plans()
 m=read_json(DATA/'manifest.json')
 for rel,h in {**m['references'],**m['plans']}.items():assert sha256_file(ROOT/rel)==h,rel
 for seed in SEEDS:
  for arm in ARMS:
   q=read_json(planpath(seed,arm));assert not(set(required_plan_keys())-set(q))

def audit_checkpoint(seed,arm):
 ck=ckpt(seed,arm);q=read_json(planpath(seed,arm));summary=read_json(ck/'train_summary.json');audit=read_json(ck/'optimizer_step_audit.json');events=read_jsonl(ck/'optimizer_update_log.jsonl');logs=read_jsonl(ck/'training_log.jsonl')
 assert summary['completed'] and summary['optimizer_steps']==23
 assert audit['prefix_updates']==10 and audit['prefix_microsteps']==80
 assert audit['suffix_actual_optimizer_steps']==13 and audit['total_actual_optimizer_steps']==23
 assert audit['suffix_microsteps']==102 and audit['tail_microsteps']==6 and audit['tail_actual_steps']==1
 assert len(events)==13 and [e['global_optimizer_step'] for e in events]==list(range(11,24))
 assert events[-1]['microstep']==182 and events[-1]['tail_flush']
 assert logs[-1]['microstep']==182 and logs[-1]['optimizer_steps']==22 # log precedes tail; not final step count
 assert summary['replay_input_tokens']==q['actual_input_tokens']==7494
 assert len(logs)==102 and sum(x['kind']=='new' for x in logs)==80
 tracked=[x for x in logs if x['kind']!='new' and any(x['episode_id']==t['id'] for t in q['p6']['target_timing'])]
 got=[(x['episode_id'],x['new_position'],23-((x['microstep']-1)//8+1)+1) for x in tracked]
 want=[(x['id'],x['position'],x['after']) for x in q['p6']['target_timing']]
 assert got==want,(got,want)
 result={'status':'PASS','optimizer_step_audit':audit,'tokens':7494,'plan_sha256':sha256_file(planpath(seed,arm)),'finished':time.strftime('%F %T %z')}
 write_json(ck.parent/'attempt2_meta.json',result);return result

def train(seed,arm):
 runtime_guard();safe();ck=ckpt(seed,arm)
 if (ck/'train_summary.json').exists():audit_checkpoint(seed,arm);return
 if ck.parent.exists():raise SystemExit('partial attempt2 exists; preserve, do not silently overwrite: '+str(ck.parent))
 from . import e3_data as E
 from .e3_run import guards,v3_leakage_guard
 from .p6_e3_train_attempt2 import train_replay_stage_e3
 from .e4_run import CALENDAR_PATH,DB_PATH,OLD,leakage_guard,start_adapter
 from .replay_study import config_for
 guards();q=read_json(planpath(seed,arm));cfg=config_for('A',seed,batch_size=1)
 pools={f:str(ROOT/'data_ext_e4/pool'/(f+'.jsonl')) for f in OLD};probes={f:str(ROOT/'data_ext_monitor_v2'/(f+'.jsonl')) for f in OLD}
 new=str(ROOT/'data_phase2/calendar/train.jsonl');rows=read_jsonl(new)+[r for p in [*pools.values(),*probes.values()] for r in read_jsonl(p)]
 leakage_guard(rows);v3_leakage_guard(rows)
 def override(pools,extra_pools,budget,seed):
  assert budget==7494
  index={(f,x['row_index'],x['episode_id']):x for f,rs in pools.items() for x in rs}
  for x in q['items']:
   y=index[(x['family'],x['row_index'],x['episode_id'])];assert all(x[k]==y[k] for k in ['input_tokens','supervised_tokens'])
  return copy.deepcopy(q)
 log('TRAIN '+D.label(seed,arm))
 train_replay_stage_e3(config=cfg,stage=dict(cfg['stages'][4],index=4),train_path=new,old_train_paths=pools,probe_paths=probes,previous_adapter=str(start_adapter(seed)),output_dir=str(ck),db_path=str(DB_PATH),calendar_path=str(CALENDAR_PATH),mode='targeted',replay_ratio=.10,uniform_floor=.2,prefix_dir=str(ROOT/f'runs_ext_e4/prefixes/A_seed{seed}'),target_ids=read_json(ROOT/'data_ext_e4/manifest.json')['target_ids'],target_fraction=E.TF25,target_family_weights={f:1/len(OLD) for f in OLD},plan_override=override,extra_replay_family=None,require_prefix_reuse=True)
 audit_checkpoint(seed,arm);runtime_guard();log('TRAIN AUDIT PASS '+D.label(seed,arm)+' actual_steps=23 suffix=13 tokens=7494')

# Evaluation/final report helpers retain P6 protocol but route every write to attempt2.
P=types.SimpleNamespace(ROOT=ROOT,DATA=D.DATA,RUNS=RUNS,SEEDS=SEEDS,ARMS=ARMS,SKILLS=D.SKILLS,fixture=D.fixture,planpath=planpath,ckpt=ckpt,label=D.label,safe=safe,log=log)

def rows_for(suite):
 if suite.startswith('p6_'):
  family=suite[3:];rows=[r for r in read_jsonl(P.DATA/'holdout/rows.jsonl') if r['tool_family']==family]
  return rows,str(P.fixture('holdout')),str(P.ROOT/'data_phase2/fixtures/calendar.json'),sha256_file(P.DATA/'holdout/rows.jsonl')
 from .p1_run import suite_rows
 return suite_rows(suite)

def evaluate(seed,arm,only=None):
 from .replay_study import config_for
 from .sft.evaluate import load_eval_model,evaluate_family,free_model
 out=P.RUNS/'evaluation'/P.label(seed,arm);todo=[x for x in (only or SUITES) if not (out/x/'stage_report.json').exists()]
 if not todo:return
 runtime_guard();P.safe();cfg=config_for('A',seed,batch_size=1);cfg['evaluation']['batch_size']=1
 P.log('EVAL '+P.label(seed,arm)+' suites='+str(todo));model,tok=load_eval_model(cfg,str(P.ckpt(seed,arm)))
 try:
  for name in todo:
   P.safe();rows,db,cal,h=rows_for(name);started=time.time()
   rep=evaluate_family(model,tok,rows,cfg,{'name':'P6_B1_'+P.label(seed,arm),'index':4,'adapter':str(P.ckpt(seed,arm))},out/name,db,cal)
   assert rep['evaluation_protocol']['batch_size']==1
   write_json(out/name/'p6_meta.json',{'suite':name,'n':len(rows),'rows_sha256':h,'protocol':'Protocol-B1','seconds':time.time()-started,'finished':time.strftime('%F %T %z')})
 finally:free_model(model)


def score(path,skill=None,exclude=False):
 if not path.exists():return None
 rs=read_jsonl(path)
 if skill:rs=[r for r in rs if skill in r['episode_id']]
 if exclude:rs=[r for r in rs if 'file_last_match' not in r['episode_id']]
 assert rs
 return {'n':len(rs),**{k:sum(bool(r[k]) for r in rs)/len(rs) for k in ['joint_success','tool_correct','arguments_correct','final_correct']}}

def finalize(*,allow_cpu_mock=False):
 runtime_guard();rows=[];suites=0
 for seed in P.SEEDS:
  for arm in P.ARMS:
   out=P.RUNS/'evaluation'/P.label(seed,arm);r={'seed':seed,'arm':arm,'skills':{}}
   for name in SUITES:
    if (out/name/'stage_report.json').exists():
     rep=read_json(out/name/'stage_report.json');assert rep['evaluation_protocol']['batch_size']==1
     if rep.get('synthetic_cpu_contract'):assert allow_cpu_mock and 'cpu_contract_tests' in str(P.RUNS)
     suites+=1
   for skill in P.SKILLS:
    family='database' if skill.startswith('db.') else 'file' if skill.startswith('file.') else 'python'
    r['skills'][skill]=score(out/('p6_'+family)/'results.jsonl',skill)
   done=all(v is not None for v in r['skills'].values());r['macro_joint']=statistics.mean(v['joint_success'] for v in r['skills'].values()) if done else None
   r['calendar']=score(out/'v3fix/results.jsonl');r['file_nontarget']=score(out/'p2_file/results.jsonl',exclude=True)
   r['allocation']=read_json(P.planpath(seed,arm))['p6']['counts'];r['tokens']=read_json(P.planpath(seed,arm))['actual_input_tokens'];rows.append(r)
 pairs={}
 for base in ['balanced_uniform','balanced_early']:
  d=[]
  for seed in P.SEEDS:
   x=next(r for r in rows if r['seed']==seed and r['arm']=='devgrad_uniform')['macro_joint'];y=next(r for r in rows if r['seed']==seed and r['arm']==base)['macro_joint']
   d.append(None if x is None or y is None else x-y)
  pairs['devgrad_uniform-'+base]={'per_seed':d,'mean':statistics.mean(d) if all(v is not None for v in d) else None}
 complete=suites==45 and all(r['macro_joint'] is not None and r['calendar'] is not None and r['file_nontarget'] is not None for r in rows)
 result={'synthetic_cpu_contract':bool(allow_cpu_mock),'time':time.strftime('%F %T %z'),'complete':complete,'B1_suites':suites,'rows':rows,'pairs':pairs};write_json(P.RUNS/'summary.json',result)
 md=['# P6 attempt2实验报告：开发梯度驱动的一次预算规划','',f'更新：{result["time"]}（北京时间）；complete={complete}；B1套件{suites}/45。',
 '这是开发梯度代理驱动的单次预算规划，不是在线状态分类器或已测恢复速度。不存在按技能名字硬编码早槽偏好。',
 '四组新holdout各12题，预注册主指标为四技能Joint宏平均；旧P4/P5卷不作新主指标。','', '|种子|臂|macro Joint|Calendar|非目标File|分配|tokens|','|---|---|---|---|---|---|---|']
 fmt=lambda x:'—' if x is None else f'{x:.3f}'
 for r in rows:md.append(f'|{r["seed"]}|{r["arm"]}|{fmt(r["macro_joint"])}|{fmt(r["calendar"]["joint_success"] if r["calendar"] else None)}|{fmt(r["file_nontarget"]["joint_success"] if r["file_nontarget"] else None)}|{r["allocation"]}|{r["tokens"]}|')
 md+=['','## 修复与公平性','旧attempt缺摘要必需quota字段而失败；新attempt只补接口诊断元数据，计划items/分配/7494 tokens/超参/holdout全部不变。校准hash核验后复用，不重复GPU校准。实际optimizer事件13次加prefix10次为23；日志最后microstep182的22是尾部6条flush之前，不是漏一步。失败adapter不复用。','','## 配对判定',json.dumps(pairs,ensure_ascii=False,indent=2)]
 if complete:
  primary=pairs['devgrad_uniform-balanced_uniform'];strong=pairs['devgrad_uniform-balanced_early']
  support=all(x>0 for x in primary['per_seed']) and primary['mean']>=.05-1e-12
  challenge=all(x>=-1e-12 for x in strong['per_seed']) and strong['mean']>=-1e-12
  md+=['','主要分配机制判据：'+('达到。' if support else '未达到。'),'FixedEarly挑战：'+('不输固定前段，达到。' if challenge else '未达到；不能声称优于两固定策略。')]
  for seed in P.SEEDS:
   a=next(r for r in rows if r['seed']==seed and r['arm']=='devgrad_uniform');b=next(r for r in rows if r['seed']==seed and r['arm']=='balanced_uniform')
   for k in ['calendar','file_nontarget']:
    delta=a[k]['joint_success']-b[k]['joint_success'];md.append(f'- {seed} {k}配对差{delta:+.3f}'+('，下降超过0.10，应报告代价。' if delta<-.10-1e-12 else '。'))
 md+=['','## 成本与边界','校准每种子41个forward/backward，0 optimizer steps；三臂共同计入同等诊断成本。生产分支23 optimizer steps，实际tokens逐臂报告。背景按同一DP匹配残余token，背景内容可变化，所以不能声称纯目标条数独立因果。','未达到判据时不自动加实验，不修改holdout，不启动下一轮。']
 REPORT.write_text('\n'.join(md)+'\n',encoding='utf-8')
 hand=['# P6 attempt2交接手册',f'更新时间：{result["time"]}（北京时间），complete={complete}。',
 '方案：P6_PREREG_20261115_devplan_ZH.md；设计/数据先冻结manifest.json，GPU只读梯度后另冻结plans_manifest.json；实现补充锁runtime_lock.json。',
 '正式队列：bash scripts/launch_p6_attempt2_20261115.sh；仅在校准完成、9计划已冻结且协调者审核后启动。',
 '监测：runs_ext_p6_devplan_attempt2/logs/status.log、queue.log、runner.pid、gpu_child.pid；STOP粘性，不自动恢复。',
 'CPU收尾：PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 .venv/bin/python -B -m fac_tinyagent.p6_attempt2 --phase finalize',
 '完整结果：runs_ext_p6_devplan_attempt2/summary.json。新增带实际optimizer.step调用凭据的训练副本；旧失败现场不改。旧microstep日志最后22不含尾部flush，新attempt用13次实际调用证明10+13=23，不能凭空添加训练。',
 '不得重跑已完成P5、修改冻结数据/旧实验/.venv/zxx/Small Agent；不发GPT，完成后不自动P7。']
 HANDOVER.write_text('\n'.join(hand)+'\n',encoding='utf-8')
 P.log('SUMMARY complete='+str(complete))



def queue():
 runtime_guard();safe()
 assert read_json(RUNS/'cpu_contract_tests'/'acceptance.json')['status']=='PASS'
 first=(SEEDS[0],ARMS[0]);train(*first);evaluate(*first,only=['p6_database'])
 ev=RUNS/'evaluation'/D.label(*first)/'p6_database'
 assert read_json(ev/'stage_report.json')['evaluation_protocol']['batch_size']==1
 assert len(read_jsonl(ev/'results.jsonl'))==24
 write_json(RUNS/'e2e_gate.json',{'status':'PASS','first':D.label(*first),'train_actual_steps':23,'tokens':7494,'first_B1_suite':'p6_database','n':24,'time':time.strftime('%F %T %z'),'scores_not_used_to_gate':True})
 log('E2E GATE PASS: first train summary + actual steps + first B1 suite; remaining 8 arms released')
 evaluate(*first);finalize()
 for arm in ARMS:
  for seed in SEEDS:
   if (seed,arm)==first:continue
   safe();train(seed,arm);evaluate(seed,arm);finalize()
 log('QUEUE COMPLETE')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--phase',required=True,choices=['initialize','verify','queue','finalize']);a=p.parse_args()
 if a.phase=='verify':runtime_guard()
 else:globals()[a.phase]()
