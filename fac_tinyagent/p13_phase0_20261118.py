"""P13 only: fixed two-window virtual AdamW intervention, independent dev Joint gate."""
from __future__ import annotations
import os
os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',HF_HUB_OFFLINE='1',TOKENIZERS_PARALLELISM='false',TZ='Asia/Shanghai')
import argparse,collections,copy,csv,fcntl,hashlib,json,math,re,signal,sqlite3,subprocess,sys,time,traceback
from pathlib import Path
from .utils import read_json,read_jsonl,write_json,write_jsonl,append_jsonl,sha256_file,canonical_json
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data_ext_p13_phase0'; RUN=ROOT/'runs_ext_p13_phase0'; LOG=RUN/'logs'
PREREG=ROOT/'P13_PHASE0_PREREG_20261118_ZH.md'; SEED=20261108; MODULE='fac_tinyagent.p13_phase0_20261118'
CAL=DATA/'fixtures/calendar.json'; DB=DATA/'fixtures/counterexample.sqlite'; SKILLS=['cal.count_date','cal.list_locations']
def log(t):print(time.strftime('%F %T %z'),t,flush=True)
def audit_history():
    """Read old outputs only to verify claimed errors; never feed blind cases to selection."""
    result={}; losses=[]
    for arm in ['t0','v1','floor_random','floor_rules']:
        counts=collections.defaultdict(collections.Counter)
        for seed in [20261108,20261109,20261110]:
            base=ROOT/'runs_ext_p12_eaar_v2/evaluation'
            rs=read_jsonl(base/f'A_seed{seed}_{arm}/results.jsonl')
            for r in rs:
                c=counts[r['skill']];c['n']+=1
                for k in ['tool_correct','arguments_correct','execution_success','final_correct','joint_success']:c[k]+=int(r[k])
            if arm=='floor_random':
                old={r['episode_id']:r for r in read_jsonl(base/f'A_seed{seed}_t0/results.jsonl')}
                b=read_jsonl(base/f'A_seed{seed}_floor_rules/results.jsonl')
                assert [r['joint_success'] for r in rs]==[r['joint_success'] for r in b]
                for r in rs:
                    if r['skill']=='cal.count_date' and old[r['episode_id']]['joint_success'] and not r['joint_success']:
                        losses.append({'seed':seed,'episode_id':r['episode_id'],'tool':r['predicted_tool'],'arguments':r['predicted_arguments'],'gold_tool':old[r['episode_id']]['predicted_tool'],'gold_arguments':old[r['episode_id']]['predicted_arguments']})
        result[arm]=dict(counts)
    out={'counts':result,'count_date_losses':losses,'all_five_day_as_month':len(losses)==5 and all(x['tool']=='calendar_count' and x['arguments']=={'month':x['gold_arguments']['date']} for x in losses),'AB_joint_identical':True,'note':'P12 report line60 mistakenly says five seeds; raw results contain three seeds. filter T0 Joint=0 is an existing gap, not demonstrated forgetting.'}
    write_json(RUN/'history_audit.json',out);return out

def sql_fixture():
    DB.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(DB) as c:
        c.execute('CREATE TABLE p13_marks(id INTEGER PRIMARY KEY,name TEXT,score REAL)')
        c.executemany('INSERT INTO p13_marks VALUES (?,?,?)',[(1,'P13_A',95),(2,'P13_B',80),(3,'P13_C',40),(4,'P13_D',10)])
        tests=[]
        for condition in ['score > 80','score > 99','score >= 80','score < 40']:
            gold=f'SELECT name FROM p13_marks WHERE {condition} ORDER BY score DESC, id ASC LIMIT 3'
            omit='SELECT name FROM p13_marks ORDER BY score DESC, id ASC LIMIT 3'
            equivalent=gold.replace('SELECT name','SELECT p13_marks.name')
            g=c.execute(gold).fetchall();b=c.execute(omit).fetchall();e=c.execute(equivalent).fetchall()
            assert g!=b and g==e
            tests.append({'gold_sql':gold,'gold_result':g,'omitted_where_sql':omit,'omitted_result':b,'omitted_strict':omit==gold,'omitted_semantic':g==b,'equivalent_sql':equivalent,'equivalent_strict':equivalent==gold,'equivalent_semantic':g==e})
    write_json(DATA/'sql_unit_acceptance.json',{'passed':True,'tests':tests,'metrics':['exact_SQL_parameter','execution_semantics'],'no_historical_blind_change':True})

def build():
    assert not DATA.exists(),'no overwrite P13 data'
    DATA.mkdir();LOG.mkdir(parents=True,exist_ok=True);sql_fixture();audit_history()
    from .p11_eaar_v1_20261118 import row,CAL_COUNT_DEV,CAL_LIST_DEV
    events=[];candidates=[];probes=[]
    # 40 distinct dates; alternate skill so candidates first8 have four per skill.
    for i in range(40):
        d=f'2031-{1+i//28:02d}-{1+i%28:02d}';n=1+(i//2)%4
        for j in range(n):
            events.append({'id':f'P13E{i:03}_{j}','title':f'P13 planning {i}_{j}','date':d,'start':f'{9+2*j:02d}:00','end':f'{10+2*j:02d}:00','location':f'P13Room_{i:03}_{[2,0,2,1][j]}','attendees':[f'P13Visitor_{i:03}']})
    write_json(CAL,{'events':events})
    for i in range(40):
        d=f'2031-{1+i//28:02d}-{1+i%28:02d}';k=i%2;skill=SKILLS[k];split='candidate' if i<16 else 'dev';j=i//2
        template=(CAL_COUNT_DEV if k==0 else CAL_LIST_DEV)[j%4]
        spec={'kind':'length'} if k==0 else {'kind':'pluck','field':'location','unique':True}
        r=row('calendar',skill,'train',i,template.format(d=d),'calendar_list',{'date':d},{},spec,cal=str(CAL))
        r.update(episode_id=f'p13-{split}-{skill}-{i:03}',split=split,evaluation_only=split=='dev',selection_allowed=split=='candidate')
        (candidates if i<16 else probes).append(r)
    # Entity and prompt separation from all historical task data incl frozen blind entities; no score use.
    historical_dates=set(); historical_prompts=set()
    for folder in ['data_phase2','data_ext_p11_eaar_v1','data_ext_p12_eaar_v2']:
        for p in (ROOT/folder).rglob('*.jsonl'):
            for r in read_jsonl(p):
                historical_prompts.add(r.get('prompt',''));a=r.get('expected_arguments',{})
                if 'date' in a:historical_dates.add(a['date'])
    assert not {r['expected_arguments']['date'] for r in candidates+probes}&historical_dates
    assert not {r['prompt'] for r in candidates+probes}&historical_prompts
    assert not {r['expected_arguments']['date'] for r in candidates}&{r['expected_arguments']['date'] for r in probes}
    write_jsonl(DATA/'candidates.jsonl',candidates);write_jsonl(DATA/'dev.jsonl',probes)
    prefix=ROOT/f'runs_ext_e4/prefixes/A_seed{SEED}'
    man=read_json(prefix/'manifest.json');new=read_jsonl(ROOT/'data_phase2/calendar/train.jsonl');m=man['metadata']['midpoint'];assert m==80
    batches=[[new[j] for j in man['metadata']['order'][m+8*i:m+8*(i+1)]] for i in range(2)]
    write_json(DATA/'batches.json',batches)
    refs=[PREREG,Path(__file__),prefix/'manifest.json',prefix/'training_state.pt',ROOT/'data_phase2/calendar/train.jsonl',ROOT/'fac_tinyagent/p7_fullstate_v2_20261115.py',ROOT/'fac_tinyagent/p11_queue_20261118.py']
    files=[p for p in DATA.rglob('*') if p.is_file()]
    write_json(DATA/'manifest.json',{'time':time.strftime('%F %T %z'),'seed':SEED,'pre_registered_before_new_model_scores':True,'hashes':{str(p.relative_to(ROOT)):sha256_file(p) for p in files+refs},'batch_episode_ids':[[r['episode_id'] for r in b] for b in batches]})
    write_json(DATA/'cpu_acceptance.json',{'passed':True,'candidates':16,'dev_probes':24,'batches':2,'entities_disjoint':True,'SQL_cases':4,'no_formal_training':True});log('CPU FREEZE COMPLETE')

def verify():
    for p,h in read_json(DATA/'manifest.json')['hashes'].items():assert sha256_file(ROOT/p)==h,'changed '+p

def inspect(allowed):
    from .p11_queue_20261118 import inspect as inherited
    s=inherited(allowed)
    # General Apex name also protected, not only r5apex.
    ps="[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); @(Get-Process -ErrorAction Stop | Where-Object {$_.ProcessName -match '(?i)r5apex|^Apex$'}).Count"
    count=int(subprocess.check_output(['/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','-NoProfile','-NonInteractive','-Command',ps],timeout=20).decode('utf-8-sig').strip())
    s['all_apex_process_count']=count;s['safe']=s['safe'] and count==0
    return s

def auc(items,key):
    a=[x[key] for x in items if x['lost']];b=[x[key] for x in items if not x['lost']]
    return None if not a or not b else sum((x>y)+.5*(x==y) for x in a for y in b)/(len(a)*len(b))
def analyze(stages,cost,restoration):
    candidates=read_jsonl(DATA/'candidates.jsonl');probes=read_jsonl(DATA/'dev.jsonl');rows={r['episode_id']:r for r in candidates+probes}
    pairs=[];ranking=[];all_transitions=[]
    for i in [1,2]:
        old=stages[i-1];new=stages[i];o={r['episode_id']:r for r in old['nll']};n={r['episode_id']:r for r in new['nll']}
        def score(e):return max(0,n[e]['nll']-o[e]['nll'])
        ids=[r['episode_id'] for r in candidates]
        top=lambda fn:set(sorted(ids,key=lambda e:(-fn(e),e))[:4])
        topI=top(score);topL=top(lambda e:o[e]['nll']);topC=top(lambda e:o[e]['input_tokens'])
        nondegenerate=sum(score(e)>0 for e in ids)>=4 and len({round(score(e),6) for e in ids})>=4 and topI!=topL and topI!=topC
        ranking.append({'batch':i,'nondegenerate':nondegenerate,'positive':sum(score(e)>0 for e in ids),'unique_rounded':len({round(score(e),6) for e in ids}),'top4_MIR':sorted(topI),'top4_NLL':sorted(topL),'top4_cost':sorted(topC),'scores':[{'episode_id':e,'delta_nll':n[e]['nll']-o[e]['nll'],'MIR':score(e),'old_nll':o[e]['nll'],'cost':o[e]['input_tokens']} for e in ids]})
        go={r['episode_id']:r for r in old['generation']};gn={r['episode_id']:r for r in new['generation']}
        for e,a in go.items():
            b=gn[e];item={'batch':i,'episode_id':e,'skill':rows[e]['skill'],'before_joint':a['joint_success'],'after_joint':b['joint_success'],'lost':bool(a['joint_success'] and not b['joint_success']),'gained':bool(not a['joint_success'] and b['joint_success']),'MIR':score(e),'old_nll':o[e]['nll'],'cost':o[e]['input_tokens'],'delta_nll':n[e]['nll']-o[e]['nll'],'before_tool':a['predicted_tool'],'after_tool':b['predicted_tool'],'before_args':a['predicted_arguments'],'after_args':b['predicted_arguments']}
            all_transitions.append(item)
            if a['joint_success']:pairs.append(item)
    lost=sum(x['lost'] for x in pairs);aucs={k:auc(pairs,k) for k in ['MIR','old_nll','cost']}
    ranked=sorted(pairs,key=lambda x:(-x['MIR'],x['batch'],x['episode_id']));q=max(1,math.ceil(len(ranked)/4));head=ranked[:q];rest=ranked[q:]
    headrate=sum(x['lost'] for x in head)/len(head) if head else None;restrate=sum(x['lost'] for x in rest)/len(rest) if rest else None
    eng=restoration['exact'] and read_json(DATA/'sql_unit_acceptance.json')['passed']
    signal_ok=lost>=3 and aucs['MIR'] is not None and aucs['MIR']>=.65 and all(aucs[k] is not None and aucs['MIR']>aucs[k] for k in ['old_nll','cost']) and headrate>restrate
    gates={'engineering':eng,'candidate_ranking':any(x['nondegenerate'] for x in ranking),'at_least_3_joint_losses':lost>=3,'predictive_signal':signal_ok}
    decision='GO_single_paired_pilot_proposal_only' if all(gates.values()) else ('UNIDENTIFIABLE_no_expansion' if lost<3 else 'NO_GO_current_configuration_only')
    result={'time':time.strftime('%F %T %z'),'gates':gates,'decision':decision,'correct_to_wrong':lost,'wrong_to_correct':sum(x['gained'] for x in all_transitions),'eligible_pairs':len(pairs),'paired_transitions':48,'unique_dev_probes':24,'AUROC':aucs,'top_quartile_loss_rate':headrate,'remaining_loss_rate':restrate,'candidate_ranking':ranking,'transitions':all_transitions,'stage_joint':[{k:sum(r['joint_success'] for r in s['generation'] if k in r['episode_id']) for k in SKILLS} for s in stages],'cost':cost,'restoration':restoration,'not_independent_repeated_probes':True,'formal_training_steps':0,'virtual_updates':2}
    write_json(RUN/'summary.json',result)
    history=read_json(RUN/'history_audit.json')
    text='# P13 Phase0 结果\n\n北京时间 '+result['time']+'\n\n'
    text+='## 客观判断\nMIR值得筛查，但DG-MIR三模块不能直接等同创新或保证论文目标；本轮不做正式三臂五种子训练。Calendar提示诊断不影响当前决策，删除；filter原T0严格Joint为0，不能称遗忘。\n\n'
    text+='## 证据复核\n五条日期退化是否全为日期当month：'+str(history['all_five_day_as_month'])+'。SQL逐臂原始核齐见history_audit.json（filter专指db.filter_cmp_top，不是全部SQL）。原报告“五种子”是笔误，实际三种子。\n\n'
    text+='## 新实验\n'+json.dumps({k:result[k] for k in ['gates','decision','stage_joint','correct_to_wrong','wrong_to_correct','eligible_pairs','AUROC','top_quartile_loss_rate','remaining_loss_rate','cost','restoration']},ensure_ascii=False,indent=2)+'\n\n'
    text+='若事件不足，结论是当前两批局部更新不可识别，不是MIR无效；不扩批救结论。ΔNLL以gold工具观测轨迹计算，Joint为实际执行两回合生成，两者不可混称。前缀到后缀两步是不含回放的新流局部反事实，不解释完整P12的历史因果。\n\nSQL新反例四例全部阻止漏WHERE碰巧同结果，且合法等价SQL语义通过/严格不通过；未改原盲卷。\n\n文献纠偏、规模及预注册门槛见P13_PHASE0_PREREG_20261118_ZH.md。梯度余弦只作可计算性诊断，未增加诊断门控或多样性采样。所有成本均为额外诊断，不藏入23正式更新。\n'
    (ROOT/'EXT_REPORT_20261118_p13_phase0_ZH.md').write_text(text,encoding='utf-8')
    (ROOT/'EXT_HANDOVER_20261118_p13_phase0_ZH.md').write_text('# P13 Phase0交接\n\n'+result['time']+' 北京时间\n\n结论：'+decision+'\n\n协议：P13_PHASE0_PREREG_20261118_ZH.md；报告：EXT_REPORT_20261118_p13_phase0_ZH.md；完整审计：runs_ext_p13_phase0/summary.json、history_audit.json、cost.json、restoration.json；输入：data_ext_p13_phase0/。\n不自动开始正式训练，不推送，不清STOP。监督日志logs/supervisor.log、logs/worker.log、logs/guard.jsonl；完成标记COMPLETE.json与supervisor_end.json。\n',encoding='utf-8')
    return result

def worker():
    signal.signal(signal.SIGTERM,lambda s,f:sys.exit(75));verify()
    import torch
    from bitsandbytes.optim import PagedAdamW8bit
    from . import p7_fullstate_v2_20261115 as FS
    from .replay_train import load_prefix,_training_state_hash
    from .sft.train import load_tokenizer,load_base_model,_attach_adapter
    from .sft.dataset import tokenize_episode,DataCollator
    from .sft.evaluate import evaluate_family,free_model
    from .replay_study import config_for
    from .e4_run import start_adapter
    cfg=config_for('A',SEED,batch_size=1);cfg['evaluation']['batch_size']=1
    prefix=ROOT/f'runs_ext_e4/prefixes/A_seed{SEED}';man=read_json(prefix/'manifest.json')
    started=time.perf_counter();cost=collections.Counter();timings={};phase=['load']
    tok=load_tokenizer(cfg);model,dtype=load_base_model(cfg);model=_attach_adapter(model,cfg,str(start_adapter(SEED)))
    params=[p for p in model.parameters() if p.requires_grad];opt=PagedAdamW8bit(params,lr=1e-4);scaler=torch.amp.GradScaler('cuda',enabled=dtype==torch.float16)
    load_prefix(prefix,model,opt,scaler,man['metadata']);assert _training_state_hash(model)==man['parameter_hash']
    original=FS.capture(model,opt,scaler);original_digest=FS.digest(original);torch.cuda.reset_peak_memory_stats()
    handle=model.register_forward_pre_hook(lambda m,a:cost.update({phase[0]+'_actual_model_forward_calls':1}))
    candidates=read_jsonl(DATA/'candidates.jsonl');probes=read_jsonl(DATA/'dev.jsonl');allrows=candidates+probes;batches=read_json(DATA/'batches.json');collator=DataCollator(tok)
    cache={}
    def ft(r):
        e=r['episode_id']
        if e not in cache:cache[e]=tokenize_episode(r,tok,1024)
        assert len(cache[e]['input_ids'])<1024
        return cache[e]
    def batch(r):return {k:v.to('cuda') for k,v in collator([ft(r)]).items()}
    def safe():
        if (LOG/'STOP').exists():raise RuntimeError('sticky STOP')
    def measure(i):
        safe();state=FS.capture(model,opt,scaler);t=time.perf_counter();out=RUN/f'stage{i}';out.mkdir();model.eval();phase[0]='nll';nll=[]
        with torch.no_grad():
            for r in allrows:
                safe()
                with torch.autocast(device_type='cuda',dtype=dtype):v=float(model(**batch(r)).loss)
                assert math.isfinite(v)
                nll.append({'episode_id':r['episode_id'],'nll':v,'input_tokens':len(ft(r)['input_ids'])});cost['teacher_forced_NLL_forwards']+=1;cost['teacher_forced_input_tokens']+=len(ft(r)['input_ids'])
        write_json(out/'nll.json',nll);timings[f'stage{i}_nll_seconds']=time.perf_counter()-t;t=time.perf_counter();phase[0]='generation'
        evaluate_family(model,tok,probes,cfg,{'name':f'P13_DEV_{i}','index':0,'family':'calendar'},out/'generation',str(DB),str(CAL))
        rs=read_jsonl(out/'generation/results.jsonl');assert len(rs)==24
        for r in rs:
            cost['generation_episodes']+=1
            for k in ['inference_calls','input_tokens','output_tokens']:cost['generation_'+k]+=r[k]
        timings[f'stage{i}_generation_seconds']=time.perf_counter()-t
        FS.restore(state,model,opt,scaler);log(f'STAGE {i} measured Joint '+str(sum(r['joint_success'] for r in rs)))
        return {'nll':nll,'generation':rs}
    stages=[];restoration=None
    try:
        # Same evaluator verifies gold tool executor/arguments before any inference.
        from .sft.evaluate import _evaluate_tool_prediction
        for r in allrows:
            g=_evaluate_tool_prediction(r,canonical_json({'tool':r['expected_tool'],'arguments':r['expected_arguments']}),str(DB),str(CAL));assert all(g[k] for k in ['tool_correct','arguments_correct','execution_success'])
        t=time.perf_counter();phase[0]='diversity';model.eval();gradients=[]
        for r in candidates[:8]:
            safe();model.zero_grad(set_to_none=True)
            with torch.autocast(device_type='cuda',dtype=dtype):loss=model(**batch(r)).loss
            loss.backward();cost['diversity_backward']+=1;cost['diversity_input_tokens']+=len(ft(r)['input_ids'])
            gradients.append(torch.cat([p.grad.detach().float().cpu().reshape(-1) if p.grad is not None else torch.zeros(p.numel()) for p in params]))
        model.zero_grad(set_to_none=True);g=torch.stack(gradients);norms=g.norm(dim=1);cos=(g@g.T)/(norms[:,None]*norms[None,:]).clamp_min(1e-30)
        write_json(RUN/'gradient_diversity.json',{'candidate_ids':[r['episode_id'] for r in candidates[:8]],'full_LoRA_gradient_dimension':g.shape[1],'gradient_norms':norms.tolist(),'cosine':cos.tolist(),'no_projection':True,'selection_effect_tested':False});del gradients,g
        timings['diversity_seconds']=time.perf_counter()-t;FS.restore(original,model,opt,scaler)
        stages.append(measure(0))
        for i,rs in enumerate(batches,1):
            t=time.perf_counter();phase[0]='virtual_update';model.train();opt.zero_grad(set_to_none=True)
            for r in rs:
                safe()
                with torch.autocast(device_type='cuda',dtype=dtype):loss=model(**batch(r)).loss
                assert torch.isfinite(loss);scaler.scale(loss/8).backward();cost['virtual_backward']+=1;cost['virtual_input_tokens']+=len(ft(r)['input_ids'])
            scaler.step(opt);scaler.update();opt.zero_grad(set_to_none=True);cost['virtual_optimizer_steps']+=1;timings[f'virtual_update{i}_seconds']=time.perf_counter()-t
            append_jsonl(RUN/'progress.jsonl',{'stage':i,'event':'virtual_step_done','time':time.strftime('%F %T %z'),'trainable_hash':_training_state_hash(model)})
            stages.append(measure(i))
    finally:
        opt.zero_grad(set_to_none=True);FS.restore(original,model,opt,scaler);after=FS.capture(model,opt,scaler);after_digest=FS.digest(after)
        restoration={'before':original_digest,'after':after_digest,'exact':original_digest==after_digest,'LoRA_before':FS.digest(original['parameters']),'LoRA_after':FS.digest(after['parameters']),'optimizer_before':FS.digest(original['optimizer']),'optimizer_after':FS.digest(after['optimizer']),'prefix_file_unchanged':sha256_file(prefix/'training_state.pt')==read_json(DATA/'manifest.json')['hashes'][str((prefix/'training_state.pt').relative_to(ROOT))]}
        write_json(RUN/'restoration.json',restoration);cost['peak_allocated_GPU_bytes']=torch.cuda.max_memory_allocated();cost['peak_reserved_GPU_bytes']=torch.cuda.max_memory_reserved();cost['elapsed_seconds']=time.perf_counter()-started
        write_json(RUN/'cost.json',{'counts':dict(cost),'timings_seconds':timings,'all_cost_is_extra_diagnostic':True,'production_optimizer_steps':0});handle.remove()
    assert restoration['exact'];verify();result=analyze(stages,read_json(RUN/'cost.json'),restoration)
    write_json(RUN/'COMPLETE.json',{'complete':True,'time':time.strftime('%F %T %z'),'decision':result['decision'],'production_steps':0,'virtual_steps':2,'new_adapter_saved':False});log('P13 COMPLETE '+result['decision']);free_model(model)

def supervise():
    LOG.mkdir(parents=True,exist_ok=True);verify();assert not (RUN/'COMPLETE.json').exists()
    with (LOG/'p13.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);s=inspect({os.getpid()});write_json(RUN/'preflight.json',s)
        if not s['safe']:write_json(RUN/'BLOCKED.json',s);log('BLOCKED');return 75
        (LOG/'supervisor.pid').write_text(str(os.getpid()));assert not (LOG/'worker.log').exists(),'no automatic partial rerun'
        with (LOG/'worker.log').open('x',buffering=1) as f:
            child=subprocess.Popen([sys.executable,'-B','-m',MODULE,'worker'],cwd=ROOT,env=os.environ,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);(LOG/'worker.pid').write_text(str(child.pid));log('START P13 worker '+str(child.pid))
            while child.poll() is None:
                try:child.wait(timeout=3);break
                except subprocess.TimeoutExpired:pass
                try:
                    s=inspect({os.getpid(),child.pid});append_jsonl(LOG/'guard.jsonl',s)
                    if s['safe']:continue
                    reason=s
                except Exception as e:reason={'inspection_error':repr(e)}
                write_json(LOG/'STOP',{'time':time.strftime('%F %T %z'),'reason':reason});os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=30)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                break
            rc=child.wait();write_json(RUN/'supervisor_end.json',{'rc':rc,'time':time.strftime('%F %T %z')});log('END P13 rc='+str(rc));return rc
if __name__=='__main__':
    time.tzset();p=argparse.ArgumentParser();p.add_argument('mode',choices=['build','supervise','worker','preflight']);a=p.parse_args()
    try:
        if a.mode=='preflight':
            s=inspect({os.getpid()});print(json.dumps(s,ensure_ascii=False));sys.exit(0 if s['safe'] else 75)
        v={'build':build,'supervise':supervise,'worker':worker}[a.mode]();sys.exit(v or 0)
    except Exception as e:
        RUN.mkdir(exist_ok=True);write_json(RUN/('ERROR_'+time.strftime('%Y%m%d_%H%M%S')+'.json'),{'error':repr(e),'time':time.strftime('%F %T %z')});traceback.print_exc();sys.exit(1)
