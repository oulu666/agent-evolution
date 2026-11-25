import sys,json,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fac_tinyagent.utils import read_json as J,read_jsonl as L,write_json
P=ROOT/'data_ext_p11_eaar_v1';R=ROOT/'runs_ext_p11_eaar_v1'
events=J(P/'fixtures/calendar.json')['events'];by=collections.defaultdict(list)
for e in events:by[e['date']].append(e)
cands=J(P/'candidates.json');tr=L(P/'train/rows.jsonl');out={}
for seed in [20261108,20261109,20261110]:
 q=J(P/f'plans/A_seed{seed}_eaar_v1.json');dev=L(R/f'probes/A_seed{seed}/dev/results.jsonl')
 out[str(seed)]={'counts':q['p11']['counts'],'timing':q['p11']['timing'],'dev':{s:sum(x['joint_success'] for x in dev if s in x['episode_id']) for s in ['cal.count_date','cal.list_locations']}}
out['location_candidates']=[{'id':x['episode_id'],'date':next(r for r in tr if r['episode_id']==x['episode_id'])['expected_arguments']['date']} for x in cands['cal.list_locations']]
for x in out['location_candidates']:
 es=by[x['date']];x.update(n=len(es),unique=len({e['location'] for e in es}))
out['train_location_distribution']=dict(collections.Counter(str((len(by[r['expected_arguments']['date']]),len({e['location'] for e in by[r['expected_arguments']['date']]}))) for r in tr if r['skill']=='cal.list_locations'))
lt=[r for r in L(P/'holdout/rows.jsonl') if r['skill']=='db.list_tables'];out['p11_lt']={'n':len(lt),'answers':list({json.dumps(r['expected_final_answer']) for r in lt})}
out['complete']=J(R/'COMPLETE.json');print(json.dumps(out,indent=2));write_json(ROOT/'_p11_fix_tmp/p12_source_audit.json',out)
