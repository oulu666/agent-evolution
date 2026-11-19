"""Add-only v3 paths and hash binding; CPU safe imports."""
import os,sys,shutil,tempfile,time,gzip
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'p15_stageaware_20261119'))
from core import *
OLD_RUN=RUN; OLD_CODE=CODE
RUN=ROOT/'runs_ext_p15_review_v3_20261119';CODE=ROOT/'p15_review_v3_20261119'
MIN_FREE=8*2**30; MAX_RUN_BYTES=32*2**30

_disk_used=None

def disk_check(extra=0,reconcile=False):
 global _disk_used
 if _disk_used is None or reconcile:
  _disk_used=sum(p.stat().st_size for p in RUN.rglob('*') if p.is_file())
 free=shutil.disk_usage(ROOT).free
 assert _disk_used+extra<=MAX_RUN_BYTES,('P15 v3 hard cap',_disk_used,extra)
 assert free-extra>=MIN_FREE,('free space reserve',free,extra)
 return {'run_bytes':_disk_used,'free_bytes':free,'hard_cap_bytes':MAX_RUN_BYTES,'minimum_free_bytes':MIN_FREE}

def meter_before(p,peak_new_bytes):
 disk_check(peak_new_bytes)
 return Path(p).stat().st_size if Path(p).exists() else 0

def meter_after(p,old):
 global _disk_used
 _disk_used+=Path(p).stat().st_size-old

def atomic_bytes(p,b):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);old=meter_before(p,len(b))
 fd,tmp=tempfile.mkstemp(prefix='atomic_',dir=p.parent)
 try:
  with os.fdopen(fd,'wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
  os.replace(tmp,p);meter_after(p,old)
 except BaseException:
  if Path(tmp).exists():meter_after(tmp,0)
  raise
 d=os.open(str(p.parent),os.O_RDONLY);os.fsync(d);os.close(d)

def atomic_json(p,x):atomic_bytes(p,(cj(x)+'\n').encode())

def write(p,x,freeze=False):
 b=(json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode();p=Path(p)
 if freeze and p.exists():assert p.read_bytes()==b,'Do not overwrite frozen '+str(p)
 else:atomic_bytes(p,b)

def append(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);b=(cj(x)+'\n').encode();old=meter_before(p,len(b))
 with p.open('ab') as f:f.write(b);f.flush();os.fsync(f.fileno())
 meter_after(p,old)

def features_load():return json.loads(gzip.decompress((OLD_RUN/'token_features.json.gz').read_bytes()))
def verify():
 import runner_v2
 runner_v2.verify()
 m=read(RUN/'runtime_manifest_v3.json')
 for p,d in m['files'].items():assert h((ROOT/p).read_bytes())==d,'v3 freeze mismatch '+p
 assert read(RUN/'cpu_acceptance.json')['pass'] is True
 return h((RUN/'runtime_manifest_v3.json').read_bytes())
