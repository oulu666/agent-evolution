"""Authorized 72-call frozen development diagnosis only. No training or formal evaluation."""
import os
os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',HF_HUB_OFFLINE='1',TOKENIZERS_PARALLELISM='false',TZ='Asia/Shanghai')
import argparse,collections,csv,datetime,fcntl,gc,hashlib,io,json,signal,subprocess,sys,time,traceback
from pathlib import Path
from .utils import read_json,read_jsonl,write_json,append_jsonl,canonical_json,sha256_file
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data_ext_p10_twoview_cpu_20261117';RUN=ROOT/'runs_ext_p10_devdiagnosis_20261117';LOG=RUN/'logs';SEEDS=[20261108,20261109,20261110]
time.tzset()
def log(s):print(time.strftime('%F %T %z'),s,flush=True)
def read_cmd(cmd):return subprocess.check_output(cmd,timeout=20).decode('utf-8-sig',errors='strict').strip()
def inspect_safety(allowed):
    ps=r"$ErrorActionPreference='Stop';[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);$p=@(Get-Process -ErrorAction Stop);[pscustomobject]@{process_count=$p.Count;game=(@($p | Where-Object {$_.ProcessName -match 'r5apex'}).Count -gt 0)} | ConvertTo-Json -Compress"
    win=json.loads(read_cmd(['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-NonInteractive','-Command',ps]));assert win['process_count']>0 and isinstance(win['game'],bool)
    power=float(read_cmd(['nvidia-smi','--query-gpu=enforced.power.limit','--format=csv,noheader,nounits']).splitlines()[0])
    raw=read_cmd(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader']);compute=[];others=[]
    for row in csv.reader(io.StringIO(raw)):
        if not row:continue
        pid=row[0].strip();entry={'pid':pid,'process':','.join(row[1:]).strip()};compute.append(entry)
        if not pid.isdigit() or int(pid) not in allowed:others.append(entry)
    projects=[]
    for line in read_cmd(['ps','-eo','pid=,args=']).splitlines():
        bits=line.strip().split(None,1)
        if len(bits)!=2:continue
        pid,cmd=bits
        if 'python' in cmd and ('fac_tinyagent.' in cmd or 'scripts/run_p' in cmd or 'scripts/launch_p' in cmd) and int(pid) not in allowed:projects.append({'pid':pid,'command':cmd})
    stop=[str(p.relative_to(ROOT)) for p in ROOT.glob('runs*/logs/STOP')]
    for p in [ROOT/'STOP',RUN/'STOP']:
        if p.exists():stop.append(str(p.relative_to(ROOT)))
    return dict(time=time.strftime('%F %T %z'),windows=win,power_limit_W=power,compute=compute,other_compute=others,other_project_python=projects,STOP=stop,safe=not win['game'] and power>=60 and not others and not projects and not stop)

def verify_inputs():
    m=read_json(DATA/'manifest.json')
    for group in ['hashes','inherited_P9_hashes']:
        for p,h in m[group].items():assert sha256_file(ROOT/p)==h,'frozen input changed '+p
    own=read_json(RUN/'runtime_manifest.json')
    for p,h in own['hashes'].items():assert sha256_file(ROOT/p)==h,'dev runtime changed '+p

def initialize():
    LOG.mkdir(parents=True,exist_ok=True)
    assert not (RUN/'runtime_manifest.json').exists(),'Existing dev attempt; do not rerun'
    paths=[Path(__file__),ROOT/'P10_DEV_STAGE_20261117_ZH.md',DATA/'manifest.json']
    write_json(RUN/'runtime_manifest.json',dict(created=time.strftime('%F %T %z'),scope='72 frozen dev calls only; zero training; zero formal calls',hashes={str(p.relative_to(ROOT)):sha256_file(p) for p in paths}))
    state=inspect_safety({os.getpid()});write_json(RUN/'preflight.json',state);print(json.dumps(state,ensure_ascii=False));return 0 if state['safe'] else 75

def supervise():
    assert (RUN/'runtime_manifest.json').exists();assert not (RUN/'records.jsonl').exists(),'No automatic rerun/resume'
    with (LOG/'dev.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);verify_inputs()
        state=inspect_safety({os.getpid()});write_json(RUN/'launch_preflight.json',state)
        if not state['safe']:write_json(RUN/'BLOCKED.json',state);log('BLOCKED preflight '+json.dumps(state));return 75
        (LOG/'supervisor.pid').write_text(str(os.getpid()))
        with (LOG/'worker.log').open('x',buffering=1) as f:
            child=subprocess.Popen([sys.executable,'-B','-m','fac_tinyagent.p10_devdiagnosis_20261117','worker'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,env=os.environ,start_new_session=True)
            (LOG/'worker.pid').write_text(str(child.pid));log('START dev worker '+str(child.pid))
            while child.poll() is None:
                try:child.wait(timeout=3);break
                except subprocess.TimeoutExpired:pass
                try:
                    state=inspect_safety({os.getpid(),child.pid});append_jsonl(LOG/'guard.jsonl',state)
                    if state['safe']:continue
                    reason=state
                except Exception as e:reason={'inspection_error':repr(e)}
                write_json(LOG/'STOP',dict(stopped=time.strftime('%F %T %z'),reason=reason));log('SAFETY STOP '+json.dumps(reason))
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=15)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                break
            rc=child.wait();write_json(RUN/'supervisor_end.json',dict(rc=rc,finished=time.strftime('%F %T %z')));log('END dev rc='+str(rc));return rc

def worker():
    import torch
    from .sft.evaluate import load_eval_model,generate_with_usage,parse_final_answer,_evaluate_tool_prediction
    from .replay_study import config_for
    from .metrics import answers_equal,joint_success
    from . import p9_counterfactual_20261117 as P9
    verify_inputs();assert not (RUN/'records.jsonl').exists();rows=read_jsonl(DATA/'dev.jsonl');assert len(rows)==8 and len({r['case'] for r in rows})==4
    for r in rows:
        g=_evaluate_tool_prediction(r,canonical_json({'tool':r['expected_tool'],'arguments':r['expected_arguments']}),str(P9.DB),str(P9.CAL));assert all(g[k] for k in ['tool_correct','arguments_correct','execution_success'])
    def stop(sig,frame):raise SystemExit(75)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    start=time.perf_counter();calls=0;all_records=[];model_receipts=[]
    def infer(model,tok,messages,tag):
        nonlocal calls
        assert calls<72,'72-call cap';assert not (LOG/'STOP').exists()
        calls+=1;append_jsonl(RUN/'calls_started.jsonl',{'index':calls,'tag':tag,'time':time.strftime('%F %T %z')})
        raw,u=generate_with_usage(model,tok,messages,128);assert u['inference_calls']==1 and u['batch_size']==1
        append_jsonl(RUN/'calls_completed.jsonl',dict(index=calls,tag=tag,**u));return raw,u
    def weights(model):
        h=hashlib.sha256();n=0
        for name,p in model.named_parameters():
            if 'lora_' in name:
                a=p.detach().cpu().contiguous();h.update(name.encode());h.update(a.view(torch.uint8).numpy().tobytes());n+=1
        assert n>0;return h.hexdigest()
    for seed in SEEDS:
        plan=read_json(DATA/f'plan_seed{seed}.json');adapter=Path(plan['reuse_ordinary_checkpoint']);old=read_json(adapter.parent/'complete.json');assert sha256_file(adapter/'adapter_model.safetensors')==old['adapter_sha256']
        log('LOAD ordinary '+str(seed));model,tok=load_eval_model(config_for('A',seed,batch_size=1),str(adapter));assert not model.training
        before=weights(model);torch.cuda.reset_peak_memory_stats();begin=calls
        for case in sorted({r['case'] for r in rows}):
            group=[]
            for kind in ['normal','reversed']:
                for intent in ['first','last']:
                    r=next(r for r in rows if r['case']==case and r['intent']==intent);usage=[];tag=f'{seed}:{case}:{kind}:{intent}'
                    item=dict(seed=seed,case=case,kind=kind,intent=intent,episode_id=r['episode_id'],n_matches=r['n_matches'],expected_answer=r['expected_final_answer'])
                    if kind=='normal':
                        raw,u=infer(model,tok,r['messages'][:2],tag+':tool');usage.append(u);res=_evaluate_tool_prediction(r,raw,str(P9.DB),str(P9.CAL));item.update(res)
                        messages=r['messages'][:2]+[{'role':'assistant','content':raw or '{}'},{'role':'user','content':'TOOL RESULT:\n'+res['observation']}];obs=res['observation']
                    else:
                        obj=json.loads(r['expected_observation']);obj['result'].reverse();obs=canonical_json(obj);messages=r['messages'][:3]+[{'role':'user','content':'TOOL RESULT:\n'+obs}]
                    answer,u=infer(model,tok,messages,tag+':answer');usage.append(u);ok,pred=parse_final_answer(answer)
                    item.update(answer_raw=answer,predicted_answer=pred,parsed_final=bool(ok),final_correct=bool(ok and answers_equal(pred,r['expected_final_answer'])),usage=usage,displayed_observation=obs)
                    if kind=='normal':item['joint_success']=joint_success(item)
                    obj=json.loads(obs);matches=obj.get('result',[]) if obj.get('ok') else []
                    if isinstance(matches,list) and matches:
                        texts=[x['text'] for x in matches];item['answer_class']='display_first' if pred==texts[0] else 'display_last' if pred==texts[-1] else 'display_interior' if pred in texts[1:-1] else 'other'
                    else:item['answer_class']='no_valid_matches'
                    append_jsonl(RUN/'records.jsonl',item);group.append(item);all_records.append(item)
            log(f'DEV {seed} case{case} done calls={calls}/72')
            if seed==SEEDS[0] and case==min(r['case'] for r in rows):
                assert calls==6 and len(group)==4 and weights(model)==before
                write_json(RUN/'e2e_gate.json',dict(passed=True,seed=seed,case=case,records=4,inference_calls=6,optimizer_updates=0,LoRA_unchanged=True,meaning='Generation/scoring/persistence contract; not an accuracy or treatment success gate'))
                log('FIRST GROUP E2E PASS')
        after=weights(model);assert before==after;assert calls-begin==24
        model_receipts.append(dict(seed=seed,adapter_sha256=old['adapter_sha256'],live_LoRA_before=before,live_LoRA_after=after,inference_calls=24,peak_gpu_GB=torch.cuda.max_memory_allocated()/1024**3))
        del model,tok;gc.collect();torch.cuda.empty_cache()
    assert calls==72 and len(all_records)==48;verify_inputs()
    write_json(RUN/'model_receipts.json',model_receipts);write_json(RUN/'COMPLETE.json',dict(complete=True,finished=time.strftime('%F %T %z'),inference_calls=72,records=48,optimizer_updates=0,formal_calls=0,elapsed_seconds=time.perf_counter()-start));log('DEV COMPLETE 72/72; NO TRAINING AUTHORIZED')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['preflight','supervise','worker']);a=p.parse_args()
    try:sys.exit({'preflight':initialize,'supervise':supervise,'worker':worker}[a.mode]())
    except Exception as e:
        LOG.mkdir(parents=True,exist_ok=True);write_json(RUN/'ERROR.json',dict(error=repr(e),time=time.strftime('%F %T %z')));traceback.print_exc();sys.exit(1)