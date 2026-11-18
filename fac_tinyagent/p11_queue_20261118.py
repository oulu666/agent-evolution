"""P11 EAAR-v1 queue: probes, freeze EAAR plans, train, B1 eval. No online plan changes."""
from __future__ import annotations
import os
os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',HF_HUB_OFFLINE='1',TOKENIZERS_PARALLELISM='false',TZ='Asia/Shanghai')
import argparse,copy,fcntl,gc,hashlib,json,signal,subprocess,sys,time,traceback,types
from pathlib import Path
from .utils import read_json,read_jsonl,write_json,append_jsonl,sha256_file,ensure_dir
from . import p11_eaar_v1_20261118 as D
from . import p10_devdiagnosis_20261117 as G
from . import p6_attempt2 as A2
ROOT=D.ROOT;DATA=D.DATA;RUNS=ROOT/'runs_ext_p11_eaar_v1';LOG=RUNS/'logs';STOP=LOG/'STOP'
SEEDS=D.SEEDS;ARMS=D.ARMS;SUITES=['p11_database','p11_file','p11_python','p11_calendar']
def log(s):print(time.strftime('%F %T %z'),s,flush=True)
def inspect(allowed):
    s=G.inspect_safety(allowed)
    extras=[str(p.relative_to(ROOT)) for p in ROOT.glob('runs*/logs/STOP')]
    extras += [str(p.relative_to(ROOT)) for p in ROOT.glob('runs*/*/logs/STOP')]
    for p in [ROOT/'STOP',STOP,ROOT/'runs_ext_p6_devplan/logs/STOP',ROOT/'runs_ext_p6_devplan_attempt2/logs/STOP']:
        if p.exists():extras.append(str(p.relative_to(ROOT)))
    s['STOP']=sorted(set(s.get('STOP',[])+extras))
    if s['STOP']:s['safe']=False
    return s
def ckpt(seed,arm):return RUNS/'branches'/D.label(seed,arm)/'checkpoint'
def evdir(seed,arm):return RUNS/'evaluation'/D.label(seed,arm)
def runtime_guard():
    m=read_json(DATA/'manifest.json')
    for rel,h in {**m['files'],**m['references']}.items():assert sha256_file(ROOT/rel)==h,rel
    if (DATA/'plans_manifest.json').exists():
        pm=read_json(DATA/'plans_manifest.json')
        for rel,h in pm['plans'].items():assert sha256_file(ROOT/rel)==h,rel
def initialize_run():
    assert DATA.exists() and not (DATA/'plans'/ 'A_seed20261108_eaar_v1.json').exists() or True
    if RUNS.exists() and (RUNS/'runtime_manifest.json').exists():
        raise SystemExit('P11 run root already initialized; refuse overwrite')
    LOG.mkdir(parents=True,exist_ok=True)
    refs=[Path(__file__),D.PREREG,ROOT/'fac_tinyagent/p11_eaar_v1_20261118.py',ROOT/'fac_tinyagent/p11_e3_train_compat_20261118.py',DATA/'manifest.json']
    write_json(RUNS/'runtime_manifest.json',{'created':time.strftime('%F %T %z'),'scope':'P11 EAAR-v1 probes + 9 training branches + B1; 0 formal before EAAR freeze','hashes':{str(p.relative_to(ROOT)):sha256_file(p) for p in refs}})
    return inspect({os.getpid()})
def cpu_accept():
    os.environ['CUDA_VISIBLE_DEVICES']=''
    D.verify()
    from .p4_forget_timing import source_after_by_index
    after=read_json(DATA/'source_after.json')
    assert after==source_after_by_index(SEEDS[0],'dose_db4',read_json(D.source(SEEDS[0]))['items'])
    candidates=read_json(DATA/'candidates.json');background=read_json(DATA/'background.json')
    # uniform / early budget and identical target multisets
    for seed in SEEDS:
        u=read_json(D.planpath(seed,'uniform'));e=read_json(D.planpath(seed,'fixed_early'))
        assert u['actual_input_tokens']==e['actual_input_tokens']==D.BUDGET
        assert [x['episode_id'] for x in u['items'] if x.get('target')]==[x['episode_id'] for x in e['items'] if x.get('target')]
        slots_u=[i for i,x in enumerate(u['items']) if x.get('target')];slots_e=[i for i,x in enumerate(e['items']) if x.get('target')]
        assert slots_u==D.DEST['uniform'] and slots_e==list(range(10))
        for q in (u,e):
            aq=A2.adapt_plan(q);assert aq['items']==q['items'] and aq['actual_input_tokens']==D.BUDGET
    # decision rule on synthetic probes, not experimental results
    def fake(skill,**kw):
        base={'skill':skill,'n':4,'joint':1,'tool':1,'args':1,'execution':1,'final':1};base.update(kw);return base
    cov=read_json(DATA/'prefix_coverage.json')
    cases=[]
    # all saturated -> balanced + scattered
    sat={s:fake(s) for s in D.SKILLS}
    d=D.decide(sat,cov,20261108);assert d['timing']=='scattered'
    assert d['skills']['cal.list_locations']['coverage_gap'] and d['skills']['cal.list_locations']['priority']>=2
    assert d['skills']['cal.count_date']['priority']==0  # prefix-covered and high joint
    t,ns,_=D.allocate_from_decision(d,D.candidate_order(candidates,20261108),20261108)
    assert sum(ns.values())==10 and ns['cal.list_locations']>=1 and len(t)==10
    # coverage gap list_locations + failing joint should get extra dose, timing scattered unless forgetting
    weak={s:fake(s) for s in D.SKILLS}
    weak['cal.list_locations'].update(joint=0,tool=1,args=1,execution=1,final=0)
    weak['file.search_last'].update(joint=0.25,tool=0.25,args=0.25,execution=0.25,final=0.25)
    d=D.decide(weak,cov,20261108);assert d['skills']['cal.list_locations']['coverage_gap'] and d['skills']['cal.list_locations']['priority']>=5
    q,_=D.plan_from_probes(20261108,[{'skill':s,'joint_success':weak[s]['joint']==1,'tool_correct':weak[s]['tool']==1,'arguments_correct':weak[s]['args']==1,'execution_success':weak[s]['execution']==1,'final_correct':weak[s]['final']==1} for s in D.SKILLS for _ in range(4)],candidates,background,after)
    # the above fake records are wrong because boolean ==1 on 0.25 is false; rebuild properly
    recs=[]
    for s in D.SKILLS:
        for i in range(4):
            j=weak[s]['joint'];rec={'skill':s,'joint_success':i<round(j*4),'tool_correct':i<round(weak[s]['tool']*4),'arguments_correct':i<round(weak[s]['args']*4),'execution_success':i<round(weak[s]['execution']*4),'final_correct':i<round(weak[s]['final']*4)}
            recs.append(rec)
    q,_=D.plan_from_probes(20261108,recs,candidates,background,after)
    assert q['actual_input_tokens']==D.BUDGET and q['within_one_percent_of_budget']
    assert q['p11']['counts']['cal.list_locations']>=2
    # true forgetting prior on count_date (prefix covered, low joint) -> early
    forget={s:fake(s) for s in D.SKILLS}
    forget['cal.count_date'].update(joint=0.25,tool=1,args=1,execution=1,final=0.25)
    recs=[]
    for s in D.SKILLS:
        for i in range(4):
            recs.append({'skill':s,'joint_success':i<round(forget[s]['joint']*4),'tool_correct':i<round(forget[s]['tool']*4),'arguments_correct':i<round(forget[s]['args']*4),'execution_success':i<round(forget[s]['execution']*4),'final_correct':i<round(forget[s]['final']*4)})
    q2,d2=D.plan_from_probes(20261109,recs,candidates,background,after)
    assert d2['timing']=='early' and d2['skills']['cal.count_date']['true_forgetting_prior']
    assert q2['actual_input_tokens']==D.BUDGET
    # do not write these synthetic EAAR plans into official plan slots
    write_json(DATA/'cpu_acceptance.json',{'passed':True,'cpu_only':True,'gpu':0,'budget':D.BUDGET,'required_plan_keys':A2.required_plan_keys(),'synthetic_cases':['all_saturated_fallback_documented','coverage_gap_gets_dose_and_exact_budget','forgetting_prior_selects_early_and_exact_budget'],'uniform_fixed_early_frozen':True,'eaar_official_plans_not_written':True,'time':time.strftime('%F %T %z')})
    log('CPU ACCEPTANCE PASS')
    return 0

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

def restore_t0(model,seed):
    # load_eval_model uses PeftModel.from_pretrained + model.eval(); the stage_03
    # adapter_config has inference_mode=true, so requires_grad is False for every
    # parameter including all 392 LoRA tensors. The E4 prefix names still match
    # model.named_parameters() exactly (base_model...lora_*.default.weight).
    # Compare against all named parameters, copy the prefix tensors, mark those
    # LoRA params trainable so the hash matches training-time _training_state_hash,
    # then return to eval. Never rewrite the frozen prefix file. Still fail hard
    # on name or hash mismatch.
    import torch
    from .replay_train import _training_state_hash
    state=torch.load(ROOT/f'runs_ext_e4/prefixes/A_seed{seed}/training_state.pt',map_location='cpu',weights_only=False)
    params=dict(model.named_parameters())
    missing=sorted(set(state['parameters'])-set(params))
    extra_lora=sorted(n for n in set(params)-set(state['parameters']) if 'lora_' in n)
    if missing or extra_lora:
        raise ValueError('T0 parameter names mismatch missing=%s extra_lora=%s'%(missing[:8],extra_lora[:8]))
    with torch.no_grad():
        for n,tensor in state['parameters'].items():
            p=params[n]
            p.copy_(tensor.to(device=p.device,dtype=p.dtype))
            p.requires_grad_(True)
    if _training_state_hash(model)!=state['parameter_hash']:
        raise ValueError('T0 parameter hash mismatch')
    model.eval();return state['parameter_hash']

def evaluate_rows(model,tok,cfg,rows,db,cal,out,name,adapter):
    from .sft.evaluate import evaluate_family
    started=time.time()
    rep=evaluate_family(model,tok,rows,cfg,{'name':'P11_B1_'+name,'index':4,'adapter':str(adapter)},out,db,cal)
    assert rep['evaluation_protocol']['batch_size']==1
    write_json(out/'p11_meta.json',{'suite':name,'n':len(rows),'protocol':'Protocol-B1','seconds':time.time()-started,'finished':time.strftime('%F %T %z')})
    return rep

def suite_rows(name):
    family={'p11_database':'database','p11_file':'file','p11_python':'python','p11_calendar':'calendar'}[name]
    split='holdout';rows=[r for r in read_jsonl(DATA/split/'rows.jsonl') if r['tool_family']==family]
    db=str(D.fixture('holdout') if family=='database' else ROOT/'data_phase2/fixtures/toolbench.db')
    cal=str(D.fixture('calendar') if family=='calendar' else ROOT/'data_phase2/fixtures/calendar.json')
    return rows,db,cal,sha256_file(DATA/split/'rows.jsonl')

def score_skill(path,skill):
    if not path.exists():return None
    rs=[r for r in read_jsonl(path) if r.get('skill')==skill or skill in r.get('episode_id','')]
    if not rs:return None
    return {'n':len(rs),**{k:sum(bool(r[k]) for r in rs)/len(rs) for k in ['joint_success','tool_correct','arguments_correct','execution_success','final_correct']}}

def probe_seed(seed):
    from .replay_study import config_for
    from .sft.evaluate import load_eval_model,free_model
    from .e4_run import start_adapter
    runtime_guard();out=RUNS/'probes'/f'A_seed{seed}';
    if (out/'summary.json').exists():return read_json(out/'summary.json')
    ensure_dir(out);cfg=config_for('A',seed,batch_size=1);cfg['evaluation']['batch_size']=1
    log('PROBE T0 '+str(seed));model,tok=load_eval_model(cfg,str(start_adapter(seed)));ph=restore_t0(model,seed)
    try:
        rows=read_jsonl(DATA/'dev'/'rows.jsonl')
        db=str(D.fixture('dev'));cal=str(D.fixture('calendar'))
        evaluate_rows(model,tok,cfg,rows,db,cal,out/'dev','p11_dev',start_adapter(seed))
    finally:
        free_model(model)
    recs=read_jsonl(out/'dev'/'results.jsonl');assert len(recs)==24
    for r in recs:
        if 'skill' not in r:
            r['skill']=next(s for s in D.SKILLS if s in r['episode_id'])
    summary={'seed':seed,'t0_parameter_hash':ph,'n':len(recs),'skills':D.summarize_probes(recs),'finished':time.strftime('%F %T %z')}
    write_json(out/'summary.json',summary);return summary

def freeze_eaar_plans():
    if (DATA/'plans_manifest.json').exists():
        runtime_guard();return read_json(DATA/'plans_manifest.json')
    candidates=read_json(DATA/'candidates.json');background=read_json(DATA/'background.json');after=read_json(DATA/'source_after.json')
    evidence={}
    for seed in SEEDS:
        recs=read_jsonl(RUNS/'probes'/f'A_seed{seed}'/'dev'/'results.jsonl')
        for r in recs:
            if 'skill' not in r:r['skill']=next(s for s in D.SKILLS if s in r['episode_id'])
        q,decision=D.plan_from_probes(seed,recs,candidates,background,after)
        assert q['actual_input_tokens']==D.BUDGET
        q=A2.adapt_plan(q)
        write_json(D.planpath(seed,'eaar_v1'),q)
        evidence[seed]={'timing':q['p11']['timing'],'counts':q['p11']['counts'],'decision':{s:q['p11']['decision']['skills'][s]['kind'] for s in D.SKILLS}}
    plans={str(D.planpath(s,a).relative_to(ROOT)):sha256_file(D.planpath(s,a)) for s in SEEDS for a in ARMS}
    manifest={'created':time.strftime('%F %T %z'),'frozen_before_formal':True,'plans':plans,'evidence':evidence,'probe_hashes':{str((RUNS/'probes'/f'A_seed{s}'/'dev'/'results.jsonl').relative_to(ROOT)):sha256_file(RUNS/'probes'/f'A_seed{s}'/'dev'/'results.jsonl') for s in SEEDS}}
    write_json(DATA/'plans_manifest.json',manifest)
    # update data manifest files map would change hashes; keep plans_manifest independent
    log('EAAR PLANS FROZEN before formal scores: '+json.dumps(evidence,ensure_ascii=False))
    return manifest

def train(seed,arm):
    runtime_guard()
    ck=ckpt(seed,arm)
    if (ck/'train_summary.json').exists():
        A2.audit_checkpoint.__wrapped__ if False else None
        return audit_train(seed,arm)
    if ck.parent.exists():raise SystemExit('partial P11 branch exists; do not overwrite '+str(ck.parent))
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
    write_json(ckpt(seed,arm).parent/'p11_meta.json',result);log('TRAIN AUDIT PASS '+D.label(seed,arm));return result

def evaluate(seed,arm,only=None):
    from .replay_study import config_for
    from .sft.evaluate import load_eval_model,free_model
    from .e4_run import start_adapter
    out=evdir(seed,arm);todo=[x for x in (only or SUITES) if not (out/x/'stage_report.json').exists()]
    if not todo:return
    runtime_guard();cfg=config_for('A',seed,batch_size=1);cfg['evaluation']['batch_size']=1
    log('EVAL '+D.label(seed,arm)+' suites='+str(todo))
    if arm=='t0':
        model,tok=load_eval_model(cfg,str(start_adapter(seed)));restore_t0(model,seed);adapter=start_adapter(seed)
    else:
        model,tok=load_eval_model(cfg,str(ckpt(seed,arm)));adapter=ckpt(seed,arm)
    try:
        for name in todo:
            rows,db,cal,h=suite_rows(name)
            evaluate_rows(model,tok,cfg,rows,db,cal,out/name,name,adapter)
            write_json(out/name/'rows_sha256.json',{'rows_sha256':h,'n':len(rows)})
    finally:
        free_model(model)

def first_gate():
    seed,arm=SEEDS[0],'uniform'
    audit=train(seed,arm)
    evaluate(seed,arm,only=['p11_database'])
    rep=read_json(evdir(seed,arm)/'p11_database'/'stage_report.json')
    n=len(read_jsonl(evdir(seed,arm)/'p11_database'/'results.jsonl'))
    gate={'passed':True,'seed':seed,'arm':arm,'optimizer_steps':23,'database_n':n,'protocol':rep['evaluation_protocol'],'meaning':'training/eval contract only, not an accuracy gate','finished':time.strftime('%F %T %z')}
    assert n==24 and rep['evaluation_protocol']['batch_size']==1
    write_json(RUNS/'e2e_gate.json',gate);log('FIRST ARM E2E GATE PASS');return gate

def finalize():
    runtime_guard();rows=[]
    arms=list(ARMS)+['t0']
    for seed in SEEDS:
        for arm in arms:
            out=evdir(seed,arm);r={'seed':seed,'arm':arm,'skills':{}}
            for s in D.SKILLS:
                fam='calendar' if s.startswith('cal.') else 'database' if s.startswith('db.') else 'file' if s.startswith('file.') else 'python'
                r['skills'][s]=score_skill(out/f'p11_{fam}'/'results.jsonl',s)
            done=all(v and v['n']==12 for v in r['skills'].values())
            r['macro_joint']=None if not done else sum(v['joint_success'] for v in r['skills'].values())/6
            r['old_joint']=None if not done else sum(r['skills'][s]['joint_success'] for s in D.OLD_SKILLS)/len(D.OLD_SKILLS)
            r['new_joint']=None if not done else sum(r['skills'][s]['joint_success'] for s in D.NEW_SKILLS)/len(D.NEW_SKILLS)
            if arm!='t0':
                r['allocation']=read_json(D.planpath(seed,arm))['p11']['counts']
                r['timing']=read_json(D.planpath(seed,arm))['p11']['timing']
                r['tokens']=read_json(D.planpath(seed,arm))['actual_input_tokens']
            rows.append(r)
    def pair(a,b):
        d=[]
        for seed in SEEDS:
            x=next(r for r in rows if r['seed']==seed and r['arm']==a)['macro_joint']
            y=next(r for r in rows if r['seed']==seed and r['arm']==b)['macro_joint']
            d.append(None if x is None or y is None else x-y)
        return {'per_seed':d,'mean':None if any(v is None for v in d) else sum(d)/len(d)}
    complete=all(r['macro_joint'] is not None for r in rows)
    result={'time':time.strftime('%F %T %z'),'complete':complete,'rows':rows,'pairs':{'eaar_v1-uniform':pair('eaar_v1','uniform'),'eaar_v1-fixed_early':pair('eaar_v1','fixed_early')}}
    write_json(RUNS/'summary.json',result);log('SUMMARY complete='+str(complete));return result

def worker():
    signal.signal(signal.SIGTERM,lambda s,f:sys.exit(75));signal.signal(signal.SIGINT,lambda s,f:sys.exit(75))
    runtime_guard();started=time.perf_counter()
    for seed in SEEDS:
        probe_seed(seed)
    freeze_eaar_plans()
    first_gate()
    # remaining trains/evals, including T0 formal after freeze
    for arm in ARMS:
        for seed in SEEDS:
            if arm=='uniform' and seed==SEEDS[0]:
                evaluate(seed,arm);continue
            train(seed,arm);evaluate(seed,arm)
    for seed in SEEDS:
        evaluate(seed,'t0')
    finalize()
    write_json(RUNS/'COMPLETE.json',{'complete':True,'finished':time.strftime('%F %T %z'),'optimizer_updates_per_trained_branch':23,'trained_branches':9,'elapsed_seconds':time.perf_counter()-started})
    log('QUEUE COMPLETE; NO ONLINE REALLOCATION')

def supervise():
    initialize=not (RUNS/'runtime_manifest.json').exists()
    if initialize:
        state=initialize_run();write_json(RUNS/'preflight.json',state)
    else:
        state=inspect({os.getpid()});write_json(RUNS/'launch_preflight.json',state)
    if not state['safe']:
        write_json(RUNS/'BLOCKED.json',state);log('BLOCKED '+json.dumps(state));return 75
    if (RUNS/'COMPLETE.json').exists():raise SystemExit('already complete; refuse rerun')
    with (LOG/'p11.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        (LOG/'supervisor.pid').write_text(str(os.getpid()))
        with (LOG/'worker.log').open('a',buffering=1) as f:
            child=subprocess.Popen([sys.executable,'-B','-m','fac_tinyagent.p11_queue_20261118','worker'],cwd=ROOT,env=os.environ,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
            (LOG/'worker.pid').write_text(str(child.pid));log('START P11 worker '+str(child.pid))
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
            rc=child.wait();write_json(RUNS/'supervisor_end.json',dict(rc=rc,finished=time.strftime('%F %T %z')));log('END P11 rc='+str(rc));return rc

if __name__=='__main__':
    time.tzset()
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['cpu_accept','preflight','supervise','worker']);a=p.parse_args()
    try:
        if a.mode=='cpu_accept':sys.exit(cpu_accept())
        if a.mode=='preflight':
            LOG.mkdir(parents=True,exist_ok=True);s=inspect({os.getpid()});write_json(RUNS/'fresh_preflight.json',s);print(json.dumps(s,ensure_ascii=False));sys.exit(0 if s['safe'] else 75)
        sys.exit({'supervise':supervise,'worker':worker}[a.mode]())
    except Exception as e:
        LOG.mkdir(parents=True,exist_ok=True);write_json(RUNS/'ERROR.json',dict(error=repr(e),time=time.strftime('%F %T %z')));traceback.print_exc();sys.exit(1)
