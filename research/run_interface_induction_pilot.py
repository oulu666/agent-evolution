"""Free contract proposals from frozen Qwen; execute typed rules on independent calendars."""
import json
import random
import re
from itertools import product

from run_rsi_operator_memory import FrozenAgent, ROOT

OUT = ROOT / 'runs_interface_induction_20261123'


def write(name, value):
    path = OUT / name
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def fixture(keys, n, seed, aligned=False):
    rng = random.Random(seed)
    first, second = list(range(n)), list(range(n))
    rng.shuffle(first)
    if aligned:
        second = first[:]
    else:
        rng.shuffle(second)
    ids = rng.sample(range(100,990),n)
    return [dict(id=str(ids[i]), **{keys[0]:9+first[i], keys[1]:40+second[i]}) for i in range(n)]


def backend(records, key, desc, cap):
    ordered = sorted(records, key=lambda r:r[key], reverse=desc)
    return [r['id'] for r in ordered[:cap]]


def interpret(raw, fields):
    text = raw.strip()
    wrapper = re.fullmatch(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL|re.IGNORECASE)
    if wrapper:
        text = wrapper[1]
    try:
        rule = json.loads(text)
    except ValueError:
        return None
    if not isinstance(rule,dict) or set(rule) != {'key','direction','take'}:
        return None
    if rule['key'] not in fields or rule['direction'] not in ('asc','desc'):
        return None
    n = rule['take']
    return rule if n is None or (type(n) is int and n>0) else None


def replay(rule, records):
    if rule is None:
        return None
    ranked = sorted(records, key=lambda x:x[rule['key']])
    if rule['direction']=='desc':
        ranked.reverse()
    return [r['id'] for r in ranked][:rule['take']]


def propose(agent, keys, observations, prior=None):
    text = ('Infer an executable contract for calendar.list(): it returns an ordered first page of event IDs. '
            f'Each event has fields id, {keys[0]}, {keys[1]}. The time fields are integers. '
            'Write a single JSON object with exactly these keys: "key" (actual field name used for sorting), '
            '"direction" ("asc" or "desc"), "take" (positive integer maximum page size or null for unlimited). '
            'Use the supplied fixture records and actual API returns when available. Give your best hypothesis. '
            'Return JSON only.\nObservations: '+json.dumps(observations,separators=(',',':')))
    if prior is not None:
        text += '\nPrior proposal to reconsider: '+prior
    raw = agent.generate([dict(role='user',content=text)],limit=96)
    return dict(raw=raw,rule=interpret(raw,['id',*keys]))


def main():
    OUT.mkdir(exist_ok=True)
    write('protocol.json',dict(worlds='2 aliases x 2 sort fields x 2 directions x 2 hidden caps (3,5)',
        proposal='unconstrained greedy text -> strict typed JSON; no offered candidate contracts or cap menu',
        stages=['schema only','2 aligned records; first proposal','8 mixed records; revise prior proposal'],
        validation='3 independent unseen calls with 11, 7 and 4 events; never shown for proposal or selection',
        comparator='enumerate schema fields, both directions and observationally possible positive sizes and null; deploy if unique',
        endpoints='correct executable hypothesis and exact predicted ordered ID list on held records; invalid abstains'))
    agent = FrozenAgent()
    results, generations = [], {}
    for variant, keys in enumerate([('begins','created'),('event_time','added_at')]):
        sparse = fixture(keys,2,83+variant,aligned=True)
        dense = fixture(keys,8,101+variant)
        held = [fixture(keys,n,180+7*variant+i) for i,n in enumerate([11,7,4])]
        for key, desc, cap in product(keys,[False,True],[3,5]):
            gold = dict(key=key,direction='desc' if desc else 'asc',take=cap)
            observations = [dict(records=bank, returned=backend(bank,key,desc,cap)) for bank in (sparse,dense)]
            held_returns = [backend(bank,key,desc,cap) for bank in held]
            prior = None
            proposals = {}
            for stage, count in [('schema',0),('first',1),('revision',2)]:
                prompt_key = json.dumps([keys,observations[:count],prior])
                if prompt_key not in generations:
                    generations[prompt_key] = propose(agent, keys, observations[:count], prior)
                proposal = generations[prompt_key]
                if stage=='first':
                    prior = proposal['raw']
                proposals[stage] = proposal
            consistent = []
            for k,d,n in product(['id',*keys],['asc','desc'],[None,*range(1,len(dense)+1)]):
                h=dict(key=k,direction=d,take=n)
                if all(replay(h,x['records'])==x['returned'] for x in observations):
                    consistent.append(h)
            proposals['enumeration'] = dict(rule=consistent[0] if len(consistent)==1 else None)
            stages = {}
            for stage,p in proposals.items():
                rule=p['rule']
                predictions=[replay(rule,bank) for bank in held]
                stages[stage]=dict(**p,exact_contract=rule==gold,
                    matches_calibration=[replay(rule,x['records'])==x['returned'] for x in observations],
                    predictions=predictions,held_correct=sum(a==b for a,b in zip(predictions,held_returns)))
            results.append(dict(variant=variant,truth=gold,calibration=observations,held_inputs=held,
                                held_returns=held_returns,consistent_rules=consistent,stages=stages))
    sums={}
    for stage in results[0]['stages']:
        values=[r['stages'][stage] for r in results]
        sums[stage]=dict(valid=sum(v['rule'] is not None for v in values),exact=sum(v['exact_contract'] for v in values),
            consistent=sum(all(v['matches_calibration']) for v in values),held_correct=sum(v['held_correct'] for v in values))
    write('results.json',results)
    write('summary.json',dict(stages=sums,unique_generations=agent.calls,weight_updates=0))
    print(sums,flush=True)


if __name__ == '__main__':
    main()
