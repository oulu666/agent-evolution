"""Synthetic in-memory SQLite experiment and reserved external model handoff."""
import argparse
from collections import Counter
from dataclasses import dataclass
import json
import random
import sqlite3
import sys

FAMILIES=('unique','duplicate','stale','conflict','absent')
MODES=('recent','route_latest','certificate','native_sql')

@dataclass(frozen=True)
class Case:
    id:str
    kind:str
    states:tuple
    edges:tuple
    expected:str|None
    actual_cap:int

def fixtures(n):
    for fi,kind in enumerate(FAMILIES):
        for i in range(n):
            idx=fi*31+i
            rng=random.Random(913+idx)
            states=tuple((f'A{key}',4+rng.randrange(5),14+j) for j,key in enumerate(rng.sample(range(100,999),3)))
            chosen=rng.randrange(3)
            t,rev,_=states[chosen]
            clean=kind in ('unique','duplicate')
            edges=[(t,rev)] if clean else []
            if kind=='duplicate':edges*=2
            if kind=='stale':edges=[(t,rev-1)]
            if kind=='conflict':edges=[(t,rev),states[(chosen+1)%3][:2]]
            yield Case(f'case{idx:03}',kind,states,tuple(edges),t if clean else None,rng.randrange(3,11))

def db(c):
    con=sqlite3.connect(':memory:')
    con.executescript('CREATE TABLE attempt(id TEXT PRIMARY KEY, rev INTEGER, cap INTEGER);'
                      'CREATE TABLE origin(probe TEXT,id TEXT,rev INTEGER);'
                      'CREATE TABLE jobs(job INTEGER PRIMARY KEY);')
    con.executemany('INSERT INTO attempt VALUES(?,?,?)',c.states)
    con.executemany('INSERT INTO origin VALUES(\'q7\',?,?)',c.edges)
    con.executemany('INSERT INTO jobs VALUES(?)',((i,) for i in range(25)))
    return con

def observe(con,cap):
    return con.execute('SELECT count(*) FROM (SELECT job FROM jobs ORDER BY job LIMIT ?)',(cap,)).fetchone()[0]

def native_bind(con):
    row=con.execute('''WITH edges AS (SELECT DISTINCT id,rev FROM origin WHERE probe='q7')
        SELECT a.id FROM edges e JOIN attempt a USING(id,rev) WHERE (SELECT count(*) FROM edges)=1''').fetchone()
    return None if row is None else row[0]

def cert(c):
    edges=set(c.edges)
    active={r[:2] for r in c.states}
    if len(edges)!=1 or not edges<=active:return None
    return next(iter(edges))[0]

def choose(mode,c,con):
    if mode=='recent':return c.states[-1][0]
    if mode=='route_latest':return c.edges[-1][0] if c.edges else None
    if mode=='certificate':return cert(c)
    return native_bind(con)

def score(c,pick,cap,con):
    real_ids={t for t,_,_ in c.states}
    invalid=(pick is not None and (pick not in real_ids or type(cap) is not int or not 1<=cap<=400)) or (pick is None and cap is not None)
    if invalid:return 'invalid'
    if pick is None:return 'safe_abstain' if c.expected is None else 'false_abstain'
    con.execute('UPDATE attempt SET cap=?,rev=rev+1 WHERE id=?',(cap,pick))
    got=con.execute('SELECT id,rev,cap FROM attempt ORDER BY id').fetchall()
    expected=sorted((t,r+(t==c.expected),c.actual_cap if t==c.expected else n) for t,r,n in c.states)
    if got==expected:return 'correct_patch'
    if cap!=c.actual_cap:return 'wrong_value'
    if c.expected is None:return 'unsafe_should_abstain'
    return 'right_value_wrong_target'

def benchmark():
    d={}
    for c in fixtures(20):
        group='preliminary_ids' if int(c.id[-3:])%31<8 else 'fresh_ids'
        tab=d.setdefault(group,{m:Counter() for m in MODES})
        for m in MODES:
            con=db(c); cap=observe(con,c.actual_cap)
            assert cap==c.actual_cap
            chosen=choose(m,c,con)
            tab[m].update([score(c,chosen,cap if chosen is not None else None,con),'cases'])
            con.close()
    print(json.dumps(dict(sqlite=sqlite3.sqlite_version,results=d),sort_keys=True,indent=2))

def prompt(c,mode):
    prefix=("One SQLite page-cap observation was produced for probe q7. Update only the same current "
            "attempt uniquely linked by q7; duplicate identical links count once. If links conflict, "
            "are missing, or identify a revision other than current, abstain. Respond with just "
            'one JSON object: {"attempt":"Axxx","cap":5} or {"abstain":true}.')
    states=[dict(attempt=t,current_revision=r,previous_cap=x) for t,r,x in c.states]
    edges=[dict(attempt=t,snapshot_revision=r) for t,r in c.edges]
    view=dict(attempts=states,probe='q7',provenance=edges,observed_count=c.actual_cap)
    if mode=='neutral':view['annotation']='precomputed auxiliary note only'
    if mode=='bound':view['annotation']=f'verified current attempt {cert(c)}' if cert(c) else 'DEFER; no valid unique current link'
    return prefix+'\n'+json.dumps(view,separators=(',',':'))

def model_cases():
    return {(c.id,m):(c,m) for c in fixtures(6) for m in ('raw','neutral','bound')}

def strict(raw):
    def unique(fields):
        d=dict(fields)
        if len(d)!=len(fields):raise ValueError('duplicate keys')
        return d
    try:
        x=json.loads(raw,object_pairs_hook=unique)
        if x=={'abstain':True} and type(x.get('abstain')) is bool:return None,None
        if type(x) is dict and set(x)=={'attempt','cap'} and type(x['attempt']) is str and type(x['cap']) is int:
            return x['attempt'],x['cap']
    except (ValueError,TypeError):pass
    raise ValueError('strict response must be a single object')

def export():
    for key,(c,m) in model_cases().items():
        print(json.dumps(dict(case=key[0],mode=m,prompt=prompt(c,m),
                              do_sample=False,max_new_tokens=96),ensure_ascii=True))

def score_responses():
    observed={}
    for row in sys.stdin:
        x=json.loads(row)
        key=x['case'],x['mode']
        if key in observed or key not in model_cases():raise ValueError('unknown or repeated response ID')
        observed[key]=x['response']
    out={m:Counter() for m in ('raw','neutral','bound')}
    for key,(c,m) in model_cases().items():
        r=out[m]
        if key not in observed:r.update(['omitted','cases']);continue
        con=db(c)
        try:
            pick,cap=strict(observed[key])
            label=score(c,pick,cap,con)
        except ValueError:label='invalid'
        finally:con.close()
        r.update([label,'cases'])
    print(json.dumps(dict(results=out),sort_keys=True,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('mode',nargs='?',default='ablation',choices=('ablation','export-prompts','score-responses'))
    mode=p.parse_args().mode
    {'ablation':benchmark,'export-prompts':export,'score-responses':score_responses}[mode]()
