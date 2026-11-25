"""Second-probe regime on the real pandas copy-on-write case; requires its sibling."""
import argparse,itertools,json,math,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'rsi_pandas_split'))
from pilot import batch,ACT,separate_gold,key

X=list(itertools.product((0,1),repeat=4)); first=(1,1,1,1); H=tuple(range(4))
def xrow(b,repeat=0):
    return (b[0],b[1],3+b[2],20+2*repeat+(1-b[3]))
def cover(hs):
    return sum(len({p[axis] for axis in hs})==1 for p in X)
def second(order,m):
    if m=='expert_contrast': return (0,1,1,1)
    if m=='one_factor':
        return tuple(0 if i==order[0] else 1 for i in H)
    def rank(p):
        b=[[i for i in H if p[i]==c] for c in (0,1)]
        b=[x for x in b if x];s=[len(x)/len(H) for x in b]
        if m=='entropy': value=(-sum(w*math.log2(w) for w in s),)
        else:
            avg=sum(w*cover(c) for w,c in zip(s,b))
            value=(min(map(cover,b)),avg) if m=='decision' else (avg,)
        return value,tuple(p[i] for i in order)
    return max((p for p in X if p!=first),key=rank)
def main(release):
    rows=[xrow(p,i) for p in X for i in range(4)]
    old,new=[batch(k,release if k=='new' else None,rows) for k in ('old','new')]
    def allowed(b):
        x=xrow(b)
        out=[i for i,a in enumerate(ACT) if new[(*x,a)]['after']==separate_gold(x)]
        assert len(out)==1
        return out[0]
    assert len([i for i in H if first[i]==allowed(first)])==4
    result={}
    for m in ('expert_contrast','one_factor','entropy','bayes','decision','direct_metadata'):
        good=wrong=defer=0; used=[]
        for order in itertools.permutations(H):
            if m!='direct_metadata':
                p=second(order,m);y=allowed(p);hyp=[i for i in H if p[i]==y];used.append(len(hyp))
            for x in rows:
                b=key(x)
                actions={b[i] for i in hyp} if m!='direct_metadata' else {int(new[(*x,ACT[0])]['shared'])}
                if len(actions)!=1:defer+=1;continue
                a=ACT[actions.pop()];g=separate_gold(x)
                ok=all(d[(*x,a)]['after']==g for d in (old,new))
                good+=ok;wrong+=not ok
        result[m]={'correct_both':good,'wrong':wrong,'defer':defer,'permutation_count':24,
                   'planned_probe_evals_per_permutation':0 if m=='direct_metadata' else 4,
                   'metadata_probes':len(rows)*24 if m=='direct_metadata' else 0}
    print(json.dumps(result,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--new',required=True);main(p.parse_args().new)
