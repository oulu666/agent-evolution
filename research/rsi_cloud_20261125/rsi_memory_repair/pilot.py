"""Finite-memory compatibility controller for real, benign SQLite restore tasks."""
import argparse,itertools,json,sqlite3
from collections import defaultdict
from pathlib import Path
NAMES=('a','b','c')
ACTIONS=frozenset(NAMES)

def execute(order,action,kept,staged):
    c=sqlite3.connect(':memory:',isolation_level=None)
    try:
        c.execute('create table work(x int)')
        c.execute('begin')
        c.execute('insert into work values (?)',(kept,))
        for k in order:
            assert k in ACTIONS
            c.execute('savepoint '+k)
        c.execute('insert into work values (?)',(staged,))
        observed=(tuple(q[0] for q in c.execute('select x from work order by rowid')),c.in_transaction)
        if action is None:return observed,None
        assert action in ACTIONS
        try:c.execute('rollback to '+action)
        except sqlite3.OperationalError:return observed,False
        got=tuple(q[0] for q in c.execute('select x from work order by rowid'))
        return observed,(got==(kept,) and c.in_transaction)
    finally:c.close()

def prepare(name):
    if name=='pairwise_trap':return list(itertools.permutations(NAMES,2))
    return [q for n in (1,2,3) for q in itertools.permutations(NAMES,n)]

def masks(histories):
    d={}
    for h in histories:
        d[h]=frozenset(a for a in NAMES if execute(h,a,10,20)[1])
        assert d[h]
    return d

def exact_table(m,k):
    # Ordinary exhaustive bounded-controller SAT-equivalent reference.
    count=0
    for flat in itertools.product(range(k),repeat=k*len(NAMES)):
        count+=1
        table=dict(zip(itertools.product(range(k),NAMES),flat))
        out=[set(ACTIONS) for _ in range(k)]
        for h,opts in m.items():
            q=0
            for e in h:q=table[q,e]
            out[q].intersection_update(opts)
        if all(out):return (table,[min(x) for x in out]),count
    return None,count

def prefix_compile(m,k):
    # Prefix constraints; reject an incompatible merge as soon as an
    # action intersection empties, without expanding remaining prefixes.
    prefixes=sorted({h[:i] for h in m for i in range(1,len(h)+1)},key=lambda h:(len(h),h))
    trans={};state={():0};out=[ACTIONS for _ in range(k)]; trial=0
    def rec(idx):
        nonlocal trial
        if idx==len(prefixes):return (dict(trans),[min(r) for r in out])
        h=prefixes[idx]; key=state[h[:-1]],h[-1]; known=key in trans
        for q in ( (trans[key],) if known else range(k) ):
           trial+=1
           old=out[q];eligible=old & m.get(h,ACTIONS)
           if not eligible:continue
           out[q]=eligible
           state[h]=q
           if not known:trans[key]=q
           ans=rec(idx+1)
           out[q]=old
           if ans is not None:return ans
           if not known:del trans[key]
        return None
    return rec(0),trial

def run(p):
 p=Path(p);p.mkdir(exist_ok=True,parents=True)
 ans={}
 for model in ('pairwise_trap','all_nonempty'):
    H=prepare(model); mm=masks(H)
    a={}; witness=None
    for k in (1,2,3):
      left,n=prefix_compile(mm,k); right,i=exact_table(mm,k)
      assert bool(left)==bool(right)
      a[str(k)]={'feasible':bool(left),'prefix_expansions':n,'complete_tables_tried':i}
      if witness is None and left:witness=left;kmin=k
    edges=sum(not(mm[x]&mm[y]) for x,y in itertools.combinations(mm,2))
    act=max(NAMES,key=lambda x:sum(x in z for z in mm.values()))
    r={'contexts':len(H),'pairwise_conflict_edges':edges,'fits':a,'min_states':kmin,'tests':{}}
    for policy in ('current_only','memorize_first','compiled'):
      correct=wrong=0
      for h in H:
       for i in range(12):
        prior,working=10+i,80+i
        if policy=='current_only': selected=act
        elif policy=='memorize_first':selected=h[0]
        else:
          table,out=witness;q=0
          for t in h:q=table[q,t]
          selected=out[q]
        seen,yes=execute(h,selected,prior,working)
        assert seen==((prior,working),True)
        correct+=bool(yes);wrong+=not bool(yes)
      r['tests'][policy]=dict(correct=correct,wrong=wrong,contexts=len(H),deployments=correct+wrong)
    ans[model]=r
 (p/'summary.json').write_text(json.dumps(ans,indent=2)+'\n')
 print(json.dumps(ans,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);run(p.parse_args().out)
