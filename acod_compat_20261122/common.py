import os,sys,json,hashlib,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'acod_v2_freeze_20261121'))
os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',TZ='Asia/Shanghai',WANDB_MODE='disabled')
time.tzset()
def now():return time.strftime('%Y-%m-%d %H:%M:%S %z')
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def rows(p):return [json.loads(s) for s in Path(p).read_text(encoding='utf-8').splitlines() if s] if Path(p).exists() else []
def save(p,x):
 with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)
def append(p,x):
 with Path(p).open('a',encoding='utf-8') as f:f.write(canonical(x)+'\n');f.flush();os.fsync(f.fileno())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def verify():
 m=read(HERE/'FREEZE_MANIFEST.json')
 for k,v in m['protected_sha256'].items():assert sha(ROOT/k)==v,'Old asset changed: '+k
 for k,v in m['new_source_sha256'].items():assert sha(HERE/k)==v,'Locked new source changed: '+k
 assert sha(HERE/'PLAN_PUBLIC.json')==m['plan_sha256']
 return m