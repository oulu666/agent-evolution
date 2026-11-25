"""One-question task-intent decision pilot on Decimal and SQLite, Python stdlib."""
from collections import Counter
from decimal import (Decimal, ROUND_DOWN, ROUND_HALF_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP)
from itertools import combinations, product
import json
from math import log2
import sqlite3

INTENTS={
    'decimal':list(product((ROUND_HALF_EVEN,ROUND_HALF_UP,ROUND_HALF_DOWN,ROUND_DOWN),(False,True))),
    'sqlite':list(product(('row_number','rank','dense_rank'),(False,True))),
}
COST_ASK=100
COST_ABSTAIN=350
COST_WRONG=1000
NATIVE={'decimal':0,'sqlite':0}
POLICIES=('native_default','never_ask','entropy','report_paircut','exact_one_step','full_report_ceiling')

def dec(inputs,h):
    mode,clamp=h
    return tuple(str((max(Decimal(0),Decimal(x)) if clamp else Decimal(x)).quantize(
               Decimal('.1'),rounding=mode)) for x in inputs)

def sql(inputs,h):
    rank,drop=h
    scores,k=inputs
    # Each generated task uses a fresh database; rank and filter options are fixed whitelist terms.
    assert rank in ('row_number','rank','dense_rank')
    ordering='score DESC, id' if rank=='row_number' else 'score DESC'
    where='WHERE score IS NOT NULL' if drop else ''
    with sqlite3.connect(':memory:') as c:
        c.execute('CREATE TABLE scores (id INTEGER PRIMARY KEY, score INTEGER)')
        c.executemany('INSERT INTO scores VALUES (?,?)',enumerate(scores))
        selected=c.execute(f'''WITH ranked AS (
            SELECT id, score, {rank}() OVER (ORDER BY {ordering}) AS r
            FROM scores {where})
            SELECT id FROM ranked WHERE r<=? ORDER BY score DESC, id''',(k,)).fetchall()
    return tuple(z[0] for z in selected)

def previews(f):
    if f=='decimal':
        return [(x,) for x in ('1.21','1.25','1.35','1.39','-1.21','-1.25','-1.35','-1.39','0.01')]
    return [((10,9,8),2),((10,10,9),2),((10,10,9,8),2),((10,8,8,7),2),((5,None,None),2),
            ((5,5,None),2),((None,None,None),2),((1,1,None,-1),3),((4,3,3,3),3),((4,4,3,None),3)]

def jobs(f):
    if f=='decimal':
        first = [
            ('1.21','2.31','0.01','0.02'),
            ('1.25','2.35','2.96','3.14'),
            ('1.24','1.98','2.33','-3.21'),
            ('-2.31','-1.21','-4.02','-3.11'),
            ('1.32','1.35','2.35','7.55'),
            ('-1.25','-2.35','1.25','2.35'),
        ]
        def shift(x):
            q=Decimal(x)
            return str(q+(5 if q>=0 else -5))
        return first+[tuple(map(shift,x[::-1])) for x in first]
    first=[
        ((10,9,8,7,6),2),
        ((10,10,9,8,7),2),
        ((10,9,9,7,None),2),
        ((10,None,None,None,0),4),
        ((10,10,8,8,None,None),3),
        ((10,10,9,9,7,None),5),
    ]
    reverse = lambda a: tuple(x+40 if x is not None else None for x in a[::-1])
    return first+[(reverse(a),k) for a,k in first]

def argmin_prediction(ids,payload):
    values=Counter(payload[i] for i in ids)
    pick,n=values.most_common(1)[0]
    wrong=len(ids)-n
    if COST_WRONG*wrong>COST_ABSTAIN*len(ids):
        return None,COST_ABSTAIN*len(ids)
    return pick,COST_WRONG*wrong

def split(row):
    groups={}
    for i,response in enumerate(row):
        groups.setdefault(response,[]).append(i)
    return list(groups.values())

def evaluate(p,questions,target,truth):
    n=len(target)
    ambiguous=len(set(target))>1
    ids=range(n)
    picked,no_ask_risk=argmin_prediction(ids,target)
    asks=0
    if p=='native_default':
        picked=target[0]
    elif p=='full_report_ceiling':
        asks=int(ambiguous)
        picked=target[truth]
    elif p!='never_ask':
        ranked=[]
        for j,row in enumerate(questions):
            groups=split(row)
            conditional=sum(argmin_prediction(g,target)[1] for g in groups)
            if p=='entropy':
                score=-sum(len(g)/n*log2(len(g)/n) for g in groups)
            elif p=='report_paircut':
                score=sum(target[x]!=target[y] and row[x]!=row[y] for x,y in combinations(ids,2))
            else:score=-conditional
            ranked.append((score,-j,conditional))
        _,neg_j,cond=max(ranked)
        if cond+COST_ASK*n<no_ask_risk:
            asks=1
            q=questions[-neg_j]
            # User returns a concrete preview result, not a private parameter ID.
            answer=q[truth]
            compatible=[i for i in ids if q[i]==answer]
            picked,_=argmin_prediction(compatible,target)
    wrong=picked is not None and picked!=target[truth]
    hold=picked is None
    return dict(wrong=int(wrong),hold=int(hold),correct=int(not wrong and not hold),
                questions=asks,false_ambiguity=int(asks and not ambiguous),
                milli_cost=asks*COST_ASK+COST_ABSTAIN*hold+COST_WRONG*wrong)

def test(f):
    api=dec if f=='decimal' else sql
    hypotheses=INTENTS[f]
    qs=[[api(x,h) for h in hypotheses] for x in previews(f)]
    scores={}
    for i,job in enumerate(jobs(f)):
        real=[api(job,h) for h in hypotheses]
        group='templates' if i<6 else 'transformed'
        result=scores.setdefault(group,{m:Counter() for m in POLICIES})
        for m in POLICIES:
            for truth in range(len(hypotheses)):
                result[m].update(evaluate(m,qs,real,truth))
    return scores

if __name__=='__main__':
    r=dict(sqlite=sqlite3.sqlite_version,results={f:test(f) for f in INTENTS})
    print(json.dumps(r,sort_keys=True,indent=2))
