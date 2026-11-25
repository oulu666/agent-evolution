"""CPU regression/simulator tests only; never opens heldout files or model outputs."""
import copy,inspect,json,os,random,sys,time
from pathlib import Path
import core
from core import *
HERE=Path(__file__).resolve().parent
RESULTS=[]
def check(name,predicate):
    try:
        result=predicate() if callable(predicate) else predicate
        assert result,name
        RESULTS.append({'name':name,'passed':True})
    except Exception as e:RESULTS.append({'name':name,'passed':False,'error':repr(e)})
def raises(fn):
    try:fn();return False
    except (ValueError,AssertionError):return True

def regression_case(kind='distinct',intent='first'):
    values={'distinct':['oak','elm','ash'],'numeric':['9','line 9','room 9'],'duplicate':['same','same','same'],'empty':[]}[kind]
    base=[{'rid':'q'+str(i),'line':9+3*i,'text':s,'eligible':True} for i,s in enumerate(values)]
    vv={}
    for name in ('original',*POOL,'reserved'):
        rr=copy.deepcopy(base)
        if name in ['value','reserved']:
            mapping={s:'mapped_'+str(i) for i,s in enumerate(sorted(set(values)))}
            for r in rr:r['text']=mapping[r['text']]
        if name in ['line','reserved']:
            for r in rr:r['line']=2*r['line']+1
        if name in ['reverse','reserved']:rr.reverse()
        if name=='rotate' and rr:rr=rr[1:]+rr[:1]
        if name=='swap' and len(rr)>1:rr[0],rr[1]=rr[1],rr[0]
        vv[name]={'rows':rr,'observation':{'result':rr},'question':'Return complete text, null if empty.','certificate':{'legal':True}}
    return {'case_id':'reg_'+kind+'_'+intent,'question':'Return complete text, null if empty.','contract':{'intent':intent,'output_schema':{'allowed_types':['string','null']}},'views':vv}

def main():
    os.environ['TZ']='Asia/Shanghai';time.tzset();start=time.perf_counter()
    numeric=regression_case('numeric');rr=numeric['views']['original']['rows'];schema={'allowed_types':['string','null']}
    for raw in ['{"answer":9}','{"answer":"9"}','{"answer":"line 9"}']:
        b=behavior_observation(raw,rr);check('retain_raw_type_'+raw,b['raw']==raw and b['syntax']['value_type']==json_type(json.loads(raw)['answer']))
    check('integer_9_not_strict_text_9',not strict_score('{"answer":9}',schema,'9')['strict_correct'])
    check('string_9_strict_text_9',strict_score('{"answer":"9"}',schema,'9')['strict_correct'])
    check('line_prefix_not_strict_text_9',not strict_score('{"answer":"line 9"}',schema,'9')['strict_correct'])
    check('line_prefix_can_be_true_text',strict_score('{"answer":"line 9"}',schema,'line 9')['strict_correct'])
    b=behavior_observation('{"answer":"9"}',rr)
    check('numeric_text_line_collision_both',set(x['kind'] for x in b['interpretations'])=={'text','line'} and b['ambiguous'])
    b=behavior_observation('{"answer":"line 9"}',rr)
    check('line_literal_text_collision_both',set(x['kind'] for x in b['interpretations'])=={'text','line'} and b['ambiguous'])
    b=behavior_observation('{"answer":"room 9"}',rr)
    check('arbitrary_numeric_text_not_line',[x['kind'] for x in b['interpretations']]==['text'])
    for value in ['meeting 9','09','9 items','line 9 extra','-9','9.0']:
        b=behavior_observation(json.dumps({'answer':value}),rr)
        check('no_loose_digit_regex_'+value,not any(x['kind']=='line' for x in b['interpretations']))
    for value in [None,[],[9,12],{},True,9.0,'', 'null']:
        raw=json.dumps({'answer':value});b=behavior_observation(raw,rr)
        check('preserve_json_value_'+canonical(value),b['syntax']['value_type']==json_type(value) and canonical(b['update_value'])==canonical(value))
    check('null_for_empty_correct',strict_score('{"answer":null}',schema,None)['strict_correct'])
    check('string_null_not_empty_correct',not strict_score('{"answer":"null"}',schema,None)['strict_correct'])
    check('empty_text_not_null',strict_score('{"answer":""}',schema,'')['strict_correct'] and not strict_score('{"answer":""}',schema,None)['strict_correct'])
    for raw in ['Answer: {"answer":9}.','```json\n{"answer":9}\n```']:
        b=behavior_observation(raw,rr)
        check('wrapper_strict_fail_behavior_salvage_'+raw,not strict_score(raw,schema,'9')['strict_correct'] and b['update_value_available'] and b['envelopes'][0]['source']=='recovered_wrapper')
    for raw in ['{"answer":9','{answer:9}','{"answer":NaN}','{"answer":9,"answer":"9"}','{"outer":{"answer":9}']:
        b=behavior_observation(raw,rr)
        check('malformed_not_silently_normalized_'+raw,not b['syntax']['exact_answer_envelope'] and not b['update_value_available'])
    b=behavior_observation('{"answer":9} {"answer":12}',rr)
    check('multiple_answer_objects_no_update',b['ambiguous'] and not b['update_value_available'] and len(b['envelopes'])==2)
    check('extra_envelope_keys_strict_reject',not parse_syntax('{"answer":"9","reason":"x"}')['exact_answer_envelope'])
    duplicated=regression_case('duplicate');b=behavior_observation('{"answer":"same"}',duplicated['views']['original']['rows'])
    check('duplicate_text_row_identity_ambiguous',b['ambiguous'] and len(b['interpretations'][0]['row_ids'])==3)
    check('empty_signature_single_class',len(equivalence_classes(regression_case('empty')))==1)
    for kind in ['distinct','numeric','duplicate','empty']:
        for intent in ['first','last']:
            c=regression_case(kind,intent);validate_case(c);classes=equivalence_classes(c)
            check('signature_prior_normalized_'+c['case_id'],abs(sum(x['prior'] for x in classes)-1)<1e-12)
            check('duplicate_rules_do_not_reweight_'+c['case_id'],equivalence_classes(c,RULES+RULES)==classes)
            for rule in RULES:
                s=initial_state(c);s=update(s,c,'original',canonical({'answer':predict(rule,c['views']['original'],intent)}))
                for policy in ['fixed','random','gbs_gini','ig_per_byte_cost']:
                    state=copy.deepcopy(s)
                    for step in range(5):
                        v=next_query(state,c,policy,seed=17)
                        raw=canonical({'answer':predict(rule,c['views'][v],intent)})
                        state=update(state,c,v,raw)
                    # Positive closed-rule checks are behavioral oracle tests, not natural root-cause labels.
                    check('sim_'+c['case_id']+'_'+str(rule)+'_'+policy,any(rule in cl['members'] for cl in state['classes']) and canonical(predict(rule,c['views']['reserved'],intent)) in prediction_set(state,c))
    c=regression_case();s=initial_state(c)
    s=update(s,c,'original','{"answer":"OUTSIDE"}')
    check('unknown_does_not_force_class',not s['classes'] and diagnosis(s)['status']=='unknown_closed_library_mismatch')
    c=regression_case();s=update(initial_state(c),c,'original','{"answer":"oak"}')
    s=update(s,c,'reverse','{"answer":99999}')
    check('mixed_incompatible_reject',not s['classes'])
    c=regression_case();s=initial_state(c);new=update(s,c,'original','not JSON')
    check('unparsed_does_not_fabricate_negative',new['classes']==s['classes'] and diagnosis(new)['status']=='insufficient_parse_evidence')
    check('reserved_cannot_update',raises(lambda:update(initial_state(c),c,'reserved','{"answer":"oak"}')))
    bad=copy.deepcopy(c);bad['future_responses']={'reverse':'poison'}
    check('future_response_table_rejected',raises(lambda:initial_state(bad)))
    for k in ['gold','family','split','labels']:
        bad=copy.deepcopy(c);bad['contract'][k]='poison'
        check('private_key_rejected_'+k,raises(lambda:initial_state(bad)))
    for name in ['empty','bad_intent','duplicate_line']:
        bad=copy.deepcopy(c)
        if name=='bad_intent':bad['contract']['intent']='middle'
        elif name=='duplicate_line':bad['views']['original']['rows'][1]['line']=bad['views']['original']['rows'][0]['line']
        else:bad['contract']['output_schema']={'allowed_types':['integer']}
        check('unsupported_contract_'+name,raises(lambda:initial_state(bad)))
    # Equivalence is based on query domain; preserve different reserved predictions within one class.
    c=regression_case()
    for v in POOL:c['views'][v]=copy.deepcopy(c['views']['original'])
    c['views']['reserved']=copy.deepcopy(c['views']['original']);c['views']['reserved']['rows'].reverse()
    s=update(initial_state(c),c,'original','{"answer":"oak"}')
    check('equivalent_members_keep_reserved_uncertainty',len(prediction_set(s,c))>=2)
    for policy in ['fixed','random','gbs_gini','ig_per_byte_cost']:
        c=regression_case();s=initial_state(c);v=next_query(s,c,policy,seed=8)
        check('same_shared_public_information_'+policy,v in POOL and not s['observed'])
    src=inspect.getsource(core.next_query)
    check('selector_no_gold_or_filesystem_api',all(x not in src for x in ['strict_score','open(','Path(','future_responses','gold']))
    check('correct_is_behavioral_combination',('coordinate_intent','text','native') in RULES and len(RULES)==24)
    forbidden=[x for x in sys.modules if x.split('.')[0] in ['torch','transformers','peft','bitsandbytes']]
    check('no_model_modules_imported',not forbidden)
    failed=sum(not r['passed'] for r in RESULTS)
    report={'time':time.strftime('%Y-%m-%d %H:%M:%S %z'),'tests':len(RESULTS),'passed':len(RESULTS)-failed,'failed':failed,'elapsed_seconds':time.perf_counter()-start,'new_generations':0,'simulator_cases_are_not_natural_root_cause_gold':True,'heldout_files_opened':0,'results':RESULTS}
    path=HERE/'cpu_regression.json';assert not path.exists(),'no overwrite test evidence'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'},ensure_ascii=False))
    if failed:
        print(json.dumps([r for r in RESULTS if not r['passed']],ensure_ascii=False));raise SystemExit(1)
if __name__=='__main__':main()