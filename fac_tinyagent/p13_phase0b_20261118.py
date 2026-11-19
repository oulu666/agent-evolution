"""Phase0B only: preregistered one-step forecast of a complete natural suffix."""
from __future__ import annotations
import os
os.environ.update(PYTHONDONTWRITEBYTECODE='1',PYTHONUNBUFFERED='1',HF_HUB_OFFLINE='1',TOKENIZERS_PARALLELISM='false',TZ='Asia/Shanghai')
import argparse,collections,copy,datetime,fcntl,hashlib,json,math,re,signal,subprocess,sys,time,traceback
from pathlib import Path
from .utils import read_json,read_jsonl,write_json,write_jsonl,append_jsonl,sha256_file,canonical_json
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data_ext_p13_phase0b';RUN=ROOT/'runs_ext_p13_phase0b';LOG=RUN/'logs'
PREREG=ROOT/'P13_PHASE0B_PREREG_20261118_ZH.md';MOD='fac_tinyagent.p13_phase0b_20261118';SEEDS=[20261108,20261109,20261110]
SKILLS=['cal.count_date','cal.list_locations'];CAL=DATA/'fixtures/calendar.json';DB=ROOT/'data_phase2/fixtures/toolbench.db'
SEGMENTS=['call','tool_name','args','call_other','final','all']
def now():return time.strftime('%F %T %z')
def log(x):print(now(),x,flush=True)
def prefix(seed):return ROOT/f'runs_ext_e4/prefixes/A_seed{seed}'
def inspect(allowed):
    from .p13_phase0_20261118 import inspect as inherited
    s=inherited(allowed)
    s['observed_GPU_memory_MiB']=float(subprocess.check_output(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],timeout=20).decode().splitlines()[0]);return s

def masks_for(r,tok):
    from .sft.dataset import tokenize_episode,conversation_text,assistant_spans
    text=conversation_text(tok,r['messages']);en=tok(text,add_special_tokens=False,return_offsets_mapping=True,return_attention_mask=False)
    ft=tokenize_episode(r,tok,1024);assert en['input_ids']==ft['input_ids'] and len(ft['input_ids'])<1024,'truncated '+r['episode_id']
    spans=assistant_spans(ft['input_ids'],tok);assert len(spans)==2
    c=set(range(*spans[0]));f=set(range(*spans[1]));call=r['messages'][2]['content'];assert json.loads(call)=={'tool':r['expected_tool'],'arguments':r['expected_arguments']}
    start=text.index(call);match=re.search(r'"tool"\s*:\s*"([^"\\]+)"',call);assert match
    nr=(start+match.start(1),start+match.end(1));am=re.search(r'"arguments"\s*:\s*',call);assert am
    obj,n=json.JSONDecoder().raw_decode(call[am.end():]);assert obj==r['expected_arguments'];ar=(start+am.end(),start+am.end()+n)
    overlap=lambda j,a:en['offset_mapping'][j][1]>a[0] and en['offset_mapping'][j][0]<a[1]
    name={j for j in c if overlap(j,nr)};args={j for j in c if overlap(j,ar)};assert name and args and not name&args
    other=c-name-args;supervised={j for j,y in enumerate(ft['labels']) if y!=-100}
    assert not c&f and c|f==supervised and not (name|args|other)&f
    assert name|args|other|f==supervised and all(j>0 for j in supervised)
    for a in [nr,ar]:
        for pos in range(*a):assert any(en['offset_mapping'][j][0]<=pos<en['offset_mapping'][j][1] for j in c),'uncovered JSON char'
    masks={'call':sorted(c),'tool_name':sorted(name),'args':sorted(args),'call_other':sorted(other),'final':sorted(f),'all':sorted(supervised)}
    assert all(masks[k] for k in SEGMENTS)
    return {'features':ft,'masks':masks,'denominators':{k:len(v) for k,v in masks.items()},'decoded_component_tokens':{k:tok.decode([ft['input_ids'][j] for j in masks[k]]) for k in ['tool_name','args','call_other','final']}}

def make_rows():
    from .p11_eaar_v1_20261118 import row
    roles=[('calibration',2033),('candidate',2034),('dev',2035)];events=[];specs=[]
    for role,year in roles:
        for k,skill in enumerate(SKILLS):
            cases=[0,7,14,21] if role=='calibration' else list(range(24))
            for i in cases:
                date=datetime.date(year,1,1)+datetime.timedelta(days=k*60+i*2);d=date.isoformat();n=[0,1,3,5][i//6];style=i%6
                forms=[d,date.strftime('%B %d, %Y'),f'{date.day} {date.strftime("%B %Y")}',d,date.strftime('%B %d, %Y'),d];shown=forms[style]
                count_templates=[f'How many events are scheduled on {shown}? Return one integer.',f'For the single calendar day {shown}, give the number of events as an integer.',f'Count events taking place on {shown}; answer with an integer.',f'What is the event total for date {shown}, not the whole month? Return one integer.',f'On {shown}, how many events occur? Output a single integer.',f'Find the number of events whose date is {shown}. Give one integer.']
                loc_templates=[f'List the distinct locations of events on {shown}, sorted alphabetically, as a JSON array.',f'For the single day {shown}, return an alphabetically sorted JSON array of unique event locations.',f'Collect event locations on {shown}; remove duplicates, sort alphabetically, and return a JSON array.',f'Which distinct locations are used on date {shown}, not the whole month? Give a sorted JSON array.',f'On {shown}, list unique event locations in alphabetical order as a JSON array.',f'Find locations for events whose date is {shown}; output a sorted JSON array without duplicates.']
                for j in range(n):
                    loc=['Zeta','Alpha','Zeta','Beta','Lima'][j]
                    events.append({'id':f'P13B_{role}_{k}_{i}_{j}','title':f'{role} session {i}_{j}','date':d,'start':f'{9+2*j:02d}:00','end':f'{10+2*j:02d}:00','location':f'{role.title()}Hall {loc}','attendees':[f'{role.title()}Guest {i}']})
                specs.append((role,k,skill,i,d,(count_templates if k==0 else loc_templates)[style],n,style))
    write_json(CAL,{'events':events});rows=collections.defaultdict(list)
    for role,k,skill,i,d,prompt,n,style in specs:
        spec={'kind':'length'} if k==0 else {'kind':'pluck','field':'location','unique':True}
        r=row('calendar',skill,'train',i,prompt,'calendar_list',{'date':d},{},spec,cal=str(CAL));r.update(episode_id=f'p13b-{role}-{skill}-{i:02}',split=role,evaluation_only=role!='candidate',selection_allowed=role=='candidate',structure={'skill':skill,'case':i,'style':style,'events':n,'location_order_pattern':'Zeta,Alpha,Zeta,Beta,Lima'[:100]},pair_id=f'{skill}:{i:02}')
        rows[role].append(r)
    for role in rows:write_jsonl(DATA/f'{role}.jsonl',rows[role])
    mapping={r['episode_id']:next(c['episode_id'] for c in rows['candidate'] if c['pair_id']==r['pair_id']) for r in rows['dev']};assert len(mapping)==48
    write_json(DATA/'pair_mapping.json',mapping)
    return rows

def build():
    assert not DATA.exists(),'never overwrite Phase0B input';DATA.mkdir();(DATA/'fixtures').mkdir();LOG.mkdir(parents=True,exist_ok=True)
    rows=make_rows();allrows=sum(rows.values(),[]);dates={r['expected_arguments']['date'] for r in allrows};assert len(dates)==104
    collisions=[];scanned=0
    for folder in ROOT.glob('data*'):
        if not folder.is_dir() or folder==DATA:continue
        for p in folder.rglob('*.jsonl'):
            for r in read_jsonl(p):
                scanned+=1
                if r.get('expected_arguments',{}).get('date') in dates:collisions.append(str(p.relative_to(ROOT)))
    assert not collisions
    from .sft.train import load_tokenizer
    from .replay_study import config_for
    tok=load_tokenizer(config_for('A',SEEDS[0],batch_size=1));features={r['episode_id']:masks_for(r,tok) for r in allrows};write_json(DATA/'features_masks.json',features)
    # No need to repeat SQL/GSS/prompt tests. Validate gold observations via existing constructor.
    old=read_json(ROOT/'runs_ext_p13_phase0/independent_acceptance.json');assert old['passed']
    refs=[PREREG,Path(__file__),ROOT/'fac_tinyagent/p13_phase0_20261118.py',ROOT/'fac_tinyagent/p7_fullstate_v2_20261115.py',ROOT/'fac_tinyagent/replay_train.py',ROOT/'fac_tinyagent/e3_train.py',ROOT/'fac_tinyagent/sft/dataset.py',ROOT/'fac_tinyagent/sft/evaluate.py',ROOT/'data_phase2/calendar/train.jsonl',ROOT/'runs_ext_p13_phase0/independent_acceptance.json']
    original=read_jsonl(ROOT/'data_phase2/calendar/train.jsonl');batches={}
    for seed in SEEDS:
        m=read_json(prefix(seed)/'manifest.json');a=m['metadata'];assert a['midpoint']==80 and len(a['order'])==160 and a['training']['gradient_accumulation_steps']==8 and a['training']['learning_rate']==1e-4
        refs.extend([prefix(seed)/'manifest.json',prefix(seed)/'training_state.pt']);batches[str(seed)]=[[original[j] for j in a['order'][80+8*i:88+8*i]] for i in range(10)]
        assert len(batches[str(seed)])==10 and all(len(b)==8 for b in batches[str(seed)])
    write_json(DATA/'batches.json',batches)
    acceptance={'passed':True,'time':now(),'rows':{k:len(v) for k,v in rows.items()},'history_rows_scanned':scanned,'entity_conflicts':collisions,'mask_partition_checks':len(features),'empty_segments':0,'max_tokens':max(len(x['features']['input_ids']) for x in features.values()),'all_gold_observations_checked_by_constructor':True,'all_masks_match_original_labels':True,'predictor_boundary':'prefix one-step virtual update; primary endpoint natural suffix step10','old_Phase0_SQL_and_literature_reused':True}
    write_json(DATA/'cpu_acceptance.json',acceptance)
    files=[p for p in DATA.rglob('*') if p.is_file()];write_json(DATA/'manifest.json',{'time':now(),'frozen_generator_before_any_GPU_scores':True,'hashes':{str(p.relative_to(ROOT)):sha256_file(p) for p in files+refs},'normal_limits':{'seeds':3,'suffix_steps':30,'predictor_virtual_steps':3,'backward_samples':264,'NLL_forward_samples':576,'generation_episodes':456,'generate_calls':912},'per_seed_attempt_cap':2})
    # CPU metric contracts, including ties and low-positive undefined.
    assert weighted_metrics([{'score':1,'lost':True,'w':1},{'score':0,'lost':False,'w':1}])['AUROC']==1
    assert weighted_metrics([{'score':0,'lost':True,'w':1},{'score':0,'lost':False,'w':1}])['AUROC']==.5
    assert weighted_metrics([{'score':0,'lost':False,'w':1}])['AUROC'] is None
    write_json(RUN/'cpu_tests.json',{'passed':True,'mask_and_metric_contracts':True,'time':now()})
    (ROOT/'EXT_HANDOVER_20261118_p13_phase0b_ZH.md').write_text('# P13 Phase0B交接（已冻结、待运行/运行中）\n\n'+now()+' 北京时间\n\n仅本轮有上限诊断获授权，未授权后续正式pilot。CPU输入、分段token与metric测试通过。协议P13_PHASE0B_PREREG_20261118_ZH.md；数据data_ext_p13_phase0b/manifest.json。执行命令 .venv/bin/python -B -m fac_tinyagent.p13_phase0b_20261118 supervise，必须经守卫；不清STOP。\n\n状态看runs_ext_p13_phase0b/active.json、progress.jsonl、logs/worker_*.log；最终看COMPLETE.json与supervisor_end.json及summary.json。若已COMPLETE则禁止再运行。若BLOCKED且无STOP，游戏退出后可同命令继续本轮；若STOP粘性保留，不绕过。意外中断每种子最多2attempt，从原前缀确定性重建并额外记成本。\n\n正常上限3种子×10自然更新+3预测虚拟步，456两回合episodes/912generate；主分数在前缀预测虚拟一步后即冻结，主终点0→10，0/5/10生成。未授权5种子三臂正式训练，不push不发GPT。\n',encoding='utf-8')
    log('PHASE0B CPU FREEZE PASS')

def verify():
    m=read_json(DATA/'manifest.json')
    for p,h in m['hashes'].items():assert sha256_file(ROOT/p)==h,'frozen input changed '+p
    return m

def weighted_metrics(items):
    items=[r for r in items if r.get('w',1)>0];pos=sum(r.get('w',1) for r in items if r['lost']);neg=sum(r.get('w',1) for r in items if not r['lost']);total=pos+neg
    if not pos or not neg:return {'n_weight':total,'events_weight':pos,'AUROC':None,'AUPRC':None,'TopQuartileRecall':None,'prevalence':pos/total if total else None}
    groups=collections.defaultdict(lambda:[0.,0.])
    for r in items:groups[r['score']][0 if r['lost'] else 1]+=r.get('w',1)
    area=0.;before_neg=0.
    for score,(p,n) in sorted(groups.items()):area+=p*(before_neg+.5*n);before_neg+=n
    tp=0.;fp=0.;ap=0.;hit=0.;remaining=total*.25
    for score,(p,n) in sorted(groups.items(),reverse=True):
        tp+=p;fp+=n;ap+=(p/pos)*(tp/(tp+fp));take=min(remaining,p+n)
        if take>0:hit+=p*take/(p+n);remaining-=take
    return {'n_weight':total,'events_weight':pos,'AUROC':area/(pos*neg),'AUPRC':ap,'TopQuartileRecall':hit/pos,'prevalence':pos/total}

class Engine:
    def __init__(self,seed,out):
        import torch
        from bitsandbytes.optim import PagedAdamW8bit
        from . import p7_fullstate_v2_20261115 as FS
        from .replay_train import load_prefix,_training_state_hash
        from .sft.train import load_tokenizer,load_base_model,_attach_adapter
        from .replay_study import config_for
        from .e4_run import start_adapter
        self.torch=torch;self.FS=FS;self.seed=seed;self.out=out;self.cost=collections.Counter();self.timings={};self.phase='load';self.started=time.perf_counter();self.cfg=config_for('A',seed,batch_size=1)
        self.tok=load_tokenizer(self.cfg);self.model,self.dtype=load_base_model(self.cfg);self.model=_attach_adapter(self.model,self.cfg,str(start_adapter(seed)));self.params=[p for p in self.model.parameters() if p.requires_grad]
        self.opt=PagedAdamW8bit(self.params,lr=1e-4);self.scaler=torch.amp.GradScaler('cuda',enabled=self.dtype==torch.float16);self.man=read_json(prefix(seed)/'manifest.json')
        load_prefix(prefix(seed),self.model,self.opt,self.scaler,self.man['metadata']);assert _training_state_hash(self.model)==self.man['parameter_hash']
        self.original=FS.capture(self.model,self.opt,self.scaler);self.original_hash=FS.digest(self.original);self.features=read_json(DATA/'features_masks.json');self.transient_features={};self.peak_alloc=0;self.peak_reserved=0;torch.cuda.reset_peak_memory_stats()
        self.hook=self.model.get_base_model().register_forward_hook(self.forward_hook);self.memory()
    def memory(self):
        t=self.torch;self.peak_alloc=max(self.peak_alloc,t.cuda.max_memory_allocated());self.peak_reserved=max(self.peak_reserved,t.cuda.max_memory_reserved())
    def forward_hook(self,m,a,o):self.cost[self.phase+'_causalLM_forward_calls']+=1;self.memory()
    def safe(self):
        if (LOG/'STOP').exists():raise RuntimeError('Phase0B sticky STOP')
    def capture(self):return self.FS.capture(self.model,self.opt,self.scaler)
    def restore(self,state):self.FS.restore(state,self.model,self.opt,self.scaler)
    def feature(self,r):
        from .sft.dataset import tokenize_episode
        e=r['episode_id']
        if e in self.features:return self.features[e]['features']
        if e not in self.transient_features:self.transient_features[e]=tokenize_episode(r,self.tok,1024)
        return self.transient_features[e]
    def batch(self,r):
        from .sft.dataset import DataCollator
        return {k:v.to('cuda') for k,v in DataCollator(self.tok)([self.feature(r)]).items()}
    def nll(self,rows,tag):
        self.safe();state=self.capture();self.phase='NLL';t=self.torch;self.model.eval();start=time.perf_counter();result=[]
        try:
            with t.no_grad():
                for r in rows:
                    self.safe();b=self.batch(r)
                    with t.autocast(device_type='cuda',dtype=self.dtype):out=self.model(**b)
                    ce=t.nn.functional.cross_entropy(out.logits[0,:-1].float(),b['labels'][0,1:],reduction='none',ignore_index=-100)
                    record={'episode_id':r['episode_id'],'input_tokens':len(self.feature(r)['input_ids'])}
                    for k,mask in self.features[r['episode_id']]['masks'].items():
                        v=float(ce[[j-1 for j in mask]].mean());assert math.isfinite(v);record[k]=v
                    assert abs(record['all']-float(out.loss))<.002,'whole-token mean mismatch'
                    result.append(record);self.cost['NLL_forward_samples']+=1;self.cost['NLL_input_tokens']+=record['input_tokens'];self.memory()
            write_json(self.out/f'{tag}.json',{'time':now(),'state_hash':self.FS.digest(state),'rows':result});return result
        finally:self.restore(state);self.timings[tag+'_seconds']=time.perf_counter()-start
    def update(self,rows,kind,step):
        self.safe();self.phase=kind;self.model.train();self.opt.zero_grad(set_to_none=True);t=self.torch;start=time.perf_counter();assert len(rows)==8
        for r in rows:
            self.safe()
            with t.autocast(device_type='cuda',dtype=self.dtype):loss=self.model(**self.batch(r)).loss
            assert t.isfinite(loss);self.scaler.scale(loss/8).backward();self.cost[kind+'_backward_samples']+=1;self.cost[kind+'_input_tokens']+=len(self.feature(r)['input_ids']);self.memory()
        self.scaler.step(self.opt);self.scaler.update();self.opt.zero_grad(set_to_none=True);self.cost[kind+'_optimizer_steps']+=1;self.memory();self.timings[f'{kind}_{step}_seconds']=time.perf_counter()-start
        state=self.capture();record={'time':now(),'seed':self.seed,'step':step,'kind':kind,'state_hash':self.FS.digest(state),'LoRA_hash':self.FS.digest(state['parameters']),'optimizer_hash':self.FS.digest(state['optimizer'])}
        append_jsonl(self.out/'updates.jsonl',record);append_jsonl(RUN/'progress.jsonl',record);log(f'{self.seed} {kind} step {step} complete')
        return record
    def generation(self,rows,tag,previous=None):
        from .sft.evaluate import generate_with_usage,_evaluate_tool_prediction,parse_final_answer
        from .metrics import answers_equal,joint_success
        self.safe();state=self.capture();binding=self.FS.digest(state);start=time.perf_counter();self.phase='generation';self.model.eval();out=self.out/tag;out.mkdir();record_path=out/'results.jsonl'
        # Only fully completed nodes may be reused, and only at identical complete state.
        if previous:
            for src in previous:
                if (src/tag/'COMPLETE.json').exists():
                    receipt=read_json(src/tag/'COMPLETE.json');assert receipt['state_hash']==binding,'deterministic reconstruction mismatch'
                    rs=read_jsonl(src/tag/'results.jsonl');assert len(rs)==len(rows);write_jsonl(record_path,rs);write_json(out/'COMPLETE.json',{**receipt,'reused_from':str(src/tag)});self.cost['reused_generation_episodes']+=len(rs);self.restore(state);return rs
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
        finally:self.restore(state);self.timings[tag+'_seconds']=time.perf_counter()-start
    def finish(self):
        self.opt.zero_grad(set_to_none=True);self.restore(self.original);after=self.capture();receipt={'time':now(),'seed':self.seed,'before':self.original_hash,'after':self.FS.digest(after),'exact':self.original_hash==self.FS.digest(after),'LoRA_before':self.FS.digest(self.original['parameters']),'LoRA_after':self.FS.digest(after['parameters']),'optimizer_before':self.FS.digest(self.original['optimizer']),'optimizer_after':self.FS.digest(after['optimizer']),'prefix_file_unchanged':sha256_file(prefix(self.seed)/'training_state.pt')==read_json(DATA/'manifest.json')['hashes'][str((prefix(self.seed)/'training_state.pt').relative_to(ROOT))]}
        self.memory();write_json(self.out/'restoration.json',receipt);self.cost['peak_allocated_GPU_bytes_over_all_segments']=self.peak_alloc;self.cost['peak_reserved_GPU_bytes_over_all_segments']=self.peak_reserved;self.cost['elapsed_seconds']=time.perf_counter()-self.started
        write_json(self.out/'cost.json',{'time':now(),'counts':dict(self.cost),'timings_seconds':self.timings,'production_optimizer_steps':0,'all_extra_diagnostic_cost':True,'forward_counter':'CausalLM invocation, includes token decode; internal layer checkpoint recomputation not separate CausalLM invocation'})
        self.hook.remove();del self.model;import gc;gc.collect();self.torch.cuda.empty_cache();assert receipt['exact'] and receipt['prefix_file_unchanged'];return receipt

def attempt_dir(kind,seed):
    root=RUN/kind/f'seed{seed}';root.mkdir(parents=True,exist_ok=True)
    attempts=sorted(root.glob('attempt[0-9][0-9]'));assert len(attempts)<2,'Phase0B maximum two attempts reached'
    out=root/f'attempt{len(attempts)+1:02}';out.mkdir();return root,out,attempts

def calibrate(seed):
    root=RUN/'calibration'/f'seed{seed}'
    if (root/'COMPLETE.json').exists():return
    root,out,prior=attempt_dir('calibration',seed);e=Engine(seed,out)
    try:
        rs=e.generation(read_jsonl(DATA/'calibration.jsonl'),'prefix_calibration',prior);summary={k:{m:sum(r[m] for r in rs if r['skill']==k) for m in ['tool_correct','arguments_correct','final_correct','joint_success']} for k in SKILLS}
    finally:receipt=e.finish()
    write_json(root/'COMPLETE.json',{'time':now(),'attempt':str(out.relative_to(ROOT)),'summary_out_of_4_per_skill':summary,'state_restored':receipt['exact'],'content_changes_allowed':False})

def freeze_after_calibration():
    assert all((RUN/'calibration'/f'seed{s}'/'COMPLETE.json').exists() for s in SEEDS)
    paths=[DATA/'manifest.json']+[RUN/'calibration'/f'seed{s}'/'COMPLETE.json' for s in SEEDS]
    p=RUN/'formal_freeze.json';hashes={str(f.relative_to(ROOT)):sha256_file(f) for f in paths}
    if p.exists():assert read_json(p)['hashes']==hashes
    else:write_json(p,{'time':now(),'calibration_completed_before_any_suffix_updates':True,'no_probe_or_candidate_edits_after_calibration':True,'hashes':hashes})

def run_seed(seed):
    root=RUN/'seeds'/f'seed{seed}'
    if (root/'COMPLETE.json').exists():return
    root,out,previous=attempt_dir('seeds',seed);e=Engine(seed,out);allrows=read_jsonl(DATA/'candidate.jsonl')+read_jsonl(DATA/'dev.jsonl');dev=read_jsonl(DATA/'dev.jsonl');batches=read_json(DATA/'batches.json')[str(seed)]
    try:
        if previous and (previous[-1]/'prediction.json').exists():
            prior=read_json(previous[-1]/'prediction.json');assert prior['origin_full_state_hash']==e.original_hash
        before=e.nll(allrows,'nll_prefix');e.update(batches[0],'predictor_virtual',1);after=e.nll(allrows,'nll_predictor_virtual1');e.restore(e.original)
        assert e.FS.digest(e.capture())==e.original_hash
        b={r['episode_id']:r for r in before};a={r['episode_id']:r for r in after}
        pred={x:{'input_tokens':b[x]['input_tokens'],'initial':{k:b[x][k] for k in SEGMENTS},'delta':{k:a[x][k]-b[x][k] for k in SEGMENTS},'risk':{k:max(0.,a[x][k]-b[x][k]) for k in SEGMENTS}} for x in b}
        write_json(out/'prediction.json',{'time':now(),'origin_full_state_hash':e.original_hash,'available_before_all_natural_suffix_updates':True,'prediction_horizon':'prefix one-step virtual forecast -> natural suffix terminal10','rows':pred})
        if previous and (previous[-1]/'prediction.json').exists():assert prior['rows']==pred,'nondeterministic forecast reconstruction'
        baseline=e.generation(dev,'node00',previous)
        # This complete at-risk map is frozen before the first natural suffix step.
        write_json(out/'at_risk.json',{'time':now(),'definition':'fixed per-seed prefix correctness; all probes retained','probe_ids':[r['episode_id'] for r in baseline],'core':[r['episode_id'] for r in baseline if r['tool_correct'] and r['arguments_correct']],'Joint':[r['episode_id'] for r in baseline if r['joint_success']]})
        for i,rows in enumerate(batches,1):
            record=e.update(rows,'natural_suffix',i)
            for old in previous:
                if (old/'updates.jsonl').exists():
                    same=[u for u in read_jsonl(old/'updates.jsonl') if u['kind']=='natural_suffix' and u['step']==i]
                    if same:assert same[0]['state_hash']==record['state_hash'],'natural stream reconstruction mismatch'
            if i in [5,10]:e.generation(dev,f'node{i:02}',previous)
    finally:receipt=e.finish()
    write_json(root/'COMPLETE.json',{'time':now(),'attempt':str(out.relative_to(ROOT)),'natural_steps':10,'predictor_virtual_steps':1,'prefix_restored':receipt['exact']})

# ---------- CPU-only analysis ----------
def metric_table(records,score_key='risk_call'):
    return {str(s):weighted_metrics([{'score':r[score_key],'lost':r['lost'],'w':1} for r in records if r['seed']==s]) for s in SEEDS}
def macro_auc(records,key,seed_weights=None,probe_weights=None):
    values=[]
    for s in SEEDS:
        sw=seed_weights.get(s,0) if seed_weights is not None else 1
        if sw<=0:continue
        items=[{'score':r[key],'lost':r['lost'],'w':probe_weights.get(r['episode_id'],0) if probe_weights is not None else 1} for r in records if r['seed']==s]
        v=weighted_metrics(items)['AUROC']
        if v is not None:values.extend([v]*sw)
    return sum(values)/len(values) if values else None

def bootstrap(records):
    import numpy as np
    rng=np.random.default_rng(20261118);ids=sorted({r['episode_id'] for r in records});out={'MIR_minus_initial_NLL':[],'MIR_minus_TokenCost':[],'MIR_AUROC':[]}
    if not ids:return {'valid_replicates':0,'intervals':{k:None for k in out},'method':'two-way seed x shared-probe bootstrap'}
    for _ in range(1000):
        sw=collections.Counter(int(x) for x in rng.choice(SEEDS,len(SEEDS),replace=True));pw=collections.Counter(str(x) for x in rng.choice(ids,len(ids),replace=True))
        v=macro_auc(records,'risk_call',sw,pw);b=macro_auc(records,'initial_call',sw,pw);c=macro_auc(records,'input_tokens',sw,pw)
        if None not in [v,b,c]:out['MIR_AUROC'].append(v);out['MIR_minus_initial_NLL'].append(v-b);out['MIR_minus_TokenCost'].append(v-c)
    intervals={k:[float(np.quantile(v,.025)),float(np.quantile(v,.975))] if v else None for k,v in out.items()}
    return {'valid_replicates':len(out['MIR_AUROC']),'requested_replicates':1000,'intervals':intervals,'method':'two-way seed x shared-probe pigeonhole bootstrap; only three seed clusters, exploratory not strong population evidence'}

def analyze():
    verify();mapping=read_json(DATA/'pair_mapping.json');full=[];primary=[];secondary=collections.defaultdict(list);outcomes={};receipts=[]
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
    for p in sorted(RUN.glob('*/seed*/attempt*/cost.json')):costs.append({'path':str(p.relative_to(ROOT)),**read_json(p)})
    totals=collections.Counter()
    for c in costs:
        for k,v in c['counts'].items():
            if k.startswith('peak_'):totals[k]=max(totals[k],v)
            else:totals[k]+=v
    guards=read_jsonl(LOG/'guard.jsonl');assert all(g['safe'] for g in guards)
    result={'time':now(),'decision':decision,'gates':gates,'primary_observation_unit':'same dev probe own pre-trajectory one-step delta_call -> terminal10 core(tool AND args) loss; not replay generalization','primary_total_at_risk':len(primary),'primary_core_losses':sum(r['lost'] for r in primary),'seeds_with_minimum_events':enough,'primary_per_seed_metrics':metrics,'primary_macro_AUROC_all_defined_seeds':means,'gate_macro_AUROC_sufficient_event_seeds':gate_means,'bootstrap_all_at_risk':ci,'bootstrap_gate_eligible_seeds':gate_ci,'candidate_mapping_is_separate_secondary_not_memory_selection_efficacy':True,'secondary_components':{k:metric_table(v) for k,v in secondary.items()},'outcomes_out_of_24_each_skill':outcomes,'records':full,'state_restoration_receipts':receipts,'cost_totals_including_all_attempts':dict(totals),'cost_attempts':costs,'safe_guard_checks':len(guards),'observed_GPU_memory_peak_MiB':max(g['observed_GPU_memory_MiB'] for g in guards) if guards else None,'formal_optimizer_steps':0,'normal_temporary_optimizer_steps':33,'limits':'exploratory post-P12 no-replay natural suffix, not P12 reproduction; repeated midpoint records not pooled into primary; three seed clusters weak external evidence; no extra experiment or formal pilot'}
    write_json(RUN/'summary.json',result);write_json(RUN/'independent_acceptance.json',{'time':now(),'passed':True,'frozen_input_hashes_verified':True,'complete_seeds':3,'all_guard_checks_safe':True,'complete_restore_checks':len(receipts),'primary_records_once_per_seed_probe':True,'masks_CPU_checks':read_json(DATA/'cpu_acceptance.json')['mask_partition_checks'],'prediction_file_precedes_all_natural_updates':True,'terminal_nodes':3,'no_formal_training':True})
    report='# P13 Phase0-B 独立实验报告\n\n北京时间 '+result['time']+'\n\n## 客观判断\n一次延长的诊断不是方法创新。修复了观测单位和时序：主分析用同一探针的前缀一步虚拟ΔNLL预测未来10步终点工具+参数退化；候选一一结构配对映射单列，并非replay选择效果。完整自然无回放suffix不复现P12带回放过程。\n\n## 结果与冻结gate\n'+json.dumps({k:result[k] for k in ['decision','gates','primary_total_at_risk','primary_core_losses','seeds_with_minimum_events','primary_per_seed_metrics','gate_macro_AUROC_sufficient_event_seeds','bootstrap_gate_eligible_seeds','outcomes_out_of_24_each_skill']},ensure_ascii=False,indent=2)+'\n\n## 成本和审计\n'+json.dumps({k:result[k] for k in ['cost_totals_including_all_attempts','safe_guard_checks','observed_GPU_memory_peak_MiB','formal_optimizer_steps']},ensure_ascii=False,indent=2)+'\n\nLoRA/optimizer/scaler/RNG/module modes均精确恢复，原前缀文件hash不变。显存记录覆盖所有段且不调用旧评测器的峰值重置；reserved可能反映WSL虚拟/共享分配而非独占物理显存。所有成本含校准和MIR虚拟预测，为额外诊断训练计算，不能称纯评测。\n\n主指标未越门槛不以次组件/中点/候选映射救结论；事件不足为UNIDENTIFIABLE，不扩大规模。即便gate过，也不自动启动正式pilot。已有SQL/GSS/文献结论直接复用，无新提示矩阵。\n'
    (ROOT/'EXT_REPORT_20261118_p13_phase0b_independent_ZH.md').write_text(report,encoding='utf-8')
    (ROOT/'EXT_HANDOVER_20261118_p13_phase0b_ZH.md').write_text('# P13 Phase0B交接\n\n'+now()+' 北京时间\n\n'+decision+'\n\n结果runs_ext_p13_phase0b/summary.json，审计independent_acceptance.json；协议P13_PHASE0B_PREREG_20261118_ZH.md；独立报告EXT_REPORT_20261118_p13_phase0b_independent_ZH.md；成本/恢复见各calibration、seeds/seed*/attempt*/cost.json和restoration.json。完成标记COMPLETE.json，监督器supervisor_end.json。不push，不启动正式MIR/DG-MIR训练，不扩大本轮。\n',encoding='utf-8')
    write_json(RUN/'COMPLETE.json',{'time':now(),'complete':True,'decision':decision,'seeds':3,'formal_updates':0});log('PHASE0B COMPLETE '+decision);return result

def worker():
    signal.signal(signal.SIGTERM,lambda s,f:sys.exit(75));signal.signal(signal.SIGINT,lambda s,f:sys.exit(75));verify()
    for seed in SEEDS:calibrate(seed)
    freeze_after_calibration()
    for seed in SEEDS:run_seed(seed)
    analyze()

def supervise():
    LOG.mkdir(parents=True,exist_ok=True);verify();assert not (RUN/'COMPLETE.json').exists(),'already complete'
    with (LOG/'phase0b.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);s=inspect({os.getpid()});stamp=time.strftime('%Y%m%d_%H%M%S');write_json(RUN/f'preflight_{stamp}.json',s)
        if not s['safe']:write_json(RUN/f'BLOCKED_{stamp}.json',s);log('BLOCKED '+json.dumps(s));return 75
        (LOG/'supervisor.pid').write_text(str(os.getpid()));wf=LOG/f'worker_{stamp}.log'
        with wf.open('x',buffering=1) as f:
            child=subprocess.Popen([sys.executable,'-B','-m',MOD,'worker'],cwd=ROOT,env=os.environ,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);(LOG/'worker.pid').write_text(str(child.pid));write_json(RUN/'active.json',{'time':now(),'supervisor_pid':os.getpid(),'worker_pid':child.pid,'worker_log':str(wf.relative_to(ROOT))});log('START Phase0B worker '+str(child.pid))
            while child.poll() is None:
                try:child.wait(timeout=3);break
                except subprocess.TimeoutExpired:pass
                try:
                    s=inspect({os.getpid(),child.pid});append_jsonl(LOG/'guard.jsonl',s)
                    if s['safe']:continue
                    reason=s
                except Exception as e:reason={'inspection_error':repr(e)}
                write_json(LOG/'STOP',{'time':now(),'reason':reason});log('SAFETY STOP '+json.dumps(reason));os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=45)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
                break
            rc=child.wait();write_json(RUN/f'supervisor_end_{stamp}.json',{'time':now(),'rc':rc});write_json(RUN/'supervisor_end.json',{'time':now(),'rc':rc});log('END Phase0B rc='+str(rc));return rc
if __name__=='__main__':
    time.tzset();p=argparse.ArgumentParser();p.add_argument('mode',choices=['build','preflight','supervise','worker','analyze']);a=p.parse_args()
    try:
        if a.mode=='preflight':
            s=inspect({os.getpid()});print(json.dumps(s,ensure_ascii=False));sys.exit(0 if s['safe'] else 75)
        v={'build':build,'supervise':supervise,'worker':worker,'analyze':analyze}[a.mode]();sys.exit(v if isinstance(v,int) else 0)
    except BaseException as e:
        if isinstance(e,SystemExit):raise
        RUN.mkdir(exist_ok=True);write_json(RUN/f'ERROR_{time.strftime("%Y%m%d_%H%M%S")}.json',{'time':now(),'error':repr(e)});traceback.print_exc();sys.exit(1)
