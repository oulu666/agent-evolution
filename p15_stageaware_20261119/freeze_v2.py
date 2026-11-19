"""Operational-only versioned guard repair; original scientific/runtime freeze immutable."""
from core import *
from prepare import protect
ORIGINAL='7fdcf44f6e80cc4150c7203765a7416ba37bbb447d2d813ac4b589e9fb27bb6e'
protect();old=RUN/'runtime_manifest.json';assert h(old.read_bytes())==ORIGINAL
m=read(old)
for path,digest in m['files'].items():assert h((ROOT/path).read_bytes())==digest,'Original frozen file changed '+path
test=read(RUN/'cpu_tests_v2.json');assert test['status']=='PASS'
for name,digest in test['tested_source_hashes'].items():assert h((CODE/name).read_bytes())==digest
new=[CODE/n for n in ['guards_v2.py','runner_v2.py','cpu_tests_v2.py','freeze_v2.py']]+[ROOT/'P15_OPERATIONAL_AMEND_20261119_guard_identity_ZH.md',RUN/'cpu_tests_v2.json',old]
refs={**m['files'],**{str(p.relative_to(ROOT)):h(p.read_bytes()) for p in new}}
write(RUN/'runtime_manifest_v2.json',{'status':'FROZEN_NOT_STARTED','training_started':False,'scientific_parent_runtime_sha256':ORIGINAL,
  'scientific_changes':False,'operational_change':'Use actual /proc exe or argv[0] for Python identity; verify real direct batch supervisor. Ignore launcher Bash/PowerShell mentioning python.',
  'files':refs,'default_cohort_trajectories':108,'optional_full_replay_trajectories':18,'entrypoint':'p15_stageaware_20261119/runner_v2.py',
  'v1_manifest_sha256':h((V1/'manifest.json').read_bytes()),'v2_manifest_sha256':h((DATA/'manifest.json').read_bytes())},True)
install(RUN/'runtime_manifest_v2.sha256',(h((RUN/'runtime_manifest_v2.json').read_bytes())+'  runtime_manifest_v2.json\n').encode())
print(cj({'runtime_manifest_v2_sha256':h((RUN/'runtime_manifest_v2.json').read_bytes()),'original_runtime_unchanged':ORIGINAL,'scientific_changes':False,'GPU_started':False}))
