"""Post-hoc attribution only: keep primary decisions and learned weights untouched."""
from itertools import product
import random
import time
from history_relation_inventory import fixture,play,OUT,FAULTS,save
from history_relation_policy import features,reference
from history_relation_results import load,risk_at,risk_bins
import numpy as np


def controls():
    primary=load('decisions.json')
    frontier={(r['layout'],r['perm']):r for r in load('frontier.json')}
    out=[]
    for perm in ('saved','construct'):
        for layout in range(60):
            menu,stock=fixture(layout,perm)
            seqs=list(product(menu,repeat=3))
            random.Random(231108+layout).shuffle(seqs)
            readings=[x for x in menu if x[2]=='stock']
            mutants=[('quantity',v) for v in sorted({x[1][1] for x in readings})]
            mutants += [('ignore',0),('ignore',1),('scope',0),('scope',1),('repeat',)]
            def killed(s):
                expected=reference(s,stock)
                return sum(reference(s,stock,m)!=expected for m in mutants)/len(mutants)
            rng=random.Random(78523+layout)
            switch=rng.choice([x for x in menu if x[1]==('select',1)])
            distinguish=rng.choice(readings)
            # Exactly the executable length-three members of S . Sigma^{<=2} . W.
            w=[s for s in seqs if s[-1]==distinguish]
            assert switch in menu
            selections={'fixed_ABA_mutation':max((s for s in seqs if features(s)[0][1]=='ABA'),key=killed),
                        'random_W':rng.choice(w)}
            for method,seq in selections.items():
                expected=reference(seq,stock)
                confidence=killed(seq)
                for fault in ('stable',*FAULTS):
                    bad,obs=play(stock,fault,seq,expected)
                    out.append(dict(layout=layout,perm=perm,method=method,fault=fault,hit=bad,
                        reachable=fault in frontier[layout,perm]['counts'],confidence=confidence,
                        queries=[q[0] for q in seq[:len(obs)]],expected=expected[:len(obs)],actual=obs,calls=len(obs)))
    save('control_traces.json',out)
    summary={}
    for perm in ('saved','construct'):
        s=summary[perm]={}
        rr=[r for r in primary+out if r['perm']==perm and r['method'] in ('joint',*selections)]
        levels=sorted({r['confidence'] for r in rr},reverse=True)
        draws=np.random.default_rng(241126).multinomial(60,[1/60]*60,size=10000)
        samples={}
        for method in ('joint',*selections):
            rows=[r for r in rr if r['method']==method]
            num=np.array([sum(r['hit'] for r in rows if r['layout']==i) for i in range(60)])
            den=np.array([sum(r['reachable'] for r in rows if r['layout']==i) for i in range(60)])
            samples[method]=draws@num/(draws@den)
            bins=risk_bins(rows,levels)
            s[method]=dict(hits=int(num.sum()),risk=float(risk_at(bins.sum(axis=0)[None,:,:],180)[0]),
                calls=sum(r['calls'] for r in rows),by_fault={f:sum(r['hit'] for r in rows if r['fault']==f) for f in FAULTS})
        s['joint_minus_fixed_ABA_ci']=np.quantile(samples['joint']-samples['fixed_ABA_mutation'],[.025,.975]).tolist()
    save('control_summary.json',summary)
    print(summary)


if __name__=='__main__':
    controls()
