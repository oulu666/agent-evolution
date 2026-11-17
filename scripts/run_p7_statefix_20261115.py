"""P7 single-GPU supervisor. STOP is sticky; never auto-resume after gaming."""
import argparse,datetime,fcntl,json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'runs_ext_p7_statefix_20261115'; L=R/'logs'; STOP=L/'STOP'
os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',TOKENIZERS_PARALLELISM='false',HF_HUB_OFFLINE='1')
def log(s):
 text=datetime.datetime.now().astimezone().isoformat()+' '+s
 print(text,flush=True)
 with (L/'status.log').open('a') as f: f.write(text+'\n')
def command(cmd): return subprocess.run(cmd,capture_output=True,timeout=30,check=True).stdout.decode('utf-8',errors='replace').strip()
def inspect():
 tasks=command(['/mnt/c/Windows/System32/tasklist.exe'])
 if not tasks: raise RuntimeError('empty tasklist')
 game='r5apex' in tasks.lower()
 cap=float(command(['nvidia-smi','--query-gpu=enforced.power.limit','--format=csv,noheader,nounits']).splitlines()[0])
 apps=command(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader'])
 gpu=command(['nvidia-smi','--query-gpu=name,memory.used,utilization.gpu','--format=csv,noheader'])
 return {'game':game,'power_cap_W':cap,'compute_apps':apps,'gpu':gpu,'stop_exists':STOP.exists() or (ROOT/'runs_ext_p6_devplan/logs/STOP').exists() or (ROOT/'runs_ext_p7_response/logs/STOP').exists()}
def preflight():
 d=inspect(); log('PREFLIGHT '+json.dumps(d))
 (R/'preflight.json').write_text(json.dumps({'time':datetime.datetime.now().astimezone().isoformat(),**d},indent=2))
 if d['game'] or d['power_cap_W']<60 or d['compute_apps'] or d['stop_exists']: raise SystemExit('unsafe preflight; no GPU launch')
 return d
def terminate(child,reason):
 STOP.write_text(reason+'\n'); log('STOP '+reason)
 if child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try: child.wait(timeout=8)
  except subprocess.TimeoutExpired: os.killpg(child.pid,signal.SIGKILL); child.wait()
def run():
 L.mkdir(parents=True,exist_ok=True)
 with (L/'queue.lock').open('a') as lock:
  try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError: raise SystemExit('P7 runner already active')
  preflight()
  (L/'runner.pid').write_text(str(os.getpid()))
  with (L/'queue.log').open('a',buffering=1) as output:
   p=subprocess.Popen([sys.executable,'-B','-m','fac_tinyagent.p7_statefix_20261115','queue'],cwd=ROOT,env=os.environ,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
   (L/'gpu_child.pid').write_text(str(p.pid)); log('START queue child='+str(p.pid))
   failures=0
   def interrupted(sig,frame):
    terminate(p,'runner interrupted'); raise SystemExit(128+sig)
   signal.signal(signal.SIGTERM,interrupted); signal.signal(signal.SIGINT,interrupted)
   while p.poll() is None:
    try: p.wait(timeout=10); break
    except subprocess.TimeoutExpired: pass
    if STOP.exists(): terminate(p,'STOP flag detected'); break
    try:
     d=inspect(); failures=0
     if d['game']: terminate(p,'r5apex detected: explicit user approval required to resume'); break
     if d['power_cap_W']<60: terminate(p,'power cap below 60W'); break
    except Exception as e:
     failures+=1; log('WATCHDOG check failed '+repr(e))
     if failures>=3: terminate(p,'3 safety-check failures (fail closed)'); break
   rc=p.wait(); log('END queue rc='+str(rc)); return rc
if __name__=='__main__':
 p=argparse.ArgumentParser(); p.add_argument('--phase',choices=['preflight','queue'],required=True); a=p.parse_args()
 L.mkdir(parents=True,exist_ok=True)
 if a.phase=='preflight': preflight()
 else: sys.exit(run())

