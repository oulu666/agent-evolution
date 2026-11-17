from pathlib import Path
import sys,json,random
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R));p=R/'fac_tinyagent/p8_decision_data_20261115.py';s=p.read_text()
s=s.replace("'database_entities_file_entities_numeric_values_split_disjoint':True", "'database_file_entities_disjoint_numeric_input_sets_disjoint':True")
old=" assert not DATA.exists() and not RUN.exists(),'no overwrite'\n for d in [DATA/'fixtures',DATA/'pools',DATA/'plans',RUN/'logs']:ensure_dir(d)\n splits={s:make_split(s) for s in ['train','dev','holdout']}\n for split,rows in splits.items():write_jsonl(DATA/(split+'.jsonl'),rows)"
new=" if DATA.exists():\n  assert not (DATA/'manifest.json').exists(),'frozen data must not change'\n  splits={split:read_jsonl(DATA/(split+'.jsonl')) for split in ['train','dev','holdout']}\n else:\n  assert not RUN.exists(),'no overwrite'\n  for d in [DATA/'fixtures',DATA/'pools',DATA/'plans',RUN/'logs']:ensure_dir(d)\n  splits={split:make_split(split) for split in ['train','dev','holdout']}\n  for split,rows in splits.items():write_jsonl(DATA/(split+'.jsonl'),rows)"
assert old in s;s=s.replace(old,new)
s=s.replace("  q['p8']={'counts'", "  q['target_actual_input_tokens']=sum(x['input_tokens'] for x in q['items'] if x['target'])\n  q['target_samples_by_family']={f:sum(x['target'] and x['family']==f for x in q['items']) for f in ['database','file','python']}\n  q['p8']={'counts'")
s=s.replace("assert c.execute(sql).fetchall()!=c.execute(wrong).fetchall();failures['SQL_where_or_tie_required']+=1", "assert c.execute(sql).fetchall()!=c.execute(wrong).fetchall();failures['SQL_where_or_tie_required']+=1\n     if r['case'] in ['zero','few']:\n      no_where=sql.split(' WHERE')[0]+' ORDER'+sql.split(' ORDER')[1];assert c.execute(sql).fetchall()!=c.execute(no_where).fetchall();failures['SQL_where_individually_required']+=1\n     if r['case'] in ['few','ties']:\n      assert c.execute(sql).fetchall()!=c.execute(sql.replace(', id ASC','')).fetchall();failures['SQL_tie_individually_required']+=1")
p.write_text(s)
from fac_tinyagent import p8_decision_data_20261115 as D
from fac_tinyagent.utils import read_jsonl,write_jsonl
assert not (D.DATA/'manifest.json').exists()
oldrows=read_jsonl(R/'data_ext_e4/pool/python.jsonl')+read_jsonl(R/'data_ext_p6_devplan/dev/rows.jsonl')+read_jsonl(R/'data_ext_p6_devplan/holdout/rows.jsonl')+read_jsonl(R/'data_ext_p7_response/check.jsonl')
used={tuple(sorted(r['expected_arguments']['values'])) for r in oldrows if 'values' in r['expected_arguments']}
for split in ['train','dev','holdout']:
 rows=read_jsonl(D.DATA/(split+'.jsonl'));rng=random.Random({'train':821,'dev':822,'holdout':823}[split]);byi={};out=[]
 for r in rows:
  if r['skill']=='py.median':
   while True:
    vals=[rng.randint(11,40) for _ in range(7)];key=tuple(sorted(vals))
    if key not in used:used.add(key);break
   i=int(r['episode_id'].rsplit('-',1)[1]);byi[i]=vals;text=', '.join(map(str,vals))
   prompt=(f'Order {text}. Give the central value, not the sorted list.' if split=='train' else f'For the measurements {text}, give the median as one number.' if split=='dev' else f'The observations are {text}. Once ordered, which value sits in the middle? Return that scalar.')
   r=D.row(split,'py.median',i,prompt,'stats_median',{'values':vals},{},{'kind':'identity'},case='median')
  elif r['skill']=='py.mean':
   i=int(r['episode_id'].rsplit('-',1)[1]);vals=byi[i];text=', '.join(map(str,vals));r=D.row(split,'py.mean',i,f'Compute the arithmetic average of {text}; return one number.','stats_mean',{'values':vals},{},{'kind':'identity'},case='mean')
  out.append(r)
 write_jsonl(D.DATA/(split+'.jsonl'),out)
D.build();print('P8 UNFROZEN CPU REFINEMENT PASS: median 7 values 11..40 matched to A; no model results inspected')
