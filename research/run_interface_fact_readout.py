"""Paired boundary-fact readout on the archived calibration and a renamed API."""
import json
from collections import Counter
from pathlib import Path

import torch
from run_interface_boundaries import OPTIONS, WORLDS, TEST_DATES, calendar, execute, iso
from run_rsi_operator_memory import FrozenAgent, ROOT, ADAPTER

OUT = ROOT/'runs_rsi_interface_facts_20261123'
PREV = ROOT/'runs_rsi_interface_20261123'


def write(name, obj):
    tmp = OUT/(name+'.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
    tmp.replace(OUT/name)


def read(path):
    return json.loads(path.read_text())


@torch.inference_mode()
def vote(agent, prompt, symbols):
    ids = [agent.tok.encode(s, add_special_tokens=False) for s in symbols]
    assert all(len(x)==1 for x in ids)
    encoded = agent.encode([dict(role='user', content=prompt)])
    logits = agent.model(**encoded,use_cache=False).logits[0,-1].float()
    return logits[[x[0] for x in ids]].tolist()


def read_fact(agent, context, day):
    ballots=[]
    for labels in [('yes','no'),('no','yes')]:
        prompt=(context+f'\nConsidering only the actual returned events: does the returned list contain an event dated {day}? '
                f'A = {labels[0]}. B = {labels[1]}. Answer with one letter.')
        scores=vote(agent,prompt,'AB')
        margin=scores[labels.index('yes')]-scores[labels.index('no')]
        ballots.append(dict(labels=labels,scores=scores,yes_margin=margin))
    mean=sum(b['yes_margin'] for b in ballots)/2
    return dict(predicted=mean>0,mean_margin=mean,ballots=ballots)


def direct(agent,context,fields):
    ballots=[]
    for i in range(4):
        menu=OPTIONS[i:]+OPTIONS[:i]
        lines=[f'{label}: {fields[0]} = D{a:+d} days, {fields[1]} = D{b:+d} days'
               for label,(a,b) in zip('ABCD',menu)]
        prompt=context+'\nChoose a mapping that retrieves exactly day D.\n'+'\n'.join(lines)+'\nAnswer one letter.'
        scores=vote(agent,prompt,'ABCD')
        ballots.append(dict(menu=menu,scores=scores,choice=menu[scores.index(max(scores))]))
    counts=Counter(b['choice'] for b in ballots)
    ranking=sorted(range(4),key=lambda j:-ballots[0]['scores'][j])
    result=max((OPTIONS[j] for j in ranking),key=lambda x:counts[x])
    return dict(adapter=result,ballots=ballots)


def main():
    OUT.mkdir(exist_ok=True)
    if (OUT/'summary.json').exists():
        print((OUT/'summary.json').read_text()); return
    write('protocol.json',dict(model=str(ADAPTER.relative_to(ROOT)),units=list(WORLDS),
        primary='both boundary bits and exact mapping per contract',secondary='complete returned event sequence on unseen dates',
        historical='reuse exact frozen direct decisions and probe results',
        transfer='renamed API and fields, new dates, raw event objects, same four contracts',
        fact_decode='two label orders per bit, mean yes-minus-no logits > 0; ties no',
        direct_decode='four cyclic orders, majority; ties first-order logits',
        privileged_diagnostic='direct choice with correct observed bits stated explicitly',
        freeze_before_deployment=True))
    agent=FrozenAgent()
    old=read(PREV/'frozen.json')
    manifests={}
    for view in ('archived','renamed'):
        worlds={}
        for name,contract in WORLDS.items():
            if view=='archived':
                probe=old['learned'][name]['observation']
                fields=('start','end')
                edges=(probe['start'],probe['end'])
                returned=probe['returned_dates']
                context='calendar_range calibration, one known event on each calibration date. '+json.dumps(probe)
                base=old['learned'][name]['model']
            else:
                fields=('lo_day','hi_day')
                edges=('2068-02-28','2068-03-01')
                days=[edges[0],iso(edges[0],1),edges[1]]
                records=[dict(date=d,id=f'M{8+i*7}') for i,d in enumerate(days)]
                result=execute(records,contract,*edges)
                returned=[r['date'] for r in result]
                probe=dict(api='agenda_window',known_records=[dict(stamp=r['date'],uid=r['id']) for r in records],
                           request=dict(zip(fields,edges)),returned_records=[dict(stamp=r['date'],uid=r['id']) for r in result])
                context='Date-window calibration. lo_day is the lower date and hi_day the upper date; inclusion is undocumented. '+json.dumps(probe)
                base=direct(agent,context,fields)
            facts=[read_fact(agent,context,d) for d in edges]
            actual=[d in returned for d in edges]
            assert tuple(actual)==contract
            predicted=[f['predicted'] for f in facts]
            explicit=context+f'\nVerified facts about the observed probe: lower endpoint present = {actual[0]}; upper endpoint present = {actual[1]}.'
            privileged=direct(agent,explicit,fields)
            def convert(bits):
                return [0 if bits[0] else -1,0 if bits[1] else 1]
            worlds[name]=dict(probe=probe,actual=actual,facts=facts,direct=base,explicit=privileged,
                              mappings=dict(direct=base['adapter'],fact_then_code=convert(predicted),
                                            given_facts_then_model=privileged['adapter'],membership_then_code=convert(actual)))
        manifests[view]=worlds
    write('frozen.json',manifests)
    frozen=read(OUT/'frozen.json')
    results=[]; totals={}
    for view,worlds in frozen.items():
        if view=='archived':
            days=TEST_DATES; records=read(PREV/'holdout_fixture.json')
        else:
            days=['2072-02-29','2073-01-01','2073-03-01','2073-04-30','2073-06-30','2073-08-31',
                  '2073-10-01','2073-12-31','2074-02-28','2074-05-12','2074-07-13','2074-09-14']
            counts={iso(d,j):(1+i%3 if j==0 else 1) for i,d in enumerate(days) for j in (-1,0,1)}
            for idx,delta in ((8,0),(9,1),(10,-1),(11,-1),(11,1)):
                counts[iso(days[idx],delta)]=0
            records=calendar(counts)
        write(view+'_fixture.json',records)
        summary={}
        for name,case in worlds.items():
            truth=WORLDS[name]
            for arm,op in case['mappings'].items():
                group=summary.setdefault(arm,dict(mappings=0,dates=0))
                group['mappings']+=op==[0 if truth[0] else -1,0 if truth[1] else 1]
                for day in days:
                    args=[iso(day,x) for x in op]
                    got=execute(records,truth,*args); expected=[r for r in records if r['date']==day]
                    group['dates']+=got==expected
                    results.append(dict(view=view,world=name,arm=arm,day=day,args=args,got=got,expected=expected,correct=got==expected))
        totals[view]=summary
    write('deployment.json',results)
    write('summary.json',dict(totals=totals,forward_calls=agent.calls,updates=0,new_probe_calls=4))
    print(totals,flush=True)


if __name__=='__main__':
    main()
