"""P6 production queue. Separate entry from calibration; requires all plans frozen."""
import argparse,copy,json,statistics,time
from pathlib import Path
from . import p6_devplan as P
from .utils import read_json,read_jsonl,write_json,sha256_file
SUITES=['p6_database','p6_file','p6_python','v3fix','p2_file']

def runtime_guard():
 P.verify_plans()
 lock=read_json(P.DATA/'runtime_lock.json')
 for rel,h in lock['files'].items():assert sha256_file(P.ROOT/rel)==h,rel

def rows_for(suite):
 if suite.startswith('p6_'):
  family=suite[3:];rows=[r for r in read_jsonl(P.DATA/'holdout/rows.jsonl') if r['tool_family']==family]
  return rows,str(P.fixture('holdout')),str(P.ROOT/'data_phase2/fixtures/calendar.json'),sha256_file(P.DATA/'holdout/rows.jsonl')
 from .p1_run import suite_rows
 return suite_rows(suite)

def train(seed,arm):
 # Reuse audited P5 training implementation in memory only. Never writes old P5 assets.
 from . import p5_file_timing as T
 T.DATA=P.DATA;T.RUNS=P.RUNS;T.STOP=P.STOP;T.PREREG=P.PREREG;T.ARMS=P.ARMS
 T.IDS=[x['episode_id'] for rs in read_json(P.DATA/'candidates.json').values() for x in rs]
 T.verify=runtime_guard;T.safe=P.safe;T.planpath=P.planpath;T.ckpt=P.ckpt
 T.train(seed,arm)
 assert (P.ckpt(seed,arm).parent/'p5_meta.json').exists(),'training audit missing'


def evaluate(seed,arm):
 from .replay_study import config_for
 from .sft.evaluate import load_eval_model,evaluate_family,free_model
 out=P.RUNS/'evaluation'/P.label(seed,arm);todo=[x for x in SUITES if not (out/x/'stage_report.json').exists()]
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

def finalize():
 runtime_guard();rows=[];suites=0
 for seed in P.SEEDS:
  for arm in P.ARMS:
   out=P.RUNS/'evaluation'/P.label(seed,arm);r={'seed':seed,'arm':arm,'skills':{}}
   for name in SUITES:
    if (out/name/'stage_report.json').exists():
     rep=read_json(out/name/'stage_report.json');assert rep['evaluation_protocol']['batch_size']==1;suites+=1
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
 result={'time':time.strftime('%F %T %z'),'complete':complete,'B1_suites':suites,'rows':rows,'pairs':pairs};write_json(P.RUNS/'summary.json',result)
 md=['# P6实验报告：开发梯度驱动的一次预算规划','',f'更新：{result["time"]}（北京时间）；complete={complete}；B1套件{suites}/45。',
 '这是开发梯度代理驱动的单次预算规划，不是在线状态分类器或已测恢复速度。不存在按技能名字硬编码早槽偏好。',
 '四组新holdout各12题，预注册主指标为四技能Joint宏平均；旧P4/P5卷不作新主指标。','', '|种子|臂|macro Joint|Calendar|非目标File|分配|tokens|','|---|---|---|---|---|---|---|']
 fmt=lambda x:'—' if x is None else f'{x:.3f}'
 for r in rows:md.append(f'|{r["seed"]}|{r["arm"]}|{fmt(r["macro_joint"])}|{fmt(r["calendar"]["joint_success"] if r["calendar"] else None)}|{fmt(r["file_nontarget"]["joint_success"] if r["file_nontarget"] else None)}|{r["allocation"]}|{r["tokens"]}|')
 md+=['','## 配对判定',json.dumps(pairs,ensure_ascii=False,indent=2)]
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
 (P.ROOT/'EXT_REPORT_20261115_p6_ZH.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
 hand=['# P6交接手册',f'更新时间：{result["time"]}（北京时间），complete={complete}。',
 '方案：P6_PREREG_20261115_devplan_ZH.md；设计/数据先冻结manifest.json，GPU只读梯度后另冻结plans_manifest.json；实现补充锁runtime_lock.json。',
 '正式队列：bash scripts/launch_p6_queue_20261115.sh；仅在校准完成、9计划已冻结且协调者审核后启动。',
 '监测：runs_ext_p6_devplan/logs/status.log、queue.log、runner.pid、gpu_child.pid；STOP粘性，不自动恢复。',
 'CPU收尾：PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 .venv/bin/python -B -m fac_tinyagent.p6_trainqueue --phase finalize',
 '完整结果：runs_ext_p6_devplan/summary.json。旧训练实现只在内存重绑定输出目录以复用，未改P5代码或文件；兼容训练审计文件叫p5_meta.json但位于P6 branches内。',
 '不得重跑已完成P5、修改冻结数据/旧实验/.venv/zxx/Small Agent；不发GPT，完成后不自动P7。']
 (P.ROOT/'EXT_HANDOVER_20261115_p6_ZH.md').write_text('\n'.join(hand)+'\n',encoding='utf-8')
 P.log('SUMMARY complete='+str(complete))


def queue():
 runtime_guard();P.safe()
 for arm in P.ARMS:
  for seed in P.SEEDS:
   P.safe();train(seed,arm);evaluate(seed,arm);finalize()
 P.log('QUEUE COMPLETE')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--phase',required=True,choices=['queue','finalize','verify']);a=p.parse_args()
 if a.phase=='verify':runtime_guard()
 else:globals()[a.phase]()
