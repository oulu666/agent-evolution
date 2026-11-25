"""Reproducible native transactional-admission pilot; external dependencies: none."""
import itertools as it
import json
import sqlite3
from collections import Counter
from dataclasses import dataclass

@dataclass(frozen=True)
class Case:
    group:str
    fixture:int
    engine_fk:bool
    parent_exists:bool
    quota:int|None
    qty:int
    initial:int
    visible_initial:bool

POLICIES=('staging_only','verify_all','proof_gate','native')

def generate():
    cases=[]
    configurations=(
        ('reference',it.product((0,1),(0,1),(0,1),(0,),(-1,0,1))),
        ('quota',it.product((0,),(1,),(0,1),(1,),(-1,0,1))),
        ('composed_holdout',it.product((0,1),(0,1),(0,1),(1,),(-1,0,1))),
    )
    for group,scenarios in configurations:
        for i,(engine,parent,visible,quota_enabled,diff) in enumerate(scenarios):
            qty=4+(i//3)%3+(11 if group=='composed_holdout' else 0)
            lim=(250 if group=='composed_holdout' else 100) if quota_enabled else None
            initial=lim-qty-diff if quota_enabled else 0
            cases.append(Case(group,len(cases),bool(engine),bool(parent),lim,qty,initial,bool(visible)))
        # Immediate SQL CHECK must catch negative quantity even with good parent.
        cases.append(Case(group,len(cases),True,True,100 if group!='reference' else None,-1,91,True))
    return cases

@dataclass(frozen=True)
class Feedback:
    staged:bool
    managed:bool
    quota:int|None
    initial:int|None
    qty:int

def decide(name,f):
    if not f.staged:return 'rollback',()
    if name=='staging_only':return 'continue',()
    if name=='verify_all':return 'verify',('parent',)+(('quota',) if f.quota is not None else ())
    if name=='proof_gate':
        obligations={'parent':'engine' if f.managed else 'unresolved'}
        if f.quota is not None:
            obligations['quota']='unresolved' if f.initial is None else (
                'proved' if f.initial+f.qty<=f.quota else 'refuted')
        if 'refuted' in obligations.values():return 'rollback',()
        unresolved=tuple(k for k,v in obligations.items() if v=='unresolved')
        return ('verify',unresolved) if unresolved else ('continue',())
    if f.quota is not None and f.initial is not None and f.initial+f.qty>f.quota:
        return 'rollback',()
    pending=(() if f.managed else ('parent',))
    if f.quota is not None and f.initial is None:pending+=('quota',)
    return ('verify',pending) if pending else ('continue',())

def execute(case,name):
    con=sqlite3.connect(':memory:',isolation_level=None)
    counts=Counter(correct=0,wrong_durable=0,unneeded_rollback=0,
                   verifies=0,engine_reject=0,continue_chosen=0,
                   verify_chosen=0,rollback_chosen=0,committed=0)
    try:
        parent=2+case.fixture
        con.execute('PRAGMA foreign_keys='+('ON' if case.engine_fk else 'OFF'))
        assert bool(con.execute('PRAGMA foreign_keys').fetchone()[0])==case.engine_fk
        con.executescript('CREATE TABLE warehouse(id INTEGER PRIMARY KEY);'
                          'CREATE TABLE reservation(ticket INTEGER PRIMARY KEY,'
                          ' warehouse INTEGER REFERENCES warehouse(id) DEFERRABLE INITIALLY DEFERRED,'
                          ' quantity INTEGER NOT NULL CHECK (quantity>=0));')
        con.execute('INSERT INTO warehouse VALUES (?)',(parent,))
        if case.initial:con.execute('INSERT INTO reservation VALUES(0,?,?)',(parent,case.initial))
        if not case.parent_exists:
            # For orphan tests, do not set up pre-existing invalid rows. A fresh unmatched key is used.
            parent+=10000
        con.execute('BEGIN')
        audit_initial=case.initial if case.parent_exists else 0
        # This snapshot read is a common, charged data-acquisition cost for all policies when visible.
        initial_read=(con.execute('SELECT coalesce(sum(quantity),0) FROM reservation WHERE warehouse=?',(parent,)).fetchone()[0]
                      if case.visible_initial else None)
        counts['common_snapshot_reads']=int(case.visible_initial)
        assert initial_read is None or initial_read==audit_initial
        staged=True
        try:
            con.execute('INSERT INTO reservation VALUES(1,?,?)',(parent,case.qty))
        except sqlite3.IntegrityError:
            staged=False
        action,checks=decide(name,Feedback(staged,case.engine_fk,case.quota,initial_read,case.qty))
        counts[action+'_chosen']+=1
        accepted = action!='rollback'
        for check in checks:
            counts['verifies']+=1
            observed=(bool(con.execute('SELECT 1 FROM warehouse WHERE id=?',(parent,)).fetchone())
                      if check=='parent' else con.execute(
                          'SELECT coalesce(sum(quantity),0) FROM reservation WHERE warehouse=?',(parent,)
                      ).fetchone()[0]<=case.quota)
            if not observed:
                accepted=False
                break
        if accepted:
            try:
                con.execute('COMMIT')
                counts['committed']+=1
            except sqlite3.IntegrityError:
                con.execute('ROLLBACK')
                counts['engine_reject']+=1
        else:con.execute('ROLLBACK')
        persisted=con.execute('SELECT quantity FROM reservation WHERE ticket=1').fetchone()
        expected=case.parent_exists and case.qty>=0 and (case.quota is None or audit_initial+case.qty<=case.quota)
        counts['correct']+=bool(persisted)==expected
        counts['wrong_durable']+=bool(persisted) and not expected
        counts['unneeded_rollback']+=not bool(persisted) and expected
        assert not persisted or persisted==(case.qty,)
        return counts
    finally:con.close()

def main():
    all_cases=generate()
    result={}
    for group in ('reference','quota','composed_holdout'):
        cases=[x for x in all_cases if x.group==group]
        reports={}
        for p in POLICIES:
            total=Counter()
            for x in cases:total.update(execute(x,p))
            reports[p]=dict(total)
        result[group]=dict(fixtures=len(cases),by_method=reports)
    print(json.dumps(dict(sqlite=sqlite3.sqlite_version,results=result),indent=2,sort_keys=True))

if __name__=='__main__':main()
