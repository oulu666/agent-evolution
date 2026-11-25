"""Paired layout bootstrap and risk at a common total adoption coverage."""
from collections import Counter
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from history_relation_inventory import OUT,FAULTS,METHODS,save


def load(name):
    return json.loads((OUT/name).read_text())


def risk_bins(rows,levels):
    bins=np.zeros((60,len(levels),2),dtype=int)
    for r in rows:
        if not r['hit']:
            bins[r['layout'],levels.index(r['confidence']),int(r['fault']!='stable')]+=1
    return bins


def risk_at(bins,target):
    bad=bins[:,:,1].cumsum(axis=1)
    n=bins.sum(axis=2).cumsum(axis=1)
    j=(n<target).sum(axis=1)
    feasible=j<n.shape[1]
    j=j.clip(max=n.shape[1]-1)
    i=np.arange(len(bins))
    before=np.where(j>0,n[i,j-1],0)
    wrong=np.where(j>0,bad[i,j-1],0)
    frac=(target-before)/np.maximum(1,n[i,j]-before)
    return np.where(feasible,(wrong+frac*(bad[i,j]-wrong))/target,np.nan)


def main():
    traces,plans,front=[load(x) for x in ('decisions.json','plans.json','frontier.json')]
    draws=np.random.default_rng(241126).multinomial(60,[1/60]*60,size=10000)
    ci=lambda a:np.nanquantile(a,[.025,.975]).tolist()
    result={}
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),sharey=True,constrained_layout=True)
    for perm,ax in zip(('saved','construct'),axes):
        part=[r for r in traces if r['perm']==perm]
        levels=sorted({r['confidence'] for r in part},reverse=True)
        stats=result[perm]={}
        counts={}
        risk={}
        for m in METHODS:
            rr=[r for r in part if r['method']==m]
            reachable=np.array([sum(r['reachable'] for r in rr if r['layout']==i) for i in range(60)])
            hits=np.array([sum(r['hit'] for r in rr if r['layout']==i) for i in range(60)])
            counts[m]=hits
            bins=risk_bins(rr,levels)
            risk[m]=risk_at(np.einsum('nl,lsc->nsc',draws,bins),180)
            total=bins.sum(axis=0)[None,:,:]
            curve=total[0].cumsum(axis=0)
            curve=curve[curve.sum(axis=1)>0]
            n=curve.sum(axis=1)
            x=np.linspace(.001,n[-1],150)
            ax.plot(x/360,np.interp(x,[0,*n],[0,*curve[:,1]])/x,label=m)
            stats[m]=dict(hits=int(hits.sum()),reachable=int(reachable.sum()),calls=sum(r['calls'] for r in rr),
                resets=len(rr),risk_50=float(risk_at(total,180)[0]),risk_curve_counts=curve.tolist(),
                by_fault={k:sum(r['hit'] for r in rr if r['fault']==k) for k in FAULTS},
                patterns=dict(Counter(r['relation'][0][1] for r in rr if r['fault']=='stable')),
                selection_ms=sum(p['plans'][m]['select_seconds'] for p in plans if p['perm']==perm)*1000/60)
        stats['joint_vs']={}
        for m in METHODS[:-1]:
            diff=risk['joint']-risk[m]
            stats['joint_vs'][m]=dict(hit_rate_ci=ci((draws@(counts['joint']-counts[m]))/(draws@reachable)),
                risk_50_ci=ci(diff),defined=int(np.isfinite(diff).sum()))
        ff=[r for r in front if r['perm']==perm]
        pp=[p for p in plans if p['perm']==perm]
        stats['audit']=dict(reachable={f:sum(f in r['counts'] for r in ff) for f in FAULTS},
            budget=sum(len(w)==4 for r in ff for w in r['witness'].values()),
            permission=sum(len(r['unreachable']) for r in ff),exact_three_calls=sum(r['exhaustive_three_calls'] for r in ff),
            exact_three_resets=sum(r['exhaustive_three_resets'] for r in ff),
            exhaustive_cpu_seconds=sum(r['three_cpu'] for r in ff),cpu_all_policies=sum(p['combined_policy_cpu'] for p in pp),
            candidate_sequences=sum(p['sequences'] for p in pp))
        if (OUT/'control_traces.json').exists():
            controls=[r for r in load('control_traces.json') if r['perm']==perm]
            for name in ('fixed_ABA_mutation','random_W'):
                rows=[r for r in controls if r['method']==name]
                bins=risk_bins(rows,sorted({r['confidence'] for r in rows},reverse=True))
                curve=bins.sum(axis=0).cumsum(axis=0)
                curve=curve[curve.sum(axis=1)>0]
                n=curve.sum(axis=1)
                x=np.linspace(.001,n[-1],150)
                ax.plot(x/360,np.interp(x,[0,*n],[0,*curve[:,1]])/x,'--',label=name)
        ax.set_title('Saved menu' if perm=='saved' else 'Constructible menu')
        ax.set_xlabel('Adopted / all cases');ax.grid(alpha=.2)
    axes[0].set_ylabel('Wrong / adopted')
    axes[1].legend(ncol=2,fontsize=8)
    fig.savefig(OUT/'risk_coverage.png',dpi=170)
    save('summary.json',result)


if __name__=='__main__':
    main()
