from pathlib import Path
import sys,json,ast,hashlib,time
R=Path(__file__).resolve().parents[1];N=R/'runs_ext_p7_statefix_v2_20261115';A=R/'runs_ext_p7_statefix_20261115';sys.path.insert(0,str(R))
accept=json.loads((N/'cpu_contract/acceptance.json').read_text());assert accept['status']=='PASS' and accept['actual_bnb_FSDP_wrapped_state_native_roundtrip_prefetch']
p=R/'fac_tinyagent/p7_statefix_report_v2_20261115.py';s=p.read_text().replace("lines+=['## 成本与方法结论'", "lines+=['## 修复执行记录','v1新增包装器在18:04:14因bnb FSDP包装态被误当运行态而失败，v2使用原生load_state_dict并通过真实bnb CPU回归及GPU完整状态校验；旧hash漂移根因不能从不完整历史产物唯一推断。详见P7_STATEFIX_V2_AMEND_20261115_ZH.md。','## 成本与方法结论'")
s=s.replace("'old_partial_reused':False", "'old_partial_reused':False,'known_extra_training_backward':40")
p.write_text(s)
files=['fac_tinyagent/p7_statefix_v2_20261115.py','fac_tinyagent/p7_fullstate_v2_20261115.py','fac_tinyagent/p7_statefix_report_v2_20261115.py','scripts/run_p7_statefix_v2_20261115.py','scripts/p7_analyze_statefix_v2_20261115.py','scripts/test_p7_statefix_v2_20261115.py','scripts/prepare_p7_statefix_v2_20261115.py','P7_STATEFIX_V2_AMEND_20261115_ZH.md','runs_ext_p7_statefix_v2_20261115/cpu_contract/acceptance.json','.venv/lib/python3.12/site-packages/bitsandbytes/optim/optimizer.py','runs_ext_p7_statefix_20261115/repair_manifest.json','runs_ext_p7_response/seed20261109/interrupted_work.json']
old=json.loads((A/'repair_manifest.json').read_text())
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for f in files:
 if f.endswith('.py'):ast.parse((R/f).read_text())
m={'created':time.strftime('%F %T %z'),'files':{**old['files'],**{f:h(R/f) for f in files}},'reuse':old['reuse'],'new_optimizer_updates':18,'logical_updates':30,'old_partial_excluded':True,'known_discarded_updates':4,'v1_failed_second_step_no_parameter_updated':True}
(N/'repair_manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2))
from fac_tinyagent.p7_statefix_v2_20261115 import verify
verify();print('V2 FREEZE PASS: actual bnb CPU contract PASS, strict exact-state restore, 18 remaining updates only')
