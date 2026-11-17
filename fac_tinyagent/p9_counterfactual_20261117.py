"""P9: paired counterfactual observation replay. Frozen, resumable single GPU jobs."""
from __future__ import annotations
import argparse, copy, gc, hashlib, json, os, random, re, signal, sqlite3, statistics, time
from pathlib import Path
from .utils import read_json, read_jsonl, write_json, write_jsonl, append_jsonl, canonical_json, sha256_file, ensure_dir
from . import p8_decision_data_20261115 as P8

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data_ext_p9_counterfactual_20261117'
RUN=ROOT/'runs_ext_p9_counterfactual_20261117'
CAL=ROOT/'data_phase2/fixtures/calendar.json'
DB=ROOT/'data_phase2/fixtures/toolbench.db'
SEEDS=[20261108,20261109,20261110]
STOP=False

def log(s): print(time.strftime('%F %T %z'),s,flush=True)
def request_stop(sig,frame):
    global STOP
    STOP=True
def guard():
    if STOP or (RUN/'logs/STOP').exists(): raise SystemExit(75)
def atomic_json(path,obj):
    path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp');write_json(tmp,obj);os.replace(tmp,path)

def schema_correct(row,db):
    row=copy.deepcopy(row)
    if row['tool_family']!='database':return row
    with sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True) as c:
        tables=[x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        context='DATABASE (read-only):\n'+'\n'.join(t+'('+', '.join(x[1]+' '+x[2] for x in c.execute('PRAGMA table_info('+t+')'))+')' for t in tables)
    system=re.sub(r'DATABASE \(read-only\):.*?(?=\n\nOutput format:)',context,row['system'],flags=re.S)
    assert system!=row['system'] or all(t in system for t in tables)
    row['system']=system;row['messages'][0]['content']=system
    return row

def file_row(eid,path,word,lines,intent,prompt,case,split):
    from .data.generate import _observation,_schemas,build_system_prompt
    from .round2_data import _messages
    env={'files':{path:'\n'.join(lines)+'\n'}};args={'path':path,'pattern':word}
    obs=_observation('file','file_search',args,env,str(DB),str(CAL))
    matches=json.loads(obs)['result'];answer=matches[0 if intent=='first' else -1]['text']
    system=build_system_prompt('file',_schemas('file',str(DB),str(CAL)))
    return dict(episode_id=eid,tool_family='file',skill='file.search_'+intent,split=split,prompt=prompt,system=system,environment=env,expected_tool='file_search',expected_arguments=args,expected_observation=obs,expected_final_answer=answer,messages=_messages(system,prompt,'file_search',args,obs,answer),case=case,intent=intent,n_matches=len(matches))

def files(split,n):
    rng=random.Random({'train':91701,'dev':91702,'holdout':91703}[split]);out=[]
    for i in range(n):
        hits=2+i%(4 if split=='holdout' else 3);path=f'p9_{split}/note_{i}.txt';word=f'k{split}{i}z'
        positions=sorted(rng.sample(range(1,18),hits));lines=[f'unrelated item {j}' for j in range(1,19)]
        values=rng.sample(range(10000,99999),hits)
        for p,v in zip(positions,values):lines[p-1]=f'{word} observation {v}'
        for intent in ['first','last']:
            if split=='train':
                prompt=(f'In {path}, search for {word!r}. Return the complete {intent} matching line in the file.' if i%2==0 else f'Search {path} for {word!r} and give only the full {intent} matching line as it occurs in the original file.')
            elif split=='dev':prompt=f'Find lines containing {word!r} in {path}. Which complete matching line occurs {intent} in the file?'
            else:
                which='earliest' if intent=='first' else 'latest'
                templates=[f'Locate matches for {word!r} in {path}; report the whole line at the {which} position in the original file.',f'For {path}, find occurrences of {word!r}. Give the full text of the {intent} occurrence in file order.',f'Look up {word!r} within {path}. Select just the complete {intent} matching line of that file.']
                prompt=templates[i%3]
            out.append(file_row(f'p9-{split}-{i}-{intent}',path,word,lines,intent,prompt,i,split))
    return out

def permute_observation(row,permutation):
    row=copy.deepcopy(row);obj=json.loads(row['expected_observation']);obj['result']=[obj['result'][j] for j in permutation]
    row['expected_observation']=canonical_json(obj);row['messages'][3]['content']='TOOL RESULT:\n'+row['expected_observation']
    row['presentation_permutation']=permutation
    return row

def probes():
    seen=read_json(ROOT/'data_ext_p81_diagnosis_20261116/seen_train.json');out={}
    for seed in SEEDS:
        old=next(r for r in seen[str(seed)] if r.get('skill')=='file.search_last')
        path=old['expected_arguments']['path'];word=old['expected_arguments']['pattern'];lines=old['environment']['files'][path].splitlines();rows=[]
        for variation in ['original','identifiers','wording','line_positions','reversed','extra_match']:
            for intent in ['first','last']:
                p=path;w=word;ls=list(lines);prompt=old['prompt'].replace('last matching','%s matching'%intent)
                if variation=='identifiers':
                    p='p9_probe/renamed.txt';w='p9probemark';ls=[x.replace(word,w) for x in ls];prompt=prompt.replace(path,p).replace(word,w)
                elif variation=='wording':prompt=f'Return the entire {intent} line containing {w!r} in the original file {p}.'
                elif variation=='line_positions':ls=['neutral prefix','another neutral']+ls[:1]+['neutral gap']+ls[1:]
                elif variation=='extra_match':ls.append(w+' additional value')
                r=file_row(f'p9-probe-{seed}-{variation}-{intent}',p,w,ls,intent,prompt,variation,'diagnostic_seen_transform')
                if variation=='reversed':r=permute_observation(r,list(reversed(range(r['n_matches']))))
                r['variation']=variation;rows.append(r)
        out[str(seed)]=rows
    return out

def build():
    assert not (DATA/'manifest.json').exists(),'frozen data cannot be rebuilt'
    from .sft.train import load_tokenizer
    from .sft.dataset import tokenize_episode
    from .replay_study import config_for
    ensure_dir(DATA);ensure_dir(RUN/'logs')
    train=files('train',24);dev=files('dev',4);holdout=files('holdout',12)
    normal=[];counter=[]
    for r in train:
        normal.append(r);perm=list(range(r['n_matches']));rng=random.Random(99170+r['case']);rng.shuffle(perm)
        # Both intents for a file see exactly the same permutation, independent of label.
        counter.append(permute_observation(r,perm))
    bg=[]
    for fam in ['database','python','calendar']:
        pool=read_jsonl(ROOT/f'data_phase2/{fam}/train.jsonl')
        for r in pool[:8]:
            r=schema_correct(r,DB);r['p9_background']=True;bg.append(r)
    for name,rows in [('normal',normal+bg),('counter',counter+bg),('dev',dev),('holdout',holdout)]:write_jsonl(DATA/(name+'.jsonl'),rows)
    write_json(DATA/'file_probes.json',probes())
    # Fixed CPU/schema diagnostic: four cases, each legacy/corrected/corrected+turn cue.
    sqls=read_jsonl(ROOT/'data_ext_p81_diagnosis_20261116/sql.jsonl');sql=[]
    ids=['p81-db-zero-filter_sort-natural','p81-db-zero-filter_sort-structured','p81-db-ties-sort-structured','p81-db-ties-filter_sort_tie-structured']
    for old in sqls:
        if old['episode_id'] not in ids:continue
        for version in ['legacy','schema','schema_turn']:
            r=copy.deepcopy(old) if version=='legacy' else schema_correct(old,ROOT/'data_ext_p81_diagnosis_20261116/probe.sqlite')
            if version=='schema_turn':
                r['prompt']+=' Current turn: call the database tool first using tool and arguments; return the answer only after TOOL RESULT.'
                r['messages'][1]['content']=r['prompt']
            r['source_episode_id']=old['episode_id'];r['episode_id']=old['episode_id']+'-'+version;r['version']=version;sql.append(r)
    write_jsonl(DATA/'sql_probes.jsonl',sql)
    sides=[]
    p8hold=read_jsonl(P8.DATA/'holdout.jsonl')
    for skill in ['db.list_tables','py.median']:
        for r in [r for r in p8hold if r['skill']==skill][:2]:
            r=schema_correct(r,P8.fixture('holdout'));r['p9_db']=str(P8.fixture('holdout'));sides.append(r)
    for r in read_jsonl(ROOT/'data_phase2/calendar/test.jsonl')[:4]:
        r['skill']='calendar';sides.append(r)
    write_jsonl(DATA/'sideeffects.jsonl',sides)
    tok=load_tokenizer(config_for('A',SEEDS[0],batch_size=1));counts={}
    for name in ['normal','counter','dev','holdout']:
        rows=read_jsonl(DATA/(name+'.jsonl'));ft=[tokenize_episode(r,tok,1024) for r in rows]
        assert all(len(x['input_ids'])<1024 for x in ft)
        counts[name]={'samples':len(rows),'input_tokens':sum(len(x['input_ids']) for x in ft),'supervised_tokens':sum(sum(t!=-100 for t in x['labels']) for x in ft)}
    assert counts['normal']==counts['counter'],counts
    for a,b in zip(normal,counter):
        assert a['prompt']==b['prompt'] and a['messages'][:3]==b['messages'][:3] and a['messages'][4:]==b['messages'][4:]
        assert sorted(json.loads(a['expected_observation'])['result'],key=lambda x:x['line'])==sorted(json.loads(b['expected_observation'])['result'],key=lambda x:x['line'])
        assert a['expected_final_answer']==b['expected_final_answer']
    sets=[set(next(iter(r['environment']['files'])) for r in rs) for rs in [train,dev,holdout]]
    assert not any(sets[i]&sets[j] for i in range(3) for j in range(i))
    assert len(sql)==12 and len(sides)==8
    # CPU correctness and distinguishability checks, actual file_search result labels.
    for r in train+dev+holdout:
        matches=json.loads(r['expected_observation'])['result'];assert len(matches)>=2
        assert matches[0]['text']!=matches[-1]['text']
        assert r['expected_final_answer']==matches[0 if r['intent']=='first' else -1]['text']
    from .sft.evaluate import _evaluate_tool_prediction
    for r in normal+bg+dev+holdout+sides:
        result=_evaluate_tool_prediction(r,json.dumps({'tool':r['expected_tool'],'arguments':r['expected_arguments']}),r.get('p9_db',str(DB)),str(CAL))
        assert all(result[k] for k in ['tool_correct','arguments_correct','execution_success']),r['episode_id']
    write_json(DATA/'checks.json',{'passed':True,'train_counter_only_display_changes':True,'equal_token_counts':counts,'disjoint_file_environments':True,'test_n_matches':[2,3,4,5],'training_n_matches':[2,3,4],'changed_train_cases':sum(a['expected_observation']!=b['expected_observation'] for a,b in zip(normal,counter))//2})
    paths=list(DATA.glob('*.json*'))+[Path(__file__),ROOT/'scripts/run_p9_20261117.py',ROOT/'P9_PREREG_20261117_ZH.md',DB,CAL,P8.fixture('holdout'),ROOT/'data_ext_p81_diagnosis_20261116/probe.sqlite']
    for seed in SEEDS:paths += [P8.ckpt(seed)/'adapter_model.safetensors',P8.ckpt(seed)/'full_state.pt',P8.ckpt(seed)/'full_state_receipt.json']
    for seed in SEEDS:paths.append(ROOT/f'runs_phase2/A_seed{seed}/config.json')
    for rel in ['fac_tinyagent/sft/dataset.py','fac_tinyagent/sft/train.py','fac_tinyagent/sft/evaluate.py','fac_tinyagent/p7_fullstate_v2_20261115.py','fac_tinyagent/p81_semantics.py','fac_tinyagent/metrics.py','fac_tinyagent/utils.py']:
        paths.append(ROOT/rel)
    write_json(DATA/'manifest.json',{'created':time.strftime('%F %T %z'),'source_commit':'7f22d267dd4bc0653809a5a45fc010d68601aff3','seeds':SEEDS,'arms':['baseline','normal','counter'],'epochs':2,'training_rows':72,'updates_per_new_branch':18,'planned_probe_calls':72,'planned_eval_calls':792,'hashes':{str(p.relative_to(ROOT)):sha256_file(p) for p in paths}})
    log('CPU BUILD/FREEZE PASS '+json.dumps(counts))

def verify():
    m=read_json(DATA/'manifest.json')
    for p,h in m['hashes'].items():assert sha256_file(ROOT/p)==h,'frozen input changed '+p

def probe(seed):
    import torch
    from .sft.evaluate import load_eval_model,generate_with_usage,parse_final_answer,_evaluate_tool_prediction
    from .replay_study import config_for
    from .metrics import answers_equal
    from .p81_semantics import semantic_sql_result
    path=RUN/f'probe_{seed}.jsonl';done={r['id'] for r in read_jsonl(path)}
    jobs=[('file',r) for r in read_json(DATA/'file_probes.json')[str(seed)]]+[('sql',r) for r in read_jsonl(DATA/'sql_probes.jsonl')]
    if len(done)==len(jobs):return
    model,tok=load_eval_model(config_for('A',seed,batch_size=1),str(P8.ckpt(seed)))
    for kind,r in jobs:
        if r['episode_id'] in done:continue
        guard();base=r['messages'][:4] if kind=='file' else r['messages'][:2]
        raw,u=generate_with_usage(model,tok,base,128)
        item={'id':r['episode_id'],'seed':seed,'kind':kind,'raw':raw,'usage':[u],'variation':r.get('variation'),'intent':r.get('intent'),'version':r.get('version'),'source_episode_id':r.get('source_episode_id')}
        if kind=='file':
            ok,ans=parse_final_answer(raw);item.update(answer=ans,correct=bool(ok and answers_equal(ans,r['expected_final_answer'])))
        else:
            res=_evaluate_tool_prediction(r,raw,str(ROOT/'data_ext_p81_diagnosis_20261116/probe.sqlite'),str(CAL));item.update(res)
            item['semantic_correct']=bool(res['tool_correct'] and semantic_sql_result(r,res['observation'],ROOT/'data_ext_p81_diagnosis_20261116/probe.sqlite'))
        append_jsonl(path,item);log(f'PROBE {seed} {r["episode_id"]}')
    del model,tok;gc.collect();torch.cuda.empty_cache()

def train(seed,arm):
    import torch
    from bitsandbytes.optim import PagedAdamW8bit
    from .sft.train import load_base_model,load_tokenizer,_attach_adapter
    from .sft.dataset import tokenize_episode,DataCollator
    from .replay_study import config_for
    from . import p7_fullstate_v2_20261115 as FS
    out=RUN/f'branches/seed{seed}_{arm}';ensure_dir(out)
    if (out/'complete.json').exists():return
    cfg=config_for('A',seed,batch_size=1);tok=load_tokenizer(cfg);model,dtype=load_base_model(cfg);model=_attach_adapter(model,cfg,str(P8.ckpt(seed)))
    opt=PagedAdamW8bit([p for p in model.parameters() if p.requires_grad],lr=1e-4);scaler=torch.cuda.amp.GradScaler(enabled=dtype==torch.float16);opt.zero_grad(set_to_none=True)
    start_receipt=read_json(P8.ckpt(seed)/'full_state_receipt.json');state=FS.load(P8.ckpt(seed)/'full_state.pt',start_receipt);FS.restore(state,model,opt,scaler);model.train()
    base_digest=FS.digest(FS.capture(model,opt,scaler))
    atomic_json(out/'start.json',{'source_full_state':start_receipt,'restored_train_state':base_digest,'new_lr':opt.param_groups[0]['lr'],'arm':arm,'seed':seed})
    del state
    rows=read_jsonl(DATA/(arm+'.jsonl'));features=[tokenize_episode(r,tok,1024) for r in rows];collator=DataCollator(tok)
    order=[]
    for epoch in range(2):
        indices=list(range(len(rows)));random.Random(seed+9170+epoch).shuffle(indices);order+=indices
    assert len(order)==144 and len(order)%8==0
    cursor=0;tokens=0;supervised=0;seconds=0.0;optimizer_calls=0;prior=None
    if (out/'resume.json').exists():
        resume=read_json(out/'resume.json');FS.restore(FS.load(out/resume['file'],resume['receipt']),model,opt,scaler)
        cursor=resume['cursor'];tokens=resume['input_tokens'];supervised=resume['supervised_tokens'];seconds=resume['seconds'];optimizer_calls=resume['optimizer_calls'];prior=out/resume['file']
    started=time.perf_counter();torch.cuda.reset_peak_memory_stats()
    original_step=opt.step;events=[]
    def counted(*a,**kw):
        z=original_step(*a,**kw);events.append(True);return z
    opt.step=counted
    for offset in range(cursor,len(order),8):
        guard();losses=[]
        for i in order[offset:offset+8]:
            batch={k:v.to('cuda') for k,v in collator([features[i]]).items()}
            with torch.autocast(device_type='cuda',dtype=dtype,enabled=dtype in (torch.bfloat16,torch.float16)):
                loss=model(**batch).loss
            assert torch.isfinite(loss),'nonfinite training loss'
            scaler.scale(loss/8).backward();losses.append(float(loss.detach()));tokens+=len(features[i]['input_ids']);supervised+=sum(t!=-100 for t in features[i]['labels'])
        previous=len(events);scaler.step(opt);scaler.update();opt.zero_grad(set_to_none=True);assert len(events)==previous+1,'optimizer update skipped'
        optimizer_calls+=1;cursor=offset+8
        snap=out/f'resume_step{optimizer_calls:03}.pt'
        if snap.exists():snap.unlink()  # Only uncommitted same-job snapshot after interrupted atomic metadata write.
        receipt=FS.save(FS.capture(model,opt,scaler),snap)
        atomic_json(out/'resume.json',{'file':snap.name,'receipt':receipt,'cursor':cursor,'input_tokens':tokens,'supervised_tokens':supervised,'optimizer_calls':optimizer_calls,'seconds':seconds+time.perf_counter()-started})
        if prior and prior!=snap:prior.unlink()
        prior=snap
        append_jsonl(out/'training.jsonl',{'cursor':cursor,'optimizer_calls':optimizer_calls,'mean_loss':statistics.mean(losses),'input_tokens':tokens,'seconds':seconds+time.perf_counter()-started})
        log(f'TRAIN {seed} {arm} step {optimizer_calls}/18 loss={statistics.mean(losses):.4f}')
    assert optimizer_calls==18
    model.save_pretrained(str(out/'checkpoint'));tok.save_pretrained(str(out/'checkpoint'))
    atomic_json(out/'complete.json',{'complete':True,'seed':seed,'arm':arm,'start_state':base_digest,'optimizer_calls':optimizer_calls,'input_tokens':tokens,'supervised_tokens':supervised,'seconds':seconds+time.perf_counter()-started,'peak_memory_gb':torch.cuda.max_memory_allocated()/1024**3,'adapter_sha256':sha256_file(out/'checkpoint/adapter_model.safetensors')})
    del model,opt,scaler,features,batch,loss,tok;gc.collect();torch.cuda.empty_cache()

def evaluate(seed,arm):
    import torch
    from .sft.evaluate import load_eval_model,generate_with_usage,parse_final_answer,_evaluate_tool_prediction
    from .replay_study import config_for
    from .metrics import answers_equal,joint_success
    path=RUN/f'eval_{seed}_{arm}.jsonl';done={r['id'] for r in read_jsonl(path)}
    rows=read_jsonl(DATA/'holdout.jsonl');side=read_jsonl(DATA/'sideeffects.jsonl')
    jobs=[('normal',r) for r in rows]+[('reversed',r) for r in rows]+[('side',r) for r in side]
    if len(done)==len(jobs):return
    adapter=P8.ckpt(seed) if arm=='baseline' else RUN/f'branches/seed{seed}_{arm}/checkpoint'
    model,tok=load_eval_model(config_for('A',seed,batch_size=1),str(adapter))
    for kind,r in jobs:
        rid=kind+':'+r['episode_id']
        if rid in done:continue
        guard();base=r['messages'][:2];usage=[]
        item={'id':rid,'seed':seed,'arm':arm,'kind':kind,'case':r.get('case'),'intent':r.get('intent'),'n_matches':r.get('n_matches'),'skill':r.get('skill',r['tool_family'])}
        if kind=='reversed':
            obs=json.loads(r['expected_observation']);obs['result'].reverse()
            messages=base+[r['messages'][2],{'role':'user','content':'TOOL RESULT:\n'+canonical_json(obs)}]
        else:
            raw,u=generate_with_usage(model,tok,base,128);usage.append(u)
            res=_evaluate_tool_prediction(r,raw,r.get('p9_db',str(DB)),str(CAL));item.update(res)
            messages=base+[{'role':'assistant','content':raw or '{}'},{'role':'user','content':'TOOL RESULT:\n'+res['observation']}]
        answer,u=generate_with_usage(model,tok,messages,128);usage.append(u);ok,pred=parse_final_answer(answer)
        item.update(answer_raw=answer,predicted_answer=pred,final_correct=bool(ok and answers_equal(pred,r['expected_final_answer'])),usage=usage)
        if kind!='reversed':item['joint_success']=joint_success(item)
        append_jsonl(path,item);done.add(rid)
        if len(done)%8==0:log(f'EVAL {seed} {arm} {len(done)}/{len(jobs)}')
    atomic_json(RUN/f'eval_{seed}_{arm}_complete.json',{'complete':True,'rows':len(done),'adapter_sha256':sha256_file(adapter/'adapter_model.safetensors')})
    del model,tok;gc.collect();torch.cuda.empty_cache()

def queue():
    verify()
    for seed in SEEDS:probe(seed)
    # Train all prespecified branches before reading holdout outputs.
    for seed in SEEDS:
        arms=['normal','counter'] if seed%2==0 else ['counter','normal']
        for arm in arms:train(seed,arm)
        a=read_json(RUN/f'branches/seed{seed}_normal/complete.json');b=read_json(RUN/f'branches/seed{seed}_counter/complete.json')
        for k in ['start_state','optimizer_calls','input_tokens','supervised_tokens']:assert a[k]==b[k],(seed,k)
    for seed in SEEDS:
        for arm in ['baseline','normal','counter']:evaluate(seed,arm)
    verify();atomic_json(RUN/'queue_complete.json',{'complete':True,'finished':time.strftime('%F %T %z')});log('P9 QUEUE COMPLETE')

if __name__=='__main__':
    signal.signal(signal.SIGTERM,request_stop);signal.signal(signal.SIGINT,request_stop)
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['build','verify','queue']);a=p.parse_args();globals()[a.phase]()
