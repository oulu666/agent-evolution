"""P12 single-GPU guarded execution of frozen A/B plans and independent paired B1."""
from __future__ import annotations
import os
os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',HF_HUB_OFFLINE='1',TOKENIZERS_PARALLELISM='false',TZ='Asia/Shanghai')
import argparse,copy,fcntl,gc,json,signal,subprocess,sys,time,traceback,collections
from pathlib import Path
from .utils import read_json,read_jsonl,write_json,write_jsonl,append_jsonl,sha256_file
from . import p12_eaar_v2_20261118 as D
from . import p11_eaar_v1_20261118 as V1
from . import p11_queue_20261118 as Q1
ROOT=D.ROOT;DATA=D.DATA;RUNS=ROOT/'runs_ext_p12_eaar_v2';LOG=RUNS/'logs';STOP=LOG/'STOP'
SEEDS=D.SEEDS;ARMS=D.ARMS
log=D.log
restore_t0=Q1.restore_t0

def inspect(allowed):
    s=Q1.inspect(allowed)
    if STOP.exists():s['STOP']=sorted(set(s['STOP']+[str(STOP.relative_to(ROOT))]));s['safe']=False
    return s

def runtime_guard():return D.verify()
def initialize_run():
    runtime_guard()
    LOG.mkdir(parents=True,exist_ok=True)
    if (RUNS/'runtime_manifest.json').exists():raise SystemExit('P12 root initialized; refuse overwrite')
    write_json(RUNS/'runtime_manifest.json',{'created':time.strftime('%F %T %z'),'frozen_manifest_sha256':sha256_file(DATA/'manifest.json'),'scope':'P12 only, max 6 training branches, 12 states x 72 B1; no next experiment'})
    return inspect({os.getpid()})
def ckpt(seed,arm):return RUNS/'branches'/D.label(seed,arm)/'checkpoint'
def evdir(seed,arm):return RUNS/'evaluation'/D.label(seed,arm)
def load_extra_features():
    import torch
    from .sft.dataset import tokenize_episode
    # prefer stored ids
    cache=read_json(DATA/'train'/'calendar_extra_features.json');out={'calendar':[]}
    for row in cache:
        feat={'input_ids':row['input_ids'],'labels':row['labels'],'attention_mask':row['attention_mask']}
        meta=next(x for x in read_json(DATA/'train'/'calendar_extra_meta.json') if x['row_index']==row['row_index'])
        out['calendar'].append({**meta,'features':feat})
    return out

def train(seed,arm):
    runtime_guard()
    ck=ckpt(seed,arm)
    if (ck/'train_summary.json').exists():
        A2.audit_checkpoint.__wrapped__ if False else None
        return audit_train(seed,arm)
    if ck.parent.exists():raise SystemExit('partial P12 branch exists; do not overwrite '+str(ck.parent))
    from . import e3_data as E
    from .e3_run import guards,v3_leakage_guard
    from .p11_e3_train_compat_20261118 import train_replay_stage_e3
    from .e4_run import CALENDAR_PATH,DB_PATH,OLD,leakage_guard,start_adapter
    from .replay_study import config_for
    guards();q=read_json(D.planpath(seed,arm));cfg=config_for('A',seed,batch_size=1)
    pools={f:str(ROOT/'data_ext_e4/pool'/(f+'.jsonl')) for f in OLD};probes={f:str(ROOT/'data_ext_monitor_v2'/(f+'.jsonl')) for f in OLD}
    new=str(ROOT/'data_phase2/calendar/train.jsonl');rows=read_jsonl(new)+[r for p in [*pools.values(),*probes.values()] for r in read_jsonl(p)]
    leakage_guard(rows);v3_leakage_guard(rows)
    extra=load_extra_features()
    def override(pools,extra_pools,budget,seed):
        assert budget==D.BUDGET
        index={}
        for f,rs in list(pools.items())+list(extra_pools.items()):
            for x in rs:index[(f,x['row_index'],x['episode_id'])]=x
        for x in q['items']:
            key=(x['family'],x['row_index'],x['episode_id'])
            assert key in index,'missing planned item '+str(key)
            assert all(x[k]==index[key][k] for k in ['input_tokens','supervised_tokens']),('prepared costs differ',key)
        return copy.deepcopy(q)
    log('TRAIN '+D.label(seed,arm))
    train_replay_stage_e3(config=cfg,stage=dict(cfg['stages'][4],index=4),train_path=new,old_train_paths=pools,probe_paths=probes,previous_adapter=str(start_adapter(seed)),output_dir=str(ck),db_path=str(DB_PATH),calendar_path=str(CALENDAR_PATH),mode='targeted',replay_ratio=.10,uniform_floor=.2,prefix_dir=str(ROOT/f'runs_ext_e4/prefixes/A_seed{seed}'),target_ids=read_json(ROOT/'data_ext_e4/manifest.json')['target_ids'],target_fraction=E.TF25,target_family_weights={f:1/len(OLD) for f in OLD},plan_override=override,extra_replay_family='calendar',require_prefix_reuse=True,extra_replay_rows=extra)
    return audit_train(seed,arm)

def audit_train(seed,arm):
    # Reuse attempt2 assertions against P11 paths
    import fac_tinyagent.p6_attempt2 as M
    old_data,old_runs,old_plan,old_ckpt=M.DATA,M.RUNS,M.planpath,M.ckpt
    try:
        M.DATA=DATA;M.RUNS=RUNS;M.planpath=D.planpath;M.ckpt=ckpt
        result=M.audit_checkpoint(seed,arm)
    finally:
        M.DATA,M.RUNS,M.planpath,M.ckpt=old_data,old_runs,old_plan,old_ckpt
    write_json(ckpt(seed,arm).parent/'p12_meta.json',result);log('TRAIN AUDIT PASS '+D.label(seed,arm));return result


def same_plan(seed):
    return read_json(D.planpath(seed,ARMS[0]))['items']==read_json(D.planpath(seed,ARMS[1]))['items']

def evaluate(seed,arm):
    from .replay_study import config_for
    from .sft.evaluate import load_eval_model,evaluate_family,free_model
    from .e4_run import start_adapter
    runtime_guard();out=evdir(seed,arm)
    if (out/'COMPLETE.json').exists():raise SystemExit('P12 state already evaluated; no silent rerun')
    if arm==ARMS[1] and same_plan(seed):
        src=evdir(seed,ARMS[0]);rs=read_jsonl(src/'results.jsonl');write_jsonl(out/'results.jsonl',rs)
        write_json(out/'COMPLETE.json',{'n':72,'reused_identical_training_plan':str(src),'finished':time.strftime('%F %T %z')});return
    cfg=config_for('A',seed,batch_size=1);cfg['evaluation']['batch_size']=1
    adapter=start_adapter(seed) if arm=='t0' else (ROOT/f'runs_ext_p11_eaar_v1/branches/A_seed{seed}_eaar_v1/checkpoint' if arm=='v1' else ckpt(seed,arm))
    log('P12 EVAL '+D.label(seed,arm));model,tok=load_eval_model(cfg,str(adapter))
    if arm=='t0':restore_t0(model,seed)
    groups=collections.defaultdict(list)
    for r in read_jsonl(DATA/'holdout/rows.jsonl'):groups[(r['tool_family'],r['p12_db_path'])].append(r)
    results=[]
    try:
        for i,((family,db),rows) in enumerate(groups.items()):
            part=out/f'part_{i:02}_{family}';rep=evaluate_family(model,tok,rows,cfg,{'name':f'P12_B1_{seed}_{arm}_{i:02}','index':4,'adapter':str(adapter)},part,db,str(D.fixture('calendar')))
            assert rep['evaluation_protocol']['batch_size']==1
            rr=read_jsonl(part/'results.jsonl')
            for r in rr:r['skill']=next(s for s in D.SKILLS if s in r['episode_id'])
            results+=rr
    finally:
        free_model(model);del model,tok;gc.collect()
    assert len(results)==72 and len({r['episode_id'] for r in results})==72
    write_jsonl(out/'results.jsonl',results)
    write_json(out/'COMPLETE.json',{'n':72,'protocol':'unchanged strict two-turn B1 batch1 greedy','finished':time.strftime('%F %T %z'),'rows_sha256':sha256_file(DATA/'holdout/rows.jsonl')})
    log('P12 EVAL COMPLETE '+D.label(seed,arm))

def finalize():
    runtime_guard();states=['t0','v1']+ARMS;records={};stats={};paired={}
    for s in SEEDS:
        for a in states:
            rs=read_jsonl(evdir(s,a)/'results.jsonl');assert len(rs)==72
            records[s,a]={r['episode_id']:r for r in rs}
            per={k:sum(r['joint_success'] for r in rs if r['skill']==k) for k in D.SKILLS}
            stats[f'{s}_{a}']={'skills_correct_out_of_12':per,'old_correct_out_of_24':sum(per[k] for k in D.OLD_SKILLS),'new_correct_out_of_48':sum(per[k] for k in D.NEW_SKILLS),'macro_joint':sum(per.values())/72}
        for a,b in [('t0','v1'),('t0',ARMS[0]),('t0',ARMS[1]),('v1',ARMS[0]),('v1',ARMS[1]),(ARMS[0],ARMS[1])]:
            per={}
            for skill in D.SKILLS:
                ids=[eid for eid,r in records[s,a].items() if r['skill']==skill]
                per[skill]={'right_to_wrong':sum(records[s,a][i]['joint_success'] and not records[s,b][i]['joint_success'] for i in ids),'wrong_to_right':sum(not records[s,a][i]['joint_success'] and records[s,b][i]['joint_success'] for i in ids),'first_error_lost':dict(collections.Counter(next((k for k in ['tool_correct','arguments_correct','execution_success','final_correct'] if not records[s,b][i][k]),'none') for i in ids if records[s,a][i]['joint_success'] and not records[s,b][i]['joint_success']))}
            paired[f'{s}_{a}_to_{b}']=per
    def total(arm,key):return sum(stats[f'{s}_{arm}'][key] for s in SEEDS)
    old='old_correct_out_of_24';new='new_correct_out_of_48'
    targets={a:total(a,old)>=total('t0',old) and total(a,old)>=total('v1',old)+3 and all(stats[f'{s}_{a}'][old]>=stats[f'{s}_t0'][old]-1 for s in SEEDS) and total(a,new)>=total('v1',new) for a in ARMS}
    extra=sum(stats[f'{s}_{ARMS[1]}'][old]>stats[f'{s}_{ARMS[0]}'][old] for s in SEEDS)>=2 and total(ARMS[1],new)>=total(ARMS[0],new)
    choice=ARMS[1] if targets[ARMS[1]] and extra else (ARMS[0] if targets[ARMS[0]] else ('B_performance_only_selection_contribution_unresolved' if targets[ARMS[1]] else 'neither_no_next_experiment'))
    aggregate={a:{'macro_joint':sum(stats[f'{s}_{a}']['macro_joint'] for s in SEEDS)/3,'old_correct_out_of_72':total(a,old),'new_correct_out_of_144':total(a,new),'skills_correct_out_of_36':{k:sum(stats[f'{s}_{a}']['skills_correct_out_of_12'][k] for s in SEEDS) for k in D.SKILLS}} for a in states}
    result={'finished':time.strftime('%F %T %z'),'complete':True,'statistics':stats,'aggregate':aggregate,'paired_transitions':paired,'performance_targets':targets,'extra_B_evidence_gate':extra,'decision':choice,'limits':'exploratory post-P11; A already rule-informed through layer selection; B tests within-layer ranking only; no independent quota/pool causal ablation; no GEM equivalence; no automatic filter followup'}
    write_json(RUNS/'summary.json',result)
    text='# P12 结果与限制\n\n北京时间 '+time.strftime('%F %T %z')+'\n\n'+json.dumps({'aggregate':aggregate,'targets':targets,'decision':choice},ensure_ascii=False,indent=2)+'\n\n本轮为见过P11结果后的探索性修订。A也因高覆盖成本层选择而受规则启发；B-A仅检验同层排序增益。不能分别证明保底配额或候选扩充的因果作用；不是GEM复现。列库表新库成绩原样报告，不因掉分救榜。不自动进入filter实验。逐技能逐种子及配对转移见summary.json。\n'
    (ROOT/'EXT_REPORT_20261118_p12_eaar_v2_ZH.md').write_text(text,encoding='utf-8')
    write_json(RUNS/'COMPLETE.json',{'complete':True,'finished':time.strftime('%F %T %z'),'trained_branches':6-sum(same_plan(s) for s in SEEDS),'evaluated_logical_states':12,'logical_items':864,'physical_eval_items':864-72*sum(same_plan(s) for s in SEEDS)})
    log('P12 COMPLETE; NO NEXT EXPERIMENT')

def worker():
    signal.signal(signal.SIGTERM,lambda s,f:sys.exit(75));signal.signal(signal.SIGINT,lambda s,f:sys.exit(75))
    runtime_guard()
    for seed in SEEDS:
        for arm in ARMS:
            if arm==ARMS[1] and same_plan(seed):
                write_json(RUNS/'reuse'/f'{seed}.json',{'identical_items':True,'source_arm':ARMS[0]});continue
            train(seed,arm)
    # No blind model score is generated before all immutable plans exist and train finishes.
    for seed in SEEDS:
        for arm in ['t0','v1']+ARMS:evaluate(seed,arm)
    finalize()
def supervise():
    initialize=not (RUNS/'runtime_manifest.json').exists()
    if initialize:
        state=initialize_run();write_json(RUNS/'preflight.json',state)
    else:
        state=inspect({os.getpid()});write_json(RUNS/'launch_preflight.json',state)
    if not state['safe']:
        write_json(RUNS/'BLOCKED.json',state);log('BLOCKED '+json.dumps(state));return 75
    if (RUNS/'COMPLETE.json').exists():raise SystemExit('already complete; refuse rerun')
    with (LOG/'p12.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        (LOG/'supervisor.pid').write_text(str(os.getpid()))
        with (LOG/'worker.log').open('a',buffering=1) as f:
            child=subprocess.Popen([sys.executable,'-B','-m','fac_tinyagent.p12_queue_20261118','worker'],cwd=ROOT,env=os.environ,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
            (LOG/'worker.pid').write_text(str(child.pid));log('START P12 worker '+str(child.pid))
            while child.poll() is None:
                try:child.wait(timeout=3);break
                except subprocess.TimeoutExpired:pass
                try:
                    s=inspect({os.getpid(),child.pid});append_jsonl(LOG/'guard.jsonl',s)
                    if s['safe']:continue
                    reason=s
                except Exception as e:reason={'inspection_error':repr(e)}
                write_json(STOP,dict(stopped=time.strftime('%F %T %z'),reason=reason));log('SAFETY STOP '+json.dumps(reason));os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=15)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                break
            rc=child.wait();write_json(RUNS/'supervisor_end.json',dict(rc=rc,finished=time.strftime('%F %T %z')));log('END P12 rc='+str(rc));return rc


if __name__=='__main__':
    time.tzset();p=argparse.ArgumentParser();p.add_argument('mode',choices=['preflight','supervise','worker']);a=p.parse_args()
    try:
        if a.mode=='preflight':
            LOG.mkdir(parents=True,exist_ok=True);s=inspect({os.getpid()});write_json(RUNS/'fresh_preflight.json',s);print(json.dumps(s,ensure_ascii=False));sys.exit(0 if s['safe'] else 75)
        sys.exit({'supervise':supervise,'worker':worker}[a.mode]())
    except Exception as e:
        LOG.mkdir(parents=True,exist_ok=True);write_json(RUNS/'ERROR.json',{'error':repr(e),'time':time.strftime('%F %T %z')});traceback.print_exc();sys.exit(1)
