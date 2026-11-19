"""Operational repair of the SAME frozen Phase0B; no new scientific thresholds."""
from . import p13_phase0b_20261118 as P
from .p13_phase0b_20261118 import ROOT,DATA,SEEDS,SKILLS,SEGMENTS,CAL,DB,now,log,read_json,read_jsonl,write_json,write_jsonl,append_jsonl,sha256_file,weighted_metrics,metric_table,macro_auc,bootstrap
import os,sys,time,math,json,collections,signal,subprocess,fcntl,traceback,argparse
from pathlib import Path
RUN=ROOT/'runs_ext_p13_phase0b_persist_20261119';LOG=RUN/'logs';MOD='fac_tinyagent.p13_phase0b_persist_20261119'
AMEND=ROOT/'P13_PHASE0B_OPERATIONAL_REPAIR_20261119_ZH.md'
def verify():
    P.verify();m=read_json(RUN/'operational_freeze.json')
    for p,h in m['hashes'].items():assert sha256_file(ROOT/p)==h,'operational frozen reference changed '+p
    return m

def build():
    from .p13_phase0b_persist_state_20261119 import cpu_test
    P.verify();assert not (RUN/'operational_freeze.json').exists();RUN.mkdir(exist_ok=True);LOG.mkdir(exist_ok=True)
    refs=[Path(__file__),AMEND,ROOT/'fac_tinyagent/p13_phase0b_persist_state_20261119.py',DATA/'manifest.json',P.RUN/'formal_freeze.json']
    reuse={}
    for seed in SEEDS:
        d=P.RUN/'calibration'/f'seed{seed}';assert (d/'COMPLETE.json').exists()
        fs=sorted(p for p in d.rglob('*') if p.is_file());refs+=fs;reuse[str(seed)]={'complete':str(d/'COMPLETE.json'),'files':len(fs)}
    inventory={str(s):len(list((P.RUN/'seeds'/f'seed{s}').glob('attempt[0-9][0-9]'))) for s in SEEDS};assert inventory[str(SEEDS[0])]==2;assert all(inventory[str(s)]<2 for s in SEEDS[1:])
    test=cpu_test();assert test['passed'];write_json(RUN/'cpu_tests.json',{'time':now(),**test,'legacy_inventory':inventory,'reuse_calibration':reuse})
    write_json(RUN/'operational_freeze.json',{'time':now(),'authorization_time_Beijing':'2026-11-19 01:04','authorization':'允许进行一次单种子最多两步的工程诊断，修复并验证状态保存恢复；通过后给受影响种子增加一次测评机会，不改科学判据，再失败就停止。','hashes':{str(p.relative_to(ROOT)):sha256_file(p) for p in refs},'old_attempt_inventory':inventory,'stage_A_limits':{'optimizer_steps':2,'backward_samples':16,'NLL_forward_samples':32,'generate':0},'stage_B_new_physical_optimizer_steps':29,'stage_B_logical_suffix_steps':30,'new_total_physical_steps':31,'no_automatic_retry':True});log('OPERATIONAL FREEZE CPU PASS')

class Engine(P.Engine):
    def __init__(self,seed,out):
        super().__init__(seed,out)
        from .p13_phase0b_persist_state_20261119 import Store
        self.store=Store(self,RUN/'state_store');self.origin=self.store.save(out/'origin.pt');self.finished=False
    def safe(self):
        stops=list(ROOT.glob('runs*/logs/STOP'))
        if stops:raise RuntimeError('sticky STOP '+str(stops))
    def nll(self,rows,tag):
        state=self.store.save(self.out/(tag+'_binding.pt'))
        try:return super().nll(rows,tag)
        finally:self.store.restore(state)
    def update(self,rows,kind,step):
        self.safe();assert len(rows)==8;self.phase=kind;self.model.train();self.opt.zero_grad(set_to_none=True);t=self.torch;start=time.perf_counter();losses=[]
        for r in rows:
            self.safe()
            with t.autocast(device_type='cuda',dtype=self.dtype):loss=self.model(**self.batch(r)).loss
            assert t.isfinite(loss);losses.append(float(loss.detach()));self.scaler.scale(loss/8).backward();self.cost[kind+'_backward_samples']+=1;self.cost[kind+'_input_tokens']+=len(self.feature(r)['input_ids']);self.memory()
        from .p13_phase0b_persist_state_20261119 import plain_cpu
        grads={n:plain_cpu(p.grad) for n,p in self.model.named_parameters() if p.grad is not None};assert grads and all(t.isfinite(v).all() for v in grads.values());gh=self.FS.digest(grads);del grads
        self.scaler.step(self.opt);self.scaler.update();self.opt.zero_grad(set_to_none=True);self.cost[kind+'_optimizer_steps']+=1;self.memory();self.timings[f'{kind}_{step}_seconds']=time.perf_counter()-start
        state=self.capture();rec={'time':now(),'seed':self.seed,'step':step,'kind':kind,'losses':losses,'gradient_sha256':gh,'state_hash':self.FS.digest(state),'LoRA_hash':self.FS.digest(state['parameters']),'optimizer_hash':self.FS.digest(state['optimizer'])}
        append_jsonl(self.out/'updates.jsonl',rec);append_jsonl(RUN/'progress.jsonl',rec);log(f'{self.seed} {kind} step {step} complete');return rec
    def finish(self):
        if self.finished:return
        self.opt.zero_grad(set_to_none=True);self.store.restore(self.origin)
        write_json(self.out/'extended_restoration.json',{'time':now(),'exact':True,'origin_receipt':self.origin,'base_buffers_quant_state_backend_included':True})
        receipt=super().finish();self.finished=True;return receipt

    def generation(self,rows,tag,previous=None):
        from .sft.evaluate import generate_with_usage,_evaluate_tool_prediction,parse_final_answer
        from .metrics import answers_equal,joint_success
        self.safe();state=self.store.save(self.out/(tag+'_binding.pt'));binding=state['semantic_sha256'];start=time.perf_counter();self.phase='generation';self.model.eval();out=self.out/tag;out.mkdir();record_path=out/'results.jsonl'
        # Only fully completed nodes may be reused, and only at identical complete state.
        if previous:
            for src in previous:
                if (src/tag/'COMPLETE.json').exists():
                    receipt=read_json(src/tag/'COMPLETE.json');assert receipt['state_hash']==binding,'deterministic reconstruction mismatch'
                    rs=read_jsonl(src/tag/'results.jsonl');assert len(rs)==len(rows);write_jsonl(record_path,rs);write_json(out/'COMPLETE.json',{**receipt,'reused_from':str(src/tag)});self.cost['reused_generation_episodes']+=len(rs);self.store.restore(state);return rs
        write_json(out/'binding.json',{'time':now(),'state_hash':binding,'rows':len(rows)})
        rs=[]
        try:
            for i,r in enumerate(rows,1):
                self.safe();messages=r['messages'][:2];usage=[]
                def infer(msgs,part,max_tokens):
                    append_jsonl(self.out/'calls_started.jsonl',{'time':now(),'tag':tag,'episode_id':r['episode_id'],'part':part});raw,u=generate_with_usage(self.model,self.tok,msgs,max_tokens);append_jsonl(self.out/'calls_completed.jsonl',{'time':now(),'tag':tag,'episode_id':r['episode_id'],'part':part,**u});usage.append(u)
                    for k in ['inference_calls','input_tokens','output_tokens']:self.cost['generation_'+k]+=u[k]
                    self.memory();return raw
                raw=infer(messages,'tool',int(self.cfg['evaluation']['max_new_tokens_tool']));res=_evaluate_tool_prediction(r,raw,str(DB),str(CAL))
                final_msgs=messages+[{'role':'assistant','content':raw or '{}'},{'role':'user','content':'TOOL RESULT:\n'+res['observation']}]
                answer=infer(final_msgs,'answer',int(self.cfg['evaluation']['max_new_tokens_answer']));ok,pred=parse_final_answer(answer)
                record={'episode_id':r['episode_id'],'skill':r['skill'],'structure':r['structure'],**res,'final_correct':bool(ok and answers_equal(r['expected_final_answer'],pred)),'answer_raw':answer,'predicted_answer':pred,'expected_final_answer':r['expected_final_answer'],'generation_usage':usage};record['joint_success']=joint_success(record)
                append_jsonl(record_path,record);rs.append(record);self.cost['generation_episodes']+=1
                if i%8==0:log(f'{self.seed} {tag} {i}/{len(rows)}');append_jsonl(RUN/'progress.jsonl',{'time':now(),'seed':self.seed,'node':tag,'episodes_completed':i,'episodes_total':len(rows)})
            write_json(out/'COMPLETE.json',{'time':now(),'state_hash':binding,'n':len(rows),'results_sha256':sha256_file(record_path)});return rs
        finally:self.store.restore(state);self.timings[tag+'_seconds']=time.perf_counter()-start

def selected():return [r for r in read_jsonl(DATA/'candidate.jsonl') if r['structure']['case'] in [0,7,14,21]]
def row_diff(a,b):
    assert [r['episode_id'] for r in a]==[r['episode_id'] for r in b]
    diffs={k:[abs(x[k]-y[k]) for x,y in zip(a,b)] for k in SEGMENTS}
    def rank(rs):return [r['episode_id'] for r in sorted(rs,key=lambda r:(-r['call'],r['episode_id']))]
    return {'exact_rows':a==b,'segments':{k:{'max':max(v),'mean':sum(v)/len(v),'changed':sum(x!=0 for x in v)} for k,v in diffs.items()},'call_top4_overlap':len(set(rank(a)[:4])&set(rank(b)[:4])),'n':len(a)}
def diagnostic():
    out=RUN/'engineering_A';out.mkdir();write_json(RUN/'A_STARTED.json',{'time':now(),'seed':SEEDS[0]});e=Engine(SEEDS[0],out);passed=False
    try:
        rows=selected();assert len(rows)==8
        pre=e.nll(rows,'nll_origin8');u=e.update(read_json(DATA/'batches.json')[str(SEEDS[0])][0],'engineering_primary',1);tv=e.store.save(out/'theta_v1.pt');a=e.nll(rows,'nll_primary8')
        e.store.restore(e.origin);e.store.restore(tv);b=e.nll(rows,'nll_restored8');comparison=row_diff(a,b);write_json(out/'saved_state_comparison.json',comparison);assert comparison['exact_rows'],'SAVED THETA_V NLL EXACT RESTORE FAILED'
        e.store.restore(e.origin);v=e.update(read_json(DATA/'batches.json')[str(SEEDS[0])][0],'engineering_control',2);c=e.nll(rows,'nll_control8')
        write_json(out/'rerun_control_comparison.json',{'time':now(),'does_not_replace_primary':True,'NLL':row_diff(a,c),'gradient_exact':u['gradient_sha256']==v['gradient_sha256'],'optimizer_exact':u['optimizer_hash']==v['optimizer_hash'],'LoRA_exact':u['LoRA_hash']==v['LoRA_hash']})
        assert e.cost['NLL_forward_samples']==32 and e.cost['engineering_primary_backward_samples']==8 and e.cost['engineering_control_backward_samples']==8 and not e.cost['generation_episodes'];passed=True
    finally:restoration=e.finish()
    assert passed and restoration['exact'];write_json(RUN/'A_PASS.json',{'time':now(),'passed':True,'theta_v1':tv,'origin':e.origin,'NLL_exact':True,'limits_met':True,'cost':str(out/'cost.json'),'natural_suffix_step1_source':'engineering_primary; control discarded'});log('A PASS: persisted state and NLL EXACT; B permitted')

def run_seed(seed):
    root=RUN/'seeds'/f'seed{seed}';root.mkdir(parents=True);attempt=3 if seed==SEEDS[0] else verify()['old_attempt_inventory'][str(seed)]+1
    out=root/f'attempt{attempt:02}';out.mkdir();write_json(root/'authorized_attempt.json',{'time':now(),'attempt':attempt,'explicit_extra_engineering_repair_attempt':seed==SEEDS[0],'one_shot_no_retry':True});e=Engine(seed,out)
    try:
        allrows=read_jsonl(DATA/'candidate.jsonl')+read_jsonl(DATA/'dev.jsonl');dev=read_jsonl(DATA/'dev.jsonl');batches=read_json(DATA/'batches.json')[str(seed)]
        if seed==SEEDS[0]:
            ar=read_json(RUN/'A_PASS.json');e.store.restore(ar['origin']);e.original=e.capture();e.original_hash=e.FS.digest(e.original);e.origin=e.store.save(out/'bound_A_origin.pt')
        before=e.nll(allrows,'nll_prefix')
        if seed==SEEDS[0]:tv=read_json(RUN/'A_PASS.json')['theta_v1'];e.store.restore(tv)
        else:e.update(batches[0],'predictor_saved_step1',1);tv=e.store.save(out/'theta_v1.pt')
        after=e.nll(allrows,'nll_predictor_virtual1')
        if seed==SEEDS[0]:
            ref=read_json(RUN/'engineering_A/nll_primary8.json')['rows'];ids={r['episode_id'] for r in ref};assert [r for r in after if r['episode_id'] in ids]==ref,'A-to-B saved theta_v predictions changed'
        e.store.restore(e.origin);b={r['episode_id']:r for r in before};a={r['episode_id']:r for r in after}
        pred={x:{'input_tokens':b[x]['input_tokens'],'initial':{k:b[x][k] for k in SEGMENTS},'delta':{k:a[x][k]-b[x][k] for k in SEGMENTS},'risk':{k:max(0.,a[x][k]-b[x][k]) for k in SEGMENTS}} for x in b}
        write_json(out/'prediction.json',{'time':now(),'origin_full_state_hash':e.original_hash,'origin_extended_hash':e.origin['semantic_sha256'],'theta_v1_receipt':tv,'available_before_all_natural_suffix_updates':True,'prediction_horizon':'prefix one-step saved virtual forecast -> natural suffix terminal10','rows':pred})
        baseline=e.generation(dev,'node00');write_json(out/'at_risk.json',{'time':now(),'definition':'fixed per-seed prefix correctness; all probes retained','probe_ids':[r['episode_id'] for r in baseline],'core':[r['episode_id'] for r in baseline if r['tool_correct'] and r['arguments_correct']],'Joint':[r['episode_id'] for r in baseline if r['joint_success']]})
        e.store.restore(tv);append_jsonl(out/'updates.jsonl',{'time':now(),'seed':seed,'step':1,'kind':'natural_suffix','physical_optimizer_update':False,'adopted_persisted_preview_step1':True,'receipt':tv});e.cost['logical_adopted_step1']+=1
        for i,rows in enumerate(batches[1:],2):
            e.update(rows,'natural_suffix',i);e.store.save(out/f'suffix_step{i:02}.pt')
            if i in [5,10]:e.generation(dev,f'node{i:02}')
    finally:receipt=e.finish()
    write_json(root/'COMPLETE.json',{'time':now(),'attempt':str(out.relative_to(ROOT)),'natural_steps':10,'prefix_restored':receipt['exact'],'adopted_step1':True})

def worker():
    signal.signal(signal.SIGTERM,lambda s,f:sys.exit(75));signal.signal(signal.SIGINT,lambda s,f:sys.exit(75));verify();diagnostic()
    assert read_json(RUN/'A_PASS.json')['passed'];write_json(RUN/'B_ENTERED.json',{'time':now(),'calibration_and_formal_freeze_reused':True,'no_partial_old_node_reused':True})
    for seed in SEEDS:run_seed(seed)
    write_json(RUN/'GPU_COMPLETE.json',{'time':now(),'seeds':3,'needs_independent_CPU_final':True})

def supervise():
    LOG.mkdir(parents=True,exist_ok=True);verify();assert not (RUN/'A_STARTED.json').exists(),'one-shot repair already started; NO AUTOMATIC RETRY'
    with (LOG/'repair.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);s=P.inspect({os.getpid()});stamp=time.strftime('%Y%m%d_%H%M%S');write_json(RUN/f'preflight_{stamp}.json',s)
        if not s['safe']:write_json(RUN/f'BLOCKED_{stamp}.json',s);return 75
        (LOG/'supervisor.pid').write_text(str(os.getpid()));wf=LOG/f'worker_{stamp}.log'
        with wf.open('x',buffering=1) as f:
            child=subprocess.Popen([sys.executable,'-B','-m',MOD,'worker'],cwd=ROOT,env=os.environ,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);(LOG/'worker.pid').write_text(str(child.pid));write_json(RUN/'active.json',{'time':now(),'supervisor_pid':os.getpid(),'worker_pid':child.pid,'worker_log':str(wf.relative_to(ROOT))});log('START persisted repair worker '+str(child.pid))
            while child.poll() is None:
                try:child.wait(timeout=3);break
                except subprocess.TimeoutExpired:pass
                try:
                    s=P.inspect({os.getpid(),child.pid});append_jsonl(LOG/'guard.jsonl',s)
                    if s['safe']:continue
                    reason=s
                except Exception as e:reason={'inspection_error':repr(e)}
                if not (LOG/'STOP').exists():write_json(LOG/'STOP',{'time':now(),'reason':reason})
                log('SAFETY STOP '+json.dumps(reason));os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=45)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                break
            rc=child.wait();write_json(RUN/'supervisor_end.json',{'time':now(),'rc':rc});log('END persisted repair rc='+str(rc));return rc

def analyze():
    independent_cpu_checks();verify();mapping=read_json(DATA/'pair_mapping.json');full=[];primary=[];secondary=collections.defaultdict(list);outcomes={};receipts=[]
    for seed in SEEDS:
        root=RUN/'seeds'/f'seed{seed}';done=read_json(root/'COMPLETE.json');out=ROOT/done['attempt'];prediction=read_json(out/'prediction.json');pred=prediction['rows'];baseline={r['episode_id']:r for r in read_jsonl(out/'node00/results.jsonl')};receipt=read_json(out/'restoration.json');assert receipt['exact'];receipts.append(receipt)
        trace=read_jsonl(out/'updates.jsonl');assert [u['step'] for u in trace if u['kind']=='natural_suffix']==list(range(1,11));assert prediction['time']<=min(u['time'] for u in trace if u['kind']=='natural_suffix')
        outcomes[str(seed)]={}
        for node in [0,5,10]:
            rs=read_jsonl(out/f'node{node:02}/results.jsonl');assert len(rs)==48
            outcomes[str(seed)][str(node)]={k:{m:sum(bool(r[m]) for r in rs if r['skill']==k) for m in ['tool_correct','arguments_correct','execution_success','final_correct','joint_success']} for k in SKILLS}
            if node==0:continue
            for r in rs:
                a=baseline[r['episode_id']];p=pred[r['episode_id']];candidate=pred[mapping[r['episode_id']]];core0=a['tool_correct'] and a['arguments_correct'];core1=r['tool_correct'] and r['arguments_correct']
                item={'seed':seed,'episode_id':r['episode_id'],'skill':r['skill'],'node':node,'baseline_core_correct':bool(core0),'after_core_correct':bool(core1),'lost':bool(core0 and not core1),'baseline_joint':a['joint_success'],'after_joint':r['joint_success'],'risk_call':p['risk']['call'],'initial_call':p['initial']['call'],'input_tokens':p['input_tokens'],'candidate_mapped_risk':candidate['risk']['call'],'before_tool':a['predicted_tool'],'after_tool':r['predicted_tool'],'before_args':a['predicted_arguments'],'after_args':r['predicted_arguments']};full.append(item)
                if node==10 and core0:primary.append(item)
                if node==10:
                    for label,metric,seg in [('tool_name','tool_correct','tool_name'),('args','arguments_correct','args'),('final','final_correct','final'),('Joint','joint_success','all')]:
                        if a[metric]:secondary[label].append({'seed':seed,'episode_id':r['episode_id'],'lost':bool(not r[metric]),'risk_call':p['risk'][seg],'initial_call':p['initial'][seg],'input_tokens':p['input_tokens']})
    metrics={k:metric_table(primary,k) for k in ['risk_call','initial_call','input_tokens','candidate_mapped_risk']};means={k:macro_auc(primary,k) for k in metrics};ci=bootstrap(primary)
    enough=[s for s in SEEDS if metrics['risk_call'][str(s)]['events_weight']>=5 and metrics['risk_call'][str(s)]['n_weight']-metrics['risk_call'][str(s)]['events_weight']>=5]
    # Statistical comparison uses exactly the same eligible seeds for all score variants.
    eligible=[r for r in primary if r['seed'] in enough];gate_means={k:macro_auc(eligible,k) for k in metrics};gate_ci=bootstrap(eligible)
    def lower_positive(k):v=gate_ci['intervals'][k];return v is not None and v[0]>0
    gates={'engineering_and_state':all(x['exact'] and x['prefix_file_unchanged'] for x in receipts),'two_seeds_each_5_events_5_non_events':len(enough)>=2,'AUROC_065_and_beats_baselines':None not in [gate_means['risk_call'],gate_means['initial_call'],gate_means['input_tokens']] and gate_means['risk_call']>=.65 and gate_means['risk_call']>max(gate_means['initial_call'],gate_means['input_tokens']),'cluster_bootstrap_difference_lower95_above0':gate_ci['valid_replicates']>=800 and lower_positive('MIR_minus_initial_NLL') and lower_positive('MIR_minus_TokenCost')}
    decision='PREDICTION_SIGNAL_ONLY_no_pilot_authorized' if all(gates.values()) else ('UNIDENTIFIABLE_no_expansion' if len(enough)<2 else 'NO_GO_current_prediction_configuration')
    costs=[]
    assert read_json(RUN/'A_PASS.json')['passed']
    assert read_json(RUN/'GPU_COMPLETE.json')['seeds']==3
    assert read_json(RUN/'supervisor_end.json')['rc']==0
    for p in sorted(RUN.glob('*/seed*/attempt*/cost.json')):costs.append({'path':str(p.relative_to(ROOT)),**read_json(p)})
    costs.append({'path':str((RUN/'engineering_A/cost.json').relative_to(ROOT)),**read_json(RUN/'engineering_A/cost.json')})
    totals=collections.Counter()
    for c in costs:
        for k,v in c['counts'].items():
            if k.startswith('peak_'):totals[k]=max(totals[k],v)
            else:totals[k]+=v
    guards=read_jsonl(LOG/'guard.jsonl');assert all(g['safe'] for g in guards)
    result={'time':now(),'decision':decision,'gates':gates,'primary_observation_unit':'same dev probe own pre-trajectory one-step delta_call -> terminal10 core(tool AND args) loss; not replay generalization','primary_total_at_risk':len(primary),'primary_core_losses':sum(r['lost'] for r in primary),'seeds_with_minimum_events':enough,'primary_per_seed_metrics':metrics,'primary_macro_AUROC_all_defined_seeds':means,'gate_macro_AUROC_sufficient_event_seeds':gate_means,'bootstrap_all_at_risk':ci,'bootstrap_gate_eligible_seeds':gate_ci,'candidate_mapping_is_separate_secondary_not_memory_selection_efficacy':True,'secondary_components':{k:metric_table(v) for k,v in secondary.items()},'outcomes_out_of_24_each_skill':outcomes,'records':full,'state_restoration_receipts':receipts,'cost_totals_including_all_attempts':dict(totals),'cost_attempts':costs,'safe_guard_checks':len(guards),'observed_GPU_memory_peak_MiB':max(g['observed_GPU_memory_MiB'] for g in guards) if guards else None,'formal_optimizer_steps':0,'normal_temporary_optimizer_steps':31,'limits':'exploratory post-P12 no-replay natural suffix, not P12 reproduction; repeated midpoint records not pooled into primary; three seed clusters weak external evidence; no extra experiment or formal pilot'}
    result['operational_amendment']=str(AMEND.relative_to(ROOT));result['legacy_costs_separate']=[{'path':str(p.relative_to(ROOT)),**read_json(p)} for p in sorted(P.RUN.glob('*/seed*/attempt*/cost.json'))];result['adopted_preview_updates_not_double_counted']=True
    write_json(RUN/'summary.json',result);write_json(RUN/'independent_acceptance.json',{'time':now(),'passed':True,'frozen_input_hashes_verified':True,'complete_seeds':3,'all_guard_checks_safe':True,'complete_restore_checks':len(receipts),'primary_records_once_per_seed_probe':True,'masks_CPU_checks':read_json(DATA/'cpu_acceptance.json')['mask_partition_checks'],'prediction_file_precedes_all_natural_updates':True,'terminal_nodes':3,'no_formal_training':True})
    report='# P13 Phase0-B 独立实验报告\n\n北京时间 '+result['time']+'\n\n## 客观判断\n一次延长的诊断不是方法创新。修复了观测单位和时序：主分析用同一探针的前缀一步虚拟ΔNLL预测未来10步终点工具+参数退化；候选一一结构配对映射单列，并非replay选择效果。完整自然无回放suffix不复现P12带回放过程。\n\n## 结果与冻结gate\n'+json.dumps({k:result[k] for k in ['decision','gates','primary_total_at_risk','primary_core_losses','seeds_with_minimum_events','primary_per_seed_metrics','gate_macro_AUROC_sufficient_event_seeds','bootstrap_gate_eligible_seeds','outcomes_out_of_24_each_skill']},ensure_ascii=False,indent=2)+'\n\n## 成本和审计\n'+json.dumps({k:result[k] for k in ['cost_totals_including_all_attempts','safe_guard_checks','observed_GPU_memory_peak_MiB','formal_optimizer_steps']},ensure_ascii=False,indent=2)+'\n\nLoRA/optimizer/scaler/RNG/module modes均精确恢复，原前缀文件hash不变。显存记录覆盖所有段且不调用旧评测器的峰值重置；reserved可能反映WSL虚拟/共享分配而非独占物理显存。所有成本含校准和MIR虚拟预测，为额外诊断训练计算，不能称纯评测。\n\n主指标未越门槛不以次组件/中点/候选映射救结论；事件不足为UNIDENTIFIABLE，不扩大规模。即便gate过，也不自动启动正式pilot。已有SQL/GSS/文献结论直接复用，无新提示矩阵。\n'
    (ROOT/'EXT_REPORT_20261119_p13_phase0b_persist_independent_ZH.md').write_text(report,encoding='utf-8')
    (ROOT/'EXT_HANDOVER_20261119_p13_phase0b_persist_ZH.md').write_text('# P13 Phase0B交接\n\n'+now()+' 北京时间\n\n'+decision+'\n\n结果runs_ext_p13_phase0b_persist_20261119/summary.json，审计independent_acceptance.json；协议P13_PHASE0B_PREREG_20261118_ZH.md；独立报告EXT_REPORT_20261119_p13_phase0b_persist_independent_ZH.md；成本/恢复见各calibration、seeds/seed*/attempt*/cost.json和restoration.json。完成标记COMPLETE.json，监督器supervisor_end.json。不push，不启动正式MIR/DG-MIR训练，不扩大本轮。\n',encoding='utf-8')
    write_json(RUN/'COMPLETE.json',{'time':now(),'complete':True,'decision':decision,'seeds':3,'formal_updates':0});log('PHASE0B COMPLETE '+decision);return result

def independent_cpu_checks():
    # No model construction, CUDA tensors or project worker may run here.
    import torch
    from . import p7_fullstate_v2_20261115 as FS
    assert read_json(RUN/'supervisor_end.json')['rc']==0
    active=read_json(RUN/'active.json')
    for pid in [active['supervisor_pid'],active['worker_pid']]:assert not Path('/proc',str(pid)).exists(),'GPU session still running'
    a=RUN/'engineering_A';assert read_json(a/'nll_primary8.json')['rows']==read_json(a/'nll_restored8.json')['rows']
    count=read_json(a/'cost.json')['counts'];assert count['NLL_forward_samples']==32 and count['engineering_primary_optimizer_steps']==1 and count['engineering_control_optimizer_steps']==1 and count.get('generation_episodes',0)==0
    receipts=list(RUN.rglob('*.receipt.json'));base_seen=set()
    for p in receipts:
        r=read_json(p);assert sha256_file(r['path'])==r['file_sha256'];payload=torch.load(r['path'],map_location='cpu',weights_only=False);assert FS.digest({'base_semantic_sha256':payload['base_semantic_sha256'],'train':payload['train'],'attrs':payload['attrs'],'backend':payload['backend']})==r['semantic_sha256']
        base=r['base_reference'];assert sha256_file(base['path'])==base['file_sha256']
        if base['path'] not in base_seen:assert FS.digest(torch.load(base['path'],map_location='cpu',weights_only=False))==base['semantic_sha256'];base_seen.add(base['path'])
    updates=0
    for seed in SEEDS:
        root=RUN/'seeds'/f'seed{seed}';out=ROOT/read_json(root/'COMPLETE.json')['attempt'];assert read_json(out/'extended_restoration.json')['exact']
        u=read_jsonl(out/'updates.jsonl');natural=[r for r in u if r['kind']=='natural_suffix'];assert [r['step'] for r in natural]==list(range(1,11))
        pred=read_json(out/'prediction.json');assert natural[0]['receipt']==pred['theta_v1_receipt'];assert natural[0]['physical_optimizer_update'] is False
        assert pred['time']<=natural[0]['time'];assert len(pred['rows'])==96
        for node in ['node00','node05','node10']:
            rr=read_json(out/node/'COMPLETE.json');rs=read_jsonl(out/node/'results.jsonl');assert len(rs)==48 and rr['results_sha256']==sha256_file(out/node/'results.jsonl')
        c=read_json(out/'cost.json')['counts'];updates+=sum(v for k,v in c.items() if k.endswith('_optimizer_steps'));assert c['NLL_forward_samples']==192 and c['generation_episodes']==144
    assert updates==29
    write_json(RUN/'persistence_independent_CPU_checks.json',{'time':now(),'passed':True,'exact_saved_NLL':True,'receipt_count':len(receipts),'base_blob_count':len(base_seen),'stage_A_physical_steps':2,'stage_B_physical_steps':29,'logical_suffix_steps':30,'all_extended_restorations_exact':True,'no_GPU_model_loaded':True})

if __name__=='__main__':
    time.tzset();ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['build','preflight','supervise','worker','final']);mode=ap.parse_args().mode
    try:
        if mode=='preflight':
            s=P.inspect({os.getpid()});print(json.dumps(s,ensure_ascii=False));sys.exit(0 if s['safe'] else 75)
        result={'build':build,'supervise':supervise,'worker':worker,'final':analyze}[mode]();sys.exit(result if isinstance(result,int) else 0)
    except BaseException as exc:
        if isinstance(exc,SystemExit):raise
        RUN.mkdir(exist_ok=True);write_json(RUN/f'FAILED_{time.strftime("%Y%m%d_%H%M%S")}.json',{'time':now(),'error':repr(exc),'no_further_attempt_authorized':True});traceback.print_exc();sys.exit(1)
