"""Real SQLite recovery, finite-horizon CPU fitted Q."""
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
import json
import random
import sqlite3

COST=dict(verify=140,plain_retry=220,idempotent_retry=260,defer=450,accept=0)
PENALTY=3000
FEATURES=('history','terminal_only','shuffle')
POLICIES=FEATURES+('native_robust','native_cost','oracle')
LABELS=('prepared','durable','opaque')

@dataclass(frozen=True)
class Case:
    idem:bool
    trust:bool
    note:str
    initial:bool

@dataclass(frozen=True)
class Obs:
    left:int
    idem:bool
    trust:bool
    note:str
    known:int|None

def fixture(r,prob):
    idem,trust=(r.random()<.5 for _ in range(2))
    note=r.choice(LABELS)
    known=trust and note!='opaque'
    initial=(note=='durable') if known else r.random()<prob
    return Case(idem,trust,note,initial)

def open_episode(f):
    con=sqlite3.connect(':memory:',isolation_level=None)
    con.execute('CREATE TABLE tickets(row INTEGER PRIMARY KEY, request INTEGER)')
    # A real pre-recovery effect, with withheld application receipt.
    con.execute('BEGIN')
    con.execute('INSERT INTO tickets(request) VALUES (1)')
    con.execute('COMMIT' if f.initial else 'ROLLBACK')
    return Obs(2,f.idem,f.trust,f.note,None),con

def acts(o):
    return ('accept','plain_retry','defer')+(
        ('idempotent_retry',) if o.idem else ())+ (('verify',) if o.left>1 else ())

def step(o,a,c):
    assert a in acts(o)
    if a=='verify':
        n=c.execute('SELECT count(*) FROM tickets WHERE request=1').fetchone()[0]
        return replace(o,left=o.left-1,known=n),COST[a],None
    if a in ('plain_retry','idempotent_retry'):
        c.execute('BEGIN IMMEDIATE')
        if a=='plain_retry':
            c.execute('INSERT INTO tickets(request) VALUES(1)')
        else:
            c.execute('INSERT INTO tickets(request) SELECT 1 WHERE NOT EXISTS'
                      '(SELECT 1 FROM tickets WHERE request=1)')
        c.execute('COMMIT')
    n=c.execute('SELECT count(*) FROM tickets WHERE request=1').fetchone()[0]
    wrong=a!='defer' and n!=1
    return None,COST[a]+PENALTY*wrong,dict(
        false_confirmation=int(wrong), duplicate_rows=max(0,n-1),
        delivered_correctly=int(a!='defer' and n==1), deferred=int(a=='defer'))

def logs():
    r=random.Random(86107)
    all_logs=[]
    for _ in range(6000):
        f=fixture(r,.5)
        obs,c=open_episode(f)
        episode=[]
        while obs:
            a=r.choice(acts(obs))
            nxt,cost,_=step(obs,a,c)
            episode.append((obs,a,cost,nxt))
            obs=nxt
        c.close()
        all_logs.append(episode)
    return all_logs

def shuffle_labels(raw):
    groups=defaultdict(list)
    r=random.Random(4411)
    for i,e in enumerate(raw):
        ob=e[0][0]
        groups[ob.idem,ob.trust].append(i)
    out=list(raw)
    for g in groups.values():
        notes=[raw[i][0][0].note for i in g]
        r.shuffle(notes)
        for i,note in zip(g,notes,strict=True):
            out[i]=[(replace(o,note=note),a,c,replace(n,note=note) if n else None)
                    for o,a,c,n in raw[i]]
    return out

def feat(o,method):
    return (o.left,o.idem,o.trust,o.note if method!='terminal_only' else 'none',o.known)

def fit(raw,method):
    d={}
    data=shuffle_labels(raw) if method=='shuffle' else raw
    for horizon in (1,2):
        costs=defaultdict(list)
        for episode in data:
            for obs,a,cost,nxt in episode:
                if obs.left!=horizon:continue
                est=0 if not nxt else min(d.get((feat(nxt,method),an),4500) for an in acts(nxt))
                costs[feat(obs,method),a].append(cost+est)
        d.update({k:sum(v)/len(v) for k,v in costs.items()})
    return d

def native(o,method,f):
    known=o.known
    if known is None:
        if method=='oracle':known=int(f.initial)
        elif o.trust and o.note!='opaque':known=int(o.note=='durable')
    if known is not None:return 'accept' if known else 'plain_retry'
    if o.idem and method=='native_robust':return 'idempotent_retry'
    if o.idem and COST['idempotent_retry']<COST['verify']+.5*COST['plain_retry']:return 'idempotent_retry'
    return 'verify'

def deploy(f,p,fitted):
    obs,c=open_episode(f)
    counter=Counter(cases=1,summed_cost=0,calls=0,probe=0,plain=0,idem=0,accounting_error=0,
                    false_confirmation=0,duplicate_rows=0,delivered_correctly=0,deferred=0)
    while obs:
        if p in FEATURES:
            tab=fitted[p]
            a=min(acts(obs),key=lambda k:tab.get((feat(obs,p),k),450 if k=='defer' else 4500))
        else:a=native(obs,p,f)
        obs,units,d=step(obs,a,c)
        counter.update(summed_cost=units,calls=int(a not in ('accept','defer')),probe=int(a=='verify'),
                       plain=int(a=='plain_retry'),idem=int(a=='idempotent_retry'))
        if d:counter.update(d)
    actual=c.execute('SELECT request FROM tickets ORDER BY row').fetchall()
    c.close()
    assert all(x==(1,) for x in actual)
    assert counter['duplicate_rows']==max(0,len(actual)-1)
    assert counter['delivered_correctly']+counter['deferred']+counter['false_confirmation']==1
    return counter

def main():
    tr=logs()
    fitters={m:fit(tr,m) for m in FEATURES}
    results={}
    for j,(generating,p) in enumerate([('balanced',.5),('mostly_committed',.8),('mostly_rolled_back',.2)]):
        r=random.Random(921243+j)
        test=[fixture(r,p) for _ in range(360)]
        tab={name:Counter() for name in POLICIES}
        for name in POLICIES:
            for item in test:tab[name].update(deploy(item,name,fitters))
        results[generating]=tab
    print(json.dumps(dict(sqlite=sqlite3.sqlite_version,training_episodes=len(tr),
                          training_steps=sum(map(len,tr)),action_value_cells={m:len(t) for m,t in fitters.items()},
                          results=results),sort_keys=True,indent=2))

if __name__=='__main__':main()
