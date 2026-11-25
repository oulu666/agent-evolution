"""Finite, real-library executable admission screen. No network/model."""
from collections import Counter
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP
from itertools import combinations, product
from pathlib import Path
import json
import random
import sqlite3

ACT={
 'decimal':list(product((ROUND_HALF_EVEN,ROUND_HALF_UP,ROUND_HALF_DOWN,ROUND_DOWN),(False,True))),
 'sqlite':list(product(('row_number','rank','dense_rank'),(False,True))),
}
ARMS=('paired','broken','positive_random','positive_curated','copy')
MASKS=('exact','partial')
SEEDS=24

def decimal(x,h):
    r,cap=h
    gross,credit=map(Decimal,x)
    return ((str(gross.quantize(Decimal('.1'),rounding=r)),),
            (str((max(Decimal(0),credit) if cap else credit).quantize(Decimal('.1'),rounding=r)),))

def sqlite(x,h):
    scores,k=x
    rank,drop=h
    assert rank in ('row_number','rank','dense_rank')
    ordering='score DESC,id' if rank=='row_number' else 'score DESC'
    where=' WHERE score IS NOT NULL' if drop else ''
    with sqlite3.connect(':memory:') as c:
        c.execute('CREATE TABLE board(id INTEGER PRIMARY KEY,score INTEGER)')
        c.executemany('INSERT INTO board VALUES (?,?)',enumerate(scores))
        ids=tuple(r[0] for r in c.execute(f"""WITH ranked AS
         (SELECT id,score,{rank}() OVER(ORDER BY {ordering}) AS r FROM board{where})
         SELECT id FROM ranked WHERE r<=? ORDER BY score DESC,id""",(k,)))
    return ids,(len(ids),)

def data(f,late):
    if f=='decimal':
        from decimal import Decimal
        pairs=[('1.24','-1.21'),('1.25','-1.25'),('1.35','-1.35'),('1.96','-1.39'),('2.01','1.09'),
               ('2.35','-2.40'),('2.55','-0.01'),('3.25','0.23')]
        return pairs if not late else [(str(Decimal(u)+11),str(Decimal(v)-(11 if v[0]=='-' else -11)))
                                       for u,v in pairs[::-1]] 
    rows=[((10,9,8,7),2),((10,10,9,7),2),((10,9,9,7),2),((10,9,None,None),3),
          ((10,10,None),2),((10,10,9,9,None),3),((10,None,None,None),2),
          ((10,10,9,None,None),4)]
    return rows if not late else [(tuple(score+200 if score is not None else None
                                         for score in ss[::-1])+(-100,),k) for ss,k in rows[::-1]]

def passed(mat,i,a,h):
    ref,scope=h
    known,want=mat[i][a],mat[i][ref]
    return known==want if scope==2 else known[scope]==want[scope]

def valid(mat,i,h):
    return [a for a in range(len(mat[i])) if passed(mat,i,a,h)]

def infer(mat,hs,recs):
    return [h for h in hs if all(passed(mat,i,a,h)==b for i,a,b in recs)]

def make_logs(mat,hs,truth,rng):
    informative=[i for i in range(len(mat)) if len(valid(mat,i,truth))<len(mat[i])]
    if len(informative)<2:return None
    ids=rng.sample(informative,2)
    anchors=[(i,rng.choice(valid(mat,i,truth)),True) for i in ids]
    failures=[(i,rng.choice([a for a in range(len(mat[i])) if a not in valid(mat,i,truth)]),False) for i in ids]
    others=[i for i in range(len(mat)) if i not in ids]
    extra=[(i,rng.choice(valid(mat,i,truth)),True) for i in rng.sample(others,2)]
    all_positive=[(i,a,True) for i in others for a in valid(mat,i,truth)]
    curated=min((p for p in combinations(all_positive,2) if p[0][0]!=p[1][0]),
                key=lambda p:len(infer(mat,hs,[*anchors,*p])))
    broken=[(a[0],b[1],False) for a,b in zip(failures,failures[::-1],strict=True)]
    return dict(paired=anchors+failures,broken=anchors+broken,positive_random=anchors+extra,
                positive_curated=anchors+list(curated),copy=anchors+extra)

def encode(log):
    return ''.join(f'{i:02}{a:02}{int(b)}' for i,a,b in log).encode('ascii')

def experiment(f,scope):
    api=(decimal if f=='decimal' else sqlite)
    actions=ACT[f]
    dev=[[api(x,h) for h in actions] for x in data(f,False)]
    test=[[api(x,h) for h in actions] for x in data(f,True)]
    hs=list(product(range(len(actions)),(2,) if scope=='exact' else (0,1)))
    results={k:Counter() for k in ARMS}
    sampled=seen_redundant=0
    for seed in range(SEEDS):
        rng=random.Random(7610+seed)
        truth=hs[seed%len(hs)]
        logs=make_logs(dev,hs,truth,rng)
        if logs is None:continue
        sampled+=1
        only_anchor=infer(dev,hs,logs['paired'][:2])
        paired=infer(dev,hs,logs['paired'])
        seen_redundant+=only_anchor==paired
        if scope=='exact':assert only_anchor==paired
        for arm,log in logs.items():
            assert len(log)==4 and len(encode(log))==20
            remaining=infer(dev,hs,log)
            positive={a for i,a,b in log if b}
            r=results[arm]
            r.update(exposures=4,bytes=20,surviving_total=len(remaining),contradiction=not remaining)
            for j,row in enumerate(test):
                n=Counter(a for i,a,b in log if b)
                if arm=='copy':picked=n.most_common(1)[0][0]
                elif not remaining:picked=None
                else:
                    score,action=max((sum(passed(test,j,a,h) for h in remaining),-a) for a in range(len(row)))
                    picked=-action if score*2>len(remaining) else None
                correct=picked is not None and passed(test,j,picked,truth)
                cannotcopy=not set(valid(test,j,truth))&positive
                r.update(correct=correct,wrong=picked is not None and not correct,abstain=picked is None,
                         no_copy_opportunity=cannotcopy,solved_no_copy=cannotcopy and correct)
    return dict(sampled=sampled,total_seeds=SEEDS,logical_redundancy=seen_redundant,
                holdout_per_seed=len(test),unique_api_outputs_built=(len(dev)+len(test))*len(actions),
                reports=results)

if __name__=='__main__':
    out={f:{p:experiment(f,p) for p in MASKS} for f in ACT}
    print(json.dumps(dict(sqlite=sqlite3.sqlite_version,results=out),indent=2,sort_keys=True))
