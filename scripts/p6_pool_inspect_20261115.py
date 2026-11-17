import json,collections,hashlib
from pathlib import Path
for f in ['file','database','python']:
 rows=[json.loads(x) for x in Path('data_ext_e4/pool/'+f+'.jsonl').read_text().splitlines() if x]
 patterns={'lt':'db_list_tables','filter':'target_db_filter_top','last':'e4_last_match','median':'target_median_natural'}
 for k,pat in patterns.items():
  rs=[r for r in rows if pat in r['episode_id']]
  if rs: print(k,len(rs),len({json.dumps(r['messages'],sort_keys=True) for r in rs}),[r['episode_id'] for r in rs[:3]])
