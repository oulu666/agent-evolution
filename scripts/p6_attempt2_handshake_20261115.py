import os,sys,time
from pathlib import Path
pid=int(sys.argv[1]);root=Path(__file__).resolve().parents[1]/'runs_ext_p6_devplan_attempt2/logs'
for _ in range(40):
 try:os.kill(pid,0)
 except ProcessLookupError:raise SystemExit('attempt2 supervisor exited; inspect logs; never auto-retry safety refusal')
 # Bind handshake to this exact supervisor, not a stale child PID file.
 rp=root/'runner.pid';cp=root/'gpu_child.pid'
 if rp.exists() and cp.exists() and int(rp.read_text())==pid:
  child=int(cp.read_text())
  try:os.kill(child,0)
  except ProcessLookupError:raise SystemExit('attempt2 child exited during startup')
  print(f'SUPERVISOR_READY pid={pid} child={child}');break
 time.sleep(.5)
else:raise SystemExit('initialization unconfirmed; inspect before retry')
