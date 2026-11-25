"""Audit the two experiments from saved proposals and independent calendar executions."""
import json
import re
from collections import Counter
from pathlib import Path

from semantic_extension_bank import CAP, NAMES, base, in_old_space, language, run_extension, target

OUT=Path(__file__).resolve().parents[1]/'runs_semantic_repair_20261123'


def read(name):
    return json.loads((OUT/name).read_text(encoding='utf8'))


def save(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf8')


def equivalent_readback(raw,alias):
    """Only unwrap a single action or commute a before-page exclusion with the stable primary sort."""
    try:
        v=json.loads(re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$','',raw,flags=re.I))
    except ValueError:
        return None
    sort=['sort',NAMES[alias][1],'asc']
    take=['take',CAP]
    if isinstance(v,list) and len(v)==1:
        v=v[0]
    elif isinstance(v,list) and len(v)==3 and all(isinstance(x,list) for x in v):
        if v[0]==sort and v[2]==take and v[1] and v[1][-1]!='after':
            v=v[1]
        elif v[0]==sort and v[1]==take and v[2] and v[2][-1]=='after':
            v=v[2]
        elif v[1:]==[sort,take] and len(v[0])==4 and v[0][0]=='exclude' and v[0][-1]=='before':
            v=v[0]
    return tuple(v) if isinstance(v,list) and tuple(v) in language(alias) else None


def shuffled_proposals(part,fixtures):
    """Exact assignment distribution: move both proposals together within a field vocabulary."""
    total=Counter({0:1})
    for alias in (0,1):
        group=[r for r in part if fixtures[r['id']]['alias']==alias]
        dp={0:Counter({0:1})}
        for target_row in group:
            new={}
            for mask,dist in dp.items():
                for j,source_row in enumerate(group):
                    if mask & (1<<j):
                        continue
                    acc=new.setdefault(mask|(1<<j),Counter())
                    hit=int(target_row['truth'] in source_row['proposals'])
                    for n,weight in dist.items():
                        acc[n+hit]+=weight
            dp=new
        combined=Counter()
        for i,a in total.items():
            for j,b in next(iter(dp.values())).items():
                combined[i+j]+=a*b
        total=combined
    observed=sum(r['proposed_truth'] for r in part)
    denom=sum(total.values())
    return dict(observed=observed,expected=sum(i*v for i,v in total.items())/denom,
                probability_at_least_observed=sum(v for i,v in total.items() if i>=observed)/denom,
                proposal_families=dict(Counter(h[0] for r in part for h in r['proposals'])))


def main():
    summary={}
    ledger=[]
    fixtures={t['id']:t for t in read('B_fixtures.json')}
    assert len(fixtures)==27
    for t in fixtures.values():
        assert not in_old_space(t['records'],t['obs'],t['alias'])
        if t['split']=='final':
            identical=[h for h in language(t['alias']) if all(run_extension(x,h,t['alias'])==
                       target(x,t['truth'],t['alias']) for x in t['held'])]
            assert identical==[tuple(t['truth'])]
    for size in ['06','17']:
        a=read(f'A_{size}.json')
        values={}
        for arm in a[0]['arms']:
            part=[v['arms'][arm] for v in a]
            values[arm]=dict(valid=sum(v['rule'] is not None for v in part),
                **{k:sum(v[k] for v in part) for k in ['count_ok','correct_take','consistent','exact','held']})
        recovered=[]
        for row in a:
            raw=re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$', '',row['arms']['A2']['raw'],flags=re.I)
            try:
                v=json.loads(raw)
                if isinstance(v,dict) and 'take' in v:
                    n=v['take']
                    recovered.append((n is None or type(n) is int and n>=row['observed'],n==row['truth']['take']))
            except ValueError:
                pass
        values['A2_field_readback']=dict(readable=len(recovered),count_ok=sum(r[0] for r in recovered),
                                         exact_take=sum(r[1] for r in recovered))
        rows=read(f'B_{size}.json')
        grammar=OUT/f'grammar_{size}.json'
        if grammar.exists():
            rows.extend(read(grammar.name))
        raw={e['hash']:e['raw'] for e in map(json.loads,(OUT/f'generations_{size}.jsonl').read_text().splitlines())}
        b={}
        for split in ['dev','final']:
            b[split]={}
            for arm in dict.fromkeys(r['arm'] for r in rows):
                part=[r for r in rows if r['arm']==arm and r['split']==split]
                assert len(part)==(3 if split=='dev' else 24)
                family_counts={}
                for family in ['unique','exclude','tie']:
                    group=[r for r in part if r['truth'][0]==family]
                    family_counts[family]=sum(r['exact'] for r in group)
                for r in part:
                    t=fixtures[r['id']]
                    if r['deployed']:
                        h=r['deployed']
                        assert run_extension(t['records'],h,t['alias'])==t['obs']
                        assert run_extension(t['probe'][r['probe']],h,t['alias'])==r['probe_obs']
                        assert sum(run_extension(x,h,t['alias'])==target(x,t['truth'],t['alias']) for x in t['held'])==r['held']
                        assert (run_extension(t['neutral'],h,t['alias'])==base(t['neutral'],t['alias']))==r['control_ok']
                        if r['control_ok'] and r['held']==len(t['held']) and split=='final':
                            ledger.append(dict(size=size,method=arm,case=t['id'],rule=h,exact=r['exact']))
                b[split][arm]=dict(n=len(part),valid_slots=sum(r['valid'] for r in part),
                    syntax_tasks=sum(bool(r['valid']) for r in part),proposed=sum(r['proposed_truth'] for r in part),
                    fit_first=sum(bool(r['first_fit']) for r in part),adopt=sum(bool(r['deployed']) for r in part),
                    wrong=sum(r['false_adopt'] for r in part),exact=sum(r['exact'] for r in part),
                    all_held=sum(r['held']==16 for r in part),held_pages=sum(r['held'] for r in part),
                    preserved=sum(r['control_ok'] for r in part),families=family_counts,
                    output_tokens=sum(r['tokens'] for r in part))
                if 'generations' in part[0]:
                    b[split][arm]['extra_truth_by_format_readback']=sum(not r['proposed_truth'] and
                        any(equivalent_readback(raw[key],fixtures[r['id']]['alias'])==tuple(r['truth'])
                            for key in r['generations']) for r in part)
                if arm in ('grammar2','hybrid'):
                    baseline={r['id']:r for r in rows if r['arm']=='search2'}
                    b[split][arm]['new_vs_search2']=[r['id'] for r in part if r['exact'] and not baseline[r['id']]['exact']]
                    b[split][arm]['lost_vs_search2']=[r['id'] for r in part if not r['exact'] and baseline[r['id']]['exact']]
                if split=='final' and arm=='grammar2':
                    b[split][arm]['within_schema_permutation']=shuffled_proposals(part,fixtures)
        summary[size]=dict(A=values,B=b)
    save('summary.json',summary)
    save('verified_extensions.json',ledger)
    print(json.dumps(summary))


if __name__=='__main__':
    main()
