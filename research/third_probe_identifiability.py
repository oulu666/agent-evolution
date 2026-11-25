"""Exact finite-menu audit of all 32 previously undecided cases."""
import json
from risk_worlds import OUT as PREV, layouts, pool, run, endpoint, focused
from pathlib import Path

OUT=PREV.parent/'runs_third_probe_20261123'
OUT.mkdir(exist_ok=True)


def save(name,obj):
    dst=OUT/name
    tmp=dst.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf8')
    tmp.replace(dst)


def main():
    original=json.loads((PREV/'decisions.json').read_text())
    cases=[r for r in original if r['arm']=='full_plus_slice' and r['unknown']]
    assert len(cases)==32
    _,wide,slices=pool()
    hypotheses=wide+slices
    out=[]
    for idx,_,_,first,bank,held in layouts():
        local=[r for r in cases if r['layout']==idx]
        if not local:
            continue
        qs=[first,*bank]
        signatures=[tuple(run(x,h) for x in qs) for h in hypotheses]
        checks=held+[focused(700000+idx*30+j,j%6) for j in range(12)]
        for r in local:
            true=tuple(endpoint(x,r['kind'],r['variant']) for x in qs)
            y=tuple(endpoint(x,r['kind'],r['variant']) for x in checks)
            candidates=[i for i,s in enumerate(signatures) if s[0]==true[0]]
            # A rival is counted only if a concrete held fixture separates its behaviour.
            rivals=[i for i in candidates if any(run(x,hypotheses[i])!=v for x,v in zip(checks,y))]
            refutable=[{i for i in rivals if signatures[i][q]!=true[q]} for q in range(len(qs))]
            all_rivals=set(rivals)
            def enough(a,b):
                return refutable[a]|refutable[b]==all_rivals
            viable=[(a,b) for a in range(1,9) for b in range(1,len(qs)) if a!=b and enough(a,b)]
            third=next((b for a,b in viable if a==r['q2']),None)
            indist=all_rivals-set.union(*refutable)
            if indist:
                category='permission'
            elif enough(r['q2'],r['q3']):
                category='already_distinguished_on_held'
            elif third is not None:
                category='change_third'
            elif viable:
                category='change_second'
            else:
                category='budget'
            # Reproduce the original verifier separately, using its public-equivalence classes.
            def certified(a,b):
                return all(s==true for i in candidates for s in [signatures[i]] if s[a]==true[a] and s[b]==true[b])
            assert not certified(r['q2'],r['q3'])
            pub=[(a,b) for a in range(1,9) for b in range(1,len(qs)) if a!=b and certified(a,b)]
            out.append(dict(id=r['id'],category=category,rivals=len(rivals),unobservable=len(indist),
                witness_rival=hypotheses[min(indist)] if indist else None,old=[r['q2'],r['q3']],
                third=third,feasible_pair=viable[:1],public_third=next((b for a,b in pub if a==r['q2']),None),
                public_pair=pub[:1]))
    save('prior_32.json',out)
    from collections import Counter
    print(Counter(x['category'] for x in out))


if __name__=='__main__':
    main()
