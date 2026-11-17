"""P7 repair: exact persisted trainable/optimizer/scaler/RNG/mode state, never numerical replay."""
import copy,hashlib,random
from pathlib import Path
import numpy as np
import torch

def clone(x):
 if torch.is_tensor(x):return x.detach().cpu().clone()
 if isinstance(x,dict):return {k:clone(v) for k,v in x.items()}
 if isinstance(x,list):return [clone(v) for v in x]
 if isinstance(x,tuple):return tuple(clone(v) for v in x)
 return copy.deepcopy(x)
def digest(x):
 h=hashlib.sha256()
 def put(y):
  h.update(type(y).__name__.encode()+b':')
  if torch.is_tensor(y):h.update(str(y.dtype).encode()+str(tuple(y.shape)).encode()+y.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy().tobytes())
  elif isinstance(y,np.ndarray):h.update(str(y.dtype).encode()+str(y.shape).encode()+y.tobytes())
  elif isinstance(y,dict):
   for k in sorted(y,key=lambda k:(str(type(k)),str(k))):put(k);put(y[k])
  elif isinstance(y,(list,tuple)):
   for v in y:put(v)
  else:h.update(repr(y).encode())
 put(x);return h.hexdigest()
def capture(model,opt,scaler):
 assert all(p.grad is None for p in model.parameters() if p.requires_grad),'snapshot requires cleared accumulation'
 return {'parameters':{n:clone(p) for n,p in model.named_parameters() if p.requires_grad},'optimizer':clone(opt.state_dict()),'scaler':clone(scaler.state_dict()),'python_rng':random.getstate(),'numpy_rng':np.random.get_state(),'torch_rng':torch.get_rng_state().clone(),'cuda_rng':[s.cpu().clone() for s in torch.cuda.get_rng_state_all()] if torch.cuda.is_available() else [],'module_modes':{n:m.training for n,m in model.named_modules()},'optimizer_attrs':{n:getattr(opt,n) for n in ['initialized'] if hasattr(opt,n)}}
def restore(s,model,opt,scaler):
 params=dict(model.named_parameters());assert set(s['parameters'])=={n for n,p in params.items() if p.requires_grad}
 with torch.no_grad():
  for n,v in s['parameters'].items():params[n].copy_(v.to(params[n].device,dtype=params[n].dtype))
 opt.load_state_dict(copy.deepcopy(s['optimizer']))
 # Reinstate stored tensor dtypes explicitly; 8-bit integer moments may not be cast to parameter dtype.
 for live,saved in zip(opt.param_groups,s['optimizer']['param_groups']):
  for p,i in zip(live['params'],saved['params']):
   def move(x):
    if torch.is_tensor(x):return x.clone().to(p.device)
    if isinstance(x,dict):return {k:move(v) for k,v in x.items()}
    if isinstance(x,list):return [move(v) for v in x]
    if isinstance(x,tuple):return tuple(move(v) for v in x)
    return copy.deepcopy(x)
   if i in s['optimizer']['state']:opt.state[p]=move(s['optimizer']['state'][i])
 for n,v in s['optimizer_attrs'].items():setattr(opt,n,v)
 scaler.load_state_dict(copy.deepcopy(s['scaler']));opt.zero_grad(set_to_none=True)
 for n,m in model.named_modules():m.training=s['module_modes'][n]
 random.setstate(s['python_rng']);np.random.set_state(s['numpy_rng']);torch.set_rng_state(s['torch_rng'])
 if s['cuda_rng']:torch.cuda.set_rng_state_all(s['cuda_rng'])
 assert digest(capture(model,opt,scaler))==digest(s),'exact full-state roundtrip failed'
def save(s,path):
 path=Path(path);assert not path.exists(),'never overwrite persisted state'
 torch.save(s,path)
 return {'semantic_sha256':digest(s),'file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size}
def load(path,receipt):
 path=Path(path);assert hashlib.sha256(path.read_bytes()).hexdigest()==receipt['file_sha256']
 s=torch.load(path,map_location='cpu',weights_only=False);assert digest(s)==receipt['semantic_sha256'];return s
