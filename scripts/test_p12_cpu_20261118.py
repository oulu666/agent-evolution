"""P12 independent CPU trainer-interface and plan invariants; no model evaluation."""
import os,sys,collections,copy,json,time
from pathlib import Path
os.environ.update(CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fac_tinyagent import p12_eaar_v2_20261118 as D,p11_eaar_v1_20261118 as V1
from fac_tinyagent.p12_queue_20261118 import load_extra_features
from fac_tinyagent.utils import read_json,read_jsonl,write_json,sha256_file
from fac_tinyagent.sft.train import load_tokenizer
from fac_tinyagent.replay_study import config_for
from fac_tinyagent.replay_train import _prepare_rows
from fac_tinyagent.p6_attempt2 import required_plan_keys
cfg=config_for('A',D.SEEDS[0],batch_size=1);tok=load_tokenizer(cfg)
index={}
for f in ['database','file','python']:
 rows=read_jsonl(ROOT/f'data_ext_e4/pool/{f}.jsonl');prepared,_=_prepare_rows(rows,tok,1024,f,complete_only=True)
 for x in prepared:index[f,x['row_index'],x['episode_id']]=x
for f,rows in load_extra_features().items():
 for x in rows:index[f,x['row_index'],x['episode_id']]=x
summary={}
for s in D.SEEDS:
 qs=[read_json(D.planpath(s,a)) for a in D.ARMS]
 for a,q in zip(D.ARMS,qs):
  assert not set(required_plan_keys())-set(q)
  assert q['actual_input_tokens']==sum(x['input_tokens'] for x in q['items'])==7494
  assert len(q['items'])==22 and sum(x['target'] for x in q['items'])==10
  cnt=collections.Counter(x['skill'] for x in q['items'] if x['target']);assert [cnt[k] for k in D.SKILLS]==[1,1,3,1,2,2]
  for x in q['items']:
   y=index[x['family'],x['row_index'],x['episode_id']]
   assert x['input_tokens']==y['input_tokens']==len(y['features']['input_ids'])
   assert x['supervised_tokens']==y['supervised_tokens']==sum(v!=-100 for v in y['features']['labels'])
  summary[f'{s}_{a}']={'input':7494,'supervised':sum(x['supervised_tokens'] for x in q['items']),'plan_sha256':sha256_file(D.planpath(s,a)),'old_ids':[x['episode_id'] for x in q['items'] if x.get('skill') in D.OLD_SKILLS]}
 assert sum(x['supervised_tokens'] for x in qs[0]['items'])==sum(x['supervised_tokens'] for x in qs[1]['items'])
 for xa,xb in zip(qs[0]['items'],qs[1]['items']):
  if xa.get('skill') not in D.OLD_SKILLS:assert xa==xb
assert len(read_jsonl(D.DATA/'holdout/rows.jsonl'))==72
# Save outside the frozen data root; the prelaunch manifest update includes this receipt.
out=ROOT/'analysis_ext_p12_cpu_20261118';out.mkdir(exist_ok=True)
write_json(out/'trainer_contract_acceptance.json',{'passed':True,'time':time.strftime('%F %T %z'),'no_model_loaded':True,'plans':summary})
print(json.dumps(summary,indent=2));print('CPU REAL PREPARED-ROW CONTRACT PASS')
