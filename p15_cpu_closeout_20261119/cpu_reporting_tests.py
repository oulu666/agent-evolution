"""No model loader, GPU attempt, inference, or frozen-file rewrite. CPU serialization regression only."""
import os
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['PYTHONDONTWRITEBYTECODE']='1'
import json,sys,pathlib,types
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'runs_ext_p15_cpu_closeout_20261119'
from json_safe import json_safe,dumps

def main():
 import torch,numpy as np
 from unittest.mock import patch
 from fac_tinyagent import p13_phase0b_persist_state_20261119 as old
 assert not torch.cuda.is_initialized();tests={}
 raw={'actual_config':{'torch_dtype':torch.float16,'dtype':torch.bfloat16},'device':torch.device('cuda:0'),'layout':torch.strided,
      'memory_format':torch.contiguous_format,'path':pathlib.PurePosixPath('/exact/path'),'numpy_dtype':np.dtype('float32'),
      'n':np.int64(7),'f':np.float32(.5),'b':np.bool_(True),'tuple':(1,'二',None)}
 try:json.dumps(raw);raise AssertionError('original defect must reproduce')
 except TypeError:tests['original_dtype_JSON_failure_reproduced']=True
 got=json.loads(dumps(raw));assert got['actual_config']=={'torch_dtype':'torch.float16','dtype':'torch.bfloat16'}
 assert got['device']=='cuda:0' and got['layout']=='torch.strided' and got['memory_format']=='torch.contiguous_format'
 assert got['path']=='/exact/path' and got['numpy_dtype']=='float32' and got['n']==7 and got['f']==.5 and got['b'] is True
 assert got['tuple']==[1,'二',None];tests['nested_known_types_exact_strings_and_numbers']=True
 assert dumps(raw)==dumps(raw);tests['deterministic_serialization']=True
 # Real legacy fingerprint structure; ONLY device-name/capability mocked. No CUDA initialization or model exists.
 class CPUFixture:
  config=types.SimpleNamespace(torch_dtype=torch.float16,dtype=torch.float16,use_cache=False)
  def get_base_model(self):return self
 with patch.object(torch.cuda,'get_device_name',return_value='CPU_MOCK_NO_GPU'),patch.object(torch.cuda,'get_device_capability',return_value=(0,0)):
  fp=old.backend_fingerprint(CPUFixture(),torch.float16)
 try:json.dumps(fp);raise AssertionError('real fingerprint dtype defect expected')
 except TypeError:pass
 fixed=json.loads(dumps(fp));assert fixed['actual_config']['dtype']=='torch.float16'
 assert fixed['GPU_name']=='CPU_MOCK_NO_GPU';tests['legacy_backend_fingerprint_structure_CPU_mock_fixed']=True
 for name,bad in [('unknown',object()),('tensor',torch.tensor([1.])),('array',np.array([1.,2.])),('nonfinite',float('nan')),('key_collision',{1:'a','1':'b'})]:
  try:dumps(bad);raise AssertionError('unsafe value accepted '+name)
  except (TypeError,ValueError):tests['fail_closed_'+name]=True
 oldrun=ROOT/'runs_ext_p15_review_v3_20261119';attempt=oldrun/'engineering_attempt01'
 assert not (attempt/'RESULT.json').exists() and not (oldrun/'START_APPROVED_V3.json').exists()
 facts=json.loads((attempt/'FORENSIC_RESULT.json').read_text())
 status={'overall_status':'NOT_FULLY_ACCEPTED/BLOCKED','CPU_serialization_fix':'PASS_ONLY',
  'original_RESULT_json_exists':False,'GPU_postgeneration_isolation_witness':False,'scientific_trajectories':0,
  'new_GPU_attempts_this_closeout':0,'formal_START_created':False,'method_effectiveness':'NO_CONCLUSION',
  'prior_physical_updates':facts['verified']['physical_optimizer_updates'],'prior_logical_updates':facts['verified']['logical_optimizer_updates'],
  'prior_generation_requests':facts['verified']['generation_physical_requests']}
 assert status['prior_physical_updates']==3 and status['prior_logical_updates']==2 and status['prior_generation_requests']==6
 tests['acceptance_stays_blocked_and_no_RESULT_START_created']=True
 assert not torch.cuda.is_initialized();tests['no_CUDA_initialization_no_model']=True
 OUT.mkdir(exist_ok=True)
 (OUT/'reporting_CPU_tests.json').write_text(dumps({'pass':all(tests.values()),'scope':'CPU reporting only; not GPU acceptance','tests':tests})+'\n')
 (OUT/'FINAL_BLOCKED_STATUS.json').write_text(dumps(status)+'\n')
 (OUT/'CPU_MOCK_fingerprint_serialized.json').write_text(dumps({'CPU_MOCK_NOT_GPU_MEASUREMENT':True,'fingerprint':fp})+'\n')
 print(dumps({'tests':tests,'pass':all(tests.values()),'final_status':status}))

if __name__=='__main__':main()
