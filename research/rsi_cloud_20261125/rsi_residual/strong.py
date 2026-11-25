"""Additional frozen comparison on new seeds after the initial pilot."""
import argparse,json
from pathlib import Path
from collections import defaultdict
import numpy as np
from bench import Task,X,Q,SIZE,H,B,D,CASES,pick
from sklearn.linear_model import MultiTaskLasso

DIST=np.abs(X[:,None,:]-X[None,:,:]).sum(2)
K=np.exp(-DIST/2)
MODES=('ridge','support_vote','l1','hamming_gp','pair_probe')
def strong(m,h,goal):
 if m in ('ridge','support_vote'):return pick(m,h,goal)
 ii=np.array(list(h)); r=np.stack(list(h.values()));ids=np.array([i for i in range(len(X)) if i not in h])
 base=r[0]+X@(r[1:D+1]-r[0]);target=goal-base[ids]
 sel=ii[D+1:];z=r[D+1:]-base[sel]
 plain=np.abs(target).sum(1)
 if not len(sel):return int(ids[np.argmin(plain+SIZE[ids]*.0001)])
 if m=='l1':
  model=MultiTaskLasso(alpha=.12,fit_intercept=False,tol=.0001,max_iter=3000)
  model.fit(Q[sel],z)
  estimates=model.predict(Q[ids]);score=np.abs(estimates-target).sum(1)
  return int(ids[np.argmin(score+SIZE[ids]*.0001)])
 if m=='hamming_gp':
  scale=max(1.,float(np.max(np.abs(z))))
  l=np.linalg.inv(K[np.ix_(sel,sel)]+.07*np.eye(len(sel)))
  right=K[np.ix_(ids,sel)]
  estimates=right@l@z
  sd=np.sqrt(np.maximum(0,1-((right@l)*right).sum(1)))
  score=np.abs(estimates-target).sum(1)-.30*scale*sd
  return int(ids[np.argmin(score+SIZE[ids]*.0001)])
 # Exposure-matched baseline: fit two-way truth table by testing one
 # pair from the best additive hypothesis. Then finish with ridge.
 best=X[ids[np.argmin(plain+SIZE[ids]*.0001)]]
 if len(sel)==1:
  opts=ids[(SIZE[ids]==2)&(np.sum((X[ids]==1)&(best==1),axis=1)==2)]
  if len(opts):return int(opts[0])
 return pick('ridge',h,goal)

def run(p,offs):
 p=Path(p);p.mkdir(parents=True,exist_ok=True);out=[];s={}
 for k,case in enumerate(CASES):
  for i in range(18):
   task=Task(offs+k*100+i,case)
   try:
    result={}
    for m in MODES:
     h={}; found=0
     for n in range(B):
      a=H[n] if n<len(H) else strong(m,h,task.goal)
      q=task.lookup(a);h[a]=q
      if np.array_equal(q,task.goal):
       found=n+1;break
     result[m]=(found,len(h))
    out.append({'case':case,'seed':offs+k*100+i,'methods':result})
   finally:task.close()
 for k in ('all',)+CASES:
  n=[a['methods'] for a in out if k=='all' or a['case']==k]
  s[k]={m:{'ok':sum(v[m][0]>0 for v in n),'calls':sum(v[m][1] for v in n),'n':len(n)} for m in MODES}
 (p/'summary.json').write_text(json.dumps(s,indent=2)+'\n')
 (p/'paired.json').write_text(json.dumps(out,indent=2)+'\n')
 print(s['all'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--offset',type=int,required=True);a=p.parse_args();run(a.out,a.offset)
