"""Bounded local frozen-checkpoint worker with inherited safety checks."""
import os
os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',TZ='Asia/Shanghai',WANDB_MODE='disabled')
import csv,fcntl,gc,hashlib,io,json,signal,subprocess,sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from protocol import *
time.tzset()
RUN=HERE/'results';LOG=RUN/'logs'
def cmd(args):return subprocess.check_output(args,timeout=20).decode('utf-8-sig',errors='strict').strip()
def safety(allowed):
    from fac_tinyagent.p10_devdiagnosis_20261117 import inspect_safety
    state=inspect_safety(allowed)
    extra=[]
    for pat in ['runs*/STOP','acod*/STOP','acod*/results/STOP','acod*/results/logs/STOP']:
        extra.extend(str(p.relative_to(ROOT)) for p in ROOT.glob(pat))
    state['STOP']=sorted(set(state['STOP']+extra))
    projects=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name) in allowed:continue
        try:
            args=[a.decode(errors='replace') for a in (p/'cmdline').read_bytes().split(b'\0') if a]
            if not args or not Path(args[0]).name.startswith('python'):continue
            try:cwd=Path(os.readlink(p/'cwd'))
            except (PermissionError,FileNotFoundError):cwd=None
            if cwd is not None and (cwd==ROOT or ROOT in cwd.parents):projects.append({'pid':int(p.name),'argv':args,'cwd':str(cwd)})
        except (PermissionError,FileNotFoundError,ProcessLookupError):pass
    state['other_project_identity']=projects
    info=cmd(['nvidia-smi','--query-gpu=memory.free,power.draw,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits']).splitlines()[0]
    state['gpu_actual']=next(csv.reader(io.StringIO(info)))
    disk=os.statvfs(ROOT);state['disk_free_bytes']=disk.f_bavail*disk.f_frsize
    state['safe']=bool(state['safe'] and not extra and not projects and state['disk_free_bytes']>1024**3)
    return state

def stop_record(reason):
    p=LOG/'STOP'
    if not p.exists():dump(p,{'owner':'acod_round1_20261121','time':now(),'reason':reason,'auto_clear':False})

def supervise():
    RUN.mkdir(exist_ok=True);LOG.mkdir(exist_ok=True);verify()
    with (LOG/'worker.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        s=safety({os.getpid(),os.getppid()});append(LOG/'guard.jsonl',s)
        if not s['safe']:
            append(RUN/'events.jsonl',{'time':now(),'event':'PREFLIGHT_BLOCKED','state':s})
            print(json.dumps(s,ensure_ascii=False),flush=True);return 75
        if (RUN/'COMPLETE.json').exists():print('Already complete; no new inference');return 0
        assert float(s['gpu_actual'][0])>=2048,'Insufficient free VRAM'
        append(RUN/'events.jsonl',{'time':now(),'event':'SUPERVISOR_START','pid':os.getpid(),'state':s})
        started=time.monotonic()
        with (LOG/'worker.log').open('a',buffering=1) as f:
            child=subprocess.Popen([sys.executable,'-B',str(HERE/'runner.py'),'worker'],cwd=ROOT,env=os.environ,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
            append(RUN/'events.jsonl',{'time':now(),'event':'WORKER_START','pid':child.pid})
            print('WORKER_PID',child.pid,flush=True)
            while child.poll() is None:
                try:child.wait(timeout=3);break
                except subprocess.TimeoutExpired:pass
                try:
                    s=safety({os.getpid(),os.getppid(),child.pid});append(LOG/'guard.jsonl',s)
                    if s['safe'] and time.monotonic()-started<1200:continue
                    reason=s if not s['safe'] else {'deadline_seconds':1200}
                except Exception as e:reason={'inspection_error':repr(e)}
                stop_record(reason);os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=15)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                break
            rc=child.wait()
        append(RUN/'events.jsonl',{'time':now(),'event':'SUPERVISOR_END','rc':rc,'elapsed_seconds':time.monotonic()-started})
        print('SUPERVISOR_END',rc,flush=True);return rc

def digest(model,torch):
    h=hashlib.sha256();n=0
    for name,p in model.named_parameters():
        h.update(name.encode());h.update(p.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes());n+=1
    assert n>0
    return h.hexdigest()
def worker():
    import torch,transformers,peft,bitsandbytes
    from fac_tinyagent.sft.evaluate import load_eval_model,generate_with_usage,parse_final_answer
    from fac_tinyagent.sft.dataset import conversation_text
    from fac_tinyagent.replay_study import config_for
    manifest=verify();tasks=read(HERE/'tasks.json')
    assert read(HERE/'cpu_tests.json')['passed']
    done=rows(RUN/'responses.jsonl') if (RUN/'responses.jsonl').exists() else []
    completed={r['id'] for r in done};assert len(completed)==len(done)
    prior=rows(RUN/'calls_started.jsonl') if (RUN/'calls_started.jsonl').exists() else []
    assert len(prior)<224
    started=time.perf_counter()
    def terminate(sig,frame):raise SystemExit(75)
    signal.signal(signal.SIGTERM,terminate);signal.signal(signal.SIGINT,terminate)
    def deadline(sig,frame):raise TimeoutError('Single generation exceeded 60s')
    signal.signal(signal.SIGALRM,deadline)
    versions={'python':sys.version,'torch':torch.__version__,'transformers':transformers.__version__,'peft':peft.__version__,'bitsandbytes':bitsandbytes.__version__}
    append(RUN/'events.jsonl',{'time':now(),'event':'WORKER_ENV','versions':versions,'pid':os.getpid(),'existing_records':len(done)})
    for m in manifest['models']:
        seed=m['seed'];adapter=Path(m['adapter'])
        pending=[(t,v) for t in tasks for v in t['views'] if f"{seed}:{t['id']}:{v}" not in completed]
        if not pending:continue
        s=safety({os.getpid(),os.getppid()});append(LOG/'worker_guard.jsonl',s)
        if not s['safe']:stop_record(s);return 75
        print(now(),'LOAD',seed,adapter,flush=True)
        cfg=config_for('A',seed,batch_size=1)
        model,tok=load_eval_model(cfg,str(adapter))
        assert not model.training and not model.config.use_cache
        assert not any(p.requires_grad for p in model.parameters()),'Model unexpectedly trainable'
        before=digest(model,torch);torch.cuda.reset_peak_memory_stats()
        cost_path=RUN/f'input_costs_seed{seed}.json'
        costs={t['id']:{v:len(tok(conversation_text(tok,x['messages'],generation=True),add_special_tokens=False)['input_ids'])+128 for v,x in t['views'].items()} for t in tasks}
        if cost_path.exists():assert read(cost_path)==costs
        else:dump(cost_path,costs)
        tokenizer_sha=hashlib.sha256(tok.backend_tokenizer.to_str().encode()).hexdigest()
        append(RUN/'events.jsonl',{'time':now(),'event':'MODEL_LOADED','seed':seed,'model_name':cfg['model_name_or_path'],'adapter_sha256':sha(adapter/'adapter_model.safetensors'),'parameter_before':before,'tokenizer_sha256':tokenizer_sha,'config_use_cache':model.config.use_cache,'trainable_parameters':0})
        model_calls=0
        try:
            for t,v in pending:
                ident=f"{seed}:{t['id']}:{v}"
                assert not (LOG/'STOP').exists() and not (ROOT/'STOP').exists()
                previous=rows(RUN/'calls_started.jsonl') if (RUN/'calls_started.jsonl').exists() else []
                assert len(previous)<224,'Total generation attempts cap reached'
                append(RUN/'calls_started.jsonl',{'id':ident,'time':now(),'index':len(previous)+1,'max_new_tokens':128})
                signal.alarm(60)
                try:raw,usage=generate_with_usage(model,tok,t['views'][v]['messages'],128)
                finally:signal.alarm(0)
                assert usage['batch_size']==1 and usage['inference_calls']==1
                ok,y=parse_final_answer(raw)
                r={'id':ident,'time':now(),'seed':seed,'task':t['id'],'file_id':t['file_id'],'family':t['family'],'view':v,'raw':raw,'parsed':bool(ok),'answer':y,'observation':y if ok else {'UNPARSED':raw},'correct':bool(ok and key(y)==key(t['views'][v]['gold'])),'usage':usage,'answer_only_oracle_tool_prefix':True}
                append(RUN/'responses.jsonl',r);completed.add(ident);model_calls+=1
                print(now(),ident,'parsed',ok,'tokens',usage['output_tokens'],'seconds',round(usage['generation_seconds'],3),'done',len(completed),flush=True)
        finally:
            after=digest(model,torch)
            append(RUN/'model_receipts.jsonl',{'time':now(),'seed':seed,'adapter':str(adapter),'adapter_sha256':sha(adapter/'adapter_model.safetensors'),'parameter_before':before,'parameter_after':after,'parameters_unchanged':before==after,'generation_calls_this_session':model_calls,'peak_allocated_GB':torch.cuda.max_memory_allocated()/1024**3,'optimizer_updates':0})
            assert before==after
            del model,tok;gc.collect();torch.cuda.empty_cache()
    verify();data=rows(RUN/'responses.jsonl');assert len(data)==224
    dump(RUN/'COMPLETE.json',{'time':now(),'calls':len(data),'unique_ids':len({r['id'] for r in data}),'worker_elapsed_seconds':time.perf_counter()-started,'new_training':0,'scope':'oracle-tool-prefix answer generation; fixed response table'})
    print(now(),'COMPLETE',len(data),flush=True);return 0
if __name__=='__main__':
    try:sys.exit(supervise() if sys.argv[1]=='supervise' else worker())
    except BaseException as e:
        if not isinstance(e,SystemExit) or e.code not in [0,None]:
            RUN.mkdir(exist_ok=True);append(RUN/'errors.jsonl',{'time':now(),'error':repr(e),'mode':sys.argv[1]});traceback.print_exc()
        raise