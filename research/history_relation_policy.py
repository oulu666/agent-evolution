"""Calendar development and frozen sequence selection. No inventory faults imported."""
from collections import Counter
from itertools import product
import random

from third_probe_inputs import public,run
from two_step_falsification import backend

PATTERNS = ('AAA','ABA','ABB','ABC','AAB')
METHODS = ('greedy','fixed','w','coverage','learned','joint_uniform','joint')


def partition(values):
    names = {}
    return ''.join(names.setdefault(v,chr(65+len(names))) for v in values)


def features(seq):
    # Wire bytes, normalized request, and semantic operation. Equalities transfer across tools.
    return tuple((name,partition([x[index] for x in seq])) for index,name in
                 ((0,'wire'),(1,'semantic'),(2,'operation')))


def development():
    counts = Counter()
    hits = Counter()
    calls = 0
    for layout in range(1200,1248):
        h,_,menu = public(layout)
        rng = random.Random(921213+layout)
        for pattern in PATTERNS:
            ids=rng.sample(range(12),3)
            for alias in (False,True):
                indices=[ids[ord(c)-65] for c in pattern]
                requests=[menu[i] for i in indices]
                seq=[(str(i)+('/alternate' if alias and k==2 else ''),i,'search')
                     for k,i in enumerate(indices)]
                for fault in ('stable','overlap_cache','backward','owner_overflow','quarter','reopen'):
                    for k,req in enumerate(requests):
                        y=backend(h,fault,req,requests[:k])
                        calls += 1
                        bad=y!=run(req['rows'],h)
                        if k:
                            for f in features(seq[:k+1]):
                                counts[f]+=1
                                hits[f]+=int(bad)
                        if bad:
                            break
    # Beta(1,1) estimate. Unseen partitions back off to the development rate at that depth.
    pooled={}
    for length in (2,3):
        keys=[f for f in counts if f[0]=='wire' and len(f[1])==length]
        pooled[length]=(1+sum(hits[f] for f in keys))/(2+sum(counts[f] for f in keys))
    weights={f:(1+hits[f])/(2+counts[f]) for f in counts}
    return weights,pooled,dict(calls=calls,episodes=48*5*2*6,
        estimates=[dict(channel=f[0],pattern=f[1],n=counts[f],hits=hits[f],weight=weights[f]) for f in sorted(counts)])


def reference(seq, stock, mutant=None):
    depot=0
    results=[]
    for wire,sem,op in seq:
        value=sem[1]
        if op=='select':
            if mutant!=('ignore',value):
                depot=value
            results.append(('selected',value))
        else:
            source=1-depot if mutant==('scope',depot) else depot
            result=stock[source][value] + int(mutant==('quantity',value))
            if mutant==('repeat',) and len(results) and seq[len(results)-1][0]==wire:
                result+=1
            results.append(('stock',result))
    return tuple(results)


def choose_all(menu, stock, layout, accounts, weights, pooled):
    import time
    start=time.perf_counter()
    seqs=list(product(menu,repeat=3))
    random.Random(231108+layout).shuffle(seqs)
    readings=[x for x in menu if x[2]=='stock']
    mutants=[('quantity',v) for v in sorted({x[1][1] for x in readings})]
    mutants += [('ignore',0),('ignore',1),('scope',0),('scope',1),('repeat',)]
    table={}
    prefixes={}
    for seq in seqs:
        f=features(seq[:2])+features(seq)
        for n in (1,2,3):
            prefix=seq[:n]
            if prefix not in prefixes:
                expected=reference(prefix,stock)
                prefixes[prefix]=sum(1<<j for j,m in enumerate(mutants) if reference(prefix,stock,m)!=expected)
        table[seq]=(f,prefixes[seq].bit_count()/len(mutants))
    prep=time.perf_counter()-start
    choices={}
    # A two-state minimal Mealy model: access south via one select, distinguish with a lookup.
    # Rotate choices among equally valid minimal covers and distinguishing symbols.
    rng=random.Random(78523+layout)
    switch=rng.choice([x for x in menu if x[1]==('select',1)])
    distinguish=rng.choice(readings)
    suite=set()
    for access in ((),(switch,)):
        for n in (0,1,2):
            for middle in product(menu,repeat=n):
                suite.add(access+middle+(distinguish,))
    w_budget=[s for s in seqs if s in suite]
    assert w_budget and all(stock[0][x[1][1]]!=stock[1][x[1][1]] for x in readings)
    delta={}
    for s in w_budget:
        state=0
        transitions=set()
        for wire,semantic,op in s:
            transitions.add((state,wire))
            if op=='select':
                state=semantic[1]
        delta[s]=len(transitions)
    for method in METHODS:
        start=time.perf_counter()
        prior=accounts[method]
        def history(s,learn):
            values=[]
            for f in table[s][0]:
                novelty=1/(1+prior[f])**0.5
                weight=weights.get(f,pooled[len(f[1])])/pooled[len(f[1])] if learn else 1.
                values.append(novelty*weight)
            return sum(values)/len(values)
        if method=='greedy':
            prefix=()
            for n in (1,2,3):
                candidates=dict.fromkeys(s[:n] for s in seqs if s[:n-1]==prefix)
                prefix=max(candidates,key=lambda s:prefixes[s].bit_count())
            chosen=prefix
        elif method=='fixed':
            chosen=next(s for s in seqs if features(s)[0][1]==PATTERNS[layout%5])
        elif method=='w':
            chosen=max(w_budget,key=lambda s:(delta[s],table[s][1]))
        elif method in ('learned','coverage'):
            chosen=max(seqs,key=lambda s:history(s,method=='learned'))
        else:
            scores={s:history(s,method=='joint') for s in seqs}
            scale=max(scores.values())
            chosen=max(seqs,key=lambda s:table[s][1]+scores[s]/scale)
        choices[method]=(chosen,table[chosen][1],time.perf_counter()-start)
        # Cross-layout scheduling uses planned exposures only, never hidden test outcomes.
        prior.update(table[chosen][0])
    return choices,dict(sequences=len(seqs),mutants=len(mutants),prefixes=len(prefixes),
        shared_seconds=prep,w_suite=len(suite),w_legal_length_three=len(w_budget))
