"""Pure stdlib, Python 3. Generate synthetic fixtures; evaluate offline trace policies."""
from collections import Counter, defaultdict
from html import escape, unescape
from itertools import permutations
import json, random, unicodedata
from urllib.parse import quote, unquote
from pathlib import Path
ORDERS=tuple(permutations(range(4)))
POLICIES=('shuffle','forward','two_ended')
BUDGET=6

def fn(k,s):
    return (unescape, unquote, lambda a:unicodedata.normalize('NFKC',a),
            lambda a:' '.join(a.split()))[k](s)

def doc(rng):
    raw=['\u3000Ａ＆Ｂ  ','  tea & cake ','50%  off','\t＜3\t','Ｃafé  １２','Ａ＆amp；Ｂ','%４１  ','A\u00a0\u00a0B','Ａ&#x3000;Ｂ']
    def transform(s):
        for _ in range(rng.randrange(1,5)):
            k=rng.randrange(4)
            if k==0:s=escape(s)
            if k==1:s=quote(s,safe='')
            if k==2:s=''.join(chr(ord(a)+65248) if 33<=ord(a)<=126 and rng.random()<.55 else a for a in s)
            if k==3:s=' '+s+'\t'
        return s
    return tuple(transform(rng.choice(raw)) for _ in range(4))

def observe(order, start, mapping):
    # One call; full snapshots after each module, including any no-ops.
    out=[start]
    for a in order:
        out.append(tuple(fn(mapping[a],s) for s in out[-1]))
    return tuple(out)

def run(start,goal,orders,policy,query):
    edge={}; rev=defaultdict(set); asked=set()
    for calls in range(1,BUDGET+1):
        scores=[]
        for rank,p in enumerate(orders):
            if p in asked:continue
            if policy=='shuffle':
                scores.append(((0,-rank),p));continue
            st=start; pref=0
            for a in p:
                if (a,st) not in edge:break
                st=edge[a,st];pref+=1
            ends={goal}; suffix=0; end_at={len(p):ends}
            for idx in reversed(range(len(p))):
                a=p[idx]; nxt=set()
                for s in ends:nxt.update(rev.get((a,s),()))
                if not nxt:break
                ends=nxt; suffix+=1;end_at[idx]=ends
            certified=(pref==len(p) and st==goal)
            assert certified == (start in end_at.get(0,()))
            if pref==len(p) and not certified:continue
            if policy=='two_ended':
                # Overlapping known prefix/suffix with incompatible states is not a certified join.
                # A zero-gap overlap that fails to meet still needs at least one unseen edge.
                extent=min(len(p)-1,pref+suffix) if not certified else len(p)
            else:extent=pref
            scores.append(((int(certified),extent,-rank),p))
        if not scores:return None,calls-1
        p=max(scores)[1];asked.add(p)
        trace=query(p)
        for a,u,v in zip(p,trace,trace[1:]):
            assert (a,u) not in edge or edge[a,u]==v
            edge[a,u]=v;rev[a,v].add(u)
        if trace[-1]==goal:return p,calls
    return None,BUDGET

def main():
    totals={p:Counter() for p in POLICIES}; paired=Counter()
    for i in range(240):
        rng=random.Random(20261125+i);mapping=list(range(4));rng.shuffle(mapping)
        hidden=rng.choice(ORDERS);start=doc(rng);sealed=[doc(rng) for _ in range(8)]
        goal=observe(hidden,start,mapping)[-1]
        orders=list(ORDERS);rng.shuffle(orders);success={}
        for name in POLICIES:
            p,n=run(start,goal,orders,name,lambda p:observe(p,start,mapping))
            ok=p is not None and all(observe(p,x,mapping)[-1]==observe(hidden,x,mapping)[-1] for x in sealed)
            totals[name].update(calls=n, calibration=int(p is not None), full=int(ok),
                                wrong_transfer=int(p is not None and not ok))
            success[name]=ok
        paired['two_only' if success['two_ended'] and not success['forward'] else
               'forward_only' if success['forward'] and not success['two_ended'] else
               'both' if success['forward'] else 'neither']+=1
    print(json.dumps(dict(fixtures=240,totals=totals,paired=paired),indent=2,sort_keys=True))
if __name__=='__main__': main()
