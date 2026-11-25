"""Two-proposal, two-call calendar extension synthesis with held-out execution."""
import argparse
import json
from collections import Counter

from semantic_extension_bank import CAP,NAMES,STATES,base,language,run_extension,target,tasks
from semantic_repair_run import Inference,as_json,save


def discrepancy(pred,obs):
    if pred is None:
        return 'Previous candidate could not be executed.'
    for i in range(max(len(pred),len(obs))):
        x=pred[i] if i<len(pred) else '<end>'
        y=obs[i] if i<len(obs) else '<end>'
        if x!=y:
            return f'First mismatch at output position {i+1}: predicted {x}, observed {y}.'
    return 'All observed output positions match.'


def ranked(task):
    # Infer visible local features, without executing trial extensions during ranking.
    alias=task['alias']
    uid,when,team,state,rank=NAMES[alias]
    seq=sorted(task['records'],key=lambda r:r[when])
    obs=task['obs']
    prefix=seq[:CAP]
    omitted=[r for r in prefix if r[uid] not in obs]
    representatives=[next(r for r in seq if r[uid]==v) for v in obs]
    pos='after' if len(obs)<CAP else 'before'
    def score(h):
        op,k,arg=h[:3]
        if op=='unique':
            if k=='row':
                return -5
            values=[r[k] for r in prefix]
            clash=len(values)-len(set(values))
            over=len(representatives)-len({r[k] for r in representatives})
            return 3*clash-3*over+(h[-1]==pos)
        if op=='exclude':
            return (2*sum(r[k]==arg for r in omitted)-3*sum(r[k]==arg for r in representatives)
                    +(h[-1]==pos))
        evidence=0
        for i,r in enumerate(representatives):
            for s in representatives[i+1:]+omitted:
                if r[when]==s[when] and r[k]!=s[k]:
                    evidence+=1 if (r[k]<s[k])==(arg=='asc') else -1
        return evidence*2+int(len(obs)==CAP)
    return sorted(language(alias),key=score,reverse=True)


def prompt(t,arm,previous=None,rule=None):
    alias=t['alias']
    uid,when,team,state,rank=NAMES[alias]
    local=arm in ('local','blind')
    text=(f'Infer the behaviour of events.list from its actual output IDs. The stable primary sort is {when} ascending, '
          f'the page size is {CAP}. Keep both. Source array order breaks unresolved ties. '
          f'Known old pipeline: [["sort","{when}","asc"],["take",{CAP}]]. '
          f'Output field is {uid}. Fields: {", ".join(NAMES[alias])}.\n')
    if arm!='blind':
        text+=(f'Extension syntax: ["unique",key,position] (keep first per {uid}, {team} or row); '
               f'["exclude","{state}",value,position] (skip matching rows); '
               f'["tie",key,direction] (secondary {rank} or {uid}, asc or desc). '
               'Position is "before" or "after" take. A tie operation follows the primary sort and precedes take.\n')
    else:
        text+=('Invent one missing list operation. Encode it as an array [verb, field, arguments...]. '
               'For order use asc/desc; for location relative to the page use before/after.\n')
    text+='Input rows: '+json.dumps(t['records'],separators=(',',':'))+'\nActual returned IDs: '+json.dumps(t['obs'])+'\n'
    if arm in ('concrete','local','blind'):
        pred=base(t['records'],alias) if previous is None else (run_extension(t['records'],rule,alias) if rule else None)
        if arm=='concrete':
            text+='Predicted IDs: '+json.dumps(pred)+'. '
        text+=discrepancy(pred,t['obs'])+'\n'
    if previous is not None:
        text+='Prior proposal: '+previous+'\n'
        if arm=='reflect':
            text+='Reflect on why your previous answer might be wrong and reconsider your reasoning. '
        elif arm=='direct':
            text+='Provide another plausible proposal. '
        else:
            text+='Repair the prior proposal if needed. '
    if local:
        text+='Return just the one added operation as a JSON array.'
    else:
        text+='Return the full three-operation pipeline as a JSON array of arrays, with the extension in its execution position.'
    return text


def parse(raw,arm,alias):
    v=as_json(raw)
    if not isinstance(v,list):
        return None
    if arm not in ('local','blind'):
        primary=['sort',NAMES[alias][1],'asc']
        page=['take',CAP]
        if len(v)!=3 or v[0]!=primary or page not in v:
            return None
        where=v.index(page)
        if where not in (1,2):
            return None
        v=v[3-where]
        if not isinstance(v,list) or not v or (where==1)!=(v[-1]=='after'):
            return None
    if not v or not all(isinstance(x,str) for x in v):
        return None
    if arm=='blind':
        aliases={'dedup':'unique','deduplicate':'unique','distinct':'unique','drop_duplicates':'unique',
                 'filter_out':'exclude','skip':'exclude','then_by':'tie','tie_break':'tie','secondary_sort':'tie'}
        v=[aliases.get(v[0].lower(),v[0].lower()),*v[1:]]
    h=tuple(v)
    return h if h in language(alias) else None


def assess(t,proposals):
    alias=t['alias']
    def predict(x,h):
        return run_extension(x,h,alias)
    consistent=list(dict.fromkeys(h for h in proposals if h and predict(t['records'],h)==t['obs']))
    def separation(x):
        responses=[tuple(base(x,alias))]+[tuple(predict(x,h)) for h in consistent]
        return -sum(v*v for v in Counter(responses).values())
    probe=max(range(len(t['probe'])),key=lambda i:separation(t['probe'][i]))
    x=t['probe'][probe]
    returned=target(x,t['truth'],alias)
    survivors=[h for h in consistent if predict(x,h)==returned]
    deployed=survivors[0] if len(survivors)==1 else None
    correct_pages=sum(predict(k,deployed)==target(k,t['truth'],alias) for k in t['held']) if deployed else 0
    return dict(proposals=proposals,valid=sum(h is not None for h in proposals),first_fit=consistent,
        probe=probe,probe_obs=returned,survivors=survivors,deployed=deployed,exact=deployed==t['truth'],
        proposed_truth=t['truth'] in proposals,held=correct_pages,
        control_ok=bool(deployed and predict(t['neutral'],deployed)==base(t['neutral'],alias)),
        false_adopt=deployed is not None and deployed!=t['truth'])


def main(size):
    ts=list(tasks())
    save('B_protocol.json',dict(old='single sort and cap; first fixture rejects even any one-field sort, direction and cap',
        grammar='16 typed extensions; two proposals per main arm, two black-box calibration calls; full search separately',
        active='from 8 new public fixtures choose maximum disagreement of first-consistent proposals and legacy pipeline',
        evaluation='16 independent unseen layouts per scenario plus neutral regression; keep only unique surviving proposal',
        splits='3 dev scenarios, 24 final (12 contracts x 2 independent layouts/schemas); initial fixtures selected only for legacy conflict',
        blind='no operation list; canonical compiler plus declared alias set; retain all raw suggestions for interpretation',
        sizes='0.6B P11 all arms; native 1.7B local and blind; frozen, 2x96 generated tokens maximum'))
    agent=Inference(size)
    arms=['direct','reflect','concrete','local','blind'] if size=='06' else ['local','blind']
    rows=[]
    for arm in arms:
        p1=agent.run([prompt(t,arm) for t in ts],96)
        h1=[parse(p['raw'],arm,t['alias']) for p,t in zip(p1,ts)]
        p2=agent.run([prompt(t,arm,p['raw'],h) for t,p,h in zip(ts,p1,h1)],96)
        for t,p,q,h in zip(ts,p1,p2,h1):
            result=assess(t,[h,parse(q['raw'],arm,t['alias'])])
            rows.append(dict(id=t['id'],split=t['split'],truth=t['truth'],arm=arm,
                             generations=[p['hash'],q['hash']],tokens=p['tokens']+q['tokens'],**result))
        save(f'B_{size}.json',rows)
        print('B',size,arm,sum(r['exact'] for r in rows if r['split']=='final' and r['arm']==arm),flush=True)
    for t in ts:
        for arm,pool in [('search2',ranked(t)[:2]),('search_all',language(t['alias']))]:
            rows.append(dict(id=t['id'],split=t['split'],truth=t['truth'],arm=arm,tokens=0,**assess(t,pool)))
    save(f'B_{size}.json',rows)
    save('B_fixtures.json',ts)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('size',choices=['06','17'])
    main(p.parse_args().size)
