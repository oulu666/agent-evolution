"""Atomic update-boundary commit. Two rolling slots + content-addressed full base.
No automatic resume, STOP removal, or old-file cleanup. Physical intent ledger is outside rollback state.
"""
import os,tempfile,time
from common import *

def helpers():
 from fac_tinyagent import p7_fullstate_v2_20261115 as fs
 from fac_tinyagent import p13_phase0b_persist_state_20261119 as persist
 return fs,persist

def file_sha(p):
 import hashlib
 d=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024**2),b''):d.update(b)
 return d.hexdigest()

def atomic_torch(p,x):
 import torch
 def size(v):
  if isinstance(v,torch.Tensor):return v.numel()*v.element_size()
  if isinstance(v,dict):return sum(size(z) for z in v.values())
  if isinstance(v,(tuple,list)):return sum(size(z) for z in v)
  return 0
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);old=meter_before(p,int(size(x)*1.02)+16*1024**2)
 fd,tmp=tempfile.mkstemp(prefix='state_',dir=p.parent);os.close(fd)
 try:
  with open(tmp,'wb') as f:torch.save(x,f);f.flush();os.fsync(f.fileno())
  os.replace(tmp,p);meter_after(p,old)
 except BaseException:
  if Path(tmp).exists():meter_after(tmp,0)
  raise
 d=os.open(str(p.parent),os.O_RDONLY);os.fsync(d);os.close(d)

def capture(model,opt,scaler,meta):
 fs,p=helpers();base=p.capture_base(model);attrs=p.runtime_attrs(model)
 return {'train':fs.capture(model,opt,scaler),'base':base,'attrs':attrs,'meta':fs.clone(meta)}

def semantic(s):
 fs,_=helpers();return fs.digest(s)

def restore(s,model,opt,scaler):
 fs,p=helpers();p.restore_base(model,s['base']);p.restore_attrs(model,s['attrs']);fs.restore(s['train'],model,opt,scaler)
 assert semantic(capture(model,opt,scaler,s['meta']))==semantic(s),'full state restoration mismatch'
 return fs.clone(s['meta'])

class Store:
 def __init__(self,path):self.path=Path(path);self.path.mkdir(parents=True,exist_ok=True)
 def commit(self,model,opt,scaler,meta):
  s=capture(model,opt,scaler,meta);fs,_=helpers();baseid=fs.digest(s['base']);blob=RUN/'base_blobs'/f'{baseid}.pt'
  # Correctness-first full base capture/hash; dedup only after content hash, never assume immutable quant state.
  disk_check(2*1024**3)
  if not blob.exists():atomic_torch(blob,s['base'])
  sd=semantic(s);small={k:v for k,v in s.items() if k!='base'};small['base_ref']=str(blob.relative_to(ROOT));small['base_semantic_sha256']=baseid
  generation=read(self.path/'CURRENT.json')['generation']+1 if (self.path/'CURRENT.json').exists() else 0
  slot=self.path/f'slot{generation%2}.pt';atomic_torch(slot,small)
  receipt={'generation':generation,'slot':slot.name,'state_file_sha256':file_sha(slot),'base_ref':str(blob.relative_to(ROOT)),
   'base_file_sha256':file_sha(blob),'full_semantic_sha256':sd,'generation_model_sha256':fs.digest({'parameters':s['train']['parameters'],'base':s['base'],'attrs':s['attrs']}),'meta':meta,'time_Beijing':time.strftime('%F %T %z')}
  # CURRENT is the commit point. Before it changes, previous CURRENT's other slot remains valid.
  atomic_json(self.path/'CURRENT.json',receipt);append(self.path/'commits.jsonl',receipt)
  return receipt
 def load(self,receipt=None):
  import torch
  r=receipt or read(self.path/'CURRENT.json');p=self.path/r['slot'];assert file_sha(p)==r['state_file_sha256']
  b=ROOT/r['base_ref'];assert file_sha(b)==r['base_file_sha256']
  s=torch.load(p,map_location='cpu',weights_only=False);base=torch.load(b,map_location='cpu',weights_only=False)
  fs,_=helpers();assert fs.digest(base)==s.pop('base_semantic_sha256');s.pop('base_ref');s['base']=base
  assert semantic(s)==r['full_semantic_sha256'];return s
 def restore(self,model,opt,scaler,receipt=None):return restore(self.load(receipt),model,opt,scaler)

class PhysicalBudget:
 def __init__(self,path,limit):self.path=Path(path);self.limit=limit
 def before_step(self):
  count=len(self.path.read_text().splitlines()) if self.path.exists() else 0
  assert count<self.limit,'physical optimizer-step limit exhausted; never auto-retry'
  append(self.path,{'physical_step_intent':count+1,'time_Beijing':time.strftime('%F %T %z')})
