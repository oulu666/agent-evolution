"""Independent recipe roots; CPU data construction only. Never imports round1 code."""
import ast,copy,hashlib,json,os,random,sys,time
from pathlib import Path
from core import POOL,canonical,validate_case
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
SEED=2026112102
STRATA=('empty','distinct','numeric_text','duplicate')
def now():return time.strftime('%Y-%m-%d %H:%M:%S %z')
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def jsonl(p,rr):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:
        for r in rr:f.write(canonical(r)+'\n')
def historical_paths():
    out=set()
    for p in (ROOT/'acod_round1_20261121').rglob('*'):
        if p.is_file():out.add(p)
    # Reconcile every old reference already frozen in R1, including adapter/config hashes.
    r=read(ROOT/'acod_round1_20261121/manifest.json')
    for name in r['hashes']:out.add(ROOT/name)
    for name in ['P14_V2_REVISION_20261119_ZH.md','P14_EVAL_PROTOCOL_20261119_ZH.md','fac_tinyagent/p9_counterfactual_20261117.py','fac_tinyagent/p10_twoview_plan_20261117.py']:
        out.add(ROOT/name)
    for base in ['data_ext_p14_eval_protocol','data_ext_p14_eval_protocol_v2','data_ext_p9_counterfactual_20261117','data_ext_p10_twoview_cpu_20261117']:
        for p in (ROOT/base).rglob('*'):
            if p.is_file() and p.suffix in ['.json','.jsonl','.md','.py','.sha256']:out.add(p)
    return sorted(out)
def before():
    assert not (HERE/'legacy_before.json').exists()
    pp=historical_paths();save(HERE/'legacy_before.json',{'time':now(),'files':{str(p.relative_to(ROOT)):sha(p) for p in pp},'round1_file_list':sorted(str(p.relative_to(ROOT)) for p in (ROOT/'acod_round1_20261121').rglob('*') if p.is_file())})
    print('BASELINE_FILES',len(pp))
def unchanged():
    old=read(HERE/'legacy_before.json')
    assert old['round1_file_list']==sorted(str(p.relative_to(ROOT)) for p in (ROOT/'acod_round1_20261121').rglob('*') if p.is_file())
    for p,h in old['files'].items():assert sha(ROOT/p)==h,'Legacy changed '+p
    return len(old['files'])

def development_flat(stratum,rng):
    # Exposed-style development: explicit flat coordinates. No heldout content constructor used here.
    words={'empty':['dry','void'],'distinct':['copper','violet','amber'],'numeric_text':['9','line 9','room 9'],'duplicate':['echo','echo','tail']}[stratum]
    rr=[{'rid':'d_'+str(i),'line':9+7*i,'text':s,'eligible':stratum!='empty'} for i,s in enumerate(words)]
    return rr,'flat','Choose the {intent} included row by its original line coordinate; return its complete text. If no row is included, return JSON null.'

def heldout_fragment_assembly(stratum,rng):
    # New content recipe root H1: fragment-local coordinates + offsets + declared source scope.
    # No flat-file regex generator, calendar fixture, or R1 template imports.
    rr=[]
    for f in range(3):
        for j in range(2):
            l=20+f*41+j*8+rng.randrange(3)
            text=f'fragment payload {f}-{j} / '+rng.choice(['birch','quartz','maple'])
            if stratum=='numeric_text':text=['9','line 9','not line 9'][j if f==0 else 2]
            if stratum=='duplicate':text='repeated fragment text' if j==0 else 'fragment suffix'
            rr.append({'rid':f's{f}_{j}','line':l,'text':text,'eligible':stratum!='empty' and f in [0,2]})
    rng.shuffle(rr)
    return rr,'fragments','The snapshot contains fragment-local positions, fragment offsets, and a list of in-scope fragments. Reconstruct global positions (offset + local_line). Among only in-scope records, return the complete text at the {intent} global position. Display order is irrelevant. Return JSON null if the scope has no records.'

def heldout_continuation_records(stratum,rng):
    # New content recipe root H2: logical records spanning physical continuation lines.
    rr=[]
    for i in range(4):
        parts=[f'heading {rng.randrange(100,999)}',f'continuation {i}',rng.choice(['footer A','footer B'])]
        text='\n'.join(parts[:2+i%2])
        if stratum=='numeric_text':text=['9','line 9','there are 9 slots',''][i]
        if stratum=='duplicate' and i<3:text='same head\nsame continuation'
        rr.append({'rid':'r_'+str(i),'line':3+11*i+rng.randrange(2),'text':text,'eligible':stratum!='empty' and i!=1})
    rng.shuffle(rr)
    return rr,'records','The snapshot lists logical records, each with a starting physical line and ordered continuation_parts. Only records marked included are candidates. Return the complete text of the {intent} included record in source order, joining its parts with a single newline; do not return its start line. If none are included, return JSON null.'

def render(kind,rr):
    if kind=='flat':return {'result':copy.deepcopy(rr)}
    if kind=='records':return {'record_matches':[{'record_key':r['rid'],'start_line':r['line'],'continuation_parts':r['text'].split('\n'),'included':r['eligible']} for r in rr]}
    assert kind=='fragments'
    groups={}
    for r in rr:groups.setdefault(r['rid'].split('_')[0],[]).append(r)
    fragments=[];active=[]
    for group,items in sorted(groups.items()):
        assert len({r['eligible'] for r in items})==1
        if items[0]['eligible']:active.append(group)
        offset=min(r['line'] for r in items)-1
        fragments.append({'fragment_key':group,'offset':offset,'records':[{'record_key':r['rid'],'local_line':r['line']-offset,'text':r['text']} for r in sorted(items,key=lambda r:r['line'])]})
    return {'fragments':fragments,'in_scope_fragments':active,'display_order':[r['rid'] for r in rr]}

def original_answer(rr,intent):
    eligible=[r for r in rr if r['eligible']]
    if not eligible:return None
    return (min if intent=='first' else max)(eligible,key=lambda r:r['line'])['text']

def make_views(base,kind,question,intent):
    views={};reference={};original=original_answer(base,intent)
    for name in ('original',*POOL,'reserved'):
        rr=copy.deepcopy(base);mapping={};line_map={}
        if name in ['value','reserved']:
            texts=sorted({r['text'] for r in rr})
            mapping={s:'\n'.join(f'mapped_{len(texts)-i}_part{j}' for j,_ in enumerate(s.split('\n'))) for i,s in enumerate(texts)}
            assert len(set(mapping.values()))==len(texts)
            for r in rr:r['text']=mapping[r['text']]
        if name in ['line','reserved']:
            line_map={r['line']:3*r['line']+5 for r in rr}
            for r in rr:r['line']=line_map[r['line']]
        if name in ['reverse','reserved']:rr.reverse()
        if name in ['rotate','line'] and rr:rr=rr[1:]+rr[:1]
        if name=='swap' and len(rr)>1:rr[0],rr[1]=rr[1],rr[0]
        gold=original_answer(rr,intent)
        assert canonical(gold)==canonical(mapping.get(original,original))
        cert={'legal':True,'scope_membership_preserved':True,'coordinate_map':str('3*l+5' if line_map else 'identity'),'selection_order_preserved':True,'text_bijection':mapping,'preserves_record_part_count':True,'snapshot_changed':bool(mapping or line_map),'answer_relation':'text_bijection' if mapping else 'equal','unsupported':False}
        views[name]={'rows':rr,'observation':render(kind,rr),'question':question,'certificate':cert}
        reference[name]=gold
    return views,reference

def generate():
    assert (HERE/'legacy_before.json').exists();unchanged()
    assert not (HERE/'data').exists(),'No overwrite of frozen data'
    cases={'development':[],'heldout':[]};golds={'development':[],'heldout':[]};meta=[];fixtures=[]
    families=[('development','D_flat_explicit',development_flat,SEED+11),('heldout','H_fragment_offsets_scope',heldout_fragment_assembly,SEED+101),('heldout','H_multiline_record_assembly',heldout_continuation_records,SEED+211)]
    for split,family,fn,seed in families:
        rng=random.Random(seed)
        for s in STRATA:
            rr,kind,template=fn(s,rng)
            file_id=hashlib.sha256(f'{seed}:{s}:base'.encode()).hexdigest()[:18]
            fixture={'fixture_id':file_id,'source_recipe':fn.__name__,'source_kind':kind,'source_rows':rr}
            fixtures.append(fixture)
            for intent in ['first','last']:
                case_id=hashlib.sha256(f'{seed}:{s}:{intent}'.encode()).hexdigest()[:20]
                question=template.format(intent=intent)
                vv,gg=make_views(rr,kind,question,intent)
                case={'case_id':case_id,'question':question,'contract':{'intent':intent,'output_schema':{'allowed_types':['string','null']}},'views':vv}
                validate_case(case);cases[split].append(case)
                golds[split].append({'case_id':case_id,'answers':gg})
                meta.append({'case_id':case_id,'split':split,'family':family,'stratum':s,'fixture_id':file_id,'builder':fn.__name__,'template':template,'seed':seed})
    for split in cases:
        # Opaque identifiers and shuffled ordering prevent exposing family/stratum labels to selector.
        random.Random(SEED+len(split)).shuffle(cases[split])
        jsonl(HERE/'data'/split/'public'/'cases.jsonl',cases[split])
        jsonl(HERE/'data'/split/'scorer_only'/'gold.jsonl',golds[split])
    jsonl(HERE/'data'/'scorer_only'/'groups.jsonl',meta)
    jsonl(HERE/'data'/'validator_only'/'source_fixtures.jsonl',fixtures)
    tree=ast.parse(Path(__file__).read_text(encoding='utf-8'))
    asthash={n.name:hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest() for n in tree.body if isinstance(n,ast.FunctionDef)}
    recipe={'root_seed':SEED,'development_cases':8,'heldout_cases':16,'heldout_families':2,'base_fixtures_heldout':8,'strata':STRATA,'views_per_case':7,'size_rationale':'2 structurally distinct construction roots x4 correctness/ambiguity strata x2 paired intents; engineering coverage, not powered efficacy estimate','family_ancestry':{'D_flat_explicit':['development_flat'],'H_fragment_offsets_scope':['heldout_fragment_assembly'],'H_multiline_record_assembly':['heldout_continuation_records'],'historical_excluded':['P9 single-flat-file literal regex templates','P10 inherited P9 dev/formal','P14 Calendar count/pluck/unique templates','R1 simple flat regex/index construction']},'shared_utilities_not_content_ancestors':['canonical JSON','make_views transform engine','render observation transport'],'builder_ast_sha256':{name:asthash[name] for name in ['development_flat','heldout_fragment_assembly','heldout_continuation_records']},'claim_boundary':'construction-family-heldout under shared finite selection/projection semantics; normalized rows common IR. Not a new tool/OOD/general task-semantic independence claim. No proof of non-overlap with uninspected historical assets.','no_round1_imports':True}
    save(HERE/'data'/'recipe_manifest.json',recipe)
    print('GENERATED development=8 heldout=16 views=168; no model outputs')
if __name__=='__main__':
    os.environ['TZ']='Asia/Shanghai';time.tzset()
    if sys.argv[1]=='before':before()
    elif sys.argv[1]=='generate':generate()