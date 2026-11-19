"""CPU-only postmortem of the ONE engineering attempt. Never imports a model loader or retries GPU.
Reconstructs only facts durably witnessed; never creates RESULT.json or opens formal launch gate.
"""
import os,sys,json,datetime,pathlib,math,hashlib
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1'
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'p15_review_v3_20261119'))
from common import *
from state_v3 import Store,semantic,helpers,file_sha

def main():
 import torch
 freeze=verify();out=RUN/'engineering_attempt01'
 def lines(p):return [json.loads(s) for s in p.read_text().splitlines() if s]
 commits=lines(out/'state/commits.jsonl');updates=lines(out/'updates.jsonl');physical=lines(out/'physical_steps.jsonl');gen=lines(out/'generation_records.jsonl')
 assert len(commits)==4 and len(updates)==3 and len(physical)==3 and len(gen)==2
 assert commits[2]['meta']['logical_update']==commits[3]['meta']['logical_update']==2
 assert commits[2]['full_semantic_sha256']==commits[3]['full_semantic_sha256']
 store=Store(out/'state');a=store.load(commits[2]);b=store.load(commits[3]);fs,p=helpers()
 assert semantic(a)==semantic(b)==commits[2]['full_semantic_sha256']
 assert updates[1]['losses']==updates[2]['losses'];assert all(math.isfinite(x['gradient_norm_before_clip']) for x in updates)
 optimizer_steps=sorted({float(v['step']) for v in b['train']['optimizer']['state'].values()})
 assert optimizer_steps==[2.]
 quant_count=len(b['base']['quant_parameter_states']);assert quant_count>0
 modes={}
 for mode,key in [('tool','tool_usage'),('real_final','real_final_usage'),('gold_final','gold_final_usage')]:
  u=[r[key] for r in gen];modes[mode]={'logical_requests':2,'physical_requests':sum(x['inference_calls'] for x in u),
   'wall_seconds_each':[x['wall_seconds'] for x in u],'wall_seconds_total':sum(x['wall_seconds'] for x in u),
   'input_tokens_each':[x['input_tokens'] for x in u],'output_tokens_each':[x['output_tokens'] for x in u],
   'peak_allocated_MiB':max(x['peak_allocated_MiB'] for x in u),'peak_reserved_MiB':max(x['peak_reserved_MiB'] for x in u),
   'length_caps_hit':sum(x.get('hit_length_cap',False) for x in u)}
 for cp in (out/'cache').glob('*.json'):
  c=read(cp);assert c['payload_sha256']==h(cj(c['payload']).encode()) and cp.stem==h(cj(c['binding']).encode())
 assert sum(x['physical_requests'] for x in modes.values())==6
 def ts(r):return datetime.datetime.strptime(r['time_Beijing'],'%Y-%m-%d %H:%M:%S %z').timestamp()
 persistence_est=[ts(commits[i+1])-ts(commits[i])-updates[i]['update_wall_seconds'] for i in (0,1)]
 per_token=[u['update_wall_seconds']/u['input_tokens'] for u in updates]
 old=read(OLD_RUN/'budget_ledger.json');new_tokens=old['new_input_tokens_required_exact'];replay_cap=old['replay_input_tokens_required_cap']
 training_hours=[(new_tokens+.75*replay_cap)*min(per_token)*.75/3600,(new_tokens+replay_cap)*max(per_token)*1.5/3600]
 persistence_hours=[41472*max(0,min(persistence_est)-2)/3600,41472*(max(persistence_est)+2)/3600]
 # Explicit scenarios, NOT confidence intervals or guaranteed bounds. Short-prompt training/decoding extrapolates poorly.
 logical_each=603072//3;conditional_cache_each=584064//3
 short_gen=[0.,0.];cap_gen=0.
 for mode,x in modes.items():
  short_gen[0]+=conditional_cache_each*min(x['wall_seconds_each'])*.75/3600
  short_gen[1]+=logical_each*max(x['wall_seconds_each'])*1.5/3600
  cap=128 if mode=='tool' else 256
  observed_s_per_output=max(t/max(1,n) for t,n in zip(x['wall_seconds_each'],x['output_tokens_each']))
  cap_gen+=logical_each*observed_s_per_output*cap*1.5/3600
 forecast={'training_active_approx_hours':training_hours,'update_boundary_persistence_occupying_GPU_hours':persistence_hours,
  'short_output_like_engineering_generation_hours':short_gen,'length_cap_scenario_generation_hours':cap_gen,
  'short_output_total_occupancy_hours':[training_hours[0]+persistence_hours[0]+short_gen[0],training_hours[1]+persistence_hours[1]+short_gen[1]],
  'long_output_total_occupancy_upper_scenario_hours':training_hours[1]+persistence_hours[1]+cap_gen,
  'formula':'training=(new exact + .75..1 replay cap)*observed min..max seconds/input token*.75..1.5; persistence=41472*(coarse boundary interval minus update time +/-2s); generation per mode=(194688 conditional cache ..201024 no hits)*observed min..max wall/request*.75..1.5; cap scenario uses slowest observed wall/output token *128/256 caps *1.5',
  'NOT_a_CI_or_guaranteed_upper_bound':True,'unmeasured_costs':'all main nodes/refresh evaluation full-base capture+restore isolation, train14 probes6048 forwards, model reloads, storage thermal/latency, OS interruptions; can increase occupancy further',
  'caveats':'ONLY2 unique train small updates and2 generation episodes. Output lengths/prefill/context/packing/backward count vary. Lower estimate assumes19008 exact checkpoint-cache hits not yet witnessed in full matrix. No scientific scores used.'}
 result={'status':'STOPPED_REPORT_SERIALIZATION_FAILURE','formal_launch_ready':False,'no_GPU_retry':True,
  'failure':'terminal TypeError: Object of type dtype is not JSON serializable in final atomic_json; RESULT.json absent. Backend fingerprint includes torch.dtype. A preceding caught error after generation cannot be excluded from durable records.',
  'runtime_manifest_v3_sha256':freeze,'cpu_only_postmortem':True,'protected_old_files_unchanged':598,
  'verified':{'physical_optimizer_updates':3,'logical_optimizer_updates':2,'physical_forward_sequences':sum(u['forward_sequences'] for u in updates),
   'physical_backward_sequences':sum(u['backward_sequences'] for u in updates),'input_tokens':sum(u['input_tokens'] for u in updates),
   'fresh_model_object_persisted_restore_next_update_exact':True,'full_state_sha256':semantic(b),'losses_exact':True,
   'final_AdamW_step_values':optimizer_steps,'quantized_parameter_state_count':quant_count,'scaler_state':b['train']['scaler'],
   'generation_logical_requests':6,'generation_physical_requests':6,'test_touched':False,'postgeneration_restore_assertion_durably_witnessed':False},
  'updates':updates,'generation_modes':modes,'checkpoint_commit_times_Beijing':[r['time_Beijing'] for r in commits],
  'coarse_persistence_seconds_each_estimate_pm2s':persistence_est,'coarse_cold_start_plus_initial_commit_seconds':ts(commits[0])-datetime.datetime.fromisoformat('2026-11-19T20:39:51.426+08:00').timestamp(),
  'forecast':forecast,'disk':disk_check(reconcile=True),'artifacts':{str(p.relative_to(ROOT)):file_sha(p) for p in (out/'terminal_failure.txt',out/'updates.jsonl',out/'physical_steps.jsonl',out/'generation_records.jsonl',out/'state/commits.jsonl',out/'state/CURRENT.json',out/'state/slot0.pt',out/'state/slot1.pt')},
  'base_blobs':[{'path':r['base_ref'],'bytes':(ROOT/r['base_ref']).stat().st_size,'sha256':r['base_file_sha256']} for r in commits[2:3]],
  'GPU_released':'separate nvidia-smi after process exit showed no compute apps; RTX4060 Laptop,8188MiB',
  'recommendation':'Do NOT start matrix or rerun engineering. Parent review CPU-only reporting serialization repair/new operational freeze, durable PASS witness, and measured occupancy budget before any launch.'}
 atomic_json(out/'FORENSIC_RESULT.json',result)
 print(cj({k:v for k,v in result.items() if k not in ('artifacts','base_blobs')}))
 assert not torch.cuda.is_initialized()

if __name__=='__main__':main()
