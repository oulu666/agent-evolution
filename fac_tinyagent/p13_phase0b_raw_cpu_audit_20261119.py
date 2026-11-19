"""Post-final CPU-only raw-call rescoring and independent frozen-metric recount. No inference."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
import ast,json,time,collections,traceback,sys,tempfile
from typing import Any,Dict,List,Optional,Tuple
from pathlib import Path
from . import p13_phase0b_persist_20261119 as F
from .metrics import answers_equal,observations_equal,joint_success
from .tools import build_calendar_registry,build_db_registry,build_file_registry,build_stats_registry,materialize_sandbox
from .utils import canonical_json,read_json,read_jsonl,write_json,sha256_file
ROOT=F.ROOT;RUN=F.RUN;OUT=RUN/'raw_independent_CPU_audit_20261119.json'

def main():
    time.tzset();F.verify();assert read_json(RUN/'cpu_final_guard_repair_20261119_v3/CPU_FINAL_COMPLETE.json')['passed'];assert not OUT.exists()
    source=ROOT/'fac_tinyagent/sft/evaluate.py';tree=ast.parse(source.read_text());names={'extract_json_object','parse_tool_call','parse_final_answer','_registry_for','_evaluate_tool_prediction'};nodes=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in names];assert len(nodes)==5
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(source),'exec'),globals())
    gold={r['episode_id']:r for r in read_jsonl(F.DATA/'dev.jsonl')};summary=read_json(RUN/'summary.json');derived=[];per_seed={};costs=[];checked=0;primary=[];mapping=read_json(F.DATA/'pair_mapping.json');all_scores=0;new_calls=0
    for seed in F.SEEDS:
        out=ROOT/read_json(RUN/'seeds'/f'seed{seed}'/'COMPLETE.json')['attempt'];pred=read_json(out/'prediction.json')['rows'];before={r['episode_id']:r for r in read_json(out/'nll_prefix.json')['rows']};after={r['episode_id']:r for r in read_json(out/'nll_predictor_virtual1.json')['rows']}
        for x,p in pred.items():
            assert p['input_tokens']==before[x]['input_tokens']
            for seg in F.SEGMENTS:assert p['initial'][seg]==before[x][seg] and p['delta'][seg]==after[x][seg]-before[x][seg] and p['risk'][seg]==max(0.,p['delta'][seg]);all_scores+=1
        nodes={}
        for node in [0,5,10]:
            records=read_jsonl(out/f'node{node:02}/results.jsonl');assert len(records)==48 and len({r['episode_id'] for r in records})==48
            for r in records:
                g=gold[r['episode_id']];assert g['tool_family']=='calendar'
                rr=_evaluate_tool_prediction(g,r['tool_call_raw'],str(F.DB),str(F.CAL))
                for key,value in rr.items():assert value==r[key],f'raw tool rescore mismatch {seed}/{node}/{r["episode_id"]}/{key}'
                ok,p=parse_final_answer(r['answer_raw']);final=bool(ok and answers_equal(g['expected_final_answer'],p));assert final==r['final_correct'] and p==r['predicted_answer'];assert r['joint_success']==joint_success({**rr,'final_correct':final});checked+=1;new_calls+=sum(u['inference_calls'] for u in r['generation_usage'])
            nodes[node]={r['episode_id']:r for r in records}
            for skill in F.SKILLS:
                counts={metric:sum(bool(r[metric]) for r in records if r['skill']==skill) for metric in ['tool_correct','arguments_correct','execution_success','final_correct','joint_success']};assert counts==summary['outcomes_out_of_24_each_skill'][str(seed)][str(node)][skill]
        ar=read_json(out/'at_risk.json');assert ar['core']==[x for x,r in nodes[0].items() if r['tool_correct'] and r['arguments_correct']];assert ar['Joint']==[x for x,r in nodes[0].items() if r['joint_success']]
        per_seed[str(seed)]={}
        for skill in F.SKILLS:
            skill_ids=[x for x,r in nodes[0].items() if r['skill']==skill];b=nodes[0];end=nodes[10];core=lambda r:bool(r['tool_correct'] and r['arguments_correct'])
            per_seed[str(seed)][skill]={'n':24,'core_correct_nodes_0_5_10':[sum(core(nodes[node][x]) for x in skill_ids) for node in [0,5,10]],'Joint_correct_nodes_0_5_10':[sum(nodes[node][x]['joint_success'] for x in skill_ids) for node in [0,5,10]],'core_at_risk':sum(core(b[x]) for x in skill_ids),'core_lost':sum(core(b[x]) and not core(end[x]) for x in skill_ids),'Joint_at_risk':sum(b[x]['joint_success'] for x in skill_ids),'Joint_lost':sum(b[x]['joint_success'] and not end[x]['joint_success'] for x in skill_ids),'Joint_gained':sum(not b[x]['joint_success'] and end[x]['joint_success'] for x in skill_ids)}
        for x,r in nodes[10].items():
            b=nodes[0][x];p=pred[x];c=pred[mapping[x]]
            if b['tool_correct'] and b['arguments_correct']:primary.append({'seed':seed,'episode_id':x,'lost':not(r['tool_correct'] and r['arguments_correct']),'risk_call':p['risk']['call'],'initial_call':p['initial']['call'],'input_tokens':p['input_tokens'],'candidate_mapped_risk':c['risk']['call']})
        costs.append({'seed':seed,**read_json(out/'cost.json')})
    for key in ['risk_call','initial_call','input_tokens','candidate_mapped_risk']:assert F.metric_table(primary,key)==summary['primary_per_seed_metrics'][key]
    assert F.bootstrap(primary)==summary['bootstrap_all_at_risk'];enough=summary['seeds_with_minimum_events'];eligible=[r for r in primary if r['seed'] in enough];assert F.bootstrap(eligible)==summary['bootstrap_gate_eligible_seeds']
    assert len(primary)==summary['primary_total_at_risk'] and sum(r['lost'] for r in primary)==summary['primary_core_losses'];assert new_calls==864
    costs.append({'phase':'engineering_A',**read_json(RUN/'engineering_A/cost.json')});physical=sum(v for c in costs for k,v in c['counts'].items() if k.endswith('_optimizer_steps'));backward=sum(v for c in costs for k,v in c['counts'].items() if k.endswith('_backward_samples'));nll=sum(c['counts']['NLL_forward_samples'] for c in costs);assert (physical,backward,nll)==(31,248,608)
    import torch;assert not torch.cuda.is_initialized()
    result={'time':F.now(),'passed':True,'raw_episodes_rescored':checked,'raw_tool_and_final_and_execution_and_Joint_exact':True,'original_metric_function_AST_source_sha256':sha256_file(source),'prediction_segment_values_rederived_exact':all_scores,'per_seed_per_skill':per_seed,'primary_metrics_and_both_bootstraps_recomputed_exact':True,'physical_updates':physical,'backward_samples':backward,'NLL_forward_samples':nll,'generation_calls_recounted':new_calls,'CPU_audit_new_optimizer_steps':0,'CPU_audit_new_forward_or_generate':0,'CUDA_initialized':False,'decision':summary['decision']};write_json(OUT,result);print(json.dumps(result,ensure_ascii=False,indent=2));return result
if __name__=='__main__':
    try:main()
    except BaseException as exc:write_json(RUN/f'RAW_CPU_AUDIT_FAILED_{time.strftime("%Y%m%d_%H%M%S")}.json',{'time':F.now(),'error':repr(exc),'stop_no_result_adjustment':True});traceback.print_exc();sys.exit(1)
