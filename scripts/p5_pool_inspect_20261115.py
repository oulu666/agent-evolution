import json
from pathlib import Path
for i,l in enumerate(Path('data_ext_e4/pool/file.jsonl').read_text().splitlines()):
 r=json.loads(l)
 if 'e4_last_match' in r['episode_id']: print(i,json.dumps(r,ensure_ascii=False))
