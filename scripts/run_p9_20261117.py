"""Single GPU supervisor; authorized game-exit auto-resume, durable training boundaries."""
import fcntl,json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];RUN=ROOT/'runs_ext_p9_counterfactual_20261117';LOG=RUN/'logs'
os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',TOKENIZERS_PARALLELISM='false',HF_HUB_OFFLINE='1',TZ='Asia/Shanghai')
time.tzset()
def log(s):
    msg=time.strftime('%F %T %z')+' '+s;print(msg,flush=True)
    with (LOG/'supervisor.log').open('a') as f:f.write(msg+'\n')
def inspect():
    def call(cmd):return subprocess.run(cmd,capture_output=True,check=True,timeout=30).stdout.decode(errors='replace').strip()
    tasks=call(['/mnt/c/Windows/System32/tasklist.exe']);assert tasks
    power=float(call(['nvidia-smi','--query-gpu=enforced.power.limit','--format=csv,noheader,nounits']).splitlines()[0])
    return {'game':'r5apex' in tasks.lower(),'power_W':power,'compute':call(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'])}
def main():
    LOG.mkdir(parents=True,exist_ok=True)
    with (LOG/'queue.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        while True:
            state=inspect();log('PREFLIGHT '+json.dumps(state))
            if (LOG/'STOP').exists():return 75
            if state['game'] or state['power_W']<60 or state['compute']:
                log('WAIT: GPU unavailable; resume automatically when free');time.sleep(30);continue
            with (LOG/'queue.log').open('a',buffering=1) as f:
                child=subprocess.Popen([sys.executable,'-B','-m','fac_tinyagent.p9_counterfactual_20261117','queue'],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,env=os.environ,start_new_session=True)
                (LOG/'child.pid').write_text(str(child.pid));interrupted=False;failures=0
                while child.poll() is None:
                    try:child.wait(timeout=10);break
                    except subprocess.TimeoutExpired:pass
                    try:
                        state=inspect();failures=0
                        if state['game'] or state['power_W']<60 or (LOG/'STOP').exists():
                            log('PAUSING at next safe saved boundary '+json.dumps(state));child.send_signal(signal.SIGTERM);interrupted=True;break
                    except Exception as e:
                        failures+=1;log('INSPECT ERROR '+repr(e))
                        if failures>=3:child.send_signal(signal.SIGTERM);interrupted=True;break
                if interrupted:
                    try:child.wait(timeout=60)
                    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                rc=child.wait();log('CHILD END '+str(rc))
            if interrupted:time.sleep(10);continue
            return rc
if __name__=='__main__':sys.exit(main())
