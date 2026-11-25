"""CPU-only behavioral grammar. No file I/O, gold, model or checkpoint access."""
import copy,json,math,random,re
OPS=('coordinate_intent','coordinate_opposite','display_first','display_last','text_min','text_max')
RULES=tuple((o,p,e) for o in OPS for p,e in [('text','native'),('line','native'),('line','decimal_string'),('line','line_prefix')])
POOL=('reverse','rotate','swap','value','line')
FORBIDDEN={'gold','expected_answer','family','split','model_responses','future_responses','labels'}
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def json_type(x):
    if x is None:return 'null'
    if isinstance(x,bool):return 'boolean'
    if isinstance(x,str):return 'string'
    if isinstance(x,int):return 'integer'
    if isinstance(x,float):return 'number'
    if isinstance(x,list):return 'array'
    return 'object'
def _pairs(pairs):
    out={}
    for k,v in pairs:
        if k in out:raise ValueError('duplicate JSON key')
        out[k]=v
    return out
def _constant(x):raise ValueError('non-JSON constant '+x)
def parse_syntax(raw):
    out={'raw':raw,'whole_json':False,'exact_answer_envelope':False,'value':None,'value_type':None,'error':None}
    try:
        obj=json.loads(raw,object_pairs_hook=_pairs,parse_constant=_constant)
        out['whole_json']=True
        if not isinstance(obj,dict) or set(obj)!= {'answer'}:raise ValueError('require exactly one answer key')
        out.update(exact_answer_envelope=True,value=obj['answer'],value_type=json_type(obj['answer']))
    except (ValueError,TypeError) as e:out['error']=str(e)
    return out

def behavior_observation(raw,rows):
    # No question/intent/gold argument. Recognize ALL matching interpretations, never choose by gold.
    syntax=parse_syntax(raw);envelopes=[];confidence='unavailable';ambiguous_syntax=False
    if syntax['exact_answer_envelope']:
        envelopes=[{'value':syntax['value'],'type':syntax['value_type'],'source':'whole_json'}];confidence='exact_syntax_not_probability'
    elif not syntax['whole_json']:
        # Limited wrapper recovery: complete unique answer object only. Never regex-pick arbitrary digits.
        dec=json.JSONDecoder(object_pairs_hook=_pairs,parse_constant=_constant);found=[]
        for i,c in enumerate(raw):
            if c!='{':continue
            try:
                obj,n=dec.raw_decode(raw[i:])
                if isinstance(obj,dict) and set(obj)=={'answer'}:found.append((i,i+n,obj['answer']))
            except ValueError:pass
        if len(found)==1 and not any(c in raw[:found[0][0]]+raw[found[0][1]:] for c in '{}[]'):
            v=found[0][2];envelopes=[{'value':v,'type':json_type(v),'source':'recovered_wrapper'}];confidence='wrapper_recovery_lower_confidence_not_probability'
        elif len(found)>1:
            ambiguous_syntax=True;envelopes=[{'value':v,'type':json_type(v),'source':'multiple_objects'} for _,_,v in found]
    interpretations=[]
    for env in envelopes:
        value=env['value'];typ=env['type'];source=env['source']
        if typ=='null':interpretations.append({'kind':'null','value':None,'source':source,'lossy':False})
        if typ=='string':
            ids=[r['rid'] for r in rows if r['text']==value]
            if ids:interpretations.append({'kind':'text','value':value,'row_ids':ids,'source':source,'lossy':False})
        number=None;encoding=None
        if typ=='integer' and value>0:number=value;encoding='native'
        if typ=='string' and re.fullmatch(r'[1-9][0-9]*',value):number=int(value);encoding='decimal_string'
        if typ=='string' and re.fullmatch(r'line [1-9][0-9]*',value):number=int(value[5:]);encoding='line_prefix'
        if number is not None:
            ids=[r['rid'] for r in rows if r['line']==number]
            if ids:interpretations.append({'kind':'line','value':number,'row_ids':ids,'encoding':encoding,'original_value':value,'original_type':typ,'source':source,'lossy':typ=='string'})
    identifiable=len(interpretations)==1 and len(interpretations[0].get('row_ids',[]))<=1 and not ambiguous_syntax
    usable=len(envelopes)==1 and not ambiguous_syntax
    return {'raw':raw,'syntax':syntax,'envelopes':envelopes,'interpretations':interpretations,'confidence_label':confidence,'ambiguous':ambiguous_syntax or len(interpretations)>1 or any(len(x.get('row_ids',[]))>1 for x in interpretations),'identifiable_interpretation':identifiable,'update_value_available':usable,'update_value':envelopes[0]['value'] if usable else None,'status':'ambiguous_no_update' if ambiguous_syntax else 'observed' if usable else 'unparsed_no_update'}

def strict_score(raw,schema,gold):
    # Scorer only. Behavioral parsing does not call this and selector never receives gold.
    s=parse_syntax(raw);valid=bool(s['exact_answer_envelope'] and s['value_type'] in schema['allowed_types'])
    return {'syntax_valid':s['exact_answer_envelope'],'output_schema_valid':valid,'strict_correct':bool(valid and canonical(s['value'])==canonical(gold)),'value':s['value'],'value_type':s['value_type']}

def validate_case(case):
    if set(case)!= {'case_id','question','contract','views'}:raise ValueError('public case keys only')
    if case['contract']['intent'] not in ['first','last']:raise ValueError('unsupported operator')
    if case['contract']['output_schema']!= {'allowed_types':['string','null']}:raise ValueError('unsupported output schema')
    if set(case['views'])!= {'original',*POOL,'reserved'}:raise ValueError('fixed view set required')
    for name,v in case['views'].items():
        if set(v)!= {'rows','observation','question','certificate'}:raise ValueError('view data keys only')
        rr=v['rows'];assert len({r['rid'] for r in rr})==len(rr)
        assert len({r['line'] for r in rr})==len(rr)
        for r in rr:
            assert set(r)== {'rid','line','text','eligible'}
            assert isinstance(r['line'],int) and not isinstance(r['line'],bool) and r['line']>0
            assert isinstance(r['text'],str) and isinstance(r['eligible'],bool)
        assert v['certificate']['legal']
    def check(x):
        if isinstance(x,dict):
            if FORBIDDEN.intersection(x):raise ValueError('private labels or outputs in public case')
            for y in x.values():check(y)
        elif isinstance(x,list):
            for y in x:check(y)
    check(case)

def predict(rule,view,intent):
    op,projection,encoding=rule;rr=[r for r in view['rows'] if r['eligible']]
    if not rr:return None
    ordered=sorted(rr,key=lambda r:r['line']);i=0 if intent=='first' else -1
    if op=='coordinate_intent':r=ordered[i]
    elif op=='coordinate_opposite':r=ordered[-1 if i==0 else 0]
    elif op=='display_first':r=rr[0]
    elif op=='display_last':r=rr[-1]
    elif op in ['text_min','text_max']:
        # Coordinate tie-break is explicit; duplicate text does not imply known selected identity.
        r=sorted(rr,key=lambda r:(r['text'],r['line']))[0 if op=='text_min' else -1]
    else:raise ValueError(op)
    value=r[projection]
    if encoding=='native':return value
    if projection!='line':raise ValueError('unsupported encoding for projection')
    if encoding=='decimal_string':return str(value)
    if encoding=='line_prefix':return 'line '+str(value)
    raise ValueError(encoding)

def equivalence_classes(case,rules=RULES):
    # Exclude reserved response AND reserved input from prior signatures. Keep every member for reserved prediction.
    out={}
    for rule in rules:
        signature=canonical([predict(rule,case['views'][v],case['contract']['intent']) for v in ('original',*POOL)])
        out.setdefault(signature,[])
        if tuple(rule) not in out[signature]:out[signature].append(tuple(rule))
    return [{'signature':s,'members':sorted(m),'prior':1/len(out)} for s,m in sorted(out.items())]

def initial_state(case,rules=RULES):
    validate_case(case)
    return {'classes':equivalence_classes(case,rules),'observed':{},'unusable':{},'queries':[],'open_world':True}
def update(state,case,view_name,raw):
    assert view_name in ('original',*POOL),'reserved is scorer-only'
    if view_name in state['observed'] or view_name in state['unusable']:raise ValueError('already observed')
    ob=behavior_observation(raw,case['views'][view_name]['rows'])
    state=copy.deepcopy(state)
    if view_name!='original':state['queries'].append(view_name)
    if not ob['update_value_available']:
        state['unusable'][view_name]=ob;return state
    value=ob['update_value'];state['observed'][view_name]=ob
    state['classes']=[c for c in state['classes'] if canonical(predict(c['members'][0],case['views'][view_name],case['contract']['intent']))==canonical(value)]
    return state

def diagnosis(state):
    n=len(state['classes']);unusable=bool(state['unusable'])
    return {'status':'unknown_closed_library_mismatch' if n==0 else 'insufficient_parse_evidence' if unusable else 'compatible_class_not_proven_mechanism','class_count':n,'rule_count':sum(len(c['members']) for c in state['classes']),'open_world_unknown_always_possible':True,'unusable_observations':len(state['unusable'])}
def prediction_set(state,case,view_name='reserved'):
    return sorted({canonical(predict(h,case['views'][view_name],case['contract']['intent'])) for c in state['classes'] for h in c['members']})

def next_query(state,case,policy,seed=0,cost=None):
    # Only public candidate inputs + explicitly queried observations. No filesystem or response table API.
    available=[v for v in POOL if v not in state['queries']]
    if not available:raise ValueError('budget exhausted')
    if policy=='fixed':return available[0]
    if policy=='random':return random.Random(seed+len(state['queries'])*1009).choice(available)
    if policy not in ['gbs_gini','ig_per_byte_cost']:raise ValueError(policy)
    cc=state['classes']
    if not cc:return available[0]
    def score(v):
        groups={}
        for c in cc:
            y=canonical(predict(c['members'][0],case['views'][v],case['contract']['intent']));groups[y]=groups.get(y,0)+c['prior']
        den=sum(groups.values());pp=[x/den for x in groups.values()]
        if policy=='gbs_gini':return 1-sum(p*p for p in pp)
        entropy=-sum(p*math.log2(p) for p in pp)
        return entropy/(cost[v] if cost else len(canonical(case['views'][v]['observation']).encode('utf-8'))+128)
    return max(available,key=lambda v:(score(v),-POOL.index(v)))