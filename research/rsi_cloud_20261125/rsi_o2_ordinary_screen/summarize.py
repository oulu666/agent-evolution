import hashlib,json,sys
from collections import defaultdict
from pathlib import Path
p=Path(sys.argv[1]); rows=[]
for name in ('pandas-2.2.3','pandas-3.1.0','pandas-3.1.1','scipy-1.17.0'):
 for ln in (p/(name+'.jsonl')).read_text().splitlines():
  d=json.loads(ln); expected=d.pop('row_sha256')
  assert hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest()==expected
  if d['event']=='end':rows.append(d)
  else: assert d['event']=='start'
result=defaultdict(dict)
for d in rows:
 k=f"{d['issue']}/{d['version']}"
 rr=result[k].setdefault(d['route'],dict(passed=0,n=0,actions=0))
 rr['n']+=1;rr['passed']+=d['passed'];rr['actions']+=d['actions']
print(json.dumps(dict(examined_issues=3,executed_issues=2,admitted=0,actions=sum(x['actions'] for x in rows),results=result),indent=2,sort_keys=True))
