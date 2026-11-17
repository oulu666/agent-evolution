"""P7 bounded optimizer-response diagnosis; old experiments are read-only."""
from __future__ import annotations
import argparse, collections, copy, json, random, sqlite3, statistics, time
from pathlib import Path
from . import p7_fullstate_20261115 as FS
from . import p6_devplan as D
from .utils import read_json, read_jsonl, write_json, write_jsonl, sha256_file, ensure_dir
ROOT=D.ROOT
DATA=ROOT/'data_ext_p7_response'
RUN=ROOT/'runs_ext_p7_statefix_20261115'
SKILLS=D.SKILLS
SEEDS=D.SEEDS

def log(s): print(time.strftime('%F %T %z'),s,flush=True)

def build():
    if DATA.exists(): raise RuntimeError('P7 data already exists')
    ensure_dir(DATA/'fixtures'); ensure_dir(RUN)
    db=DATA/'fixtures/check.sqlite'
    names=['p7_assets','p7_members','p7_results']
    with sqlite3.connect(db) as c:
        for ti,tab in enumerate(names):
            c.execute(f'CREATE TABLE {tab}(id INTEGER PRIMARY KEY,name TEXT,score REAL)')
            c.executemany(f'INSERT INTO {tab} VALUES (?,?,?)',[(i,f'p7_{ti}_{i}',(i*17+ti*11)%83+10+i/100) for i in range(1,16)])
    from .data.generate import _observation,_schemas,build_system_prompt
    from .round2_data import _messages
    from .research_data import project_answer
    rows=[]
    def add(skill,i,prompt,tool,args,env,spec):
        family={'db':'database','file':'file','py':'python'}[skill.split('.')[0]]
        cal=str(ROOT/'data_phase2/fixtures/calendar.json')
        obs=_observation(family,tool,args,env,str(db),cal)
        answer=project_answer(json.loads(obs)['result'],spec)
        system=build_system_prompt(family,_schemas(family,str(db),cal))
        rows.append(dict(episode_id=f'p7-check-{skill}-{i}',tool_family=family,skill=skill,skill_labels=[skill],split='p7_check',prompt=prompt,system=system,environment=env,expected_tool=tool,expected_arguments=args,expected_observation=obs,expected_final_answer=answer,answer_spec=spec,messages=_messages(system,prompt,tool,args,obs,answer),evaluation_only=True,selection_allowed=False))
    for i in range(2):
        add(SKILLS[0],i,['Give the names of all tables in this database as a JSON array.','Inspect the database inventory and provide all table names in a JSON list.'][i],'db_list_tables',{}, {},{'kind':'identity'})
        tab=names[i];k=i+1;v=33+i*10
        add(SKILLS[1],i,f'From {tab}(id, name, score), select the {k} names with highest score among rows with score > {v}; resolve ties by smaller id. Respond with a JSON list.','db_query',{'sql':f'SELECT name FROM {tab} WHERE score > {v} ORDER BY score DESC, id ASC LIMIT {k}'},{},{'kind':'rows_first'})
        path=f'p7_check/notes_{i}.txt';word=f'p7needle{i}'
        lines=[f'entry {j}: {word}' if j in [1,3,5][:i+2] else f'entry {j}: ordinary' for j in range(1,7)]
        add(SKILLS[2],i,f'Search {path} for {word!r}. Output the entire last matching line, preserving its text.','file_search',{'path':path,'pattern':word},{'files':{path:'\n'.join(lines)+'\n'}},{'kind':'match','index':-1})
        vals=([114,137,101,152,128,169,143] if i==0 else [218,201,245,231,207,264,252])
        add(SKILLS[3],i,f'Consider the readings {", ".join(map(str,vals))}. Sort them in ascending order and report only the middle reading.','stats_median',{'values':vals},{},{'kind':'identity'})
    write_jsonl(DATA/'check.jsonl',rows)
    dev=read_jsonl(D.DATA/'dev/rows.jsonl')
    pools={f:read_jsonl(ROOT/'data_ext_e4/pool'/f'{f}.jsonl') for f in ['file','database','python']}
    old=[*dev,*read_jsonl(D.DATA/'holdout/rows.jsonl'),*[r for rs in pools.values() for r in rs]]
    assert not {r['prompt'] for r in rows}&{r['prompt'] for r in old}
    assert not {D.digest(r['messages']) for r in rows}&{D.digest(r['messages']) for r in old}
    plans={}
    for seed in SEEDS:
        order=D.candidate_order(read_json(D.DATA/'candidates.json'),seed)
        q=read_json(D.planpath(seed,'balanced_uniform'))
        bg=next(x for x in q['items'] if not x['target'])
        actions={k:[v[j%len(v)] for j in range(2)] for k,v in order.items()}
        actions['background']=[bg,bg]
        arm_order=list(actions);random.Random(seed+700).shuffle(arm_order)
        plans[str(seed)]={'actions':actions,'arm_order':arm_order}
    write_json(DATA/'plans.json',plans)
    refs=[Path(__file__),ROOT/'P7_PROTOCOL_20261115_ZH.md',D.DATA/'dev/rows.jsonl',D.DATA/'candidates.json',ROOT/'data_phase2/calendar/train.jsonl',ROOT/'fac_tinyagent/sft/evaluate.py',ROOT/'fac_tinyagent/metrics.py',ROOT/'fac_tinyagent/replay_train.py']
    refs += [ROOT/f'data_ext_e4/pool/{f}.jsonl' for f in pools]
    refs += [ROOT/f'runs_ext_e4/prefixes/A_seed{s}/{f}' for s in SEEDS for f in ['manifest.json','training_state.pt']]
    refs += [D.RUNS/f'calibration/A_seed{s}.json' for s in SEEDS]
    refs += [ROOT/f'runs_phase2/A_seed{s}/checkpoints/stage_03_python/adapter_model.safetensors' for s in SEEDS]
    refs += [p for p in DATA.rglob('*') if p.is_file()]
    write_json(DATA/'manifest.json',{'created':time.strftime('%F %T %z'),'files':{str(p.relative_to(ROOT)):sha256_file(p) for p in refs},'new_check_n':8,'planned_optimizer_steps':30,'planned_generation_episodes':144})
    log('P7 data and design frozen')

def verify():
    for p,h in {**read_json(DATA/'manifest.json')['files'],**read_json(RUN/'repair_manifest.json')['files']}.items():
        assert sha256_file(ROOT/p)==h,p

def audit():
    from .sft.evaluate import _evaluate_tool_prediction,parse_final_answer
    from .metrics import answers_equal,joint_success
    from .research_data import project_answer
    hold=read_jsonl(D.DATA/'holdout/rows.jsonl'); gold={r['episode_id']:r for r in hold}
    gold_checks=[]
    for rows,db in [(hold,D.fixture('holdout')),(read_jsonl(DATA/'check.jsonl'),DATA/'fixtures/check.sqlite')]:
        for row in rows:
            result=_evaluate_tool_prediction(row,json.dumps({'tool':row['expected_tool'],'arguments':row['expected_arguments']}),str(db),str(ROOT/'data_phase2/fixtures/calendar.json'))
            projected=project_answer(json.loads(result['observation'])['result'],row['answer_spec'])
            assert result['execution_success'] and answers_equal(projected,row['expected_final_answer'])
            if row['skill']==SKILLS[2]:
                args=row['expected_arguments'];lines=row['environment']['files'][args['path']].splitlines()
                assert [line for line in lines if args['pattern'] in line][-1]==row['expected_final_answer']
            if row['skill']==SKILLS[3]: assert statistics.median(row['expected_arguments']['values'])==row['expected_final_answer']
            gold_checks.append(row['episode_id'])
    counts={k:collections.Counter() for k in SKILLS};details=[]
    for path in sorted((ROOT/'runs_ext_p6_devplan_attempt2/evaluation').glob('*/p6_*/results.jsonl')):
        for r in read_jsonl(path):
            g=gold[r['episode_id']];k=g['skill'];c=counts[k];c['n']+=1
            parsed,pred=parse_final_answer(r['answer_raw'])
            assert bool(parsed and answers_equal(g['expected_final_answer'],pred))==r['final_correct']
            assert joint_success(r)==r['joint_success']
            for key in ['tool_correct','arguments_correct','execution_success','final_correct','joint_success']:c[key]+=int(r[key])
            c['tool:'+str(r['predicted_tool'])]+=1
            if k==SKILLS[2]:
                matches=json.loads(g['expected_observation'])['result']
                c['first_match_answer']+=int(pred==matches[0]['text'])
                c['last_match_answer']+=int(pred==matches[-1]['text'])
            details.append({'branch':path.parts[-3],**r})
    assert sum(c['n'] for c in counts.values())==432
    cross={}
    for seed in SEEDS:
        old=read_json(D.RUNS/f'calibration/A_seed{seed}.json')
        dots=[v for k,row in old['dotmatrix'].items() for j,v in row.items() if j!=k]
        cross[str(seed)]={'negative_cross_pairs':sum(v<0 for v in dots),'total_cross_pairs':len(dots),'calibration':old}
    write_json(RUN/'audit.json',{'gold_checks':len(gold_checks),'scoring_rows_checked':len(details),'counts':counts,'cross_gradients':cross,'scoring_mismatches':0})
    log('P7 CPU audit '+json.dumps(counts))

def queue():
    import torch
    from bitsandbytes.optim import PagedAdamW8bit
    from .replay_train import load_prefix,_training_state_hash
    from .sft.train import load_tokenizer,load_base_model,_attach_adapter
    from .sft.dataset import tokenize_episode,DataCollator,assistant_spans
    from .sft.evaluate import evaluate_family,free_model
    from .replay_study import config_for
    from .e4_run import start_adapter
    verify()
    dev=read_jsonl(D.DATA/'dev/rows.jsonl');check=read_jsonl(DATA/'check.jsonl')
    pools={f:read_jsonl(ROOT/'data_ext_e4/pool'/f'{f}.jsonl') for f in ['file','database','python']}
    cal=read_jsonl(ROOT/'data_phase2/calendar/train.jsonl');plans=read_json(DATA/'plans.json')
    for seed in SEEDS:
        if (RUN/f'seed{seed}/complete.json').exists():continue
        cfg=config_for('A',seed,batch_size=1);tok=load_tokenizer(cfg);model,dtype=load_base_model(cfg);model=_attach_adapter(model,cfg,str(start_adapter(seed)))
        params=[p for p in model.parameters() if p.requires_grad];collator=DataCollator(tok)
        prefix=ROOT/f'runs_ext_e4/prefixes/A_seed{seed}';man=read_json(prefix/'manifest.json');order=man['metadata']['order']
        root=ensure_dir(RUN/f'seed{seed}'); costs=collections.Counter();started=time.time()
        reused=read_json(RUN/'repair_manifest.json')['reuse'].get(str(seed),{})
        reused_arms=set(reused.get('arms',[]))
        def safe():
            if (RUN/'logs/STOP').exists(): raise RuntimeError('P7 STOP')
        def ft(row):return tokenize_episode(row,tok,1024)
        def batch(row):return {k:v.to('cuda') for k,v in collator([ft(row)]).items()}
        def vec():return torch.cat([p.detach().float().cpu().reshape(-1) for p in params])
        def restore():
            opt=PagedAdamW8bit(params,lr=1e-4);scaler=torch.amp.GradScaler('cuda',enabled=dtype==torch.float16)
            st=load_prefix(prefix,model,opt,scaler,man['metadata'])
            assert _training_state_hash(model)==man['parameter_hash'];costs['restorations']+=1
            return opt,scaler
        def gradient(rows):
            model.eval();avg=None
            for row in rows:
                safe();model.zero_grad(set_to_none=True)
                loss=model(**batch(row)).loss;assert torch.isfinite(loss);loss.backward()
                g=torch.cat([p.grad.detach().float().cpu().reshape(-1) if p.grad is not None else torch.zeros(p.numel()) for p in params])
                avg=g if avg is None else avg+g;costs['diagnostic_backward']+=1
            model.zero_grad(set_to_none=True);return avg/len(rows)
        def nll(rows):
            model.eval();out=[]
            for row in rows:
                safe();features=ft(row);b={k:v.to('cuda') for k,v in collator([features]).items()}
                with torch.no_grad():
                    output=model(**b)
                    ce=torch.nn.functional.cross_entropy(output.logits[0,:-1].float(),b['labels'][0,1:],reduction='none',ignore_index=-100)
                    spans=assistant_spans(features['input_ids'],tok);assert len(spans)==2
                    values=[float(ce[a-1:z-1].mean()) for a,z in spans]
                out.append({'id':row['episode_id'],'skill':row['skill'],'nll':float(output.loss),'tool_nll':values[0],'final_nll':values[1]});costs['nll_forward']+=1
            return out
        def measure(tag,generation=False):
            out=ensure_dir(root/tag)
            state=FS.capture(model,opt,scaler)
            binding=FS.save(state,out/'full_state.pt')
            write_json(out/'full_state_receipt.json',binding)
            disk_state=FS.load(out/'full_state.pt',binding)
            FS.restore(disk_state,model,opt,scaler)
            costs['exact_disk_restore_checks']+=1
            if (out/'nll.json').exists():
                data=read_json(out/'nll.json')
                assert data['parameter_hash']==_training_state_hash(model), 'Reconstructed state differs: '+tag
            else:
                data={'dev':nll(dev),'check':nll(check),'parameter_hash':_training_state_hash(model)}
                write_json(out/'nll.json',data)
            if generation:
                model.eval()
                for family in ['database','file','python']:
                    rows=[r for r in check if r['tool_family']==family]
                    if (out/family/'stage_report.json').exists():
                        assert len(read_jsonl(out/family/'results.jsonl'))==len(rows)
                        continue
                    if (out/family).exists():
                        target=RUN/'interruptions'/f'{seed}_{tag}_{family}'
                        assert target.resolve().is_relative_to(RUN.resolve()) and (out/family).resolve().is_relative_to(RUN.resolve())
                        ensure_dir(target.parent); (out/family).rename(target)
                    evaluate_family(model,tok,rows,cfg,{'name':f'P7_{seed}_{tag}','index':0,'family':family},out/family,str(DATA/'fixtures/check.sqlite'),str(ROOT/'data_phase2/fixtures/calendar.json'))
                    costs['generation_episodes']+=len(rows)
            assert read_json(out/'nll.json')['parameter_hash']==_training_state_hash(model),'measurement and persisted model differ'
            FS.restore(disk_state,model,opt,scaler)
            costs['exact_disk_restore_checks']+=1
            write_json(out/'state_binding.json',{'parameter_hash':_training_state_hash(model),'checkpoint':binding,'full_model_optimizer_scaler_rng_modes_exact':True})
            log(f'MEASURE {seed} {tag} FULL_STATE_EXACT')
            return data
        opt,scaler=restore();basevec=vec();measure('baseline',True)
        gd=gradient(dev);assert _training_state_hash(model)==man['parameter_hash']
        action_meta=read_json(root/'action_meta.json') if (root/'action_meta.json').exists() else {};plan=plans[str(seed)]
        for arm in plan['arm_order']:
            actions=plan['actions'][arm];rs=[pools[a['family']][a['row_index']] for a in actions]
            if arm in reused_arms and arm in action_meta and all((root/f'{arm}_2'/f/'stage_report.json').exists() for f in ['database','file','python']):
                log(f'REUSE COMPLETE {seed} {arm}');continue
            opt,scaler=restore()
            gs=gradient([rs[0]])
            action_meta[arm]={'single_gradient_norm':float(gs.norm()),'single_raw_dot':float(torch.dot(gd,gs)),'single_unit_dot':float(torch.dot(gd,gs)/(gs.norm()+1e-12)),'input_tokens':[len(ft(r)['input_ids']) for r in rs]}
            # Measurement must not consume RNG or optimizer state before branching.
            opt,scaler=restore()
            replay_tokens=0
            for dose in [1,2]:
                assert not (root/f'{arm}_{dose}'/'receipt.json').exists(),'partial new attempt: resume only from full persisted state, never replay old measurement'
                reconstruct=False
                # Restore RNG after any measurement between optimizer steps.
                if dose==2:
                    random.setstate(rng_python);torch.set_rng_state(rng_cpu);torch.cuda.set_rng_state_all(rng_cuda)
                model.train();opt.zero_grad(set_to_none=True)
                common=[cal[order[80+(dose-1)*7+j]] for j in range(7)]
                trainrows=common+[rs[dose-1]]
                for row in trainrows:
                    safe()
                    with torch.autocast(device_type='cuda',dtype=dtype):loss=model(**batch(row)).loss
                    assert torch.isfinite(loss);scaler.scale(loss/8).backward();costs['reconstruction_training_backward' if reconstruct else 'training_backward']+=1;costs['reconstruction_input_tokens' if reconstruct else 'training_input_tokens']+=len(ft(row)['input_ids'])
                scaler.step(opt);scaler.update();opt.zero_grad(set_to_none=True);costs['reconstruction_optimizer_steps' if reconstruct else 'optimizer_steps']+=1
                rng_python=random.getstate();rng_cpu=torch.get_rng_state();rng_cuda=torch.cuda.get_rng_state_all()
                replay_tokens+=len(ft(rs[dose-1])['input_ids'])
                dx=vec()-basevec
                receipt={'seed':seed,'arm':arm,'dose':dose,'actual_optimizer_steps':dose,'replay_input_tokens':replay_tokens,'delta_norm':float(dx.norm()),'linear_predicted_dev_drop':-float(torch.dot(gd,dx)),'common_calendar_ids':[r['episode_id'] for r in common],'replay_id':rs[dose-1]['episode_id'],'prefix_hash':man['parameter_hash']}
                receipt_path=root/f'{arm}_{dose}'/'receipt.json'
                if receipt_path.exists():
                    old=read_json(receipt_path)
                    for key in ['seed','arm','dose','replay_input_tokens','replay_id','common_calendar_ids','prefix_hash']:assert receipt[key]==old[key]
                else:write_json(receipt_path,receipt)
                measure(f'{arm}_{dose}',dose==2)
            write_json(root/'action_meta.json',action_meta)
        restore();assert _training_state_hash(model)==man['parameter_hash'];verify()
        assert costs['optimizer_steps']==2*(5-len(reused_arms))
        assert costs['generation_episodes']==(0 if reused.get('baseline') else 8)+8*(5-len(reused_arms))
        costs['reused_optimizer_steps']=2*len(reused_arms)
        costs['reused_generation_episodes']=(8 if reused.get('baseline') else 0)+8*len(reused_arms)
        write_json(root/'complete.json',{'seed':seed,'costs':costs,'seconds':time.time()-started,'prefix_restored':True,'frozen_inputs_unchanged':True})
        free_model(model);del model,params,opt,scaler,gd,gs,basevec
    log('P7 STATEFIX QUEUE COMPLETE')
    from .p7_statefix_report_20261115 import finalize
    finalize()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['build','verify','audit','queue']);args=p.parse_args();globals()[args.phase]()
