from pathlib import Path
import sys,json,hashlib,ast,shutil,time
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R));N=R/'runs_ext_p7_statefix_20261115';O=R/'runs_ext_p7_response'
p=R/'scripts/p7_analyze_statefix_20261115.py';p.write_text((R/'scripts/p7_analyze.py').read_text().replace('from fac_tinyagent.p7_response import RUN,DATA,SEEDS,SKILLS','from fac_tinyagent.p7_statefix_20261115 import RUN,DATA,SEEDS,SKILLS'))
p=R/'fac_tinyagent/p7_statefix_20261115.py';s=p.read_text().replace("    log('P7 STATEFIX QUEUE COMPLETE')", "    log('P7 STATEFIX QUEUE COMPLETE')\n    from .p7_statefix_report_20261115 import finalize\n    finalize()")
p.write_text(s)
accept=json.loads((N/'cpu_contract/acceptance.json').read_text());assert accept['status']=='PASS'
for name in ['audit.json','sql_counterfactual.json','sql_tie_counterexample.json']:
 if (O/name).exists():shutil.copyfile(O/name,N/name)
files=['fac_tinyagent/p7_statefix_20261115.py','fac_tinyagent/p7_fullstate_20261115.py','fac_tinyagent/p7_statefix_report_20261115.py','scripts/run_p7_statefix_20261115.py','scripts/p7_analyze_statefix_20261115.py','scripts/prepare_p7_statefix_20261115.py','scripts/test_p7_statefix_20261115.py','P7_STATEFIX_AMEND_20261115_ZH.md','fac_tinyagent/p7_resume.py','fac_tinyagent/p7_response.py','P7_PROTOCOL_20261115_ZH.md','data_ext_p7_response/manifest.json','runs_ext_p7_statefix_20261115/cpu_contract/acceptance.json']
files += [str(p.relative_to(R)) for pattern in ['seed20261108/**/*','seed20261109/baseline/**/*','seed20261109/db.filter_cmp_top_1/**/*','seed20261109/db.filter_cmp_top_2/**/*'] for p in O.glob(pattern) if p.is_file()]
for p in [R/f for f in files if f.endswith('.py')]:ast.parse(p.read_text())
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest={'created':time.strftime('%F %T %z'),'files':{f:h(R/f) for f in files},'reuse':{'20261108':{'whole_seed':True},'20261109':{'arms':['db.filter_cmp_top'],'baseline':True}},'new_optimizer_updates':18,'logical_updates':30,'old_partial_excluded':True}
(N/'repair_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
from fac_tinyagent.p7_statefix_20261115 import verify
verify();print('FROZEN AND VERIFIED: CPU PASS, original design intact, 6/15 complete pairs reused, 9 remaining pairs /18 new updates')
