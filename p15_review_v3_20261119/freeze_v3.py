"""Freeze v3 only, after CPU acceptance, before any GPU engineering."""
from common import *
if __name__=='__main__':
 a=read(RUN/'cpu_acceptance.json');assert a['pass']
 files=list(CODE.glob('*.py'))+[RUN/'review_budget_v3.json',RUN/'engineering_plan.json',RUN/'cpu_acceptance.json',OLD_RUN/'runtime_manifest_v2.json',ROOT/'P15_REVIEW_REVISION_V3_20261119_ZH.md']
 for p,d in a['source_hashes'].items():assert h((ROOT/p).read_bytes())==d
 m={'version':'P15 review v3, untrained amendment','files':{str(p.relative_to(ROOT)):h(p.read_bytes()) for p in sorted(files)},
  'formal_start_approved':False,'engineering_scope':'one attempt <=3 physical optimizer updates and <=6 train/dev generations; never test',
  'old598_unchanged':True,'prior_runtime_manifest_v2_sha256':h((OLD_RUN/'runtime_manifest_v2.json').read_bytes())}
 write(RUN/'runtime_manifest_v3.json',m,True);print(h((RUN/'runtime_manifest_v3.json').read_bytes()))
