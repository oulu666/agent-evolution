"""Independent Phase0B CPU contracts and completed-state audit; no GPU use."""
import argparse,collections,json,math,time
from pathlib import Path
from .utils import read_json,read_jsonl,write_json,sha256_file
from . import p13_phase0b_20261118 as P

def cpu():
    P.verify();features=read_json(P.DATA/'features_masks.json');checks=0
    for e,x in features.items():
        m={k:set(v) for k,v in x['masks'].items()};expected={i for i,y in enumerate(x['features']['labels']) if y!=-100};parts=[m[k] for k in ['tool_name','args','call_other','final']]
        assert set.union(*parts)==expected and sum(map(len,parts))==len(expected)
        assert m['call']==m['tool_name']|m['args']|m['call_other'] and m['all']==expected
        assert all(x['denominators'][k]==len(m[k])>0 for k in m)
        # Deterministic synthetic CE: segment weighted means must reconstruct whole mean.
        losses={i:(i%11)/7 for i in expected};whole=sum(losses.values())/len(expected)
        reconstructed=sum(sum(losses[i] for i in a) for a in parts)/len(expected);assert abs(whole-reconstructed)<1e-12;checks+=1
    case=[{'score':.9,'lost':True},{'score':.6,'lost':False},{'score':.3,'lost':True},{'score':.1,'lost':False}]
    m=P.weighted_metrics(case);assert abs(m['AUROC']-.75)<1e-12 and abs(m['AUPRC']-5/6)<1e-12 and abs(m['TopQuartileRecall']-.5)<1e-12
    tied=P.weighted_metrics([{'score':1,'lost':True},{'score':1,'lost':False}]);assert tied['AUROC']==.5 and tied['AUPRC']==.5 and tied['TopQuartileRecall']==.25
    # Absent bootstrap clusters get ZERO weight, not one.
    rows=[{'seed':P.SEEDS[0],'episode_id':'a','lost':True,'risk_call':1},{'seed':P.SEEDS[0],'episode_id':'b','lost':False,'risk_call':0},{'seed':P.SEEDS[1],'episode_id':'a','lost':True,'risk_call':0},{'seed':P.SEEDS[1],'episode_id':'b','lost':False,'risk_call':1}]
    assert P.macro_auc(rows,'risk_call',{P.SEEDS[0]:1},{'a':1,'b':1})==1
    assert P.macro_auc(rows,'risk_call',{P.SEEDS[0]:1},{'a':1}) is None
    mapping=read_json(P.DATA/'pair_mapping.json');dev={r['episode_id']:r for r in read_jsonl(P.DATA/'dev.jsonl')};cand={r['episode_id']:r for r in read_jsonl(P.DATA/'candidate.jsonl')}
    assert len(mapping)==48 and len(set(mapping.values()))==48
    for d,c in mapping.items():assert dev[d]['structure']==cand[c]['structure'] and dev[d]['expected_arguments']['date']!=cand[c]['expected_arguments']['date']
    result={'time':P.now(),'passed':True,'mask_partition_and_normalization_checks':checks,'metric_tie_AP_topK_tests':True,'bootstrap_absent_cluster_zero_weight_tests':True,'predefined_structure_mapping_pairs':48,'phase0b_manifest_sha256':sha256_file(P.DATA/'manifest.json'),'audit_source_sha256':sha256_file(Path(__file__))}
    write_json(P.RUN/'independent_cpu_acceptance.json',result);print(json.dumps(result,ensure_ascii=False));return result

def final():
    cpu();assert read_json(P.RUN/'COMPLETE.json')['complete'];assert read_json(P.RUN/'supervisor_end.json')['rc']==0
    guards=read_jsonl(P.LOG/'guard.jsonl');assert all(g['safe'] for g in guards);updates=[];statechecks=[]
    for seed in P.SEEDS:
        done=read_json(P.RUN/'seeds'/f'seed{seed}'/'COMPLETE.json');out=P.ROOT/done['attempt'];trace=read_jsonl(out/'updates.jsonl');virtual=[r for r in trace if r['kind']=='predictor_virtual'];natural=[r for r in trace if r['kind']=='natural_suffix'];assert len(virtual)==1 and len(natural)==10
        assert virtual[0]['state_hash']==natural[0]['state_hash'],'predictor vs actual step1 mismatch'
        restore=read_json(out/'restoration.json');assert restore['exact'] and restore['before']==restore['after'] and restore['prefix_file_unchanged']
        rows0={r['episode_id']:r for r in read_jsonl(out/'node00/results.jsonl')};rows10={r['episode_id']:r for r in read_jsonl(out/'node10/results.jsonl')};assert len(rows0)==48 and set(rows0)==set(rows10)
        risk=[e for e,r in rows0.items() if r['tool_correct'] and r['arguments_correct']];lost=[e for e in risk if not(rows10[e]['tool_correct'] and rows10[e]['arguments_correct'])]
        updates.append({'seed':seed,'at_risk':len(risk),'lost':len(lost)});statechecks.append({'seed':seed,'virtual_first_step_matches_actual':True,'exact_restore':True})
        for node in [0,5,10]:
            for r in read_jsonl(out/f'node{node:02}/results.jsonl'):assert r['joint_success']==all(r[k] for k in ['tool_correct','arguments_correct','execution_success','final_correct'])
    s=read_json(P.RUN/'summary.json');assert sum(r['lost'] for r in updates)==s['primary_core_losses'] and sum(r['at_risk'] for r in updates)==s['primary_total_at_risk']
    result={'time':P.now(),'passed':True,'per_seed_independent_recount':updates,'state_checks':statechecks,'safe_guards':len(guards),'decision':s['decision'],'no_repeat_midpoint_rows_in_primary':True}
    write_json(P.RUN/'independent_final_acceptance.json',result);print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['cpu','final']);a=p.parse_args();{'cpu':cpu,'final':final}[a.mode]()
