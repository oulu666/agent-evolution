"""Public calibration sandbox, hidden calendar implementations and typed rule language."""
import itertools
import json
import random
import re
from pathlib import Path

from semantic_extension_bank import fixture, NAMES, STATES

OUT=Path(__file__).resolve().parents[1]/'runs_risk_completion_20261123'
OUT.mkdir(exist_ok=True)
FAMILIES=(('uid','owner','row'),('drop0','drop1','drop2'),('rank_up','rank_down','id_up','id_down'))
PAGE='page'
SLICE=re.compile(r's\((-?\d*),(-?\d*),(-?\d*)\)')


def save(name,obj):
    dest=OUT/name
    tmp=dest.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf8')
    tmp.replace(dest)


def pool():
    small=[(op,PAGE) for family in FAMILIES for op in family]
    small += [(PAGE,op) for family in FAMILIES[:2] for op in family]
    wide=[]
    for selected in itertools.product(*[(None,*family) for family in FAMILIES]):
        ops=[x for x in selected if x]
        if ops:
            wide.extend(itertools.permutations([*ops,PAGE]))
    slices=[(f's({start},,{step})',PAGE) for start in ('',0,1,2,3,-1) for step in (1,2,3,-1)]
    return list(dict.fromkeys(small)),list(dict.fromkeys(wide)),list(dict.fromkeys(slices))


def normalize(records,alias):
    names=NAMES[alias]
    return [tuple(r[k] if i!=3 else STATES[alias].index(r[k]) for i,k in enumerate(names)) for r in records]


def family(rule):
    for op in rule:
        if op!=PAGE:
            return next((n for n,f in zip(('unique','filter','tie'),FAMILIES) if op in f),'slice')
    return 'base'


def run(rows,rule):
    seq=sorted(rows,key=lambda r:r[1])
    for op in rule:
        if op==PAGE:
            seq=seq[:3]
        elif op in FAMILIES[0]:
            seen={}
            for r in seq:
                key=r if op=='row' else r[0 if op=='uid' else 2]
                seen.setdefault(key,r)
            seq=list(seen.values())
        elif op in FAMILIES[1]:
            seq=[r for r in seq if r[3]!=int(op[-1])]
        elif op in FAMILIES[2]:
            k=4 if op.startswith('rank') else 0
            seq=sorted(sorted(seq,key=lambda r:r[k],reverse=op.endswith('down')),key=lambda r:r[1])
        else:
            args=SLICE.fullmatch(op).groups()
            seq=seq[slice(*(int(v) if v else None for v in args))]
    return tuple(r[0] for r in seq)


def endpoint(rows,kind,i):
    # Implement the environment separately from the rule interpreter.
    seq=sorted(rows,key=lambda r:r[1])
    def first_by(seq,k):
        return [r for j,r in enumerate(seq) if all(v[k]!=r[k] for v in seq[:j])]
    if kind=='simple':
        result=[first_by(seq,0)[:3], [r for r in seq if r[3]!=1][:3],
                sorted(seq,key=lambda r:(r[1],-r[4]))[:3]][i]
    elif kind=='compound':
        if i==0:
            result=first_by([r for r in seq if r[3]!=2],2)[:3]
        elif i==1:
            result=[r for r in sorted(seq,key=lambda r:(r[1],r[4]))[:3] if r[3]!=1]
        else:
            result=first_by(sorted(seq,key=lambda r:(r[1],-r[4]))[:3],0)
    else:
        result=[seq[1:4],[r for j,r in enumerate(seq) if j%2==0][:3],list(reversed(seq))[:3]][i]
    return tuple(r[0] for r in result)


def focused(seed,i):
    rng=random.Random(seed)
    labels=rng.sample(list('ABCDEFGHIJKLMNOPQRSTUVWX'),7)
    rows=[(labels[j],j//2,chr(65+j),j%3,7-j) for j in range(7)]
    if i==0: # Independent identifiers, shared owner.
        rows=[(x,t,'M' if j<3 else g,s,r) for j,(x,t,g,s,r) in enumerate(rows)]
    elif i==1: # Same identifier, independent owners.
        rows=[(labels[0] if j<3 else x,t,g,s,r) for j,(x,t,g,s,r) in enumerate(rows)]
    elif i==2:
        rows=[(x,0,g,s,r) for x,t,g,s,r in rows]
    elif i==3:
        rows=[(x,t,g,1 if j<3 else 2,r) for j,(x,t,g,s,r) in enumerate(rows)]
    elif i==4:
        rows=[(x,t,g,2 if j<2 else 0,r) for j,(x,t,g,s,r) in enumerate(rows)]
    elif i==5:
        rows=rows[:2]
    elif i==6:
        rows=[(x,j,g,0,r) for j,(x,t,g,s,r) in enumerate(rows)]
    rng.shuffle(rows)
    return rows


def layouts():
    for idx in range(24):
        alias=idx%2
        seed=930000+1000*idx
        raw=fixture(seed,alias)
        bank=[normalize(fixture(seed+j,alias),alias) for j in range(1,9)]
        bank += [focused(seed+50+j,j) for j in range(7)]
        held=[normalize(fixture(seed+100+j,alias),alias) for j in range(24)]
        held += [focused(seed+210+j,j) for j in range(7)]
        yield idx,alias,raw,normalize(raw,alias),bank,held


def prompt(rows,obs):
    return ('Infer a calendar rule from the actual returned IDs. Rows are [id,time,owner,status,rank]. '
            'Start in stable ascending time order. Return a space-separated pipeline with exactly one page operation '
            '(keep first 3). Operations execute left to right. uid/owner/row keep first per ID/owner/whole row. '
            'drop0/drop1/drop2 remove that status. rank_up/rank_down/id_up/id_down order time ties by that field. '
            's(start,stop,step) slices the current list; omitted bounds are empty. '
            'You may compose operations. Give only the pipeline. Rows='+json.dumps(rows,separators=(',',':'))+
            ' Actual IDs='+json.dumps(obs))


def parse(raw):
    text=raw.strip().strip('`').strip()
    tokens=tuple(text.split())
    if not 1<=len(tokens)<=5 or tokens.count(PAGE)!=1:
        return None
    for op in tokens:
        if op==PAGE or any(op in f for f in FAMILIES):
            continue
        m=SLICE.fullmatch(op)
        if not m or any(len(a)>4 for a in m.groups()) or (m[3] and int(m[3])==0):
            return None
    return tokens
