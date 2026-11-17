"""Synthetic planning tests only: no model/GPU and no holdout outputs."""
import ast,json,sys,time
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from fac_tinyagent import p6_devplan as P
P.verify();stats=[]
for seed in P.SEEDS:
 base=P.make_plan(seed,'balanced_uniform',{s:1. for s in P.SKILLS})
 zero=P.make_plan(seed,'devgrad_uniform',{s:0. for s in P.SKILLS})
 assert base['p6']['counts']==zero['p6']['counts'],'all-zero fallback differs from uniform'
 for focus in P.SKILLS:
  plan=P.make_plan(seed,'devgrad_uniform',{s:float(s==focus) for s in P.SKILLS})
  assert plan['p6']['counts'][focus]==7
  assert sum(plan['p6']['counts'].values())==10
  assert abs(plan['actual_input_tokens']-7494)<=74.94
  stats.append({'seed':seed,'synthetic_high_signal':focus,'counts':plan['p6']['counts'],'tokens':plan['actual_input_tokens']})
# Independent gold semantic checks, without loading model/formal predictions.
rows=P.read_jsonl(P.DATA/'dev/rows.jsonl')+P.read_jsonl(P.DATA/'holdout/rows.jsonl')
for r in rows:
 obs=json.loads(r['expected_observation'])['result']
 if r['skill']=='file.search_last':assert r['expected_final_answer']==obs[-1]['text']
 if r['skill']=='py.median':assert r['expected_final_answer']==sorted(r['expected_arguments']['values'])[3]
 if r['skill']=='db.filter_cmp_top':assert r['expected_final_answer']==[v[0] for v in obs['rows']]
for p in [R/'fac_tinyagent/p6_devplan.py',*sorted((R/'scripts').glob('*p6*20261115.py'))]:ast.parse(p.read_text())
out={'status':'PASS','created':time.strftime('%F %T %z'),'zero_fallback_and_12_extreme_allocations':True,'semantic_gold_checked':len(rows),'synthetic_not_model_data':stats,'gpu_started':False}
P.write_json(P.RUNS/'cpu_acceptance.json',out)
print('CPU ACCEPTANCE PASS: 12 extreme allocations + 3 zero fallbacks + 64 semantic gold; no GPU')
