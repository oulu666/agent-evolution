"""CPU-ONLY P10 candidate preparation. No model loading, generation, or GPU runner."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='',HF_HUB_OFFLINE='1',TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
import collections,copy,hashlib,inspect,json,random,sqlite3,time
from pathlib import Path
from . import p9_counterfactual_20261117 as P9
from . import p8_decision_data_20261115 as P8
from .utils import read_json,read_jsonl,write_json,write_jsonl,sha256_file,canonical_json
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data_ext_p10_twoview_cpu_20261117'
SEEDS=[20261108,20261109,20261110]

def pools(base):
    reverse=[]
    for a in base:
        b=copy.deepcopy(a)
        if a['tool_family']=='file':
            obj=json.loads(a['expected_observation']);obj['result'].reverse()
            b['messages'][3]['content']='TOOL RESULT:\n'+canonical_json(obj)
        reverse.append(b)
    return reverse

def schedule(base,seed):
    byn=collections.defaultdict(set)
    for a in base:
        if a['tool_family']=='file':byn[a['n_matches']].add(a['case'])
    bits={}
    for n,cases in sorted(byn.items()):
        cases=sorted(cases);assert len(cases)==8;random.Random(101117+n).shuffle(cases)
        bits.update({i:int(k>=4) for k,i in enumerate(cases)})
    events=[]
    for epoch in range(2):
        indices=list(range(len(base)));random.Random(seed+9170+epoch).shuffle(indices)
        for i in indices:
            a=base[i];view=(epoch^bits[a['case']]) if a['tool_family']=='file' else 0
            events.append(dict(epoch=epoch,index=i,view=view,episode_id=a['episode_id']))
    return events,bits

def new_file_holdout():
    rng=random.Random(101117303);out=[]
    for case in range(12):
        group=case//4;n=2+case%4;path=f'p10_prospective/fresh_{case}.txt';marker=f'p10unique{case}q'
        positions=sorted(rng.sample(range(1,21),n));lines=[f'plain record {i}' for i in range(1,23)]
        for p,v in zip(positions,rng.sample(range(20000,99999),n)):lines[p-1]=f'{marker} measurement {v}'
        for intent in ['first','last']:
            if group==0:
                prompt=(f'In {path}, search for {marker!r}. Return the complete {intent} matching line in the file.' if case%2==0 else f'Search {path} for {marker!r} and give only the full {intent} matching line as it occurs in the original file.')
            elif group==1:
                edge='beginning' if intent=='first' else 'end'
                prompt=f'Search file {path} for the marker {marker!r}. Of its matching lines in file order, copy the entire one closest to the {edge} of the file.'
            else:
                relation='before' if intent=='first' else 'after'
                prompt=f'Find every line containing {marker!r} in {path}. Return the complete matching line that occurs {relation} all the other matching lines in the original file.'
            a=P9.file_row(f'p10-prospective-{case}-{intent}',path,marker,lines,intent,prompt,case,'p10_prospective')
            a.update(wording_group=group,wording_label=['train_style_new_entities','new_paraphrase_edge','new_paraphrase_relation'][group],evaluation_only=True,selection_allowed=False)
            out.append(a)
    return out

def sql_retention():
    from .data.generate import _observation,_schemas,build_system_prompt
    from .round2_data import _messages
    from .research_data import project_answer
    from .p81_semantics import semantic_sql_result
    fixture=OUT/'retention.sqlite';rows=[];checks=collections.Counter()
    with sqlite3.connect(fixture) as c:
        for i,scores in enumerate([[10,20,30,40,50,5],[20,90,50,10,90,30],[80,80,80,80,80,80],[95,95,80,80,50,10,60]]):
            tab=f'p10retain_{i}';c.execute(f'CREATE TABLE {tab}(id INTEGER PRIMARY KEY,name TEXT,score REAL)')
            names=[f'p10sql_{i}_{s}' for s in random.Random(101117400+i).sample(range(1000,9999),len(scores))]
            c.executemany(f'INSERT INTO {tab} VALUES (?,?,?)',[(k+1,n,sc) for k,(n,sc) in enumerate(zip(names,scores))]);c.execute(f'CREATE INDEX idx_{tab} ON {tab}(score DESC,id DESC)')
    for i in range(4):
        tab=f'p10retain_{i}';sql=f'SELECT name FROM {tab} WHERE score > 50 ORDER BY score DESC, id ASC LIMIT 4';args={'sql':sql}
        prompt=f'From {tab}(id, name, score), return a JSON array of at most four names whose score is greater than 50, highest score first and smaller id first on equal scores.'
        obs=_observation('database','db_query',args,{},str(fixture),str(P9.CAL));answer=project_answer(json.loads(obs)['result'],{'kind':'rows_first'})
        system=build_system_prompt('database',_schemas('database',str(fixture),str(P9.CAL)))
        a=dict(episode_id=f'p10-retention-sql-{i}',tool_family='database',skill='db.filter_cmp_top',operation='filter_sort_tie',prompt=prompt,system=system,environment={},expected_tool='db_query',expected_arguments=args,expected_observation=obs,expected_final_answer=answer,answer_spec={'kind':'rows_first'},messages=_messages(system,prompt,'db_query',args,obs,answer),evaluation_db=str(fixture),evaluation_only=True,selection_allowed=False)
        a=P9.schema_correct(a,fixture);assert semantic_sql_result(a,obs,fixture)
        same=_observation('database','db_query',{'sql':sql.replace(', id ASC',', id')},{},str(fixture),str(P9.CAL));assert semantic_sql_result(a,same,fixture)
        checks['omitted_ASC_semantically_equal']+=1
        for label,wrong in [('no_where',sql.replace(' WHERE score > 50','')),('no_tie',sql.replace(', id ASC',''))]:
            wobs=_observation('database','db_query',{'sql':wrong},{},str(fixture),str(P9.CAL))
            checks[label+'_counterexamples']+=not semantic_sql_result(a,wobs,fixture)
        rows.append(a)
    assert checks['no_where_counterexamples']>=2 and checks['no_tie_counterexamples']>=2
    return rows,dict(checks)

def build():
    assert not OUT.exists(),'Refuse overwrite candidate assets'
    OUT.mkdir()
    from .sft.train import load_tokenizer
    from .sft.dataset import tokenize_episode,DataCollator
    from .sft.evaluate import _evaluate_tool_prediction
    from .replay_study import config_for
    from . import p7_fullstate_v2_20261115 as FS
    import torch
    torch.set_num_threads(1);assert not torch.cuda.is_available(),'CPU preparation must not see CUDA'
    old=read_json(P9.DATA/'manifest.json');bad=[p for p,h in old['hashes'].items() if sha256_file(ROOT/p)!=h];assert not bad,bad
    base=read_jsonl(P9.DATA/'normal.jsonl');rev=pools(base);assert len(base)==len(rev)==72
    tok=load_tokenizer(config_for('A',SEEDS[0],batch_size=1));normal_f=[tokenize_episode(a,tok,1024) for a in base];rev_f=[tokenize_episode(a,tok,1024) for a in rev]
    for a,b,af,bf in zip(base,rev,normal_f,rev_f):
        assert a['messages'][:3]==b['messages'][:3] and a['messages'][4:]==b['messages'][4:]
        assert a['expected_observation']==b['expected_observation'] and a['expected_final_answer']==b['expected_final_answer']
        assert len(af['input_ids'])==len(bf['input_ids'])<1024
        assert af['labels']==bf['labels'],'Full label positions and IDs must agree'
        if a['tool_family']!='file':assert a==b
        else:
            v=json.loads(b['messages'][3]['content'].split('\n',1)[1]);v['result'].sort(key=lambda x:x['line'])
            assert canonical_json(v)==a['expected_observation']
            orig=json.loads(a['expected_observation'])['result'];assert a['expected_final_answer']==orig[0 if a['intent']=='first' else -1]['text']
    write_jsonl(OUT/'normal_pool.jsonl',base);write_jsonl(OUT/'reverse_pool.jsonl',rev)
    plans=[]
    for seed in SEEDS:
        events,bits=schedule(base,seed);rece=read_json(P9.RUN/f'branches/seed{seed}_normal/complete.json');start=read_json(P9.RUN/f'branches/seed{seed}_normal/start.json');logs=read_jsonl(P9.RUN/f'branches/seed{seed}_normal/training.jsonl')
        assert rece['optimizer_calls']==18 and [x['optimizer_calls'] for x in logs]==list(range(1,19))
        assert start['restored_train_state']==start['source_full_state']['semantic_sha256']==rece['start_state']
        assert sha256_file(P9.RUN/f'branches/seed{seed}_normal/checkpoint/adapter_model.safetensors')==rece['adapter_sha256']
        totals=collections.Counter();perstep=[];views=collections.defaultdict(list)
        for offset in range(0,144,8):
            sums=collections.Counter()
            for e in events[offset:offset+8]:
                af=normal_f[e['index']];bf=(rev_f if e['view'] else normal_f)[e['index']]
                assert len(af['input_ids'])==len(bf['input_ids']) and af['labels']==bf['labels']
                sums['input_tokens']+=len(bf['input_ids']);sums['supervised_tokens']+=sum(x!=-100 for x in bf['labels'])
                if base[e['index']]['tool_family']=='file':views[e['episode_id']].append(e['view'])
            totals.update(sums);perstep.append(dict(step=offset//8+1,**sums))
        assert all(sorted(x)==[0,1] for x in views.values()) and len(views)==48
        assert dict(totals)==dict(input_tokens=53734,supervised_tokens=7486)
        assert all(totals[k]==rece[k] for k in ['input_tokens','supervised_tokens'])
        for e in [0,1]:
            for n in [2,3,4]:
                selected={base[x['index']]['case']:x['view'] for x in events if x['epoch']==e and base[x['index']]['tool_family']=='file' and base[x['index']]['n_matches']==n}
                assert sum(selected.values())==4 and len(selected)==8
        plan=dict(seed=seed,arm='paired_two_view',source_full_state=str(P8.ckpt(seed)/'full_state.pt'),source_full_state_receipt=str(P8.ckpt(seed)/'full_state_receipt.json'),source_state_semantic_sha256=start['restored_train_state'],reuse_ordinary_checkpoint=str(P9.RUN/f'branches/seed{seed}_normal/checkpoint'),source_config=str(ROOT/f'runs_phase2/A_seed{seed}/config.json'),learning_rate=start['new_lr'],microsteps=144,gradient_accumulation=8,optimizer_updates=18,epochs=2,bits=bits,events=events,per_step_budget=perstep,**totals)
        write_json(OUT/f'plan_seed{seed}.json',plan);plans.append(plan)
    dev=read_jsonl(P9.DATA/'dev.jsonl');holdout=new_file_holdout();sql,sqlchecks=sql_retention();side=copy.deepcopy(read_jsonl(P9.DATA/'sideeffects.jsonl'))+sql
    write_jsonl(OUT/'dev.jsonl',dev);write_jsonl(OUT/'holdout.jsonl',holdout);write_jsonl(OUT/'sideeffects.jsonl',side)
    sets=[]
    for rr in [base,dev,holdout]:
        ff=[r for r in rr if r['tool_family']=='file'];sets.append({k:set(r['prompt'] if k=='prompt' else r['expected_arguments']['path'] if k=='path' else r['expected_arguments']['pattern'] if k=='marker' else r['expected_final_answer'] for r in ff) for k in ['prompt','path','marker','answer']})
    for key in ['prompt','path','marker','answer']:assert not any(sets[i][key]&sets[j][key] for i in range(3) for j in range(i))
    gold=0
    for a in base+rev+dev+holdout+side:
        db=a.get('evaluation_db',a.get('p9_db',str(P9.DB)));g=_evaluate_tool_prediction(a,canonical_json({'tool':a['expected_tool'],'arguments':a['expected_arguments']}),db,str(P9.CAL))
        assert all(g[k] for k in ['tool_correct','arguments_correct','execution_success']),a['episode_id'];gold+=1
    assert str(inspect.signature(P9.train))=='(seed, arm)'
    source=inspect.getsource(P9.train)
    for contract in ['FS.restore','FS.capture','len(events)==previous+1','optimizer_calls==18','len(order)==144','loss/8']:assert contract in source,contract
    # Real CPU collator/autograd/optimizer control flow, never the research model.
    class Tiny(torch.nn.Module):
        def __init__(self):
            super().__init__();self.emb=torch.nn.Embedding(31,8);self.drop=torch.nn.Dropout(.1);self.head=torch.nn.Linear(8,31)
        def forward(self,batch):
            z=self.head(self.drop(self.emb(batch['input_ids']%31)));y=batch['labels'];y=torch.where(y!=-100,y%31,y)
            return torch.nn.functional.cross_entropy(z[:,:-1].reshape(-1,31),y[:,1:].reshape(-1),ignore_index=-100)
    torch.manual_seed(101117);model=Tiny();opt=torch.optim.AdamW(model.parameters(),lr=1e-4);scaler=torch.amp.GradScaler('cpu',enabled=False);coll=DataCollator(tok);updates=0
    features=[(rev_f if e['view'] else normal_f)[e['index']] for e in plans[0]['events']]
    for i,feature in enumerate(features):
        batch=coll([feature]);assert all(v.device.type=='cpu' for v in batch.values());(model(batch)/8).backward()
        if (i+1)%8==0:opt.step();opt.zero_grad(set_to_none=True);updates+=1
    assert updates==18
    state=FS.capture(model,opt,scaler);digest=FS.digest(state)
    def next_update():
        model(coll([features[0]])).backward();opt.step();opt.zero_grad(set_to_none=True);return FS.digest(FS.capture(model,opt,scaler))
    expected=next_update();model.eval();FS.restore(state,model,opt,scaler);assert FS.digest(FS.capture(model,opt,scaler))==digest
    assert next_update()==expected,'CPU next update after restore differs'
    checks=dict(passed=True,cpu_only=True,gpu_model_loads=0,gpu_generation_calls=0,gpu_optimizer_updates=0,inherited_frozen_files_verified=len(old['hashes']),tokenizer=str(tok.name_or_path),source_train_signature='(seed, arm)',per_example_input_and_full_labels_exact=True,per_optimizer_batch_budget_exact=True,microsteps=144,optimizer_updates_per_branch=18,branch_input_tokens=53734,branch_supervised_tokens=7486,new_branches=3,total_new_updates=54,total_new_input_tokens=161202,total_new_supervised_tokens=22458,gold_tool_execution_checks=gold,SQL=sqlchecks,train_dev_test_exact_disjoint=True,holdout_wording_match_count_cells=12,holdout_rows=24,side_rows=12,dev_generation_calls_planned=72,formal_generation_calls_planned=576,total_generation_calls_planned=648,toy_cpu_microsteps=144,toy_cpu_main_optimizer_calls=18,toy_cpu_restore_test_optimizer_calls=2,fullstate_cpu_roundtrip_and_identical_next_update=True,gpu_native_optimizer_e2e_verified=False,remaining_gate='No GPU runner or launch authorization; need independent dev trigger and first real E2E')
    write_json(OUT/'cpu_acceptance.json',checks)
    files=list(OUT.glob('*'))+[Path(__file__),ROOT/'P10_PREREG_DRAFT_20261117_twoview_ZH.md']
    write_json(OUT/'manifest.json',dict(stage='CPU candidate only; not GPU launch ready',created=time.strftime('%F %T %z'),hashes={str(p.relative_to(ROOT)):sha256_file(p) for p in files if p.is_file()},inherited_P9_hashes=old['hashes']))
    print(json.dumps(checks,ensure_ascii=False,indent=2))

if __name__=='__main__':build()