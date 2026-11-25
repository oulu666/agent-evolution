"""Larger challenge library, and an independent counterfactual pair with a hidden size regime."""
import json
from itertools import product
from risk_worlds import OUT,endpoint,focused,layouts,run,save
from run_risk_verification import simulate


def size_pair(idx,rows,bank):
    seed=4000000+idx*100
    base=sorted(focused(seed,6),key=lambda r:r[1])
    # Deliberately decorrelate ID/owner and include both nonzero states across the prefix.
    first=[(r[0],j,'same' if j<3 else str(j),[0,1,2][j%3],r[4]) for j,r in enumerate(base)]
    tail=[('tail'+str(j),100+j,'tail'+str(j),0,j) for j in range(7)]
    result=[]
    for kind,drift,stretch in product(('id','filter'),(False,True),(False,True)):
        leader=('uid','page') if kind=='id' else ('drop1','page')
        def blackbox(x):
            seq=sorted(x,key=lambda r:r[1])
            switched=drift and len(x)>10
            if kind=='id':
                k=2 if switched else 0
                seq=[r for j,r in enumerate(seq) if all(p[k]!=r[k] for p in seq[:j])]
            else:
                seq=[r for r in seq if r[3]!=(2 if switched else 1)]
            return tuple(r[0] for r in seq[:3])
        probes=[rows,bank[0],first+tail if stretch else first]
        predicted=[run(x,leader) for x in probes]
        actual=[blackbox(x) for x in probes]
        accept=predicted==actual
        assert predicted[2]==run(first,leader)
        result.append(dict(layout=idx,semantics=kind,drift=drift,long_third=stretch,accept=accept,
            correct_adoption=accept and not drift,wrong_adoption=accept and drift,unknown=not accept,
            dimensions=[len(x) for x in probes],predicted=predicted,observed=actual))
    return result


def main():
    original=json.loads((OUT/'decisions.json').read_text())
    base={r['id']:r for r in original if r['arm']=='top2'}
    out=[];pairs=[]
    for idx,alias,raw,rows,bank,held in layouts():
        pairs.extend(size_pair(idx,rows,bank))
        stress=held+[focused(700000+idx*30+j,j%6) for j in range(12)]
        for kind,i in product(('simple','compound','outside'),range(3)):
            def call(x):
                return endpoint(x,kind,i)
            key=f'{idx}-{kind}-{i}'
            # Verify that the baseline stored for the headline comparisons uses this same public bank.
            check=simulate('top2',alias,raw,rows,bank,call,[])
            old=base[key]
            assert (check['q2'],check['q3'],check['decision'])==(old['q2'],old['q3'],tuple(old['decision']) if old['decision'] else None)
            result=simulate('wide_shadow',alias,raw,rows,bank,call,[])
            h=result['decision']
            ok=bool(h and all(run(x,h)==call(x) for x in stress))
            out.append(dict(id=key,layout=idx,kind=kind,correct=ok,wrong=h is not None and not ok,
                            unknown=h is None,**result))
    save('wide_challenges.json',out)
    save('size_pairs.json',pairs)
    print('wide challenge',*[sum(r[k] for r in out) for k in ('correct','wrong','unknown','veto')])


if __name__=='__main__':
    main()
