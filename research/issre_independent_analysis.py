"""Create a complete screening ledger and paired finite-menu summaries from locked replays."""
from collections import Counter
from itertools import product
import csv
import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path
from issre_independent_collect import OUT,HERE
from issre_independent_replay import passed

EXCLUDED={390:'README sorting example',1105:'test/documentation typos',3776:'comments only',
          382:'README filter example',3772:'recursion in diagnostics; outside finite display domain',
          379:'type annotation only',3731:'type annotation only',1045:'documentation website',
          3720:'translated README',221:'CI configuration',1038:'docstring whitespace',
          1036:'docstring and private comment',3698:'documentation website'}


def main():
    frame=json.loads((OUT/'frame.json').read_text(encoding='utf8'))
    replay=json.loads((OUT/'replay.json').read_text(encoding='utf8'))
    assert frame['protocol_sha256']==hashlib.sha256((HERE/'ISSRE_INDEPENDENT_PROTOCOL_20261124.md').read_bytes()).hexdigest()
    assert replay['probes_sha256']==hashlib.sha256((HERE/'issre_independent_cases.py').read_bytes()).hexdigest()
    tested={r['pr']:r for r in replay['outcomes']}
    ledger=[]
    for i in range(10):
        for p in frame['projects']:
            r=p['records'][i]
            n=r['number']
            if n in tested:
                status='paired' if tested[n]['confirmed'] else 'not_reproduced'
                reason='related size formatting repairs; representative #250' if n==240 else ''
            elif n in EXCLUDED:
                status,reason='excluded',EXCLUDED[n]
            else:
                status,reason='not_attempted','stopping boundary reached'
            ledger.append(dict(order=len(ledger)+1,project=p['repo'],pr=n,title=r['title'],
                               status=status,reason=reason,url=r['html_url']))
    with (OUT/'screening.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(ledger[0]))
        w.writeheader()
        w.writerows(ledger)
    groups=[r for r in tested.values() if r['confirmed'] and r['pr']!=240]
    assert len(groups)==replay['independent_count']
    report={}
    for p in frame['projects']:
        rr=[r for r in groups if r['repo']==p['repo']]
        stages=Counter(r['status'] for r in ledger if r['project']==p['repo'])
        report[p['repo']]=dict(frame_total=p['total'],screening=stages,groups=len(rr),
            smoke=sum(not passed(r['parent_rows'][1],'status') for r in rr),
            coarse=sum(not passed(r['parent_rows'][1],'coarse') for r in rr),
            fine=sum(not passed(r['parent_rows'][1],'fine') for r in rr))
    # B is the per-test cap on the recorded API path. Selection is one test from the menu.
    matrix=[]
    for access,budget,observer,policy in product(('ordinary','both'),range(1,6),
            ('status','coarse','fine'),('default_first','boundary_first','uniform','any')):
        total=0
        per_defect={}
        for r in groups:
            inputs=r['parent_rows'][:1 if access=='ordinary' else 2]
            result=[int(len(z['steps'])<=budget and not passed(z,observer)) for z in inputs]
            pick={'default_first':result[0],'boundary_first':result[-1],
                  'uniform':sum(result)/len(result),'any':max(result)}[policy]
            total+=pick
            per_defect[str(r['pr'])]=pick
        matrix.append(dict(access=access,budget=budget,observer=observer,selection=policy,
                           expected_detections=total,by_pr=per_defect))
    (OUT/'factorial.json').write_text(json.dumps(matrix,indent=1),encoding='utf8')
    result=dict(projects=report,python=platform.python_version(),numpy=version('numpy'),
                wcwidth='0.2.13',catalog_compiler='Babel 2.17.0',
                coarse_distinct_groups=[r['pr'] for r in groups if r['pr'] not in (1088,1082)],
                budget_semantic=[r['expected_detections'] for r in matrix if r['access']=='both'
                     and r['observer']=='fine' and r['selection']=='any'])
    (OUT/'summary.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result))


if __name__=='__main__':
    main()
