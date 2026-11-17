import collections,json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def j(p):return json.loads(p.read_text())
pool=[json.loads(l) for l in (R/'data_ext_e4/pool/file.jsonl').read_text().splitlines() if l]
ids=['file-train-e4_last_match-%03d'%i for i in [0,6,7,14]]
for eid in ids:
 r=next(x for x in pool if x['episode_id']==eid)
 obs=r['expected_observation'];obs=json.loads(obs) if isinstance(obs,str) else obs
 answer=json.loads(r['messages'][-1]['content'])['answer']
 assert 'last line' in r['prompt'] and r['expected_tool']=='file_search'
 assert answer==obs['result'][-1]['text']
 print('SEARCH_LAST',eid,answer)
for s in [20261108,20261109,20261110]:
 ps=[j(R/f'data_ext_p5_file_timing/plans/A_seed{s}_{a}.json') for a in ['early','uniform','late']]
 counters=[collections.Counter(json.dumps(x,sort_keys=True) for x in p['items']) for p in ps]
 assert counters[0]==counters[1]==counters[2]
 assert all(collections.Counter(x['episode_id'] for x in p['items'] if x['episode_id'] in ids)==collections.Counter(ids) for p in ps)
 print('MULTISET_OK',s,ps[0]['actual_input_tokens'])
# Verify actual training microstep formula used by CPU dry-run and runtime assertion.
src=(R/'fac_tinyagent/p5_file_timing.py').read_text()
assert "23-((x['microstep']-1)//8+1)+1" in src
assert j(R/'runs_ext_p5_file_timing/dry_run.json')['status']=='PASS'
print('ACTUAL_OPTIMIZER_TIMING_ASSERTION_OK')
