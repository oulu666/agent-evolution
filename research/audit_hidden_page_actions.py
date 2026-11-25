"""Exact two-call bounds when the calendar API can also query shorter intervals."""
from collections import Counter
from itertools import product

from run_hidden_page_probes import (OUT, CONTRACTS, CAPS, MASKS, WINDOWS, WORLDS, bank,
                                    execute, predict, predicted_dates, partition, singleton_count, write)
from run_interface_boundaries import iso


def design(table, firsts, queries):
    all_h = range(len(CONTRACTS))
    pairs = ((a, b) for a in firsts for b in queries if a != b)
    static = max(pairs, key=lambda p: singleton_count(partition(table, all_h, p)))
    trees = {}
    scores = {}
    for a in firsts:
        tree = {}
        score = 0
        for (reply,), group in partition(table, all_h, [a]).items():
            b = max((q for q in queries if a != q),
                    key=lambda q: singleton_count(partition(table, group, [q])))
            tree[reply] = b
            score += singleton_count(partition(table, group, [b]))
        trees[a], scores[a] = tree, score
    first = max(firsts, key=scores.get)
    return static, first, trees[first]


def main():
    OUT.mkdir(exist_ok=True)
    intervals = list(WINDOWS)
    for start, end in WINDOWS:
        days = [start, iso(start, 1), end]
        intervals.extend((a, b) for a in days for b in days if a <= b and (a, b) != (start, end))
    all_h = range(len(CONTRACTS))
    bounds, cases = [], []
    for layout in product(MASKS, repeat=3):
        records = bank(layout)
        days = [r['date'] for r in records]
        table = [[tuple(predicted_dates(a, b, offsets, days)[:cap]) for offsets, cap in CONTRACTS]
                 for a, b in intervals]
        assert all(predict(days, q, h) == table[q][h] for q in range(3) for h in all_h)
        for name, queries in [('full', range(3)), ('subranges', range(len(intervals)))]:
            for mode, firsts in [('shared', [0]), ('free', queries)]:
                static, first, tree = design(table, firsts, queries)
                row = dict(layout=layout, menu=name, mode=mode, static_pair=static, first=first,
                           tree=[dict(reply=r, second=q) for r, q in tree.items()],
                           static=0, adaptive=0, gains=0, losses=0,
                           all_queries=singleton_count(partition(table, all_h, queries)))
                for world, cap in product(WORLDS, CAPS):
                    l, r = WORLDS[world]
                    truth = CONTRACTS.index(((0 if l else -1, 0 if r else 1), cap))
                    observed = {}
                    for arm, a, fixed_b in [('static', static[0], static[1]), ('adaptive', first, None)]:
                        def invoke(q):
                            return tuple(t['date'] for t in execute(records, (l, r), *intervals[q])[:cap])
                        reply = invoke(a)
                        rem = [h for h in all_h if table[a][h] == reply]
                        b = fixed_b if arm == 'static' else tree[reply]
                        if len(rem) > 1:
                            other = invoke(b)
                            final = [h for h in rem if table[b][h] == other]
                        else:
                            b, other, final = None, None, rem
                        assert truth in final
                        observed[arm] = dict(first=a, reply=reply, remaining=rem, second=b,
                                             second_reply=other, final=final)
                        row[arm] += len(final) == 1
                    sg, ag = (len(observed[a]['final']) == 1 for a in ('static', 'adaptive'))
                    row['gains'] += ag and not sg
                    row['losses'] += sg and not ag
                    cases.append(dict(layout=layout, menu=name, mode=mode, world=world, cap=cap, **observed))
                bounds.append(row)
    summary = []
    for menu, mode in product(['full', 'subranges'], ['shared', 'free']):
        selected = [r for r in bounds if (r['menu'], r['mode']) == (menu, mode)]
        counts = Counter(r['adaptive'] - r['static'] for r in selected)
        episode_rows = [r for r in cases if (r['menu'], r['mode']) == (menu, mode)]
        summary.append(dict(menu=menu, mode=mode, layout_gain_histogram=counts,
            calls={a:sum(1+(r[a]['second'] is not None) for r in episode_rows) for a in ['static','adaptive']},
            **{k:sum(r[k] for r in selected) for k in ['static','adaptive','gains','losses','all_queries']}))
    write('action_space.json', dict(intervals=intervals, summary=summary, bounds=bounds))
    write('action_traces.json', cases)
    print(summary, flush=True)


if __name__ == '__main__':
    main()
