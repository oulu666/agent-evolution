"""Additional descriptive audit: matched no-copy* strata defined by common anchors only."""
from collections import Counter
import itertools as it
import json
import random
from run import ACT, MASKS, SEEDS, data, decimal, sqlite, make_logs, passed, valid, infer

def audit():
    out={}
    for f, actions in ACT.items():
        api={'decimal':decimal,'sqlite':sqlite}[f]
        dev=[[api(x,h) for h in actions] for x in data(f,False)]
        test=[[api(x,h) for h in actions] for x in data(f,True)]
        for scope in MASKS:
            hs=list(it.product(range(len(actions)),(2,) if scope=='exact' else (0,1)))
            ctr=Counter()
            for seed in range(SEEDS):
                truth=hs[seed%len(hs)]
                logs=make_logs(dev,hs,truth,random.Random(7610+seed))
                if not logs:continue
                anchors=logs['paired'][:2]
                anchor_actions={a for _,a,_ in anchors}
                for j,row in enumerate(test):
                    if anchor_actions.intersection(valid(test,j,truth)):continue
                    ctr['cases']+=1
                    for arm in ('paired','broken','positive_random','positive_curated'):
                        posterior=infer(dev,hs,logs[arm])
                        if not posterior:continue
                        score,k=max((sum(passed(test,j,a,h) for h in posterior),-a) for a in range(len(row)))
                        ctr[arm]+=score*2>len(posterior) and passed(test,j,-k,truth)
            out[f+'_'+scope]=ctr
    print(json.dumps(dict(meaning="correct when no shared anchor action is accepted",groups=out),
                     indent=2,sort_keys=True))

if __name__=='__main__':audit()
