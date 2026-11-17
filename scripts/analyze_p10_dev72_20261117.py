"""CPU-only analysis of the completed, authorized frozen 72-call dev diagnosis."""
import collections,datetime,json,statistics,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];RUN=ROOT/'runs_ext_p10_devdiagnosis_20261117';DATA=ROOT/'data_ext_p10_twoview_cpu_20261117'
def j(p):return json.loads(p.read_text(encoding='utf-8'))
def rows(p):return [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines() if s.strip()]
def rate(rr,key):return dict(correct=sum(bool(r.get(key)) for r in rr),n=len(rr),rate=statistics.mean(bool(r.get(key)) for r in rr) if rr else None)
def sha(p):return hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
def main():
    complete=j(RUN/'COMPLETE.json');end=j(RUN/'supervisor_end.json');assert complete['complete'] and end['rc']==0
    r=rows(RUN/'records.jsonl');calls=rows(RUN/'calls_completed.jsonl');starts=rows(RUN/'calls_started.jsonl');assert len(r)==48 and len(calls)==len(starts)==72
    assert [x['index'] for x in calls]==[x['index'] for x in starts]==list(range(1,73));assert len({(x['seed'],x['case'],x['kind'],x['intent']) for x in r})==48
    usage={k:sum(c[k] for c in calls) for k in ['inference_calls','input_tokens','output_tokens','total_tokens','generation_seconds']};assert usage['inference_calls']==72
    dev={x['episode_id']:x for x in rows(DATA/'dev.jsonl')};cells=[];seed_summary=[];categories=[];context_exact=[]
    for seed in [20261108,20261109,20261110]:
        sr=[x for x in r if x['seed']==seed];assert len(sr)==16
        for kind in ['normal','reversed']:
            for intent in ['first','last']:
                group=[x for x in sr if x['kind']==kind and x['intent']==intent];assert len(group)==4
                c=dict(seed=seed,kind=kind,intent=intent,answer=rate(group,'final_correct'),answer_class=dict(collections.Counter(x['answer_class'] for x in group)))
                if kind=='normal':
                    for key in ['joint_success','tool_correct','arguments_correct','execution_success']:c[key]=rate(group,key)
                cells.append(c)
                errors=collections.Counter()
                for x in group:
                    if kind=='normal' and not x['tool_correct']:error='tool_or_tool_format'
                    elif kind=='normal' and not x['arguments_correct']:error='arguments'
                    elif kind=='normal' and not x['execution_success']:error='execution'
                    elif not x['parsed_final']:error='final_format'
                    elif not x['final_correct']:error='final_'+x['answer_class']
                    else:error='success'
                    errors[error]+=1
                    if kind=='normal':context_exact.append(dict(seed=seed,case=x['case'],intent=intent,tool_history_exact_gold=x['tool_call_raw']==dev[x['episode_id']]['messages'][2]['content']))
                categories.append(dict(seed=seed,kind=kind,intent=intent,first_failure_stage=dict(errors)))
        case_rows=[]
        for case in range(4):
            cr=[x for x in sr if x['case']==case];normal=[x for x in cr if x['kind']=='normal'];reverse=[x for x in cr if x['kind']=='reversed']
            call_ok=all(all(x[k] for k in ['tool_correct','arguments_correct','execution_success']) for x in normal)
            normal_pair=all(x['joint_success'] for x in normal);reverse_pair=all(x['final_correct'] for x in reverse);all4=normal_pair and reverse_pair
            case_rows.append(dict(case=case,n_matches=cr[0]['n_matches'],normal_calls_correct=call_ok,normal_pair=normal_pair,reverse_pair=reverse_pair,all4=all4,preregistered_gap=call_ok and not all4))
        seed_summary.append(dict(seed=seed,normal_pair=rate(case_rows,'normal_pair'),reverse_pair=rate(case_rows,'reverse_pair'),all4=rate(case_rows,'all4'),call_correct_gap_cases=[x['case'] for x in case_rows if x['preregistered_gap']],gap_trigger=any(x['preregistered_gap'] for x in case_rows),cases=case_rows))
    triggers=sum(s['gap_trigger'] for s in seed_summary);pre=j(RUN/'launch_preflight.json');guard=rows(RUN/'logs/guard.jsonl');assert pre['safe'] and all(g['safe'] for g in guard);assert not (RUN/'logs/STOP').exists()
    receipts=j(RUN/'model_receipts.json');assert all(s['live_LoRA_before']==s['live_LoRA_after'] and s['inference_calls']==24 for s in receipts)
    for group in ['hashes','inherited_P9_hashes']:
        for p,h in j(DATA/'manifest.json')[group].items():assert sha(ROOT/p)==h
    for p,h in j(RUN/'runtime_manifest.json')['hashes'].items():assert sha(ROOT/p)==h
    calendar=j(RUN/'calendar_retrospective_CPU.json')['rows'];coverage=j(RUN/'background_coverage_CPU.json')['families']
    calendar_summary={arm:{k:rate([x for x in calendar if x['arm']==arm],k) for k in ['tool_correct','arguments_correct','execution_success','final_correct','joint_success']} for arm in ['baseline','normal','counter']}
    summary=dict(complete=True,created=datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z'),scope='frozen independent dev only; no treatment trained; no formal outputs read',cells=cells,seed_summary=seed_summary,error_categories=categories,tool_history_exact_gold=context_exact,preregistered_gap_seeds=triggers,preregistered_gap_triggered=triggers>=2,trigger_does_not_authorize_training=True,usage=usage,optimizer_updates=0,formal_generation_calls=0,wall_clock=complete,e2e=j(RUN/'e2e_gate.json'),model_receipts=receipts,guard_checks=len(guard),calendar_retrospective=calendar_summary,background_coverage=coverage)
    with (RUN/'summary.json').open('x',encoding='utf-8') as f:json.dump(summary,f,ensure_ascii=False,indent=2)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()