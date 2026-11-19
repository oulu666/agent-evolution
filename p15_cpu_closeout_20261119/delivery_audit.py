"""CPU-only exact candidate inventory/security/hash audit; NEVER stages, commits or starts GPU."""
import os,sys,json,pathlib,re,hashlib
os.environ.update(CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1')
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'runs_ext_p15_cpu_closeout_20261119'
sys.path.insert(0,str(ROOT/'p15_review_v3_20261119'))
from common import verify,read,h,cj

def main():
 freeze=verify();old=ROOT/'runs_ext_p15_review_v3_20261119';assert not (old/'START_APPROVED_V3.json').exists()
 assert not (old/'engineering_attempt01/RESULT.json').exists()
 status=read(OUT/'FINAL_BLOCKED_STATUS.json');assert status['overall_status']=='NOT_FULLY_ACCEPTED/BLOCKED'
 assert read(OUT/'reporting_CPU_tests.json')['pass'] and read(OUT/'token_cache_rebuild_check.json')['cache_sha256']=='0982d02d2ee51de2eaa89068efa9a9ea00fe997f05a0436b1b99f400821ae6b0'
 files=[ROOT/'.gitattributes'];files+=list((ROOT/'data_ext_p14_eval_protocol_v2').rglob('*.json'))+list((ROOT/'data_ext_p14_eval_protocol_v2').rglob('*.jsonl'))+list((ROOT/'data_ext_p14_eval_protocol_v2').rglob('*.sha256'))
 for code in ('p15_stageaware_20261119','p15_review_v3_20261119','p15_cpu_closeout_20261119'):files+=list((ROOT/code).glob('*.py'))
 for pat in ('P14_V2_REVISION_20261119_ZH.md','P15_*20261119*.md','EXT_HANDOVER_20261119_p15*.md','EXT_REPORT_20261119_p15*.md','EXT_REPORT_20261119_p14v2*.md','EXT_*20261119_P14v2_P15_FINAL_BLOCKED_ZH.md'):files+=list(ROOT.glob(pat))
 first=ROOT/'runs_ext_p15_stageaware_20261119'
 files+=[p for p in first.iterdir() if p.is_file() and p.suffix in ('.json','.log','.sha256')]
 files+=[p for p in old.iterdir() if p.is_file() and p.suffix=='.json']
 files+=[old/'postprocess_measurements_cpu.py']
 eng=old/'engineering_attempt01'
 files+=[p for p in eng.iterdir() if p.is_file() and p.suffix in ('.json','.jsonl','.txt')]
 files += [eng/'state/commits.jsonl',eng/'state/CURRENT.json']
 reserved=[OUT/'candidate_inventory.json',OUT/'upload_preflight.json']
 files+=[p for p in OUT.iterdir() if p.is_file() and p.suffix=='.json' and p not in reserved]
 files=sorted(set(files));assert all(p.exists() for p in files)
 denied=[];findings=[];records={}
 patterns={
  'private_key':rb'-----BEGIN [A-Z ]*PRIVATE KEY-----',
  'github_token':rb'gh[pousr]_[A-Za-z0-9]{25,}',
  'github_fine_grained':rb'github_pat_[A-Za-z0-9_]{40,}',
  'huggingface_token':rb'hf_[A-Za-z0-9]{30,}',
  'AWS_access_key':rb'AKIA[0-9A-Z]{16}',
  'bearer_secret':rb'(?i)authorization[\x22\x27\s:=]+Bearer\s+[A-Za-z0-9._-]{25,}',
  'model_API_secret':rb'\bsk-[A-Za-z0-9_-]{25,}'}
 for p in files:
  rel=p.relative_to(ROOT).as_posix();parts=p.relative_to(ROOT).parts
  if any(x in parts for x in ('.git','.venv','__pycache__','cache','base_blobs','cpu_fixtures','_p11_fix_tmp','draft_failure_01','draft_failure_02')) or p.suffix in ('.pt','.bin','.safetensors','.zip','.gz','.pid','.lock') or p.name in ('tokenizer.json','tokenizer_config.json','vocab.json','merges.txt','START_APPROVED.json','START_APPROVED_V3.json','STOP'):denied.append(rel)
  b=p.read_bytes();assert len(b)<8*1024**2,('candidate exceeds8MiB',rel)
  for name,pat in patterns.items():
   if re.search(pat,b):findings.append({'path':rel,'rule':name})
  assert b'\0' not in b,('nontext payload candidate',rel)
  records[rel]={'sha256':h(b),'bytes':len(b)}
 assert not denied and not findings,{'denied':denied,'secret_findings':findings}
 # Keep old manifests untouched even where intentionally omitted local-only artifacts are referenced.
 omission={'token_features.json.gz':{'reason':'derived token cache excluded; reconstruct deterministically with rebuild_token_features_cpu.py --write',
  'sha256':read(OUT/'token_cache_rebuild_check.json')['cache_sha256'],'bytes':250448},
  'cache_dirs':'all excluded, including6 engineering cached responses; raw generation_records and recorded hashes retained',
  'large_local_only':'857797695-byte base blob and two61244021-byte optimizer/scaler/RNG states retained locally; original forensic SHA evidence included, payloads not published',
  'other':'source/transfer zip duplicates, CPU toy fixtures, running lock/PID and old draft_failure/_p11_fix_tmp excluded, not deleted'}
 inventory={'files':records,'metadata_files_excluded_from_own_hash_index':[str(p.relative_to(ROOT)) for p in reserved],
  'base_files_count':len(files),'base_bytes':sum(r['bytes'] for r in records.values()),'omissions':omission,
  'target_repo':'https://github.com/oulu666/agent-evolution','branch':'main','prior_HEAD':'fbecfebe01405542468e9fcdd47b59983aa6d01a'}
 (OUT/'candidate_inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
 pre={'pass':True,'scope':'exact publication candidates; security pattern scan not guarantee against every secret','secret_pattern_rules':list(patterns),'secret_findings':findings,'denied_paths':denied,
  'old598_unchanged':True,'v3_runtime_manifest_sha256':freeze,'v3_original_RESULT_absent':True,'START_absent':True,
  'new_GPU_attempts':0,'formal_trajectories':0,'final_status':'NOT_FULLY_ACCEPTED/BLOCKED','metadata_self_hash_exclusion':True}
 (OUT/'upload_preflight.json').write_text(cj(pre)+'\n')
 allfiles=files+reserved
 (OUT/'candidate_paths.nul').write_bytes(b''.join(str(p.relative_to(ROOT)).replace('\\','/').encode()+b'\0' for p in allfiles))
 print(cj({'audit':'PASS','candidate_files':len(allfiles),'candidate_bytes':sum(p.stat().st_size for p in allfiles),
  'inventory_sha256':h((OUT/'candidate_inventory.json').read_bytes()),'secret_findings':findings,'v3_frozen_sha256':freeze,'final_status':'NOT_FULLY_ACCEPTED/BLOCKED'}))

if __name__=='__main__':main()
