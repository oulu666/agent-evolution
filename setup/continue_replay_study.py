"""Wait for the already running historical audit, then execute the frozen pilot."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fac_tinyagent.replay_study import HISTORICAL, run_all

started = time.monotonic()
while len(list(HISTORICAL.glob("*/*/*/stage_report.json"))) < 48:
    if time.monotonic() - started > 3600:
        raise TimeoutError("Historical audit did not complete; no training was started")
    time.sleep(10)
print("Historical endpoints complete; continuing frozen study.", flush=True)
run_all()
