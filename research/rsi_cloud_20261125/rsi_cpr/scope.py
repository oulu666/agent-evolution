"""Scope-uncertainty repair: no single guessed scope is allowed to veto a candidate."""
import argparse,csv,itertools,json
from collections import defaultdict
from pathlib import Path
import numpy as np
from sklearn.tree import DecisionTreeClassifier
from pilot import A,N,F,KINDS,T,W,ANCHOR,World,pick,project
MODES=('fixed_scope','static_cpr','cart','scope_map','ensemble_no_bonus','scoper')
MAX=20
CASES=KINDS+('multiple_missing',)
FEAT=np.stack([(A[:,j]==i).astype(int) for j in range(N) for i in range(3)],axis=1)
ALL_VARS=set(range(N)); ALPHA=.45

def scope_models(scope):
    return [[(base+ext,sum(A[:,p]*3**i for i,p in enumerate(base+ext)),len(ext))
             for k in range(min(2,N-len(base))+1)
             for ext in itertools.combinations(sorted(ALL_VARS-set(base)),k)]
            for base in scope]

def choice(mode,h,models,rng,P):
    if mode in ('fixed_scope','static_cpr'):
        return pick('scope_optimistic' if mode=='fixed_scope' else 'cpr',h,None,rng,P,None)
    ids=np.array([i for i in range(len(A)) if i not in h]); ii=np.array(list(h))
    y=np.stack(list(h.values())); penalty=T[ids]*1e-4
    means=(y.sum(0)+1)/(len(ii)+2); ps=np.zeros((len(ids),N)); all_records=[]
    for j in range(N):
        own=A[ii,j]; prior=np.array([(1+y[own==k,j].sum())/(2+sum(own==k)) for k in range(3)])[A[ids,j]]
        if mode=='cart':
            obj=DecisionTreeClassifier(max_depth=4,random_state=0).fit(FEAT[ii],y[:,j]); dist=obj.predict_proba(FEAT[ids])
            pp=dist[:,list(obj.classes_).index(1)] if 1 in obj.classes_ else np.zeros(len(ids))
            ps[:,j]=.8*pp+.2*prior;continue
        records=[]
        for scope,proj,extra in models[j]:
            v=proj[ii]
            bins=np.unique(v)
            counts=np.bincount(v,weights=y[:,j],minlength=proj.max()+1)
            obs=np.bincount(v,minlength=proj.max()+1)
            if np.any((counts[bins]>0)&(counts[bins]<obs[bins])):continue
            seen=obs[proj[ids]]>0
            known=counts[proj[ids]]>0
            weight=extra*np.log(.40)-len(bins)*np.log(2)
            pu=np.where(seen,known,prior)
            records.append((weight,pu,seen,proj[ids]))
        if not records:
            ps[:,j]=prior; all_records.append([]); continue
        if mode=='scope_map': records=[max(records,key=lambda v:v[0])]
        w=np.array([p[0] for p in records]);w=np.exp(w-w.max());w/=w.sum()
        for q,p in zip(w,records):ps[:,j]+=q*p[1]
        all_records.append(list(zip(w,records)))
    pr=ps.prod(axis=1); act=pr.copy()
    if mode=='scoper':
        plausible=pr>0
        if plausible.any():
            for j,records in enumerate(all_records):
                for w,(_,p,seen,cells) in records:
                    mask=(~seen)&plausible
                    if not mask.any():continue
                    other=pr[mask]/np.maximum(ps[mask,j],1e-12)
                    tot=np.bincount(cells[mask],weights=other,minlength=max(cells)+1)
                    act[mask]+=ALPHA*w*(1-p[mask])*tot[cells[mask]]/sum(plausible)
    if np.max(pr)==0:return int(ids[np.argmax(ps.sum(1)-penalty)])
    return int(ids[np.argmax(act-penalty)])

def create(f,seed,case):
    w=World(f,seed,case if case!='multiple_missing' else 'missing_edge')
    if case=='multiple_missing':
        g=np.random.default_rng(seed+1)
        for j in [i for i in g.permutation(N) if w.scope[i]==w.real[i]][:2]:
            p=next(x for x in g.permutation(N) if x not in w.real[j])
            w.real[j]+= (int(p),)
            tab=np.tile(w.lut[j],3)
            size=len(w.lut[j])
            # Preserve previously feasible assignments as well as create a drift.
            tab[size:2*size]=np.roll(w.lut[j],1)
            w.lut[j]=tab
    return w

def run(path,n,offset):
    out=Path(path);out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for fi,f in enumerate(F):
        for ci,case in enumerate(CASES):
            for s in range(n):
                seed=offset+fi*100000+ci*10000+s
                env=create(f,seed,case); M=scope_models(env.scope); P=project(env.scope)
                for mode in MODES:
                    h={}; win=0; rng=np.random.default_rng(seed)
                    for q in range(MAX):
                        a=int(W[q]) if q<ANCHOR else choice(mode,h,M,rng,P)
                        y=env.check(a);h[a]=y
                        if y.all(): win=q+1;break
                    rows.append(dict(format=f,kind=case,seed=seed,method=mode,found=win,calls=len(h),
                        indices=list(h),verdicts=[''.join(map(str,x)) for x in h.values()]))
    with (out/'traces.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    acc=defaultdict(list)
    for r in rows:
        for g in ('all',r['format'],r['kind']):acc[g,r['method']].append(r)
    d={}
    for (g,m),rr in acc.items():
        d.setdefault(g,{})[m]={'n':len(rr),'calls':sum(x['calls'] for x in rr),**{f'at{k}':sum(0<r['found']<=k for r in rr) for k in (13,16,20)}}
    (out/'summary.json').write_text(json.dumps(d,indent=2)+'\n')
    print(d['all'])
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--n',type=int,default=12);p.add_argument('--offset',type=int,required=True);r=p.parse_args();run(r.out,r.n,r.offset)
