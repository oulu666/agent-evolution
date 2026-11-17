import json,collections
from pathlib import Path
R=Path('.')
def j(p): return json.loads(Path(p).read_text())
def jl(p): return [json.loads(x) for x in Path(p).read_text().splitlines() if x]
pool=jl('data_ext_e4/pool/file.jsonl')
for i,r in enumerate(pool):
 if 'e4_target' in r['episode_id']:
  print('TARGET',i,json.dumps(r,ensure_ascii=False))
for s in [20261108,20261109,20261110]:
 p=j(f'data_ext_e3/plans/A_seed{s}_dose_db4.json')
 print('PLAN',s,json.dumps({k:v for k,v in p.items() if k!='items'}))
 print('ITEMS',json.dumps(p['items']))
 for a in ['stage_02_database','stage_03_python','none']:
  f=R/f'runs_ext_p1_b1/evaluation/A_seed{s}_{a}/natv2_file/results.jsonl'
  rs=jl(f)
  print('B1',s,a,len(rs),sum(bool(x['joint_success']) for x in rs))
print('CONFIG',j('runs_ext_e4/prefixes/A_seed20261108/manifest.json'))
