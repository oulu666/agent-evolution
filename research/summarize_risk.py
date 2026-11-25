import json
import random
from collections import Counter,defaultdict
from statistics import median
from risk_worlds import OUT,save


def read(name):
    return json.loads((OUT/name).read_text(encoding='utf8'))


def bias():
    old=json.loads((OUT.parent/'runs_semantic_repair_20261123/grammar_06.json').read_text())
    old={r['id']:r for r in old if r['arm']=='grammar2' and r['split']=='final'}
    parts=defaultdict(list)
    for case in read('bias.json'):
        r=old[case['id']]
        parts['original'].append((r['proposals'],r['truth']))
        for k in ('reversed_order','sampling'):
            parts[k].append(([json.loads(v) for v in case[k]['raw']],r['truth']))
    return {k:dict(families=dict(Counter(p[0] for ps,g in v for p in ps)),
                   truth_hits=sum(g in ps for ps,g in v),distinct=sum(len({tuple(p) for p in ps}) for ps,g in v))
            for k,v in parts.items()}


def main():
    rows=read('decisions.json')
    if (OUT/'wide_challenges.json').exists():
        base={r['id']:r for r in rows if r['arm']=='top2'}
        for item in read('wide_challenges.json'):
            parent=base[item['id']]
            assert parent['candidates']==item['candidates']
            rows.append(dict(arm='wide_shadow',input_tokens=0,tokens=0,model_seconds=0,
                             free_hit=parent['free_hit'],model_hit=parent['model_hit'],recall=parent['recall'],**item))
    arms=list(dict.fromkeys(r['arm'] for r in rows))
    assert len(rows)==len(arms)*216
    stats={}
    for arm in arms:
        r=[v for v in rows if v['arm']==arm]
        assert len({x['id'] for x in r})==216 and all(x['calls']==3 and sum(map(int,[x['correct'],x['wrong'],x['unknown']]))==1 for x in r)
        stats[arm]=dict(**{k:sum(x[k] for x in r) for k in ('recall','correct','wrong','unknown','tokens','input_tokens','calls','model_seconds','veto')},
            admitted=sum(x['gate'] is not None for x in r),cpu_ms_total=sum(x['cpu_ms'] for x in r),
            cpu_ms_median=median(x['cpu_ms'] for x in r),evals=sum(sum(x['evaluations'].values()) for x in r),
            by_kind={s:{k:sum(x[k] for x in r if x['kind']==s) for k in ('correct','wrong','unknown','recall','model_hit','free_hit')}
                     for s in ('simple','compound','outside')})
    rng=random.Random(20261123)
    samples=[rng.choices(range(24),k=24) for _ in range(10000)]
    comparisons={}
    contrasts=[('risk','top2'),('risk','hybrid'),('gated','hybrid'),('gated_active','gated'),('risk','gated_active'),
                ('risk','program_risk'),('risk','slice_program_risk'),('full_composed','full16'),('full_plus_slice','risk')]
    if 'wide_shadow' in arms:
        contrasts.append(('wide_shadow','top2'))
    for a,b in contrasts:
        left={r['id']:r for r in rows if r['arm']==a}
        right={r['id']:r for r in rows if r['arm']==b}
        measures={}
        for k in ('correct','wrong'):
            d=[0]*24
            diff=[]
            for key,v in left.items():
                delta=int(v[k])-int(right[key][k])
                d[v['layout']]+=delta
                diff.append(delta)
            boot=sorted(sum(d[i] for i in sample)*100/216 for sample in samples)
            measures[k]=dict(plus=diff.count(1),minus=diff.count(-1),pp=sum(diff)*100/216,
                             ci95_pp=[boot[249],boot[9749]])
        comparisons[a+' vs '+b]=measures
    samples=[json.loads(line) for line in (OUT/'proposals.jsonl').read_text().splitlines()]
    actual={k:sum(x[mode][k] for x in samples for mode in ('free','beam')) for k in ('input_tokens','output_tokens','seconds')}
    summary=dict(arms=stats,by_layout_paired=comparisons,bias=bias(),unique_histories=len(samples),actual_model=actual)
    if (OUT/'size_pairs.json').exists():
        pairs=read('size_pairs.json')
        summary['size_stress']={str((drift,long)):dict(n=len(part),accepted=sum(r['accept'] for r in part),
            wrong=sum(r['wrong_adoption'] for r in part),unknown=sum(r['unknown'] for r in part))
            for drift in (False,True) for long in (False,True)
            for part in [[r for r in pairs if r['drift']==drift and r['long_third']==long]]}
    save('summary.json',summary)
    for k,s in stats.items():
        print(k,*[s[x] for x in ('recall','correct','wrong','unknown','admitted','veto','evals','cpu_ms_median')])
    print('decoding',summary['bias'])


if __name__=='__main__':
    main()
