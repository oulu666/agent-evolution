"""Counterfactual repair-decision admission screen. Python 3.12, NumPy 2.3.5."""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_DOWN
import json
import random
import statistics
import sys

import numpy as np


def evaluate(family, adapter, row):
    a, b, u = row
    if family == "decimal":
        mode = [ROUND_HALF_EVEN, ROUND_HALF_UP, ROUND_DOWN][adapter]
        return Decimal(a).scaleb(-1).quantize(Decimal("1"), rounding=mode)
    if family == "numpy":
        x = np.float64(a / 10)
        return (np.rint, lambda y: np.copysign(np.floor(abs(y) + 0.5), y),
                np.trunc)[adapter](x)
    if family == "datetime":
        start = date(2024, 1 + b % 12, min(28, 1 + u % 29))
        if adapter == 0:
            return start + timedelta(days=a)
        if adapter == 1:
            return start + timedelta(weeks=a // 7, days=a % 7)
        return start + timedelta(days=max(0, a))
    seq = (a, b, u, a)
    if adapter == 0:
        return statistics.mean(seq)
    if adapter == 1:
        return statistics.mean(sorted(seq))
    return statistics.median(seq)


def input_row(rng, stress):
    if stress:
        return (-rng.randrange(1, 10) * 10 - rng.choice([5, 9]),
                rng.randrange(3, 15), rng.randrange(15, 30))
    return (rng.randrange(1, 10) * 10, rng.randrange(1, 10), rng.randrange(1, 10))


def scenarios(family, seed, n=384):
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        adapter = rng.randrange(3)
        prevalence = rng.choice([0.0, 0.15, 0.45, 0.85])
        preview_mix = rng.choice([0.0, 0.25, 0.75])
        canary_mix = rng.choice([0.0, 0.25, 0.75, 1.0])
        c_f, c_v = rng.choice([2., 3.]), rng.choice([.75, 1.25])
        def mismatch(stress):
            row = input_row(rng, stress)
            return evaluate(family, 0, row) != evaluate(family, adapter, row)
        previews = [mismatch(rng.random() < preview_mix) for _ in range(4)]
        flag = bool(mismatch(rng.random() < canary_mix))
        bad = bool(any([mismatch(rng.random() < prevalence) for _ in range(6)]))
        x = [sum(previews)/4, prevalence, preview_mix, canary_mix,
             sum(previews)/4*canary_mix, prevalence*canary_mix]
        assert len(x) == 6
        out.append((x, float(bad), float(flag), c_f, c_v))
    return out


def fit(X, Y):
    penalty = np.eye(X.shape[1])*2
    penalty[0, 0] = 0
    return np.linalg.solve(X.T @ X + penalty, X.T @ Y)


def arrays(rows):
    X, b, f, cf, cv = zip(*rows)
    return (np.column_stack((np.ones(len(X)), X)), *(np.array(v) for v in (b,f,cf,cv)))


def losses(b, f, cf, cv, penalty):
    return np.column_stack((penalty*b, cv+f*cf+(1-f)*penalty*b, cf))


def choose(train, test, penalty):
    X,b,f,cf,cv = train
    T,_,_,tc,tv = test
    cost = losses(b,f,cf,cv,penalty)
    p = np.clip(T @ fit(X,b),0,1)
    # Paired factorization estimates canary outcomes separately in bad/good contexts.
    qbad = np.clip(T @ fit(X[b==1], f[b==1]),0,1)
    qgood = np.clip(T @ fit(X[b==0], f[b==0]),0,1)
    def decision(error, signal, leaked):
        return losses_from_rates(error,signal,leaked,tc,tv,penalty).argmin(axis=1)
    joint = np.clip(T @ fit(X,np.column_stack((b,f,b*(1-f)))),0,1)
    marginal_q = f[b==1].mean()
    marginal_good = f[b==0].mean()
    direct_residual = np.column_stack((cost[:,0],cost[:,1]-cv, cost[:,2]-cf))
    direct = np.column_stack((T,tc)) @ fit(np.column_stack((X,cf)),direct_residual)
    direct += np.column_stack((np.zeros(len(T)),tv,tc))
    return {
        'factorized': decision(p,p*qbad+(1-p)*qgood,p*(1-qbad)),
        'joint_ridge': decision(*joint.T),
        'direct_cost_ridge': direct.argmin(axis=1),
        'confidence_fixed_detection': decision(p,p*marginal_q+(1-p)*marginal_good,p*(1-marginal_q)),
        'preview_rule': np.where(T[:,1]>0,2,np.where((T[:,2]>0.25)&(T[:,4]>=0.5),1,0)),
        'always_verify': np.ones(len(T),dtype=int),
        'always_fallback': np.full(len(T),2),
        'always_accept': np.zeros(len(T),dtype=int),
    }


def losses_from_rates(error, signal, missed, cf, cv, penalty):
    return np.column_stack((penalty*error, cv+cf*signal+penalty*missed,cf))


def main():
    families = ("decimal","numpy","datetime","statistics")
    data = {f: scenarios(f,8401+i) for i,f in enumerate(families)}
    out = {}
    for penalty in (4,8,16):
        by_family = {}
        for family in families:
            train=arrays([r for k,v in data.items() if k!=family for r in v])
            test=arrays(data[family])
            _,bad,flag,cf,cv=test
            loss=losses(bad,flag,cf,cv,penalty)
            actions=choose(train,test,penalty)
            actions["clairvoyant"]=loss.argmin(axis=1)
            by_family[family] = {k:{
                "cost":float(loss[np.arange(len(a)),a].sum()),
                "unsafe":int(np.sum(bad*((a==0)|((a==1)&(flag==0))))),
                "actions":[int(np.sum(a==i)) for i in range(3)]
            } for k,a in actions.items()}
        totals={k:{"cost":sum(f[k]["cost"] for f in by_family.values()),
                   "unsafe":sum(f[k]["unsafe"] for f in by_family.values())}
                for k in by_family[families[0]]}
        out[penalty]={"totals":totals,"by_family":by_family}
    print(json.dumps({"python":sys.version.split()[0],"numpy":np.__version__,
                      "cases_per_family":384,"results":out},indent=2,sort_keys=True))


if __name__ == "__main__":
    main()
