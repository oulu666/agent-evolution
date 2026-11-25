"""Online identification control on archived cases, with no nominated contract."""
import json
from collections import Counter, defaultdict

from third_probe_identifiability import OUT as HIST
from risk_worlds import layouts, endpoint, focused, run
from two_step_falsification import RULES, save


def partition(ids, column):
    groups = defaultdict(list)
    for i in ids:
        groups[column[i]].append(i)
    return groups


def quality(groups, signatures):
    certified = sum(len(g) for g in groups if len({signatures[i] for i in g}) == 1)
    return certified, -sum(len(g)**2 for g in groups)


def policy(table, signatures, ids, method):
    choices = []
    for a in range(1,9):
        observed = partition(ids, table[a])
        legal = [b for b in range(1,len(table)) if a!=b]
        def value(g,b):
            return quality(partition(g,table[b]).values(),signatures)
        if method == 'static':
            def fixed_score(b):
                scores = [value(g,b) for g in observed.values()]
                return tuple(map(sum,zip(*scores)))
            b = max(legal,key=fixed_score)
            score = fixed_score(b)
            branches = dict.fromkeys(observed,b)
        else:
            branches = {k:max(legal,key=lambda b:value(g,b)) for k,g in observed.items()}
            scores = [value(g,branches[k]) for k,g in observed.items()]
            score = tuple(map(sum,zip(*scores))) if method=='adaptive' else quality(observed.values(),signatures)
        choices.append((score,a,branches))
    _,a,branches = max(choices,key=lambda x:x[0])
    return a,branches


def main():
    archived = json.loads((HIST/'prior_32.json').read_text())
    out = []
    for layout,_,_,first,bank,held in layouts():
        cases = [r for r in archived if int(r['id'].split('-')[0])==layout]
        if not cases:
            continue
        menu = [first,*bank]
        table = [[run(q,r) for r in RULES] for q in menu]
        signatures = list(zip(*table))
        checks = held+[focused(700000+layout*30+j,j%6) for j in range(12)]
        for case in cases:
            _,kind,variant = case['id'].split('-')
            def get(q):
                return endpoint(q,kind,int(variant))
            first_result = get(first)
            ids = [i for i,x in enumerate(table[0]) if x==first_result]
            for method in ('greedy','static','adaptive'):
                a,branches = policy(table,signatures,ids,method)
                ya = get(menu[a])
                b = branches[ya]
                yb = get(menu[b])
                left = [i for i in ids if table[a][i]==ya and table[b][i]==yb]
                assert left
                out.append(dict(id=case['id'],category=case['category'],method=method,
                    plan=[a,b],old=case['old'],remaining=len(left),
                    public_certificate=len({signatures[i] for i in left})==1,
                    held_certificate=all(run(q,RULES[i])==get(q) for q in checks for i in left)))
    save('historical.json',out)
    print(Counter((r['category'],r['method']) for r in out if r['held_certificate']))


if __name__=='__main__':
    main()
