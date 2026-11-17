from pathlib import Path
import ast,hashlib,json,shutil,sys,time
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R));O=R/'runs_ext_p7_response';N=R/'runs_ext_p7_statefix_20261115'
assert not N.exists(),'fresh attempt required'
s=(R/'fac_tinyagent/p7_resume.py').read_text();s=s.replace("RUN=ROOT/'runs_ext_p7_response'","RUN=ROOT/'runs_ext_p7_statefix_20261115'")
s=s.replace('from pathlib import Path','from pathlib import Path\nfrom . import p7_fullstate_20261115 as FS')
s=s.replace("    for p,h in read_json(DATA/'manifest.json')['files'].items():", "    for p,h in {**read_json(DATA/'manifest.json')['files'],**read_json(RUN/'repair_manifest.json')['files']}.items():")
s=s.replace("        prior_path=root/'interrupted_work.json'\n        if prior_path.exists(): costs.update(read_json(prior_path)['costs'])", "        reused=read_json(RUN/'repair_manifest.json')['reuse'].get(str(seed),{})\n        reused_arms=set(reused.get('arms',[]))")
s=s.replace("            out=ensure_dir(root/tag)\n            if (out/'nll.json').exists():", "            out=ensure_dir(root/tag)\n            state=FS.capture(model,opt,scaler)\n            binding=FS.save(state,out/'full_state.pt')\n            write_json(out/'full_state_receipt.json',binding)\n            disk_state=FS.load(out/'full_state.pt',binding)\n            FS.restore(disk_state,model,opt,scaler)\n            costs['exact_disk_restore_checks']+=1\n            if (out/'nll.json').exists():")
s=s.replace("            log(f'MEASURE {seed} {tag}')", "            assert read_json(out/'nll.json')['parameter_hash']==_training_state_hash(model),'measurement and persisted model differ'\n            FS.restore(disk_state,model,opt,scaler)\n            costs['exact_disk_restore_checks']+=1\n            write_json(out/'state_binding.json',{'parameter_hash':_training_state_hash(model),'checkpoint':binding,'full_model_optimizer_scaler_rng_modes_exact':True})\n            log(f'MEASURE {seed} {tag} FULL_STATE_EXACT')")
s=s.replace("            if arm in action_meta and all((root/f'{arm}_2'/f/'stage_report.json').exists() for f in ['database','file','python']):", "            if arm in reused_arms and arm in action_meta and all((root/f'{arm}_2'/f/'stage_report.json').exists() for f in ['database','file','python']):")
s=s.replace("                reconstruct=(root/f'{arm}_{dose}'/'receipt.json').exists()", "                assert not (root/f'{arm}_{dose}'/'receipt.json').exists(),'partial new attempt: resume only from full persisted state, never replay old measurement'\n                reconstruct=False")
s=s.replace("        assert costs['optimizer_steps']==10 and costs['generation_episodes']==48", "        assert costs['optimizer_steps']==2*(5-len(reused_arms))\n        assert costs['generation_episodes']==(0 if reused.get('baseline') else 8)+8*(5-len(reused_arms))\n        costs['reused_optimizer_steps']=2*len(reused_arms)\n        costs['reused_generation_episodes']=(8 if reused.get('baseline') else 0)+8*len(reused_arms)")
s=s.replace("    log('P7 queue COMPLETE')", "    log('P7 STATEFIX QUEUE COMPLETE')")
assert 'prior_path' not in s and 'FULL_STATE_EXACT' in s
p=R/'fac_tinyagent/p7_statefix_20261115.py';p.write_text(s)
t=(R/'scripts/run_p7_resume_20261115.py').read_text().replace("R=ROOT/'runs_ext_p7_response'", "R=ROOT/'runs_ext_p7_statefix_20261115'").replace("'fac_tinyagent.p7_resume'", "'fac_tinyagent.p7_statefix_20261115'")
t=t.replace("or (ROOT/'runs_ext_p6_devplan/logs/STOP').exists()", "or (ROOT/'runs_ext_p6_devplan/logs/STOP').exists() or (ROOT/'runs_ext_p7_response/logs/STOP').exists()")
(R/'scripts/run_p7_statefix_20261115.py').write_text(t)
for p in [R/'fac_tinyagent/p7_fullstate_20261115.py',R/'fac_tinyagent/p7_statefix_20261115.py',R/'scripts/run_p7_statefix_20261115.py']:ast.parse(p.read_text())
(N/'logs').mkdir(parents=True)
# Reuse only complete, internally consistent original seed or action. No incomplete File state is copied.
shutil.copytree(O/'seed20261108',N/'seed20261108')
src=O/'seed20261109';dst=N/'seed20261109';dst.mkdir()
for name in ['baseline','db.filter_cmp_top_1','db.filter_cmp_top_2']:shutil.copytree(src/name,dst/name)
meta=json.loads((src/'action_meta.json').read_text());assert list(meta)==['db.filter_cmp_top'];(dst/'action_meta.json').write_text(json.dumps(meta))
for seed,arms in [(20261108,['db.list_tables','db.filter_cmp_top','file.search_last','py.median','background']),(20261109,['db.filter_cmp_top'])]:
 man=json.loads((R/f'runs_ext_e4/prefixes/A_seed{seed}/manifest.json').read_text());base=json.loads((O/f'seed{seed}/baseline/nll.json').read_text());assert base['parameter_hash']==man['parameter_hash']
 for arm in arms:
  for d in [1,2]:
   rec=json.loads((O/f'seed{seed}/{arm}_{d}/receipt.json').read_text());assert rec['prefix_hash']==man['parameter_hash'] and rec['dose']==d and rec['actual_optimizer_steps']==d
  assert all((O/f'seed{seed}/{arm}_2'/f/'stage_report.json').exists() for f in ['database','file','python'])
print('NEW ATTEMPT PREPARED: source files unchanged; reuse seed08 + seed09 DB pair; 18 new optimizer updates; old File partial excluded')
