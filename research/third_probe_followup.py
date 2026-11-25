"""Paired uncertainty, menu relabeling and a repeat-last control on the saved experiment."""
import json
from collections import Counter
import numpy as np
from third_probe_inputs import OUT,TEST,public,run,evaluate,save


def read(name):
    return json.loads((OUT/name).read_text())


def risk_at(counts,order,target):
    # Tied confidence levels use a uniform fraction of all scenarios at that level.
    if target<=0:
        return float('nan')
    good=bad=0
    for i in order:
        a,b=counts[i]
        if a and good+a>=target:
            w=bad+b*(target-good)/a
            return w/(target+w)
        good+=a;bad+=b
    return float('nan')


def matched_interval(data,baseline):
    weights=np.random.default_rng(20261123).multinomial(24,[1/24]*24,size=10000)
    matrices=[]
    for method in ('tiny_program',baseline):
        part=[r for r in data if r['method']==method and r['permission']=='build' and r['split']=='test' and r['accepted']]
        levels=sorted({r['confidence'] for r in part},reverse=True)
        m=np.zeros((24,len(levels),2),dtype=int)
        for r in part:
            m[r['layout'],levels.index(r['confidence']),int(r['mechanism']!='stable')]+=1
        matrices.append(np.einsum('bi,ijk->bjk',weights,m))
    diffs=[]
    for a,b in zip(*matrices):
        target=min(a[:,0].sum(),b[:,0].sum())
        if target:
            diffs.append(100*(risk_at(a,range(len(a)),target)-risk_at(b,range(len(b)),target)))
    return dict(valid_draws=len(diffs),matched_risk_difference_pp_ci95=np.percentile(diffs,[2.5,97.5]).tolist())


def main():
    data=read('decisions.json')
    plans={(r['layout'],r['permission']):r for r in read('plans.json')}
    positions=read('position_audit.json')
    assert len(positions)==16
    audit={}
    for permission in ('read','build'):
        p=[r for r in positions if r['permission']==permission]
        hist=Counter()
        for r in p:
            old=plans[r['layout'],permission]
            if old['parsed'] and r['parsed']:
                hist['both_parse']+=1
                hist['same_physical']+=old['picks']['tiny_program']['name']==r['physical']
                hist['same_index']+=old['parsed'].get('index')==r['parsed'].get('index')
            hist['repeat_after_shuffle']+=r['physical']=='past1'
            hist['repeat_before_shuffle']+=old['picks']['tiny_program']['name']=='past1'
            hist['legal_after_shuffle']+=r['parsed'] is not None
        audit[permission]=dict(hist)
    control=[]
    for i in range(24):
        h,past,_=public(i)
        for mechanism in ('stable',*TEST):
            ys=[evaluate(h,mechanism,q,past[:j]) for j,q in enumerate(past)]
            q=past[-1]
            y=evaluate(h,mechanism,q,past)
            control.append(dict(layout=i,mechanism=mechanism,returns=ys+[y],refuted=y!=run(q['rows'],h)))
    save('repeat_control.json',control)
    save('supplement.json',dict(position=audit,bootstrap={m:matched_interval(data,m) for m in ('mutation','mutation_time')},
         repeat_detections=dict(Counter(r['mechanism'] for r in control if r['refuted']))))


if __name__=='__main__':
    main()
