"""P12 exploratory retention-floor / within-cost-stratum rule ranking. CPU freeze."""
from __future__ import annotations
import os,copy,json,itertools,random,sqlite3,time,collections
from pathlib import Path
from . import p11_eaar_v1_20261118 as V1
from .utils import read_json,read_jsonl,write_json,write_jsonl,sha256_file
ROOT=V1.ROOT;DATA=ROOT/'data_ext_p12_eaar_v2';PREREG=ROOT/'P12_PREREG_20261118_ZH.md'
SEEDS=V1.SEEDS;SKILLS=V1.SKILLS;OLD_SKILLS=V1.OLD_SKILLS;NEW_SKILLS=V1.NEW_SKILLS
ARMS=['floor_random','floor_rules'];BUDGET=7494
label=V1.label
def planpath(s,a):return DATA/'plans'/(label(s,a)+'.json')
def fixture(k):return DATA/'fixtures'/('calendar.json' if k=='calendar' else k+'.sqlite')
def digest(o):return V1.digest(o)
def log(s):print(time.strftime('%F %T %z'),s,flush=True)

def rule_coverage(r):
    """Exact trajectory differences, fixed training-side rules; no model scores."""
    result=json.loads(r['expected_observation'])['result'];gold=r['expected_final_answer'];d=r['expected_arguments']['date']
    if r['skill']=='cal.count_date':
        wrong=[('day_as_month', 'calendar_count',{'month':d},None),('first_only','calendar_list',{'date':d},min(1,len(result))),('distinct_location_count','calendar_list',{'date':d},len({x['location'] for x in result}))]
    else:
        loc=[x['location'] for x in result]
        wrong=[('first_location','calendar_list',{'date':d},loc[:1]),('keep_duplicates','calendar_list',{'date':d},sorted(loc)),('first_occurrence_order','calendar_list',{'date':d},list(dict.fromkeys(loc))),('titles','calendar_list',{'date':d},sorted({x['title'] for x in result})),('start_times','calendar_list',{'date':d},sorted({x['start'] for x in result}))]
    hits=[name for name,t,a,ans in wrong if (t!=r['expected_tool'] or a!=r['expected_arguments'] or ans!=gold)]
    return {'excluded_rules':hits,'denominator':len(wrong),'integer_weighted_score':len(hits)*(5 if len(wrong)==3 else 3),'rules':[{'name':n,'tool':t,'arguments':a,'answer':ans} for n,t,a,ans in wrong]}

def make_candidates():
    from .sft.train import load_tokenizer
    from .sft.dataset import tokenize_episode
    from .replay_study import config_for
    from .data.generate import _observation
    from .research_data import project_answer
    tok=load_tokenizer(config_for('A',SEEDS[0],batch_size=1))
    original=read_jsonl(V1.DATA/'train/rows.jsonl');rows=list(copy.deepcopy(original))
    assert len(original)==24
    # Retain the 24 original records; exactly one complementary skill per date.
    for i,r in enumerate(original):
        d=r['expected_arguments']['date'];count=r['skill']=='cal.list_locations';skill=OLD_SKILLS[0 if count else 1]
        prompt=(V1.CAL_COUNT_DEV if count else V1.CAL_LIST_DEV)[i%4].format(d=d)
        spec={'kind':'length'} if count else {'kind':'pluck','field':'location','unique':True}
        x=V1.row('calendar',skill,'train',i,prompt,'calendar_list',{'date':d},{},spec,cal=str(V1.fixture('calendar')))
        x['episode_id']=f'p12-train-{skill}-{i:03}';rows.append(x)
    assert len(rows)==48 and len({r['expected_arguments']['date'] for r in rows})==24
    meta=[];features=[]
    for i,r in enumerate(rows):
        obs=_observation('calendar',r['expected_tool'],r['expected_arguments'],r['environment'],str(ROOT/'data_phase2/fixtures/toolbench.db'),str(V1.fixture('calendar')))
        assert json.loads(obs)['ok'] and json.loads(obs)==json.loads(r['expected_observation'])
        assert project_answer(json.loads(obs)['result'],r['answer_spec'])==r['expected_final_answer']
        ft=tokenize_episode(r,tok,1024);assert len(ft['input_ids'])<1024
        item={'family':'calendar','row_index':30000+i,'episode_id':r['episode_id'],'input_tokens':len(ft['input_ids']),'supervised_tokens':sum(v!=-100 for v in ft['labels']),'truncated':False,'target':True,'skill':r['skill'],'message_hash':digest(r['messages'])}
        item['rule_coverage']=rule_coverage(r);meta.append(item)
        features.append({'row_index':item['row_index'],'episode_id':r['episode_id'],'input_ids':ft['input_ids'],'labels':ft['labels'],'attention_mask':ft.get('attention_mask',[1]*len(ft['input_ids']))})
    # Strict B1 semantics: calendar_count rejects full dates; daily count uses list+length.
    invalid=json.loads(_observation('calendar','calendar_count',{'month':rows[0]['expected_arguments']['date']},{},str(ROOT/'data_phase2/fixtures/toolbench.db'),str(V1.fixture('calendar'))))
    assert not invalid['ok']
    write_jsonl(DATA/'train/rows.jsonl',rows);write_json(DATA/'train/calendar_extra_meta.json',meta);write_json(DATA/'train/calendar_extra_features.json',features)
    return rows,meta

def plans(meta):
    from .p6_attempt2 import adapt_plan
    # Read only the P11 dev results for algorithm decisions; never P12 holdout scores.
    c=read_json(V1.DATA/'candidates.json');bg=V1.background_options(read_json(V1.DATA/'background.json'));after=read_json(V1.DATA/'source_after.json')
    cov=read_json(V1.DATA/'prefix_coverage.json');report={}
    for seed in SEEDS:
        recs=read_jsonl(ROOT/f'runs_ext_p11_eaar_v1/probes/A_seed{seed}/dev/results.jsonl')
        for r in recs:r['skill']=next(s for s in SKILLS if s in r['episode_id'])
        stats=V1.summarize_probes(recs);info=V1.decide(stats,cov,seed)['skills'];order=V1.candidate_order(c,seed)
        assert all(stats[s]['joint']>0 for s in OLD_SKILLS)
        counts={s:1 for s in SKILLS}
        while sum(counts[s] for s in NEW_SKILLS)<8:
            s=max(NEW_SKILLS,key=lambda s:(info[s]['priority']/((counts[s]+1)*order[s][counts[s]%len(order[s])]['input_tokens']),-SKILLS.index(s)))
            counts[s]+=1
        assert [counts[s] for s in SKILLS]==[1,1,3,1,2,2],counts
        new={s:[copy.deepcopy(order[s][i%len(order[s])]) for i in range(counts[s])] for s in NEW_SKILLS}
        newcost=sum(x['input_tokens'] for xs in new.values() for x in xs)
        strata=collections.defaultdict(list)
        for a,b in itertools.product([x for x in meta if x['skill']==OLD_SKILLS[0]],[x for x in meta if x['skill']==OLD_SKILLS[1]]):
            cost=(a['input_tokens']+b['input_tokens'],a['supervised_tokens']+b['supervised_tokens']);score=a['rule_coverage']['integer_weighted_score']+b['rule_coverage']['integer_weighted_score']
            if BUDGET-newcost-cost[0] in bg:strata[cost].append((score,a,b))
        feasible={k:xs for k,xs in strata.items() if len({x[0] for x in xs})>1}
        if not feasible:raise ValueError(('no EXACT feasible unequal-score joint input+supervision cost layer',seed))
        def rank(k):
            xs=feasible[k];return (max(x[0] for x in xs),max(x[0] for x in xs)-min(x[0] for x in xs),len(xs))
        best=max(map(rank,feasible));ties=sorted(k for k in feasible if rank(k)==best)
        rng=random.Random(seed+1200);layer=rng.choice(ties);xs=feasible[layer]
        a=rng.choice(xs);top=[x for x in xs if x[0]==max(y[0] for y in xs)];b=rng.choice(top)
        background=copy.deepcopy(bg[BUDGET-newcost-layer[0]])
        for x in background:x['target']=False
        assert len(background)==12
        evidence={'input_supervised_cost_layer':layer,'score_units':'integer/15, equal skill weights','layer_rank':best,'n_feasible_layers':len(feasible),'n_combinations_in_layer':len(xs),'A_score':a[0]/15,'B_score':b[0]/15,'priorities':info,'counts':counts}
        for arm,chosen in zip(ARMS,[a,b]):
            queues={**copy.deepcopy(new),OLD_SKILLS[0]:[copy.deepcopy(chosen[1])],OLD_SKILLS[1]:[copy.deepcopy(chosen[2])]}
            skills=list(SKILLS);random.Random(seed+11).shuffle(skills);targets=[]
            while any(queues.values()):
                for s in skills:
                    if queues[s]:targets.append(queues[s].pop(0))
            for x in targets:x['target']=True
            q=V1.assemble_plan(seed,arm,targets,counts,'scattered',copy.deepcopy(background),after,'P12 retention floor; exact cost-stratum A random vs B fixed-rule ranking')
            q['p12']=copy.deepcopy(evidence);q['p12']['arm']=arm
            q=adapt_plan(q);assert q['actual_input_tokens']==7494 and len(q['items'])==22
            write_json(planpath(seed,arm),q)
        qa,qb=[read_json(planpath(seed,a)) for a in ARMS]
        # Exact same schedule/new inputs/bg, same old aggregate input and supervision.
        assert sum(x['supervised_tokens'] for x in qa['items'])==sum(x['supervised_tokens'] for x in qb['items'])
        for xa,xb in zip(qa['items'],qb['items']):
            if xa.get('skill') not in OLD_SKILLS:assert xa==xb
        evidence['same_training_plan']=qa['items']==qb['items'];report[str(seed)]=evidence
    write_json(DATA/'plan_decisions.json',report)
    return report

def make_holdout():
    """Fixed deterministic instance+wording holdout; no model interaction."""
    rng=random.Random(2026111812);old=read_jsonl(V1.DATA/'holdout/rows.jsonl');calold=read_json(V1.fixture('calendar'))['events'];events=[];rows=[]
    calpath=fixture('calendar');base_db=str(ROOT/'data_phase2/fixtures/toolbench.db')
    cal_cases=[]
    for skill in OLD_SKILLS:
        originals=[r for r in old if r['skill']==skill];profiles=[]
        for r in originals:
            es=[e for e in calold if e['date']==r['expected_arguments']['date']];profiles.append((len(es),len({e['location'] for e in es})))
        rng.shuffle(profiles)
        for i,(n,u) in enumerate(profiles):
            d=f'2028-{6+OLD_SKILLS.index(skill):02d}-{i+1:02d}'
            rooms=[f'Pavilion_{chr(90-j)}_{OLD_SKILLS.index(skill)}{i:02}' for j in range(u)]
            locs=rooms+[rng.choice(rooms) for _ in range(n-u)];rng.shuffle(locs)
            for j,loc in enumerate(locs):events.append({'id':f'P12_{len(events):03}','title':f'Verification Session {len(events):03}','date':d,'start':f'{9+2*j:02}:00','end':f'{10+2*j:02}:00','location':loc,'attendees':[f'Visitor_{i:02}_{j}']})
            cal_cases.append((skill,i,d))
    write_json(calpath,{'events':events})
    def add(f,s,i,p,t,a,env,spec,db=None):
        r=V1.row(f,s,'holdout',i,p,t,a,env,spec,db=str(db or base_db),cal=str(calpath));r['episode_id']=f'p12-holdout-{s}-{i:03}';r['p12_db_path']=str(db or base_db);rows.append(r)
    # Distinct question forms, not reusing train/dev/P11 holdout prompt strings.
    count_forms=['For the day {d}, supply only the total number of scheduled entries.','I need an integer: how many appointments fall on {d}?','Determine how many entries the schedule has on {d}; answer as an integer.','Looking only at {d}, what is the total event count? Use a number.']
    list_forms=['For the schedule dated {d}, provide all nonrepeated venue names in alphabetical order as a JSON array.','Which locations are used on {d}? Remove repetitions, alphabetize, and answer as a JSON array.','Extract the venue field for the events of {d}; output a sorted JSON array without duplicates.','For entries taking place on {d}, collect every unique location in a sorted JSON array.']
    for s,i,d in cal_cases:
        count=s==OLD_SKILLS[0];prompt=(count_forms if count else list_forms)[i%4].format(d=d)
        add('calendar',s,i,prompt,'calendar_list',{'date':d},{},{'kind':'length'} if count else {'kind':'pluck','field':'location','unique':True})
    for i in range(12):
        db=fixture(f'blind_{i:02}');names=[f'p12x_{i:02}_{x}' for x in ['instruments','samples','observations']]
        with sqlite3.connect(db) as conn:
            for tab in names:
                conn.execute(f'CREATE TABLE {tab}(id INTEGER PRIMARY KEY,name TEXT,score REAL)')
                vals=[(j,f'p12_entity_{i:02}_{j:02}',rng.randrange(14,96)+j/100) for j in range(1,21)]
                conn.executemany(f'INSERT INTO {tab} VALUES (?,?,?)',vals)
        lt=['Identify the tables available here; respond with a JSON list containing every table name.','Retrieve the complete set of table identifiers from this database as a JSON array.','Give an alphabetically sorted JSON array naming all tables in the current database.','Inspect the database table inventory and return just a JSON array of identifiers.'][i%4]
        add('database','db.list_tables',i,lt,'db_list_tables',{},{},{'kind':'identity'},db)
        tab=names[i%3];v=29+11*(i%4);k=1+i%3;sql=f'SELECT name FROM {tab} WHERE score > {v} ORDER BY score DESC, id ASC LIMIT {k}'
        p=f'From {tab}(id, name, score), select rows with score greater than {v}; order by score descending then id ascending, and give the first {k} name values as a JSON array.'
        add('database','db.filter_cmp_top',i,p,'db_query',{'sql':sql},{},{'kind':'rows_first'},db)
        path=f'p12_blind/bulletin_{i:03}.txt';word=f'p12signal{i:02}';lines=[f'entry {j+1}: neutral value {rng.randint(10,99)}' for j in range(7)]
        for j in sorted(rng.sample(range(7),2+i%2)):lines[j]=f'entry {j+1}: contains {word}'
        add('file','file.search_last',i,f'Locate occurrences of {word!r} in {path}; give exactly the text of the last matching line.','file_search',{'path':path,'pattern':word},{'files':{path:'\n'.join(lines)+'\n'}},{'kind':'match','index':-1})
        vals=rng.sample(range(131,260),7);text=', '.join(map(str,vals))
        add('python','py.median',i,f'Consider these seven measurements: {text}. After arranging them in ascending order, report the middle measurement.','stats_median',{'values':vals},{},{'kind':'identity'})
    rows.sort(key=lambda r:(SKILLS.index(r['skill']),r['episode_id']));assert len(rows)==72
    write_jsonl(DATA/'holdout/rows.jsonl',rows)
    return rows

def build():
    os.environ.update(CUDA_VISIBLE_DEVICES='',HF_HUB_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1',TOKENIZERS_PARALLELISM='false')
    if DATA.exists():raise SystemExit('P12 data exists; refuse overwrite')
    for sub in ['train','holdout','fixtures','plans']:(DATA/sub).mkdir(parents=True,exist_ok=True)
    train,meta=make_candidates();decisions=plans(meta);hold=make_holdout()
    from .data.generate import _observation
    from .research_data import project_answer
    for r in hold:
        obs=json.loads(_observation(r['tool_family'],r['expected_tool'],r['expected_arguments'],r['environment'],r['p12_db_path'],str(fixture('calendar'))))
        assert obs['ok'] and project_answer(obs['result'],r['answer_spec'])==r['expected_final_answer']
    previous=read_jsonl(V1.DATA/'dev/rows.jsonl')+read_jsonl(V1.DATA/'holdout/rows.jsonl')+train
    for family in ['database','file','python']:previous+=read_jsonl(ROOT/f'data_ext_e4/pool/{family}.jsonl')
    previous+=read_jsonl(ROOT/'data_phase2/calendar/train.jsonl')
    assert not {r['prompt'] for r in hold}&{r['prompt'] for r in previous}
    dates={r['expected_arguments']['date'] for r in hold if r['tool_family']=='calendar'};pastdates={r['expected_arguments']['date'] for r in previous if 'date' in r['expected_arguments']};assert not dates&pastdates
    oldlocs={e['location'] for e in read_json(V1.fixture('calendar'))['events']+read_json(ROOT/'data_phase2/fixtures/calendar.json')['events']};assert not oldlocs&{e['location'] for e in read_json(fixture('calendar'))['events']}
    tables=[r for r in hold if r['skill']=='db.list_tables'];assert len({r['p12_db_path'] for r in tables})==12 and len({tuple(r['expected_final_answer']) for r in tables})==12
    write_json(DATA/'cpu_acceptance.json',{'passed':True,'time':time.strftime('%F %T %z'),'train_calendar_rows':48,'executor_label_checks':120,'all_exact_input_budget':7494,'old_input_and_supervision_cost_matched':True,'blind_n':72,'independent_three_table_dbs':12,'train_dev_blind_entities_disjoint':True,'decisions':decisions})
    refs=[PREREG,ROOT/'fac_tinyagent/p12_eaar_v2_20261118.py',ROOT/'fac_tinyagent/p12_queue_20261118.py',ROOT/'fac_tinyagent/p11_queue_20261118.py',ROOT/'fac_tinyagent/p11_e3_train_compat_20261118.py',V1.DATA/'manifest.json',V1.DATA/'candidates.json',V1.DATA/'background.json',V1.DATA/'fixtures/calendar.json',V1.DATA/'train/rows.jsonl']
    for s in SEEDS:refs += [ROOT/f'runs_ext_e4/prefixes/A_seed{s}/training_state.pt',ROOT/f'runs_ext_e4/prefixes/A_seed{s}/manifest.json',ROOT/f'runs_ext_p11_eaar_v1/probes/A_seed{s}/dev/results.jsonl',ROOT/f'runs_ext_p11_eaar_v1/branches/A_seed{s}_eaar_v1/checkpoint/adapter_model.safetensors']
    files=[p for p in DATA.rglob('*') if p.is_file()]
    manifest={'created':time.strftime('%F %T %z'),'scope':'P12 only; exploratory post-P11 revision; no holdout model scores opened','files':{str(p.relative_to(ROOT)):sha256_file(p) for p in files},'references':{str(p.relative_to(ROOT)):sha256_file(p) for p in refs},'decisions':decisions}
    write_json(DATA/'manifest.json',manifest);log('P12 CPU FREEZE PASS '+sha256_file(DATA/'manifest.json'))

def verify():
    m=read_json(DATA/'manifest.json')
    for rel,h in {**m['files'],**m['references']}.items():assert sha256_file(ROOT/rel)==h,rel
    return m
if __name__=='__main__':build()
