"""Batch two readbacks while preserving isolation on actual SQLite actions."""
import argparse,itertools,json,random,sqlite3,statistics,time
from pathlib import Path
MODES=('fresh','unisolated','savepoint_only','always_restore','typed_native','watch_restore')
REGIMES={'row_row':('row_a','row_a'),'cache_cache':('cache','cache'),
         'mixed':('row_a','cache'),'disjoint':('row_a','row_b')}
SIZES=(0,128,2048)
CACHED=333

class Runner:
 def __init__(self,rows):
    self.rows=rows;self.nconn=0;self.nsql=0
 def sql(self,c,s,a=()):
    self.nsql+=1;return c.execute(s,a)
 def setup(self):
    self.nconn+=1
    c=sqlite3.connect(':memory:',isolation_level=None)
    for name in ('row_a','row_b'):self.sql(c,'CREATE TABLE '+name+'(x INTEGER)')
    self.sql(c,'PRAGMA cache_size='+str(CACHED))
    self.nsql+=1
    c.executemany('INSERT INTO row_a VALUES(?)',((i,) for i in range(self.rows)))
    return c
 def single(self,c,op,val):
    if op=='cache':
      before=self.sql(c,'PRAGMA cache_size').fetchone()[0]
      self.sql(c,f'PRAGMA cache_size={CACHED+1+val}')
      after=self.sql(c,'PRAGMA cache_size').fetchone()[0]
      return int(before==CACHED and after==CACHED+1+val),after-CACHED-1
    count=self.sql(c,'SELECT COUNT(*) FROM '+op).fetchone()[0]
    self.sql(c,'INSERT INTO '+op+' VALUES(?)',(val,))
    new=self.sql(c,'SELECT COUNT(*) FROM '+op).fetchone()[0]
    good=int(count==(self.rows if op=='row_a' else 0) and new==count+1)
    return good,val
 def run(self,ops,vals,m):
    result=[]
    if m=='fresh':
       for o,x in zip(ops,vals):
        c=self.setup()
        try:result.append(self.single(c,o,x))
        finally:c.close()
       return result
    c=self.setup()
    try:
      for i,(o,x) in enumerate(zip(ops,vals)):
       if m=='unisolated':
          result.append(self.single(c,o,x));continue
       last=(i+1==len(ops))
       # Last action needs no reset because the isolated worker closes.
       if last:
          result.append(self.single(c,o,x));continue
       if m=='typed_native':
         if o=='cache':
            bound=self.sql(c,'PRAGMA cache_size').fetchone()[0]
            result.append(self.single(c,o,x))
            self.sql(c,f'PRAGMA cache_size={bound}')
         else:
            self.sql(c,'SAVEPOINT isolate')
            result.append(self.single(c,o,x))
            self.sql(c,'ROLLBACK TO isolate');self.sql(c,'RELEASE isolate')
       else:
         self.sql(c,'SAVEPOINT isolate')
         result.append(self.single(c,o,x))
         self.sql(c,'ROLLBACK TO isolate');self.sql(c,'RELEASE isolate')
         if m=='always_restore': self.sql(c,f'PRAGMA cache_size={CACHED}')
         if m=='watch_restore':
            v=self.sql(c,'PRAGMA cache_size').fetchone()[0]
            if v!=CACHED:self.sql(c,f'PRAGMA cache_size={CACHED}')
    finally:c.close()
    return result

def experiment(out,repeats):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 r=random.Random(8201); rows=[];tot={}
 configs=list(itertools.product(REGIMES,SIZES,tuple(itertools.product((0,1),repeat=2))))
 for case,n,vals in configs:
    expected=[(1,v) for v in vals] # Independent user contract.
    # Interleave methods and report median per case to avoid order artifacts.
    rec={m:[] for m in MODES}
    for rep in range(repeats):
       mm=list(MODES);r.shuffle(mm)
       for m in mm:
          job=Runner(n);t=time.perf_counter_ns()
          response=job.run(REGIMES[case],vals,m)
          dt=time.perf_counter_ns()-t
          rec[m].append((response,dt,job.nconn,job.nsql))
    for m,L in rec.items():
      first,_,conn,sql=L[0];assert all((x[0],*x[2:])==(first,conn,sql) for x in L)
      rows.append(dict(case=case,rows=n,method=m,ok=int(first==expected),state_precondition_ok=sum(a for a,_ in first),
                       conn=conn,sql=sql,logical_probes=2,median_ns=statistics.median(x[1] for x in L)))
 for k in ('all',)+tuple(REGIMES):
  t={}
  for m in MODES:
    z=[x for x in rows if x['method']==m and (k=='all' or k==x['case'])]
    t[m]={a:sum(x[a] for x in z) for a in ('ok','conn','sql','logical_probes','median_ns')}
    t[m]['cases']=len(z)
  tot[k]=t
 (out/'summary.json').write_text(json.dumps(tot,indent=2)+'\n')
 (out/'measurements.json').write_text(json.dumps(rows,indent=1)+'\n')
 print(json.dumps(tot,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--repeats',type=int,default=11);a=p.parse_args();experiment(a.out,a.repeats)
