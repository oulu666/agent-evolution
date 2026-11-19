"""CPU-only final entry. Preserve frozen GPU/science source; repair ONLY PID identity guard."""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import sys,time,json,hashlib,inspect,difflib,traceback
from pathlib import Path
from . import p13_phase0b_persist_20261119 as F
from .p13_phase0b_persist_20261119 import ROOT,RUN,SEEDS,read_json,read_jsonl,write_json,sha256_file,now
AUDIT=RUN/'cpu_final_guard_repair_20261119_v2'

def is_project_python(record,root=str(ROOT)):
    if not record:return False
    cmd=record.get('argv',[]);exe=Path(record.get('exe','')).name.lower()
    python=exe.startswith('python') or (bool(cmd) and Path(cmd[0]).name.lower().startswith('python'))
    return python and (any('fac_tinyagent' in arg or 'p13_phase0b' in arg for arg in cmd) or record.get('cwd','')==root or (python and not record.get('cwd','')))

def should_block(record,own_pid):
    return bool(record and record['pid']!=own_pid and is_project_python(record))

def cpu_guard_tests():
    root=str(ROOT)
    cases=[('pid_absent',None,False),('unrelated_pid_reuse',{'pid':470,'argv':['/usr/lib/systemd/systemd-udevd','--daemon'],'exe':'/usr/lib/systemd/systemd-udevd','cwd':'/'},False),('real_experiment_alive',{'pid':470,'argv':['.venv/bin/python','-B','-m','fac_tinyagent.p13_phase0b_persist_20261119','worker'],'exe':'/usr/bin/python3.12','cwd':root},True),('same_module_different_PID',{'pid':999,'argv':['python','-m','fac_tinyagent.p13_phase0b_persist_20261119','supervise'],'exe':'/usr/bin/python3','cwd':'/tmp'},True)]
    out=[]
    for name,record,expected in cases:
        actual=should_block(record,123);assert actual==expected;out.append({'case':name,'expected_block':expected,'actual_block':actual,'passed':True})
    return out

def proc_record(pid):
    p=Path('/proc',str(pid))
    try:
        argv=[x.decode(errors='replace') for x in (p/'cmdline').read_bytes().split(b'\0') if x]
        stat=(p/'stat').read_text();fields=stat.rsplit(') ',1)[1].split()
        try:exe=os.readlink(p/'exe')
        except (FileNotFoundError,PermissionError):exe=''
        try:cwd=os.readlink(p/'cwd')
        except (FileNotFoundError,PermissionError):cwd=''
        return {'pid':pid,'argv':argv,'exe':exe,'cwd':cwd,'start_ticks_since_boot':fields[19],'state':fields[0]}
    except (FileNotFoundError,ProcessLookupError):return None

def cpu_identity_guard(active):
    # Historical numeric PIDs are evidence to inspect, never process identities.
    recorded={str(pid):proc_record(pid) for pid in [active['supervisor_pid'],active['worker_pid']]}
    records=[]
    for p in Path('/proc').iterdir():
        if p.name.isdigit():
            r=proc_record(int(p.name))
            if r and is_project_python(r):records.append(r)
    blocking=[r for r in records if should_block(r,os.getpid())]
    state=F.P.inspect({os.getpid()}) # Read-only Windows/GPU/project scan. Does not load a model.
    evidence={'time':now(),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'self':proc_record(os.getpid()),'historical_recorded_numeric_PIDs_current_identity':recorded,'current_project_python':records,'blocking_project_python':blocking,'read_only_GPU_and_Windows_check':state,'rule':'Require rc0, GPU_COMPLETE and all nodes; block actual project Python or any GPU compute, not unrelated reused numeric PID.'}
    write_json(AUDIT/'process_identity_check.json',evidence)
    assert not blocking,'actual experiment/project Python still running'
    assert not state['compute'] and not state['other_project_python'],'actual GPU compute/project task still running'
    assert not state['STOP'] and not state['windows']['game'],'STOP/game present; final blocked'
    assert read_json(RUN/'GPU_COMPLETE.json')['seeds']==3
    assert read_json(RUN/'supervisor_end.json')['rc']==0
    for seed in SEEDS:
        root=RUN/'seeds'/f'seed{seed}';out=ROOT/read_json(root/'COMPLETE.json')['attempt']
        for node in ['node00','node05','node10']:
            assert len(read_jsonl(out/node/'results.jsonl'))==48
            assert read_json(out/node/'COMPLETE.json')['n']==48
def repaired_independent_cpu_checks():
    # No model construction, CUDA tensors or project worker may run here.
    import torch
    from . import p7_fullstate_v2_20261115 as FS
    assert read_json(RUN/'supervisor_end.json')['rc']==0
    active=read_json(RUN/'active.json')
    cpu_identity_guard(active)
    a=RUN/'engineering_A';assert read_json(a/'nll_primary8.json')['rows']==read_json(a/'nll_restored8.json')['rows']
    count=read_json(a/'cost.json')['counts'];assert count['NLL_forward_samples']==32 and count['engineering_primary_optimizer_steps']==1 and count['engineering_control_optimizer_steps']==1 and count.get('generation_episodes',0)==0
    receipts=list(RUN.rglob('*.receipt.json'));base_seen=set()
    for p in receipts:
        r=read_json(p);assert sha256_file(r['path'])==r['file_sha256'];payload=torch.load(r['path'],map_location='cpu',weights_only=False);assert FS.digest({'base_semantic_sha256':payload['base_semantic_sha256'],'train':payload['train'],'attrs':payload['attrs'],'backend':payload['backend']})==r['semantic_sha256']
        base=r['base_reference'];assert sha256_file(base['path'])==base['file_sha256']
        if base['path'] not in base_seen:assert FS.digest(torch.load(base['path'],map_location='cpu',weights_only=False))==base['semantic_sha256'];base_seen.add(base['path'])
    updates=0
    for seed in SEEDS:
        root=RUN/'seeds'/f'seed{seed}';out=ROOT/read_json(root/'COMPLETE.json')['attempt'];assert read_json(out/'extended_restoration.json')['exact']
        u=read_jsonl(out/'updates.jsonl');natural=[r for r in u if r['kind']=='natural_suffix'];assert [r['step'] for r in natural]==list(range(1,11))
        pred=read_json(out/'prediction.json');assert natural[0]['receipt']==pred['theta_v1_receipt'];assert natural[0]['physical_optimizer_update'] is False
        assert pred['time']<=natural[0]['time'];assert len(pred['rows'])==96
        for node in ['node00','node05','node10']:
            rr=read_json(out/node/'COMPLETE.json');rs=read_jsonl(out/node/'results.jsonl');assert len(rs)==48 and rr['results_sha256']==sha256_file(out/node/'results.jsonl')
        c=read_json(out/'cost.json')['counts'];updates+=sum(v for k,v in c.items() if k.endswith('_optimizer_steps'));assert c['NLL_forward_samples']==192 and c['generation_episodes']==144
    assert updates==29
    write_json(RUN/'persistence_independent_CPU_checks.json',{'time':now(),'passed':True,'exact_saved_NLL':True,'receipt_count':len(receipts),'base_blob_count':len(base_seen),'stage_A_physical_steps':2,'stage_B_physical_steps':29,'logical_suffix_steps':30,'all_extended_restorations_exact':True,'no_GPU_model_loaded':True})

def main():
    time.tzset();assert not (RUN/'COMPLETE.json').exists(),'already final-complete; no overwrite';AUDIT.mkdir(exist_ok=True)
    frozen=F.verify();src=Path(F.__file__);expected=frozen['hashes'][str(src.relative_to(ROOT))];assert sha256_file(src)==expected
    original=inspect.getsource(F.independent_cpu_checks);replacement=inspect.getsource(repaired_independent_cpu_checks)
    expected_original=replacement.replace('def repaired_independent_cpu_checks():','def independent_cpu_checks():').replace('    cpu_identity_guard(active)',"    for pid in [active['supervisor_pid'],active['worker_pid']]:assert not Path('/proc',str(pid)).exists(),'GPU session still running'")
    assert original.rstrip()==expected_original.rstrip(),'patch extends beyond one operational guard'
    tests=cpu_guard_tests();write_json(AUDIT/'unit_tests.json',{'time':now(),'passed':True,'cases':tests})
    diff=''.join(difflib.unified_diff(original.splitlines(True),replacement.splitlines(True),fromfile='frozen:independent_cpu_checks',tofile='new CPU wrapper:repaired_independent_cpu_checks'))
    (AUDIT/'guard_only.diff').write_text(diff)
    scientific_refs={str(F.DATA/'manifest.json'):sha256_file(F.DATA/'manifest.json'),str(ROOT/'fac_tinyagent/p13_phase0b_20261118.py'):sha256_file(ROOT/'fac_tinyagent/p13_phase0b_20261118.py'),str(src):sha256_file(src),str(ROOT/'P13_PHASE0B_PREREG_20261118_ZH.md'):sha256_file(ROOT/'P13_PHASE0B_PREREG_20261118_ZH.md')}
    receipt={'time':now(),'operational_only':True,'new_CPU_wrapper':str(Path(__file__).relative_to(ROOT)),'new_wrapper_sha256':sha256_file(__file__),'original_frozen_module_sha256':expected,'original_function_sha256':hashlib.sha256(original.encode()).hexdigest(),'new_function_sha256':hashlib.sha256(replacement.encode()).hexdigest(),'scientific_refs_unchanged':scientific_refs,'original_failure_preserved':str(RUN/'FAILED_20261119_023945.json'),'original_failure_sha256':sha256_file(RUN/'FAILED_20261119_023945.json'),'core_algorithm_and_scientific_gates_not_changed':True,'no_new_GPU_attempt':True,'CUDA_VISIBLE_DEVICES':os.environ['CUDA_VISIBLE_DEVICES']}
    write_json(AUDIT/'operational_patch_receipt.json',receipt)
    cpu_identity_guard(read_json(RUN/'active.json'))
    F.independent_cpu_checks=repaired_independent_cpu_checks # Explicit, audited one-guard in-memory adapter; frozen file untouched.
    result=F.analyze()
    import torch
    assert not torch.cuda.is_initialized(),'CPU final unexpectedly initialized CUDA'
    for p,h in scientific_refs.items():assert sha256_file(p)==h
    write_json(AUDIT/'CPU_FINAL_COMPLETE.json',{'time':now(),'passed':True,'decision':result['decision'],'CUDA_initialized':False,'new_optimizer_steps':0,'new_NLL_forward':0,'new_generate':0,'original_science_hashes_unchanged':True})
    return result

if __name__=='__main__':
    try:main()
    except BaseException as e:
        AUDIT.mkdir(exist_ok=True);write_json(AUDIT/f'FAILED_CPU_FINAL_{time.strftime("%Y%m%d_%H%M%S")}.json',{'time':now(),'error':repr(e),'no_GPU_retry':True});traceback.print_exc();sys.exit(1)
