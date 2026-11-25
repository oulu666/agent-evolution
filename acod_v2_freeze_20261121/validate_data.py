"""Independent CPU schema/gold/transform validator. It never executes selectors on heldout."""
import copy,json,sys,time
from pathlib import Path
from core import POOL,canonical,validate_case
HERE=Path(__file__).resolve().parent

def unpack(observation):
    # Deliberately independent of build_data.render and original_answer.
    if set(observation)=={'result'}:return copy.deepcopy(observation['result'])
    if set(observation)=={'record_matches'}:
        result=[]
        for r in observation['record_matches']:
            assert set(r)=={'record_key','start_line','continuation_parts','included'}
            assert r['continuation_parts'] and all(isinstance(s,str) for s in r['continuation_parts'])
            result.append({'rid':r['record_key'],'line':r['start_line'],'text':'\n'.join(r['continuation_parts']),'eligible':r['included']})
        return result
    assert set(observation)=={'fragments','in_scope_fragments','display_order'}
    mapping={};sources=set()
    for f in observation['fragments']:
        assert f['fragment_key'] not in sources;sources.add(f['fragment_key'])
        assert isinstance(f['offset'],int) and f['offset']>=0
        for r in f['records']:
            assert r['record_key'] not in mapping and r['local_line']>0
            mapping[r['record_key']]={'rid':r['record_key'],'line':f['offset']+r['local_line'],'text':r['text'],'eligible':f['fragment_key'] in observation['in_scope_fragments']}
    assert set(observation['in_scope_fragments'])<=sources
    order=observation['display_order'];assert len(order)==len(set(order)) and set(order)==set(mapping)
    return [mapping[k] for k in order]

def independently_select(rr,intent):
    eligible=sorted([r for r in rr if r['eligible']],key=lambda r:r['line'])
    return None if not eligible else eligible[0 if intent=='first' else -1]['text']

def verify_case(case,gold,source):
    validate_case(case);assert gold['case_id']==case['case_id']
    original=unpack(case['views']['original']['observation'])
    assert canonical(original)==canonical(source['source_rows'])
    intent=case['contract']['intent'];g0=independently_select(original,intent)
    byid={r['rid']:r for r in original}
    checked=0
    for name,v in case['views'].items():
        rr=unpack(v['observation']);assert canonical(rr)==canonical(v['rows'])
        assert len({r['rid'] for r in rr})==len(rr) and set(r['rid'] for r in rr)==set(byid)
        cert=v['certificate'];mapping=cert['text_bijection']
        value=name in ['value','reserved'];line=name in ['line','reserved']
        if value:assert set(mapping)=={r['text'] for r in original} and len(set(mapping.values()))==len(mapping)
        else:assert mapping=={}
        for r in rr:
            old=byid[r['rid']]
            assert r['eligible'] is old['eligible']
            assert r['line']==(3*old['line']+5 if line else old['line'])
            assert r['text']==mapping.get(old['text'],old['text'])
            assert len(r['text'].split('\n'))==len(old['text'].split('\n'))
        assert cert['coordinate_map']==('3*l+5' if line else 'identity')
        assert cert['snapshot_changed']==(value or line)
        g=independently_select(rr,intent)
        assert canonical(g)==canonical(gold['answers'][name])
        assert canonical(g)==canonical(mapping.get(g0,g0))
        checked+=1
    return checked

def lines(path):return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s]
def main():
    start=time.perf_counter();groups=lines(HERE/'data/scorer_only/groups.jsonl');fixtures={x['fixture_id']:x for x in lines(HERE/'data/validator_only/source_fixtures.jsonl')}
    gm={x['case_id']:x for x in groups};ids={};counts={};checks=0;data={}
    for split,expected in [('development',8),('heldout',16)]:
        public=lines(HERE/'data'/split/'public/cases.jsonl');gold={x['case_id']:x for x in lines(HERE/'data'/split/'scorer_only/gold.jsonl')}
        assert len(public)==len(gold)==expected
        ids[split]={c['case_id'] for c in public};assert ids[split]==set(gold)
        data[split]=public
        for c in public:
            meta=gm[c['case_id']];assert meta['split']==split
            checks+=verify_case(c,gold[c['case_id']],fixtures[meta['fixture_id']]);counts[meta['family']]=counts.get(meta['family'],0)+1
    assert not ids['development'] & ids['heldout']
    df={x['fixture_id'] for x in groups if x['split']=='development'};hf={x['fixture_id'] for x in groups if x['split']=='heldout'};assert not df & hf
    dt={x['template'] for x in groups if x['split']=='development'};ht={x['template'] for x in groups if x['split']=='heldout'};assert not dt & ht and len(ht)==2
    recipe=json.loads((HERE/'data/recipe_manifest.json').read_text());aa=recipe['family_ancestry']
    assert set(aa['D_flat_explicit']).isdisjoint(aa['H_fragment_offsets_scope']) and set(aa['D_flat_explicit']).isdisjoint(aa['H_multiline_record_assembly'])
    assert len(set(recipe['builder_ast_sha256'].values()))==3
    # Independent negative validator cases; these are synthetic corruptions, not model-response methods.
    c=data['development'][2];meta=gm[c['case_id']];source=fixtures[meta['fixture_id']]
    gold=next(x for x in lines(HERE/'data/development/scorer_only/gold.jsonl') if x['case_id']==c['case_id'])
    negative=[]
    def reject(label,cc,gg=gold,ss=source):
        try:verify_case(cc,gg,ss)
        except (ValueError,AssertionError,KeyError,TypeError):negative.append({'name':label,'passed':True});return
        raise AssertionError('validator accepted corrupted '+label)
    bad=copy.deepcopy(c);bad['views']['value']['certificate']['text_bijection']={'wrong':'map'};reject('illegal_text_mapping',bad)
    bad=copy.deepcopy(c);bad['views']['line']['rows'][0]['line']+=1;reject('coordinate_receipt_mismatch',bad)
    bad=copy.deepcopy(c);bad['gold']='leaked';reject('private_label_in_public',bad)
    bad=copy.deepcopy(c);bad['views']['reverse']['rows'][0]['eligible']=not bad['views']['reverse']['rows'][0]['eligible'];reject('scope_mutation',bad)
    bad=copy.deepcopy(c);bad['views']['original']['rows'][1]['line']=bad['views']['original']['rows'][0]['line'];reject('duplicate_coordinates',bad)
    bad=copy.deepcopy(c);bad['views']['value']['certificate']['legal']=False;reject('uncertified_transform',bad)
    badgold=copy.deepcopy(gold);badgold['answers']['original']={'not':'a text answer'};reject('wrong_gold',copy.deepcopy(c),badgold)
    badsource=copy.deepcopy(source);badsource['source_rows']=[];reject('source_ancestry_mismatch',copy.deepcopy(c),gold,badsource)
    # Interfaces are process discipline, not a promise of encryption or permission isolation.
    from interfaces import load_public,model_messages,selector_costs,AccessBoundaryError
    try:load_public(HERE/'data/heldout/scorer_only/gold.jsonl');raise AssertionError('gold route accepted')
    except AccessBoundaryError:negative.append({'name':'gold_path_loader_rejected','passed':True})
    # Only development inputs enter interface smoke checks; no heldout selector or model-response use.
    for case in load_public(HERE/'data/development/public/cases.jsonl'):
        costs=selector_costs(case);assert set(costs)==set(POOL) and all(x>128 for x in costs.values())
        for v in case['views']:
            mm=model_messages(case,v)
            assert len(mm)==2 and mm[1]['content']==case['views'][v]['question']+'\nTOOL RESULT:\n'+canonical(case['views'][v]['observation'])
    assert not any(n.split('.')[0] in ['torch','transformers','peft','bitsandbytes'] for n in sys.modules)
    out={'time':time.strftime('%Y-%m-%d %H:%M:%S %z'),'passed':True,'failed':0,'case_checks':24,'view_checks':checks,'negative_checks':len(negative),'family_cases':counts,'case_id_overlap':0,'fixture_overlap':0,'template_overlap':0,'heldout_selector_executions':0,'heldout_response_reads':0,'new_model_generations':0,'gold_access':'validator only; no selector/model prompt routes','elapsed_seconds':time.perf_counter()-start,'negative_tests':negative}
    path=HERE/'data_validation.json';assert not path.exists();path.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(out,ensure_ascii=False))
if __name__=='__main__':main()