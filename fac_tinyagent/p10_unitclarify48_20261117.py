"""48 new answer-only dev calls: one fixed text/line output-field clarification."""
import os
os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',HF_HUB_OFFLINE='1',TOKENIZERS_PARALLELISM='false',TZ='Asia/Shanghai')
import argparse,collections,fcntl,gc,hashlib,json,signal,subprocess,sys,time,traceback
from pathlib import Path
from .utils import read_json,read_jsonl,write_json,append_jsonl,sha256_file,canonical_json
from . import p10_devdiagnosis_20261117 as G
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data_ext_p10_twoview_cpu_20261117';BASE=ROOT/'runs_ext_p10_devdiagnosis_20261117';RUN=ROOT/'runs_ext_p10_unitclarify48_20261117';LOG=RUN/'logs';SEEDS=[20261108,20261109,20261110]
CLARIFY="Output-field clarification: In the answer field, return the complete value of the selected matching item's text field, not its line field and not only a number extracted from its text. Keep the task's original selection instruction unchanged."
time.tzset()
def log(s):print(time.strftime('%F %T %z'),s,flush=True)
def inspect(allowed):
    state=G.inspect_safety(allowed)
    if (RUN/'STOP').exists():state['STOP'].append(str((RUN/'STOP').relative_to(ROOT)));state['safe']=False
    return state

def verify():
    m=read_json(DATA/'manifest.json')
    for kind in ['hashes','inherited_P9_hashes']:
        for p,h in m[kind].items():assert sha256_file(ROOT/p)==h,p
    for p,h in read_json(RUN/'runtime_manifest.json')['hashes'].items():assert sha256_file(ROOT/p)==h,p

def initialize():
    assert not RUN.exists(),'No overwrite/automatic rerun';LOG.mkdir(parents=True)
    assert read_json(BASE/'COMPLETE.json')['inference_calls']==72
    baseline=read_jsonl(BASE/'records.jsonl');assert len(baseline)==48
    dev={r['episode_id']:r for r in read_jsonl(DATA/'dev.jsonl')}
    for b in baseline:
        r=dev[b['episode_id']];orig=json.loads(r['expected_observation'])['result'];assert r['expected_final_answer']==orig[0 if r['intent']=='first' else -1]['text']
        assert b['expected_answer']==r['expected_final_answer']
    paths=[Path(__file__),ROOT/'P10_DEV48_UNIT_CLARIFY_PREREG_20261117_ZH.md',DATA/'manifest.json',BASE/'records.jsonl',BASE/'model_receipts.json',BASE/'final_manifest.json',ROOT/'fac_tinyagent/p10_devdiagnosis_20261117.py']
    write_json(RUN/'runtime_manifest.json',dict(created=time.strftime('%F %T %z'),scope='48 additional answer-only dev calls; cached baselines; no training/formal',clarification=CLARIFY,success_criterion='normal strict gain >=12/24 and normal item selection retained24/24',hashes={str(p.relative_to(ROOT)):sha256_file(p) for p in paths}))
    state=inspect({os.getpid()});write_json(RUN/'preflight.json',state);print(json.dumps(state,ensure_ascii=False));return 0 if state['safe'] else 75

def supervise():
    assert not (RUN/'records.jsonl').exists();verify()
    with (LOG/'dev.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);state=inspect({os.getpid()});write_json(RUN/'launch_preflight.json',state)
        if not state['safe']:write_json(RUN/'BLOCKED.json',state);log('BLOCKED '+json.dumps(state));return 75
        (LOG/'supervisor.pid').write_text(str(os.getpid()))
        with (LOG/'worker.log').open('x',buffering=1) as f:
            child=subprocess.Popen([sys.executable,'-B','-m','fac_tinyagent.p10_unitclarify48_20261117','worker'],cwd=ROOT,env=os.environ,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
            (LOG/'worker.pid').write_text(str(child.pid));log('START clarify48 worker '+str(child.pid))
            while child.poll() is None:
                try:child.wait(timeout=3);break
                except subprocess.TimeoutExpired:pass
                try:
                    state=inspect({os.getpid(),child.pid});append_jsonl(LOG/'guard.jsonl',state)
                    if state['safe']:continue
                    reason=state
                except Exception as e:reason={'inspection_error':repr(e)}
                write_json(LOG/'STOP',dict(stopped=time.strftime('%F %T %z'),reason=reason));log('STOP '+json.dumps(reason));os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=15)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                break
            rc=child.wait();write_json(RUN/'supervisor_end.json',dict(rc=rc,finished=time.strftime('%F %T %z')));log('END clarify48 rc='+str(rc));return rc

def worker():
    import torch
    from .sft.evaluate import load_eval_model,generate_with_usage,parse_final_answer
    from .replay_study import config_for
    from .metrics import answers_equal
    verify();assert not (RUN/'records.jsonl').exists();base=read_jsonl(BASE/'records.jsonl');dev={r['episode_id']:r for r in read_jsonl(DATA/'dev.jsonl')};assert len(base)==48
    signal.signal(signal.SIGTERM,lambda s,f:sys.exit(75));signal.signal(signal.SIGINT,lambda s,f:sys.exit(75));calls=0;started=time.perf_counter();receipts=[]
    def weights(model):
        h=hashlib.sha256();n=0
        for name,p in model.named_parameters():
            if 'lora_' in name:h.update(name.encode());h.update(p.detach().cpu().contiguous().view(torch.uint8).numpy().tobytes());n+=1
        assert n;return h.hexdigest()
    for seed in SEEDS:
        adapter=Path(read_json(DATA/f'plan_seed{seed}.json')['reuse_ordinary_checkpoint']);ref=next(x for x in read_json(BASE/'model_receipts.json') if x['seed']==seed);assert sha256_file(adapter/'adapter_model.safetensors')==ref['adapter_sha256']
        log('LOAD '+str(seed));model,tok=load_eval_model(config_for('A',seed,batch_size=1),str(adapter));assert not model.training;before=weights(model);assert before==ref['live_LoRA_after'];torch.cuda.reset_peak_memory_stats()
        for case in range(4):
            for kind in ['normal','reversed']:
                for intent in ['first','last']:
                    b=next(b for b in base if b['seed']==seed and b['case']==case and b['kind']==kind and b['intent']==intent);r=dev[b['episode_id']]
                    call=b['tool_call_raw'] if kind=='normal' else r['messages'][2]['content'];messages=r['messages'][:2]+[{'role':'assistant','content':call},{'role':'user','content':'TOOL RESULT:\n'+b['displayed_observation']+'\n\n'+CLARIFY}]
                    assert calls<48 and not (LOG/'STOP').exists();calls+=1;tag=f'{seed}:{case}:{kind}:{intent}';append_jsonl(RUN/'calls_started.jsonl',dict(index=calls,tag=tag,time=time.strftime('%F %T %z')))
                    raw,u=generate_with_usage(model,tok,messages,128);assert u['inference_calls']==1;append_jsonl(RUN/'calls_completed.jsonl',dict(index=calls,tag=tag,**u));ok,pred=parse_final_answer(raw)
                    item={k:b[k] for k in ['seed','case','kind','intent','episode_id','n_matches','expected_answer','displayed_observation']};item.update(answer_raw=raw,predicted_answer=pred,parsed_final=bool(ok),final_correct=bool(ok and answers_equal(pred,b['expected_answer'])),usage=[u],generation_scope='answer_only_cached_prefix',baseline_tag=tag,clarification=CLARIFY)
                    if kind=='normal':
                        for k in ['tool_correct','arguments_correct','execution_success']:item['cached_'+k]=b[k]
                        item['cached_trajectory_joint']=bool(all(b[k] for k in ['tool_correct','arguments_correct','execution_success']) and item['final_correct'])
                    append_jsonl(RUN/'records.jsonl',item)
            log(f'CLARIFY {seed} case{case} calls={calls}/48')
            if seed==SEEDS[0] and case==0:
                assert calls==4 and weights(model)==before;write_json(RUN/'e2e_gate.json',dict(passed=True,inference_calls=4,records=4,LoRA_unchanged=True,optimizer_updates=0,meaning='generation/persistence/scoring contract, not accuracy'));log('FIRST GROUP PASS')
        after=weights(model);assert before==after;receipts.append(dict(seed=seed,adapter_sha256=ref['adapter_sha256'],live_LoRA_before=before,live_LoRA_after=after,inference_calls=16,peak_gpu_GB=torch.cuda.max_memory_allocated()/1024**3));del model,tok;gc.collect();torch.cuda.empty_cache()
    assert calls==48;verify();write_json(RUN/'model_receipts.json',receipts);write_json(RUN/'COMPLETE.json',dict(complete=True,finished=time.strftime('%F %T %z'),inference_calls=48,records=48,new_tool_calls=0,optimizer_updates=0,formal_calls=0,elapsed_seconds=time.perf_counter()-started));log('COMPLETE clarify48; NO TRAINING')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['preflight','supervise','worker']);a=p.parse_args()
    try:sys.exit({'preflight':initialize,'supervise':supervise,'worker':worker}[a.mode]())
    except Exception as e:LOG.mkdir(parents=True,exist_ok=True);write_json(RUN/'ERROR.json',dict(error=repr(e),time=time.strftime('%F %T %z')));traceback.print_exc();sys.exit(1)