"""Budget/access measurement on real SQLite savepoints and injected adapter faults."""
from collections import Counter
from itertools import product
from pathlib import Path
import hashlib
import json
import random
import sqlite3
import sys

from history_relation_policy import features

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runs_empirical_study_20261124'
OLD=ROOT/'runs_history_relation_20261124'
MENUS={'basic':('getA','addA','mark','undo'),
       'extended':('getA','addA','mark','undo','getB','addB','release')}
FAULTS=('stale_read','wrong_row','undo_ignored','release_reverts','outer_rollback')
MUTANTS=('highA','highB','lost_writes','swapped_read','double_write','clear_on_mark')


def save(name,value):
    OUT.mkdir(exist_ok=True)
    (OUT/name).write_text(json.dumps(value,indent=1,ensure_ascii=False),encoding='utf8')


def initial(layout):
    rng=random.Random(115077+layout)
    return (rng.randrange(1,101),rng.randrange(200,301))


def predict(seq,values,mutation=None):
    values=list(values)
    marks=[]
    out=[]
    for q in seq:
        i=int(q.endswith('B'))
        if q.startswith('get'):
            j=1-i if mutation=='swapped_read' else i
            out.append(values[j]+int(mutation=='high'+q[-1]))
            continue
        if q.startswith('add') and mutation!='lost_writes':
            values[i]+=1+int(mutation=='double_write')
        elif q=='mark' and len(marks)<2:
            marks.append(values[:])
            if mutation=='clear_on_mark':
                values=[0,0]
        elif marks and q=='undo':
            values=marks[-1][:]
        elif marks and q=='release':
            marks.pop()
        out.append('ok')
    return out


def execute(seq,values,fault,expected):
    db=sqlite3.connect(':memory:',isolation_level=None)
    try:
        db.execute('CREATE TABLE ledger(id TEXT PRIMARY KEY, v INTEGER)')
        db.executemany('INSERT INTO ledger VALUES(?,?)',zip('AB',values))
        depth=0
        cache={}
        out=[]
        for q,target in zip(seq,expected):
            y='ok'
            if q.startswith('get'):
                y=db.execute('SELECT v FROM ledger WHERE id=?',(q[-1],)).fetchone()[0]
                if fault=='stale_read':
                    y=cache.setdefault(q[-1],y)
            elif q.startswith('add'):
                key='A' if q=='addB' and fault=='wrong_row' else q[-1]
                db.execute('UPDATE ledger SET v=v+1 WHERE id=?',(key,))
            elif q=='mark' and depth<2:
                depth+=1
                db.execute(f'SAVEPOINT s{depth}')
                cache.clear()
            elif q=='undo' and depth and fault!='undo_ignored':
                if fault=='outer_rollback':
                    depth=1
                db.execute(f'ROLLBACK TO s{depth}')
                cache.clear()
            elif q=='release' and depth:
                if fault=='release_reverts':
                    db.execute(f'ROLLBACK TO s{depth}')
                db.execute(f'RELEASE s{depth}')
                depth-=1
                cache.clear()
            out.append(y)
            if y!=target:
                break
        return out
    finally:
        db.close()


def witnesses(menu):
    # A wrong-row write and a reverting release require the missing public operation.
    blocked={f for f,q in [('wrong_row','addB'),('release_reverts','release')] if q not in menu}
    remaining=set(FAULTS)-blocked
    seen={}
    resets=calls=0
    for length in range(1,6):
        for seq in product(menu,repeat=length):
            if not remaining:
                break
            target=predict(seq,initial(0))
            for f in sorted(remaining):
                out=execute(seq,initial(0),f,target)
                resets+=1
                calls+=len(out)
                if out!=target:
                    seen[f]=list(seq)
                    remaining.remove(f)
    assert not remaining
    return dict(witness=seen,blocked=sorted(blocked),oracle_calls=calls,oracle_resets=resets)


def encoded(seq):
    return tuple((q,q,q[:3] if q.startswith(('get','add')) else q) for q in seq)


def plans(layout,menu,accounts,weights,backoff):
    rng=random.Random(441190+layout)
    seqs=list(product(menu,repeat=3))
    rng.shuffle(seqs)
    values=initial(layout)
    def killed(s):
        y=predict(s,values)
        return sum(predict(s,values,m)!=y for m in MUTANTS)/len(MUTANTS)
    kills={s:killed(s) for s in seqs}
    hist={}
    relations={}
    for s in seqs:
        v=encoded(s)
        fs=features(v[:2])+features(v)
        relations[s]=fs
        hist[s]=sum(weights.get(f,backoff[len(f[1])])/backoff[len(f[1])]/
                    (1+accounts[f])**0.5 for f in fs)/len(fs)
    scale=max(hist.values())
    joint=max(seqs,key=lambda s:kills[s]+hist[s]/scale)
    accounts.update(relations[joint])
    aba=max((s for s in seqs if s[0]==s[2]!=s[1]),key=kills.get)
    # Classical state-cover access sequences for public depth 0, 1 and 2; random suffix.
    depth=layout%3
    access=('mark',)*depth
    return {'ABA':aba+tuple(rng.choices(menu,k=2)),
            'state_prefix':access+tuple(rng.choices(menu,k=5-depth)),
            'random':tuple(rng.choices(menu,k=5)),'joint_3':joint}


def main():
    dev=json.loads((OLD/'development.json').read_text())
    digest=hashlib.sha256(Path(__file__).with_name('history_relation_policy.py').read_bytes()).hexdigest()
    assert dev['policy_sha256']==digest
    weights={(r['channel'],r['pattern']):r['weight'] for r in dev['estimates']}
    backoff={}
    for n in (2,3):
        subset=[r for r in dev['estimates'] if r['channel']=='wire' and len(r['pattern'])==n]
        backoff[n]=(1+sum(r['hits'] for r in subset))/(2+sum(r['n'] for r in subset))
    traces=[]
    certs={}
    for perm,menu in MENUS.items():
        certs[perm]=witnesses(menu)
        replay=[]
        account=Counter()
        for layout in range(36):
            vals=initial(layout)
            for f,s in certs[perm]['witness'].items():
                y=predict(s,vals)
                out=execute(s,vals,f,y)
                assert out[:-1]==y[:-1] and out[-1]!=y[-1]
                replay.append(dict(layout=layout,fault=f,seq=s,expected=y,observed=out))
            for method,s in plans(layout,menu,account,weights,backoff).items():
                y=predict(s,vals)
                for f in ('stable',*FAULTS):
                    out=execute(s,vals,f,y)
                    hit=len(out) if out!=y else None
                    if hit:
                        assert f!='stable' and len(certs[perm]['witness'][f])<=hit
                    traces.append(dict(layout=layout,permission=perm,method=method,fault=f,
                                       plan=s,expected=y,observed=out,first_difference=hit))
        certs[perm]['replays']=replay
    save('sqlite_witnesses.json',certs)
    save('sqlite_traces.json',traces)
    save('versions.json',dict(python=sys.version,sqlite=sqlite3.sqlite_version,policy_sha256=digest))


if __name__=='__main__':
    main()
