"""P15 local QLoRA entry. Model/GPU imports happen ONLY after --execute + approval + guards."""
import os
os.environ.update(HF_HUB_OFFLINE='1',TOKENIZERS_PARALLELISM='false',PYTHONDONTWRITEBYTECODE='1')
import argparse,contextlib,copy,fcntl,gzip,itertools,json,random,shutil,subprocess,sys,time,traceback
from core import *
from guards_v2 import Guard,SafetyStop

def verify():
 m=read(RUN/'runtime_manifest_v2.json')
 for p,digest in m['files'].items():assert h((ROOT/p).read_bytes())==digest,'Frozen runtime mismatch '+p
 for p,digest in read(DATA/'manifest.json')['files'].items():assert h((ROOT/p).read_bytes())==digest,'Frozen v2 mismatch '+p
 for p,digest in read(RUN/'protected_before.json').items():assert h((ROOT/p).read_bytes())==digest,'Old protected file changed '+p
 for name,digest in read(RUN/'tokenizer_identity.json')['files'].items():assert h((Path(CONFIG['model_name_or_path'])/name).read_bytes())==digest
 ident=read(RUN/'base_model_identity.json');base=Path(ident['path'])
 for name,meta in ident['weight_files'].items():
  digest=hashlib.sha256()
  with (base/name).open('rb') as f:
   for chunk in iter(lambda:f.read(8*1024*1024),b''):digest.update(chunk)
  assert digest.hexdigest()==meta['sha256'],'Base weight identity changed'
 return m

def require_start(command,execute):
 if not execute:raise PermissionError('CPU default; explicit --execute and parent START_APPROVED.json required')
 m=verify();p=RUN/'START_APPROVED.json'
 if not p.exists():raise PermissionError('GPU NOT authorized in this engineering phase; parent launch approval artifact absent')
 a=read(p);assert a['runtime_manifest_sha256']==h((RUN/'runtime_manifest_v2.json').read_bytes())
 assert command in a['allowed_commands']
 return m

@contextlib.contextmanager
def preserved_rng(t):
 import numpy as np
 state=(random.getstate(),np.random.get_state(),t.get_rng_state(),t.cuda.get_rng_state_all())
 try:yield
 finally:
  random.setstate(state[0]);np.random.set_state(state[1]);t.set_rng_state(state[2]);t.cuda.set_rng_state_all(state[3])

def append(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open('a',encoding='utf8') as f:f.write(cj(value)+'\n')

def generate(model,tok,msgs,max_new,guard):
 import torch
 from transformers import StoppingCriteria,StoppingCriteriaList
 funcs=tokenizer_functions();text=funcs['conversation_text'](tok,msgs,True)
 enc=tok(text,return_tensors='pt',add_special_tokens=False);n=int(enc['input_ids'].shape[1]);guard.check()
 if n+max_new>4096:return '',{'inference_calls':0,'input_tokens':0,'rejected_prompt_tokens':n,'output_tokens':0,'wall_seconds':0,'context_overflow':True}
 class StopGuard(StoppingCriteria):
  def __call__(self,input_ids,scores,**kw):return guard.stop.is_set()
 enc={k:v.to('cuda') for k,v in enc.items()};start=time.perf_counter()
 eos=[v for v in {tok.eos_token_id,tok.convert_tokens_to_ids('<|im_end|>')} if isinstance(v,int) and v>=0]
 with torch.no_grad():out=model.generate(**enc,max_new_tokens=max_new,do_sample=False,pad_token_id=tok.pad_token_id,eos_token_id=eos,use_cache=True,stopping_criteria=StoppingCriteriaList([StopGuard()]))
 guard.check();ids=out[0,n:];raw=tok.decode(ids,skip_special_tokens=True).strip()
 return raw,{'inference_calls':1,'input_tokens':n,'output_tokens':len(ids),'wall_seconds':time.perf_counter()-start,'context_overflow':False,'hit_length_cap':len(ids)==max_new}

def evaluate(model,tok,rr,guard,path=None):
 import torch
 from fac_tinyagent.sft.evaluate import parse_tool_call,parse_final_answer
 from fac_tinyagent.metrics import answers_equal,observations_equal,joint_success
 assert rr and len({r['split'] for r in rr})==1
 bound=BoundCalendar(rr[0]['split']);was=model.training;result=[]
 with preserved_rng(torch):
  model.eval()
  try:
   for r in rr:
    episode_start=time.perf_counter()
    guard.check();tool_raw,ut=generate(model,tok,r['messages'][:2],128,guard);call=parse_tool_call(tool_raw)
    tool=call['tool'] if call else None;args=call['arguments'] if call else {}
    obs=bound.execute(r,tool,args) if tool else {'ok':False,'error':'model did not return a valid tool call'}
    real_messages=r['messages'][:2]+[{'role':'assistant','content':tool_raw},{'role':'user','content':'TOOL RESULT:\n'+cj(obs)}]
    real,ur=generate(model,tok,real_messages,256,guard);gold,ug=generate(model,tok,r['messages'][:4],256,guard)
    ok,ans=parse_final_answer(real);gok,gans=parse_final_answer(gold)
    rec={'episode_id':r['episode_id'],'split':r['split'],'skill':r['skill'],'continual_group':r['continual_group'],
     'tool_correct':tool==r['expected_tool'],'arguments_correct':answers_equal(args,r['expected_arguments']),
     'execution_success':observations_equal(cj(obs),r['expected_observation']),
     'final_correct':bool(ok and not ur['context_overflow'] and answers_equal(ans,r['expected_final_answer'])),
     'gold_final_correct':bool(gok and not ug['context_overflow'] and answers_equal(gans,r['expected_final_answer'])),
     'predicted_tool':tool,'predicted_arguments':args,'tool_raw':tool_raw,'real_final_raw':real,'gold_final_raw':gold,
     'tool_usage':ut,'real_final_usage':ur,'gold_final_usage':ug,'actual_observation_sha256':h(cj(obs).encode())}
    rec['episode_wall_seconds']=time.perf_counter()-episode_start
    rec['tool_args_core']=rec['tool_correct'] and rec['arguments_correct'];rec['joint_success']=joint_success(rec)
    result.append(rec)
    if path:append(path,rec)
  finally:model.train(was)
 return result

def features_load():return json.loads(gzip.decompress((RUN/'token_features.json.gz').read_bytes()))

def trainable_state(model):return {n:p.detach().cpu().clone() for n,p in model.named_parameters() if p.requires_grad}

def save_node(model,opt,scaler,tok,out,meta,torch,optimizer=True):
 import numpy as np
 out.mkdir(parents=True,exist_ok=False);model.save_pretrained(str(out/'adapter'),safe_serialization=True)
 if optimizer:
  torch.save({'optimizer':opt.state_dict(),'scaler':scaler.state_dict(),'python_rng':random.getstate(),'numpy_rng':np.random.get_state(),
              'torch_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state_all(),'metadata':meta},out/'optimizer_rng.pt')
 write(out/'COMPLETE.json',{**meta,'adapter_sha256':h((out/'adapter/adapter_model.safetensors').read_bytes())})

def loss_probe(model,features,ids,guard,torch):
 out=[];was=model.training;model.eval()
 with preserved_rng(torch),torch.no_grad():
  for eid in ids:
   guard.check();f=features[eid];x=torch.tensor([f['input_ids']],device='cuda');start=time.perf_counter()
   with torch.autocast(device_type='cuda',dtype=torch.float16):logits=model(input_ids=x,attention_mask=torch.ones_like(x)).logits[:,:-1].float()
   rec={'episode_id':eid,'input_tokens':f['input_tokens'],'forward_sequences':1,'extra_backward':0}
   for mode in ('call','final'):
    y=torch.tensor([f['masks'][mode]],device='cuda')[:,1:]
    rec[mode+'_NLL']=float(torch.nn.functional.cross_entropy(logits.reshape(-1,logits.shape[-1]),y.reshape(-1),ignore_index=-100))
   rec['wall_seconds']=time.perf_counter()-start;out.append(rec)
 model.train(was);return out

def _run_trajectory(c,guard):
 trajectory_start=time.perf_counter()
 import torch,numpy as np
 from fac_tinyagent.sft.train import load_base_model,load_tokenizer,_attach_adapter
 torch.manual_seed(c['seed']);torch.cuda.manual_seed_all(c['seed']);np.random.seed(c['seed']);random.seed(c['seed'])
 config=copy.deepcopy(CONFIG);config['seed']=c['seed'];out=RUN/'trajectories'/c['id']
 if out.exists():raise FileExistsError('Refuse overwrite/retry; existing trajectory '+str(out))
 out.mkdir(parents=True);guard.check();tok=load_tokenizer(config);model,dtype=load_base_model(config);model=_attach_adapter(model,config,None)
 expected=read(RUN/'budget_ledger.json')['lora_trainable_parameters_structure_estimate'];actual=sum(p.numel() for p in model.parameters() if p.requires_grad)
 assert actual==expected,(actual,expected)
 opt=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=1e-4,betas=(.9,.999),eps=1e-8,weight_decay=0)
 scaler=torch.cuda.amp.GradScaler(enabled=True);features=features_load();train=rows('train');dev=rows('dev');lookup={r['episode_id']:r for r in train}
 subset=read(RUN/'diagnostic_subsets.json');diagids=set(subset['dev_ids']);diag=[r for r in dev if r['episode_id'] in diagids]
 streams=read(RUN/'new_streams.json')[str(c['seed'])];anchors={};old=[];nodes=[];updates=0;started=time.perf_counter()
 rng=random.Random(c['seed']+8191);guard.check()
 # Stage 00 baseline includes unlearned tasks, enabling actual FWT rather than a fabricated proxy.
 save_node(model,opt,scaler,tok,out/'node00',{'node':0,'optimizer_updates':0,'runtime_manifest_sha256':h((RUN/'runtime_manifest_v2.json').read_bytes())},torch,False)
 base=evaluate(model,tok,dev,guard,out/'node00/dev.jsonl');nodes.append(base);write(out/'node00/dev_summary.json',aggregate(base))
 write(out/'node00/train_loss_probe.json',loss_probe(model,features,subset['train_loss_ids'],guard,torch))
 adaptive=c['method'] in ('p11_priority','layer_replay','no_priority','no_layer')
 try:
  for stage,group in enumerate(c['order'],1):
   oldskills={r['skill'] for r in old};state={'weights':{s:1/max(1,len(oldskills)) for s in oldskills},'components':{s:'both' for s in oldskills}}
   for step,new in enumerate(streams[group]):
    guard.check()
    if adaptive and old and step in (0,64):
     recs=evaluate(model,tok,[r for r in diag if r['skill'] in oldskills],guard,out/f'diagnostic_stage{stage}_update{step}.jsonl')
     state=priority(c['method'],oldskills,profile(recs),anchors)
     write(out/f'diagnostic_stage{stage}_update{step}_decision.json',state)
     write(out/f'diagnostic_stage{stage}_update{step}_cost.json',{'episode_wall_seconds':sum(r['episode_wall_seconds'] for r in recs),'generate_forward_requests':sum(r[u]['inference_calls'] for r in recs for u in ('tool_usage','real_final_usage','gold_final_usage')),'input_tokens':sum(r[u]['input_tokens'] for r in recs for u in ('tool_usage','real_final_usage','gold_final_usage')),'output_tokens':sum(r[u]['output_tokens'] for r in recs for u in ('tool_usage','real_final_usage','gold_final_usage')),'extra_backward':0,'extra_optimizer_updates':0})
    replay=choose_replay(c['method'],old,features,state,rng)
    ni=sum(features[e]['input_tokens'] for e,m in replay);ns=sum(features[e]['supervised_tokens'][m] for e,m in replay)
    if c['method']!='full_replay':assert ni<=REPLAY_CAP[0] and ns<=REPLAY_CAP[1]
    examples=[(e,'both','new') for e in new['ids']]+[(e,m,'replay') for e,m in replay]
    from optimization import optimizer_update
    start=time.perf_counter();counts=optimizer_update(model,opt,scaler,features,examples,'cuda',guard);updates+=1
    forward=counts['forward_sequences'];backward=counts['backward_sequences']
    append(out/'updates.jsonl',{'stage':stage,'group':group,'update_in_stage':step+1,'optimizer_updates':updates,
      'new_ids':new['ids'],'new_input_tokens':new['input_tokens'],'new_supervised_tokens':new['supervised_tokens'],
      'replay_items':replay,'replay_input_tokens':ni,'replay_supervised_tokens':ns,
      'replay_input_utilization':ni/REPLAY_CAP[0] if old and c['method']!='seqft' else None,
      'replay_supervision_utilization':ns/REPLAY_CAP[1] if old and c['method']!='seqft' else None,
      'forward_sequences':forward,'backward_sequences':backward,'diagnostic_extra_backward':0,'wall_seconds':time.perf_counter()-start,
      'allocated_gpu_MiB':torch.cuda.max_memory_allocated()/2**20,'reserved_gpu_MiB':torch.cuda.max_memory_reserved()/2**20})
   node=out/f'node{stage:02d}';save_node(model,opt,scaler,tok,node,{'node':stage,'optimizer_updates':updates,'group':group,'seed':c['seed'],'runtime_manifest_sha256':h((RUN/'runtime_manifest_v2.json').read_bytes())},torch)
   recs=evaluate(model,tok,dev,guard,node/'dev.jsonl');nodes.append(recs);write(node/'dev_summary.json',aggregate(recs))
   write(node/'train_loss_probe.json',loss_probe(model,features,subset['train_loss_ids'],guard,torch))
   p=profile([r for r in recs if r['episode_id'] in diagids and r['continual_group']==group]);anchors.update(p)
   old.extend(load_group(train,group))
  assert updates==3*STEPS
  write(out/'dev_longitudinal.json',longitudinal(nodes,c['order'],{r['episode_id']:r for r in dev}))
  write(out/'COMPLETE.json',{'id':c['id'],'optimizer_updates':updates,'stages':3,'runtime_manifest_sha256':h((RUN/'runtime_manifest_v2.json').read_bytes()),'wall_seconds':time.perf_counter()-trajectory_start,'test_evaluated_during_training':False})
 except BaseException as exc:
  # Preserve partial-run evidence; no automatic clearing, deletion, overwrite, or continuation.
  write(out/'INTERRUPTED.json',{'optimizer_updates_completed':updates,'error':repr(exc),'traceback':traceback.format_exc(),'midstage_exact_resume_supported':False,'no_automatic_retry':True})
  raise
 finally:
  del model,opt,scaler;torch.cuda.empty_cache()


def train_one(cid,execute):
 require_start('train',execute);cohort=read(RUN/'cohort.json')+read(RUN/'optional_full_replay_cohort.json');matches=[c for c in cohort if c['id']==cid];assert len(matches)==1
 if matches[0]['method']=='full_replay':assert read(RUN/'START_APPROVED.json').get('allow_full_replay') is True,'Full Replay not approved by default'
 # Exclusive local lock for P15; existing GPU/project-process checks also detect other research jobs.
 with (RUN/'single_gpu.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);guard=Guard();guard.start()
  try:_run_trajectory(matches[0],guard)
  finally:guard.close()

def batch(execute,include_full=False):
 require_start('batch',execute)
 budget=read(RUN/'budget_ledger.json');cohort=read(RUN/'cohort.json')
 if include_full:
  assert read(RUN/'START_APPROVED.json').get('allow_full_replay') is True
  cohort+=read(RUN/'optional_full_replay_cohort.json')
 pending=sum(not (RUN/'trajectories'/c['id']/'COMPLETE.json').exists() for c in cohort)
 required=2_000_000_000+2*budget['disk_adapter_optimizer_payload_estimate_bytes']*pending//budget['required_trajectories']
 assert shutil.disk_usage(ROOT).free>=required,'Insufficient conservative remaining-run disk reserve; do not prune old runs'
 for c in cohort:
  path=RUN/'trajectories'/c['id']
  if path.exists():
   receipt=read(path/'COMPLETE.json') if (path/'COMPLETE.json').exists() else None
   if receipt and receipt['runtime_manifest_sha256']==h((RUN/'runtime_manifest_v2.json').read_bytes()):continue
   raise RuntimeError('Incomplete trajectory present; no automatic retry/resume '+c['id'])
  subprocess.run([sys.executable,'-B',str(CODE/'runner_v2.py'),'train','--id',c['id'],'--execute'],cwd=ROOT,check=True)

def test_all(execute,include_full=False):
 require_start('test',execute);cohort=read(RUN/'cohort.json')
 if include_full:
  assert read(RUN/'START_APPROVED.json').get('allow_full_replay') is True
  cohort+=read(RUN/'optional_full_replay_cohort.json')
 digest=h((RUN/'runtime_manifest_v2.json').read_bytes())
 # Blind-test results are not generated until EVERY main cohort trajectory completed, all rules frozen.
 for c in cohort:
  receipt=read(RUN/'trajectories'/c['id']/'COMPLETE.json');assert receipt['runtime_manifest_sha256']==digest and receipt['optimizer_updates']==384
 from fac_tinyagent.sft.evaluate import load_eval_model,free_model
 with (RUN/'single_gpu.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);guard=Guard();guard.start()
  try:
   test=rows('test')
   for c in cohort:
    out=RUN/'test_evaluation'/c['id']
    if out.exists():raise FileExistsError('No blind-test overwrite/retry '+str(out))
    out.mkdir(parents=True);nodes=[]
    for stage in range(4):
     guard.check();cfg=copy.deepcopy(CONFIG);cfg['seed']=c['seed'];adapter=RUN/'trajectories'/c['id']/f'node{stage:02d}/adapter'
     model,tok=load_eval_model(cfg,str(adapter))
     try:recs=evaluate(model,tok,test,guard,out/f'node{stage:02d}.jsonl');nodes.append(recs);write(out/f'node{stage:02d}_summary.json',aggregate(recs))
     finally:free_model(model)
    write(out/'longitudinal.json',longitudinal(nodes,c['order'],{r['episode_id']:r for r in test}))
    write(out/'COMPLETE.json',{'runtime_manifest_sha256':digest,'nodes':4,'episodes':1392})
  finally:guard.close()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=['list','guard','train','batch','test']);p.add_argument('--execute',action='store_true');p.add_argument('--id');p.add_argument('--include-full',action='store_true');a=p.parse_args()
 if a.command=='list':print(cj(read(RUN/'cohort.json')))
 elif a.command=='guard':
  from guards_v2 import inspect
  print(cj(inspect(False)))
 elif a.command=='train':train_one(a.id,a.execute)
 elif a.command=='batch':batch(a.execute,a.include_full)
 elif a.command=='test':test_all(a.execute,a.include_full)
