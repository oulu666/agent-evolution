"""Synthetic inventory session, held-out mechanisms and independent witness audit."""
from collections import Counter
from itertools import product
from pathlib import Path
import hashlib
import json
import random
import time

from history_relation_policy import METHODS,choose_all,development,features,reference

OUT=Path(__file__).resolve().parents[1]/'runs_history_relation_20261124'
FAULTS=('alias_reservation','scope_price','double_select','aisle_cursor','deferred_commit')


def save(name,obj):
    OUT.mkdir(exist_ok=True)
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=1),encoding='utf8')


def fixture(layout,perm):
    rng=random.Random(982415+layout)
    levels=rng.sample(range(10,98),8)
    stock=(levels[:4],levels[4:])
    def request(op,v,alternate=False):
        wire=f'{op}?id={v:02}' if alternate else f'{op}?id={v}'
        return wire,(op,v),op
    # Alternate spelling normalizes to the same integer. Scope is session-local in both permissions.
    ids=rng.sample(range(4),2)
    menu=[request('select',v) for v in (0,1)]+[request('stock',v) for v in ids]
    if layout%3:
        menu.append(request('stock',ids[0],True))
    if perm=='construct':
        menu=[request('select',v) for v in (0,1)]+[request('stock',v,a) for v in range(4) for a in (False,True)]
    return menu,stock


class Session:
    def __init__(self,stock,fault):
        self.stock=stock
        self.scope=0
        self.fault=fault
        self.log=[]

    def call(self,req):
        wire=req[0]
        op,number=wire.split('?id=')
        v=int(number)
        hist=self.log
        prev=self.scope
        if op=='select':
            self.scope=v
            answer=('selected',v)
        else:
            qty=self.stock[self.scope][v]
            if self.fault=='alias_reservation' and hist and hist[-1][1:3]==('stock',v) and hist[-1][0]!=wire:
                qty-=1
            if self.fault=='scope_price' and len(hist)>=2:
                a,b=hist[-2:]
                if a[1:3]==('stock',v) and b[1]=='select' and b[3]!=self.scope:
                    qty=self.stock[b[3]][v]
            if self.fault=='double_select' and len(hist)>=2 and hist[-1][1]=='select' and hist[-2][1:3]==hist[-1][1:3]:
                qty=0
            if self.fault=='aisle_cursor' and hist and hist[-1][1]=='stock':
                other=hist[-1][2]
                if other!=v and other//2==v//2:
                    qty=self.stock[self.scope][other]
            if self.fault=='deferred_commit' and len(hist)>=3:
                a,b,c=hist[-3:]
                if a[1]==b[1]=='stock' and a[2]!=b[2] and c[1]=='select' and c[3]!=self.scope:
                    qty=self.stock[c[3]][v]
            answer=('stock',qty)
        hist.append((wire,op,v,prev))
        return answer


def play(stock,fault,seq,expected):
    session=Session(stock,fault)
    out=[]
    for q,y in zip(seq,expected):
        out.append(session.call(q))
        if out[-1]!=y:
            return True,out
    return False,out


def frontier(menu,stock):
    start=time.process_time()
    calls=resets=0
    found={}
    counts=Counter()
    for seq in product(menu,repeat=3):
        expected=reference(seq,stock)
        for fault in FAULTS:
            bad,obs=play(stock,fault,seq,expected)
            calls+=len(obs)
            resets+=1
            if bad:
                counts[fault]+=1
                if fault not in found or len(found[fault])>len(obs):
                    found[fault]=[q[0] for q in seq[:len(obs)]]
    three_cpu=time.process_time()-start
    missing=set(FAULTS)-found.keys()
    extra_calls=extra_resets=0
    for seq in product(menu,repeat=4):
        if not missing:
            break
        expected=reference(seq,stock)
        for fault in tuple(missing):
            bad,obs=play(stock,fault,seq,expected)
            extra_calls+=len(obs)
            extra_resets+=1
            if bad:
                found[fault]=[q[0] for q in seq[:len(obs)]]
                missing.remove(fault)
    return dict(witness=found,counts=dict(counts),unreachable=sorted(missing),
                exhaustive_three_calls=calls,exhaustive_three_resets=resets,three_cpu=three_cpu,
                fourth_audit_calls=extra_calls,fourth_audit_resets=extra_resets)


def main():
    weights,pooled,dev=development()
    dev['policy_sha256']=hashlib.sha256(Path(__file__).with_name('history_relation_policy.py').read_bytes()).hexdigest()
    save('development.json',dev)
    decisions=[]
    witnesses=[]
    plans=[]
    for perm in ('saved','construct'):
        accounts={m:Counter() for m in METHODS}
        for layout in range(60):
            menu,stock=fixture(layout,perm)
            cpu=time.process_time()
            picks,info=choose_all(menu,stock,layout,accounts,weights,pooled)
            info['combined_policy_cpu']=time.process_time()-cpu
            plans.append(dict(layout=layout,perm=perm,**info,plans={m:dict(seq=[r[0] for r in s],
                fraction_mutants=k,select_seconds=t) for m,(s,k,t) in picks.items()}))
            witness=frontier(menu,stock)
            witnesses.append(dict(layout=layout,perm=perm,**witness))
            for m,(seq,kill,_) in picks.items():
                expected=reference(seq,stock)
                for fault in ('stable',*FAULTS):
                    bad,obs=play(stock,fault,seq,expected)
                    w=witness['witness'].get(fault,[])
                    assert not bad or 0<len(w)<=3
                    assert not (fault=='stable' and bad)
                    decisions.append(dict(layout=layout,perm=perm,method=m,fault=fault,hit=bad,
                        reachable=0<len(w)<=3,confidence=kill,queries=[q[0] for q in seq[:len(obs)]],
                        expected=expected[:len(obs)],actual=obs,relation=features(seq),calls=len(obs)))
    save('decisions.json',decisions)
    save('frontier.json',witnesses)
    save('plans.json',plans)
    print(len(decisions),'executed episodes')


if __name__=='__main__':
    main()
