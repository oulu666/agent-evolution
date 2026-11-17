"""P8: two-arm prospective content intervention; no online allocator or fitted predictor."""
from __future__ import annotations
import argparse,copy,json,statistics,time
from pathlib import Path
from . import p8_decision_data_20261115 as D
from .utils import read_json,read_jsonl,write_json,write_jsonl,sha256_file,ensure_dir
ROOT=D.ROOT;DATA=D.DATA;RUNS=D.RUN;SEEDS=D.SEEDS;ARMS=D.ARMS;SKILLS=D.SKILLS
REPORT=ROOT/'EXT_REPORT_20261115_p8_decision_ZH.md';HANDOVER=ROOT/'EXT_HANDOVER_20261115_p8_decision_ZH.md'
SUITES=['database','file','python','calendar','nontarget_database','nontarget_file','nontarget_python']
STOP=RUNS/'logs/STOP'
def log(s):D.log('P8 '+s)
def safe():
 if STOP.exists():raise SystemExit('P8 safety STOP, do not clear automatically')
 from .p0_run import refuse_if_game
 refuse_if_game()
def runtime_guard():
 m=read_json(DATA/'manifest.json')
 for f,h in m['files'].items():assert sha256_file(ROOT/f)==h,f
 assert read_json(RUNS/'cpu_contract/acceptance.json')['status']=='PASS'
def ckpt(seed,arm):return D.oldck(seed) if arm=='original' else D.ckpt(seed)
def audit_checkpoint(seed):
 ck=ckpt(seed,'decision');q=read_json(D.planpath(seed));s=read_json(ck/'train_summary.json');a=read_json(ck/'optimizer_step_audit.json');events=read_jsonl(ck/'optimizer_update_log.jsonl');logs=read_jsonl(ck/'training_log.jsonl');old=read_jsonl(D.oldck(seed)/'training_log.jsonl')
 assert s['completed'] and s['optimizer_steps']==23 and s['partial_accumulation_microsteps']==6
 assert a['prefix_updates']==10 and a['suffix_actual_optimizer_steps']==13 and a['total_actual_optimizer_steps']==23 and a['tail_actual_steps']==1
 assert len(events)==13 and events[-1]['tail_flush'] and events[-1]['microstep']==182
 assert len(logs)==102 and s['replay_samples']==22 and s['replay_input_tokens']==q['actual_input_tokens'] and s['replay_supervised_tokens']==sum(x['supervised_tokens'] for x in q['items'])
 assert [(x['kind'],x['new_position'],x['microstep'],x['optimizer_steps']) for x in logs]==[(x['kind'],x['new_position'],x['microstep'],x['optimizer_steps']) for x in old]
 assert [(x['episode_id'],x['input_tokens']) for x in logs if x['kind']=='new']==[(x['episode_id'],x['input_tokens']) for x in old if x['kind']=='new']
 assert s['midpoint_trainable_state_sha256']==read_json(D.oldck(seed)/'train_summary.json')['midpoint_trainable_state_sha256']
 assert (ck/'prefix_full_state_receipt.json').exists() and (ck/'full_state_receipt.json').exists()
 write_json(ck.parent/'p8_train_audit.json',{'status':'PASS','actual_total_updates':23,'actual_new_updates':13,'tokens':q['actual_input_tokens'],'supervised_tokens':s['replay_supervised_tokens'],'packing_calendar_timing_identical_to_A':True,'exact_fullstate_roundtrip':True,'finished':time.strftime('%F %T %z')})
def train(seed):
 runtime_guard();safe();ck=ckpt(seed,'decision');assert not ck.parent.exists(),'fresh branch only; preserve partial attempt'
 from . import e3_data as E
 from .p8_train_20261115 import train_replay_stage_e3
 from .e4_run import CALENDAR_PATH,DB_PATH,OLD,start_adapter
 from .replay_study import config_for
 cfg=config_for('A',seed,batch_size=1);q=read_json(D.planpath(seed));pools={f:str(ROOT/f'data_ext_e4/pool/{f}.jsonl') for f in OLD};probes={f:str(ROOT/f'data_ext_monitor_v2/{f}.jsonl') for f in OLD};extra={f:str(DATA/f'pools/{f}.jsonl') for f in OLD}
 def override(pools,extra_pools,budget,seed):
  assert budget==7494
  index={(f,x['row_index'],x['episode_id']):x for f,rs in pools.items() for x in rs}
  for x in q['items']:
   y=index[(x['family'],x['row_index'],x['episode_id'])];assert all(x[k]==y[k] for k in ['input_tokens','supervised_tokens'])
  return copy.deepcopy(q)
 targets=read_json(ROOT/'data_ext_e4/manifest.json')['target_ids']
 targets={f:list(targets.get(f,[]))+[r['episode_id'] for r in read_jsonl(extra[f])] for f in OLD}
 log('TRAIN '+D.label(seed,'decision'))
 train_replay_stage_e3(config=cfg,stage=dict(cfg['stages'][4],index=4),train_path=str(ROOT/'data_phase2/calendar/train.jsonl'),old_train_paths=pools,probe_paths=probes,previous_adapter=str(start_adapter(seed)),output_dir=str(ck),db_path=str(DB_PATH),calendar_path=str(CALENDAR_PATH),mode='targeted',replay_ratio=.10,uniform_floor=.2,prefix_dir=str(ROOT/f'runs_ext_e4/prefixes/A_seed{seed}'),target_ids=targets,target_fraction=E.TF25,target_family_weights={f:1/len(OLD) for f in OLD},plan_override=override,require_prefix_reuse=True,additional_train_paths=extra)
 audit_checkpoint(seed);runtime_guard();log('TRAIN AUDIT PASS '+str(seed)+' total23 new13 exact_fullstate=PASS')
def suite_rows(name):
 if name in ['database','file','python']:
  return [r for r in read_jsonl(DATA/'holdout.jsonl') if r['tool_family']==name],str(D.fixture('holdout')),str(ROOT/'data_phase2/fixtures/calendar.json')
 if name=='calendar':
  from .p1_run import suite_rows as oldrows
  rows,db,cal,h=oldrows('v3fix');return rows,db,cal
 fam=name.split('_')[1]
 from .p1_run import suite_rows as oldrows
 _,db,cal,_=oldrows('p2_'+fam)
 return read_jsonl(DATA/(name+'.jsonl')),db,cal
def evaluate(seed,arm,only=None):
 from .replay_study import config_for
 from .sft.evaluate import load_eval_model,evaluate_family,free_model
 out=RUNS/'evaluation'/D.label(seed,arm);todo=[s for s in (only or SUITES) if not (out/s/'stage_report.json').exists()]
 if not todo:return
 runtime_guard();safe();cfg=config_for('A',seed,batch_size=1);cfg['evaluation']['batch_size']=1;log('EVAL '+D.label(seed,arm)+' '+str(todo));model,tok=load_eval_model(cfg,str(ckpt(seed,arm)))
 try:
  for name in todo:
   safe();rows,db,cal=suite_rows(name);t=time.time();rep=evaluate_family(model,tok,rows,cfg,{'name':'P8_'+D.label(seed,arm),'index':4,'adapter':str(ckpt(seed,arm))},out/name,db,cal);assert rep['evaluation_protocol']['batch_size']==1
   write_json(out/name/'p8_meta.json',{'n':len(rows),'protocol':'Protocol-B1','seconds':time.time()-t,'finished':time.strftime('%F %T %z')})
 finally:free_model(model)
def score(rows):
 return {'n':len(rows),**{k:statistics.mean(bool(r[k]) for r in rows) for k in ['joint_success','tool_correct','arguments_correct','execution_success','final_correct']}}
def finalize(*,allow_cpu_mock=False):
 runtime_guard();rows=[];suite_count=0
 for seed in SEEDS:
  for arm in ARMS:
   out=RUNS/'evaluation'/D.label(seed,arm);entry={'seed':seed,'arm':arm,'skills':{},'side_effects':{},'replay_tokens':7494 if arm=='original' else read_json(D.planpath(seed))['actual_input_tokens']}
   for name in SUITES:
    p=out/name/'stage_report.json'
    if not p.exists():continue
    rep=read_json(p);assert rep['evaluation_protocol']['batch_size']==1
    if rep.get('synthetic_cpu_contract'):assert allow_cpu_mock and 'cpu_contract' in str(RUNS)
    suite_count+=1;rs=read_jsonl(out/name/'results.jsonl')
    if name in ['database','file','python']:
     for k in sorted({k for r in rs for k in r['skill_labels']}):
      val=score([r for r in rs if k in r['skill_labels']]);(entry['skills'] if k in SKILLS else entry['side_effects'])[k]=val
    else:entry['side_effects'][name]=score(rs)
   entry['macro_joint']=statistics.mean(entry['skills'][k]['joint_success'] for k in SKILLS) if len(entry['skills'])==4 else None;rows.append(entry)
 diffs=[]
 for seed in SEEDS:
  a=next(r for r in rows if r['seed']==seed and r['arm']=='original')['macro_joint'];b=next(r for r in rows if r['seed']==seed and r['arm']=='decision')['macro_joint'];diffs.append(None if a is None or b is None else b-a)
 complete=suite_count==42 and all(r['macro_joint'] is not None for r in rows);mean=statistics.mean(diffs) if all(x is not None for x in diffs) else None
 result={'time':time.strftime('%F %T %z'),'complete':complete,'synthetic_cpu_contract':allow_cpu_mock,'B1_suites':suite_count,'rows':rows,'B_minus_A':{'per_seed':diffs,'mean':mean},'preregistered_content_support':complete and all(x>0 for x in diffs) and mean>=.10-1e-12}
 write_json(RUNS/'summary.json',result)
 md=['# P8决策对照经验干预报告',f'更新时间：{result["time"]}（北京时间）；complete={complete}，B1 {suite_count}/42。','本轮只检验经验包信息是否改变严格Joint，不训练收益回归、不比较无独立信号的C，不声称EAAR已成功。','|seed|arm|新holdout四技能Joint宏平均|replay input tokens|','|---|---|---|---|']
 for r in rows:md.append(f'|{r["seed"]}|{r["arm"]}|{r["macro_joint"]}|{r["replay_tokens"]}|')
 md+=['## 配对差B−A',json.dumps(result['B_minus_A'],ensure_ascii=False,indent=2),'预注册判据：3/3种子差值>0且均值>=0.10；本次达到='+str(result['preregistered_content_support'])+'。','## 预算与复用','A只读复用P6 balanced_uniform真实最终adapter；B从相同step80前缀训练，保留完全相同12背景条目、22条经验packing及Calendar序列/槽位；仅替换10个目标槽。都23累计更新（前缀10+新增13）。B输入token差异<=1%，无填充，监督token逐臂报告在cpu_data_checks.json，不能冒称精确相同token/监督量。','File目标槽包含first/last合法对照正例，其他为新schema实体、必须WHERE/tie的SQL与中央值函数正例。是整个经验包对照，不把多样性/措辞/输入内容各自宣称独立因果。','主新题48（每技能12），另8题first/mean行为控制；dev16未作GPU选策略；Calendar30与非目标各族4题副作用单列summary。旧P6/P7正式卷不作新主指标。','## 逐技能和副作用',json.dumps(rows,ensure_ascii=False,indent=2),'主效应与副作用需并列判断。未达到时不自动加臂/改题/启动P9。']
 REPORT.write_text('\n\n'.join(md)+'\n')
 HANDOVER.write_text('P8输出runs_ext_p8_decision_20261115；方案P8_PREREG_20261115_decision_ZH.md；输入与代码manifest在data_ext_p8_decision_20261115/manifest.json。\n完整为QUEUE COMPLETE + END queue rc=0 + summary.complete=true + 42套B1；首关e2e_gate.json。\n监测logs/status.log、queue.log、STOP、runner.pid、gpu_child.pid。安全STOP不自动清除或恢复。\nCPU收尾：PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 .venv/bin/python -B -m fac_tinyagent.p8_decision_20261115 --phase finalize\n没有自动C/P9，无外部GPT发送。\n')
 log('SUMMARY complete='+str(complete))
def queue():
 runtime_guard();safe();seed=SEEDS[0];train(seed);evaluate(seed,'decision',only=['database'])
 out=RUNS/'evaluation'/D.label(seed,'decision')/'database';assert len(read_jsonl(out/'results.jsonl'))==24
 write_json(RUNS/'e2e_gate.json',{'status':'PASS','first':D.label(seed,'decision'),'train_summary_completed':True,'total_updates':23,'first_B1_n':24,'scores_not_used_to_gate':True,'time':time.strftime('%F %T %z')});log('E2E GATE PASS: real full training summary + actual 23 + exact fullstate + first B1; release remaining comparisons')
 for seed in SEEDS:
  if seed!=SEEDS[0]:train(seed)
  evaluate(seed,'decision');finalize();evaluate(seed,'original');finalize()
 log('QUEUE COMPLETE')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--phase',required=True,choices=['queue','finalize','verify']);args=p.parse_args();runtime_guard() if args.phase=='verify' else globals()[args.phase]()
