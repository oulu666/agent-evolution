"""Offline artifact correctness with missing report preferences; no network."""
import csv
from collections import Counter
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP, localcontext
from io import StringIO
from itertools import product
import json
import random

PREFS=tuple(product((False,True),(False,True)))  # count missing as zero, half up
METHODS=('wait','eager','static_dag','receipt','guarded_dag')
HEADER=('section','count','mean')
FAMILIES=('stable','ties','missing','empty_group')

def fixture(i,family):
    rng=random.Random(i*31+101)
    rows=[]
    for j in range(2+i%3):
        g=f'department-{i}-{j}'
        base=(rng.randint(1,7)*1000) # even tenths at base
        vector={
            'stable': [base+2,base+3],
            'ties': [base+3,base+7],
            'missing':[base+1,base+4,None],
            'empty_group':[None,None] if j==0 else [base+5],
        }[family]
        rows.extend((g,x) for x in vector)
    rng.shuffle(rows)
    return rows

def to_input(rows):
    w=StringIO(newline='')
    cw=csv.writer(w,lineterminator='\n')
    cw.writerow(('section','score_cents'))
    cw.writerows(rows)
    return w.getvalue()

def load(blob):
    source=csv.DictReader(StringIO(blob,newline=''))
    return [(r['section'],int(r['score_cents']) if r['score_cents'] else None) for r in source]

def checkpoint(records):
    tmp={}
    for g,x in records:
        n,s,m=tmp.get(g,(0,0,0))
        tmp[g]=(n+(x is not None),s+(x or 0),m+(x is None))
    return tuple(sorted(tmp.items()))

def project(state,pref):
    include,half_up=pref
    with localcontext() as ctx:
        ctx.prec=40
        mode=ROUND_HALF_UP if half_up else ROUND_HALF_EVEN
        report=[]
        for k,(n,s,m) in state:
            n=n+(m if include else 0)
            mean='NA' if not n else str((Decimal(s)/(100*n)).quantize(Decimal('.1'),rounding=mode))
            report.append((k,n,mean))
        return tuple(report)

def output(report):
    f=StringIO(newline='')
    w=csv.writer(f,lineterminator='\n')
    w.writerow(HEADER);w.writerows(report)
    return f.getvalue().encode('utf8')

def native_invariant(state):
    for _,(n,s,m) in state:
        if m:return False
        q,r=divmod(s,10*n)
        if 2*r==10*n and q%2==0:return False
    return True

def oracle(rows,pref):
    include,half_up=pref
    want=[]
    for g in sorted({g for g,_ in rows}):
        v=[x if x is not None else 0 for gg,x in rows if gg==g and (include or x is not None)]
        if not v:mean='NA'
        else:
            den=10*len(v)
            q,r=divmod(sum(v),den)
            if 2*r>den or 2*r==den and (half_up or q%2):q+=1
            mean=f'{q//10}.{q%10}'
        want.append((g,str(len(v)),mean))
    return tuple(want)

def independent_check(blob,rows,pref):
    if blob is None:return False
    got=tuple(map(tuple,csv.reader(StringIO(blob.decode('utf8'),newline=''))))
    return got==(HEADER,*oracle(rows,pref))

def run(method,source,answer):
    ctr=Counter()
    ctr.update({k:0 for k in ('pre','post','rework_stages','preliminary_projections','built_early')})
    state=early=report=None
    if method!='wait':
        state=checkpoint(load(source))
        ctr['pre']+=2
    if method=='eager':
        early=output(project(state,PREFS[0]))
        ctr.update(pre=2,preliminary_projections=1)
    if method=='receipt':
        projections=[project(state,p) for p in PREFS]
        ctr.update(pre=1,preliminary_projections=4)
        if len(set(projections))==1:
            early=output(projections[0])
            ctr['pre']+=1
        # A receipt only certifies invariants. It doesn't cache all hypothetical rendered reports.
    if method=='guarded_dag':
        ctr['pre']+=1
        if native_invariant(state):
            early=output(project(state,PREFS[0]))
            ctr.update(pre=2,preliminary_projections=1)
    assert ctr['pre']<=5
    if early is not None:
        ctr['built_early']+=1
    if state is None:
        state=checkpoint(load(source))
        ctr['post']+=2
    if early is None or method=='eager' and answer!=PREFS[0]:
        # Eager only reuses same policy. It has no evidence outputs under the alternatives would agree.
        report=output(project(state,answer))
        ctr['post']+=2
        ctr['rework_stages']+=2 if early is not None else 0
    else:
        report=early
    return early,report,ctr

def main():
    result={}
    for split,ids in [('development',range(8)),('holdout',range(54,64))]:
        dest=result.setdefault(split,{k:Counter() for k in METHODS})
        for f,i in product(FAMILIES,ids):
            rows=fixture(i,f)
            source=to_input(rows)
            for answer,method in product(PREFS,METHODS):
                early,final,ctr=run(method,source,answer)
                good=independent_check(final,rows,answer)
                allsafe=early is not None and all(independent_check(early,rows,q) for q in PREFS)
                ctr.update(cases=1,final_correct=good,safe_early=allsafe,
                           unsafe_early=early is not None and not allsafe)
                ctr['total']=ctr['pre']+ctr['post']
                dest[method].update(ctr)
    print(json.dumps(dict(results=result),sort_keys=True,indent=2))

if __name__=='__main__':main()
