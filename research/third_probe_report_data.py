"""Selective-risk curves and matched-coverage contrasts with layout-level resampling."""
import json
from collections import Counter,defaultdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from pathlib import Path
from third_probe_inputs import OUT,TEST,DEV,save


METHODS=['random','disagreement','mutation','tiny_program','mutation_time']
LABELS=['Random','Program disagreement','Program mutation','TinyAgent + program','Time-budgeted mutation']
COLORS=['#78838a','#26748a','#c17820','#9b3c73','#326849']


def grouped(rows,mode):
    bins=defaultdict(lambda:[0,0])
    for r in rows:
        allow=r['accepted'] if mode=='frozen' else not r['refuted']
        if allow:
            bins[r['confidence']][int(r['mechanism']!='stable')]+=1
    right=wrong=0
    points=[]
    for score,(good,bad) in sorted(bins.items(),reverse=True):
        right+=good;wrong+=bad
        points.append(dict(threshold=score,correct=right,wrong=wrong,
            coverage=(right+wrong)/len(rows),correct_coverage=right/len(rows),risk=wrong/(right+wrong)))
    return points


def matched(points,target):
    if not target:
        return None
    a=b=0
    for p in points:
        x,y=p['correct'],p['wrong']
        if x>=target and x>a:
            bad=b+(y-b)*(target-a)/(x-a)
            return bad/(target+bad)
        a,b=x,y
    return None


def main():
    data=json.loads((OUT/'decisions.json').read_text())
    reach=json.loads((OUT/'reachability.json').read_text())
    plans=json.loads((OUT/'plans.json').read_text())
    summary={};curves={};contrasts={}
    font=Path('C:/Windows/Fonts/msyh.ttc')
    chinese=font.exists()
    if chinese:
        font_manager.fontManager.addfont(str(font))
        plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
    labels_plot=['随机请求','候选分歧','程序变异','0.6B + 程序','等时间预算程序变异'] if chinese else LABELS
    fig,axs=plt.subplots(2,2,figsize=(11,8),sharey=True)
    for j,perm in enumerate(['read','build']):
        subset=[r for r in data if r['permission']==perm and r['split']=='test']
        summary[perm]={}
        curves[perm]={}
        for i,m in enumerate(METHODS):
            part=[r for r in subset if r['method']==m]
            detected={k:sum(r['refuted'] for r in part if r['mechanism']==k) for k in TEST}
            dev={k:sum(r['refuted'] for r in data if r['method']==m and r['permission']==perm and r['mechanism']==k) for k in DEV}
            n=sum(r['accepted'] for r in part)
            good=sum(r['accepted'] and r['mechanism']=='stable' for r in part)
            assert len(part)==120 and not any(r['refuted'] for r in part if r['mechanism']=='stable')
            out=dict(detected=detected,dev=dev,correct=good,wrong=n-good,accepted=n,unknown=120-n,
                     risk=(n-good)/n if n else None,coverage=n/120,calls=360,
                     decision_seconds=sum(r['selection_seconds'] for r in part if r['mechanism']=='stable'))
            summary[perm][m]=out
            curves[perm][m]={}
            for k,mode in enumerate(('frozen','passed_only')):
                points=grouped(part,mode)
                curves[perm][m][mode]=points
                ax=axs[k][j]
                ax.plot([100*p['coverage'] for p in points],[100*p['risk'] for p in points],
                        label=labels_plot[i],color=COLORS[i],lw=1.6,marker=['o','s','^','D','x'][i],ms=4,alpha=.85)
                ax.set_title(('Read-only' if j==0 else 'Constructible')+(' | frozen verifier' if k==0 else ' | pass-only diagnostic'))
                ax.set_xlabel('Adopted / all scenarios (%)');ax.set_ylabel('Wrong / adopted (%)')
                ax.grid(alpha=.22);ax.set_ylim(-3,103)
                if chinese:
                    ax.set_title(('只读日历' if j==0 else '可构造日历')+(' · 冻结验收器' if k==0 else ' · 仅按未被反驳验收'))
                    ax.set_xlabel('采用覆盖率（%）');ax.set_ylabel('已采用解释中的错误比例（%）')
        front=[r for r in reach if r['permission']==perm and r['mechanism'] in TEST]
        summary[perm]['attainable']={k:sum(bool(r['actual_catalog_witnesses'] or r['extra_witness']) for r in front if r['mechanism']==k) for k in TEST}
        pp=[r for r in plans if r['permission']==perm]
        summary[perm]['proposals']=dict(legal=sum(r['parsed'] is not None for r in pp),
            created=sum(r['picks']['tiny_program']['name']=='model' for r in pp),
            input_tokens=sum(r['model']['input_tokens'] for r in pp),output_tokens=sum(r['model']['output_tokens'] for r in pp),
            seconds=sum(r['model']['batch_share_seconds'] for r in pp),extra_cpu_candidates=sum(r['extra_mutations'] for r in pp))
        contrasts[perm]={}
        for baseline in ['mutation','mutation_time']:
            a='tiny_program';b=baseline
            aa=[r for r in subset if r['method']==a];bb=[r for r in subset if r['method']==b]
            assert [(r['layout'],r['mechanism']) for r in aa]==[(r['layout'],r['mechanism']) for r in bb]
            gains=sum(x['refuted'] and not y['refuted'] for x,y in zip(aa,bb))
            losses=sum(y['refuted'] and not x['refuted'] for x,y in zip(aa,bb))
            delta=np.array([sum(int(x['refuted'])-int(y['refuted']) for x,y in zip(aa,bb) if x['layout']==i)/4 for i in range(24)])
            boot=np.random.default_rng(1123).integers(0,24,(10000,24))
            comparison=dict(gain=gains,loss=losses,delta_refuted_pp=delta.mean()*100,
                             ci95=np.percentile(delta[boot].mean(axis=1)*100,[2.5,97.5]).tolist())
            for mode in ['frozen','passed_only']:
                ca=curves[perm][a][mode];cb=curves[perm][b][mode]
                target=min(ca[-1]['correct'] if ca else 0,cb[-1]['correct'] if cb else 0)
                comparison[mode]=dict(matched_correct=target,tiny_risk=matched(ca,target),baseline_risk=matched(cb,target))
            contrasts[perm][b]=comparison
    handles,labels=axs[1][0].get_legend_handles_labels()
    fig.legend(handles,labels,loc='lower center',ncol=3,frameon=False)
    axs[0][0].text(.04,.14,'随机与 0.6B：零采用，风险无定义' if chinese else 'Random and 0.6B: no adoptions',
                   transform=axs[0][0].transAxes,fontsize=9)
    fig.suptitle('第三问的风险与覆盖率 · 四种留出失效机制' if chinese else 'Third-probe selective risk | held-out mechanisms',fontsize=15)
    fig.tight_layout(rect=[0,.09,1,.95])
    fig.savefig(OUT/'risk_coverage.png',dpi=175)
    save('summary.json',dict(results=summary,paired=contrasts))
    save('risk_coverage.json',curves)
    print(json.dumps(dict(results=summary,paired=contrasts)))


if __name__=='__main__':
    main()
