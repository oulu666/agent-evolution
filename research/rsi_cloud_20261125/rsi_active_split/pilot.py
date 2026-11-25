"""Active choice of a second witness with source-preserving action certificates."""
import argparse,itertools,json,math,random,sqlite3
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
A=('a','b','c'); H=8; T=8; N=12
COUNT=20
MODES=('fixed','entropy','bayes','repair_worst','exact_worst')
CASES=('generic','biased','no_signal','harmless')

@lru_cache(maxsize=None)
def sqlite_mask(mask):
    # Evaluate all feasible named rollback actions on isolated DB copies.
    actual=0
    for a in range(3):
        c=sqlite3.connect(':memory:',isolation_level=None)
        try:
            c.execute('create table work(v int)')
            c.execute('begin')
            c.execute('insert into work values(11)')
            for j in range(3):
                if mask&(1<<j):c.execute('savepoint '+A[j])
            c.execute('insert into work values(29)')
            snap=tuple(x[0] for x in c.execute('select v from work order by rowid'))
            assert snap==(11,29) and c.in_transaction
            try:c.execute('rollback to '+A[a])
            except sqlite3.OperationalError:continue
            if tuple(x[0] for x in c.execute('select v from work'))==(11,) and c.in_transaction:
                actual|=1<<a
        finally:c.close()
    return actual

class World:
 def __init__(self,seed,case):
    r=random.Random(seed)
    self.case=case
    self.old=tuple(r.choice((1,2,3,4,5,6,7)) for _ in range(N))
    if case=='harmless': self.old=tuple(x|1 for x in self.old)
    self.deploy=[]; self.diag=[]
    for h in range(H):
       # First observation leaves exactly four compatible explanations.
       first=1 if h<4 else 2
       d=(first,*[r.randrange(1,8) for _ in range(T-1)])
       if case=='no_signal':d=(first,*[first]*(T-1))
       self.diag.append(d)
       def nextmask(o):
          if case=='harmless':return r.randrange(1,8)|1
          if r.random()<.23:return r.randrange(1,8)
          return r.choice([m for m in range(1,8) if m&o])
       self.deploy.append(tuple(nextmask(o) for o in self.old))
    self.ws=tuple((5 if case=='biased' and h%4==0 else 1) for h in range(H))
    self.freq=tuple((5 if case=='biased' and x<4 else 1) for x in range(N))

def branches(w,hs,q):
    b=defaultdict(list)
    for h in hs:b[w.diag[h][q]].append(h)
    return [tuple(x) for x in b.values()]

def certificate(w,hs,x):
    z=w.old[x]
    for h in hs:z&=w.deploy[h][x]
    return (z&-z) if z else 0
def cover(w,hs):
    return sum(f for x,f in enumerate(w.freq) if certificate(w,hs,x))
def exact_branch_bound(w,hs):
    # Independent enumeration of possible single actions in each deployment
    # context. Abstention always available, additive objective across contexts.
    return sum(w.freq[x]*max([0]+[int(bool(w.old[x]&a) and
                 all(w.deploy[h][x]&a for h in hs)) for a in (1,2,4)]) for x in range(N))

def select(w,hs,mode):
 if mode=='fixed':return 1
 opts=[]
 p=sum(w.ws[h] for h in hs)
 for q in range(1,T):
    bb=branches(w,hs,q); ww=[sum(w.ws[h] for h in b)/p for b in bb]
    cc=[cover(w,b) for b in bb]
    avg=sum(a*b for a,b in zip(ww,cc))
    metric={'entropy':(-sum(x*math.log2(x) for x in ww),),
            'bayes':(avg,), 'repair_worst':(min(cc),avg)}
    if mode=='exact_worst':
        ex=[exact_branch_bound(w,b) for b in bb]
        assert ex==cc
        # Tie by the same documented convention; comparison is an equality certificate.
        key=(min(ex),sum(a*b for a,b in zip(ww,ex)))
    else: key=metric[mode]
    opts.append((key,-q))
 return -max(opts)[1]

def run(out):
 p=Path(out);p.mkdir(parents=True,exist_ok=True)
 rows=[];tot=defaultdict(dict)
 for ci,case in enumerate(CASES):
  for i in range(COUNT):
    w=World(60800+ci*300+i,case)
    for true in range(H):
      h0=tuple(h for h in range(H) if w.diag[h][0]==sqlite_mask(w.diag[true][0]))
      assert true in h0
      for mode in MODES:
       q=select(w,h0,mode)
       got=sqlite_mask(w.diag[true][q]);h1=tuple(h for h in h0 if w.diag[h][q]==got)
       deployed=[certificate(w,h1,x) for x in range(N)]
       new=old=wrong=defer=0
       for x,(a,f) in enumerate(zip(deployed,w.freq)):
        if not a:defer+=f;continue
        oc=bool(sqlite_mask(w.old[x])&a)
        tc=bool(sqlite_mask(w.deploy[true][x])&a)
        old+=f*oc;new+=f*tc;wrong+=f*(not tc or not oc)
       assert wrong==0
       rows.append(dict(case=case,world=i,truth=true,mode=mode,q=q,before=cover(w,h0),eligible=sum(w.freq),correct=new,wrong=wrong,defer=defer,old=old))
 for k in ('all',)+CASES:
  for mode in MODES:
   z=[x for x in rows if x['mode']==mode and (k=='all' or x['case']==k)]
   v={a:sum(r[a] for r in z) for a in ('before','eligible','correct','wrong','defer','old')}
   grouped=defaultdict(list)
   for r in z:grouped[(r['case'],r['world'])].append(r['correct'])
   v.update(episodes=len(z),minsum=sum(min(r) for r in grouped.values()),logical_candidate_evals=6*len(z))
   tot[k][mode]=v
 ex={(r['case'],r['world'],r['truth']):r for r in rows if r['mode']=='exact_worst'}
 assert all((r['q'],r['correct'])==(ex[r['case'],r['world'],r['truth']]['q'],ex[r['case'],r['world'],r['truth']]['correct'])
            for r in rows if r['mode']=='repair_worst')
 (p/'summary.json').write_text(json.dumps(tot,indent=2)+'\n')
 (p/'traces.json').write_text(json.dumps(rows,indent=1)+'\n')
 print(json.dumps(tot,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);run(p.parse_args().out)
