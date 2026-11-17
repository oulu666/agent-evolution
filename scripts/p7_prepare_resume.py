"""Generate an explicit resume-only copy; preserve the original frozen runner."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fac_tinyagent.utils import read_json,read_jsonl,write_json,sha256_file
from fac_tinyagent.p7_response import RUN,DATA,verify
verify()
src=(ROOT/'fac_tinyagent/p7_response.py').read_text()
def replace(old,new):
    global src
    assert src.count(old)==1,(old[:80],src.count(old))
    src=src.replace(old,new)

replace("root=ensure_dir(RUN/f'seed{seed}'); costs=collections.Counter();started=time.time()", "root=ensure_dir(RUN/f'seed{seed}'); costs=collections.Counter();started=time.time()\n        prior_path=root/'interrupted_work.json'\n        if prior_path.exists(): costs.update(read_json(prior_path)['costs'])")
replace("out=ensure_dir(root/tag);data={'dev':nll(dev),'check':nll(check),'parameter_hash':_training_state_hash(model)}\n            write_json(out/'nll.json',data)", "out=ensure_dir(root/tag)\n            if (out/'nll.json').exists():\n                data=read_json(out/'nll.json')\n                assert data['parameter_hash']==_training_state_hash(model), 'Reconstructed state differs: '+tag\n            else:\n                data={'dev':nll(dev),'check':nll(check),'parameter_hash':_training_state_hash(model)}\n                write_json(out/'nll.json',data)")
replace("rows=[r for r in check if r['tool_family']==family]\n                    evaluate_family", "rows=[r for r in check if r['tool_family']==family]\n                    if (out/family/'stage_report.json').exists():\n                        assert len(read_jsonl(out/family/'results.jsonl'))==len(rows)\n                        continue\n                    if (out/family).exists():\n                        target=RUN/'interruptions'/f'{seed}_{tag}_{family}'\n                        assert target.resolve().is_relative_to(RUN.resolve()) and (out/family).resolve().is_relative_to(RUN.resolve())\n                        ensure_dir(target.parent); (out/family).rename(target)\n                    evaluate_family")
replace("action_meta={};plan=plans[str(seed)]", "action_meta=read_json(root/'action_meta.json') if (root/'action_meta.json').exists() else {};plan=plans[str(seed)]")
replace("actions=plan['actions'][arm];rs=[pools[a['family']][a['row_index']] for a in actions]", "actions=plan['actions'][arm];rs=[pools[a['family']][a['row_index']] for a in actions]\n            if arm in action_meta and all((root/f'{arm}_2'/f/'stage_report.json').exists() for f in ['database','file','python']):\n                log(f'REUSE COMPLETE {seed} {arm}');continue")
replace("for dose in [1,2]:\n                # Restore", "for dose in [1,2]:\n                reconstruct=(root/f'{arm}_{dose}'/'receipt.json').exists()\n                # Restore")
replace("costs['training_backward']+=1;costs['training_input_tokens']+=len(ft(row)['input_ids'])", "costs['reconstruction_training_backward' if reconstruct else 'training_backward']+=1;costs['reconstruction_input_tokens' if reconstruct else 'training_input_tokens']+=len(ft(row)['input_ids'])")
replace("costs['optimizer_steps']+=1", "costs['reconstruction_optimizer_steps' if reconstruct else 'optimizer_steps']+=1")
replace("write_json(root/f'{arm}_{dose}'/'receipt.json',receipt)", "receipt_path=root/f'{arm}_{dose}'/'receipt.json'\n                if receipt_path.exists():\n                    old=read_json(receipt_path)\n                    for key in ['seed','arm','dose','replay_input_tokens','replay_id','common_calendar_ids','prefix_hash']:assert receipt[key]==old[key]\n                else:write_json(receipt_path,receipt)")
replace("free_model(model);del model,params,opt,scaler,gd,gs,basevec", "free_model(model);del model,params,opt,scaler,gd,gs,basevec") if False else None
out=ROOT/'fac_tinyagent/p7_resume.py'
if out.exists():raise RuntimeError('resume copy exists')
out.write_text(src,encoding='utf-8')

# Reconstruct accounting from actual completed optimizer receipts. Interruption was
# during generation, so each preceding train update has an on-disk receipt.
root=RUN/'seed20261109';receipts=[read_json(p) for p in root.glob('*/receipt.json')]
assert len(receipts)==4
cal={r['episode_id']:r for r in read_jsonl(ROOT/'data_phase2/calendar/train.jsonl')}
from fac_tinyagent.sft.train import load_tokenizer
from fac_tinyagent.replay_study import config_for
from fac_tinyagent.sft.dataset import tokenize_episode
tok=load_tokenizer(config_for('A',20261109,batch_size=1))
plans=read_json(DATA/'plans.json')['20261109']['actions']
train_tokens=0
for r in receipts:
    train_tokens+=sum(len(tokenize_episode(cal[eid],tok,1024)['input_ids']) for eid in r['common_calendar_ids'])
    train_tokens+=plans[r['arm']][r['dose']-1]['input_tokens']
generated=sum(len(read_jsonl(p)) for p in root.glob('*/*/results.jsonl'))
write_json(root/'interrupted_work.json',{'reason':'Apex watchdog at 2026-11-15 16:42:34 +0800','user_authorized_resume_when_game_exits':True,'costs':{'optimizer_steps':len(receipts),'training_backward':8*len(receipts),'training_input_tokens':train_tokens,'nll_forward':24*len(list(root.glob('*/nll.json'))),'generation_episodes':generated,'diagnostic_backward':18,'restorations':5},'accounting_note':'18 backward =16 dev + filter candidate + file candidate; interruption occurred after their 4 optimizer receipts during file generation. Any additional unfinished generation cost is unrecorded, not zero.'})
runner=(ROOT/'scripts/run_p7_response_20261115.py').read_text(encoding='utf-8-sig').replace('fac_tinyagent.p7_response','fac_tinyagent.p7_resume')
(ROOT/'scripts/run_p7_resume_20261115.py').write_text(runner,encoding='utf-8')
write_json(RUN/'resume_manifest.json',{'reason':'Resume after game exit, unchanged data/actions/hyperparameters','user_authorization':'游戏退出后自动接续本轮实验','files':{str(p.relative_to(ROOT)):sha256_file(p) for p in [out,ROOT/'scripts/run_p7_resume_20261115.py',Path(__file__)]},'completed_evaluations_reused':True,'reconstruct_partial_branch_requires_two_extra_optimizer_steps':True})
print('Resume prepared; original frozen inputs and completed results preserved.')
