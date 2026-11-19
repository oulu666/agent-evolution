"""Runnable v3 formal entry; GPU gated pending parent resource review. Full Replay deferred."""
import os
os.environ.update(HF_HUB_OFFLINE='1',TOKENIZERS_PARALLELISM='false',PYTHONDONTWRITEBYTECODE='1',CUBLAS_WORKSPACE_CONFIG=':4096:8')
import argparse,fcntl,subprocess,time,traceback,gc
from common import *
from guards_v3 import Guard,inspect
from model_v3 import make
from state_v3 import Store,PhysicalBudget,capture,restore,semantic,atomic_torch,file_sha,helpers
from engine_v3 import optimizer_update
from evaluation_v3 import ExactCache,evaluate

def require(command,execute):
 assert execute,'GPU disabled by default'
 freeze=verify();a=read(RUN/'START_APPROVED_V3.json')
 assert a['runtime_manifest_sha256']==freeze and command in a['allowed_commands']
 assert read(RUN/'engineering_attempt01/RESULT.json')['status']=='PASS','Real engineering acceptance must PASS'
 return freeze

def isolated_eval(m,tok,opt,scaler,meta,rr,guard,path,scope,binding,cache_path):
 snapshot=capture(m,opt,scaler,meta)
 try:
  cache=ExactCache(cache_path,scope,binding,{'p14v2_manifest_sha256':h((DATA/'manifest.json').read_bytes()),
   'fixture_sha256':h((DATA/'fixtures'/f"{rr[0]['split']}.json").read_bytes())})
  records=evaluate(m,tok,rr,guard,cache)
  atomic_json(path,records);return records
 finally:restore(snapshot,m,opt,scaler)

def save_generation(out,store,receipt):
 fs,p=helpers();s=store.load(receipt);out.mkdir(parents=True,exist_ok=True)
 state={'parameters':s['train']['parameters'],'attrs':s['attrs'],'base_ref':receipt['base_ref'],
  'base_file_sha256':receipt['base_file_sha256'],'generation_model_sha256':receipt['generation_model_sha256']}
 fn=out/'generation_state.pt'
 if fn.exists():
  import torch
  assert fs.digest(torch.load(fn,map_location='cpu',weights_only=False))==fs.digest(state)
 else:disk_check(128*1024**2);atomic_torch(fn,state)
 atomic_json(out/'GENERATION_STATE.json',{'file_sha256':file_sha(fn),'semantic_sha256':fs.digest(state),'generation_model_sha256':receipt['generation_model_sha256']})

def trajectory(c,resume=False):
 freeze=verify();out=RUN/'trajectories'/c['id'];features=features_load();train=rows('train');dev=rows('dev')
 subset=read(OLD_RUN/'diagnostic_subsets.json');diagids=set(subset['dev_ids']);diag=[r for r in dev if r['episode_id'] in diagids]
 streams=read(OLD_RUN/'new_streams.json')[str(c['seed'])];guard=Guard()
 if resume:assert out.exists() and not (out/'COMPLETE.json').exists()
 else:out.mkdir(parents=True,exist_ok=False)
 with (RUN/'single_gpu.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:
   disk_check(2*1024**3);guard.start()
   import torch
   m,tok,opt,scaler=make(c['seed'],guard);store=Store(out/'state');physical=PhysicalBudget(out/'physical_steps.jsonl',384)
   if resume:
    meta=store.restore(m,opt,scaler);assert meta['manifest_sha256']==freeze
    intents=len((out/'physical_steps.jsonl').read_text().splitlines()) if (out/'physical_steps.jsonl').exists() else 0
    assert intents==meta['global_update'],'Uncommitted optimizer intent: ambiguous physical compute; stop for explicit recovery-budget revision'
   else:
    meta={'phase':'node','node':0,'stage':0,'step':0,'global_update':0,'anchors':{},'decision':{},'diag_done_at':None,
     'selection_rng':random.Random(c['seed']+8191).getstate(),'replay_queue':[],'manifest_sha256':freeze}
    # Fixed teacher-forced warmup/probe; no optimizer step, same14 train rows for every trajectory.
    from runner_v2 import loss_probe
    atomic_json(out/'node00_initial_train_probe.json',loss_probe(m,features,subset['train_loss_ids'],guard,torch))
    store.commit(m,opt,scaler,meta)
   while meta['phase']!='done':
    guard.check();receipt=read(out/'state/CURRENT.json');binding={'generation_model_sha256':receipt['generation_model_sha256'],'manifest_sha256':freeze}
    scope={'trajectory':c['id'],'seed':c['seed']}
    if meta['phase']=='node':
     node=meta['node'];nd=out/f'node{node:02d}'
     recs=isolated_eval(m,tok,opt,scaler,meta,diag,guard,nd/'dev88_records.json',scope,binding,out/'cache')
     atomic_json(nd/'dev88_summary.json',aggregate(recs));save_generation(nd,store,receipt)
     if node:
      from runner_v2 import loss_probe
      atomic_json(nd/'train_loss_probe.json',loss_probe(m,features,subset['train_loss_ids'],guard,torch))
      group=c['order'][node-1];meta['anchors'].update(profile([r for r in recs if r['continual_group']==group]))
     if node==3:meta['phase']='done'
     else:
      meta.update(phase='updates',stage=node+1,step=0,diag_done_at=None)
      old=[r for r in train if r['continual_group'] in c['order'][:node]];skills={r['skill'] for r in old}
      meta['decision']={'weights':{s:1/max(1,len(skills)) for s in skills},'components':{s:'both' for s in skills}}
     store.commit(m,opt,scaler,meta);continue
    stage=meta['stage'];step=meta['step'];group=c['order'][stage-1]
    if step==STEPS:meta.update(phase='node',node=stage);store.commit(m,opt,scaler,meta);continue
    old=[r for r in train if r['continual_group'] in c['order'][:stage-1]];skills={r['skill'] for r in old}
    adaptive=c['method'] in ('p11_priority','layer_replay','no_priority','no_layer')
    if adaptive and old and step in (0,64) and meta['diag_done_at']!=step:
     records=isolated_eval(m,tok,opt,scaler,meta,[r for r in diag if r['skill'] in skills],guard,
      out/f'diagnostic_stage{stage}_update{step}.json',scope,binding,out/'cache')
     meta['decision']=priority(c['method'],skills,profile(records),meta['anchors']);meta['diag_done_at']=step
     store.commit(m,opt,scaler,meta)
    rng=random.Random();rng.setstate(meta['selection_rng']);new=streams[group][step]
    replay=choose_replay(c['method'],old,features,meta['decision'],rng)
    ni=sum(features[e]['input_tokens'] for e,mode in replay);ns=sum(features[e]['supervised_tokens'][mode] for e,mode in replay)
    assert ni<=REPLAY_CAP[0] and ns<=REPLAY_CAP[1]
    examples=[(e,'both','new') for e in new['ids']]+[(e,mode,'replay') for e,mode in replay]
    start=time.perf_counter();counts=optimizer_update(m,opt,scaler,features,examples,'cuda',guard,physical.before_step,
     lambda event:append(out/'micro_events.jsonl',{'logical_update':meta['global_update']+1,**event}))
    meta.update(step=step+1,global_update=meta['global_update']+1,selection_rng=rng.getstate(),replay_queue=replay)
    meta['last_update_cost']={**counts,'new_input_tokens':new['input_tokens'],'new_supervised_tokens':new['supervised_tokens'],
     'replay_input_tokens':ni,'replay_supervised_tokens':ns,'replay_input_utilization':ni/REPLAY_CAP[0] if replay else None,
     'replay_supervision_utilization':ns/REPLAY_CAP[1] if replay else None,'new_ids':new['ids'],'stage':stage,'group':group}
    # Always commit successful optimizer update before honoring a newly observed STOP.
    t=time.perf_counter();r=store.commit(m,opt,scaler,meta)
    append(out/'updates.jsonl',{'global_update':meta['global_update'],**meta['last_update_cost'],'checkpoint_seconds':time.perf_counter()-t,
     'wall_with_checkpoint_seconds':time.perf_counter()-start,'checkpoint_state_sha256':r['full_semantic_sha256']})
   nodes=[read(out/f'node{i:02d}/dev88_records.json') for i in range(4)]
   atomic_json(out/'dev88_longitudinal.json',longitudinal(nodes,c['order'],{r['episode_id']:r for r in diag}))
   atomic_json(out/'COMPLETE.json',{'id':c['id'],'optimizer_updates':384,'runtime_manifest_sha256':freeze,'test_during_training':False})
  except BaseException as exc:
   atomic_json(out/'INTERRUPTED.json',{'error':repr(exc),'traceback':traceback.format_exc(),'manual_resume_only':True,
    'last_committed':read(out/'state/CURRENT.json') if (out/'state/CURRENT.json').exists() else None});raise
  finally:guard.close()

def batch(execute):
 require('batch',execute)
 for c in read(OLD_RUN/'cohort.json'):
  p=RUN/'trajectories'/c['id']
  if p.exists():
   if (p/'COMPLETE.json').exists():continue
   raise RuntimeError('Incomplete trajectory; no automatic restart: '+c['id'])
  subprocess.run([sys.executable,'-B',str(CODE/'runner_v3.py'),'train','--id',c['id'],'--execute'],cwd=ROOT,check=True)

def test_all(execute):
 freeze=require('test',execute);cohort=read(OLD_RUN/'cohort.json')
 for c in cohort:
  r=read(RUN/'trajectories'/c['id']/'COMPLETE.json');assert r['runtime_manifest_sha256']==freeze and r['optimizer_updates']==384
 # All108 completed first; no blind-test feedback into any method/threshold/schedule.
 import torch
 fs,p=helpers();guard=Guard()
 with (RUN/'single_gpu.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);guard.start()
  try:
   rr=rows('test')
   for c in cohort:
    out=RUN/'test_evaluation'/c['id'];out.mkdir(parents=True,exist_ok=True);nodes=[]
    for node in range(4):
     guard.check();nd=RUN/'trajectories'/c['id']/f'node{node:02d}';r=read(nd/'GENERATION_STATE.json');assert file_sha(nd/'generation_state.pt')==r['file_sha256']
     s=torch.load(nd/'generation_state.pt',map_location='cpu',weights_only=False);assert fs.digest(s)==r['semantic_sha256']
     m,tok,opt,scaler=make(c['seed'],guard);base=ROOT/s['base_ref'];assert file_sha(base)==s['base_file_sha256']
     b=torch.load(base,map_location='cpu',weights_only=False);p.restore_base(m,b);p.restore_attrs(m,s['attrs']);params=dict(m.named_parameters())
     with torch.no_grad():
      for name,v in s['parameters'].items():params[name].copy_(v.to(params[name].device))
     actual=fs.digest({'parameters':{n:v.detach().cpu().clone() for n,v in m.named_parameters() if v.requires_grad},'base':p.capture_base(m),'attrs':p.runtime_attrs(m)})
     assert actual==s['generation_model_sha256']
     cache=ExactCache(out/'cache',{'trajectory':c['id'],'seed':c['seed']},{'generation_model_sha256':actual,'manifest_sha256':freeze},
      {'p14v2_manifest_sha256':h((DATA/'manifest.json').read_bytes()),'fixture_sha256':h((DATA/'fixtures/test.json').read_bytes())})
     recs=evaluate(m,tok,rr,guard,cache);nodes.append(recs);atomic_json(out/f'node{node:02d}.json',recs)
     del m,opt,scaler;gc.collect();torch.cuda.empty_cache()
    atomic_json(out/'longitudinal.json',longitudinal(nodes,c['order'],{r['episode_id']:r for r in rr}));atomic_json(out/'COMPLETE.json',{'runtime_manifest_sha256':freeze,'nodes':4,'episodes':1392})
  finally:guard.close()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=['guard','list','train','batch','test']);p.add_argument('--execute',action='store_true');p.add_argument('--id');p.add_argument('--resume',action='store_true');a=p.parse_args()
 if a.command=='guard':print(cj(inspect(False)))
 elif a.command=='list':print(cj(read(OLD_RUN/'cohort.json')))
 elif a.command=='batch':batch(a.execute)
 elif a.command=='test':test_all(a.execute)
 else:
  require('train',a.execute);matches=[c for c in read(OLD_RUN/'cohort.json') if c['id']==a.id];assert len(matches)==1;trajectory(matches[0],a.resume)
