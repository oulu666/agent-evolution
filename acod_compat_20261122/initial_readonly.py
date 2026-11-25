import json
from pathlib import Path
r=Path(__file__).resolve().parents[1]
def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x]
tasks=json.loads((r/'acod_round1_20261121/tasks.json').read_text())
print('Historical IDs:',[t['id'] for t in tasks if t['family']=='historical_dev'])
for ident in ['historical_0_first','historical_1_last']:
 t=next(t for t in tasks if t['id']==ident)
 print('Chosen candidate',ident,'rows',len(t['rows']),'roles',[m['role'] for m in t['views']['original']['messages']])
 old=[x for x in rows(r/'acod_round1_20261121/results/responses.jsonl') if x['task']==ident and x['view']=='original']
 print('Prior exposed raw:',[{'seed':x['seed'],'raw':x['raw']} for x in old])
print('Known old STOP:',(r/'acod_v2_eval_20261122/results/logs/STOP').read_text())