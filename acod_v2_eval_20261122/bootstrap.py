"""Operational bootstrap only. Locked runner/messages/analysis remain byte-identical."""
import os,runpy,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
# Derive paths inside Python: avoid outer WSL shell expanding PWD before its inner cd.
os.environ['PYTHONPATH']=os.pathsep.join([str(ROOT),str(HERE)])
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(HERE))
from lock_protocol import verify,rows,save,sha,now
if sys.argv[1]=='check':
    assert not rows(HERE/'results/calls_started.jsonl') and not rows(HERE/'results/responses.jsonl')
    verify()
    test=subprocess.run([sys.executable,'-B','-c','import fac_tinyagent,lock_protocol; print("CHILD_PROJECT_IMPORT_OK")'],cwd=ROOT,env=os.environ,capture_output=True,text=True,check=True,timeout=20)
    save(HERE/'STARTUP_AMENDMENT_02.json',{'time':now(),'startup_failures_before_any_model':len(rows(HERE/'results/errors.jsonl')),'attempts_before_change':0,'responses_before_change':0,'reason':'Outer shell expanded PWD to /mnt/c/Users/Egret before inner cd; environment-only amendment01 did not resolve project import','fix':'Python bootstrap derives ROOT from __file__, sets explicit inherited PYTHONPATH, then runs unchanged runner','bootstrap_sha256':sha(__file__),'protocol_lock_sha256':sha(HERE/'PROTOCOL_LOCK.json'),'child_import_test':test.stdout.strip(),'PYTHONPATH':os.environ['PYTHONPATH'],'model_protocol_changed':False})
    print(test.stdout.strip())
else:
    mode=sys.argv[1];assert mode in ['supervise','worker']
    sys.argv=[str(HERE/'runner.py'),mode]
    runpy.run_path(str(HERE/'runner.py'),run_name='__main__')