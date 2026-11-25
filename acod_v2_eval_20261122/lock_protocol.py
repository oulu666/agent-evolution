"""Public-input-only analysis lock. No response-table or gold reads before collection."""
import copy,hashlib,importlib.metadata,json,os,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;V2=ROOT/'acod_v2_freeze_20261121'
sys.path.insert(0,str(V2))
from core import POOL,canonical,equivalence_classes,predict,validate_case
from interfaces import load_public,model_messages,selector_costs,AccessBoundaryError
os.environ['TZ']='Asia/Shanghai';time.tzset()
def now():return time.strftime('%Y-%m-%d %H:%M:%S %z')
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def save(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)
def append(p,x):
    with Path(p).open('a',encoding='utf-8') as f:f.write(json.dumps(x,ensure_ascii=False)+'\n');f.flush()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def rows(p):
    p=Path(p)
    return [] if not p.exists() else [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines() if s]
def transform_rows(case,name,source):
    rr=copy.deepcopy(source)
    if name=='value':
        mapping=case['views']['value']['certificate']['text_bijection']
        for r in rr:r['text']=mapping[r['text']]
    elif name=='line':
        for r in rr:r['line']=3*r['line']+5
        if rr:rr=rr[1:]+rr[:1] # Frozen line view also rotates display.
    elif name=='reverse':rr.reverse()
    elif name=='rotate':rr=rr[1:]+rr[:1] if rr else rr
    elif name=='swap':
        if len(rr)>1:rr[0],rr[1]=rr[1],rr[0]
    else:raise ValueError(name)
    return rr

def inspect_pairs(case):
    base=case['views']['original']['rows'];reserved=case['views']['reserved']['rows']
    mapping=case['views']['value']['certificate']['text_bijection']
    for name in POOL:assert canonical(transform_rows(case,name,base))==canonical(case['views'][name]['rows']),name
    triple=transform_rows(case,'value',base)
    for r in triple:r['line']=3*r['line']+5
    triple.reverse();assert canonical(triple)==canonical(reserved)
    exact=[];content_only=[]
    for a in POOL:
        for b in POOL:
            try:combo=transform_rows(case,b,transform_rows(case,a,base))
            except KeyError:continue
            if canonical(combo)==canonical(reserved):exact.append([a,b])
            elif canonical(sorted(combo,key=lambda r:r['rid']))==canonical(sorted(reserved,key=lambda r:r['rid'])):content_only.append([a,b])
    classes=equivalence_classes(case)
    reserved_splitting=[]
    for i,c in enumerate(classes):
        values={canonical(predict(h,case['views']['reserved'],case['contract']['intent'])) for h in c['members']}
        if len(values)>1:reserved_splitting.append({'class_index':i,'member_rules':c['members'],'reserved_prediction_count':len(values)})
    return {'case_id':case['case_id'],'row_count':len(base),'exact_two_factor_pairs_for_reserved':exact,'content_equal_but_display_context_differs':content_only,'paired_interaction_eligible':bool(exact),'reserved_algebra':'reverse_display ∘ pure_line(3*l+5) ∘ value_bijection','line_single_algebra':'rotate_left_display ∘ pure_line(3*l+5)','missing_reverse_value_single':'reserved also changes coordinates; it is not reverse∘value alone','pool_equivalence_classes':len(classes),'classes_splittable_by_reserved':reserved_splitting}

def verify():
    lock=read(HERE/'PROTOCOL_LOCK.json')
    for name,h in lock['source_hashes'].items():assert sha(HERE/name)==h,'Execution source changed '+name
    for name,h in lock['protected_hashes'].items():assert sha(ROOT/name)==h,'Protected asset changed '+name
    vm=read(V2/'manifest.json')
    for name,h in vm['hashes'].items():assert sha(V2/name)==h
    return lock

def lock():
    assert not (HERE/'PROTOCOL_LOCK.json').exists()
    assert sha(V2/'manifest.json')==(V2/'manifest.sha256').read_text().split()[0]
    vm=read(V2/'manifest.json')
    for name,h in vm['hashes'].items():assert sha(V2/name)==h
    for name,h in read(V2/'PRE_DATA_LOCK.json')['source_sha256'].items():assert sha(V2/name)==h
    public=load_public(V2/'data/heldout/public/cases.jsonl');assert len(public)==16
    try:load_public(V2/'data/heldout/scorer_only/gold.jsonl');raise RuntimeError('gold accepted')
    except AccessBoundaryError:pass
    plans=[]
    for c in public:
        pair=inspect_pairs(c)
        plans.append({'case_id':c['case_id'],'messages_sha256':{v:hashlib.sha256(canonical(model_messages(c,v)).encode()).hexdigest() for v in ('original',*POOL,'reserved')},'costs':selector_costs(c),'pair_inspection':pair})
    models=[];refs=read(ROOT/'runs_ext_p10_formal_prompt_20261117/model_receipts.json')
    for seed in [20261108,20261109]:
        p=read(ROOT/f'data_ext_p10_twoview_cpu_20261117/plan_seed{seed}.json');adapter=Path(p['reuse_ordinary_checkpoint']);h=sha(adapter/'adapter_model.safetensors')
        assert h==next(x['adapter_sha256'] for x in refs if x['seed']==seed)
        cfg=ROOT/f'runs_phase2/A_seed{seed}/config.json'
        models.append({'seed':seed,'adapter':str(adapter),'adapter_sha256':h,'adapter_config_sha256':sha(adapter/'adapter_config.json'),'source_config_sha256':sha(cfg),'model_name_or_path':read(cfg)['model_name_or_path']})
    protected=dict(read(V2/'legacy_before.json')['files'])
    for name,h in protected.items():assert sha(ROOT/name)==h
    for p in V2.rglob('*'):
        if p.is_file():protected[str(p.relative_to(ROOT))]=sha(p)
    for p in [ROOT/'fac_tinyagent/sft/evaluate.py',ROOT/'fac_tinyagent/sft/train.py',ROOT/'fac_tinyagent/sft/dataset.py',ROOT/'fac_tinyagent/replay_study.py',ROOT/'fac_tinyagent/p10_devdiagnosis_20261117.py']:
        protected[str(p.relative_to(ROOT))]=sha(p)
    for m in models:
        for name in ['adapter_model.safetensors','adapter_config.json']:
            p=Path(m['adapter'])/name;protected[str(p.relative_to(ROOT))]=sha(p)
    sources=[p for p in HERE.iterdir() if p.is_file() and p.suffix in ['.py','.md']]
    versions={name:importlib.metadata.version(name) for name in ['torch','transformers','peft','bitsandbytes']}
    item={'created':now(),'max_generation_attempts':224,'heldout_cases':16,'development_cases_evaluated':0,'views_per_case':7,'checkpoints':2,'models':models,'python':sys.version,'installed_package_versions':versions,'decode':{'B':1,'greedy':True,'use_cache':False,'max_new_tokens':128,'single_call_timeout_seconds':60,'supervisor_timeout_seconds':1500},'policies':['fixed','random','gbs_gini','ig_per_byte_cost'],'random_seeds':list(range(20)),'additional_query_budgets':[1,2,4],'fixed_response_table_not_online_policy_calls':True,'reserved_never_enters_selector_update':True,'gold_only_scorer_after_collection':True,'interaction_definition':{
        'full_pair_requirement':'shared original X, existing single views T1(X),T2(X), and reserved exactly T2(T1(X)) including row identity/content/coordinates/eligibility AND display order. Content equality alone is insufficient for display-sensitive behavior.',
        'strict_unit_eligibility':'Only exact complete pairs; all required outputs must have exact answer envelope and valid task schema. To count singles-normal/combo-failed, base and both singles must additionally be strictly correct using their OWN independent gold, and combo must be schema-valid but strictly wrong. Unparsed/invalid-schema outputs are separately counted, not relabeled normal.',
        'binary_interaction_contrast':'If a complete pair exists, z_v=1[strict_correct(v)], contrast=z_combo-z_T1-z_T2+z_original is descriptive per-unit only; no causal/statistical nonadditivity claim. If no complete pairs, strict interaction is NOT ESTIMABLE, not zero.',
        'behavior_layer':'Independently evaluate full-pool compatible classes and whether parsed reserved answer belongs to their union. This is fixed-library predictive consistency, NOT a paired interaction or hidden switching mechanism.',
        'missing_pairs':'No new queries/data/rules may be created to complete them in this run.'},'plans':plans,'protected_hashes':protected,'source_hashes':{p.name:sha(p) for p in sources},'no_natural_responses_seen_before_lock':True,'v2_manifest_sha256':sha(V2/'manifest.json')}
    save(HERE/'PROTOCOL_LOCK.json',item)
    print(json.dumps({'locked':True,'heldout_cases':16,'generation_cap':224,'complete_interaction_quads':sum(bool(p['pair_inspection']['exact_two_factor_pairs_for_reserved']) for p in plans),'protected_files':len(protected),'source_files':len(sources),'pool_classes_split_by_reserved':sum(len(p['pair_inspection']['classes_splittable_by_reserved']) for p in plans)},ensure_ascii=False))
if __name__=='__main__':lock()