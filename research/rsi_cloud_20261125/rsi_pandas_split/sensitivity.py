"""Post-pilot equal-information comparison and feature-order sensitivity."""
from itertools import permutations
import argparse,json
from pathlib import Path
from pilot import data,batch,masks,ACT,key,separate_gold

def choose(labeled,order,standard,src_cases):
    def pick(x,j):
        return 0 if j<0 else int(key(x)[j])
    all_h=[]
    for j in (-1,*order):
     for a in (0,1):
      for b in ((a,) if j<0 else (0,1)):
       run=lambda x,j=j,a=a,b=b:(a,b)[pick(x,j)]
       if not all(run(x) in y for x,y in labeled.items()):continue
       complexity=(j>=0,(-1 if j<0 else order.index(j)),a,b)
       if standard:
        # Ordinary stability regularizer: edit only where the old policy
        # disagrees after fitting the newly labeled histories.
        cost=(sum(run(x)!=0 for x in src_cases),*complexity)
       else:
        cost=((a!=0)+(b!=0),*complexity)
       all_h.append((cost,run))
    return min(all_h,key=lambda x:x[0])[1]

def run(path):
    t=data(False);h=data(True)
    truth={}
    data_runtime={x:batch(x,path if x=='new' else None,t+h) for x in ('old','new')}
    y=masks(t,data_runtime['new'])
    for n in (1,2):
        for anchor in ('draft','attached'):
            sub=(t if anchor=='draft' else list(reversed(t)))[:n]
            ex={x:y[x] for x in sub}
            rr={'local':[],'minimal_change':[]}
            for order in permutations(range(4)):
                for mode in rr:
                    pol=choose(ex,order,mode=='minimal_change',h)
                    counts=[sum(data_runtime[k][(*x,ACT[pol(x)])]['after']==separate_gold(x) for x in h) for k in ('old','new')]
                    rr[mode].append(tuple(counts))
            from collections import Counter
            print(n,anchor,{m:dict(sorted(Counter(v).items())) for m,v in rr.items()})
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--new',required=True);run(p.parse_args().new)
