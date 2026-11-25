"""Matched evidence ablation on archived and structurally new calendar layouts."""
import json
import random
from itertools import combinations, product

import numpy as np

from run_hidden_page_probes import CONTRACTS, WINDOWS, partition, singleton_count
from run_interface_boundaries import calendar, execute, iso, predicted_dates
from run_interface_fact_readout import vote
from run_rsi_operator_memory import FrozenAgent, ROOT

OUT = ROOT / 'runs_page_evidence_ablation_20261123'
ARMS = ('static', 'A', 'B', 'C', 'D', 'oracle')
SEED = 20261123


def write(name, data):
    dest = OUT / name
    tmp = dest.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(dest)


def fixtures():
    rng = random.Random(SEED)
    for index, endpoints in enumerate(product(range(2), repeat=6)):
        shift = rng.randrange(3)
        middle = [1, 1, 1]
        middle[shift] = rng.choice((0, 2))
        for split in ('reference', 'held'):
            starts = [a for a, _ in WINDOWS] if split == 'reference' else [
                iso('2085-04-15', index * 40 + j * 9) for j in range(3)]
            counts = {}
            for j, start in enumerate(starts):
                triple = endpoints[2*j], (1 if split == 'reference' else middle[j]), endpoints[2*j+1]
                counts.update({iso(start, k): n for k, n in enumerate(triple)})
            fields = ('start', 'end', 'date') if (split == 'reference' or index % 2 == 0) else ('from_day','through_day','on_day')
            yield split, index, starts, counts, fields


def plan(table):
    groups = list(partition(table, range(len(CONTRACTS)), [0]).values())
    queries = range(1, len(table))
    def n(group, q):
        return singleton_count(partition(table, group, [q]))
    base = max(queries, key=lambda q:sum(n(g,q) for g in groups))
    def value(extra):
        return sum(max(n(g,base), n(g,extra)) for g in groups)
    extra = max((q for q in queries if q != base), key=value)
    return [base, extra], value(extra) > sum(n(g,base) for g in groups)


def views(arm, days, windows, fields, seen, remaining, table, order, ordering):
    left, right, date = fields
    def request(q):
        return dict(zip((left,right), windows[q]))
    menu = dict(zip('AB', order))
    def page(response):
        return [{date:d} for d in response]
    text = ('Identify an undocumented calendar contract using one further request. Start and end can each '
            'be inclusive or exclusive; results are sorted by date, and the first page holds 1, 2 or unlimited events. '
            'All twelve combinations are equally likely. Choose the request most likely to identify all three properties '
            'uniquely. The known fixture lists one date per event, including duplicates.\n')
    data = dict(fixture=days, first_request=request(0), observed_first_page=page(seen),
                choices={label:request(q) for label,q in menu.items()})
    ids = [h for h in ordering if h in remaining]
    if arm in 'BCD':
        data['remaining_contracts'] = [
            dict(id=i, include_start=CONTRACTS[h][0][0]==0, include_end=CONTRACTS[h][0][1]==0,
                 page_size=CONTRACTS[h][1] or 'unlimited') for i,h in enumerate(ids)]
    if arm in 'CD':
        data['predicted_pages_by_date'] = [
            dict(id=i, **{label:table[q][h] for label,q in menu.items()}) for i,h in enumerate(ids)]
    if arm == 'D':
        data['contracts_uniquely_identifiable'] = {
            label:singleton_count(partition(table, remaining, [q])) for label,q in menu.items()}
    return text + json.dumps(data, separators=(',',':')) + '\nAnswer with one letter: A or B.'


def summarize(rows, branches, pairs, split):
    subset = [r for r in rows if r['split']==split]
    strict = [b for b in branches if b['split']==split and b['gold'] is not None]
    panel = [p for p in pairs if p['split']==split]
    stats = {}
    for arm in ARMS:
        stats[arm] = dict(correct=sum(r['success'][arm] for r in subset),
            calls=sum(r['calls'] for r in subset), episodes=len(subset),
            gained=sum(r['success'][arm] and not r['success']['static'] for r in subset),
            lost=sum(r['success']['static'] and not r['success'][arm] for r in subset),
            strict_correct=sum(b['choice'][arm]==b['gold'] for b in strict), strict=len(strict),
            pair_correct=sum(p['correct'][arm] for p in panel), pairs=len(panel))
    intervals = {}
    rng = np.random.default_rng(SEED)
    samples = rng.integers(0,64,(20000,64))
    for a,b in [('B','A'),('C','A'),('C','B'),('C','static'),('D','C'),('D','static')]:
        delta = np.zeros(64)
        for r in subset:
            delta[r['index']] += int(r['success'][a])-int(r['success'][b])
        boots = delta[samples].mean(axis=1)*100/12
        intervals[f'{a}-{b}'] = np.percentile(boots,[2.5,97.5]).tolist()
    return dict(arms=stats, interval_pp=intervals, paired_layouts=len({p['index'] for p in panel}))


def main():
    OUT.mkdir(exist_ok=True)
    write('protocol.json', dict(seed=SEED, shared_first=True, max_calls=2, hypotheses=CONTRACTS,
        panels='64 archived schedules and 64 new: one center changed from 1 event to 0 or 2, dates shifted and half of held schemas aliased',
        model='P11 seed08 frozen, A/B logits in both action orders, same remaining-set verifier for all arms',
        routing='menu fixed from public fixture before tool feedback; static fallback on layouts with no adaptive gain',
        evidence=['A actual page + common task and fixture','B adds consistent contracts','C adds per-contract counterfactuals','D adds singleton counts per action'],
        primary='strict opposite-optimum reply pairs within same layout, both decisions correct; jointly confirmed contracts / 768',
        gate='C evidence route requires positive C-static on held and improved paired accuracy vs A; inspect clustered uncertainty before attributing gains',
        intervals='paired percentile bootstrap by layout, 20,000 draws for identification rate differences'))
    log_path = OUT / 'votes.jsonl'
    votes = {}
    if log_path.exists():
        for line in log_path.read_text().splitlines():
            entry = json.loads(line)
            votes[entry['key']] = entry
    agent = FrozenAgent()
    rows, branches, pairs = [], [], []
    for split, index, starts, counts, fields in fixtures():
        records = calendar(counts)
        days = [r['date'] for r in records]
        windows = [(d,iso(d,2)) for d in starts] + [(iso(d,i),iso(d,j)) for d in starts
            for i in range(3) for j in range(i,3) if (i,j)!=(0,2)]
        table = [[tuple(predicted_dates(*w,op,days)[:cap]) for op,cap in CONTRACTS] for w in windows]
        menu, route = plan(table)
        order_rng = random.Random(f'{SEED}/{index}/{split}')
        ordering = list(range(len(CONTRACTS)))
        order_rng.shuffle(ordering)
        presentation = order_rng.sample(menu,2)
        histories = {}
        for truth, ((l,r),cap) in enumerate(CONTRACTS):
            def call(q):
                return tuple(x['date'] for x in execute(records,(l==0,r==0),*windows[q])[:cap])
            seen = call(0)
            rem = [h for h in ordering if table[0][h]==seen]
            assert truth in rem
            if seen not in histories:
                scores = [singleton_count(partition(table,rem,[q])) for q in menu]
                oracle = menu[1] if scores[1]>scores[0] else menu[0]
                choice = dict(static=menu[0], oracle=oracle)
                for arm in 'ABCD':
                    choice[arm] = menu[0]
                    if not route or len(rem)==1:
                        continue
                    key = json.dumps([split,index,list(seen),arm])
                    if key not in votes:
                        ballots = []
                        margin = 0
                        for order in (presentation,presentation[::-1]):
                            prompt = views(arm,days,windows,fields,seen,rem,table,order,ordering)
                            logits = vote(agent,prompt,'AB')
                            ballots.append(dict(order=order, logits=logits))
                            margin += (logits[0]-logits[1])*(1 if order[0]==menu[0] else -1)
                        votes[key] = dict(key=key,ballots=ballots,choice=menu[int(margin<0)])
                        with log_path.open('a',encoding='utf-8') as f:
                            f.write(json.dumps(votes[key])+'\n')
                    choice[arm] = votes[key]['choice']
                branch = dict(split=split,index=index,seen=seen,remaining=rem,menu=menu,
                    requests=[windows[q] for q in menu], scores=scores,choice=choice,
                    gold=oracle if route and len(rem)>1 and scores[0]!=scores[1] else None)
                histories[seen] = branch
                branches.append(branch)
            success, outcomes = {}, {}
            for arm,q in histories[seen]['choice'].items():
                reply = call(q) if len(rem)>1 else None
                final = rem if reply is None else [h for h in rem if table[q][h]==reply]
                assert truth in final
                success[arm] = len(final)==1
                outcomes[arm] = dict(request=q if reply is not None else None, reply=reply,remaining=final)
            rows.append(dict(split=split,index=index,truth=truth,seen=seen,calls=1+int(len(rem)>1),success=success,outcomes=outcomes))
        for a,b in combinations(histories.values(),2):
            if None in (a['gold'],b['gold']) or a['gold']==b['gold']:
                continue
            pairs.append(dict(split=split,index=index,seen=[a['seen'],b['seen']],
                correct={arm:a['choice'][arm]==a['gold'] and b['choice'][arm]==b['gold'] for arm in ARMS}))
    write('decisions.json',rows)
    write('branches.json',branches)
    write('pairs.json',pairs)
    summary = {s:summarize(rows,branches,pairs,s) for s in ('reference','held')}
    summary.update(forwards=len(votes)*2,weight_updates=0)
    write('summary.json',summary)
    print(json.dumps(summary),flush=True)


if __name__=='__main__':
    main()
