import os,sys,time
from pathlib import Path
pid=int(sys.argv[1]);root=Path(__file__).resolve().parents[1]/'runs_ext_p6_devplan/logs'
for _ in range(20):
 try:os.kill(pid,0)
 except ProcessLookupError:raise SystemExit('P6 supervisor exited; inspect launcher.log/status.log; DO NOT auto-retry safety refusal')
 if (root/'gpu_child.pid').exists():
  print('SUPERVISOR_READY child='+str((root/'gpu_child.pid').read_text()).strip());break
 time.sleep(.5)
else:raise SystemExit('P6 supervisor initialization unconfirmed; inspect logs before any further action')
