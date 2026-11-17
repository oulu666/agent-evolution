from pathlib import Path
import collections,json,statistics,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fac_tinyagent.utils import read_json,read_jsonl,write_json
from fac_tinyagent.p81_diagnosis_20261116 import DATA,RUN,SEEDS,verify
from fac_tinyagent import p8_decision_data_20261115 as P8
mean=statistics.mean

def metrics(rs,fields):return {'n':len(rs),**{f:mean(float(r[f]) for r in rs) if rs else None for f in fields}}
def main():
    verify();manifest=read_json(DATA/'manifest.json');seen=read_json(DATA/'seen_train.json');allrows=[];complete=True
    counts={};exposure={}
    for seed in SEEDS:
        exposure[str(seed)]={'original_last_slots':sum(x.get('skill')=='file.search_last' for x in read_json(P8.source(seed))['items']),'decision_selected':dict(collections.Counter(r['skill'] for r in seen[str(seed)]))}
        for arm in ['original','decision']:
            p=RUN/f'seed{seed}_{arm}.jsonl';rs=read_jsonl(p) if p.exists() else []
            assert len(rs)==len({r['id'] for r in rs})
            want=len(seen[str(seed)])+(72 if arm=='decision' else 0);counts[f'{seed}_{arm}']={'actual':len(rs),'expected':want}
            complete &= len(rs)==want and (RUN/f'seed{seed}_{arm}_complete.json').exists();allrows+=rs
    fc={};sc={};tc={};pair={}
    for seed in SEEDS:
        fs=[r for r in allrows if r['seed']==seed and r['kind']=='file']
        for wording in ['natural','explicit_line']:
            for order in ['ascending','reversed']:
                for intent in ['first','last']:
                    rs=[r for r in fs if r['meta']['wording']==wording and r['meta']['presentation']==order and r['meta']['intent']==intent]
                    fc[f'{seed}/{wording}/{order}/{intent}']=metrics(rs,['correct','first_presented','min_line','max_line'])
                index={(r['meta']['case'],r['meta']['intent']):r for r in fs if r['meta']['wording']==wording and r['meta']['presentation']==order}
                pairs=[(index[(i,'first')],index[(i,'last')]) for i in range(6) if (i,'first') in index and (i,'last') in index]
                pair[f'{seed}/{wording}/{order}']={'n_pairs':len(pairs),'both_correct':mean(a['correct'] and b['correct'] for a,b in pairs) if pairs else None,'answer_changed':mean(a['predicted_answer']!=b['predicted_answer'] for a,b in pairs) if pairs else None}
        ss=[r for r in allrows if r['seed']==seed and r['kind']=='sql']
        for wording in ['natural','structured']:
            for op in ['sort','filter','filter_sort','filter_sort_tie']:
                rs=[r for r in ss if r['meta']['wording']==wording and r['meta']['operation']==op]
                sc[f'{seed}/{wording}/{op}']=metrics(rs,['tool_correct','arguments_correct','execution_success','semantic_execution','has_where','has_tie','has_limit'])
        for arm in ['original','decision']:
            for skill in ['file.search_first','file.search_last','db.filter_cmp_top']:
                rs=[r for r in allrows if r['seed']==seed and r['arm']==arm and r['kind']=='seen' and r['skill']==skill]
                tc[f'{seed}/{arm}/{skill}']=metrics(rs,['tool_correct','arguments_correct','execution_success','final_correct','joint_success'])
    archive=read_json(RUN/'p8_error_audit.json');ac={}
    for skill in ['file.search_last','db.filter_cmp_top']:
        rs=[r for r in archive if r['skill']==skill]
        ac[skill]=metrics(rs,['first','last','other'] if skill.startswith('file') else ['has_where','has_tie','has_limit','exact','execution'])
    usages=[u for r in allrows for u in r['usage']]
    costs={'generation_calls':len(usages),'input_tokens':sum(u['input_tokens'] for u in usages),'output_tokens':sum(u['output_tokens'] for u in usages),'generation_seconds':sum(u['generation_seconds'] for u in usages),'optimizer_steps':0,'planned_calls':manifest['planned_generation_calls']}
    if complete:assert costs['generation_calls']==costs['planned_calls']==272
    out={'complete':bool(complete),'counts':counts,'file_cells':fc,'file_pairs':pair,'sql_cells':sc,'seen_train':tc,'p8_archived_errors':ac,'actual_exposure':exposure,'costs':costs}
    write_json(RUN/'summary.json',out)
    print('COMPLETE',complete,'calls',len(usages));print('ARCHIVED',json.dumps(ac));print('EXPOSURE',json.dumps(exposure))
    if complete:
        for title,d in [('FILE',fc),('PAIRS',pair),('SQL',sc),('SEEN',tc)]:
            print(title)
            for k,v in d.items():print(k,json.dumps(v))
if __name__=='__main__':main()
