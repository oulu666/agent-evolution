"""CPU-only matched analysis. Strict scores never accept line numbers as text."""
import collections,datetime,hashlib,json,re,statistics
from pathlib import Path
R=Path(__file__).resolve().parents[1];Q=R/'runs_ext_p10_unitclarify48_20261117';B=R/'runs_ext_p10_devdiagnosis_20261117';D=R/'data_ext_p10_twoview_cpu_20261117'
def j(p):return json.loads(p.read_text(encoding='utf-8'))
def rows(p):return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
def rate(rr,k):return dict(correct=sum(bool(x.get(k)) for x in rr),n=len(rr),rate=statistics.mean(bool(x.get(k)) for x in rr) if rr else None)
def sha(p):return hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
def key(x):return x['seed'],x['case'],x['kind'],x['intent']
def explain(x,dev):
    display=json.loads(x['displayed_observation'])['result'];p=x['predicted_answer'];texts=[t['text'] for t in display];idx=None;unit='other'
    if p in texts:idx=texts.index(p);unit='full_line_text'
    else:
        mt=re.fullmatch(r'(?:line\s*:?\s*)?([0-9]+)',str(p).strip(),re.I)
        if mt:
            n=int(mt.group(1));found=[i for i,t in enumerate(display) if t['line']==n]
            if len(found)==1:idx=found[0];unit='original_line_number_only'
            else:
                found=[i for i,t in enumerate(display) if re.search(r'\b'+re.escape(str(n))+r'$',t['text'])]
                if len(found)==1:idx=found[0];unit='payload_value_only'
                else:unit='unresolved_number'
    original=json.loads(dev[x['episode_id']]['expected_observation'])['result'];gold=original[0 if x['intent']=='first' else -1]['line'];selected=display[idx]['line'] if idx is not None else None
    return dict(unit=unit,selected=selected,gold=gold,item_correct=selected==gold,position='first' if idx==0 else 'last' if idx is not None and idx==len(display)-1 else 'interior' if idx is not None else 'unresolved')
def main():
    complete=j(Q/'COMPLETE.json');assert complete['inference_calls']==48 and complete['optimizer_updates']==0 and j(Q/'supervisor_end.json')['rc']==0
    baseline={key(x):x for x in rows(B/'records.jsonl')};new={key(x):x for x in rows(Q/'records.jsonl')};assert len(baseline)==len(new)==48 and baseline.keys()==new.keys()
    dev={x['episode_id']:x for x in rows(D/'dev.jsonl')};calls=rows(Q/'calls_completed.jsonl');starts=rows(Q/'calls_started.jsonl');assert len(calls)==len(starts)==48 and [x['index'] for x in calls]==list(range(1,49))
    assert len({x['clarification'] for x in new.values()})==1 and next(iter(new.values()))['clarification']==j(Q/'runtime_manifest.json')['clarification']
    pairs=[]
    for k,b in baseline.items():
        n=new[k];assert b['displayed_observation']==n['displayed_observation'] and b['expected_answer']==n['expected_answer'];be=explain(b,dev);ne=explain(n,dev)
        pairs.append(dict(seed=k[0],case=k[1],kind=k[2],intent=k[3],baseline_strict=b['final_correct'],new_strict=n['final_correct'],before=be,after=ne,identity_same=be['selected']==ne['selected'],strict_gain=not b['final_correct'] and n['final_correct'],strict_loss=b['final_correct'] and not n['final_correct'],identity_gain=not be['item_correct'] and ne['item_correct'],identity_loss=be['item_correct'] and not ne['item_correct'],unit_only_repair=be['item_correct'] and ne['item_correct'] and not b['final_correct'] and n['final_correct'],new_parsed=n['parsed_final']))
    cells=[];cases=[]
    for seed in [20261108,20261109,20261110]:
        for kind in ['normal','reversed']:
            for intent in ['first','last']:
                group=[x for x in pairs if x['seed']==seed and x['kind']==kind and x['intent']==intent]
                cells.append(dict(seed=seed,kind=kind,intent=intent,before_strict=rate(group,'baseline_strict'),after_strict=rate(group,'new_strict'),before_item_correct=sum(x['before']['item_correct'] for x in group),after_item_correct=sum(x['after']['item_correct'] for x in group),before_units=dict(collections.Counter(x['before']['unit'] for x in group)),after_units=dict(collections.Counter(x['after']['unit'] for x in group)),strict_gains=sum(x['strict_gain'] for x in group),strict_losses=sum(x['strict_loss'] for x in group),identity_changes=sum(not x['identity_same'] for x in group),unit_only_repairs=sum(x['unit_only_repair'] for x in group)))
        for case in range(4):
            g=[x for x in pairs if x['seed']==seed and x['case']==case];assert len(g)==4
            cases.append(dict(seed=seed,case=case,before_all4=all(x['baseline_strict'] for x in g),after_all4=all(x['new_strict'] for x in g),before_normal_pair=all(x['baseline_strict'] for x in g if x['kind']=='normal'),after_normal_pair=all(x['new_strict'] for x in g if x['kind']=='normal')))
    totals={}
    for kind in ['normal','reversed']:
        g=[x for x in pairs if x['kind']==kind]
        totals[kind]=dict(before_strict=rate(g,'baseline_strict'),after_strict=rate(g,'new_strict'),before_item_correct=sum(x['before']['item_correct'] for x in g),after_item_correct=sum(x['after']['item_correct'] for x in g),before_units=dict(collections.Counter(x['before']['unit'] for x in g)),after_units=dict(collections.Counter(x['after']['unit'] for x in g)),strict_gains=sum(x['strict_gain'] for x in g),strict_losses=sum(x['strict_loss'] for x in g),identity_same=sum(x['identity_same'] for x in g),identity_gains=sum(x['identity_gain'] for x in g),identity_losses=sum(x['identity_loss'] for x in g),unit_only_repairs=sum(x['unit_only_repair'] for x in g))
    usage={k:sum(c[k] for c in calls) for k in ['inference_calls','input_tokens','output_tokens','total_tokens','generation_seconds']};old_usage={k:sum(b['usage'][-1][k] for b in baseline.values()) for k in usage};assert usage['inference_calls']==old_usage['inference_calls']==48
    normal=totals['normal'];passed=normal['after_strict']['correct']-normal['before_strict']['correct']>=12 and normal['after_item_correct']>=24
    for p,h in j(Q/'runtime_manifest.json')['hashes'].items():assert sha(R/p)==h
    for label in ['hashes','inherited_P9_hashes']:
        for p,h in j(D/'manifest.json')[label].items():assert sha(R/p)==h
    receipts=j(Q/'model_receipts.json');assert all(x['live_LoRA_before']==x['live_LoRA_after'] for x in receipts)
    guard=rows(Q/'logs/guard.jsonl');assert all(x['safe'] for x in guard) and not (Q/'logs/STOP').exists()
    summary=dict(complete=True,created=datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z'),scope='48 new answer-only dev clarifications; cached48 baselines not rerun',cells=cells,totals=totals,paired_cases=cases,pairs=pairs,usage_new48=usage,usage_cached48_answers=old_usage,additional_input_tokens=usage['input_tokens']-old_usage['input_tokens'],preregistered_normal_unit_repair_success=passed,optimizer_updates=0,new_tool_calls=0,formal_calls=0,model_receipts=receipts,guard_checks=len(guard),completion=complete)
    with (Q/'summary.json').open('x',encoding='utf-8') as f:json.dump(summary,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in summary.items() if k not in ['pairs','paired_cases']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()