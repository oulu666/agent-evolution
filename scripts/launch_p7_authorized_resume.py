"""User authorized resumption once Apex exits. Preserve the STOP record."""
import ast,datetime,time
from pathlib import Path
import run_p7_resume_20261115 as S
ast.parse((S.ROOT/'fac_tinyagent/p7_resume.py').read_text())
while True:
    d=S.inspect()
    if not d['game'] and not d['compute_apps'] and d['power_cap_W']>=60:
        break
    S.log('WAIT authorized resume: game or compute resource still occupied')
    time.sleep(30)
if S.STOP.exists():
    archive=S.STOP.with_name('STOP.game_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    assert archive.resolve().is_relative_to(S.L.resolve())
    S.STOP.rename(archive)
S.log('RESUME explicitly authorized by user after game exit; prior STOP archived')
raise SystemExit(S.run())
