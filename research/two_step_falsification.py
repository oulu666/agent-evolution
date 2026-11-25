"""Finite-menu falsification of a single nominated deterministic contract."""
from collections import Counter
from pathlib import Path
import json
import random
import time

from third_probe_compare import one_edit
from third_probe_inputs import RULES, public, run

OUT = Path(__file__).resolve().parents[1] / 'runs_two_step_20261123'
METHODS = ('greedy', 'static', 'adaptive', 'risk', 'oracle')
FAULTS = ('overlap_cache', 'reopen', 'backward', 'owner_overflow', 'quarter')
LAYOUTS = range(1200, 1248)


def save(name, obj):
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding='utf8')


def backend(h, fault, req, hist):
    expected = run(req['rows'], h)
    last = hist[-1] if hist else None
    if fault == 'overlap_cache' and last and last['name'] != req['name']:
        if max(last['start'], req['start']) <= min(last['end'], req['end']):
            return run(last['rows'], h)
    if fault == 'reopen' and len(hist) >= 2:
        if req['name'] == hist[-2]['name'] and req['name'] != last['name']:
            return ()
    if fault == 'backward' and last and req['start'] < last['start']:
        return expected[1:]
    if fault == 'owner_overflow':
        rows = sorted(req['rows'], key=lambda r: r[1])
        if len(rows) >= 4 and rows[2][2] == rows[3][2]:
            return expected + (rows[3][0],)
    if fault == 'quarter' and (req['start'][:4], (int(req['start'][5:7])-1)//3) != (
            req['end'][:4], (int(req['end'][5:7])-1)//3):
        return expected[:-1]
    return expected


class Planner:
    def __init__(self, h, bank, first_result, layout):
        self.bank = bank
        self.order = list(range(len(bank)))
        random.Random(141120 + layout).shuffle(self.order)
        self.expected = [run(q['rows'], h) for q in bank]
        live = [r for r in RULES if run(bank[0]['rows'], r) == first_result]
        self.table = [[run(q['rows'], r) for r in live] for q in bank]
        neighbors = [i for i, r in enumerate(live) if one_edit(h, r)
                     and any(row[i] != y for row, y in zip(self.table, self.expected))]
        self.full = []
        self.kill = []
        self.disagreement = []
        for row, y in zip(self.table, self.expected):
            self.full.append(sum(1 << i for i, v in enumerate(row) if v != y))
            self.kill.append(sum(1 << j for j, i in enumerate(neighbors) if row[i] != y))
            self.disagreement.append(-sum(n*n for n in Counter(row).values()))
        self.history_bit = 1 << len(neighbors)
        self.count = len(neighbors) + 1
        self.all_bits = (1 << self.count) - 1
        self.outside = 0
        for bits in self.full:
            self.outside |= bits
        self.live_count = len(live)

    def mutations(self, before, q):
        # The old repetition defect is a known development mutant. Test faults are hidden.
        return self.kill[q] | (self.history_bit if before == q and self.expected[q] else 0)

    def best_third(self, second, remaining):
        return max(self.order, key=lambda q: (
            (remaining & self.mutations(second, q)).bit_count(), self.disagreement[q]))

    def risk_score(self, a, b):
        first = self.mutations(0, a)
        killed = (first | self.mutations(a,b)).bit_count()
        residual = 0.5 * (1 - killed / self.count)
        can_adopt = (self.full[a] | self.full[b]) == self.outside
        loss = min(4 * residual, 0.5) if can_adopt else 0.5
        third_cost = 0.01 * (1 - 0.5 * first.bit_count() / self.count)
        return (-loss-third_cost, killed, first.bit_count(), self.disagreement[a], self.disagreement[b])

    def risk_third(self, a):
        return max(self.order, key=lambda b: self.risk_score(a,b))

    def plan(self, method):
        if method == 'greedy':
            a = max(self.order, key=lambda q: (
                self.mutations(0, q).bit_count(), self.disagreement[q]))
            return a, None
        def score(a, b):
            first = self.mutations(0, a)
            killed = (first | self.mutations(a, b)).bit_count()
            tie = (first.bit_count(), self.disagreement[a], self.disagreement[b])
            return (killed, *tie)
        if method == 'static':
            return max(((a,b) for a in self.order for b in self.order), key=lambda ab: score(*ab))
        if method == 'risk':
            a = max(self.order,key=lambda a:self.risk_score(a,self.risk_third(a)))
            return a, None
        # Conditional optimum given that the second observation agrees with H.
        branches = [(a, self.best_third(a, self.all_bits ^ self.mutations(0,a))) for a in self.order]
        a, _ = max(branches, key=lambda ab: score(*ab))
        return a, None


def oracle_pairs(h, bank, service, expected):
    first = bank[0]
    checked = 0
    for i, a in enumerate(bank):
        checked += 1
        if backend(h, service, a, [first]) != expected[i]:
            return (i, None), checked
    for i, a in enumerate(bank):
        for j, b in enumerate(bank):
            checked += 1
            if backend(h, service, b, [first, a]) != expected[j]:
                return (i, j), checked
    return None, checked


def main():
    rows, costs, witnesses = [], [], []
    for layout in LAYOUTS:
        h, _, catalog = public(layout)
        for perm, bank in [('read', catalog[:12]), ('build', catalog)]:
            start = time.process_time()
            first_result = backend(h, 'stable', bank[0], [])
            p = Planner(h, bank, first_result, layout)
            prep = time.process_time() - start
            plans = {}
            for method in METHODS[:-1]:
                start = time.process_time()
                wall = time.perf_counter()
                a,b = p.plan(method)
                plans[method] = (a,b)
                costs.append(dict(layout=layout,perm=perm,method=method,
                    plan_wall=time.perf_counter()-wall,
                    shared_cpu=prep,plan_cpu=time.process_time()-start,menu=len(bank),
                    live=p.live_count,mutants=p.count,pair_scores=len(bank)**2 if method!='greedy' else 0,
                    predictions=len(RULES)+len(bank)*p.live_count))
            for fault in ('stable', *FAULTS):
                start = time.process_time()
                witness, probes = oracle_pairs(h, bank, fault, p.expected)
                witnesses.append(dict(layout=layout,perm=perm,fault=fault,witness=witness,
                    audit_calls=probes,audit_cpu=time.process_time()-start))
                for method in METHODS:
                    start = time.process_time()
                    a,b = (witness or (0,0)) if method=='oracle' else plans[method]
                    observed = [backend(h,fault,bank[0],[])]
                    assert observed[0] == first_result
                    observed.append(backend(h,fault,bank[a],[bank[0]]))
                    refuted = observed[-1] != p.expected[a]
                    ks = p.mutations(0,a)
                    full = p.full[a]
                    qs = [0,a]
                    replan_wall = 0.0
                    if not refuted:
                        if b is None:
                            wall = time.perf_counter()
                            b = p.risk_third(a) if method=='risk' else p.best_third(a, p.all_bits ^ ks)
                            replan_wall = time.perf_counter()-wall
                        observed.append(backend(h,fault,bank[b],[bank[0],bank[a]]))
                        refuted = observed[-1] != p.expected[b]
                        ks |= p.mutations(a,b)
                        full |= p.full[b]
                        qs.append(b)
                    remaining = p.count - ks.bit_count()
                    risk = remaining / (p.count + remaining)
                    # Stable and all non-refuted hidden faults have exactly the same trace.
                    eligible = not refuted and full == p.outside
                    accepted = eligible and (method != 'risk' or 4*risk <= 1-risk)
                    rows.append(dict(layout=layout,perm=perm,fault=fault,method=method,
                        queries=qs,observed=observed,expected=[p.expected[q] for q in qs],
                        refuted=refuted,reachable=witness is not None,accepted=accepted,
                        eligible=eligible,risk=risk,replan_wall=replan_wall,online_cpu=time.process_time()-start))
    save('traces.json', rows)
    save('costs.json', costs)
    save('reachability.json', witnesses)
    for r,s in zip(rows[1::5],rows[2::5]):
        assert r['queries']==s['queries'] and r['observed']==s['observed']
    assert all(not r['refuted'] or r['reachable'] for r in rows)
    assert all(r['refuted']==r['reachable'] for r in rows if r['method']=='oracle')
    print(len(rows), 'completed traces')


if __name__ == '__main__':
    main()
