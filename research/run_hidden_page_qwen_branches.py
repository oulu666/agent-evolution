"""Measure frozen-model selection where a precomputed two-action menu can help."""
import json
from itertools import product

from run_hidden_page_probes import (OUT, CONTRACTS, CAPS, WORLDS, bank, execute, partition,
                                    predicted_dates, singleton_count, qwen_pick, write, FrozenAgent)


def main():
    audit = json.loads((OUT / 'action_space.json').read_text())
    windows = [tuple(pair) for pair in audit['intervals']]
    designs = [d for d in audit['bounds'] if d['menu'] == 'subranges' and d['mode'] == 'shared']
    agent = FrozenAgent()
    logs, rows = [], []
    for design in designs:
        layout = design['layout']
        records = bank(layout)
        days = [record['date'] for record in records]
        table = [[tuple(predicted_dates(*w, offsets, days)[:cap]) for offsets, cap in CONTRACTS] for w in windows]
        groups = partition(table, range(len(CONTRACTS)), [0])
        base = design['static_pair'][1]
        def solved(group, q):
            return singleton_count(partition(table, group, [q]))
        def menu_yield(extra):
            return sum(max(solved(group, base), solved(group, extra)) for group in groups.values())
        extra = max((q for q in range(1, len(windows)) if q != base), key=menu_yield)
        route = menu_yield(extra) > design['static']
        cache = {}
        for world, cap in product(WORLDS, CAPS):
            left, right = WORLDS[world]
            truth = CONTRACTS.index(((0 if left else -1, 0 if right else 1), cap))
            def call(query):
                return tuple(r['date'] for r in execute(records, (left, right), *windows[query])[:cap])
            first = call(0)
            rem = groups[(first,)]
            if route and len(rem) > 1 and first not in cache:
                cache[first] = qwen_pick(agent, days, first, rem, windows, (base, extra))
                logs.append(dict(layout=layout, reply=first, candidates=rem, **cache[first]))
            qwen = cache[first]['choice'] if first in cache else base
            controller = max((base, extra), key=lambda q: solved(rem, q)) if route else base
            for arm, q in [('preplanned', base), ('qwen', qwen), ('controller', controller)]:
                second = call(q) if len(rem) > 1 else None
                final = rem if second is None else [h for h in rem if table[q][h] == second]
                assert truth in final
                rows.append(dict(layout=layout, routed=route, menu=[base,extra], world=world, cap=cap,
                                 truth=truth, arm=arm, reply=first, candidates=rem, second=q if second is not None else None,
                                 observed=second, final=final, correct=len(final)==1))
    summary = {}
    for arm in ['preplanned','qwen','controller']:
        part = [r for r in rows if r['arm'] == arm]
        base_rows = [r for r in rows if r['arm'] == 'preplanned']
        summary[arm] = dict(correct=sum(r['correct'] for r in part), calls=sum(1+(r['second'] is not None) for r in part),
            routed_correct=sum(r['routed'] and r['correct'] for r in part), routed_episodes=sum(r['routed'] for r in part),
            gains=sum(r['correct'] and not b['correct'] for r,b in zip(part,base_rows)),
            losses=sum(b['correct'] and not r['correct'] for r,b in zip(part,base_rows)))
    write('qwen_subrange.json', dict(summary=summary, decisions=rows, ballots=logs, model_forwards=agent.calls))
    print(summary, flush=True)


if __name__ == '__main__':
    main()
