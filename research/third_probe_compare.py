"""Only the third request changes. Mechanism labels are read after every policy has selected."""
import datetime as dt
import json
import random
import time
from collections import Counter
from third_probe_inputs import OUT,DEV,TEST,RULES,public,run,evaluate,make,parse_request,save


def one_edit(h,r):
    if len(h)==len(r):
        return sum(x!=y for x,y in zip(h,r))==1 or any(
            r==h[:j]+(h[j+1],h[j])+h[j+2:] for j in range(len(h)-1))
    a,b=sorted((h,r),key=len)
    return len(b)==len(a)+1 and any(a==b[:i]+b[i+1:] for i in range(len(b)))


def killed(q,h,mutants):
    expected=run(q['rows'],h)
    return sum(run(q['rows'],r)!=expected for r in mutants)


def mixed_request(layout,number,rng):
    date=dt.date(2038,1,1)+dt.timedelta(days=rng.randrange(4*366))
    return make(date.isoformat(),rng.randrange(32),rng.randint(1,24),rng.randint(1,24),
                rng.randint(1,24),1800000+number+layout*100000,'cpu'+str(number))


def select(layout,perm,h,history,bank,model):
    expected=[run(x['rows'],h) for x in history]
    live=[r for r in RULES if all(run(x['rows'],r)==y for x,y in zip(history,expected))]
    mutants=[r for r in live if one_edit(h,r)]
    if not mutants:
        mutants=[r for r in RULES if one_edit(h,r)]
    def disagreement(q):
        grouped=Counter(run(q['rows'],r) for r in live)
        return -sum(v*v for v in grouped.values())
    def timed(fn):
        start=time.perf_counter()
        choice=fn()
        return choice,time.perf_counter()-start
    rng=random.Random(3351700+layout)
    # Random order is seeded per layout, shared by deterministic methods for score ties.
    order=list(range(len(bank)))
    rng.shuffle(order)
    rand,t0=timed(lambda:bank[order[0]])
    disc,t1=timed(lambda:bank[max(order,key=lambda i:disagreement(bank[i]))])
    def best_mutant():
        values={i:killed(bank[i],h,mutants) for i in order}
        best=max(values.values())
        return bank[max((i for i in order if values[i]==best),key=lambda i:disagreement(bank[i]))]
    mut,t2=timed(best_mutant)
    proposal,obj=parse_request(model['raw'],layout,perm,bank)
    hybrid=proposal or mut
    picks=dict(random=rand,disagreement=disc,mutation=mut,tiny_program=hybrid)
    times=dict(random=t0,disagreement=t1,mutation=t2,tiny_program=model['batch_share_seconds']+(0 if proposal else t2))
    attempts=0
    # Extra program-only baseline gets at most the amortized time of the hybrid, or the regular mutation run.
    # Read-only requests have already been exhausted; in the writable case explore additional legal inputs.
    bestq=mut
    search_time=t2
    if perm=='build' and t2<times['tiny_program']:
        start=time.perf_counter()
        value=(killed(mut,h,mutants),disagreement(mut))
        limit=times['tiny_program']-t2
        while time.perf_counter()-start<limit:
            q=mixed_request(layout,attempts,rng)
            attempts+=1
            k=killed(q,h,mutants)
            if k>=value[0]:
                score=(k,disagreement(q))
                if score>value:
                    bestq,value=q,score
        search_time+=time.perf_counter()-start
    picks['mutation_time']=bestq
    times['mutation_time']=search_time
    return live,mutants,picks,times,obj,attempts


def main():
    decisions=[];plans=[];frontier=[]
    for layout in range(24):
        h,history,catalog=public(layout)
        for perm in ('read','build'):
            bank=catalog[:12] if perm=='read' else catalog
            while True:
                models={(r['layout'],r['permission']):r for r in json.loads((OUT/'model.json').read_text())}
                if (layout,perm) in models:
                    break
                time.sleep(1)
            model=models[layout,perm]
            live,mu,picks,times,obj,attempts=select(layout,perm,h,history,bank,model)
            # Freeze equivalence check across methods. All authorized public comparison inputs are included.
            equiv={r:all(run(q['rows'],h)==run(q['rows'],r) for q in bank) for r in live}
            plans.append(dict(layout=layout,permission=perm,h=h,first=history,model=model,parsed=obj,
                live=len(live),surviving_neighbors=len(mu),picks=picks,times=times,extra_mutations=attempts))
            for mechanism in ('stable',*DEV,*TEST):
                # Stateful endpoint is evaluated anew with the same two-request prefix in every arm.
                for j,q in enumerate(history):
                    assert evaluate(h,mechanism,q,history[:j])==run(q['rows'],h)
                allowed=[q for q in bank if evaluate(h,mechanism,q,history)!=run(q['rows'],h)]
                # Legal supplementary witnesses for the write permission; this oracle is only for attribution.
                witnesses=[]
                if perm=='build' and not allowed and mechanism!='stable':
                    for i in range(512):
                        rr=random.Random(layout*700+i)
                        day=('2040-02-28','2041-12-31','2040-05-01')[i%3]
                        q=make(day,i%6,rr.randint(3,24),rr.randint(1,5),rr.randint(1,5),i+11233,'audit'+str(i))
                        if evaluate(h,mechanism,q,history)!=run(q['rows'],h):
                            witnesses.append(q['name'])
                            break
                frontier.append(dict(layout=layout,permission=perm,mechanism=mechanism,
                    actual_catalog_witnesses=[q['name'] for q in allowed],extra_witness=witnesses))
                for method,q in picks.items():
                    observed=evaluate(h,mechanism,q,history)
                    predicted=run(q['rows'],h)
                    refuted=observed!=predicted
                    remaining=[r for r in live if run(q['rows'],r)==observed]
                    # Previous full-enumeration consistency/equivalence gate specialized to the nominated H.
                    accepted=not refuted and all(equiv[r] for r in remaining)
                    # Common confidence score within the original gate; no ground truth enters its computation.
                    confidence=1-len(remaining)/len(live)
                    decisions.append(dict(layout=layout,permission=perm,method=method,mechanism=mechanism,
                        split='development' if mechanism in DEV else 'test',third=q['name'],observed=observed,
                        predicted=predicted,refuted=refuted,accepted=accepted,confidence=confidence,
                        initial=len(live),survivors=len(remaining),selection_seconds=times[method],calls=3))
    save('plans.json',plans)
    save('decisions.json',decisions)
    save('reachability.json',frontier)
    print(len(decisions),'actual paired executions',flush=True)


if __name__=='__main__':
    main()
