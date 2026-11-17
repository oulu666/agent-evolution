"""CPU analysis of completed one-shot formal validation. No output mapping for scoring."""
import collections,datetime,hashlib,json,re,statistics
from pathlib import Path
R=Path(__file__).resolve().parents[1];Q=R/'runs_ext_p10_formal_prompt_20261117';D=R/'data_ext_p10_twoview_cpu_20261117'
def j(p):return json.loads(p.read_text(encoding='utf-8'))
def rows(p):return [json.loads(x)for x in p.read_text(encoding='utf-8').splitlines()if x.strip()]
def score(x):return bool(x['joint_success']if x['kind']=='normal'else x['final_correct'])
def key(x):return x['seed'],x['case'],x['kind'],x['intent']
def explain(x,dev):
    obj=json.loads(x['displayed_observation']);display=obj.get('result',[])if obj.get('ok')else[];display=display if isinstance(display,list)and all(isinstance(t,dict)and'text'in t and'line'in t for t in display)else[]
    p=x['predicted_answer'];texts=[t['text']for t in display];idx=None;unit='other'if display else'no_valid_matches'
    if p in texts:idx=texts.index(p);unit='full_line_text'
    else:
        mt=re.fullmatch(r'(?:line\s*:?\s*)?([0-9]+)',str(p).strip(),re.I)
        if mt and display:
            n=int(mt.group(1));found=[i for i,t in enumerate(display)if t['line']==n]
            if len(found)==1:idx=found[0];unit='original_line_number_only'
            else:
                found=[i for i,t in enumerate(display)if re.search(r'\b'+re.escape(str(n))+r'$',t['text'])]
                if len(found)==1:idx=found[0];unit='payload_value_only'
                else:unit='unresolved_number'
    orig=json.loads(dev[x['episode_id']]['expected_observation'])['result'];gold=orig[0 if x['intent']=='first'else-1]['line'];selected=display[idx]['line']if idx is not None else None
    return dict(unit=unit,selected=selected,gold=gold,item_correct=selected==gold,valid_matches=bool(display),position='first'if idx==0 else'last'if idx is not None and idx==len(display)-1 else'interior'if idx is not None else'unresolved')
def comparison(rr):
    orig=[x for x in rr if x['prompt_condition']=='original'];clar=[x for x in rr if x['prompt_condition']=='clarified'];a={key(x):x for x in orig};b={key(x):x for x in clar};assert a.keys()==b.keys();n=len(a)
    paired=collections.Counter();ids=collections.Counter();units={};positions={}
    for k,x in a.items():
        y=b[k];paired['both_correct'if score(x)and score(y)else'original_only_harm'if score(x)else'clarified_only_gain'if score(y)else'both_wrong']+=1
        ids['identity_gains']+=not x['identity']['item_correct']and y['identity']['item_correct'];ids['identity_losses']+=x['identity']['item_correct']and not y['identity']['item_correct'];ids['same_selected_identity']+=x['identity']['selected']==y['identity']['selected'];ids['pure_unit_strict_repairs']+=not score(x)and score(y)and x['identity']['item_correct']and y['identity']['item_correct']
    for label,group in [('original',orig),('clarified',clar)]:units[label]=dict(collections.Counter(x['identity']['unit']for x in group));positions[label]=dict(collections.Counter(x['identity']['position']for x in group))
    return dict(n=n,original=sum(score(x)for x in orig),clarified=sum(score(x)for x in clar),delta_pp=100*(sum(score(x)for x in clar)-sum(score(x)for x in orig))/n if n else 0,paired=dict(paired),identity_correct_original=sum(x['identity']['item_correct']for x in orig),identity_correct_clarified=sum(x['identity']['item_correct']for x in clar),identity_transitions=dict(ids),units=units,display_positions=positions)
def main():
    complete=j(Q/'COMPLETE.json');assert complete['inference_calls']==360 and complete['optimizer_updates']==0 and j(Q/'supervisor_end.json')['rc']==0
    rr=rows(Q/'records.jsonl');assert len(rr)==288 and len({(*key(x),x['prompt_condition'])for x in rr})==288
    assert {x['seed']for x in rr}=={20261108,20261109,20261110}and{str(x['case'])for x in rr}=={str(x)for x in range(12)}and{x['prompt_condition']for x in rr}=={'original','clarified'}
    calls=rows(Q/'calls_completed.jsonl');starts=rows(Q/'calls_started.jsonl');assert len(calls)==len(starts)==360 and[x['index']for x in calls]==list(range(1,361))and len({x['tag']for x in calls})==360
    assert dict(collections.Counter(x['stage']for x in calls))==dict(normal_shared_tool=72,normal_answer=144,reversed_answer=144)
    tools=rows(Q/'shared_tools.jsonl');assert len(tools)==len({x['tag']for x in tools})==72
    by_tool={x['tag']:x for x in tools};dev={x['episode_id']:x for x in rows(D/'holdout.jsonl')};assert{x['episode_id']for x in rr}==set(dev)
    for x in rr:
        assert x['expected_answer']==dev[x['episode_id']]['expected_final_answer'];x['identity']=explain(x,dev)
        if x['kind']=='normal':
            t=by_tool[x['shared_tool_tag']];assert all(x[k]==t[k]for k in ['tool_correct','arguments_correct','execution_success','tool_call_raw','observation'])and x['displayed_observation']==t['observation'];assert x['joint_success']==all(x[k]for k in ['tool_correct','arguments_correct','execution_success','final_correct'])
    paired={(x['seed'],x['case'],x['kind'],x['intent']):{}for x in rr}
    for x in rr:paired[key(x)][x['prompt_condition']]=x
    deltas=[]
    for k,p in paired.items():
        a,b=p['original'],p['clarified'];assert a['displayed_observation']==b['displayed_observation'];deltas.append(b['usage'][0]['input_tokens']-a['usage'][0]['input_tokens'])
    assert set(deltas)=={46},set(deltas)
    per_seed=[];totals={};case_pairs=[]
    for seed in [20261108,20261109,20261110]:
        c={'seed':seed}
        for kind in ['normal','reversed']:
            for intent in ['first','last','both']:c[kind+'_'+intent]=comparison([x for x in rr if x['seed']==seed and x['kind']==kind and(intent=='both'or x['intent']==intent)])
        per_seed.append(c)
        for case in range(12):
            row=dict(seed=seed,case=case)
            for prompt in ['original','clarified']:
                g=[x for x in rr if x['seed']==seed and x['case']==case and x['prompt_condition']==prompt];assert len(g)==4
                row[prompt+'_all4']=all(score(x)for x in g);row[prompt+'_normal_pair']=all(score(x)for x in g if x['kind']=='normal');row[prompt+'_reversed_pair']=all(score(x)for x in g if x['kind']=='reversed')
            case_pairs.append(row)
    for kind in ['normal','reversed']:
        for intent in ['first','last','both']:totals[kind+'_'+intent]=comparison([x for x in rr if x['kind']==kind and(intent=='both'or x['intent']==intent)])
    group_metrics={}
    for metric in ['all4','normal_pair','reversed_pair']:
        group_metrics[metric]=dict(n=36,original=sum(x['original_'+metric]for x in case_pairs),clarified=sum(x['clarified_'+metric]for x in case_pairs),gains=sum(not x['original_'+metric]and x['clarified_'+metric]for x in case_pairs),harms=sum(x['original_'+metric]and not x['clarified_'+metric]for x in case_pairs),per_seed=[dict(seed=seed,original=sum(x['original_'+metric]for x in case_pairs if x['seed']==seed),clarified=sum(x['clarified_'+metric]for x in case_pairs if x['seed']==seed),n=12)for seed in [20261108,20261109,20261110]])
    strata=[]
    for field in ['wording_label','n_matches']:
        for value in sorted({x[field]for x in rr}):
            row=dict(field=field,value=value)
            for kind in ['normal','reversed']:
                for intent in ['first','last','both']:row[kind+'_'+intent]=comparison([x for x in rr if x[field]==value and x['kind']==kind and(intent=='both'or x['intent']==intent)])
            strata.append(row)
    numeric=['inference_calls','input_tokens','output_tokens','total_tokens','generation_seconds'];cost=lambda g:{k:sum(x[k]for x in g)for k in numeric};costs=dict(actual_total=cost(calls),shared_normal_tools=cost([x for x in calls if x['stage']=='normal_shared_tool']))
    for kind in ['normal','reversed']:
        for prompt in ['original','clarified']:costs[kind+'_'+prompt+'_answers']=cost([x['usage'][0]for x in rr if x['kind']==kind and x['prompt_condition']==prompt])
    assert costs['actual_total']['input_tokens']==sum(x['input_tokens']for x in tools for x in [x['usage']])+sum(x['usage'][0]['input_tokens']for x in rr)
    pipeline={k:sum(t[k]for t in tools)for k in ['tool_correct','arguments_correct','execution_success']};pipeline['n']=len(tools)
    normal=totals['normal_both'];success=normal['delta_pp']>=10-1e-9 and sum(x['normal_both']['delta_pp']>0 for x in per_seed)>=2 and totals['normal_first']['delta_pp']>=0
    guards=rows(Q/'logs/guard.jsonl');assert all(x['safe']for x in guards);receipts=j(Q/'model_receipts.json');assert all(x['live_LoRA_before']==x['live_LoRA_after']for x in receipts)
    for p,h in j(Q/'runtime_manifest.json')['hashes'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h,p
    for kind in ['hashes','inherited_P9_hashes']:
        for p,h in j(D/'manifest.json')[kind].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h,p
    summary=dict(complete=True,created=datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %z'),scope='unseen formal File validation, two frozen prompts, no training',per_seed=per_seed,totals=totals,group_metrics=group_metrics,strata=strata,pipeline=pipeline,costs=costs,preregistered_practical_success=success,first_strict_harms=totals['normal_first']['paired'].get('original_only_harm',0),first_identity_losses=totals['normal_first']['identity_transitions']['identity_losses'],paired_input_increment_tokens=46,all_actual_calls=360,completion=complete,model_receipts=receipts,safety=dict(checks=len(guards),all_safe=True,min_power=min(x['power_limit_W']for x in guards),max_power=max(x['power_limit_W']for x in guards)))
    for filename,obj in [('summary.json',summary),('identity_unit_explanation_CPU.json',rr),('case_pairs_CPU.json',case_pairs)]:
        with(Q/filename).open('x',encoding='utf-8')as f:json.dump(obj,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:v for k,v in summary.items()if k not in ['strata','model_receipts']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()