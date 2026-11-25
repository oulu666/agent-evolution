"""Intervention-certified transfer between tested SQLite and pandas public APIs."""
from collections import Counter, defaultdict
from dataclasses import dataclass
import itertools as it
import json
import random
import sqlite3

import pandas as pd

@dataclass(frozen=True)
class Row:
    id:str
    key:tuple[str|None,str|None]
    payload:str|None

def bits(key):return sum((x is None)<<i for i,x in enumerate(key))

def source_backend(left,right,policy):
    with sqlite3.connect(':memory:') as c:
        c.executescript('CREATE TABLE lhs(id,k0,k1,payload); CREATE TABLE rhs(id,k0,k1,payload); '
                        'CREATE TABLE allowed(pattern INTEGER);')
        c.executemany('INSERT INTO allowed VALUES(?)',((m,) for m in policy))
        for table,rows in [('lhs',left),('rhs',right)]:
            c.executemany(f'INSERT INTO {table} VALUES(?,?,?,?)',((r.id,*r.key,r.payload) for r in rows))
        return Counter(c.execute('''SELECT l.id,r.id FROM lhs l LEFT JOIN rhs r
                ON l.k0 IS r.k0 AND l.k1 IS r.k1 AND ((r.k0 IS NULL)+2*(r.k1 IS NULL))
                IN (SELECT pattern FROM allowed)'''))

def key_for(p,pfx):
    return tuple(None if p&(1<<i) else f'{pfx}-{p}-{i}' for i in range(2))

def certify(run):
    lhs=[Row('anchor-'+str(p),key_for(p,'src'),str(p)) for p in range(4)]
    # At least one key is nonmissing on this distractor, so no both-missing anchor can match.
    base=[Row('unrelated',('distractor-a','distractor-b'),None)]
    injected=[Row('inject-'+str(p),key_for(p,'src'),None) for p in range(4)]
    before=run(lhs,base)
    after=run(lhs,base+injected)
    assert before==Counter((r.id,None) for r in lhs)
    add=after-before
    allowed=frozenset(p for p in range(4) if add['anchor-'+str(p),'inject-'+str(p)]==1)
    assert sum(add.values())==len(allowed)
    return allowed

def make_target(j):
    rng=random.Random(683+j)
    left=[];right=[]
    for p in range(4):
        a=key_for(p,'target-'+str(j))
        left.extend([Row(f'l-{p}-{k}',a,None if k==0 else 'given') for k in (0,1)])
        right.extend([Row(f'r-{p}-{k}',a,None if k==0 else 'stored') for k in range(1+j%3)])
    left.append(Row('l-no-match',(f'missing-{j}',None),None))
    right.append(Row('r-no-match',(f'irrelevant-{j}',None),None))
    rng.shuffle(left);rng.shuffle(right)
    return left,right

def app_oracle(left,right,policy):
    result=Counter()
    for one in left:
        matches=[other.id for other in right if other.key==one.key and bits(one.key) in policy]
        result.update((one.id,ri) for ri in (matches or [None]))
    return result

def canonical_ir(left,right,allow):
    ind=defaultdict(list)
    for record in right:
        # Canonical typed null-safe products, restricted to authorized patterns.
        if bits(record.key) in allow:ind[record.key].append(record.id)
    return Counter((row.id,rid) for row in left for rid in (ind.get(row.key) or [None]))

def frames(left,right):
    # Layout and column names deliberately differ from source physical schema.
    l=pd.DataFrame(([r.key[1],r.payload,r.id,r.key[0]] for r in left),
                   columns=['dest_type','unrelated_left','lid','zone'])
    r=pd.DataFrame(([r.payload,r.key[0],r.id,r.key[1]] for r in right),
                   columns=['memo_unused','prov','rid','family'])
    return l,r

def merge(l,r):
    out=pd.merge(l,r,how='left',left_on=['zone','dest_type'],right_on=['prov','family'])
    return Counter((a,None if pd.isna(b) else b) for a,b in zip(out.lid,out.rid,strict=True))

def transport(left,right,allow):
    # Contract compiler: null-pattern certificate prunes right candidates, not preserved left records.
    return merge(*frames(left,[r for r in right if bits(r.key) in allow]))

def native(left,right,allow):
    # Native pandas prefilter: derive allowed rows without looping over target artifacts.
    l,r=frames(left,right)
    pattern=r.prov.isna().astype('int8')+2*r.family.isna().astype('int8')
    return merge(l,r.loc[pattern.isin(allow)])

def classify(allow):
    return frozenset([0]+[i for i in (1,2) if i in allow]+([3] if {1,2}<=allow else []))

def main():
    nested={}
    profiles={}
    for prefix in it.product((0,1),repeat=3):
        policy=frozenset((0,*(i+1 for i,t in enumerate(prefix) if t)))
        cert=certify(lambda a,b:source_backend(a,b,policy))
        assert cert==policy
        category='separable' if classify(policy)==policy else 'interaction'
        profiles[str(sorted(policy))]=dict(family=category,source_discovered=sorted(cert))
        table=nested.setdefault(category,{k:Counter() for k in
                    ('raw_pandas','default_sql_adapter','axiswise','transport','native','canonical_ir')})
        for j in range(12):
            l,r=make_target(j)
            expected=app_oracle(l,r,policy)
            choices=dict(raw_pandas=merge(*frames(l,r)),
                         default_sql_adapter=native(l,r,frozenset({0})),
                         axiswise=native(l,r,classify(cert)),
                         transport=transport(l,r,cert),
                         native=native(l,r,cert),
                         canonical_ir=canonical_ir(l,r,cert))
            for name,val in choices.items():
                table[name].update(reports=1,correct=val==expected,
                                   missing_matches=sum((expected-val).values()),
                                   excess_matches=sum((val-expected).values()))
    print(json.dumps(dict(pandas=pd.__version__,sqlite=sqlite3.sqlite_version,
                          source_reads=2*len(profiles),source_injected_rows=4*len(profiles),
                          profiles=profiles,results=nested),sort_keys=True,indent=2))

if __name__=='__main__':main()
