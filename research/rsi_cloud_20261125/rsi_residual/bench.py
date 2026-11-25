"""Controlled black-box search over editable inputs to a real SQLite report."""
import argparse,itertools,json,sqlite3
from functools import lru_cache
from collections import defaultdict
from pathlib import Path
import numpy as np
D=7; W=3; B=12
X=np.array(list(itertools.product(range(2),repeat=D)),int)
IX={tuple(x):i for i,x in enumerate(X)}
ONES=[IX[tuple(np.eye(D,dtype=int)[j])] for j in range(D)]
H=[0]+ONES
P=list(itertools.combinations(range(D),2))
Q=np.column_stack([X[:,a]*X[:,b] for a,b in P])
SIZE=X.sum(1)
S=[(i,) for i in range(len(P))]+list(itertools.combinations(range(len(P)),2))
MODES=('greedy','single_delta','ridge','support_vote')
CASES=('additive','sparse2','dense','cubic')
PER=24

class Task:
 def __init__(self,seed,kind):
    rng=np.random.default_rng(seed)
    self.base=rng.integers(70,120,W)
    self.u=rng.integers(-6,7,(D,W))
    n={'additive':0,'sparse2':2,'dense':6,'cubic':2}[kind]
    terms=[(tuple([j]),vv) for j,vv in enumerate(self.u)]
    for k in rng.choice(len(P),size=n,replace=False):
       v=rng.integers(-10,11,W);v[0]=int(rng.choice([-9,9]))
       terms.append((P[int(k)],v))
    if kind=='cubic': terms.append((tuple(sorted(map(int,rng.choice(D,size=3,replace=False)))),np.array([13,8,-7])))
    target_mask=rng.integers(0,2,D); index=np.where(target_mask)[0]
    if len(index)<3:target_mask[rng.choice(D,3,replace=False)]=1
    self.truth=tuple(target_mask.tolist())
    self.goal=self.base+sum((v for q,v in terms if all(target_mask[j] for j in q)),np.zeros(W,int))
    self.db=sqlite3.connect(':memory:')
    self.db.execute('CREATE TABLE adjustments(mask INTEGER, a INTEGER, b INTEGER, c INTEGER)')
    self.db.executemany('INSERT INTO adjustments VALUES(?,?,?,?)',[(0,*map(int,self.base))]+[(sum(1<<j for j in q),*map(int,v)) for q,v in terms])
 def lookup(self,i):
    mask=sum(int(X[i,j])<<j for j in range(D))
    return np.array(self.db.execute('SELECT SUM(a),SUM(b),SUM(c) FROM adjustments WHERE (mask & ?) = mask',(mask,)).fetchone())
 def close(self):self.db.close()

def pick(mode,h,goal):
 ii=np.array(list(h)); r=np.stack(list(h.values()))
 ids=np.array([i for i in range(len(X)) if i not in h])
 if mode=='greedy':
    best=ii[np.argmin(np.abs(r-goal).sum(1)+SIZE[ii]*1e-4)]
    return int(ids[np.argmin(np.abs(X[ids]-X[best]).sum(1)+SIZE[ids]*.0001)])
 baseline=r[0]+X@(r[1:D+1]-r[0])
 loss=np.abs(baseline[ids]-goal).sum(1)
 if mode=='single_delta':return int(ids[np.argmin(loss+SIZE[ids]*.0001)])
 sel=ii[D+1:]; z=r[D+1:]-baseline[sel]
 q=Q[sel]
 if not len(sel):return int(ids[np.argmin(loss+SIZE[ids]*.0001)])
 cov=np.linalg.inv(q@q.T+.8*np.eye(len(q)))
 proj=Q[ids]@q.T
 change=proj@cov@z
 distance=np.abs(baseline[ids]+change-goal).sum(1)
 var=np.maximum(0,Q[ids].sum(1)-((proj@cov)*proj).sum(1))
 greedy=distance-.2*np.sqrt(var)+SIZE[ids]*.0001
 if mode=='ridge':return int(ids[np.argmin(greedy)])
 probs=np.zeros(len(ids));mean=np.zeros(len(ids));total=0.
 for subset in S:
    L=q[:,subset]; g=np.array(subset)
    beta=np.linalg.pinv(L)@z
    if not np.allclose(L@beta,z,atol=1e-8):continue
    # Underidentified columns may explain no observed change. Penalize them
    # instead of assuming they have a calibrated posterior.
    if not np.allclose(beta,np.round(beta),atol=1e-8):continue
    if np.max(np.abs(beta))>24:continue
    pr=.42**len(subset)
    delta=Q[ids][:,g]@np.rint(beta)
    score=np.abs(baseline[ids]+delta-goal).sum(1)
    probs+=pr*(score==0);mean+=pr*score;total+=pr
 if total and probs.max()>0:return int(ids[np.argmin(-probs/total+.002*mean/total+SIZE[ids]*.0001)])
 return int(ids[np.argmin(greedy)])

def main(out,offset):
 p=Path(out);p.mkdir(parents=True,exist_ok=True)
 rows=[]; summary=defaultdict(lambda:defaultdict(dict))
 for j,k in enumerate(CASES):
  for i in range(PER):
   seed=offset+100*j+i; task=Task(seed,k)
   try:
    for m in MODES:
     h={}; found=0
     for n in range(B):
      a=H[n] if n<len(H) else pick(m,h,task.goal)
      q=task.lookup(a);h[a]=q
      if np.array_equal(q,task.goal):
       found=n+1;break
     rows.append(dict(case=k,seed=seed,method=m,found=found,calls=len(h),actions=list(h)))
   finally:task.close()
 for k in ('all',)+CASES:
  for m in MODES:
   z=[r for r in rows if (k=='all' or k==r['case']) and r['method']==m]
   summary[k][m]=dict(n=len(z),ok=sum(r['found']>0 for r in z),calls=sum(r['calls'] for r in z),at10=sum(0<r['found']<=10 for r in z))
 (p/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 (p/'decisions.json').write_text(json.dumps(rows,indent=2)+'\n')
 print(json.dumps(summary))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--offset',type=int,required=True);a=p.parse_args();main(a.out,a.offset)
