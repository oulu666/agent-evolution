"""Factorial, inference-only diagnosis after P8; no optimizer or model mutation."""
from __future__ import annotations
import argparse,collections,copy,json,random,re,sqlite3,statistics,time
from pathlib import Path
from .utils import read_json,read_jsonl,write_json,write_jsonl,sha256_file,ensure_dir,append_jsonl,canonical_json
from . import p8_decision_data_20261115 as P8
ROOT=P8.ROOT;DATA=ROOT/'data_ext_p81_diagnosis_20261116';RUN=ROOT/'runs_ext_p81_diagnosis_20261116';SEEDS=P8.SEEDS
CAL=str(ROOT/'data_phase2/fixtures/calendar.json')

def log(s):print(time.strftime('%F %T %z'),s,flush=True)
def ckpt(seed,arm):return P8.ckpt(seed) if arm=='decision' else P8.oldck(seed)
def make_row(eid,family,prompt,tool,args,env,db,spec):
    from .data.generate import _observation,_schemas,build_system_prompt
    from .round2_data import _messages
    from .research_data import project_answer
    obs=_observation(family,tool,args,env,str(db),CAL);assert json.loads(obs)['ok']
    answer=project_answer(json.loads(obs)['result'],spec);system=build_system_prompt(family,_schemas(family,str(db),CAL))
    return dict(episode_id=eid,tool_family=family,skill_labels=[family+'.diagnosis'],split='p81_diagnostic',prompt=prompt,system=system,environment=env,expected_tool=tool,expected_arguments=args,expected_observation=obs,expected_final_answer=answer,answer_spec=spec,messages=_messages(system,prompt,tool,args,obs,answer))

def build():
    if DATA.exists():raise RuntimeError('New roots required')
    ensure_dir(DATA);ensure_dir(RUN/'logs');db=DATA/'probe.sqlite'
    tables=['p81_zero','p81_few','p81_ties']
    with sqlite3.connect(db) as c:
        for ti,tab in enumerate(tables):
            c.execute(f'CREATE TABLE {tab}(id INTEGER PRIMARY KEY,name TEXT,score REAL)')
            vals=[(i,f'p81_entity_{ti}_{i}',(20+i if ti==0 else 80 if ti==2 or i in [2,5] else 20+i)) for i in range(1,7)]
            c.executemany(f'INSERT INTO {tab} VALUES (?,?,?)',vals)
            c.execute(f'CREATE INDEX idx_{tab} ON {tab}(score DESC,id DESC)')
    files=[]
    for case in range(6):
        n=2+case%3;path=f'p81/record_{case}.txt';word=f'p81key{case}'
        numbers=[2,4,6,8][:n];texts={j:f'entry {j}: {word} value p81_{case}_{j}' for j in numbers}
        lines=[texts.get(j,f'entry {j}: neutral') for j in range(1,10)];env={'files':{path:'\n'.join(lines)+'\n'}}
        for which in ['first','last']:
            for wording in ['natural','explicit_line']:
                prompt=(f'Return the full {which} matching line in {path} containing {word!r}.' if wording=='natural' else f'Search {path} for {word!r}. Among the matching file lines, select the one with the {"smallest" if which=="first" else "largest"} line number. Return only its complete text.')
                for order in ['ascending','reversed']:
                    r=make_row(f'p81-file-{case}-{which}-{wording}-{order}','file',prompt,'file_search',{'path':path,'pattern':word},env,db,{'kind':'match','index':0 if which=='first' else -1})
                    obs=json.loads(r['expected_observation']);matches=obs['result']
                    if order=='reversed':obs['result']=list(reversed(matches))
                    r.update(case=case,n_matches=n,intent=which,wording=wording,presentation=order,presented_observation=canonical_json(obs),min_line_answer=texts[numbers[0]],max_line_answer=texts[numbers[-1]],first_presented_answer=obs['result'][0]['text'])
                    files.append(r)
    sql=[]
    for case,tab in zip(['zero','few','ties'],tables):
        for operation in ['sort','filter','filter_sort','filter_sort_tie']:
            for wording in ['natural','structured']:
                where=' WHERE score > 50' if operation!='sort' else ''
                order='' if operation=='filter' else ' ORDER BY score DESC'+(', id ASC' if operation=='filter_sort_tie' else '')
                limit='' if operation=='filter' else ' LIMIT 4'
                query=f'SELECT name FROM {tab}'+where+order+limit
                filtering=' whose score is above 50' if where else ''
                natural=(f'From {tab}(id, name, score), return the names{filtering}.' if operation=='filter' else f'From {tab}(id, name, score), return up to four names{filtering}, highest score first'+(', with smaller id first when scores tie.' if operation=='filter_sort_tie' else '.'))
                structured=f'Table: {tab}(id, name, score). Output column: name. Filter: {"score > 50" if where else "none"}. Ordering: {"none" if not order else "score descending, then id ascending" if operation=="filter_sort_tie" else "score descending"}. Limit: {"none" if not limit else "4"}. Return names as a JSON list.'
                r=make_row(f'p81-db-{case}-{operation}-{wording}','database',natural if wording=='natural' else structured,'db_query',{'sql':query},{},db,{'kind':'rows_first'})
                r.update(case=case,operation=operation,wording=wording);sql.append(r)
    train=read_jsonl(P8.DATA/'train.jsonl');index={r['episode_id']:r for r in train};selected={}
    for seed in SEEDS:
        ids=[x['episode_id'] for x in read_json(P8.planpath(seed))['items'] if x.get('target') and x['family'] in ['file','database'] and x.get('skill') in ['file.search_last','db.filter_cmp_top']]
        selected[str(seed)]=[index[eid] for eid in ids];assert len(ids)==len(set(ids))
    write_jsonl(DATA/'file.jsonl',files);write_jsonl(DATA/'sql.jsonl',sql);write_json(DATA/'seen_train.json',selected)
    # New prompts, entities; same abstract operations. Check gold by actual execution.
    from .sft.evaluate import _evaluate_tool_prediction
    oldprompts={r['prompt'] for r in read_jsonl(P8.DATA/'train.jsonl')+read_jsonl(P8.DATA/'dev.jsonl')+read_jsonl(P8.DATA/'holdout.jsonl')}
    assert not oldprompts&{r['prompt'] for r in files+sql}
    for r in files+sql:
        g=_evaluate_tool_prediction(r,canonical_json({'tool':r['expected_tool'],'arguments':r['expected_arguments']}),str(db),CAL)
        assert g['execution_success'] and g['arguments_correct']
    assert len(files)==48 and len(sql)==24
    total=3*(len(files)+len(sql))+4*sum(map(len,selected.values()))
    refs=[Path(__file__),ROOT/'P81_PREREG_20261116_ZH.md',ROOT/'fac_tinyagent/sft/evaluate.py',ROOT/'fac_tinyagent/sft/dataset.py',ROOT/'fac_tinyagent/metrics.py',P8.DATA/'train.jsonl',P8.DATA/'fixtures/train.sqlite']
    refs += [ckpt(s,a)/'adapter_model.safetensors' for s in SEEDS for a in ['original','decision']]
    refs += [P8.planpath(s) for s in SEEDS]
    refs += [p for p in DATA.rglob('*') if p.is_file()]
    write_json(DATA/'manifest.json',{'created':time.strftime('%F %T %z'),'files':{str(p.relative_to(ROOT)):sha256_file(p) for p in refs},'file_conditions':48,'sql_conditions':24,'seen_train_per_seed':{k:len(v) for k,v in selected.items()},'planned_generation_calls':total,'optimizer_steps':0})
    log('FROZEN '+str(total)+' generation calls')

def verify():
    for p,h in read_json(DATA/'manifest.json')['files'].items():assert sha256_file(ROOT/p)==h,p

def audit():
    gold={r['episode_id']:r for r in read_jsonl(P8.DATA/'holdout.jsonl')};out=[]
    for path in sorted((P8.RUN/'evaluation').glob('*/**/results.jsonl')):
        if path.parent.name not in ['file','database']:continue
        for r in read_jsonl(path):
            g=gold.get(r['episode_id'])
            if g is None or g['skill'] not in ['file.search_last','db.filter_cmp_top']:continue
            x={'model':path.parts[-3],'id':r['episode_id'],'skill':g['skill'],'case':g.get('case'),'tool':r['predicted_tool'],'joint':r['joint_success']}
            if g['skill']=='file.search_last':
                ms=json.loads(g['expected_observation'])['result'];x.update(first=r['predicted_answer']==ms[0]['text'],last=r['predicted_answer']==ms[-1]['text'],other=r['predicted_answer'] not in [m['text'] for m in ms])
            else:
                q=r['predicted_arguments'].get('sql','');expected=g['expected_arguments']['sql'];x.update(predicted_sql=q,expected_sql=expected,has_where=bool(re.search(r'\bWHERE\b',q,re.I)),has_tie=bool(re.search(r'\bid\s+ASC\b',q,re.I)),has_limit=bool(re.search(r'\bLIMIT\b',q,re.I)),exact=r['arguments_correct'],execution=r['execution_success'])
            out.append(x)
    write_json(RUN/'p8_error_audit.json',out);log('Archived P8 error audit '+str(len(out)))

def queue():
    from .sft.evaluate import load_eval_model,generate_with_usage,parse_final_answer,_evaluate_tool_prediction,free_model
    from .replay_study import config_for
    from .metrics import answers_equal,joint_success
    import hashlib,torch
    def adapter_hash(model):
        h=hashlib.sha256();count=0
        for name,p in sorted(model.named_parameters()):
            if 'lora_' in name:
                h.update(name.encode());h.update(p.detach().contiguous().view(torch.uint8).cpu().numpy().tobytes());count+=1
        assert count>0,'No adapter tensors checked'
        return h.hexdigest()
    verify();files=read_jsonl(DATA/'file.jsonl');sql=read_jsonl(DATA/'sql.jsonl');seen=read_json(DATA/'seen_train.json')
    for seed in SEEDS:
        for arm in ['decision','original']:
            path=RUN/f'seed{seed}_{arm}.jsonl';done={r['id'] for r in read_jsonl(path)} if path.exists() else set()
            jobs=[('seen',r) for r in seen[str(seed)]]
            if arm=='decision':jobs += [('file',r) for r in files]+[('sql',r) for r in sql]
            random.Random(seed+8100).shuffle(jobs)
            jobs=[(kind,r) for kind,r in jobs if kind+':'+r['episode_id'] not in done]
            if not jobs:continue
            if (RUN/'logs/STOP').exists():raise RuntimeError('P81 STOP')
            cfg=config_for('A',seed,batch_size=1);model,tok=load_eval_model(cfg,str(ckpt(seed,arm)));before=adapter_hash(model)
            try:
                for kind,r in jobs:
                    if (RUN/'logs/STOP').exists():raise RuntimeError('P81 STOP')
                    rid=kind+':'+r['episode_id'];base=r['messages'][:2]
                    item={'id':rid,'seed':seed,'arm':arm,'kind':kind,'episode_id':r['episode_id'],'meta':{k:r[k] for k in ['case','intent','wording','presentation','operation','n_matches'] if k in r}}
                    if kind=='file':
                        messages=base+[r['messages'][2],{'role':'user','content':'TOOL RESULT:\n'+r['presented_observation']}]
                        raw,usage=generate_with_usage(model,tok,messages,128);parsed,pred=parse_final_answer(raw)
                        item.update(answer_raw=raw,predicted_answer=pred,correct=bool(parsed and answers_equal(r['expected_final_answer'],pred)),first_presented=pred==r['first_presented_answer'],min_line=pred==r['min_line_answer'],max_line=pred==r['max_line_answer'],usage=[usage])
                    else:
                        raw,usage=generate_with_usage(model,tok,base,128)
                        db=P8.DATA/'fixtures/train.sqlite' if kind=='seen' else DATA/'probe.sqlite'
                        res=_evaluate_tool_prediction(r,raw,str(db),CAL);item.update(res);item['usage']=[usage]
                        if kind=='seen':
                            messages=base+[{'role':'assistant','content':raw or '{}'},{'role':'user','content':'TOOL RESULT:\n'+res['observation']}]
                            answer,u=generate_with_usage(model,tok,messages,128);parsed,pred=parse_final_answer(answer)
                            item.update(answer_raw=answer,predicted_answer=pred,final_correct=bool(parsed and answers_equal(r['expected_final_answer'],pred)));item['joint_success']=joint_success(item);item['usage'].append(u);item['skill']=r['skill']
                        else:
                            from .p81_semantics import semantic_sql_result
                            semantic=semantic_sql_result(r,res['observation'],db)
                            q=res['predicted_arguments'].get('sql','')
                            item.update(semantic_execution=semantic,has_where=bool(re.search(r'\bWHERE\b',q,re.I)),has_tie=bool(re.search(r'\bid\s+ASC\b',q,re.I)),has_limit=bool(re.search(r'\bLIMIT\b',q,re.I)))
                    append_jsonl(path,item);done.add(rid)
                    if len(done)%12==0:log(f'{seed} {arm} completed={len(done)}')
                assert adapter_hash(model)==before
                write_json(RUN/f'seed{seed}_{arm}_complete.json',{'complete':True,'rows':len(done),'adapter_sha256':sha256_file(ckpt(seed,arm)/'adapter_model.safetensors'),'parameter_hash_unchanged':True,'optimizer_steps':0})
            finally:free_model(model)
    verify();log('QUEUE COMPLETE')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',choices=['build','verify','audit','queue'],required=True);a=p.parse_args();globals()[a.phase]()
