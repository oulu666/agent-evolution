"""Layout-paired inference and risk at fixed total adoption coverage."""
from collections import Counter
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from two_step_falsification import LAYOUTS, METHODS, FAULTS, OUT, save


def read(name):
    return json.loads((OUT/name).read_text())


def ranked_bins(rows, levels):
    x = np.zeros((len(LAYOUTS), len(levels), 2),dtype=int)
    for r in rows:
        if r['accepted']:
            x[r['layout']-LAYOUTS.start,levels.index(r['risk']),int(r['fault']!='stable')] += 1
    return x


def risk_at(bins,n):
    totals = bins.cumsum(axis=1)
    bad = totals[:,:,1]
    counts = totals.sum(axis=2)
    i = (counts < n).sum(axis=1)
    valid = i < counts.shape[1]
    i = i.clip(max=counts.shape[1]-1)
    k = np.arange(len(bins))
    prior_n = np.where(i>0,counts[k,i-1],0)
    prior_bad = np.where(i>0,bad[k,i-1],0)
    within = (n-prior_n)/np.maximum(1,counts[k,i]-prior_n)
    return np.where(valid,(prior_bad+within*(bad[k,i]-prior_bad))/n,np.nan)


def main():
    traces, costs, oracle = [read(n) for n in ('traces.json','costs.json','reachability.json')]
    summary = {}
    draws = np.random.default_rng(231123).multinomial(48,[1/48]*48,size=10000)
    fig,axes = plt.subplots(1,2,figsize=(9,4),sharey=True,constrained_layout=True)
    for ax,perm in zip(axes,('read','build')):
        sub=[r for r in traces if r['perm']==perm]
        levels=sorted({r['risk'] for r in sub})
        stats={}; data={}
        for method in METHODS:
            rr=[r for r in sub if r['method']==method]
            cc=[r for r in costs if r['perm']==perm and r['method']==method]
            hits=np.array([sum(r['refuted'] for r in rr if r['layout']==j) for j in LAYOUTS])
            attainable=np.array([sum(r['reachable'] for r in rr if r['layout']==j) for j in LAYOUTS])
            bins=ranked_bins(rr,levels)
            data[method]=(hits,bins)
            s=stats[method]=dict(detected=int(hits.sum()),attainable=int(attainable.sum()),
                adopted=sum(r['accepted'] for r in rr),bad=sum(r['accepted'] and r['fault']!='stable' for r in rr),
                calls=sum(len(r['queries']) for r in rr),
                hits_by_fault=dict(Counter(r['fault'] for r in rr if r['refuted'])),
                missed_accessible=int(attainable.sum()-hits.sum()),unreachable=240-int(attainable.sum()),
                planning_cpu_seconds=sum(r['plan_cpu'] for r in cc),
                plan_wall_ms_per_layout=np.mean([r['plan_wall']*1000 for r in cc]) if cc else None,
                additional_selection_ms_per_episode=np.mean([r['replan_wall']*1000 for r in rr]),
                common_cpu_seconds=sum(r['shared_cpu'] for r in cc),
                total_signature_evals=sum(r['predictions'] for r in cc),
                online_cpu_seconds=sum(r['online_cpu'] for r in rr))
            if method=='oracle':
                continue
            s['risk_at_50pct']=float(risk_at(bins.sum(axis=0)[None,:],144)[0])
            curve=bins.sum(axis=0).cumsum(axis=0)
            curve=curve[curve.sum(axis=1)>0]
            # A threshold tie is sampled uniformly. Risk is flat to the first threshold.
            count=curve.sum(axis=1)
            cover=np.linspace(0.001,count[-1],220)
            bad=np.interp(cover,[0,*count],[0,*curve[:,1]])
            ax.plot(cover/288,bad/cover,markevery=50,marker={'greedy':'o','static':'s','adaptive':'+','risk':'x'}[method],
                    label=method,alpha=0.7)
        greedy,gb=data['greedy']
        hits,bins=data['adaptive']
        hitdiff=draws@(hits-greedy)/(draws@attainable)
        def band(x):
            return np.nanpercentile(x,[2.5,97.5]).tolist()
        def resample(x):
            return np.einsum('dl,lsc->dsc',draws,x)
        riskdiff=risk_at(resample(bins),144)-risk_at(resample(gb),144)
        paired=list(zip([r for r in sub if r['method']=='greedy'],[r for r in sub if r['method']=='adaptive']))
        stats['contrast']=dict(hit_rate_ci=band(hitdiff),wins=sum(b['refuted'] and not a['refuted'] for a,b in paired),
            losses=sum(a['refuted'] and not b['refuted'] for a,b in paired),
            risk_50_ci=band(riskdiff),defined_bootstraps=int(np.isfinite(riskdiff).sum()),
            distinct_requests=sum(a['queries']!=b['queries'] for a,b in paired))
        rh,rb=data['risk']
        dr=risk_at(resample(rb),144)-risk_at(resample(gb),144)
        stats['risk_vs_greedy']=dict(hit_rate_ci=band(draws@(rh-greedy)/(draws@attainable)),
            risk_50_ci=band(dr),defined_bootstraps=int(np.isfinite(dr).sum()))
        stats['oracle_audit']=dict(calls=sum(r['audit_calls'] for r in oracle if r['perm']==perm),
            cpu_seconds=sum(r['audit_cpu'] for r in oracle if r['perm']==perm))
        summary[perm]=stats
        ax.set_title('Read only' if perm=='read' else 'Constructible menu')
        ax.set_xlabel('Adoption coverage')
        ax.grid(alpha=0.25)
    axes[0].set_ylabel('Errors / adopted contracts')
    axes[0].legend()
    fig.savefig(OUT/'risk_coverage.png',dpi=180)
    save('summary.json',summary)
    print(json.dumps(summary))


if __name__=='__main__':
    main()
