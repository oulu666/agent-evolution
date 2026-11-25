"""Post-pilot two-query lower/upper bound check; no frozen source is changed."""
import argparse,itertools,json
from pandas_gate import X,H,batch,key,ACT,separate_gold,xrow,second

def run(release):
    rows=[xrow(b,i) for b in X for i in range(4)]
    old,new=[batch(k,release if k=='new' else None,rows) for k in ('old','new')]
    def observe(q):
        row=xrow(q)
        vals=[i for i,a in enumerate(ACT) if new[(*row,a)]['after']==separate_gold(row)]
        assert len(vals)==1
        return vals[0]
    assert observe((1,1,1,1))==1
    assert all(any(x[i]!=x[j] for x in X) for i,j in itertools.combinations(H,2))
    one_probe_full_guarantee=max(min(int(len(b)==1) for b in ([i for i in H if p[i]==z] for z in set(p))) for p in X)
    assert one_probe_full_guarantee==0
    ans=0
    for order in itertools.permutations(H):
        q=second(order,'decision');y=observe(q)
        remain=[i for i in H if q[i]==y];assert len(remain)==2
        d=min(p for p in X if p[remain[0]]!=p[remain[1]])
        z=observe(d);hh=[i for i in remain if d[i]==z];assert len(hh)==1
        for row in rows:
            a=ACT[key(row)[hh[0]]]
            ans+=all(b[(*row,a)]['after']==separate_gold(row) for b in (old,new))
    print(json.dumps({'one_probe_full_guarantee':False,'two_added_probes_correct_both':ans,
                      'evaluations':len(rows)*24, 'logical_action_runs_from_first_per_order':6}))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--new',required=True);run(a.parse_args().new)
