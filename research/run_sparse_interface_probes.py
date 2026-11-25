"""Matched two-call active identification in an exhaustive sparse calendar bank."""
import json
from collections import Counter, defaultdict
from itertools import product

from run_interface_boundaries import WORLDS, OPTIONS, iso, calendar, execute, predicted_dates
from run_interface_fact_readout import vote
from run_rsi_operator_memory import ROOT, FrozenAgent

OUT=ROOT/'runs_sparse_interface_probes_20261123'
WINDOWS=[('2076-02-28','2076-03-01'),('2077-03-30','2077-04-01'),('2077-12-30','2078-01-01')]
MASKS=('none','left','right','both')


def save(name,obj):
    path=OUT/name
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2))
    tmp.replace(path)


def bank(layout):
    counts={}
    for (start,end),mask in zip(WINDOWS,layout):
        counts[iso(start,1)]=1
        counts[start]=int(mask in ('left','both'))
        counts[end]=int(mask in ('right','both'))
    return calendar(counts)


def signature(known,i,h):
    return tuple(predicted_dates(*WINDOWS[i],h,known))


def information(known,i,remaining):
    buckets=Counter(signature(known,i,h) for h in remaining)
    # Equal priors: minimizing this sum minimizes expected posterior set size.
    return sum(n*n for n in buckets.values())


def ask_window(agent,known,seen,remaining):
    evidence=dict(first_query=WINDOWS[0],returned_dates=seen,
                  candidate_adapters=list(remaining),known_calendar_dates=known)
    context=('A query may include or exclude its first and last date. Candidate adapters are offsets for requesting one day. '
             'You may make one more query. Choose the window whose possible returned events best distinguish the remaining adapters. '
             f'Evidence: {json.dumps(evidence)}. ')
    ballots=[]
    for order in [(1,2),(2,1)]:
        text=context+f'A = {WINDOWS[order[0]]}; B = {WINDOWS[order[1]]}. Answer one letter.'
        scores=vote(agent,text,'AB')
        ballots.append(dict(order=order,scores=scores,margin_for_window1=(scores[0]-scores[1])*(1 if order[0]==1 else -1)))
    return (1 if sum(v['margin_for_window1'] for v in ballots)>=0 else 2),ballots


def main():
    OUT.mkdir(exist_ok=True)
    if (OUT/'summary.json').exists():
        print((OUT/'summary.json').read_text());return
    save('protocol.json',dict(windows=WINDOWS,masks=MASKS,design='full factorial 4^3 schedules crossed with four contracts',
         access='complete known event dates in calibration sandbox; no hidden contract, model receives exact same surviving hypotheses as rule',
         budget='shared first window; if unique stop, otherwise one additional call for two-call policies; if ambiguous abstain',
         arms=['schema_same_day','one_probe','fixed_second','occupancy_plan','information_gain','qwen_window','known_contract'],
         model='P11 seed 08 frozen; compare both menu orders and average signed logits',
         primary='correct unique mappings / all; wrong acceptance; unresolved; calls',
         evaluation='six independent nonempty target dates with neighbors, exact returned events; abstention yields no service'))
    agent=FrozenAgent()
    rows=[]; model_log=[]
    checkdays=['2080-02-29','2081-01-01','2081-03-01','2081-06-30','2081-08-31','2081-12-31']
    dep=calendar({iso(day,off):1+int(off==0) for day in checkdays for off in (-1,0,1)})
    for layout in product(MASKS,repeat=3):
        data=bank(layout);known=[r['date'] for r in data]
        def invoke(i,contract):
            return tuple(r['date'] for r in execute(data,contract,*WINDOWS[i]))
        # Preplanned without API feedback: cover endpoint types missing in the first window.
        missing=set(('left','right'))-set(x for x,d in zip(('left','right'),WINDOWS[0]) if d in known)
        preplanned=max((1,2),key=lambda i:sum(d in known and x in missing for x,d in zip(('left','right'),WINDOWS[i])))
        for name,contract in WORLDS.items():
            truth=(0 if contract[0] else -1,0 if contract[1] else 1)
            seen=invoke(0,contract)
            rem=[h for h in OPTIONS if signature(known,0,h)==seen]
            assert truth in rem
            picks={'fixed_second':1,'occupancy_plan':preplanned,
                   'information_gain':min((1,2),key=lambda i:information(known,i,rem))}
            if len(rem)>1:
                pick,ballots=ask_window(agent,known,seen,rem)
                model_log.append(dict(layout=layout,world=name,seen=seen,remaining=rem,choice=pick,ballots=ballots))
                picks['qwen_window']=pick
            else:
                picks['qwen_window']=1
            for arm in ['schema_same_day','known_contract','one_probe',*picks]:
                second=None; reply=None
                if arm in ('schema_same_day','known_contract'):
                    candidates=[(0,0) if arm=='schema_same_day' else truth]; calls=0
                else:
                    candidates=rem;calls=1
                    if arm in picks and len(rem)>1:
                        second=picks[arm];reply=invoke(second,contract);calls+=1
                        candidates=[h for h in rem if signature(known,second,h)==reply]
                selected=candidates[0] if len(candidates)==1 else None
                good=0
                if selected is not None:
                    for day in checkdays:
                        got=execute(dep,contract,iso(day,selected[0]),iso(day,selected[1]))
                        good+=got==[r for r in dep if r['date']==day]
                rows.append(dict(layout=layout,world=name,arm=arm,first_reply=seen if calls else None,
                    first_remaining=rem if calls else None,second=second,second_reply=reply,remaining=candidates,
                    calls=calls,decision=selected,correct=selected==truth,wrong=selected is not None and selected!=truth,deploy_ok=good))
    save('decisions.json',rows);save('model_ballots.json',model_log)
    summary={}
    for arm in sorted({r['arm'] for r in rows}):
        group=[r for r in rows if r['arm']==arm]
        summary[arm]=dict(episodes=len(group),correct=sum(r['correct'] for r in group),
            wrong=sum(r['wrong'] for r in group),abstain=sum(r['decision'] is None for r in group),
            calls=sum(r['calls'] for r in group),deploy_ok=sum(r['deploy_ok'] for r in group))
    save('summary.json',dict(results=summary,model_forwards=agent.calls,weight_updates=0))
    print(summary,flush=True)


if __name__=='__main__':
    main()
