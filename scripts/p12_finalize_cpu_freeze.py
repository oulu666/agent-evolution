"""Pre-training P12 final freeze after independent tokenizer/interface CPU test."""
import sys,time,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fac_tinyagent import p12_eaar_v2_20261118 as D
from fac_tinyagent.utils import read_json,write_json,sha256_file
m=read_json(D.DATA/'manifest.json');prior=sha256_file(D.DATA/'manifest.json')
if 'final_cpu_freeze' in m:raise SystemExit('already finalized; no overwrite')
# Preserve initial CPU freeze receipt; only source interface validation was corrected.
m['initial_cpu_freeze_sha256']=prior
m['final_cpu_freeze']={'time':time.strftime('%F %T %z'),'reason':'prelaunch CPU interface acceptance: prepared base rows expose input/supervised tokens but not message_hash; compare supported fields. No data/plan/score changes.'}
for rel in list(m['references']):m['references'][rel]=sha256_file(ROOT/rel)
refs=['scripts/test_p12_cpu_20261118.py','scripts/launch_p12_20261118.sh','scripts/p12_finalize_cpu_freeze.py','analysis_ext_p12_cpu_20261118/trainer_contract_acceptance.json','fac_tinyagent/e3_train.py','fac_tinyagent/replay_train.py','fac_tinyagent/sft/evaluate.py','fac_tinyagent/tools/calendar_tools.py','fac_tinyagent/research_data.py']
for rel in refs:m['references'][rel]=sha256_file(ROOT/rel)
write_json(D.DATA/'manifest.json',m);D.verify()
info={'time':time.strftime('%F %T %z'),'manifest_sha256':sha256_file(D.DATA/'manifest.json'),'holdout_sha256':sha256_file(D.DATA/'holdout/rows.jsonl'),'prereg_sha256':sha256_file(D.PREREG),'decisions':{s:{k:v for k,v in d.items() if k not in ['priorities']} for s,d in m['decisions'].items()},'actual_training_branches':6-sum(d['same_training_plan'] for d in m['decisions'].values()),'physical_eval_states':12-sum(d['same_training_plan'] for d in m['decisions'].values())}
write_json(ROOT/'analysis_ext_p12_cpu_20261118/final_freeze_receipt.json',info);print(json.dumps(info,indent=2))
