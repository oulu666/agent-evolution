"""ONE bounded engineering attempt, <=3 physical steps, <=6 generation requests, never test."""
import os
os.environ.update(HF_HUB_OFFLINE='1',TOKENIZERS_PARALLELISM='false',PYTHONDONTWRITEBYTECODE='1',CUBLAS_WORKSPACE_CONFIG=':4096:8')
import gc,time,traceback,fcntl
from common import *
from guards_v3 import Guard,inspect
from state_v3 import Store,PhysicalBudget,capture,semantic,restore,helpers
from engine_v3 import optimizer_update
from model_v3 import make
from evaluation_v3 import ExactCache,evaluate

def run(execute=False):
 assert execute,'Explicit engineering-only --execute required'
 freeze=verify();plan=read(RUN/'engineering_plan.json');out=RUN/'engineering_attempt01'
 out.mkdir(exist_ok=False) # Existing attempt is final; never automatic retry.
 report={'runtime_manifest_v3_sha256':freeze,'scientific_trajectory':False,'status':'started','physical_step_limit':3,
  'logical_update_limit':2,'generation_request_limit':6,'test_read':False,'start_Beijing':time.strftime('%F %T %z')}
 atomic_json(out/'ATTEMPT.json',report);guard=Guard();started=time.perf_counter()
 try:
  with (RUN/'single_gpu.lock').open('a') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);report['disk_before']=disk_check();guard.start()
   import torch
   torch.cuda.reset_peak_memory_stats();m,tok,opt,scaler=make(17,guard);features=features_load()
   report['model_loaded_seconds']=time.perf_counter()-started
   _,persist=helpers();report['backend_fingerprint']=persist.backend_fingerprint(m,torch.float16)
   report['quantized_parameter_count']=sum(p.__class__.__name__=='Params4bit' for p in m.parameters());assert report['quantized_parameter_count']>0
   report['AMP']={'enabled':scaler.is_enabled(),'autocast':'float16','loss_scaler_initial':scaler.get_scale()};assert scaler.is_enabled()
   report['trainable_parameters']=sum(p.numel() for p in m.parameters() if p.requires_grad)
   store=Store(out/'state');budget=PhysicalBudget(out/'physical_steps.jsonl',3);rng=random.Random(8191+17)
   meta={'logical_update':0,'stream_position':0,'diagnostic_anchors':{},'decision':{'engineering_fixed_plan':True},
    'replay_queue':[x for x in plan['updates'][1]],'replay_selection_rng':rng.getstate(),'runtime_manifest_sha256':freeze}
   t=time.perf_counter();r0=store.commit(m,opt,scaler,meta);report['initial_commit_seconds']=time.perf_counter()-t;costs=[]
   def step(index):
    nonlocal meta
    result=optimizer_update(m,opt,scaler,features,plan['updates'][index],'cuda',guard,budget.before_step)
    # A nonempty persistent queue/RNG participates in the exact comparison.
    rng.setstate(meta['replay_selection_rng']);rng.random();meta.update(logical_update=index+1,stream_position=index+1,replay_selection_rng=rng.getstate(),replay_queue=plan['updates'][index])
    costs.append(result);append(out/'updates.jsonl',{'physical_update':len(costs),**result});return result
   step(0);t=time.perf_counter();r1=store.commit(m,opt,scaler,meta);report['update1_commit_seconds']=time.perf_counter()-t
   step(1);t=time.perf_counter();r2=store.commit(m,opt,scaler,meta);report['update2_commit_seconds']=time.perf_counter()-t
   a=store.load(r2);a_sha=semantic(a)
   # Reconstruct model/optimizer/scaler objects, then load a committed on-disk state, not a CPU in-memory clone.
   del m,opt,scaler;gc.collect();torch.cuda.empty_cache();t=time.perf_counter();m,tok,opt,scaler=make(17,guard)
   meta=store.restore(m,opt,scaler,r1);report['reconstruct_and_restore_seconds']=time.perf_counter()-t
   step(1);b=capture(m,opt,scaler,meta);b_sha=semantic(b)
   report['resume_comparison']={'exact':a_sha==b_sha,'uninterrupted_full_state_sha256':a_sha,'restored_next_update_full_state_sha256':b_sha,
    'scope':'new model/optimizer/scaler objects in same process, full persisted base+quant+buffers+attrs+optimizer+scaler+RNG+queue; fresh OS process not tested',
    'losses_exact':costs[1]['losses']==costs[2]['losses']}
   assert a_sha==b_sha and report['resume_comparison']['losses_exact'],'exact persisted next-update equivalence failed; no extra attempt'
   store.commit(m,opt,scaler,meta)
   allrr={r['episode_id']:r for split in ('train','dev') for r in rows(split)}
   before=capture(m,opt,scaler,meta);bindings={'checkpoint_full_semantic_sha256':b_sha,'manifest_sha256':freeze}
   gen=[]
   for eid in plan['generation_ids']:
    r=allrr[eid];cache=ExactCache(out/'cache',{'trajectory':'engineering-only','seed':17},bindings,
     {'p14v2_manifest_sha256':h((DATA/'manifest.json').read_bytes()),'fixture_sha256':h((DATA/'fixtures'/f"{r['split']}.json").read_bytes())})
    gen+=evaluate(m,tok,[r],guard,cache,out/'generation_records.jsonl')
   restore(before,m,opt,scaler);assert semantic(capture(m,opt,scaler,meta))==semantic(before)
   modes={}
   for mode,key in [('tool','tool_usage'),('real_final','real_final_usage'),('gold_final','gold_final_usage')]:
    u=[r[key] for r in gen];modes[mode]={'logical_requests':len(u),'physical_requests':sum(x['inference_calls'] for x in u),
     'wall_seconds':sum(x['wall_seconds'] for x in u),'input_tokens':sum(x['input_tokens'] for x in u),'output_tokens':sum(x['output_tokens'] for x in u),
     'hit_length_cap':sum(x.get('hit_length_cap',False) for x in u),
     'peak_allocated_MiB':max(x.get('peak_allocated_MiB',0) for x in u),'peak_reserved_MiB':max(x.get('peak_reserved_MiB',0) for x in u)}
   assert len(gen)==2 and sum(x['physical_requests'] for x in modes.values())<=6
   report.update(status='PASS',updates=costs,generation_modes=modes,physical_optimizer_updates=3,logical_optimizer_updates=2,
    extra_recompute_optimizer_updates=1,extra_recompute_backward_sequences=costs[2]['backward_sequences'],
    max_allocated_MiB=max([c['peak_allocated_MiB'] for c in costs]+[x['peak_allocated_MiB'] for x in modes.values()]),
    max_reserved_MiB=max([c['peak_reserved_MiB'] for c in costs]+[x['peak_reserved_MiB'] for x in modes.values()]),
    gradient_finite=True,checkpoint_current=read(out/'state/CURRENT.json'))
 except BaseException as exc:
  report.update(status='BLOCKED_OR_FAILED',error=repr(exc),traceback=traceback.format_exc(),no_automatic_retry=True)
 finally:
  guard.close();report['elapsed_seconds']=time.perf_counter()-started
  report['physical_step_intents']=len((out/'physical_steps.jsonl').read_text().splitlines()) if (out/'physical_steps.jsonl').exists() else 0
  report['last_committed_checkpoint']=read(out/'state/CURRENT.json') if (out/'state/CURRENT.json').exists() else None
  report['disk_after']=disk_check(reconcile=True);atomic_json(out/'RESULT.json',report)
 print(cj({k:v for k,v in report.items() if k not in ('checkpoint_current','last_committed_checkpoint','updates','traceback')}))
 if report['status']!='PASS':raise RuntimeError('Engineering stopped; inspect RESULT.json. No automatic second attempt.')

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');run(p.parse_args().execute)
