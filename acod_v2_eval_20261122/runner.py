"""Bounded v2 heldout response collection; gold/groups never parsed in worker."""
import os
os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',TZ='Asia/Shanghai',WANDB_MODE='disabled')
import csv,fcntl,gc,io,signal,subprocess,traceback
from lock_protocol import *
RUN=HERE/'results';LOG=RUN/'logs'
def cmd(args):return subprocess.check_output(args,timeout=20).decode('utf-8-sig',errors='strict').strip()
def safety(allowed):
    from fac_tinyagent.p10_devdiagnosis_20261117 import inspect_safety
    s=inspect_safety(allowed);extra=[]
    for pattern in ['runs*/STOP','acod*/STOP','acod*/results/STOP','acod*/results/logs/STOP']:
        extra += [str(p.relative_to(ROOT)) for p in ROOT.glob(pattern)]
    s['STOP']=sorted(set(s['STOP']+extra));projects=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name) in allowed:continue
        try:
            args=[a.decode(errors='replace') for a in (p/'cmdline').read_bytes().split(b'\0') if a]
            if not args or not Path(args[0]).name.startswith('python'):continue
            try:cwd=Path(os.readlink(p/'cwd'))
            except (PermissionError,FileNotFoundError):cwd=None
            if cwd is not None and (cwd==ROOT or ROOT in cwd.parents):projects.append({'pid':int(p.name),'argv':args,'cwd':str(cwd)})
        except (PermissionError,FileNotFoundError,ProcessLookupError):pass
    s['other_project_identity']=projects
    s['gpu_actual']=next(csv.reader(io.StringIO(cmd(['nvidia-smi','--query-gpu=memory.free,power.draw,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits']).splitlines()[0])))
    disk=os.statvfs(ROOT);s['disk_free_bytes']=disk.f_bavail*disk.f_frsize
    s['safe']=bool(s['safe'] and not extra and not projects and s['disk_free_bytes']>1024**3)
    return s

def stop_record(reason):
    if not (LOG/'STOP').exists():save(LOG/'STOP',{'owner':'acod_v2_eval_20261122','time':now(),'reason':reason,'auto_clear':False})
def digest(model,torch):
    h=hashlib.sha256();n=0
    for name,p in model.named_parameters():
        h.update(name.encode());h.update(p.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes());n+=1
    assert n>0
    return h.hexdigest()
def supervise():
    RUN.mkdir(exist_ok=True);LOG.mkdir(exist_ok=True);lock=verify()
    with (LOG/'worker.lock').open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        s=safety({os.getpid(),os.getppid()});append(LOG/'guard.jsonl',s)
        if not s['safe']:
            append(RUN/'events.jsonl',{'time':now(),'event':'PREFLIGHT_BLOCKED','state':s});print(json.dumps(s),flush=True);return 75
        if (RUN/'COMPLETE.json').exists():print('Already completed; no new calls');return 0
        assert float(s['gpu_actual'][0])>=2048
        append(RUN/'events.jsonl',{'time':now(),'event':'SUPERVISOR_START','pid':os.getpid(),'state':s});start=time.monotonic()
        with (LOG/'worker.log').open('a',buffering=1) as out:
            child=subprocess.Popen([sys.executable,'-B',str(HERE/'runner.py'),'worker'],cwd=ROOT,stdout=out,stderr=subprocess.STDOUT,env=os.environ,start_new_session=True)
            append(RUN/'events.jsonl',{'time':now(),'event':'WORKER_START','pid':child.pid});print('WORKER_PID',child.pid,flush=True)
            while child.poll() is None:
                try:child.wait(timeout=3);break
                except subprocess.TimeoutExpired:pass
                try:
                    s=safety({os.getpid(),os.getppid(),child.pid});append(LOG/'guard.jsonl',s)
                    if s['safe'] and time.monotonic()-start<1500:continue
                    reason=s if not s['safe'] else {'deadline_seconds':1500}
                except Exception as e:reason={'inspection_error':repr(e)}
                stop_record(reason);os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=15)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                break
            rc=child.wait()
        append(RUN/'events.jsonl',{'time':now(),'event':'SUPERVISOR_END','rc':rc,'elapsed_seconds':time.monotonic()-start});print('SUPERVISOR_END',rc,flush=True)
        return rc

def worker():
    import torch,transformers,peft,bitsandbytes
    from fac_tinyagent.sft.evaluate import load_eval_model,generate_with_usage
    from fac_tinyagent.replay_study import config_for
    lock=verify();cases=load_public(V2/'data/heldout/public/cases.jsonl');assert len(cases)==16
    planned={p['case_id']:p for p in lock['plans']};done={r['id'] for r in rows(RUN/'responses.jsonl')}
    assert len(rows(RUN/'calls_started.jsonl'))<224
    versions={name:importlib.metadata.version(name) for name in ['torch','transformers','peft','bitsandbytes']}
    assert versions==lock['installed_package_versions']
    append(RUN/'events.jsonl',{'time':now(),'event':'WORKER_ENV','python':sys.version,'versions':versions,'pid':os.getpid(),'existing_records':len(done)})
    def stop(sig,frame):raise SystemExit(75)
    def deadline(sig,frame):raise TimeoutError('generate exceeded 60 seconds')
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGALRM,deadline)
    started=time.perf_counter()
    for identity in lock['models']:
        seed=identity['seed'];pending=[(c,v) for c in cases for v in ('original',*POOL,'reserved') if f"{seed}:{c['case_id']}:{v}" not in done]
        if not pending:continue
        s=safety({os.getpid(),os.getppid()});append(LOG/'worker_guard.jsonl',s)
        if not s['safe']:stop_record(s);return 75
        print(now(),'LOAD',seed,flush=True)
        cfg=config_for('A',seed,batch_size=1);assert cfg['model_name_or_path']==identity['model_name_or_path']
        model,tok=load_eval_model(cfg,identity['adapter'])
        assert not model.training and not model.config.use_cache and not any(p.requires_grad for p in model.parameters())
        before=digest(model,torch);torch.cuda.reset_peak_memory_stats();session_calls=0
        append(RUN/'events.jsonl',{'time':now(),'event':'MODEL_LOADED','seed':seed,'adapter':identity['adapter'],'adapter_sha256':sha(Path(identity['adapter'])/'adapter_model.safetensors'),'parameter_digest_before':before,'trainable_parameters':0,'use_cache':model.config.use_cache,'tokenizer_sha256':hashlib.sha256(tok.backend_tokenizer.to_str().encode()).hexdigest()})
        try:
            for c,v in pending:
                ident=f"{seed}:{c['case_id']}:{v}";messages=model_messages(c,v)
                mh=hashlib.sha256(canonical(messages).encode()).hexdigest();assert mh==planned[c['case_id']]['messages_sha256'][v]
                assert not (LOG/'STOP').exists() and not (ROOT/'STOP').exists()
                previous=rows(RUN/'calls_started.jsonl');assert len(previous)<224
                append(RUN/'calls_started.jsonl',{'time':now(),'id':ident,'index':len(previous)+1,'message_sha256':mh,'max_new_tokens':128})
                signal.alarm(60)
                try:raw,usage=generate_with_usage(model,tok,messages,128)
                except BaseException as e:
                    append(RUN/'call_failures.jsonl',{'time':now(),'id':ident,'error':repr(e)});raise
                finally:signal.alarm(0)
                assert usage['batch_size']==1 and usage['inference_calls']==1
                append(RUN/'responses.jsonl',{'id':ident,'time':now(),'seed':seed,'case_id':c['case_id'],'view':v,'raw':raw,'message_sha256':mh,'usage':usage,'scope':'frozen_public_tool_observation_answer_only'})
                done.add(ident);session_calls+=1
                print(now(),ident,'output_tokens',usage['output_tokens'],'seconds',round(usage['generation_seconds'],3),'done',len(done),flush=True)
        finally:
            after=digest(model,torch)
            append(RUN/'model_receipts.jsonl',{'time':now(),'seed':seed,'adapter_sha256':sha(Path(identity['adapter'])/'adapter_model.safetensors'),'parameter_digest_before':before,'parameter_digest_after':after,'parameters_unchanged':before==after,'generation_calls':session_calls,'peak_allocated_GB':torch.cuda.max_memory_allocated()/1024**3,'optimizer_updates':0})
            assert before==after
            del model,tok;gc.collect();torch.cuda.empty_cache()
    verify();data=rows(RUN/'responses.jsonl');assert len(data)==224 and len({r['id'] for r in data})==224
    save(RUN/'COMPLETE.json',{'time':now(),'completed_generations':224,'elapsed_worker_seconds':time.perf_counter()-started,'optimizer_updates':0,'exposure_status':'All v2 heldout inputs and their natural outputs now exposed for future method development; never reuse as new independent v3 final test.'})
    print(now(),'COMPLETE 224',flush=True);return 0
if __name__=='__main__':
    try:sys.exit(supervise() if sys.argv[1]=='supervise' else worker())
    except BaseException as e:
        if not isinstance(e,SystemExit) or e.code not in [0,None]:
            RUN.mkdir(exist_ok=True);append(RUN/'errors.jsonl',{'time':now(),'mode':sys.argv[1],'error':repr(e)});traceback.print_exc()
        raise