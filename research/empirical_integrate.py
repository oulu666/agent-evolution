"""Audit archived evidence, run only new stock controls, and derive paper tables."""
from collections import Counter,defaultdict
import json
import random
import hashlib

from empirical_sqlite import ROOT,OLD,OUT,FAULTS as SQL_FAULTS,save
from history_relation_inventory import FAULTS,fixture,play
from history_relation_policy import reference


def load(path):
    return json.loads(path.read_text(encoding='utf8'))


def risk_at(rows,pi,target):
    totals=Counter(r['fault']=='stable' for r in rows)
    bins=defaultdict(lambda:[0.,0.])
    for r in rows:
        if not r['hit']:
            stable=r['fault']=='stable'
            bins[r['confidence']][int(not stable)]+=(1-pi if stable else pi)/totals[stable]
    n=bad=0
    for score,(good,wrong) in sorted(bins.items(),reverse=True):
        if n+good+wrong>=target-1e-12:
            frac=min(1,(target-n)/(good+wrong))
            return dict(risk=(bad+frac*wrong)/target,score=score,tie_fraction=frac)
        n+=good+wrong
        bad+=wrong
    return None


def measure(rows,witness,blocked,faults):
    cells=[]
    for perm in sorted({r['perm'] for r in rows}):
        for method in sorted({r['method'] for r in rows if r['perm']==perm}):
            subset=[r for r in rows if r['perm']==perm and r['method']==method]
            groups=Counter(r['layout'] for r in subset)
            assert all(n==len(faults)+1 for n in groups.values())
            for budget in (2,3,4,5):
                if method=='joint_3' and budget!=3:
                    continue
                counts=Counter()
                for r in subset:
                    key=(perm,r['layout'],r['fault'])
                    diff=r['first_difference']
                    counts['calls']+=min(diff or budget,budget)
                    if r['fault']=='stable':
                        assert diff is None
                        continue
                    if key in blocked:
                        category='permission'
                    elif witness[key]>budget:
                        category='budget'
                    elif diff and diff<=budget:
                        category='hit'
                    else:
                        category='miss'
                    counts[category]+=1
                    if diff:
                        assert key not in blocked and diff>=witness[key]
                cells.append(dict(perm=perm,method=method,B=budget,**{k:counts[k] for k in
                              ('hit','miss','budget','permission','calls')},resets=len(subset)))
    return cells


def main():
    paths=[OLD/(f+'.json') for f in ('decisions','control_traces','frontier','summary','development')]
    calendar=ROOT/'runs_two_step_20261123'/'traces.json'
    source_hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*paths,calendar]}
    c=load(calendar)
    def group(m):
        return {(r['layout'],r['perm'],r['fault']):r for r in c if r['method']==m}
    sta,ada=group('static'),group('adaptive')
    assert sta.keys()==ada.keys() and all(sta[k]['queries']==ada[k]['queries'] and
             sta[k]['observed']==ada[k]['observed'] for k in sta)
    assert len(sta)==576
    stock_rows=load(paths[0])+load(paths[1])
    assert len(stock_rows)==6480 and len({(r['perm'],r['method'],r['fault'],r['layout']) for r in stock_rows})==6480
    assert all((r['actual']!=r['expected'])==r['hit'] for r in stock_rows)
    front=load(paths[2])
    witness={(r['perm'],r['layout'],f):len(w) for r in front for f,w in r['witness'].items()}
    blocked={(r['perm'],r['layout'],f) for r in front for f in r['unreachable']}
    originals={(r['perm'],r['layout'],r['fault']):r for r in stock_rows if r['method']=='fixed_ABA_mutation'}
    stock=[]
    risk_rows=[r for r in stock_rows if r['method'] in ('fixed_ABA_mutation','greedy','joint','random_W')]
    for perm in ('saved','construct'):
        for lay in range(60):
            menu,vals=fixture(lay,perm)
            bank={q[0]:q for q in menu}
            rng=random.Random(177161+lay)
            healthy=originals[perm,lay,'stable']
            aba=tuple(bank[q] for q in healthy['queries'])+tuple(rng.choices(menu,k=2))
            # Balanced minimal state cover of the two warehouse states.
            prefix=() if lay%2==0 else (next(q for q in menu if q[1]==('select',1)),)
            plans={'ABA':aba,'state_prefix':prefix+tuple(rng.choices(menu,k=5-len(prefix)))}
            for method,s in plans.items():
                y=reference(s,vals)
                mutants=[('quantity',v) for v in sorted({q[1][1] for q in menu if q[2]=='stock'})]
                mutants+=[('ignore',0),('ignore',1),('scope',0),('scope',1),('repeat',)]
                conf=sum(reference(s[:3],vals,m)!=y[:3] for m in mutants)/len(mutants)
                for f in ('stable',*FAULTS):
                    hit,obs=play(vals,f,s,y)
                    d=len(obs) if hit else None
                    stock.append(dict(perm=perm,layout=lay,method=method,fault=f,
                        plan=[q[0] for q in s],observed=obs,expected=y,first_difference=d))
                    if method=='ABA':
                        archive=originals[perm,lay,f]
                        assert archive['hit']==bool(d and d<=3)
                    else:
                        risk_rows.append(dict(perm=perm,layout=lay,method=method,fault=f,hit=bool(d and d<=3),confidence=conf))
    save('inventory_new_traces.json',stock)
    scenarios=[]
    for perm in ('saved','construct'):
        for m in sorted({r['method'] for r in risk_rows}):
            rr=[r for r in risk_rows if r['method']==m and r['perm']==perm]
            for pi in (.01,.05,.2,5/6):
                for target in (.25,.5,.75):
                    scenarios.append(dict(perm=perm,method=m,prevalence=pi,coverage=target,
                        result=risk_at(rr,pi,target)))
    certs=load(OUT/'sqlite_witnesses.json')
    sq=load(OUT/'sqlite_traces.json')
    for r in sq:
        r['perm']=r['permission']
    sw={(perm,i,f):len(s) for perm,cert in certs.items() for i in range(36) for f,s in cert['witness'].items()}
    sb={(perm,i,f) for perm,cert in certs.items() for i in range(36) for f in cert['blocked']}
    save('budget_matrix.json',dict(inventory=measure(stock,witness,blocked,FAULTS),sqlite=measure(sq,sw,sb,SQL_FAULTS)))
    save('risk_sensitivity.json',scenarios)
    family=[]
    for perm in ('saved','construct'):
        for m in ('greedy','joint','fixed_ABA_mutation','state_prefix'):
            for omitted in FAULTS:
                part=[r for r in risk_rows if r['perm']==perm and r['method']==m and r['fault']!=omitted]
                family.append(dict(perm=perm,method=m,omitted=omitted,result=risk_at(part,.05,.5)))
    save('fault_mix_sensitivity.json',family)
    save('archive_audit.json',dict(archived_stock_episodes=len(stock_rows),matched_calendar_episodes=len(sta),
                                  source_sha256=source_hashes))


if __name__=='__main__':
    main()
