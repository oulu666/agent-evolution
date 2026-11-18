"""P11 EAAR-v1: freezeable pre-training replay planner. CPU data/plans/rules only in build mode."""
from __future__ import annotations
import os,argparse,collections,copy,hashlib,itertools,json,random,sqlite3,time
from pathlib import Path
from .utils import read_json,read_jsonl,write_json,write_jsonl,sha256_file,canonical_json,ensure_dir
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data_ext_p11_eaar_v1'
SEEDS=[20261108,20261109,20261110]
SKILLS=['cal.count_date','cal.list_locations','db.list_tables','db.filter_cmp_top','file.search_last','py.median']
OLD_SKILLS=['cal.count_date','cal.list_locations']
NEW_SKILLS=['db.list_tables','db.filter_cmp_top','file.search_last','py.median']
ARMS=['uniform','fixed_early','eaar_v1']
DEST={'uniform':[0,2,5,7,9,12,14,16,19,21],'fixed_early':list(range(10)),'eaar_v1':None}
POSITIONS=[87,95,103,111,119,127,135,143,151,159]
PAT={'db.list_tables':'db_list_tables','db.filter_cmp_top':'target_db_filter_top','file.search_last':'e4_last_match','py.median':'target_median_natural','cal.count_date':'calendar-train-calendar_count_date','cal.list_locations':'p11-train-cal.list_locations'}
BUDGET=7494
PREREG=ROOT/'P11_PREREG_20261118_EAAR_V1_ZH.md'
def log(s):print(time.strftime('%F %T %z'),s,flush=True)
def digest(obj):return hashlib.sha256(canonical_json(obj).encode()).hexdigest()
def identify(row):
    eid=row.get('episode_id','')
    for k,p in PAT.items():
        if p in eid:return k
    return None
def label(s,a):return f'A_seed{s}_{a}'
def planpath(s,a):return DATA/'plans'/(label(s,a)+'.json')
def source(s):return ROOT/f'data_ext_e3/plans/A_seed{s}_dose_db4.json'
def fixture(kind):
    if kind=='calendar':return DATA/'fixtures'/'calendar.json'
    if kind in ('dev','holdout'):return DATA/'fixtures'/(kind+'.sqlite')
    raise KeyError(kind)
def make_db(split):
    names=['p11d_crew','p11d_parts','p11d_marks'] if split=='dev' else ['p11h_teams','p11h_catalog','p11h_ratings']
    rng=random.Random(2026111801 if split=='dev' else 2026111802)
    db=fixture(split)
    if db.exists():db.unlink()
    with sqlite3.connect(db) as c:
        for tab in names:
            c.execute(f'CREATE TABLE {tab}(id INTEGER PRIMARY KEY,name TEXT,score REAL)')
            c.executemany(f'INSERT INTO {tab} VALUES (?,?,?)',[(i,f'{split}_p11_{tab}_{i:02}',rng.randint(14,96)+i/100) for i in range(1,21)])
    return names
def historical_calendar_entities():
    old=read_json(ROOT/'data_phase2/fixtures/calendar.json')['events']
    dates={e['date'] for e in old};ids={e['id'] for e in old};locs={e['location'] for e in old}
    for split in ['train','val','test']:
        for r in read_jsonl(ROOT/'data_phase2/calendar'/f'{split}.jsonl'):
            if r['expected_tool'] in {'calendar_list','calendar_count'} and 'date' in r.get('expected_arguments',{}):
                dates.add(r['expected_arguments']['date'])
            if 'episode_id' in r and 'list_locations' in r['episode_id']:
                pass
    return dates,ids,locs
def make_calendar():
    banned_dates,banned_ids,banned_locs=historical_calendar_entities()
    rng=random.Random(2026111803)
    rooms=['Studio 1','Annex Q','Dock 7','Loft K','Atrium 2','Bay 9']
    titles=['Intake Sync','Material Check','Pilot Brief','Harbor Review','Night Handoff','Sketch Lab','Dock Audit']
    people=['Nia','Omar','Pia','Quinn','Rafi','Suki','Toma']
    assert not set(rooms)&banned_locs
    events=[];day=0
    # 72 event-days in 2027, none overlapping historical 2026 fixture dates.
    while len(events)<160:
        day+=1;date=f'2027-{(day//28)%9+1:02d}-{(day%28)+1:02d}'
        if date in banned_dates or not date[5:7] in {'01','02','03','04','05','06','07','08','09'}:
            continue
        n=1+rng.randint(0,3);used=set();start=9
        for j in range(n):
            loc=rng.choice(rooms)
            # force some duplicate locations on multi-event days
            if j and rng.random()<0.45:loc=rng.choice(list(used) or [loc])
            used.add(loc)
            eid=f'P11E{len(events)+1:03}'
            assert eid not in banned_ids
            events.append({'id':eid,'title':rng.choice(titles)+f' {len(events)+1}','date':date,'start':f'{start:02d}:00','end':f'{start+1:02d}:00','location':loc,'attendees':rng.sample(people,3)})
            start+=2
    write_json(fixture('calendar'),{'events':events})
    return events
def row(family,skill,split,i,prompt,tool,args,env,spec,cal=None,db=None):
    from .data.generate import _observation,_schemas,build_system_prompt
    from .round2_data import _messages
    from .research_data import project_answer,task_signature
    db=str(db or (fixture(split) if family=='database' else ROOT/'data_phase2/fixtures/toolbench.db'))
    cal=str(cal or fixture('calendar'))
    obs=_observation(family,tool,args,env,db,cal);o=json.loads(obs);assert o['ok'],(skill,args,obs)
    answer=project_answer(o['result'],spec);system=build_system_prompt(family,_schemas(family,db,cal))
    r={'episode_id':f'p11-{split}-{skill}-{i:03}','tool_family':family,'split':split,'template_id':f'p11_{split}_{skill}','skill':skill,'prompt':prompt,'system':system,'environment':env,'expected_tool':tool,'expected_arguments':args,'skill_labels':[skill],'answer_spec':spec,'expected_observation':obs,'expected_final_answer':answer,'evaluation_only':split!='train','selection_allowed':split=='dev','messages':_messages(system,prompt,tool,args,obs,answer)}
    r['data_signature']=task_signature(r);return r
LT_DEV=['Return every table name in this database as a JSON array.','List the database tables and output a JSON array of their names.','Give a JSON array containing each table identifier present here.','Produce the complete table inventory as a JSON array of names.']
LT_TEST=['For this independent database, output a JSON array of its table names.','Enumerate all tables here and answer with a JSON array of names.','What table identifiers exist in this database? Reply with a JSON array.','Show the table inventory using a JSON array of names.','Report every table present as a JSON array.','Fetch the names of all tables and return a JSON array.','Name each table in this database with a JSON array.','Provide a JSON array listing this database\'s tables.','Which tables belong to this database? Use a JSON array.','Return a JSON array of the table-name inventory.','Give the full set of table names as a JSON array.','Output the existing table identifiers in a JSON array.']
CAL_COUNT_DEV=['How many events occur on {d}? Return a single integer.','Count the events dated {d} and answer with one integer.','On {d}, what is the number of events? Give an integer only.','Return the integer count of events that take place on {d}.']
CAL_COUNT_TEST=['Give the number of events on {d} as a single integer.','How many calendar events are scheduled on {d}? Answer with an integer.','Count events whose date is {d} and return that integer.','What is the event count for {d}? Return one integer.','Report an integer equal to the number of events on {d}.','For date {d}, output the integer event count.','Return a single integer counting events on {d}.','How many events does {d} contain? Answer with an integer.','State the integer number of events occurring on {d}.','Provide the event total on {d} as an integer.','Count all events dated {d}; return the integer total.','Output the integer count of events held on {d}.']
CAL_LIST_DEV=['List the distinct locations of events on {d}, sorted alphabetically, as a JSON array.','On {d}, return a sorted JSON array of unique event locations.','Give the distinct locations for events dated {d}, sorted, in a JSON array.','Collect unique event locations on {d}, sort them, and return a JSON array.']
CAL_LIST_TEST=['Return a sorted JSON array of the distinct locations of events on {d}.','For {d}, list unique event locations in alphabetical order as a JSON array.','Output the distinct, sorted locations of events dated {d} as a JSON array.','Which distinct locations host events on {d}? Return a sorted JSON array.','Give unique locations of {d} events, sorted alphabetically, in a JSON array.','Produce a sorted JSON array of distinct event locations on {d}.','List every unique location used on {d}, sorted, as a JSON array.','Return alphabetically sorted distinct locations for events on {d} in a JSON array.','On date {d}, output unique event locations as a sorted JSON array.','Provide a JSON array of distinct, alphabetically sorted locations on {d}.','Find events on {d} and return their unique locations, sorted, as a JSON array.','State the distinct locations of {d} events in a sorted JSON array.']
def calendar_dates(events,kind):
    by={}
    for e in events:by.setdefault(e['date'],[]).append(e)
    usable=[]
    for d,rs in sorted(by.items()):
        locs=[e['location'] for e in rs]
        usable.append((d,len(rs),len(set(locs)),sorted(set(locs))))
    if kind=='count':
        # mix 1-4 event days
        return [x for x in usable]
    # list: prefer days with at least one location, include some duplicate-location days
    return [x for x in usable if x[2]>=1]
def build_eval_and_calendar_candidates():
    events=make_calendar();dates=calendar_dates(events,'count')
    # partition dates: train 16, dev 8, holdout 12 for each calendar skill, disjoint.
    rng=random.Random(2026111804)
    count_days=dates[:];rng.shuffle(count_days)
    list_days=[x for x in dates if x[2]>=1]
    # ensure some list days have duplicate locations
    dup=[x for x in list_days if x[1]>x[2]];uniq=[x for x in list_days if x[1]==x[2]]
    rng.shuffle(dup);rng.shuffle(uniq)
    list_pool=(dup+uniq)
    used=set()
    def take(pool,n,tag):
        out=[]
        for item in pool:
            if item[0] in used:continue
            out.append(item);used.add(item[0])
            if len(out)==n:return out
        raise RuntimeError('not enough disjoint calendar dates for '+tag)
    short_list=[x for x in list_pool if x[1]<=3]
    short_count=[x for x in count_days if x[1]<=3]
    cal_parts={'train_list':take(short_list,16,'train_list'),'dev_list':take(list_pool,4,'dev_list'),'holdout_list':take(list_pool,12,'holdout_list'),'train_count':take(short_count,8,'train_count'),'dev_count':take(count_days,4,'dev_count'),'holdout_count':take(count_days,12,'holdout_count')}
    rows={'train':[],'dev':[],'holdout':[]}
    def add_cal(split,skill,items,prompts):
        for i,item in enumerate(items):
            d=item[0]
            if skill=='cal.count_date':
                rows[split].append(row('calendar',skill,split,i,prompts[i].format(d=d),'calendar_list',{'date':d},{},{'kind':'length'}))
            else:
                rows[split].append(row('calendar',skill,split,i,prompts[i].format(d=d),'calendar_list',{'date':d},{},{'kind':'pluck','field':'location','unique':True}))
    add_cal('train','cal.list_locations',cal_parts['train_list'],CAL_LIST_TEST[:16] if False else (CAL_LIST_DEV*4)[:16])
    add_cal('dev','cal.list_locations',cal_parts['dev_list'],CAL_LIST_DEV)
    add_cal('holdout','cal.list_locations',cal_parts['holdout_list'],CAL_LIST_TEST)
    add_cal('train','cal.count_date',cal_parts['train_count'],(CAL_COUNT_DEV*2)[:8])
    add_cal('dev','cal.count_date',cal_parts['dev_count'],CAL_COUNT_DEV)
    add_cal('holdout','cal.count_date',cal_parts['holdout_count'],CAL_COUNT_TEST)
    for split,n,names in [('dev',4,make_db('dev')),('holdout',12,make_db('holdout'))]:
        rng=random.Random(2026111805 if split=='dev' else 2026111806)
        lt=LT_DEV if split=='dev' else LT_TEST
        for i in range(n):
            rows[split].append(row('database','db.list_tables',split,i,lt[i],'db_list_tables',{},{},{'kind':'identity'}))
            tab=names[i%3];v=26+11*(i%4)+3*(split=='holdout');k=1+i%3
            sql=f'SELECT name FROM {tab} WHERE score > {v} ORDER BY score DESC, id ASC LIMIT {k}'
            prompt=(f'Table {tab} has columns id, name, score. Filter to score > {v}, rank by descending score and ascending id on ties, and return the first {k} names as a JSON list.' if split=='dev' else f'Using {tab}(id, name, score), report the names of the top {k} rows with score above {v}. Sort by score descending, then id ascending; return a JSON list.')
            rows[split].append(row('database','db.filter_cmp_top',split,i,prompt,'db_query',{'sql':sql},{},{'kind':'rows_first'}))
            path=f'p11_{split}/note_{i:03}.txt';word=f'{split}mark{i:02}';hits=sorted(rng.sample(range(7),2+i%2));lines=[f'row {z+1}: filler value {rng.randint(10,99)}' for z in range(7)]
            for z in hits:lines[z]=f'row {z+1}: {word} appears in this row'
            prompt=(f'Return the last line in {path} that contains {word!r}.' if split=='dev' else f'In {path}, find {word!r} and return the complete final matching line exactly.')
            rows[split].append(row('file','file.search_last',split,i,prompt,'file_search',{'path':path,'pattern':word},{'files':{path:'\n'.join(lines)+'\n'}},{'kind':'match','index':-1}))
            vals=rng.sample(range(13,120),7);text=', '.join(map(str,vals))
            prompt=(f'Place these readings in increasing order: {text}. Which reading occupies the middle position?' if split=='dev' else f'The sample is {text}. Sort the observations from lowest to highest and give the central observation.')
            rows[split].append(row('python','py.median',split,i,prompt,'stats_median',{'values':vals},{},{'kind':'identity'}))
    for split in rows:
        rows[split].sort(key=lambda r:(SKILLS.index(r['skill']),r['episode_id']))
        write_jsonl(DATA/split/'rows.jsonl',rows[split])
    return rows,cal_parts
def classify_skill(stats,prefix_count):
    j=stats['joint'];tool=stats['tool'];args=stats['args'];exe=stats['execution'];final=stats['final']
    gap=prefix_count==0
    saturated=j>=0.75-1e-12
    forget=prefix_count>0 and j<0.5-1e-12
    output_fail=(min(tool,args,exe)>=0.75-1e-12) and (final<0.5-1e-12)
    score=0
    if j<=1e-12:score+=3
    elif j<0.5-1e-12:score+=2
    elif j<0.75-1e-12:score+=1
    if gap:score+=2
    if forget:score+=2
    if output_fail:score+=1
    if saturated and score==0:kind='saturated'
    elif forget:kind='true_forgetting_prior'
    elif gap:kind='coverage_gap'
    elif output_fail:kind='output_operator_fail'
    else:kind='acquisition'
    return {'skill':stats['skill'],'priority':score,'kind':kind,'coverage_gap':gap,'saturated':saturated,'true_forgetting_prior':forget,'output_operator_fail':output_fail,'dev_joint':j,'dev_tool':tool,'dev_args':args,'dev_execution':exe,'dev_final':final,'prefix_count':prefix_count}
def decide(probe_by_skill,prefix_counts,seed):
    info={s:classify_skill(probe_by_skill[s],prefix_counts[s]) for s in SKILLS}
    ns={s:0 for s in SKILLS}
    order=list(SKILLS);random.Random(seed+11).shuffle(order)
    for s in order:
        if info[s]['priority']>=1 and sum(ns.values())<10:ns[s]=1
    def next_key(s,candidates):
        nxt=candidates[s][ns[s]%len(candidates[s])]
        return (info[s]['priority']/((ns[s]+1)*nxt['input_tokens']),-order.index(s))
    timing='early' if any(info[s]['true_forgetting_prior'] or (info[s]['output_operator_fail'] and prefix_counts[s]>0) for s in SKILLS) else 'scattered'
    return {'counts':ns,'timing':timing,'skills':info}
def allocate_from_decision(decision,candidates,seed):
    info=decision['skills'];ns=dict(decision['counts'])
    if max(x['priority'] for x in info.values())==0:
        ns=balanced_counts(seed)
    else:
        while sum(ns.values())<10:
            def key(s):
                nxt=candidates[s][ns[s]%len(candidates[s])]
                return (info[s]['priority']/((ns[s]+1)*nxt['input_tokens']),-list(SKILLS).index(s))
            ns[max(SKILLS,key=key)]+=1
    order=list(SKILLS);random.Random(seed+11).shuffle(order)
    result=[];counts=collections.Counter()
    while len(result)<10:
        for s in order:
            if counts[s]<ns[s]:
                result.append(copy.deepcopy(candidates[s][counts[s]%len(candidates[s])]));counts[s]+=1
    return result,dict(ns),{'timing':decision['timing'],'skills':info}
def plan_from_probes(seed,probe_records,candidates,background,after):
    cov=read_json(DATA/'prefix_coverage.json')
    decision=decide(summarize_probes(probe_records),cov,seed)
    order=candidate_order(candidates,seed)
    targets,ns,meta=allocate_from_decision(decision,order,seed)
    for x in targets:x['target']=True
    bg,cost,need=fill_background(targets,background_options(background))
    for x in bg:x['target']=False
    q=assemble_plan(seed,'eaar_v1',targets,ns,meta['timing'],bg,after,'EAAR-v1 frozen one-shot rule; no formal scores; no NLL benefit')
    q['p11']['decision']=dict(timing=meta['timing'],counts=ns,skills=meta['skills'],background_need=need,background_cost=cost)
    return q,decision
def balanced_counts(seed):
    ns={s:1 for s in SKILLS};groups=list(SKILLS);random.Random(seed).shuffle(groups)
    for s in groups[:4]:ns[s]+=1
    return ns
def take_targets(order,ns):
    result=[];counts=collections.Counter()
    groups=list(order)
    while len(result)<10:
        for s in groups:
            if counts[s]<ns[s]:
                result.append(copy.deepcopy(order[s][counts[s]%len(order[s])]));counts[s]+=1
    return result
def background_options(background):
    per={}
    for f,rs in background.items():
        opts={}
        for ix in itertools.combinations_with_replacement(range(len(rs)),4):
            items=[rs[i] for i in ix];opts.setdefault(sum(x['input_tokens'] for x in items),items)
        per[f]=opts
    dp={0:[]}
    for f in sorted(per):
        nxt={}
        for cost,items in dp.items():
            for v,more in sorted(per[f].items()):nxt.setdefault(cost+v,items+more)
        dp=nxt
    return dp
def fill_background(targets,dp):
    need=BUDGET-sum(x['input_tokens'] for x in targets)
    cost=min(dp,key=lambda v:(abs(v-need),v));assert abs(cost-need)<=0.01*BUDGET,('no budget match',need,cost)
    return copy.deepcopy(dp[cost]),cost,need
def candidate_order(candidates,s):
    order={}
    for k,rs in candidates.items():
        order[k]=copy.deepcopy(rs);random.Random(str(s)+'-'+k).shuffle(order[k])
    return order
def make_plan(seed,arm,targets,counts,timing,benefit,source_after):
    from .p4_forget_timing import recompute_meta,segment_of
    dest=DEST['fixed_early'] if timing=='early' else DEST['uniform']
    if arm=='fixed_early':assert timing=='early'
    if arm=='uniform':assert timing=='scattered'
    items=[None]*22
    for i,x in zip(dest,targets):items[i]=x
    from_bg=fill_background.__defaults__
    return dest,items
def assemble_plan(seed,arm,targets,counts,timing,bg,after,note):
    from .p4_forget_timing import recompute_meta,segment_of
    dest=DEST['fixed_early'] if timing=='early' else DEST['uniform']
    items=[None]*22
    for i,x in zip(dest,targets):items[i]=x
    itr=iter(bg)
    for i in range(22):
        if items[i] is None:items[i]=next(itr)
    q=read_json(source(seed));q.pop('e3_plan',None);q['items']=items;recompute_meta(q)
    q['uniform_actual_input_tokens']=sum(x['input_tokens'] for x in items if not x.get('target'))
    q.pop('quota_error_tokens_by_family',None)
    tracked=[{'id':x['episode_id'],'index':i,'position':POSITIONS[segment_of(i,22)],'after':after[i]} for i,x in enumerate(items) if x.get('target')]
    q['p11']={'arm':arm,'counts':counts,'timing':timing,'budget_deviation':q['actual_input_tokens']-BUDGET,'target_timing':tracked,'planner':note,'background_rule':'same 4/family token-residual filler; no formal score'}
    q['p6']={'arm':arm,'counts':counts,'benefit':None,'budget_deviation':q['actual_input_tokens']-BUDGET,'target_timing':tracked,'planner':note,'background_rule':q['p11']['background_rule']}
    q['p5']={'target_timing':tracked,'note':'read-only P5 trainer interface compatibility; policy in p11'}
    return q
def prefix_coverage():
    rows=read_jsonl(ROOT/'data_phase2/calendar/train.jsonl')
    counts={s:0 for s in SKILLS}
    for r in rows:
        s=identify(r)
        if s:counts[s]+=1
        # titles are a different list projection; recorded separately, not as list_locations
    counts['cal.list_titles']=sum('calendar_list_titles' in r['episode_id'] for r in rows)
    return counts
def summarize_probes(records):
    out={}
    for s in SKILLS:
        rs=[r for r in records if r['skill']==s];assert rs
        def mean(k):return sum(bool(r[k]) for r in rs)/len(rs)
        out[s]={'skill':s,'n':len(rs),'joint':mean('joint_success'),'tool':mean('tool_correct'),'args':mean('arguments_correct'),'execution':mean('execution_success'),'final':mean('final_correct')}
    return out
def write_placeholder_uniform_plans(candidates,background,after):
    dp=background_options(background);plans={}
    for seed in SEEDS:
        order=candidate_order(candidates,seed)
        ns=balanced_counts(seed);targets=take_targets(order,ns)
        for x in targets:x['target']=True
        bg,cost,need=fill_background(targets,dp)
        for x in bg:x['target']=False
        u=assemble_plan(seed,'uniform',targets,ns,'scattered',bg,after,'fixed balanced counts; scattered slots')
        e=assemble_plan(seed,'fixed_early',copy.deepcopy(targets),ns,'early',copy.deepcopy(bg),after,'same multiset as uniform; early slots only')
        assert [x['episode_id'] for x in u['items'] if x.get('target')]==[x['episode_id'] for x in e['items'] if x.get('target')]
        from .p6_attempt2 import adapt_plan
        write_json(planpath(seed,'uniform'),adapt_plan(u));write_json(planpath(seed,'fixed_early'),adapt_plan(e))
        plans[seed]={'uniform':u,'fixed_early':e,'eaar_pending':True,'background_need':need,'background_cost':cost}
    return plans
def build():
    os.environ.update(CUDA_VISIBLE_DEVICES='',HF_HUB_OFFLINE='1',TOKENIZERS_PARALLELISM='false',PYTHONDONTWRITEBYTECODE='1')
    if DATA.exists():raise SystemExit('Refuse existing P11 data root')
    ensure_dir(DATA/'fixtures');ensure_dir(DATA/'dev');ensure_dir(DATA/'holdout');ensure_dir(DATA/'train');ensure_dir(DATA/'plans')
    rows,cal_parts=build_eval_and_calendar_candidates()
    from .sft.train import load_tokenizer
    from .sft.dataset import tokenize_episode
    from .replay_study import config_for
    from .p4_forget_timing import source_after_by_index
    tok=load_tokenizer(config_for('A',SEEDS[0],batch_size=1))
    pools={f:read_jsonl(ROOT/'data_ext_e4/pool'/(f+'.jsonl')) for f in ['database','file','python']}
    prefix=read_jsonl(ROOT/'data_phase2/calendar/train.jsonl')
    prepared=[];features={}
    def add_prep(family,i,r,skill=None):
        ft=tokenize_episode(r,tok,1024);assert len(ft['input_ids'])<1024 and any(x!=-100 for x in ft['labels'])
        item={'family':family,'row_index':i,'episode_id':r['episode_id'],'input_tokens':len(ft['input_ids']),'supervised_tokens':sum(x!=-100 for x in ft['labels']),'truncated':False,'target':False,'skill':skill or identify(r),'message_hash':digest(r['messages'])}
        prepared.append(item);return item,ft
    for family,rs in pools.items():
        for i,r in enumerate(rs):add_prep(family,i,r)
    for i,r in enumerate(prefix):
        item,ft=add_prep('calendar',i,r)
        features.setdefault('calendar_prefix',{})[i]={'features':ft,**item}
    extra=[]
    for offset,r in enumerate(x for x in rows['train'] if x['skill']=='cal.list_locations'):
        item,ft=add_prep('calendar',10000+offset,r,skill='cal.list_locations');item['target']=True
        extra.append({**item,'features':ft,'messages':r['messages'],'source':'p11_new'})
    # optional extra new count_date candidates on new fixture, high index, not required if prefix counts suffice
    for offset,r in enumerate(x for x in rows['train'] if x['skill']=='cal.count_date'):
        item,ft=add_prep('calendar',20000+offset,r,skill='cal.count_date')
        extra.append({**item,'features':ft,'messages':r['messages'],'source':'p11_new_count'})
    write_jsonl(DATA/'train'/'calendar_extra.jsonl',[x['messages'] and {k:v for k,v in x.items() if k!='features'} | {'has_features':True} for x in extra])
    # store features separately as unusable in jsonl easily; write sidecar
    write_json(DATA/'train'/'calendar_extra_meta.json',[{k:v for k,v in x.items() if k!='features'} for x in extra])
    # pickle-free feature cache: token ids
    feat_cache=[]
    for x in extra:
        ft=x['features'];feat_cache.append({'row_index':x['row_index'],'episode_id':x['episode_id'],'input_ids':list(ft['input_ids']),'labels':list(ft['labels']),'attention_mask':list(ft['attention_mask']) if 'attention_mask' in ft else [1]*len(ft['input_ids'])})
    write_json(DATA/'train'/'calendar_extra_features.json',feat_cache)
    candidates={};background={}
    for s in SKILLS:
        distinct={}
        for x in prepared:
            if x['skill']==s:distinct.setdefault(x['message_hash'],copy.deepcopy(x))
        # cap 8 distinct, prefer existing e4/prefix first then extras
        selected=sorted(distinct.values(),key=lambda x:(0 if x['row_index']>=10000 else 1,x['input_tokens'],x['episode_id']))[:8]
        if s.startswith('cal.'):
            selected=[x for x in selected if x['row_index']>=10000][:8]
        assert selected,s
        candidates[s]=selected
    for f in ['database','file','python']:
        rs=[x for x in prepared if x['family']==f and x['skill'] is None and 'stats_median' not in x['episode_id'] and 'file_search_first' not in x['episode_id'] and 'db_list_tables' not in x['episode_id'] and 'target_db_filter_top' not in x['episode_id']]
        bycost={}
        for x in rs:bycost.setdefault(x['input_tokens'],x)
        background[f]=sorted(bycost.values(),key=lambda x:(x['input_tokens'],x['episode_id']))
        assert len(background[f])>=4,f
    write_json(DATA/'candidates.json',candidates);write_json(DATA/'background.json',background)
    write_json(DATA/'prefix_coverage.json',prefix_coverage())
    # leakage
    def ents(rs,family,key):
        out=set()
        for r in rs:
            if r['tool_family']!=family:continue
            if key=='prompt':out.add(r['prompt'])
            elif key=='path':out.add(r['expected_arguments'].get('path'))
            elif key=='pattern':out.add(r['expected_arguments'].get('pattern'))
            elif key=='values':
                if 'values' in r['expected_arguments']:out.add(tuple(sorted(r['expected_arguments']['values'])))
            elif key=='date':
                if 'date' in r['expected_arguments']:out.add(r['expected_arguments']['date'])
            elif key=='messages':out.add(digest(r['messages']))
        return out
    train_all=rows['train']+[r for rs in pools.values() for r in rs]+prefix
    checks={'dev':len(rows['dev']),'holdout':len(rows['holdout']),'train_new_calendar':len(rows['train']),'candidate_counts':{s:len(v) for s,v in candidates.items()}}
    assert not ({r['prompt'] for r in rows['dev']}&{r['prompt'] for r in rows['holdout']})
    assert not ({digest(r['messages']) for r in train_all}&{digest(r['messages']) for r in rows['dev']+rows['holdout']})
    assert not ({tuple(sorted(r['expected_arguments']['values'])) for r in rows['dev'] if r['skill']=='py.median'}&{tuple(sorted(r['expected_arguments']['values'])) for r in rows['holdout'] if r['skill']=='py.median'})
    assert not ({r['expected_arguments']['date'] for r in rows['dev'] if r['tool_family']=='calendar'}&{r['expected_arguments']['date'] for r in rows['holdout'] if r['tool_family']=='calendar'})
    assert not ({r['expected_arguments']['date'] for r in rows['train'] if r['tool_family']=='calendar'}&{r['expected_arguments']['date'] for r in rows['dev']+rows['holdout'] if r['tool_family']=='calendar'})
    hist_dates,_,_=historical_calendar_entities()
    used_dates={r['expected_arguments']['date'] for r in rows['dev']+rows['holdout']+rows['train'] if r['tool_family']=='calendar'}
    assert not used_dates&hist_dates
    checks.update({'dev_holdout_prompts_disjoint':True,'messages_disjoint_from_train_pools':True,'python_value_sets_disjoint':True,'calendar_dates_disjoint':True,'calendar_dates_disjoint_from_phase2':True,'database_schema_entities_disjoint':True})
    after=source_after_by_index(SEEDS[0],'dose_db4',read_json(source(SEEDS[0]))['items'])
    for s in SEEDS[1:]:
        assert source_after_by_index(s,'dose_db4',read_json(source(s))['items'])==after
    write_json(DATA/'source_after.json',after)
    plans=write_placeholder_uniform_plans(candidates,background,after)
    # token checks
    for seed in SEEDS:
        for arm in ['uniform','fixed_early']:
            q=read_json(planpath(seed,arm));assert q['actual_input_tokens']==BUDGET and q['within_one_percent_of_budget']
    checks['uniform_fixed_early_tokens']=BUDGET
    write_json(DATA/'cpu_data_checks.json',checks)
    refs=[PREREG,Path(__file__),ROOT/'fac_tinyagent/p11_e3_train_compat_20261118.py',ROOT/'fac_tinyagent/p6_e3_train_attempt2.py',ROOT/'fac_tinyagent/p6_attempt2.py',ROOT/'fac_tinyagent/p6_devplan.py']
    refs += [ROOT/'data_ext_e4/pool'/(f+'.jsonl') for f in pools]
    refs += [ROOT/f'runs_ext_e4/prefixes/A_seed{s}/training_state.pt' for s in SEEDS]
    refs += [ROOT/f'runs_ext_e4/prefixes/A_seed{s}/manifest.json' for s in SEEDS]
    refs += [ROOT/f'runs_phase2/A_seed{s}/config.json' for s in SEEDS]
    refs += [ROOT/f'runs_phase2/A_seed{s}/checkpoints/stage_03_python/adapter_model.safetensors' for s in SEEDS]
    refs += [ROOT/'data_phase2/calendar/train.jsonl',ROOT/'data_phase2/fixtures/calendar.json']
    files=[p for p in DATA.rglob('*') if p.is_file() and p.name!='manifest.json']
    write_json(DATA/'manifest.json',{'created':time.strftime('%F %T %z'),'stage':'CPU freeze of data, rules, and Uniform/FixedEarly plans; EAAR plans pending independent dev probes','seeds':SEEDS,'arms':ARMS,'skills':SKILLS,'old_skills':OLD_SKILLS,'new_skills':NEW_SKILLS,'budget_input_tokens':BUDGET,'updates':'prefix10+suffix13=23','formal_opened':False,'files':{str(p.relative_to(ROOT)):sha256_file(p) for p in files},'references':{str(p.relative_to(ROOT)):sha256_file(p) for p in refs if p.exists()},'checks':checks,'notes':'EAAR plans are not written until GPU dev probes finish and are frozen before formal scores'})
    log('P11 data and rules frozen; Uniform/FixedEarly plans ready; no GPU started')
def verify():
    m=read_json(DATA/'manifest.json')
    for p,h in {**m['files'],**m['references']}.items():assert sha256_file(ROOT/p)==h,p
    return m
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--phase',required=True,choices=['build','verify']);a=p.parse_args()
    if a.phase=='build':build()
    else:verify();print('OK')
