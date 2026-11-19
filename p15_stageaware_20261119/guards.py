"""Fail-closed local single-GPU guard. Read-only except NEW P15 sticky STOP evidence."""
import csv,io,json,os,subprocess,threading,time
from pathlib import Path
from core import ROOT,RUN,read,write
class SafetyStop(RuntimeError):pass

def safety_decision(stops,game,power,others,projects,ac=True):
 return not stops and not game and power>=60 and not others and not projects and ac

def inspect(allow_own=False):
 # Keep old low-power threshold >=60W and strengthen Apex names/AC checks.
 stops=[str(p.relative_to(ROOT)) for pattern in ('STOP','runs*/STOP','runs*/logs/STOP','runs*/*/logs/STOP') for p in ROOT.glob(pattern)]
 ps=r'''$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); $p=@(Get-Process);$b=@(Get-CimInstance Win32_Battery);[pscustomobject]@{process_count=$p.Count;game=(@($p|Where-Object {$_.ProcessName -match '(?i)r5apex|^Apex$'}).Count -gt 0);battery_status=@($b|ForEach-Object {$_.BatteryStatus})} | ConvertTo-Json -Compress'''
 cmd=['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-NonInteractive','-Command',ps]
 win=json.loads(subprocess.check_output(cmd,timeout=20).decode('utf-8-sig'));assert win['process_count']>0
 power=float(subprocess.check_output(['nvidia-smi','--query-gpu=enforced.power.limit','--format=csv,noheader,nounits'],text=True,timeout=15).strip().splitlines()[0])
 raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'],text=True,timeout=15)
 allowed={os.getpid()} if allow_own else set()
 # Only admit a verified direct batch supervisor, never arbitrary recorded numeric PIDs.
 parent=Path('/proc')/str(os.getppid())
 try:
  argv=(parent/'cmdline').read_bytes().replace(b'\0',b' ').decode()
  if 'runner.py batch' in argv and 'p15_stageaware_20261119' in argv:allowed.add(os.getppid())
 except OSError:pass
 others=[]
 for row in csv.reader(io.StringIO(raw)):
  if row and (not row[0].strip().isdigit() or int(row[0].strip()) not in allowed):others.append(row)
 projects=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit() or int(p.name) in allowed|{os.getpid()}:continue
  try:
   cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
   if 'python' not in cmd:continue
   cwd=(p/'cwd').resolve()
   if 'fac_tinyagent.' in cmd or 'p15_stageaware_20261119/' in cmd or cwd==ROOT:projects.append({'pid':int(p.name),'argv':cmd})
  except (OSError,PermissionError):continue
 battery=win.get('battery_status',[])
 if not isinstance(battery,list):battery=[battery]
 ac=all(x not in (1,4,5) for x in battery) # discharging/low/critical
 return {'STOP':sorted(set(stops)),'windows':win,'power_limit_W':power,'other_compute':others,'other_project_python':projects,'AC_not_discharging':ac,
         'safe':safety_decision(stops,win['game'],power,others,projects,ac)}

class Guard:
 def __init__(self):self.reason=None;self.stop=threading.Event();self.shutdown=threading.Event();self.thread=None
 def check(self):
  if self.stop.is_set():raise SafetyStop(str(self.reason))
 def trip(self,reason):
  self.reason=reason;self.stop.set()
  # Never clear a STOP; new evidence only belongs to this P15 directory.
  path=RUN/'logs/STOP'
  if not path.exists():write(path,{'time_Beijing':time.strftime('%F %T %z'),'reason':reason})
 def start(self):
  state=inspect(False);write(RUN/'latest_preflight.json',state)
  if not state['safe']:self.trip({'preflight':state});raise SafetyStop(str(state))
  def loop():
   while not self.shutdown.wait(2):
    try:
     state=inspect(True)
     if not state['safe']:self.trip(state);return
    except Exception as exc:self.trip({'guard_error':repr(exc)});return
  self.thread=threading.Thread(target=loop,daemon=True);self.thread.start()
 def close(self):self.shutdown.set();self.thread.join(timeout=25) if self.thread else None
