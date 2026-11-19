"""CPU-only reporting adapter. Not imported by frozen GPU runtime; never changes acceptance.
Known dtype/device/layout/path types map to exact public strings. Unknown objects and
nonfinite floats fail closed: no lossy default=str or silent large tensor serialization.
"""
import enum,json,math
from pathlib import PurePath
from collections.abc import Mapping

def json_safe(value):
 import torch,numpy as np
 if value is None or isinstance(value,(str,bool,int)):return value
 if isinstance(value,float):
  if not math.isfinite(value):raise ValueError('nonfinite report float')
  return value
 if isinstance(value,(torch.dtype,torch.device,torch.layout,torch.memory_format,np.dtype,PurePath)):return str(value)
 if isinstance(value,np.generic):return json_safe(value.item())
 if isinstance(value,enum.Enum):return f'{type(value).__module__}.{type(value).__qualname__}.{value.name}'
 if isinstance(value,Mapping):
  if any(not isinstance(k,str) for k in value):raise TypeError('report keys must be strings; refuse coercion/collision')
  return {k:json_safe(v) for k,v in value.items()}
 if isinstance(value,(tuple,list)):return [json_safe(v) for v in value]
 raise TypeError('unsupported reporting value: '+type(value).__module__+'.'+type(value).__qualname__)

def dumps(value):return json.dumps(json_safe(value),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
