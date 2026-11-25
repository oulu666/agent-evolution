"""Compose new read-only SQLite report expressions, not patches to the tool."""
import argparse,itertools,json,random,sqlite3
from collections import Counter,defaultdict
from pathlib import Path

# Counts charged per SQL expression on one example, including atom probes.
# Fresh DB instances and target oracle are generated deterministically.
DEVS=(0,1,2); EVALS=(3,4,5,6); BUDGET=42
ATOMS=[(op,sel,side) for op in ('count','qty','amt')
       for sel,side in [('all',0),('kind',0),('kind',1),('kind',2),('region',0),('region',1),('paid',0),('paid',1)]]
AA=list(range(len(ATOMS)))
GRAM=[(i,j,s) for s in (1,-1) for i,j in itertools.product(AA,repeat=2) if i!=j and (s<0 or i<j)]
METHODS=('catalog','enumerate','factor_all','contrast')

def sql(i):
    op,sel,side=ATOMS[i]
    exp={'count':'1','qty':'qty','amt':'amt'}[op]
    fld={'all':'1','kind':'kind','region':'region','paid':'paid'}[sel]
    if sel=='all':return f'SUM({exp})'
    return f'SUM(CASE WHEN {fld}={side} THEN {exp} ELSE 0 END)'

class World:
 def __init__(self,seed,family):
    self.conn=sqlite3.connect(':memory:')
    self.conn.execute('create table ledger(e int,g int, kind int,region int,paid int,qty int,amt int)')
    self.seed=seed;self.family=family
    r=random.Random(seed)
    # Separate generator: report request is two independently-defined ledger slices.
    is1=[i for i,a in enumerate(ATOMS) if a[0]==('amt' if family==2 else 'qty') and a[1] in ('kind','region')]
    is2=[i for i,a in enumerate(ATOMS) if a[1] in ('paid','region') and a[0]==('count' if family==1 else 'amt')]
    i,j=r.choice(is1),r.choice(is2)
    if i==j:j=next(a for a in is2 if a!=i)
    s=1 if family==0 else -1
    self.target={}
    self.original=(i,j,s)
    for e in range(7):
     items=[]
     for g in range(3):
      for k in range(15+3*e):
       # Examples 0-2 are complete, hidden data do not enter the planner.
       items.append((e,g,r.randrange(3),r.randrange(2),r.randrange(2),r.randrange(1,9),r.randrange(5,60)))
     self.conn.executemany('insert into ledger values(?,?,?,?,?,?,?)',items)
     def value(atom, g):
        op,sel,side=ATOMS[atom]
        qt={'count':None,'qty':5,'amt':6}[op]; sl={'all':None,'kind':2,'region':3,'paid':4}[sel]
        return sum(1 if qt is None else rec[qt] for rec in items if rec[1]==g and (sl is None or rec[sl]==side))
     self.target[e]=tuple(value(i,g)+s*value(j,g) for g in range(3))
 def call(self,e,c):
    a=sql(c) if isinstance(c,int) else ('('+sql(c[0])+('+' if c[2]>0 else '-')+sql(c[1])+')')
    return tuple(int(row[1]) for row in self.conn.execute(f'SELECT g,{a} FROM ledger WHERE e=? GROUP BY g ORDER BY g',(e,)))
 def close(self):self.conn.close()

def search(w,m):
    seen={};calls=0; goal={e:w.target[e] for e in DEVS}
    def use(e,c):
     nonlocal calls
     if (e,c) not in seen:
      if calls>=BUDGET:return None
      seen[e,c]=w.call(e,c);calls+=1
     return seen[e,c]
    def check(c):
     return all(use(e,c)==goal[e] for e in DEVS)
    if m in ('catalog','enumerate'):
     order=AA if m=='catalog' else GRAM
     for c in order:
      if check(c):return c,calls
      if calls>=BUDGET:break
     return None,calls
    if m=='factor_all':
     # Complete effect inversion on the lowest-ID example.
     for a in AA:use(0,a)
     idx=defaultdict(list)
     for a in AA:idx[seen[0,a]].append(a)
     opts=set()
     for a in AA:
      u=seen[0,a]
      for s in (1,-1):
       need=tuple(s*(b-v) for b,v in zip(goal[0],u))
       for b in idx[need]:
        if a!=b and (s<0 or a<b):opts.add((a,b,s))
     for c in sorted(opts):
      if check(c):return c,calls
     return None,calls
    # Contrast refinement over *atoms*, not entire candidates. Open
    # only the needed atoms on subsequent examples when ambiguity persists.
    candidates=list(GRAM)
    for e in DEVS:
     active=sorted({a for c in candidates for a in c[:2]})
     if calls+len(active)+len(DEVS)>BUDGET:break
     for a in active:use(e,a)
     candidates=[(a,b,s) for a,b,s in candidates
                 if tuple(x+s*y for x,y in zip(seen[e,a],seen[e,b]))==goal[e]]
     if len(candidates)<=1:break
    for c in sorted(candidates,key=lambda c:(c[2]<0,c[0],c[1])):
     if check(c):return c,calls
     if calls>=BUDGET:break
    return None,calls

def main(path):
 output=Path(path);output.mkdir(exist_ok=True,parents=True)
 rows=[];cert=[]
 for f in range(3):
  for k in range(20):
   w=World(18200+f*100+k,f)
   try:
    old=[a for a in AA if all(w.call(e,a)==w.target[e] for e in DEVS+EVALS)]
    yes=all(w.call(e,w.original)==w.target[e] for e in DEVS+EVALS)
    cert.append({'family':f,'case':k,'old':len(old),'valid_witness':yes})
    assert yes
    for m in METHODS:
     choice,n=search(w,m); assert n<=BUDGET
     passed=(choice is not None and all(w.call(e,choice)==w.target[e] for e in EVALS))
     rows.append({'family':f,'case':k,'method':m,'choice':choice,'calls':n,'state':'correct' if passed else 'defer' if choice is None else 'wrong'})
   finally:w.close()
 summary={m:{**Counter(q['state'] for q in rows if q['method']==m),
              'calls':sum(q['calls'] for q in rows if q['method']==m)} for m in METHODS}
 summary['cert']={'n':len(cert),'old_no_solution':sum(c['old']==0 for c in cert),'valid_new':sum(c['valid_witness'] for c in cert)}
 (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 (output/'decisions.json').write_text(json.dumps({'cert':cert,'runs':rows},indent=2)+'\n')
 print(json.dumps(summary,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);main(p.parse_args().out)
