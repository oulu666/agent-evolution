#!/usr/bin/env python3
"""P14 deterministic dataset freeze + CPU-only acceptance. No model imports."""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
import ast, collections, datetime as dt, hashlib, itertools, json, re, random, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data_ext_p14_eval_protocol'
RUN = ROOT / 'runs_ext_p14_eval_protocol'
sys.path.insert(0, str(ROOT))
from fac_tinyagent.tools.calendar_tools import build_calendar_registry, CalendarStore
from fac_tinyagent.metrics import answers_equal, joint_success

def canon(x): return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
def packed(x): return (json.dumps(x, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()
def sha(x): return hashlib.sha256(x).hexdigest()
def rel(p): return str(p.relative_to(ROOT))
def install(p, data):
    if p.exists():
        assert p.read_bytes() == data, 'Frozen file mismatch; do not overwrite: '+str(p)
    else:
        p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
def pure_existing_function(path, name):
    node = next(n for n in ast.parse(path.read_text(encoding='utf-8')).body if isinstance(n, ast.FunctionDef) and n.name == name)
    node.returns = None
    for a in node.args.args: a.annotation = None
    ns = {}; exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), ns)
    return ns[name]
project_answer = pure_existing_function(ROOT/'fac_tinyagent/research_data.py', 'project_answer')

# Every split has independently written wording families, not a renamed template ID.
TEXT = {
 'train': {
 'literal_count': ['Count events on {d}; supply one integer.', 'Give the event count for the day {d} as an integer.', 'For {d}, count the scheduled entries and answer numerically.'],
 'no_count_question': ['How many appointments fall on {d}? Answer with one integer.', 'What number of calendar entries belongs to {d}? Use an integer.', 'How many scheduled items does the date {d} have? Give an integer.'],
 'synonym_total': ['Tally the appointments dated {d}; output the integer total.', 'Sum up the scheduled entries for {d}; provide an integer.', 'Report the total number of meetings taking place on {d} as an integer.'],
 'day_month_contrast': ['Count only events on {d}, not the whole month; return an integer.', 'The target is the single day {d}, not its month: how many events? Integer only.', 'For the daily rather than monthly total at {d}, return the integer number of entries.'],
 'month': ['Count all events in month {m}; give an integer.', 'How many events occur throughout {m}? Return one integer.', 'Tally entries over the entire calendar month {m}; output an integer.'],
 'locations': ['List unique event locations on {d}, alphabetically sorted, as a JSON array.', 'On {d}, deduplicate the location values and sort them ascending; return a JSON array.', 'Collect distinct venues for {d} in alphabetical order; answer with a JSON array.'],
 'fields': ['Extract every event {field} on {d}; keep repetitions, sort lexicographically, and return a JSON array.', 'For {d}, return a lexicographically sorted JSON array of all {field} values, including duplicates.', 'Collect the {field} field from events on {d}, sort ascending without deduplication, and answer with a JSON array.']},
 'dev': {
 'literal_count': ['Return an integer equal to the count of appointments dated {d}.', 'Obtain the count for calendar items occurring on {d}; an integer is required.', 'Please count the entries whose date matches {d}, then give that integer.'],
 'no_count_question': ['How many diary entries are assigned to {d}? Respond with an integer.', 'What is the number of appointments scheduled for the date {d}? Integer response.', 'For the calendar day {d}, how many entries are present? Reply numerically as an integer.'],
 'synonym_total': ['Determine the aggregate number of appointments for {d}; respond with an integer.', 'An integer is needed: tally up the calendar items for {d}.', 'Compute the daily total of scheduled entries at {d}; give a whole number.'],
 'day_month_contrast': ['Although this date contains a year and month, count only the day {d}; integer answer.', 'Use day-level rather than month-level scope for {d}; return its event total as an integer.', 'Restrict the tally to the complete date {d}, excluding other days in that month; integer only.'],
 'month': ['The scope is the complete month {m}: return its event total as an integer.', 'Across all dates within {m}, how many entries exist? Give an integer.', 'For month-wide scope {m}, report the integer count of appointments.'],
 'locations': ['Which different location strings are attached to {d} entries? Alphabetize and emit a JSON array.', 'Build an alphabetic JSON array from the nonrepeated venues used on {d}.', 'Deduplicate venues among the appointments dated {d}; present an ascending JSON array.'],
 'fields': ['Using appointments dated {d}, report all values under {field} in lexicographic order, duplicates preserved, as a JSON array.', 'Take {field} from each {d} entry; alphabetize that full multiset into a JSON array.', 'A JSON array is required for {d}: lexicographically order the {field} values without removing repeats.']},
 'test': {
 'literal_count': ['Produce just the integer event count associated with {d}.', 'Supply the count of scheduled calendar records for {d} in integer form.', 'Count records belonging to the calendar date {d}. Respond using a single integer.'],
 'no_count_question': ['For appointments bearing date {d}, what is their number? One integer, please.', 'How many records would the diary show for {d}? Supply one integer.', 'What number of scheduled records appears under {d}? Answer as an integer.'],
 'synonym_total': ['Give a whole-number tally of the appointments attached to {d}.', 'Find the sum of entries scheduled for {d}; the result must be an integer.', 'Calculate the total appointments bearing {d} and emit an integer.'],
 'day_month_contrast': ['Ignore the monthly aggregate: count calendar records for {d} alone. Integer output.', 'Treat {d} as a full date, not a month identifier, and provide its integer event total.', 'Use the individual date {d} to obtain the number of entries; a monthly answer is not wanted. Return an integer.'],
 'month': ['Over the full span of {m}, supply the integer number of scheduled records.', 'Count records from every day belonging to {m}; output an integer alone.', 'Return a whole-number tally for the month designated {m}, covering all its dates.'],
 'locations': ['Form a JSON array of different venues from {d} records, arranged alphabetically.', 'Return the alphabetized set of {d} location strings encoded as a JSON array.', 'For records bearing {d}, emit each venue once in an ascending JSON array.'],
 'fields': ['From calendar records bearing {d}, gather {field} with multiplicity intact and emit a lexicographically ordered JSON array.', 'Emit a JSON array containing each {field} value for {d}; lexicographic sorting is required and repeated values stay.', 'Read the {field} values of {d} records into a JSON array sorted lexicographically, retaining any repeated entries.']}}
# Only mathematically feasible cells. Random means neither increasing nor decreasing.
def location_cases():
    out = [('empty', [], 'none', 'not_applicable'),
           ('one_single', [0], 'none', 'constant'),
           ('one_repeated', [0,0,0,0], 'all', 'constant')]
    for u in (2,3,4):
        for dup in ('none','partial'):
            vals = list(range(u)) if dup == 'none' else list(range(u))+[0, u-1]
            for order in ('sorted','reverse','random'):
                v = sorted(vals)
                if order == 'reverse': v.reverse()
                if order == 'random':
                    if u == 2 and dup == 'none': continue
                    v = v[1:] + v[:1]
                    if v == sorted(vals) or v == sorted(vals, reverse=True):
                        v = [0,u-1]+[x for x in vals if x not in (0,u-1)]+[u-1,0]
                    assert sorted(v) == sorted(vals)
                out.append((f'u{u}_{dup}_{order}',v,dup,order))
    return out
CASES = location_cases()

def generate():
    result = {}; metadata = {}
    for split, reps, year in [('train',24,2030),('dev',12,2040),('test',12,2050)]:
        events=[]; drafts=[]; serial=0
        def add(kind, case, loc_indexes, duplicate='not_applicable', order='not_applicable', field=None, lex=None):
            nonlocal serial
            serial += 1; index=serial-1; d=(dt.date(year,1,1)+dt.timedelta(days=index*2)).isoformat()
            prefix=f'P14-{split}-{serial:04d}'
            es=[]
            if order == 'random':
                loc_indexes=list(loc_indexes); rng=random.Random(2026111900+serial)
                for attempt in range(100):
                    rng.shuffle(loc_indexes)
                    if loc_indexes!=sorted(loc_indexes) and loc_indexes!=sorted(loc_indexes,reverse=True): break
                else: raise AssertionError('No nonmonotone ordering')
            for j, locidx in enumerate(loc_indexes):
                # Start-time order is the tool-return order; fixture storage is reversed separately.
                e={'id':f'{prefix}-E{j:02d}','title':f'{prefix}-Agenda-{chr(90-j)}','date':d,
                   'start':f'{8+j:02d}:10','end':f'{8+j:02d}:50',
                   'location':f'{prefix}-Venue-{chr(65+locidx)}','attendees':[f'{prefix}-Person-A', f'{prefix}-Person-B']}
                es.append(e)
            events.extend(reversed(es))
            if kind == 'month':
                alt=(dt.date.fromisoformat(d)+dt.timedelta(days=1)).isoformat()
                # Dedicated neighbouring date creates legitimate monthly-vs-daily contrast.
                events.append({'id':prefix+'-OTHER','title':prefix+'-OtherAgenda','date':alt,'start':'15:10','end':'15:50','location':prefix+'-OtherVenue','attendees':[prefix+'-OtherPerson']})
            family = lex or kind
            tindex = case['rep']%3
            template=TEXT[split][family][tindex]
            prompt=template.format(d=d,m=d[:7],field={'start':'start time (the start field, HH:MM)'}.get(field,field))
            tool='calendar_count' if kind=='month' else 'calendar_list'
            args={'month':d[:7]} if kind=='month' else {'date':d}
            skill={'count':'cal.count_date','month':'cal.count_month','locations':'cal.list_locations','fields':f'cal.extract_{field}_sorted'}[kind]
            spec={'kind':'identity'} if kind=='month' else {'kind':'length'} if kind=='count' else {'kind':'pluck','field':'location','unique':True} if kind=='locations' else {'kind':'pluck','field':field,'unique':False}
            distinct=len(set(loc_indexes))
            tags={'task':kind,'count_wording':lex or 'not_applicable','location_cardinality':str(distinct) if distinct<3 else '3plus',
                  'distinct_locations_exact':distinct,'deduplication':duplicate,'input_location_order':order,
                  'field':field or 'not_applicable','case':case['id'],'event_count':len(es),
                  'difficulty':'hard' if distinct>=3 or duplicate=='partial' or order in ('reverse','random') or family=='day_month_contrast' else 'base',
                  'error_facets': ['day_month_tool_confusion','length_projection'] if kind=='count' else ['month_scope'] if kind=='month' else ['field_confusion','deduplication','sorting'] if kind=='locations' else ['field_confusion','sorting','retain_multiplicity'],
                  'operation_group': 'counts' if kind in ('count','month') else kind,
                  'interference_groups':['shared_calendar_list'] if tool=='calendar_list' else ['day_month_routing'],
                  'stage_role':'assign_from_sequence_not_accuracy','interference_eligible':['low','medium','high']}
            entities={'dates':[d], 'months':[d[:7]],'event_ids':[e['id'] for e in es], 'titles':[e['title'] for e in es],
                      'locations':sorted(set(e['location'] for e in es)), 'people':sorted({a for e in es for a in e['attendees']})}
            drafts.append({'episode_id':prefix,'tool_family':'calendar','split':split,'skill':skill,'skill_labels':[skill],
                           'skill_definition':{'tool':tool,'operation':spec,'output_type':'integer' if kind in ('count','month') else 'sorted_string_array'},
                           'prompt':prompt,'query':prompt,'template_id':f'{split}.{family}.{tindex}', 'template_text':template,
                           'environment':{},'fixture_path':f'data_ext_p14_eval_protocol/fixtures/{split}.json',
                           'expected_tool':tool,'expected_arguments':args,'answer_spec':spec,'strata':tags,'entity_set':entities,
                           'evaluation_only':split!='train','selection_allowed':split=='dev','replay_eligible':split=='train'})
        for lex in ('literal_count','no_count_question','synonym_total','day_month_contrast'):
            for i in range(reps):
                n=[0,1,2,4,6,3][i%6]
                add('count',{'id':'count_'+lex,'rep':i},list(range(n)),lex=lex)
        for i in range(reps): add('month',{'id':'month_contrast','rep':i},list(range(1+i%4)))
        for label, vals, dup, order in CASES:
            for i in range(reps): add('locations',{'id':label,'rep':i},vals,dup,order)
        for f in ('title','location','id','start'):
            for i in range(reps): add('fields',{'id':'extract_'+f,'rep':i},[2,0,2,1],field=f)
        result[f'fixtures/{split}.json']=packed({'events':events})
        metadata[split]={'rows':drafts,'fixture':{'events':events}}
    return result, metadata

def snapshot_sources():
    # Protect all existing Python source/tests/scripts + root reports + P4--P13 data JSONs.
    files=set()
    for folder in ('fac_tinyagent','scripts','tests'):
        files.update((ROOT/folder).rglob('*.py'))
    files.update(p for p in ROOT.glob('*.md') if 'p14' not in p.name.lower())
    for d in ROOT.glob('data_ext_p*'):
        if d==DATA: continue
        for pattern in ('*.json','*.jsonl','*.sqlite'):
            files.update(d.rglob(pattern))
    files={p for p in files if p.is_file() and '__pycache__' not in p.parts}
    return {rel(p):sha(p.read_bytes()) for p in sorted(files)}

def historical_audit():
    old=ROOT/'data_ext_p11_eaar_v1'
    rows=[json.loads(x) for x in (old/'dev/rows.jsonl').read_text().splitlines() if x]
    candidates=json.loads((old/'candidates.json').read_text())
    lookup={}
    for name in ('rows.jsonl','calendar_extra.jsonl'):
        for line in (old/'train'/name).read_text().splitlines():
            if line:
                r=json.loads(line);lookup[r['episode_id']]=r
    reg=build_calendar_registry(str(old/'fixtures/calendar.json'))
    detail=[]
    for c in candidates['cal.list_locations']:
        r=lookup[c['episode_id']];o=reg.execute(r['expected_tool'],r['expected_arguments']); assert o['ok']
        detail.append({'episode_id':r['episode_id'],'event_count':len(o['result']),'distinct_locations':len({e['location'] for e in o['result']})})
    return {'p11_dev_counts':dict(collections.Counter(r.get('skill') for r in rows)), 'p11_location_candidate_details':detail,
            'p11_candidate_distinct_location_histogram':dict(collections.Counter(str(r['distinct_locations']) for r in detail)),
            'p12_p13_scope':'Read-only source/report review; no model or historical predictions re-evaluated.',
            'p13_reference':'EXT_REPORT_20261119_p13_phase0b_final_independent_ZH.md'}

def validate_schema(schema,args):
    assert isinstance(args,dict) and set(schema.get('required',[]))<=set(args)
    assert set(args)<=set(schema['properties'])
    for k,v in args.items():
        assert schema['properties'][k]['type']=='string' and isinstance(v,str) and v
        assert re.fullmatch(r'\d{4}-\d{2}-\d{2}' if k=='date' else r'\d{4}-\d{2}',v)

def current_gpu():
    p=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader'],text=True,capture_output=True)
    assert p.returncode==0, 'GPU process check unavailable: '+p.stderr
    assert not p.stdout.strip(), 'GPU process detected; stop without interference: '+p.stdout
    return {'query':'nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader','output':p.stdout,'gpu_compute_processes':0}

def main():
    gpu_before=current_gpu()
    RUN.mkdir(exist_ok=True)
    prior=RUN/'protected_sources_before.json'
    before=snapshot_sources()
    if prior.exists(): assert json.loads(prior.read_text())==before,'Protected old files changed; stop'
    else: install(prior,packed(before))
    products,meta=generate()
    # Install fixture bytes first: actual existing registry executes all gold calls.
    for name,b in products.items(): install(DATA/name,b)
    matrices={}; isolates={}; totals={}; skills={}; case_matrix={}; template_counts={}
    template_bank={}
    row_bytes={}
    for split,obj in meta.items():
        reg=build_calendar_registry(str(DATA/f'fixtures/{split}.json'))
        schemas={s['name']:s['input_schema'] for s in reg.schemas()}
        system='You are a deterministic tool-using assistant. Calendar data is read-only.\nTools:\n'+'\n'.join(s['name']+': '+s['description']+' Schema: '+canon(s['input_schema']) for s in reg.schemas())+'\nFirst turn: exactly one JSON object {"tool": <tool_name>, "arguments": <object>}. After TOOL RESULT, exactly one JSON object {"answer": <value>}. No other text.'
        for r in obj['rows']:
            validate_schema(schemas[r['expected_tool']],r['expected_arguments'])
            o=reg.execute(r['expected_tool'],r['expected_arguments']); assert o['ok'],r['episode_id']
            r['expected_observation']=canon(o)
            r['expected_final_answer']=project_answer(o['result'],r['answer_spec'])
            # Independent answer oracle reads raw fixture, not existing projection.
            a=r['expected_arguments'];raw=obj['fixture']['events']
            raw=[e for e in raw if e['date']==a['date']] if 'date' in a else [e for e in raw if e['date'].startswith(a['month']+'-')]
            k=r['strata']['task']
            independent=len(raw) if k in ('count','month') else sorted({e['location'] for e in raw}) if k=='locations' else sorted(e[r['answer_spec']['field']] for e in raw)
            assert answers_equal(independent,r['expected_final_answer'])
            if k=='locations':
                vals=[e['location'] for e in o['result']]
                assert len(set(vals))==r['strata']['distinct_locations_exact']
                order=r['strata']['input_location_order']
                if order=='sorted': assert vals==sorted(vals) and len(set(vals))>1
                if order=='reverse': assert vals==sorted(vals,reverse=True) and len(set(vals))>1
                if order=='random': assert vals!=sorted(vals) and vals!=sorted(vals,reverse=True)
                dup=r['strata']['deduplication']
                if dup=='all': assert len(vals)>1 and len(set(vals))==1
                if dup=='partial': assert 1<len(set(vals))<len(vals)
                if dup=='none': assert len(vals)==len(set(vals))
            r['system']=system
            r['messages']=[{'role':'system','content':system},{'role':'user','content':r['prompt']},
                {'role':'assistant','content':canon({'tool':r['expected_tool'],'arguments':a})},
                {'role':'user','content':'TOOL RESULT:\n'+r['expected_observation']},
                {'role':'assistant','content':canon({'answer':r['expected_final_answer']})}]
            r['data_signature']=sha(canon({'prompt':r['prompt'],'tool':r['expected_tool'],'arguments':a}).encode())
            template_bank[r['template_id']]=r['template_text']
        rows=obj['rows'];totals[split]=len(rows)
        row_bytes[split]=(''.join(canon(r)+'\n' for r in rows)).encode()
        products[f'{split}/rows.jsonl']=row_bytes[split]
        install(DATA/f'{split}/rows.jsonl',row_bytes[split])
        matrices[split]={facet:dict(sorted(collections.Counter(str(r['strata'][facet]) for r in rows if r['strata']['task']==task).items())) for facet,task in [('count_wording','count'),('location_cardinality','locations'),('deduplication','locations'),('input_location_order','locations'),('field','fields')]}
        skills[split]=dict(sorted(collections.Counter(r['skill'] for r in rows).items()))
        case_matrix[split]=dict(sorted(collections.Counter(r['strata']['case'] for r in rows).items()))
        template_counts[split]={c:len({r['template_id'] for r in rows if r['strata']['case']==c}) for c in case_matrix[split]}
        assert all(n >= (24 if split=='train' else 12) for n in case_matrix[split].values())
        assert all(n>=3 for n in template_counts[split].values())
        # Include every fixture entity, not only gold-call-visible ones; time tokens are shared schema primitives.
        fixtures=obj['fixture']['events']
        isolates[split]={'query':{r['query'] for r in rows},'template_id':{r['template_id'] for r in rows},
            'template_text':{r['template_text'] for r in rows},
            'dates':{e['date'] for e in fixtures}|{r['expected_arguments']['date'] for r in rows if 'date' in r['expected_arguments']},
            'months':{e['date'][:7] for e in fixtures},
            'event_ids':{e['id'] for e in fixtures},'titles':{e['title'] for e in fixtures},
            'locations':{e['location'] for e in fixtures},'people':{v for e in fixtures for v in e['attendees']}}
        assert len(isolates[split]['query'])==len(rows)
        assert not any(r['split']!='train' and r['replay_eligible'] for r in rows)
    pair_checks={}
    for a,b in itertools.combinations(meta,2):
        pair_checks[a+'__'+b]={k:len(isolates[a][k]&isolates[b][k]) for k in isolates[a]}
        assert not any(pair_checks[a+'__'+b].values())
    # Derive replay pool from TRAIN ONLY; candidate ids are a manifest, never dev/test messages.
    pool={'source':'train/rows.jsonl','episode_ids':[r['episode_id'] for r in meta['train']['rows']],
          'n':totals['train'],'policy':'All train rows eligible; no difficulty filtering. Dev/test forbidden.'}
    products['replay_candidates.json']=packed(pool)
    products['template_bank.json']=packed(template_bank)
    groups=['counts','locations','fields']
    sequences={'status':'NOT_STARTED','training_performed':False,'seed_ids_reserved':[17,29,43],
               'stage_orders':[list(p) for p in itertools.permutations(groups)],
               'new_old_assignments':'At each stage, current group=new; groups already trained=old; unexposed=unlearned, not forgotten.',
               'interference_levels':{'low':'Different tool/output stage pairs (month count vs extraction), matched stage size.',
                 'medium':'Shared calendar_list with count vs field output.', 'high':'Shared calendar_list with location-vs-other-field or day/month routing conflicts.'},
               'assembly_requirements':'Factors are annotations/specifications only. Actual order/mixture sampling and matched budgets must be approved and frozen before any run; no causal interference claim from labels.'}
    products['continual_factors.json']=packed(sequences)
    products['coverage_expected.json']=packed({'totals':totals,'strata':matrices,'case_matrix':case_matrix,'skills':skills,'templates_per_case':template_counts})
    for name,b in products.items(): install(DATA/name,b)
    # B1 metric truth table: answer-only failures cannot disappear behind perfect call metrics.
    truth=[]
    for vals in itertools.product((False,True),repeat=4):
        r=dict(zip(('tool_correct','arguments_correct','execution_success','final_correct'),vals))
        assert joint_success(r)==all(vals);truth.append({**r,'joint_success':joint_success(r)})
    assert not joint_success(dict(tool_correct=True,arguments_correct=True,execution_success=True,final_correct=False))
    assert not any(m.split('.')[0] in ('torch','transformers','peft','bitsandbytes') for m in sys.modules)
    after=snapshot_sources();assert after==before,'Old protected files changed'
    install(RUN/'protected_sources_after.json',packed(after))
    audit=historical_audit();install(RUN/'historical_audit.json',packed(audit))
    frozen=[DATA/n for n in sorted(products)]+[Path(__file__),DATA/'source_reference.zip',ROOT/'P14_EVAL_PROTOCOL_20261119_ZH.md']
    assert all(p.exists() for p in frozen)
    manifest={'version':'P14-data-v1-20261119','timezone':'Asia/Shanghai','freeze_type':'protocol+data+CPU acceptance; NOT a training experiment',
              'files':{rel(p):{'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size} for p in frozen},
              'protected_source_snapshot_sha256':sha(prior.read_bytes()),'protected_source_files':len(before),
              'split_rows':totals,'blind_test_policy':'Test gold may be inspected by deterministic validation only, not method/threshold/checkpoint selection.'}
    install(DATA/'manifest.json',packed(manifest))
    digest=sha((DATA/'manifest.json').read_bytes());install(DATA/'manifest.sha256',(digest+'  manifest.json\n').encode())
    gpu_after=current_gpu()
    acceptance={'status':'PASS','cpu_only':True,'model_imports':False,'model_inference':False,'training':False,
                'split_rows':totals,'strata':matrices,'case_matrix':case_matrix,'skills':skills,
                'template_counts_per_case':template_counts,'split_overlap_counts':pair_checks,
                'tool_schema_and_execution_rows':sum(totals.values()),'independent_answer_oracle_rows':sum(totals.values()),
                'coverage_no_empty_feasible_cells':True,'replay_train_only':True,'replay_rows':totals['train'],
                'deterministic_regeneration_byte_identical':True,'metric_truth_table_cases':len(truth),
                'protected_source_files':len(before),'protected_sources_unchanged':True,'manifest_sha256':digest,
                'gpu_process_check_before':gpu_before,'gpu_process_check_after':gpu_after}
    install(RUN/'cpu_acceptance.json',packed(acceptance))
    install(RUN/'b1_metric_truth_table.json',packed(truth))
    print(canon({'status':'PASS','split_rows':totals,'manifest_sha256':digest,'old_protected_files_unchanged':len(before),'location_case_cells':len(CASES)}))
if __name__=='__main__': main()
