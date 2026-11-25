"""Frozen-TinyAgent experiment on observationally distinguishable calendar APIs."""
from datetime import date, timedelta
from pathlib import Path
from collections import Counter
import json

from run_rsi_operator_memory import FrozenAgent, ROOT, ADAPTER
import torch

OUT = ROOT/'runs_rsi_interface_20261123'
DAY = timedelta(days=1)
OPTIONS = ((0,0),(0,1),(-1,0),(-1,1))
# Endpoint implementations are kept separate from the selector and its inputs.
WORLDS = {'v01':(True,False),'v02':(False,False),'v03':(True,True),'v04':(False,True)}
SCHEMA = {'name':'calendar_range','arguments':{'start':'ISO date','end':'ISO date'},
          'description':'Return calendar events between start and end, ordered by date and id.'}
TEST_DATES = ['2043-12-31','2044-02-29','2044-03-01','2044-04-30','2044-05-15','2044-06-16',
              '2045-01-01','2045-02-28','2045-04-11','2045-05-07','2045-06-25','2045-08-09']


def save(name,obj):
    path=OUT/name
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2))
    tmp.replace(path)


def iso(day,offset=0):
    return (date.fromisoformat(day)+offset*DAY).isoformat()


def calendar(counts):
    return [dict(date=d,id=f'evt-{d}-{i}') for d in sorted(counts) for i in range(counts[d])]


def execute(records,contract,start,end):
    date.fromisoformat(start)
    date.fromisoformat(end)
    if start>end:
        raise ValueError('inverted bounds')
    left_closed,right_closed=contract
    return [r for r in records if (r['date']>start or left_closed and r['date']==start)
            and (r['date']<end or right_closed and r['date']==end)]


def predicted_dates(left,right,offsets,days):
    # Invert the proposed day-to-window encoding to predict a probe result.
    low=iso(left,-offsets[0])
    high=iso(right,-offsets[1])
    return [d for d in days if low<=d<=high]


def probes(contract):
    known=calendar({'2040-04-10':1,'2040-04-11':1,'2040-04-12':1})
    days=[r['date'] for r in known]
    left,right=days[0],days[-1]
    result=execute(known,contract,left,right)
    seen=[r['date'] for r in result]
    consistent=[op for op in OPTIONS if predicted_dates(left,right,op,days)==seen]
    assert len(consistent)==1
    return dict(known_event_dates=days,start=left,end=right,returned_dates=seen),consistent[0]


@torch.inference_mode()
def select(agent,menu,observation):
    choices='\n'.join(f'{label}: start = D{a:+d} days, end = D{b:+d} days'
                       for label,(a,b) in zip('ABCD',menu))
    prompt=(f'API schema: {json.dumps(SCHEMA)}\n'
            'We want all events on one day D, excluding earlier and later days. '
            'Choose the adapter that calls this API with the correct two dates. '
            'Boundary inclusion is undocumented. '
            f'Calibration (one event per known date): {json.dumps(observation)}\n'
            f'{choices}\nWhich adapter should be reused on future days? Answer one letter.')
    enc=agent.encode([dict(role='user',content=prompt)])
    logits=agent.model(**enc,use_cache=False).logits[0,-1].float()
    ids=[agent.tok.encode(k,add_special_tokens=False) for k in 'ABCD']
    assert all(len(i)==1 for i in ids)
    scores=logits[[i[0] for i in ids]].tolist()
    index=scores.index(max(scores))
    return dict(menu=menu,label='ABCD'[index],adapter=menu[index],logits=scores)


def decide(agent,observations):
    runs=[select(agent,OPTIONS[i:]+OPTIONS[:i],observations) for i in range(4)]
    counts=Counter(tuple(r['adapter']) for r in runs)
    # In a vote tie use the first presentation's highest-ranked tied option.
    ranking=sorted(range(4),key=lambda j:-runs[0]['logits'][j])
    winner=max((OPTIONS[j] for j in ranking),key=lambda k:counts[k])
    return dict(adapter=winner,votes=runs)


def main():
    OUT.mkdir(exist_ok=True)
    if (OUT/'summary.json').exists():
        print((OUT/'summary.json').read_text())
        return
    save('protocol.json',dict(schema=SCHEMA,dates=TEST_DATES,options=OPTIONS,
         model=str(ADAPTER.relative_to(ROOT)),decode='greedy one-token, four cyclic orders, majority vote; ties by first menu logit',
         primary='exact day adapter, by interface',secondary='exact returned event sequence, by date',
         arms=['schema_default','model_prior','model_evidence','constraint_solver','oracle'],
         primary_unit='4 synthetic boundary contracts, same schema, one read-only probe per contract'))
    agent=FrozenAgent()
    prior=decide(agent,None)
    learned={}
    for name,contract in WORLDS.items():
        observation,solver=probes(contract)
        chosen=decide(agent,observation)
        learned[name]=dict(observation=observation,solver=solver,model=chosen)
        print('Frozen',name,chosen['adapter'],flush=True)
    save('frozen.json',dict(prior=prior,learned=learned))
    binding=json.loads((OUT/'frozen.json').read_text())
    counts={}
    for i,d in enumerate(TEST_DATES):
        for delta,n in [(-1,1),(0,1+i%3),(1,1)]:
            counts.setdefault(iso(d,delta),n)
    # Include sparse and empty targets where an incorrect mapping can look right.
    counts[TEST_DATES[8]]=0
    counts[iso(TEST_DATES[9],1)]=0
    counts[iso(TEST_DATES[10],-1)]=0
    counts[iso(TEST_DATES[11],1)]=counts[iso(TEST_DATES[11],-1)]=0
    holdout=calendar(counts)
    save('holdout_fixture.json',holdout)
    trials=[]
    summary={}
    for name,(left,right) in WORLDS.items():
        record=binding['learned'][name]
        oracle=(0 if left else -1,0 if right else 1)
        arms=dict(schema_default=(0,0),model_prior=binding['prior']['adapter'],
                  model_evidence=record['model']['adapter'],constraint_solver=record['solver'],oracle=oracle)
        table={}
        for arm,op in arms.items():
            correct=0
            for d in TEST_DATES:
                call=dict(start=iso(d,op[0]),end=iso(d,op[1]))
                got=execute(holdout,(left,right),**call)
                expected=[r for r in holdout if r['date']==d]
                ok=got==expected
                correct+=ok
                trials.append(dict(interface=name,arm=arm,day=d,call=call,returned=got,expected=expected,correct=ok))
            table[arm]=dict(mapping=list(op),mapping_correct=tuple(op)==oracle,correct_dates=correct)
        summary[name]=table
    save('trials.json',trials)
    total={arm:dict(mappings=sum(v[arm]['mapping_correct'] for v in summary.values()),
                    days=sum(v[arm]['correct_dates'] for v in summary.values())) for arm in next(iter(summary.values()))}
    save('summary.json',dict(totals=total,interfaces=summary,probe_calls=4,selector_forwards=agent.calls,parameter_updates=0))
    print(total,flush=True)


if __name__=='__main__':
    main()
