"""Three-call comparison. Policy functions receive only public inputs and observed replies."""
import json
import time
from collections import Counter
from itertools import permutations,product
from risk_worlds import OUT,endpoint,layouts,pool,run,parse,save,family,focused
from run_semantic_extensions import ranked
from semantic_extension_bank import NAMES,STATES

SMALL,WIDE,SLICES=pool()
ARMS=('top2','diverse2','hybrid','gated','gated_active','risk','program_risk','slice_program_risk',
      'full16','full_composed','full_plus_slice')


def convert(h,alias):
    name,key,val=h[:3]
    fields=NAMES[alias]
    if name=='unique':
        op='uid' if key==fields[0] else 'owner' if key==fields[2] else 'row'
    elif name=='exclude':
        op='drop'+str(STATES[alias].index(val))
    else:
        op=('rank' if key==fields[4] else 'id')+('_up' if val=='asc' else '_down')
    return ('page',op) if h[-1]=='after' else (op,'page')


def unique(seq):
    return list(dict.fromkeys(seq))


class Predictions:
    def __init__(self,rows):
        self.rows=rows
        self.cache={}
        self.phases=Counter()
        self.phase='initial'

    def __call__(self,q,h):
        k=(q,h)
        if k not in self.cache:
            self.cache[k]=run(self.rows[q],h)
            self.phases[self.phase]+=1
        return self.cache[k]


def distance(a,b):
    return abs(len(a)-len(b))+sum(x!=y for x,y in zip(a,b))


def program_pool(raw,obs,alias,P):
    ranks=[convert(h,alias) for h in ranked(dict(records=raw,obs=list(obs),alias=alias))]
    # Residual-directed expansion. Try ordered pairs of the best single-family edits.
    ranks.sort(key=lambda h:distance(P(0,h),obs))
    seeds=unique(next(x for x in h if x!='page') for h in ranks)[:5]
    neighbors=unique(p for a,b in permutations(seeds,2) if family((a,))!=family((b,))
                     for p in ((a,b,'page'),(a,'page',b),('page',a,b)))
    candidates=unique([*ranks,*neighbors[:40]])
    return sorted(candidates,key=lambda h:distance(P(0,h),obs))


def choose_gate(top,extras,obs,P,qs):
    first,second=top
    active=[h for h in top if P(0,h)==obs]
    for h in extras:
        if h in top or P(0,h)!=obs:
            continue
        keep=first if first in active or second not in active else second
        gain=loss=0
        for q in qs:
            old={P(q,v) for v in active}
            new={P(q,v) for v in (keep,h) if P(0,v)==obs}
            gain+=len(new-old)
            loss+=len(old-new)
        if loss==0 and gain>=2:
            return [keep,h],dict(gain=gain,loss=loss)
    return top,None


def split_score(q,candidates,P):
    return -sum(n*n for n in Counter(P(q,h) for h in candidates).values())


def simulate(arm,alias,raw,rows,bank,call,proposals):
    clock=time.process_time_ns()
    obs=call(rows)
    P=Predictions([rows,*bank])
    gate=None
    qset=list(range(1,len(bank)+1))
    if arm.startswith('full'):
        candidates={'full16':SMALL,'full_composed':WIDE,'full_plus_slice':WIDE+SLICES}[arm]
    else:
        ordered=program_pool(raw,obs,alias,P)
        top=ordered[:2]
        candidates=top
        if arm=='diverse2':
            candidates=[top[0],next(h for h in ordered if family(h)!=family(top[0]))]
        elif arm=='hybrid':
            candidates=[top[0],next((h for h in proposals if h!=top[0]),top[1])]
        elif arm in ('gated','gated_active','risk','program_risk','slice_program_risk'):
            P.phase='gate'
            extras=ordered[2:4] if arm=='program_risk' else proposals
            if arm=='slice_program_risk':
                extras=sorted(SLICES,key=lambda h:distance(P(0,h),obs))[:2]
            candidates,gate=choose_gate(top,extras,obs,P,qset)
    P.phase='verify'
    rem=[h for h in candidates if P(0,h)==obs]
    q2=max(qset[:8],key=lambda q:split_score(q,[('page',),*rem],P))
    y2=call(bank[q2-1])
    rem=[h for h in rem if P(q2,h)==y2]
    remaining=[q for q in qset if q!=q2]
    shadows=[]
    if arm in ('gated_active','risk','program_risk','slice_program_risk','wide_shadow'):
        P.phase='challengers'
        shadow_bank=WIDE if arm=='wide_shadow' else SMALL
        shadows=[h for h in shadow_bank if h not in rem and P(0,h)==obs and P(q2,h)==y2]
    P.phase='probe'
    if shadows and rem:
        def score(q):
            return (sum(P(q,a)!=P(q,b) for a in rem for b in shadows),split_score(q,rem,P))
    else:
        def score(q):
            return split_score(q,[('page',),*rem],P)
    q3=max(remaining,key=score)
    y3=call(bank[q3-1])
    live=[h for h in rem if P(q3,h)==y3]
    # Equivalent candidates on the whole public probe bank count as one behavioural prediction.
    def distinguish(h,leader):
        return any(P(q,h)!=P(q,leader) for q in qset)
    leader=live[0] if live else None
    if leader and any(distinguish(h,leader) for h in live[1:]):
        leader=None
    veto=False
    if leader and arm in ('risk','program_risk','slice_program_risk','wide_shadow'):
        veto=any(P(q3,h)==y3 and distinguish(h,leader) for h in shadows)
        if veto:
            leader=None
    ms=(time.process_time_ns()-clock)/1e6
    return dict(candidates=candidates,decision=leader,calls=3,q2=q2,q3=q3,obs=obs,y2=y2,y3=y3,
                live=live,shadows=len(shadows),veto=veto,gate=gate,
                evaluations=dict(P.phases),cpu_ms=ms)


def historical():
    old=OUT.parent/'runs_semantic_repair_20261123'
    case=next(x for x in json.loads((old/'B_fixtures.json').read_text()) if x['id']=='final-1-3')
    r=next(x for x in json.loads((old/'grammar_06.json').read_text()) if x['id']==case['id'] and x['arm']=='hybrid')
    from semantic_extension_bank import target
    from risk_worlds import normalize
    fields=NAMES[1]
    rows=[dict(zip(fields,v)) for v in [('id1',1,'Alice','active',0),('id2',2,'Alice','active',1)]]
    actual=target(rows,case['truth'],1)
    predicted=run(normalize(rows,1),convert(r['deployed'],1))
    return dict(original_case=case['id'],original_two_proposals=r['proposals'],actual=actual,
                claimed=predicted,fixture=rows,falsified=list(predicted)!=actual)


def main():
    proposals=json.loads((OUT/'case_proposals.json').read_text())
    ledger=[]
    for idx,alias,raw,rows,bank,held in layouts():
        # Test equivalence offline. No signature, category or case ID enters the policy.
        stress=held+[focused(700000+idx*30+j,j%6) for j in range(12)]
        signatures={}
        def sig(h):
            if h not in signatures:
                signatures[h]=tuple(run(x,h) for x in stress)
            return signatures[h]
        for kind,i in product(('simple','compound','outside'),range(3)):
            key=f'{idx}-{kind}-{i}'
            v=proposals[key]
            suggestions=unique(h for s in v['free']['raw']+v['beam']['raw'] if (h:=parse(s)))[:2]
            def call(x):
                return endpoint(x,kind,i)
            truth=tuple(call(x) for x in stress)
            for arm in ARMS:
                result=simulate(arm,alias,raw,rows,bank,call,suggestions)
                recall=any(sig(h)==truth for h in result['candidates'])
                chosen=result['decision']
                ok=chosen is not None and sig(chosen)==truth
                used=arm in ('hybrid','gated','gated_active','risk')
                ledger.append(dict(id=key,layout=idx,kind=kind,variant=i,arm=arm,correct=ok,
                    recall=recall,wrong=chosen is not None and not ok,unknown=chosen is None,
                    tokens=sum(v[m]['output_tokens'] for m in ('beam','free')) if used else 0,
                    input_tokens=sum(v[m]['input_tokens'] for m in ('beam','free')) if used else 0,
                    model_seconds=sum(v[m]['seconds'] for m in ('beam','free')) if used else 0,
                    free_hit=bool(parse(v['free']['raw'][0]) and sig(parse(v['free']['raw'][0]))==truth),
                    model_hit=any(sig(h)==truth for h in suggestions),suggestions=suggestions,**result))
    # Candidates for exhaustive methods can be regenerated from the common schema.
    for r in ledger:
        if r['arm'].startswith('full'):
            r['candidate_count']=len(r.pop('candidates'))
    save('decisions.json',ledger)
    save('historical.json',historical())
    print(len(ledger),'evaluations',flush=True)


if __name__=='__main__':
    main()
