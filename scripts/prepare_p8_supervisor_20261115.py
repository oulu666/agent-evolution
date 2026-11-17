from pathlib import Path
R=Path(__file__).resolve().parents[1]
p=R/'fac_tinyagent/p8_decision_20261115.py';s=p.read_text().replace('其他为多schema/table、必须WHERE/tie的SQL','其他为新schema实体、必须WHERE/tie的SQL');p.write_text(s)
s=(R/'scripts/run_p6_attempt2_20261115.py').read_text().replace("R=ROOT/'runs_ext_p6_devplan_attempt2'", "R=ROOT/'runs_ext_p8_decision_20261115'").replace("'fac_tinyagent.p6_attempt2'", "'fac_tinyagent.p8_decision_20261115'").replace('P6 runner already active','P8 runner already active').replace(" or (ROOT/'runs_ext_p6_devplan/logs/STOP').exists()",'')
(R/'scripts/run_p8_decision_20261115.py').write_text(s)
print('P8 prereg and same safety supervisor ready; no GPU started')
