"""One-shot prospective File validation: frozen ordinary adapters, two fixed prompts."""
import os
os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',HF_HUB_OFFLINE='1',TOKENIZERS_PARALLELISM='false',TZ='Asia/Shanghai')
import argparse,fcntl,gc,hashlib,json,signal,subprocess,sys,time,traceback
from pathlib import Path
from .utils import read_json,read_jsonl,write_json,append_jsonl,canonical_json,sha256_file
from . import p10_devdiagnosis_20261117 as G
from .p10_unitclarify48_20261117 import CLARIFY
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data_ext_p10_twoview_cpu_20261117';RUN=ROOT/'runs_ext_p10_formal_prompt_20261117';LOG=RUN/'logs';SEEDS=[20261108,20261109,20261110]
time.tzset()
def log(s):print(time.strftime('%F %T %z'),s,flush=True)
def inspect(allowed):
    s=G.inspect_safety(allowed)
    if(RUN/'STOP').exists():s['STOP'].append(str((RUN/'STOP').relative_to(ROOT)));s['safe']=False
    return s
def verify():
    m=read_json(DATA/'manifest.json')
    for k in ['hashes','inherited_P9_hashes']:
        for p,h in m[k].items():assert sha256_file(ROOT/p)==h,p
    for p,h in read_json(RUN/'runtime_manifest.json')['hashes'].items():assert sha256_file(ROOT/p)==h,p
    assert CLARIFY==read_json(ROOT/'runs_ext_p10_unitclarify48_20261117/runtime_manifest.json')['clarification']
def initialize():
    assert not RUN.exists(),'No overwrite or automatic rerun';LOG.mkdir(parents=True)
    assert sha256_file(DATA/'holdout.jsonl')=='9277e44d15fce68c1844722bb599200e9e21452db7a596000060d330e62ecb3d'
    provenance=dict(frozen_created=read_json(DATA/'manifest.json')['created'],prior_run_jsonl_scanned=3131,existing_formal_outputs=[],prior_dev_model_sources=['dev.jsonl only:72 calls','dev.jsonl cached prefixes only:48 clarification answers'],gold_CPU_verification_not_model_output=True,formal_used_to_select_prompt=False,paths_markers_exact_prompts_disjoint=True,wording='4 train-style new-entity files +8 paraphrase files;not fully template disjoint',counts='train/dev2,3,4;formal2,3,4,5;5 only OOD',clarification=CLARIFY,formal_opened_for_model=False)
    write_json(RUN/'provenance.json',provenance)
    paths=[Path(__file__),ROOT/'P10_FORMAL_PROMPT_PREREG_20261117_ZH.md',RUN/'provenance.json',DATA/'manifest.json',ROOT/'fac_tinyagent/p10_devdiagnosis_20261117.py',ROOT/'fac_tinyagent/p10_unitclarify48_20261117.py',ROOT/'fac_tinyagent/sft/evaluate.py',ROOT/'fac_tinyagent/metrics.py',ROOT/'runs_ext_p10_unitclarify48_20261117/model_receipts.json',ROOT/'runs_ext_p10_unitclarify48_20261117/runtime_manifest.json']
    for seed in SEEDS:paths.append(Path(read_json(DATA/f'plan_seed{seed}.json')['reuse_ordinary_checkpoint'])/'adapter_model.safetensors')
    write_json(RUN/'runtime_manifest.json',dict(created=time.strftime('%F %T %z'),scope='one-shot prospective fixed-prompt File validation; no training;360 calls cap',calls=dict(normal_shared_tool=72,normal_answers=144,reversed_answers=144,total=360),clarification=CLARIFY,hashes={str(p.relative_to(ROOT)):sha256_file(p)for p in paths}))
    verify();s=inspect({os.getpid()});write_json(RUN/'preflight.json',s);print(json.dumps(s));return 0 if s['safe']else 75
def supervise():
    assert not(RUN/'records.jsonl').exists();verify()
    with(LOG/'formal.lock').open('a')as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);s=inspect({os.getpid()});write_json(RUN/'launch_preflight.json',s)
        if not s['safe']:write_json(RUN/'BLOCKED.json',s);log('BLOCKED '+json.dumps(s));return 75
        (LOG/'supervisor.pid').write_text(str(os.getpid()))
        with(LOG/'worker.log').open('x',buffering=1)as f:
            child=subprocess.Popen([sys.executable,'-B','-m','fac_tinyagent.p10_formal_prompt_20261117','worker'],cwd=ROOT,env=os.environ,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);(LOG/'worker.pid').write_text(str(child.pid));log('START formal worker '+str(child.pid))
            while child.poll()is None:
                try:child.wait(timeout=3);break
                except subprocess.TimeoutExpired:pass
                try:
                    s=inspect({os.getpid(),child.pid});append_jsonl(LOG/'guard.jsonl',s)
                    if s['safe']:continue
                    reason=s
                except Exception as e:reason={'inspection_error':repr(e)}
                write_json(LOG/'STOP',dict(stopped=time.strftime('%F %T %z'),reason=reason));log('SAFETY STOP '+json.dumps(reason));os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=15)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                break
            rc=child.wait();write_json(RUN/'supervisor_end.json',dict(rc=rc,finished=time.strftime('%F %T %z')));log('END formal rc='+str(rc));return rc
def worker():
    import torch
    from .sft.evaluate import load_eval_model,generate_with_usage,parse_final_answer,_evaluate_tool_prediction
    from .replay_study import config_for
    from .metrics import answers_equal,joint_success
    from . import p9_counterfactual_20261117 as P9
    verify();assert not(RUN/'records.jsonl').exists();rows=read_jsonl(DATA/'holdout.jsonl');assert len(rows)==24 and len({r['case']for r in rows})==12
    signal.signal(signal.SIGTERM,lambda s,f:sys.exit(75));signal.signal(signal.SIGINT,lambda s,f:sys.exit(75));calls=0;started=time.perf_counter();receipts=[];records=0
    def weights(model):
        h=hashlib.sha256();n=0
        for name,p in model.named_parameters():
            if'lora_'in name:h.update(name.encode());h.update(p.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes());n+=1
        assert n;return h.hexdigest()
    def infer(model,tok,messages,tag,stage):
        nonlocal calls
        assert calls<360 and not(LOG/'STOP').exists();calls+=1;append_jsonl(RUN/'calls_started.jsonl',dict(index=calls,tag=tag,stage=stage,time=time.strftime('%F %T %z')));raw,u=generate_with_usage(model,tok,messages,128);assert u['inference_calls']==1 and u['batch_size']==1;append_jsonl(RUN/'calls_completed.jsonl',dict(index=calls,tag=tag,stage=stage,**u));return raw,u
    for seed in SEEDS:
        adapter=Path(read_json(DATA/f'plan_seed{seed}.json')['reuse_ordinary_checkpoint']);ref=next(x for x in read_json(ROOT/'runs_ext_p10_unitclarify48_20261117/model_receipts.json')if x['seed']==seed);assert sha256_file(adapter/'adapter_model.safetensors')==ref['adapter_sha256']
        log('LOAD ordinary '+str(seed));model,tok=load_eval_model(config_for('A',seed,batch_size=1),str(adapter));assert not model.training;before=weights(model);assert before==ref['live_LoRA_after'];torch.cuda.reset_peak_memory_stats();begin=calls
        for case in sorted({r['case']for r in rows}):
            common={}
            for intent in ['first','last']:
                r=next(r for r in rows if r['case']==case and r['intent']==intent);tag=f'{seed}:{case}:{intent}:shared_tool';raw,u=infer(model,tok,r['messages'][:2],tag,'normal_shared_tool');res=_evaluate_tool_prediction(r,raw,str(P9.DB),str(P9.CAL));common[intent]=(raw,res,tag);append_jsonl(RUN/'shared_tools.jsonl',dict(seed=seed,case=case,intent=intent,episode_id=r['episode_id'],tag=tag,prefix_sha256=hashlib.sha256(canonical_json(r['messages'][:2]).encode()).hexdigest(),usage=u,**res))
            for kind in ['normal','reversed']:
                for intent in ['first','last']:
                    r=next(r for r in rows if r['case']==case and r['intent']==intent)
                    if kind=='normal':call,res,tooltag=common[intent];obs=res['observation']
                    else:call=r['messages'][2]['content'];obj=json.loads(r['expected_observation']);obj['result'].reverse();obs=canonical_json(obj)
                    for prompt in ['original','clarified']:
                        messages=r['messages'][:2]+[{'role':'assistant','content':call or'{}'},{'role':'user','content':'TOOL RESULT:\n'+obs+('\n\n'+CLARIFY if prompt=='clarified'else'')}];tag=f'{seed}:{case}:{kind}:{intent}:{prompt}';raw,u=infer(model,tok,messages,tag,kind+'_answer');ok,pred=parse_final_answer(raw)
                        item={k:r[k]for k in ['case','intent','episode_id','n_matches','wording_group','wording_label']};item.update(seed=seed,kind=kind,prompt_condition=prompt,expected_answer=r['expected_final_answer'],displayed_observation=obs,answer_raw=raw,predicted_answer=pred,parsed_final=bool(ok),final_correct=bool(ok and answers_equal(pred,r['expected_final_answer'])),usage=[u],generation_scope='normal_actual_tool_prefix_branched_answer'if kind=='normal'else'oracle_reversed_answer_only')
                        if kind=='normal':item.update(res);item['shared_tool_tag']=tooltag;item['joint_success']=joint_success(item)
                        append_jsonl(RUN/'records.jsonl',item);records+=1
            log(f'FORMAL {seed} case{case} done calls={calls}/360')
            if seed==SEEDS[0]and case==min(r['case']for r in rows):
                assert calls==10 and records==8 and weights(model)==before;write_json(RUN/'e2e_gate.json',dict(passed=True,inference_calls=10,records=8,new_actual_tools=2,LoRA_unchanged=True,optimizer_updates=0,meaning='actual QLoRA/tool/scoring/persistence interface; not accuracy gate'));log('FIRST GROUP E2E PASS')
        after=weights(model);assert before==after and calls-begin==120;receipts.append(dict(seed=seed,adapter_sha256=ref['adapter_sha256'],live_LoRA_before=before,live_LoRA_after=after,inference_calls=120,peak_gpu_GB=torch.cuda.max_memory_allocated()/1024**3));del model,tok;gc.collect();torch.cuda.empty_cache()
    assert calls==360 and records==288;verify();write_json(RUN/'model_receipts.json',receipts);write_json(RUN/'COMPLETE.json',dict(complete=True,finished=time.strftime('%F %T %z'),inference_calls=360,normal_shared_tools=72,normal_answers=144,reversed_oracle_answers=144,records=288,optimizer_updates=0,elapsed_seconds=time.perf_counter()-started));log('COMPLETE FORMAL360; NO TRAINING OR FOLLOWUP')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['preflight','supervise','worker']);a=p.parse_args()
    try:sys.exit({'preflight':initialize,'supervise':supervise,'worker':worker}[a.mode]())
    except Exception as e:LOG.mkdir(parents=True,exist_ok=True);write_json(RUN/'ERROR.json',dict(error=repr(e),time=time.strftime('%F %T %z')));traceback.print_exc();sys.exit(1)