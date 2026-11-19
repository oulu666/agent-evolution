"""P14 publication audit: CPU/read-only checks, no model or credential access."""
from pathlib import Path
import hashlib,json,re,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data_ext_p14_eval_protocol';RUN=ROOT/'runs_ext_p14_eval_protocol'
MANIFEST='944b8e3d9b254e928559a55623aef3c41060234a8b04f010b9f1919f0f0b3881'
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha((DATA/'manifest.json').read_bytes())==MANIFEST
manifest=json.loads((DATA/'manifest.json').read_text())
for path,meta in manifest['files'].items():
    b=(ROOT/path).read_bytes();assert sha(b)==meta['sha256'] and len(b)==meta['bytes'],path
old=json.loads((RUN/'protected_sources_before.json').read_text())
assert old==json.loads((RUN/'protected_sources_after.json').read_text())
for path,digest in old.items():assert sha((ROOT/path).read_bytes())==digest,path
files=list(DATA.rglob('*'))
files=[p for p in files if p.is_file()]
files += [ROOT/n for n in ['P14_EVAL_PROTOCOL_20261119_ZH.md','EXT_HANDOVER_20261119_p14_eval_protocol_ZH.md','EXT_REPORT_20261119_p14_eval_protocol_ZH.md']]
files += [RUN/n for n in ['b1_metric_truth_table.json','cpu_acceptance.json','freeze_pass_01.log','freeze_pass_02.log','historical_audit.json','protected_sources_before.json','protected_sources_after.json','draft_failure_01/cpu_failure.txt','draft_failure_02/cpu_failure.txt','publish_cpu_audit.py']]
files=sorted(set(files));assert len(files)==27
rules={
'private_key':rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
'github_token':rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})',
'openai_key':rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}',
'aws_access_key':rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
'credential_literal':rb'''(?i)["'](?:password|api_key|access_token|refresh_token|client_secret)["']\s*[:=]\s*["'][^"'\r\n]{12,}["']''',
'authenticated_url':rb'https?://[^\s/:]+:[^\s/@]+@',
}
# Never echo potential matched secrets; only identify the file/rule on failure.
def scan(name,b):
    for rule,pattern in rules.items():
        assert not re.search(pattern,b), 'Potential secret in '+name+' rule='+rule
for p in files:
    rp=p.relative_to(ROOT).as_posix()
    assert not any(part in ('.venv','__pycache__','.cache') for part in p.parts)
    assert p.suffix.lower() not in ('.pt','.pth','.safetensors','.bin','.pyc','.lock','.pid','.sqlite'),rp
    assert p.stat().st_size<10_000_000,rp
    if p.suffix=='.zip':
        with zipfile.ZipFile(p) as z:
            for entry in z.infolist():
                assert Path(entry.filename).name==entry.filename
                assert Path(entry.filename).suffix in ('.py','.md','.json','.jsonl')
                scan(rp+'!'+entry.filename,z.read(entry))
    else:scan(rp,p.read_bytes())
accept=json.loads((RUN/'cpu_acceptance.json').read_text());assert accept['status']=='PASS' and accept['cpu_only'] and not accept['training']
paths=[p.relative_to(ROOT).as_posix() for p in files]+['runs_ext_p14_eval_protocol/publish_cpu_audit.json']
if '--staged' in sys.argv:
    git='/mnt/c/Program Files/Git/cmd/git.exe'
    winroot=r'C:\Users\Egret\Desktop\oulu\Agent Self-Evolution\fac_tinyagent'
    def cmd(*args):return subprocess.check_output([git,'-C',winroot,*args])
    staged=cmd('diff','--cached','--name-only','-z').decode().split('\0');staged=[x for x in staged if x]
    assert sorted(staged)==sorted(paths), 'Staged path set does not match allowlist'
    for path,meta in manifest['files'].items():
        assert sha(cmd('show',':'+path))==meta['sha256'],'Git staged normalization changed frozen bytes: '+path
    assert sha(cmd('show',':data_ext_p14_eval_protocol/manifest.json'))==MANIFEST
    print(json.dumps({'staged_audit':'PASS','staged_file_count':len(staged),'frozen_blob_bytes_preserved':True}))
else:
    report={'status':'PASS','purpose':'P14 publication allowlist and secret/weight/cache review only; no training',
            'manifest_sha256_unchanged':MANIFEST,'old_protected_files_unchanged':len(old),
            'file_count_including_this_report':len(paths),
            'candidate_files_without_this_report':{p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in files},
            'secret_scan_rules':list(rules),'secret_scan_findings':0,
            'excluded_and_preserved_locally':['_p11_fix_tmp/','runs_ext_p14_eval_protocol/draft_failure_01/ duplicate draft code/protocol/fixtures/train','runs_ext_p14_eval_protocol/draft_failure_02/ duplicate draft code'],
            'credential_access':'No credential content read; Windows Git configured helper=manager is used by git itself.',
            'cpu_evidence':'two previous full generation/acceptance runs PASS; this audit does not load models or query GPU'}
    (RUN/'publish_cpu_audit.json').write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
    print(json.dumps({'status':'PASS','files':len(paths),'bytes_before_audit_report':sum(p.stat().st_size for p in files),'manifest':MANIFEST,'secrets_found':0,'protected_old_files':len(old)}))
