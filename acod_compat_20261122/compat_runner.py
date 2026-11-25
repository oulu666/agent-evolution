"""12 fixed compatibility calls only; scorer/gold is not opened in collection."""
from common import *
import subprocess,csv,io,signal,gc,traceback,fcntl
RUN=HERE/'results';LOG=RUN/'logs'
def safety(allowed):
 from fac_tinyagent.p10_devdiagnosis_20261117 import inspect_safety
 s=inspect_safety(allowed);m=read(HERE/'FREEZE_MANIFEST.json');allstop=set(s['STOP'])
 for pat in ['runs*/STOP','acod*/STOP','acod*/results/STOP','acod*/results/logs/STOP']:
  allstop.update(str(p.relative_to(ROOT)) for p in ROOT.glob(pat))
 isolated=[];active=[]
 for name in sorted(allstop):
  if name==m['isolated_historical_STOP']['path'] and sha(ROOT/name)==m['isolated_historical_STOP']['sha256']:isolated.append(name)
  else:active.append(name)
 projects=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit() or int(p.name) in allowed:continue
  try:
   args=[a.decode(errors='replace') for a in (p/'cmdline').read_bytes().split(b'\0') if a]
   if not args or not Path(args[0]).name.startswith('python'):continue
   cwd=Path(os.readlink(p/'cwd'))
   if cwd==ROOT or ROOT in cwd.parents:projects.append({'pid':int(p.name),'argv':args})
  except (PermissionError,FileNotFoundError,ProcessLookupError):pass
 raw=subprocess.check_output(['nvidia-smi','--query-gpu=memory.free,power.draw,utilization.gpu,temperature.gpu','--format=csv,noheader,nounits'],timeout=20).decode().strip().splitlines()[0]
 s['gpu_actual']=next(csv.reader(io.StringIO(raw)));d=os.statvfs(ROOT);s.update(disk_free_bytes=d.f_bavail*d.f_frsize,isolated_unchanged_historical_STOP=isolated,active_STOP=active,other_project_identity=projects)
 s['safe']=bool(s['safe'] and not active and not projects and s['disk_free_bytes']>1024**3)
 return s

def stop_record(reason):
 if not (LOG/'STOP').exists():save(LOG/'STOP',{'owner':'acod_compat_20261122','time':now(),'reason':reason,'auto_clear':False})
def digest(model,torch):
 h=hashlib.sha256()
 for n,p in model.named_parameters():h.update(n.encode());h.update(p.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes())
 return h.hexdigest()
def supervise():
 RUN.mkdir(exist_ok=True);LOG.mkdir(exist_ok=True);verify()
 assert not (RUN/'supervisor_start.json').exists(),'No automatic restart'
 with (LOG/'worker.lock').open('a') as f:
  fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);s=safety({os.getpid(),os.getppid()});append(LOG/'guard.jsonl',s)
  if not s['safe'] or float(s['gpu_actual'][0])<2048:
   stop_record(s);save(RUN/'BLOCKED.json',s);print(canonical(s),flush=True);return 75
  save(RUN/'supervisor_start.json',{'time':now(),'pid':os.getpid(),'state':s});start=time.monotonic()
  with (LOG/'worker.log').open('x',buffering=1) as out:
   env=dict(os.environ);env['PYTHONPATH']=str(ROOT)
   child=subprocess.Popen([sys.executable,'-B',str(HERE/'compat_runner.py'),'worker'],cwd=ROOT,env=env,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
   save(RUN/'worker_identity.json',{'pid':child.pid,'time':now()});print('WORKER_PID',child.pid,flush=True)
   while child.poll() is None:
    try:child.wait(timeout=3);break
    except subprocess.TimeoutExpired:pass
    try:
     s=safety({os.getpid(),os.getppid(),child.pid});append(LOG/'guard.jsonl',s)
     if s['safe'] and time.monotonic()-start<600:continue
     reason=s if not s['safe'] else {'deadline_seconds':600}
    except Exception as e:reason={'inspection_error':repr(e)}
    stop_record(reason);os.killpg(child.pid,signal.SIGTERM)
    try:child.wait(timeout=15)
    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
    break
   rc=child.wait()
  save(RUN/'supervisor_end.json',{'time':now(),'rc':rc,'wall_seconds':time.monotonic()-start});print('SUPERVISOR_END',rc,flush=True);return rc

def worker():
 import torch
 from fac_tinyagent.sft.evaluate import load_eval_model,generate_with_usage
 from fac_tinyagent.replay_study import config_for
 from fac_tinyagent.sft.dataset import conversation_text
 verify();plan=read(HERE/'PLAN_PUBLIC.json');assert len(plan['cases'])==2 and len(plan['configurations'])==3
 def terminate(sig,frame):raise SystemExit(75)
 def deadline(sig,frame):raise TimeoutError('single generation exceeded 60 seconds')
 signal.signal(signal.SIGTERM,terminate);signal.signal(signal.SIGINT,terminate);signal.signal(signal.SIGALRM,deadline)
 for ident in plan['models']:
  seed=ident['seed'];s=safety({os.getpid(),os.getppid()});append(LOG/'worker_guard.jsonl',s)
  if not s['safe']:stop_record(s);return 75
  print(now(),'LOAD',seed,flush=True);cfg=config_for('A',seed,batch_size=1)
  assert cfg['model_name_or_path']==ident['model_name_or_path']
  model,tok=load_eval_model(cfg,ident['adapter']);assert not model.training and not model.config.use_cache and not any(p.requires_grad for p in model.parameters())
  before=digest(model,torch);count=0;torch.cuda.reset_peak_memory_stats()
  assert before==ident['expected_parameter_digest']
  assert hashlib.sha256(tok.backend_tokenizer.to_str().encode()).hexdigest()==plan['tokenizer_backend_sha256']
  append(RUN/'model_events.jsonl',{'time':now(),'seed':seed,'adapter':ident['adapter'],'parameter_digest_before':before,'generation_config':model.generation_config.to_dict(),'model_use_cache':model.config.use_cache})
  try:
   for case in plan['cases']:
    for config in plan['configurations']:
     key=f"{seed}:{case['case_id']}:{config}";messages=case['messages'][config]
     assert len(rows(RUN/'calls_started.jsonl'))<12
     assert not (LOG/'STOP').exists() and not (ROOT/'STOP').exists()
     text=conversation_text(tok,messages,generation=True);n=len(tok(text,add_special_tokens=False)['input_ids'])
     assert n==case['input_tokens'][config] and sha(HERE/f"prompts/{case['case_id']}__{config}.txt")==hashlib.sha256(text.encode()).hexdigest()
     append(RUN/'calls_started.jsonl',{'id':key,'time':now(),'input_tokens':n,'message_sha256':hashlib.sha256(canonical(messages).encode()).hexdigest()})
     signal.alarm(60)
     try:raw,usage=generate_with_usage(model,tok,messages,128)
     except BaseException as e:append(RUN/'call_failures.jsonl',{'id':key,'time':now(),'error':repr(e)});raise
     finally:signal.alarm(0)
     assert usage['inference_calls']==1 and usage['batch_size']==1 and usage['input_tokens']==n
     append(RUN/'responses.jsonl',{'id':key,'time':now(),'seed':seed,'case_id':case['case_id'],'configuration':config,'raw':raw,'usage':usage});count+=1
     print(now(),key,'tokens',usage['output_tokens'],'seconds',round(usage['generation_seconds'],3),flush=True)
  finally:
   after=digest(model,torch);append(RUN/'model_receipts.jsonl',{'time':now(),'seed':seed,'before':before,'after':after,'parameters_unchanged':before==after,'generation_calls':count,'peak_allocated_GiB':torch.cuda.max_memory_allocated()/1024**3,'optimizer_updates':0});assert before==after
   del model,tok;gc.collect();torch.cuda.empty_cache()
 verify();assert len(rows(RUN/'responses.jsonl'))==12
 save(RUN/'COMPLETE.json',{'time':now(),'generations':12,'retries':0,'training':0});return 0
if __name__=='__main__':
 try:sys.exit(supervise() if sys.argv[1]=='supervise' else worker())
 except BaseException as e:
  if not isinstance(e,SystemExit) or e.code not in [0,None]:RUN.mkdir(exist_ok=True);append(RUN/'errors.jsonl',{'time':now(),'error':repr(e)});traceback.print_exc()
  raise