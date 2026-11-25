"""Identify both calendar boundaries and an undocumented first-page size."""
import json
from collections import defaultdict
from itertools import combinations, product
from math import log2
from pathlib import Path

from run_sparse_interface_probes import WINDOWS, MASKS, bank
from run_interface_boundaries import WORLDS, OPTIONS, execute, predicted_dates
from run_interface_fact_readout import vote
from run_rsi_operator_memory import FrozenAgent

OUT = Path(__file__).resolve().parents[1] / 'runs_hidden_page_probes_20261123'
CAPS = (1, 2, None)
CONTRACTS = tuple(product(OPTIONS, CAPS))
QUERIES = tuple(range(len(WINDOWS)))


def write(name, value):
    path = OUT / name
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def predict(days, query, h):
    offsets, cap = CONTRACTS[h]
    return tuple(predicted_dates(*WINDOWS[query], offsets, days)[:cap])


def call_tool(records, world, cap, query):
    matches = execute(records, WORLDS[world], *WINDOWS[query])
    return tuple(row['date'] for row in matches[:cap])


def partition(table, candidates, queries):
    groups = defaultdict(list)
    for h in candidates:
        key = tuple(table[q][h] for q in queries)
        groups[key].append(h)
    return groups


def singleton_count(groups):
    return sum(len(group) == 1 for group in groups.values())


def select_second(table, first, candidates, method):
    def score(q):
        groups = partition(table, candidates, [q])
        if method == 'entropy':
            return -sum(len(g) * log2(len(g)) for g in groups.values())
        return singleton_count(groups)
    return max((q for q in QUERIES if q != first), key=score)


def adaptive_yield(table, first):
    count = 0
    for candidates in partition(table, range(len(CONTRACTS)), [first]).values():
        q = select_second(table, first, candidates, 'success')
        count += singleton_count(partition(table, candidates, [q]))
    return count


def qwen_pick(agent, days, reply, candidates, windows=WINDOWS, alternatives=(1, 2)):
    hypotheses = [dict(start_inclusive=(left == 0), end_inclusive=(right == 0), cap=cap)
                  for (left, right), cap in (CONTRACTS[h] for h in candidates)]
    context = (
        'A calendar API returns matching events in ascending order, truncated at its hidden page size '
        '(null means unlimited). Each known date has one event. Identify both boundary flags and page size. '
        'One more request is allowed. Pick the request most likely to leave exactly one possible contract. '
        f'Known dates: {json.dumps(days)}. First request: {WINDOWS[0]}. '
        f'Actual first page: {list(reply)}. Equally likely remaining contracts: {json.dumps(hypotheses)}.'
    )
    ballots = []
    margin = 0
    for a, b in (alternatives, alternatives[::-1]):
        scores = vote(agent, context + f' A = {windows[a]}. B = {windows[b]}. Reply with one letter.', 'AB')
        margin += (scores[0] - scores[1]) * (1 if a == alternatives[0] else -1)
        ballots.append(dict(order=[a, b], scores=scores))
    return dict(choice=alternatives[0 if margin >= 0 else 1], ballots=ballots)


def main():
    OUT.mkdir(exist_ok=True)
    write('protocol.json', dict(layouts=MASKS, windows=WINDOWS, hypotheses=CONTRACTS,
          primary='unique correct joint boundary and cap identification; uniform worlds within layout',
          baseline='optimize single precommitted query pair over same candidate space and primary metric',
          arms='shared first: fixed, static, entropy, success, qwen; free first: best static and best adaptive',
          budget='two distinct first-page queries maximum; stop as soon as joint contract is unique',
          observations='known calibration fixture; actual response dates, no count metadata, no cursor, no total',
          ties='lowest query index, lexicographic pair; Qwen averages both label orders',
          model='P11 seed08 frozen with exact surviving contracts; same prompt cached by observed history',
          secondary='whether boundary pair alone is unique under same policies'))
    agent = FrozenAgent()
    traces = []
    ballots_path = OUT / 'ballots.jsonl'
    logs = {}
    if ballots_path.exists():
        for line in ballots_path.read_text().splitlines():
            item = json.loads(line)
            logs[(tuple(item['layout']), tuple(item['observed']))] = item['ballot']
    all_h = list(range(len(CONTRACTS)))
    for layout in product(MASKS, repeat=3):
        records = bank(layout)
        days = [r['date'] for r in records]
        table = [[predict(days, q, h) for h in all_h] for q in QUERIES]
        pairs = list(combinations(QUERIES, 2))
        yields = {pair: singleton_count(partition(table, all_h, pair)) for pair in pairs}
        best_pair = max(pairs, key=yields.get)
        anchored = max((pair for pair in pairs if pair[0] == 0), key=yields.get)
        best_first = max(QUERIES, key=lambda q: adaptive_yield(table, q))
        start = len(traces)
        for world, cap in product(WORLDS, CAPS):
            left, right = WORLDS[world]
            truth = CONTRACTS.index(((0 if left else -1, 0 if right else 1), cap))
            for arm, first in [('fixed', 0), ('static', 0), ('qwen', 0), ('entropy', 0),
                               ('success', 0), ('static_free', best_pair[0]), ('success_free', best_first)]:
                seen = call_tool(records, world, cap, first)
                rem = [h for h in all_h if table[first][h] == seen]
                second = again = None
                final = rem
                if len(rem) > 1:
                    if arm == 'qwen':
                        key = layout, seen
                        if key not in logs:
                            logs[key] = qwen_pick(agent, days, seen, rem)
                            with ballots_path.open('a', encoding='utf-8') as out:
                                out.write(json.dumps(dict(layout=layout, observed=seen, ballot=logs[key])) + '\n')
                        second = logs[key]['choice']
                    elif arm in ('fixed', 'static', 'static_free'):
                        second = {'fixed': 1, 'static': anchored[1], 'static_free': best_pair[1]}[arm]
                    else:
                        second = select_second(table, first, rem, arm)
                    again = call_tool(records, world, cap, second)
                    final = [h for h in rem if table[second][h] == again]
                assert truth in final
                traces.append(dict(layout=layout, world=world, cap=cap, truth=truth, arm=arm,
                    first=first, observed=seen, candidates=rem, second=second, returned=again, final=final,
                    joint=len(final) == 1, boundary=len({CONTRACTS[h][0] for h in final}) == 1))
        local = traces[start:]
        for arm, expected in [('static', yields[anchored]), ('static_free', yields[best_pair]),
                              ('success', adaptive_yield(table, 0)), ('success_free', adaptive_yield(table, best_first))]:
            assert sum(r['joint'] for r in local if r['arm'] == arm) == expected
    write('decisions.json', traces)
    summary = {}
    for arm in dict.fromkeys(r['arm'] for r in traces):
        group = [r for r in traces if r['arm'] == arm]
        correct = sum(r['final'] == [r['truth']] for r in group)
        calls = sum(1 + (r['second'] is not None) for r in group)
        summary[arm] = dict(episodes=len(group), correct=correct, wrong=sum(r['joint'] for r in group)-correct,
                            abstain=sum(not r['joint'] for r in group), calls=calls, calls_per_correct=calls/correct,
                            boundary=sum(r['boundary'] for r in group))
    write('summary.json', dict(arms=summary, unique_model_decisions=len(logs), model_forwards=2*len(logs), updates=0))
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()
