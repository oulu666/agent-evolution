"""CPU only: add review plan and bounded engineering plan; preserve P14/P15 v1-v2."""
from common import *

def main():
 cohort=read(OLD_RUN/'cohort.json');assert len(cohort)==108 and {c['method'] for c in cohort}==set(METHODS)
 ids=set(read(OLD_RUN/'diagnostic_subsets.json')['dev_ids']);diag=[r for r in rows('dev') if r['episode_id'] in ids]
 by=collections.Counter(r['continual_group'] for r in diag);assert len(diag)==88
 adaptive={'p11_priority','layer_replay','no_priority','no_layer'}
 refresh=sum(2*(2*by[c['order'][0]]+by[c['order'][1]]) for c in cohort if c['method'] in adaptive)
 ledger={'trajectories':108,'methods':METHODS,'per_method':18,'logical_updates':108*384,
  'dev_node_episodes':108*4*88,'dev_refresh_episodes':refresh,'test_episodes':108*4*348,
  'dev_logical_generation_requests':3*(108*4*88+refresh),'test_logical_generation_requests':3*108*4*348,
  'total_logical_generation_requests':3*(108*4*88+refresh+108*4*348),
  'potential_same_checkpoint_update0_reuse_requests':3*refresh//2,
  'request_cap_after_update0_exact_cache_if_all_bindings_match':3*(108*4*88+refresh//2+108*4*348),
  'real_gold_prompt_reuse':'additional only after exact prompt bytes/model/data/generation key equality; no assumed hit rate',
  'stage1_shared_states':False,'full_replay':'deferred; NOT seventh arm',
  'test_during_training':False,'new_stream_source':str((OLD_RUN/'new_streams.json').relative_to(ROOT)),
  'new_stream_sha256':h((OLD_RUN/'new_streams.json').read_bytes()),
  'new_budget_ledger_source':str((OLD_RUN/'budget_ledger.json').relative_to(ROOT)),
  'fairness':{'branch_weights_when_replay':{'new':.5,'replay':.5},'new_only_weight':1.,
   'normalization':'each branch effective supervised tokens separately','not_equal_compute_or_supervision':True,
   'scope':'method-paired same order/seed new stream; not cross-stage equal intensity or pure interference causality'},
  'disk':{'hard_run_bytes':MAX_RUN_BYTES,'free_reserve_bytes':MIN_FREE,'rolling_slots':2,
   'node_storage':'four trainable-only generation states, base/quant/buffer blobs content-addressed; no duplicate adapter packages'},
  'deterministic_backend':{'torch_use_deterministic_algorithms':True,'cudnn_benchmark':False,'cudnn_deterministic':True,'CUBLAS_WORKSPACE_CONFIG':':4096:8'}}
 write(RUN/'review_budget_v3.json',ledger,True)
 train=rows('train');dev=rows('dev');f=features_load()
 def first(skill,rr=train,predicate=lambda r:True):return next(r['episode_id'] for r in rr if r['skill']==skill and predicate(r))
 loc=first('cal.list_locations',predicate=lambda r:isinstance(r['expected_final_answer'],list) and len(r['expected_final_answer'])>=3)
 updates=[[(first('cal.extract_id_sorted'),'both','new'),(first('cal.extract_title_sorted'),'both','new'),(loc,'final','replay')],
  [(first('cal.extract_location_sorted'),'both','new'),(first('cal.extract_start_sorted'),'both','new'),(first('cal.count_date'),'call','replay')]]
 plan={'seed':17,'non_scientific':True,'physical_update_cap':3,'unique_logical_updates':2,'updates':updates,
  'generation_ids':[first('cal.count_month'),first('cal.extract_id_sorted',dev)],'generation_calls_by_mode_cap':{'tool':2,'real_final':2,'gold_final':2},
  'per_logical_update_input_tokens':[sum(f[e]['input_tokens'] for e,m,b in ex) for ex in updates],
  'physical_input_token_total':sum(f[e]['input_tokens'] for e,m,b in updates[0])+2*sum(f[e]['input_tokens'] for e,m,b in updates[1]),
  'new_object_reconstruction':True,'same_process_only':True,'failure_policy':'one attempt only; retain evidence; no automatic extra updates/attempts'}
 write(RUN/'engineering_plan.json',plan,True);print(cj({'budget':ledger,'engineering':plan}))

if __name__=='__main__':main()
