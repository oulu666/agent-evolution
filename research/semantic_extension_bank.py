"""Read-only black-box calendar fixtures and an independent extension interpreter."""
import random
from itertools import product

CAP=3
NAMES=[('id','time','team','state','rank'),('uid','slot','owner','status','priority')]
STATES=[('live','off','hold'),('active','closed','paused')]


def fixture(seed,alias):
    rng=random.Random(seed)
    names=NAMES[alias]
    states=STATES[alias]
    ids=rng.sample(list('ABCDEFGHIJKLMNOPQRSTUVWX'),6)
    return [dict(zip(names,(rng.choice(ids),rng.randrange(4),rng.choice('XYZ'),
                            rng.choice(states),rng.randrange(8)))) for _ in range(10)]


def language(alias):
    uid,_,team,state,rank=NAMES[alias]
    return ([('unique',k,pos) for k,pos in product([uid,team,'row'],['before','after'])]+
            [('exclude',state,v,pos) for v,pos in product(STATES[alias],['before','after'])]+
            [('tie',k,d) for k,d in product([rank,uid],['asc','desc'])])


def base(records,alias):
    uid,when,*_=NAMES[alias]
    return [r[uid] for r in sorted(records,key=lambda r:r[when])[:CAP]]


def run_extension(records,h,alias):
    uid,when,*_=NAMES[alias]
    seq=sorted(records,key=lambda r:r[when])
    op,key,arg=h[:3]
    if op=='tie':
        seq=sorted(sorted(records,key=lambda r:r[key],reverse=arg=='desc'),key=lambda r:r[when])
    else:
        if h[-1]=='after':
            seq=seq[:CAP]
        if op=='unique':
            keep={}
            for r in seq:
                k=tuple(sorted(r.items())) if key=='row' else r[key]
                keep.setdefault(k,r)
            seq=list(keep.values())
        elif op=='exclude':
            seq=[r for r in seq if r[key]!=arg]
    return [r[uid] for r in seq[:CAP]]


def target(records,h,alias):
    uid,when,*_=NAMES[alias]
    result=[]
    visits=0
    for t in sorted({r[when] for r in records}):
        group=[r for r in records if r[when]==t]
        if h[0]=='tie':
            group.sort(key=lambda r:r[h[1]],reverse=h[2]=='desc')
        for row in group:
            visits+=1
            if h[-1]=='after' and visits>CAP:
                break
            if h[0]=='exclude' and row[h[1]]==h[2]:
                continue
            if h[0]=='unique' and any((prev==row if h[1]=='row' else prev[h[1]]==row[h[1]]) for prev in result):
                continue
            result.append(row)
            if len(result)==CAP:
                return [r[uid] for r in result]
    return [r[uid] for r in result]


def programs(alias,split):
    uid,_,team,state,rank=NAMES[alias]
    active,off,hold=STATES[alias]
    if split=='dev':
        return [('unique',uid,'before'),('exclude',state,off,'before'),('tie',rank,'asc')]
    return ([('unique',k,pos) for k,pos in product([uid,team],['before','after'])]+
            [('exclude',state,v,pos) for v,pos in product([off,hold],['before','after'])]+
            [('tie',k,d) for k,d in product([rank,uid],['asc','desc'])])


def in_old_space(records,observed,alias):
    # Test even the more permissive legacy language: any single field/direction/page length.
    uid=NAMES[alias][0]
    return any([r[uid] for r in sorted(records,key=lambda r:r[k],reverse=rev)[:len(observed)]]==observed
               for k,rev in product(NAMES[alias],[False,True]))


def tasks():
    for split in ['dev','final']:
        for layout in range(1 if split=='dev' else 2):
            alias=layout
            for j,h in enumerate(programs(alias,split)):
                seed=(140000 if split=='dev' else 260000)+layout*40000+j*1000
                for offset in range(300):
                    records=fixture(seed+offset,alias)
                    obs=target(records,h,alias)
                    if obs and not in_old_space(records,obs,alias):
                        break
                else:
                    raise RuntimeError(f'No witness for {h}')
                probe=[fixture(seed+400+i,alias) for i in range(8)]
                held=[fixture(seed+600+i,alias) for i in range(16)]
                # A separate simple old-behaviour calendar for regression checking.
                uid,when,team,state,rank=NAMES[alias]
                neutral=[{uid:str(i),when:i,team:str(i),state:STATES[alias][0],rank:i} for i in range(5)]
                assert target(neutral,h,alias)==base(neutral,alias)
                assert all(target(x,h,alias)==run_extension(x,h,alias) for x in [records,*probe,*held])
                yield dict(id=f'{split}-{layout}-{j}',split=split,alias=alias,seed=seed+offset,
                           truth=h,records=records,obs=obs,probe=probe,held=held,neutral=neutral)
